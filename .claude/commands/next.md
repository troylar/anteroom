---
name: next
description: Prioritized work queue sorted by priority labels and VISION.md alignment
allowed-tools: Bash, Read, Grep, Glob, Task
---

# /next Skill

Show a prioritized work queue of open issues, sorted by priority labels and grouped by VISION.md direction areas.

## Usage

```
/next                      # Prioritized queue (excludes in-progress/blocked)
/next --all                # Include in-progress and blocked issues
/next --area knowledge     # Filter by vision direction area
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

### Step 2: Fetch Data (parallel)

**A — All open issues:**
```bash
gh issue list --state open --limit 100 --json number,title,labels,assignees,body
```

**B — VISION.md direction areas:**
Read `VISION.md` and extract the "Direction (Current)" section. Identify the 4 direction areas:
- Knowledge Management
- Deeper Agentic Capabilities
- Extensibility
- Developer Workflow

**C — In-progress and blocked issues:**
```bash
gh issue list --label "in-progress" --state open --json number,title,labels,assignees
gh issue list --label "blocked" --state open --json number,title,labels,assignees
```

### Step 3: Categorize Each Issue

For each open issue:

1. **Priority** — from `priority:*` labels:
   - `priority:critical` → Critical
   - `priority:high` → High
   - `priority:medium` → Medium
   - `priority:low` → Low
   - No priority label → Medium (default)

2. **Vision area** — keyword match the issue title and body against direction areas:
   - Knowledge: knowledge, notebook, document, note, search, embedding, RAG, memory
   - Agentic: agent, tool, MCP, loop, iteration, autonomous, skill, orchestration
   - Extensibility: MCP, plugin, config, integration, API, protocol, standard
   - Dev Workflow: CLI, test, lint, deploy, CI, DX, developer, workflow, skill
   - Other: anything that doesn't match

3. **Status:**
   - `in-progress` label → In Progress
   - `blocked` label → Blocked
   - `ready-for-review` label → Ready for Review
   - None → Ready

4. **Dependencies** — scan issue body for:
   - "depends on #N" / "blocked by #N" / "after #N" / "requires #N"
   - If the dependency issue is still OPEN, mark as a dependency

### Step 4: Filter

- Default: exclude issues with `in-progress`, `blocked`, or `ready-for-review` labels
- With `--all`: include everything
- With `--area <area>`: only show issues matching that vision area

### Step 5: Display Queue

Sort by priority tier (critical → high → medium → low), then by issue number within each tier. Group by vision area.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  📋 Work Queue
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  🔴 Critical
  (none — that's good)

  🟠 High
  (none)

📋 Knowledge Management
  🟡 #83 — Add knowledge notebook support
  🟡 #91 — Semantic search improvements
  🟢 #105 — Export notebooks to markdown

📋 Deeper Agentic Capabilities
  🟡 #95 — Subagent orchestration
  🟢 #110 — Tool chaining improvements

📋 Extensibility
  🟡 #88 — Custom MCP server templates

📋 Developer Workflow
  🟡 #102 — CI pipeline improvements
  🟢 #115 — Lint rule updates

📋 Other
  🟡 #120 — UI polish pass

────────────────────────────────────────────

  🔴 Critical: 0  🟠 High: 0  🟡 Medium: 6  🟢 Low: 3
  📊 Total: 9 issues ready to work

────────────────────────────────────────────
```

Priority indicators:
- 🔴 Critical
- 🟠 High
- 🟡 Medium (default for unlabeled)
- 🟢 Low

### Step 6: Recommend Next Item

Below the queue, highlight the recommended next item with rationale:

```
  ⭐ Recommended: #83 — Add knowledge notebook support
     Rationale: Highest priority in Knowledge Management,
     no dependencies, aligns with core product direction.

────────────────────────────────────────────
  👉 Next: /start-work 83
────────────────────────────────────────────
```

Recommendation logic:
1. Pick the highest priority issue that is not blocked and has no open dependencies
2. Prefer issues in the direction area with the most issues (active area of development)
3. Prefer issues with clear acceptance criteria in the body
4. If tied, prefer the lower issue number (older = waiting longer)

### Step 7: Show In-Progress/Blocked (if --all)

If `--all` was passed, add a section at the bottom:

```
📋 In Progress
  🔄 #128 — Handle stale auth cookies    → assigned to @troylar
  🔄 #130 — Canvas streaming             → assigned to @troylar

📋 Blocked
  🚫 #95 — Subagent orchestration        → blocked by #83
```

## Guidelines

- Always show `#N — title` for issue references (fetch title from the API response)
- Default view (no flags) should be actionable — only show issues you can start right now
- If there are 0 issues ready, say so and suggest `/triage --reassess` or `/new-issue`
- Priority indicators use colored circle emoji for quick scanning
- Keep the display compact — no issue bodies, just numbers + titles + labels
