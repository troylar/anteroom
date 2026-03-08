---
name: senior-review
description: AI senior reviewer sign-off for implementation plans and PRs
allowed-tools: Bash, Read, Edit, Grep, Glob, Task, WebFetch
---

# /senior-review Skill

Act as a senior software engineer reviewing an implementation plan (on an issue) or code changes (on a PR). Approve or request changes.

## Usage

```
/senior-review 83        # Review issue #83 (plan review)
/senior-review PR 85     # Review PR #85 (code review for deploy gate)
/senior-review           # Auto-detect: PR for current branch, or issue from branch name
```

## Workflow

### Step 0: Detect Target

Determine whether reviewing an **issue** (plan review) or a **PR** (deploy gate review):

- If argument starts with `PR` or `pr`: extract the PR number, set `mode = pr`
- If argument is a plain number: check if it's an issue with `needs-senior-review` label
  ```bash
  gh issue view <N> --json labels --jq '.labels[].name' | grep -q "needs-senior-review"
  ```
  - If yes: set `mode = issue`
  - If no: check if it's a PR number
    ```bash
    gh pr view <N> --json number 2>/dev/null
    ```
    - If yes: set `mode = pr`
    - If no: set `mode = issue` (default to plan review)
- If no argument: detect from current branch
  ```bash
  # Try PR first
  gh pr view --json number --jq '.number' 2>/dev/null
  # If no PR, extract issue number from branch name
  git branch --show-current | grep -oP 'issue-\K\d+'
  ```

---

## Issue Mode (Plan Review)

### Step I-1: Fetch Issue and Plan

```bash
gh issue view <N> --json number,title,body,labels,state,assignees
```

- If the issue doesn't have the `needs-senior-review` label, warn: "This issue hasn't been planned yet. Run `/plan-work <N>` first."
- If the issue already has `senior-approved`, warn: "Already approved. Re-review anyway?"
- Extract the implementation plan from the issue body (everything after `## Implementation Plan`)

### Step I-2: Review the Plan (parallel agents)

Launch parallel review agents:

**Agent A — Feasibility & Completeness (Sonnet):**
1. Read the implementation plan
2. Read `CLAUDE.md` for architecture context
3. Check:
   - [ ] Are all affected files identified? (grep for imports, references, call sites that the plan might miss)
   - [ ] Are the implementation steps in the right order? (dependencies between steps)
   - [ ] Are there missing steps? (DB migrations, config changes, CLAUDE.md updates)
   - [ ] Is the testing strategy sufficient? (covers happy path, error cases, edge cases)
   - [ ] Are breaking changes identified and handled?

**Agent B — Scope & Risk (Sonnet):**
1. Read the implementation plan and the original issue description
2. Read `VISION.md`
3. Check:
   - [ ] Does the plan scope match the issue scope? (not doing too much or too little)
   - [ ] Are there scope creep risks? (features not in the issue being added)
   - [ ] Are risks properly identified? (missing risks, underestimated complexity)
   - [ ] Is the phasing reasonable? (too much in one PR, or unnecessarily split)
   - [ ] Are there simpler alternatives the plan didn't consider?

**Agent C — Security & Architecture (Sonnet):**
1. Read the implementation plan
2. Read affected source files
3. Check:
   - [ ] Do changes to security-sensitive code note OWASP requirements?
   - [ ] Are new endpoints/tools properly gated (auth, CSRF, rate limiting)?
   - [ ] Does the architecture follow existing patterns? (no unnecessary abstractions)
   - [ ] Are new dependencies justified?
   - [ ] Is the data flow clear and consistent with the existing architecture?

### Step I-3: Evaluate and Decide

Aggregate findings from all agents. Categorize each finding:

- **Blocker**: Must be addressed before implementation can start. Plan has a gap that would lead to rework or bugs.
- **Suggestion**: Would improve the plan but not a showstopper. Can be addressed during implementation.
- **Note**: Observation for the implementer's awareness. No action required.

**Decision criteria:**
- **Approve** if: zero blockers. Suggestions and notes are fine.
- **Request changes** if: one or more blockers exist.

### Step I-4: Post Review and Update Labels

#### If Approved

```bash
gh label create "senior-approved" --color "0E8A16" --description "Senior reviewer has approved" --force
gh issue edit <N> --remove-label "needs-senior-review" --add-label "senior-approved"
```

Post an approval comment:

```bash
gh issue comment <N> --body "$(cat <<'COMMENT'
### Senior Review: Approved

<1-2 sentence summary of the plan's strengths>

**Suggestions** (address during implementation):
- <suggestion 1>
- <suggestion 2>

**Notes:**
- <note 1>

---
*Reviewed by AI senior reviewer via `/senior-review`*
COMMENT
)"
```

Omit the Suggestions or Notes sections if there are none.

#### If Changes Requested

Do NOT add the `senior-approved` label. Keep `needs-senior-review`.

Post a changes-requested comment:

```bash
gh issue comment <N> --body "$(cat <<'COMMENT'
### Senior Review: Changes Requested

**Blockers** (must address before implementation):

1. **<blocker title>**
   <explanation of the gap and what needs to change in the plan>

2. **<blocker title>**
   <explanation>

**Suggestions** (optional improvements):
- <suggestion>

---
*Reviewed by AI senior reviewer via `/senior-review`. Update the plan and re-run `/senior-review <N>` for re-evaluation.*
COMMENT
)"
```

### Step I-5: Report

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  🔍 Senior Review: #<N> — <title>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  📋 Plan reviewed: <N> steps across <N> files
  🔴 Blockers:      <N>
  🟡 Suggestions:   <N>
  🔵 Notes:         <N>

  Result:           ✅ APPROVED / ❌ CHANGES REQUESTED

<If approved:>
────────────────────────────────────────────
  ✅ Plan approved — ready to start work
  👉 Next: /start-work <N>
────────────────────────────────────────────

<If changes requested:>
────────────────────────────────────────────
  ❌ <N> blocker(s) must be addressed
  👉 Next: update the plan, then re-run /senior-review <N>
────────────────────────────────────────────
```

---

## PR Mode (Deploy Gate Review)

### Step P-1: Fetch PR

```bash
gh pr view <N> --json number,title,body,state,mergeable,labels,reviews,statusCheckRollup,commits,files
```

- If the PR is closed/merged, abort
- If the PR is a draft, abort
- If the PR already has `senior-approved` label, warn: "Already approved. Re-review anyway?"

### Step P-2: Review the PR (parallel agents)

**Agent A — Code Quality & Correctness (Sonnet):**
1. Read the full diff: `gh pr diff <N>`
2. Read modified source files for context
3. Check:
   - [ ] Logic correctness — off-by-one, null handling, type mismatches
   - [ ] Error handling — appropriate, not too broad, not swallowed
   - [ ] Resource management — files/connections closed, async context managers used
   - [ ] Concurrency safety — shared mutable state, race conditions
   - [ ] Edge cases — empty inputs, missing keys, boundary values

**Agent B — CI & Test Verification (Haiku):**
1. Check CI status:
   ```bash
   gh pr checks <N> --json name,state,conclusion
   ```
2. Check test coverage:
   - Are new functions covered by tests?
   - Do test names follow conventions?
   - Are edge cases tested?
3. Check for test-only changes that might mask issues

**Agent C — Security & Compliance (Sonnet):**
1. Read the diff for security-sensitive patterns
2. Check:
   - [ ] SQL parameterization (no string concatenation)
   - [ ] Input validation at system boundaries
   - [ ] Path traversal prevention
   - [ ] No hardcoded secrets
   - [ ] Auth/CSRF on new endpoints
   - [ ] Safe deserialization
   - [ ] Commit messages reference issues

### Step P-3: Evaluate and Decide

Same categorization as issue mode: **Blocker**, **Suggestion**, **Note**.

**Decision criteria:**
- **Approve** if: zero blockers, CI passing
- **Request changes** if: blockers exist or CI failing

### Step P-4: Post Review and Update Labels

#### If Approved

```bash
gh label create "senior-approved" --color "0E8A16" --description "Senior reviewer has approved" --force
gh pr edit <N> --remove-label "needs-senior-review" --add-label "senior-approved"
```

Post approval comment:

```bash
gh pr comment <N> --body "$(cat <<'COMMENT'
### Senior Review: Approved

<1-2 sentence summary>

**Suggestions:**
- <if any>

---
*Reviewed by AI senior reviewer via `/senior-review`. Ready for deploy.*
COMMENT
)"
```

#### If Changes Requested

```bash
gh pr comment <N> --body "$(cat <<'COMMENT'
### Senior Review: Changes Requested

**Blockers:**

1. **<title>**
   <explanation>

---
*Reviewed by AI senior reviewer via `/senior-review`. Address blockers and re-run `/senior-review PR <N>`.*
COMMENT
)"
```

### Step P-5: Report

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  🔍 Senior Review: PR #<N> — <title>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  📊 Changes:    <N> files, +<X> -<Y>
  🧪 CI:         ✅ passing / ❌ failing
  🔴 Blockers:   <N>
  🟡 Suggestions: <N>
  🔵 Notes:      <N>

  Result:        ✅ APPROVED / ❌ CHANGES REQUESTED

<If approved:>
────────────────────────────────────────────
  ✅ PR approved — ready to deploy
  👉 Next: /deploy
────────────────────────────────────────────

<If changes requested:>
────────────────────────────────────────────
  ❌ <N> blocker(s) must be addressed
  👉 Next: fix issues, then re-run /senior-review PR <N>
────────────────────────────────────────────
```

## Guidelines

- The senior reviewer is thorough but not pedantic — focus on things that would cause rework, bugs, or security issues
- Don't block on style preferences or minor naming choices
- Trust the implementer on domain decisions — flag concerns, don't dictate
- If the plan is mostly good with minor gaps, approve with suggestions rather than blocking
- Re-reviews after changes should focus on whether blockers were addressed, not re-review everything
