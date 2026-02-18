---
name: cleanup
description: Post-work cleanup — stale branches, orphaned worktrees, unclosed issues, stale labels
allowed-tools: Bash, Read, Grep, Glob, Task
---

# /cleanup Skill

Clean up stale branches, orphaned worktrees, unclosed issues, and stale labels after work is merged and deployed.

## Usage

```
/cleanup              # Show report and clean interactively
/cleanup --dry-run    # Show report only, no changes
```

## Workflow

### Step 1: Ensure Labels Exist

Create all lifecycle labels idempotently:

```bash
gh label create "priority:critical" --color "B60205" --description "Blocking other work" --force
gh label create "priority:high" --color "D93F0B" --description "Important, should be next" --force
gh label create "priority:medium" --color "FBCA04" --description "Standard priority" --force
gh label create "priority:low" --color "0E8A16" --description "Nice to have" --force
gh label create "in-progress" --color "6F42C1" --description "Actively being worked on" --force
gh label create "ready-for-review" --color "0075CA" --description "PR submitted" --force
gh label create "blocked" --color "9E9E9E" --description "Blocked by something" --force
```

### Step 2: Gather State (parallel)

Launch parallel operations to collect cleanup candidates:

**A — Stale local branches:**
```bash
git branch --list "issue-*"
```
For each branch, extract the issue number and check if the issue is CLOSED:
```bash
gh issue view <N> --json state --jq '.state'
```
A local branch is stale if its issue is CLOSED.

**B — Stale remote branches:**
```bash
git fetch --prune origin
git branch -r --list "origin/issue-*"
```
For each remote branch, check if there's a merged PR for it:
```bash
gh pr list --head "issue-<N>" --state merged --json number,title
```
A remote branch is stale if its PR was merged.

**C — Orphaned worktrees:**
```bash
git worktree list --porcelain
```
For each worktree (not the main one), check:
- Does the branch still exist? (`git branch --list <branch>`)
- Is the associated issue CLOSED?
A worktree is orphaned if the branch is gone or the issue is closed.

**D — Issues with stale labels:**
```bash
gh issue list --label "in-progress" --state closed --json number,title
gh issue list --label "ready-for-review" --state closed --json number,title
```
Closed issues should not have workflow labels.

**E — Open issues with stale in-progress label:**
```bash
gh issue list --label "in-progress" --state open --json number,title
```
For each, check if a corresponding branch exists:
```bash
git branch --list "issue-<N>-*" && git branch -r --list "origin/issue-<N>-*"
```
If no branch exists locally or remotely, the label is stale.

### Step 3: Reconcile Merged PRs with Open Issues

Find merged PRs whose closing issues are still OPEN:
```bash
gh pr list --state merged --limit 20 --json number,title,closingIssuesReferences
```
For each closing issue reference, check if the issue is still OPEN:
```bash
gh issue view <N> --json state --jq '.state'
```

### Step 4: Display Report

Always display the full report, formatted per output-formatting rules. For every issue reference, fetch and show the title alongside the number.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  🧹 Cleanup Report
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 Local Branches to Delete
  issue-83-knowledge-notebooks     → #83 — Add knowledge notebook support (CLOSED)
  issue-95-subagent-orchestration  → #95 — Subagent orchestration (CLOSED)

📋 Remote Branches to Prune
  origin/issue-83-knowledge-notebooks  → PR #100 — feat: knowledge notebooks (merged)
  origin/issue-95-subagent-orchestration → PR #110 — feat: subagent orchestration (merged)

📋 Worktrees to Remove
  ../parlor-83-knowledge-notebooks     → #83 — Add knowledge notebook support (CLOSED)

📋 Issues to Close
  #128 — Handle stale auth cookies     → merged via PR #135

📋 Stale Labels to Remove
  #91 — Search endpoint bug            → remove `in-progress` (issue closed)
  #102 — MCP integration               → remove `in-progress` (no branch exists)

────────────────────────────────────────────
  📊 Summary: N branches, N worktrees, N issues, N labels
────────────────────────────────────────────
```

If nothing to clean:
```
────────────────────────────────────────────
  ✅ Everything is clean — nothing to do
────────────────────────────────────────────
```

### Step 5: Check for Dry Run

If `--dry-run` was passed, stop here. Do not prompt for action.

### Step 6: Prompt for Action

If there are items to clean:

```
  Options:
    → Clean all — execute all cleanup actions
    → Pick categories — choose which categories to clean
    → Abort — do nothing
```

If "Pick categories," list each category and let the user choose which to execute.

### Step 7: Execute Cleanup

For each category the user approved:

**Local branches:**
```bash
git branch -D <branch>
```

**Remote branches:**
```bash
git push origin --delete <branch>
```

**Worktrees:**
```bash
git worktree remove <path> --force
```

**Issues to close:**
```bash
gh issue close <N> --comment "Closed by /cleanup — merged via PR #<PR>"
```

**Stale labels:**
```bash
gh issue edit <N> --remove-label "in-progress"
gh issue edit <N> --remove-label "ready-for-review"
```

### Step 8: Post-Cleanup Report

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✅ Cleanup Complete
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  🔀 Branches deleted:  N local, N remote
  📂 Worktrees removed: N
  📋 Issues closed:     N
  🏷️ Labels cleaned:    N

────────────────────────────────────────────
  👉 Next: /next to find your next task
────────────────────────────────────────────
```

## Guidelines

- Always show `#N — title` for issue references (fetch title with `gh issue view <N> --json title --jq '.title'`)
- Always show `PR #N — title` for PR references
- Never delete branches or worktrees without user confirmation (unless scripted)
- Be careful with `git worktree remove --force` — only use when the worktree's branch is confirmed gone or its issue is closed
- If a worktree has uncommitted changes, warn the user and skip it
