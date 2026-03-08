---
name: start-work
description: Begin work on an approved GitHub issue — create branch and worktree
allowed-tools: Bash, Read, Edit, Grep, Glob, Task
---

# /start-work Skill

Create a branch and worktree for an approved GitHub issue. The issue must have been planned (`/plan-work`) and approved (`/senior-review`) before work can begin.

## Usage

```
/start-work 83                  # Start work on approved issue #83 in a worktree
```

The argument is a GitHub issue number.

Work is **always** set up in a **git worktree** — a separate working directory linked to the same repo. This keeps the main checkout clean and lets you work on multiple features simultaneously without stashing. Never work directly on the main checkout.

## Workflow

### Step 1: Fetch and Validate the Issue

```bash
gh issue view <N> --json number,title,body,labels,state,assignees
```

- If the issue is closed, warn the user and ask if they want to proceed
- If the issue is assigned to someone else, warn the user

### Step 1c: Check Assignment and Status

Ensure lifecycle labels exist (idempotent):
```bash
gh label create "in-progress" --color "6F42C1" --description "Actively being worked on" --force
gh label create "ready-for-review" --color "0075CA" --description "PR submitted" --force
gh label create "blocked" --color "9E9E9E" --description "Blocked by something" --force
```

Check if the issue is already being worked on:

1. **Assignment check:** If the issue is assigned to someone else, warn:
   ```
   ⚠️ #<N> — <title> is assigned to @<user>. Continue anyway?
   ```

2. **Double-up check:** If the issue has the `in-progress` label, warn:
   ```
   ⚠️ #<N> — <title> is already marked as in-progress. Continue anyway?
   ```

3. If the user confirms, assign the issue and add the label:
   ```bash
   gh issue edit <N> --add-assignee @me --add-label "in-progress"
   ```

### Step 1d: Senior Review Gate (hard block)

Check if the issue has been planned and approved by a senior reviewer:

```bash
gh issue view <N> --json labels --jq '.labels[].name'
```

**If `senior-approved` label is present:** continue to Step 2.

**If `needs-senior-review` label is present (planned but not reviewed):**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ❌ Blocked: Senior Review Required
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Issue #<N> has been planned but not yet approved.
  A senior reviewer must sign off before work can begin.

────────────────────────────────────────────
  👉 Next: run /senior-review <N> to get sign-off
────────────────────────────────────────────
```
**Stop. Do not proceed.**

**If neither label is present (no plan exists):**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  📋 No plan found — running /plan-work first
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```
Auto-run `/plan-work <N>`. After `/plan-work` completes, display:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ❌ Blocked: Senior Review Required
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Plan created and issue updated. A senior reviewer
  must approve before work can begin.

────────────────────────────────────────────
  👉 Next: run /senior-review <N> to get sign-off,
           then re-run /start-work <N>
────────────────────────────────────────────
```
**Stop. Do not proceed.**

### Step 2: Check for Existing Work

Check if work has already started on this issue:

```bash
git branch --list "issue-<N>-*"
gh pr list --search "head:issue-<N>" --json number,title,state,headRefName
```

If a branch or PR already exists, show it and ask the user how to proceed:
- Continue on the existing branch
- Start fresh (new branch)
- Abort

### Step 3: Create Branch and Workspace

Generate a branch name from the issue:
- Format: `issue-<N>-<short-description>`
- `<short-description>`: 2-4 words from the issue title, kebab-case, max 50 chars total
- Example: issue #83 "Add knowledge notebook support" → `issue-83-knowledge-notebooks`

#### Create Worktree

Create a branch and set up a worktree in a sibling directory:

```bash
git fetch origin main
git branch issue-<N>-<description> origin/main
git worktree add ../<repo-name>-<N>-<short-description> issue-<N>-<description>
```

Create an isolated virtual environment and install dev dependencies in the worktree:
```bash
cd ../<repo-name>-<N>-<short-description> && python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]" -q
```

**IMPORTANT: Per-worktree venvs are required.** Editable installs (`pip install -e .`) are global to the Python interpreter — the last worktree to run it wins, and all other worktrees import from the wrong source tree. Each worktree MUST have its own `.venv` to prevent cross-contamination. All subsequent commands (`pytest`, `ruff`, etc.) in the worktree must use the worktree's venv (either activate it or use `.venv/bin/python`).

The worktree path follows the pattern: `../<repo-name>-<N>-<short-description>` (sibling to the main repo directory).
- Example: issue #95 "Add sub-agent orchestration" → `../anteroom-95-subagent-orchestration`
- The `<short-description>` matches the branch name suffix for easy identification

**IMPORTANT:** Never create a branch in the main checkout. Always use a worktree.

### Step 4: Report

Extract the implementation plan from the issue body (everything after `## Implementation Plan`) and display it.

Print:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  🚀 Ready to Work: #<N> — <title>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  🔀 Branch:     issue-<N>-<description>
  📂 Worktree:   ../<repo>-<N>-<description>
  👤 Assigned:   @<user>
  🏷️ Status:     in-progress
  ✅ Approved:   senior-approved

<The implementation plan from the issue body>

────────────────────────────────────────────
  👉 Next: cd ../<repo>-<N>-<description> and say "go",
           or adjust the plan
────────────────────────────────────────────
```

## Guidelines

- Don't start coding — this skill only sets up the branch and worktree
- The implementation plan from `/plan-work` is already in the issue body — display it for reference
- If the issue body has no implementation plan section, warn the user (this shouldn't happen if the workflow was followed)
- If the issue description is vague or missing acceptance criteria, flag what's unclear
