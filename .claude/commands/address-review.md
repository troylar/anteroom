---
name: address-review
description: Systematically address reviewer comments on a pull request
allowed-tools: Bash, Read, Edit, Grep, Glob, Task
---

# /address-review Skill

Fetch unresolved reviewer comments on a PR, categorize them, apply fixes, run checks, commit, push, and post a summary comment telling the reviewer exactly what changed.

Handles comments from both human reviewers and AI reviewers (e.g., `/code-review` output). AI review comments are parsed structurally for numbered issues with file:line references.

## Usage

```
/address-review              # Auto-detect PR for current branch
/address-review 815          # Address comments on PR #815
/address-review --dry-run    # Analyze comments but don't fix, commit, or push
/address-review --all        # Include resolved threads and previously addressed comments
```

## Workflow

### Step 0: Detect Worktree

Determine if we're running inside a git worktree:

```bash
WORKTREE_PATH=$(git rev-parse --show-toplevel)
MAIN_WORKTREE=$(git worktree list --porcelain | head -1 | sed 's/worktree //')
```

If `$WORKTREE_PATH` != `$MAIN_WORKTREE`, we are in a worktree. **All file reads, edits, and commands MUST use the worktree path, not the main checkout.** Display the worktree path in all reports.

### Step 1: Resolve PR and Context

If a PR number is provided as an argument, use it. Otherwise, detect the PR for the current branch:
```bash
gh pr view --json number,title,headRefName,baseRefName,state,url --jq '{number,title,headRefName,baseRefName,state,url}'
```

Abort if:
- No PR found for the current branch
- PR is closed or merged

Extract the issue number from the branch name (`issue-<N>-...`):
```bash
git branch --show-current
```

### Step 2: Fetch All Review Comments (parallel)

**A — Pull request review comments (inline code comments):**
```bash
gh api repos/{owner}/{repo}/pulls/<PR>/comments --paginate --jq '.[] | {id, path, line, original_line, diff_hunk, body, user: .user.login, created_at, in_reply_to_id, pull_request_review_id}'
```

**B — Pull request reviews (top-level review bodies):**
```bash
gh api repos/{owner}/{repo}/pulls/<PR>/reviews --jq '.[] | {id, state, body, user: .user.login, submitted_at}'
```

**C — Issue comments (general PR conversation):**
```bash
gh api repos/{owner}/{repo}/issues/<PR>/comments --jq '.[] | {id, body, user: .user.login, created_at}'
```

**D — Thread resolution status (GraphQL):**
```bash
gh api graphql -f query='
  query($owner:String!, $repo:String!, $pr:Int!) {
    repository(owner:$owner, name:$repo) {
      pullRequest(number:$pr) {
        reviewThreads(first:100) {
          nodes {
            id
            isResolved
            comments(first:10) {
              nodes { databaseId body author { login } }
            }
          }
        }
      }
    }
  }
' -f owner="{owner}" -f repo="{repo}" -F pr=<PR>
```

### Step 3: Filter and Deduplicate

1. **Exclude self-comments**: Filter out comments where `user` matches `gh api user --jq .login`.

2. **Exclude resolved threads** (unless `--all`): Match thread resolution status from GraphQL to REST API comment IDs via `databaseId`. Skip comments in resolved threads.

3. **Exclude previously addressed comments** (unless `--all`): Check for existing `/address-review` summary comments on the PR (contain "Review feedback addressed" AND "Generated with [Claude Code]"). Parse the "Addressed" table to identify comment numbers already handled. Skip those.

4. **Detect AI review comments**: Comments containing "### Code review" AND "Generated with [Claude Code]" are AI review output. Parse them structurally:
   - Extract numbered issues: `N. <emoji> <description>` with `File:`, `Detail:`, `Suggestion:` fields
   - Each numbered issue becomes a separate actionable item with its file:line reference
   - The AI review comment itself is not an "issue" — its individual findings are

5. **Group threaded replies**: For inline comments, group by `in_reply_to_id` to reconstruct threads. The root comment is the actionable item; replies provide additional context.

6. **Skip empty/praise**: Filter out reviews with empty bodies, "LGTM", approval-only reviews, and pure praise.

### Step 4: Categorize Comments

For each remaining comment (or extracted AI finding), classify:

| Category | Criteria | Action |
|----------|----------|--------|
| `code-fix` | Requests a specific code change, identifies a bug, incorrect logic | Auto-fix |
| `test-needed` | Requests a test, points out missing coverage | Auto-fix (add test) |
| `question` | Asks "why?", requests explanation, seeks clarification | Draft response |
| `suggestion` | Proposes alternative approach, optional improvement | Evaluate and decide |
| `nit` | Style, naming, formatting, minor preference | Auto-fix |

Classification approach:
- **AI review findings**: Use the category label from the AI comment (bug, security, CLAUDE.md, vision, docs) and map to `code-fix`
- **Human comments with code suggestions** (GitHub suggestion blocks): `code-fix`
- **Comments containing** "fix", "bug", "broken", "wrong", "incorrect", "should be", "must be" → `code-fix`
- **Comments containing** "test", "coverage", "assert", "verify" → `test-needed`
- **Comments containing** "why", "?", "curious", "explain" → `question`
- **Comments containing** "consider", "maybe", "alternatively", "nit:", "optional" → `suggestion` or `nit`
- **Ambiguous**: default to `suggestion` (requires human judgment)

### Step 5: Display Analysis

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  📬 Review Comments — PR #<N>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  📂 Worktree:   <worktree path> (or "main checkout" if not in a worktree)
  🔗 PR:         #<N> — <title>
  👤 Reviewers:   <list of unique comment authors>
  💬 Comments:    <total> total, <filtered> actionable
  ⏭️ Skipped:     <resolved> resolved, <self> self, <addressed> previously addressed

📋 Code Fixes (<count>)
  1. 🔧 <file>:<line> — <brief summary of requested change>
     Reviewer: @<user>
     Comment: "<first 120 chars of comment>"

📋 Tests Needed (<count>)
  2. 🧪 <file or module> — <what test is needed>
     Reviewer: @<user>

📋 Questions (<count>)
  3. ❓ <file>:<line> — <question summary>
     Reviewer: @<user>

📋 Suggestions (<count>)
  4. 💡 <file>:<line> — <suggestion summary>
     Reviewer: @<user>

📋 Nits (<count>)
  5. ✏️ <file>:<line> — <nit description>
     Reviewer: @<user>

────────────────────────────────────────────
  🔧 Auto-fixable: <count> (code-fix + test-needed + nit)
  🧠 Needs judgment: <count> (question + suggestion)
────────────────────────────────────────────
```

If `--dry-run` was passed, stop here.

### Step 6: Address Auto-fixable Comments

For each `code-fix`, `test-needed`, and `nit` comment, in order:

1. **Read the relevant code**: Read the file at the referenced path and line. Read enough context (at least 50 lines around the target) to understand the function/class.

2. **Understand the request**: Parse the reviewer's comment to understand exactly what change is needed. If the comment includes a GitHub suggestion block, extract the suggested code.

3. **Apply the fix**:
   - For code fixes: modify the source file
   - For test additions: create or modify the appropriate test file (`tests/unit/test_<module>.py`)
   - For nits: apply the formatting/naming/style change

4. **Track the change**: Record `{comment_id, category, file, description_of_fix}` for the summary.

### Step 7: Evaluate Suggestions

For each `suggestion` comment:

1. Read the relevant code and the suggestion.
2. Evaluate whether the suggestion improves the code:
   - Does it reduce complexity?
   - Does it align with project patterns in CLAUDE.md?
   - Does it have security implications?
3. If clearly beneficial, apply it and record as "accepted."
4. If it requires human judgment, record as "deferred" with a brief rationale.

Display inline:
```
  💡 Suggestion #4: <summary>
     ✅ Accepted — <reason>
     — or —
     ⏸️ Deferred — <reason, for human to decide>
```

### Step 8: Draft Question Responses

For each `question` comment:

1. Read the relevant code to understand the implementation decision.
2. Draft a concise answer (2-4 sentences max).
3. Display the draft for user review.

```
  ❓ Question #3: <question summary>
     Draft: "<the drafted answer>"
```

Ask the user: "Review the drafted responses above. Edit any, or say 'go' to proceed."

If the user provides edits, incorporate them. If the user says "go", proceed.

### Step 9: Run Checks

After all fixes are applied:

```bash
ruff check --fix src/ tests/ 2>&1 | tail -20
ruff format src/ tests/ 2>&1 | tail -20
pytest tests/unit/ -x -q 2>&1 | tail -40
```

**Worktree detection**: If `.venv/` exists, prefix with `.venv/bin/`:
```bash
.venv/bin/ruff check --fix src/ tests/
.venv/bin/python -m pytest tests/unit/ -x -q
```

If tests fail due to review fixes, fix and re-run. If failures are pre-existing, note in summary but don't block.

### Step 10: Stage and Commit

Stage only files modified to address review comments:
```bash
git add <specific files>
```

Never use `git add -A` or `git add .`.

Commit:
```bash
git commit -m "$(cat <<'EOF'
fix(<scope>): address review feedback (#<issue>)

<one-line summary per addressed comment>

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

Scope: use the module with the most changes. Type: `fix` for code-fix/test-needed, `refactor` if only nits/suggestions.

### Step 11: Push

```bash
git push
```

If push fails due to remote changes:
```bash
git pull --rebase origin $(git branch --show-current)
git push
```

### Step 12: Post Summary Comment

The summary comment is the reviewer's guide to the fix commit. It must be detailed enough that the reviewer can verify each fix without re-reading the entire diff. Optimize for reviewer efficiency: link each fix back to the original comment, explain the approach, and call out anything that warrants re-review.

```bash
gh pr comment <PR> --body "$(cat <<'EOF'
### Review feedback addressed

Addressed comments from @<reviewer1>, @<reviewer2>.

**Commit:** <short SHA> `fix(<scope>): address review feedback (#<issue>)`

#### Addressed

| # | Category | File | Original Comment | What Changed |
|---|----------|------|-----------------|--------------|
| 1 | 🔧 Fix | `path/file.py:L42` | @reviewer: "<first 80 chars of their comment>" | <Detailed description of the fix: what was wrong, what the fix does, and why this approach was chosen. e.g., "Eliminated redundant `list_messages()` call by refactoring `_load_conversation_messages()` to return `(ai_messages, stored_messages)` tuple. All 5 call sites updated to unpack. Saves one full DB round-trip on every conversation resume."> |
| 2 | 🧪 Test | `tests/unit/test_foo.py` | @reviewer: "<comment>" | <What test was added and what it verifies. e.g., "Added `test_fork_preserves_metadata` — creates message with metadata, forks conversation, verifies metadata survives the fork via `list_messages()` on the forked conversation."> |
| 3 | ✏️ Nit | `path/file.py:L15` | @reviewer: "<comment>" | <What was changed. e.g., "Renamed `data` to `metadata_json` for clarity"> |
| 4 | 💡 Accepted | `path/file.py:L88` | @reviewer: "<suggestion>" | <Why accepted and what was done. e.g., "Added defensive `try/catch` around `JSON.parse(msg.metadata)` to match the Python-side graceful fallback pattern in `list_messages()`."> |

#### File Change Summary

For each file modified in the fix commit, describe what changed and why:

| File | Changes |
|------|---------|
| `src/anteroom/cli/repl.py` | <e.g., "Refactored `_load_conversation_messages()` return type from `list[dict]` to `tuple[list[dict], list[dict]]` to expose raw stored messages. Updated all 5 call sites. Eliminates redundant DB query on resume path."> |
| `src/anteroom/static/js/chat.js` | <e.g., "Wrapped metadata JSON.parse in try/catch block (line 1980). Malformed metadata now silently skips rendering instead of throwing."> |

#### Responses

**@<reviewer> asked** (<file>:<line>): "<full question text>"
> <Detailed answer with code references. e.g., "The `fork_conversation()` function uses a raw SQL `SELECT *` (line 622), which returns `metadata` as the original TEXT column value — already a valid JSON string. It does NOT go through `list_messages()` which would deserialize it. So `msg.get('metadata')` returns a JSON string, and inserting it directly into the new row is correct. `copy_conversation_to_db()` uses `list_messages()` which DOES deserialize, hence the `json.dumps()` call there. The asymmetry is intentional.">

#### Deferred

| # | Category | File | Original Comment | Reason |
|---|----------|------|-----------------|--------|
| 5 | 💡 Suggestion | `path/file.py:L120` | @reviewer: "<suggestion>" | <Why deferred with full context. e.g., "Rendering RAG sources out of message order on resume is a valid UX concern, but fixing it requires refactoring the resume display pipeline which is out of scope for this PR. The current behavior shows sources before the conversation — functional but not ideal. Created follow-up issue #NNN."> |

#### Verification

The reviewer can verify these fixes by:
- <e.g., "Checking that `_load_conversation_messages()` now returns a tuple at line 200-207">
- <e.g., "Confirming all 5 call sites unpack with `_, stored = ...` or `messages, _ = ...`">
- <e.g., "Searching for `JSON.parse` in chat.js to verify the try/catch wrapping">

#### Checks

- 🧪 Tests: <N> passed, <M> skipped
- 🔍 Lint: ✅ clean
- 📝 Format: ✅ clean

---
Generated with [Claude Code](https://claude.ai/code)
EOF
)"
```

Omit "Responses" if no questions. Omit "Deferred" if nothing deferred. Omit "Verification" for trivial changes (single nit fixes).

### Step 13: Resolve Addressed Threads

For inline comments addressed with code fixes or nits, resolve the review threads:

```bash
gh api graphql -f query='
  mutation($threadId:ID!) {
    resolveReviewThread(input:{threadId:$threadId}) {
      thread { isResolved }
    }
  }
' -f threadId="<thread_node_id>"
```

Only resolve `code-fix` and `nit` threads. Do not resolve `question` or `suggestion` threads — the reviewer should confirm those.

### Step 14: Final Report

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✅ Review Feedback Addressed — PR #<N>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  📂 Worktree:    <worktree path> (or "main checkout" if not in a worktree)
  🔗 PR:          #<N> — <title>
  🌐 URL:         <PR URL>
  💬 Processed:   <count> comments from <count> reviewers
  🔧 Fixed:       <count> (code fixes + tests + nits)
  💡 Accepted:    <count> suggestions
  ❓ Responded:   <count> questions
  ⏸️ Deferred:    <count> (needs human decision)
  🧪 Tests:       ✅ <N> passed
  📝 Commit:      <short SHA>

────────────────────────────────────────────
  👉 Next: wait for re-review,
           or /address-review again after new comments
────────────────────────────────────────────
```

## Multiple Review Rounds

This skill is designed to be run repeatedly:

1. Each invocation checks for prior `/address-review` summary comments
2. Parses the "Addressed" table to skip already-handled comments
3. Only processes new/unresolved comments (unless `--all`)
4. Posts a new summary comment (preserving review history)

## Guidelines

- **Worktree venv**: Use `.venv/bin/python -m pytest` and `.venv/bin/ruff` when in a worktree
- Never commit with failing tests unless failures are pre-existing
- Never use `git add -A` or `git add .` — always add specific files
- Never resolve threads for questions or suggestions — only for direct code fixes and nits
- If a comment references code that no longer exists, note as "N/A — code no longer present"
- If a reviewer's comment is ambiguous, classify as `suggestion` and defer
- Use `gh` for all GitHub interactions
- Respect the commit format: `type(scope): description (#issue)`
- AI reviewer comments with structured findings (numbered issues with file:line) are parsed into individual actionable items, not treated as a single comment
