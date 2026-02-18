---
name: triage
description: Set or reassess priority on issues against VISION.md
allowed-tools: Bash, Read, Grep, Glob, Task
---

# /triage Skill

Set priority on individual issues or reassess all open issues against VISION.md.

## Usage

```
/triage 83 high                          # Set priority on issue #83
/triage 83 critical                      # Set critical priority
/triage 83 medium                        # Set medium priority
/triage 83 low                           # Set low priority
/triage 83 blocked "waiting on #95"      # Mark as blocked with reason
/triage 83 unblock                       # Remove blocked label
/triage --reassess                       # Full reassessment of all open issues
```

## Workflow — Single Issue Mode

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

### Step 2: Fetch Issue Details

```bash
gh issue view <N> --json number,title,labels,body,state,assignees
```

If the issue is closed, warn the user and ask if they want to proceed.

### Step 3: Update Priority

If setting a priority (critical/high/medium/low):

1. Remove all existing `priority:*` labels:
   ```bash
   gh issue edit <N> --remove-label "priority:critical" --remove-label "priority:high" --remove-label "priority:medium" --remove-label "priority:low"
   ```
2. Add the new priority label:
   ```bash
   gh issue edit <N> --add-label "priority:<level>"
   ```

If marking as blocked:

1. Add the `blocked` label:
   ```bash
   gh issue edit <N> --add-label "blocked"
   ```
2. Add a comment with the reason:
   ```bash
   gh issue comment <N> --body "🚫 Marked as blocked: <reason>"
   ```

If unblocking:

1. Remove the `blocked` label:
   ```bash
   gh issue edit <N> --remove-label "blocked"
   ```
2. Add a comment:
   ```bash
   gh issue comment <N> --body "✅ Unblocked"
   ```

### Step 4: Report Change

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  🏷️ Triage: #<N> — <title>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Previous:  🟡 medium
  Updated:   🟠 high

────────────────────────────────────────────
  👉 Next: /next to see the updated queue
────────────────────────────────────────────
```

---

## Workflow — Reassess Mode (`--reassess`)

### Step 1: Ensure Labels Exist

Same as single issue mode — create all 7 labels idempotently.

### Step 2: Fetch All Data (parallel)

**A — All open issues:**
```bash
gh issue list --state open --limit 100 --json number,title,labels,body,assignees
```

**B — VISION.md:**
Read `VISION.md` and extract:
- Core principles
- Direction areas (Knowledge, Agentic, Extensibility, Dev Workflow)
- Negative guardrails ("What Anteroom Is Not")

**C — Recent activity:**
```bash
gh issue list --state closed --limit 20 --json number,title,labels,closedAt
```

### Step 3: Evaluate Each Issue

Launch a Sonnet agent to evaluate all open issues against VISION.md. For each issue, determine:

1. **Vision alignment** — which direction area does it support? Does it conflict with any guardrails?
2. **Type** — bug (security, functional, UX), enhancement, refactor, documentation, testing
3. **Impact** — how many users/use cases does this affect?
4. **Effort** — rough estimate (small/medium/large) based on issue description
5. **Dependencies** — does it depend on or block other issues?
6. **Suggested priority:**
   - **Critical** — security bugs, data loss, blocking other work
   - **High** — bugs affecting core functionality, features in the current sprint direction
   - **Medium** — enhancements aligned with vision, non-blocking improvements
   - **Low** — nice-to-haves, cosmetic, future-looking

### Step 4: Display Proposed Changes

Show a table of all issues with current and proposed priorities:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  🏷️ Triage Reassessment
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

| #   | Title                              | Current | Proposed | Area         | Rationale                    |
|-----|-------------------------------------|---------|----------|--------------|------------------------------|
| 83  | Add knowledge notebook support      | —       | 🟠 high  | Knowledge    | Core direction, high demand  |
| 91  | Semantic search improvements        | —       | 🟡 medium| Knowledge    | Enhancement, not blocking    |
| 95  | Subagent orchestration              | —       | 🟠 high  | Agentic      | Enables tool chaining        |
| 102 | CI pipeline improvements            | —       | 🟡 medium| Dev Workflow | Quality of life              |
| 105 | Export notebooks to markdown        | —       | 🟢 low   | Knowledge    | Nice to have                 |
| 110 | Tool chaining improvements          | 🟡 medium| 🟡 medium| Agentic      | (no change)                  |

────────────────────────────────────────────
  📊 Changes: N priorities to set, M unchanged
────────────────────────────────────────────
```

### Step 5: Prompt for Action

```
  Options:
    → Apply all — set all proposed priorities
    → Pick — choose which changes to apply
    → Skip — don't change anything
```

### Step 6: Apply Changes

For each approved change:

1. Remove existing `priority:*` labels
2. Add the new `priority:<level>` label
3. Track changes for the summary

### Step 7: Update ROADMAP.md (optional)

After applying changes, ask:

```
  Update ROADMAP.md with the new priorities? (y/n)
```

If yes, regenerate `ROADMAP.md` based on current issue state (see ROADMAP.md structure below).

### Step 8: Summary Report

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✅ Triage Complete
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  🔴 Critical:  N issues
  🟠 High:      N issues
  🟡 Medium:    N issues
  🟢 Low:       N issues
  📖 ROADMAP:   updated / skipped

────────────────────────────────────────────
  👉 Next: /next to see the prioritized queue
────────────────────────────────────────────
```

---

## ROADMAP.md Generation

When generating or updating `ROADMAP.md`, use this structure:

```markdown
# Anteroom Roadmap

Aligned with [VISION.md](VISION.md). Updated YYYY-MM-DD.

## Critical
- [ ] #N — title

## Knowledge Management

### High
- [ ] #N — title

### Medium
- [ ] #N — title

### Low
- [ ] #N — title

## Deeper Agentic Capabilities

### High
- [ ] #N — title

### Medium
- [ ] #N — title

### Low
- [ ] #N — title

## Extensibility

### High
- [ ] #N — title

### Medium
- [ ] #N — title

### Low
- [ ] #N — title

## Developer Workflow

### High
- [ ] #N — title

### Medium
- [ ] #N — title

### Low
- [ ] #N — title

## Other

### High
- [ ] #N — title

### Medium
- [ ] #N — title

### Low
- [ ] #N — title
```

Rules:
- Omit empty sections and subsections
- Critical issues go in a top-level section regardless of area
- Use checkbox format so progress is visible at a glance
- Header shows the last-updated date
- Only include OPEN issues

## Guidelines

- Always show `#N — title` for issue references
- Priority indicators: 🔴 Critical, 🟠 High, 🟡 Medium, 🟢 Low
- In reassess mode, the Sonnet agent should be thorough but not over-triage — when in doubt, suggest medium
- Don't change priorities on issues that are `in-progress` unless the user specifically targets them
- Blocked issues keep their priority label — `blocked` is a status, not a priority
