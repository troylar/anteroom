---
name: plan-work
description: Explore codebase and create implementation plan for a GitHub issue
allowed-tools: Bash, Read, Edit, Grep, Glob, Task
---

# /plan-work Skill

Explore the codebase and create a detailed implementation plan for a GitHub issue, then update the issue body with the plan.

## Usage

```
/plan-work 83        # Plan work for issue #83
```

The argument is a GitHub issue number.

## Workflow

### Step 1: Fetch and Validate the Issue

```bash
gh issue view <N> --json number,title,body,labels,state,assignees
```

- If the issue is closed, warn the user and ask if they want to proceed
- If the issue already has the `senior-approved` label, inform the user and ask if they want to re-plan (this will remove the label and require re-approval)

### Step 2: Vision Alignment Check

Read `VISION.md` and evaluate the issue against the product vision.

1. Check against the **"What Anteroom Is Not"** negative guardrails:
   - Does this make Anteroom a walled garden? (proprietary extension system, required infrastructure for extensibility)
   - Does this make Anteroom more like a ChatGPT clone? (chat-only feature with no agentic/tool value)
   - Does this make Anteroom a configuration burden? (feature that doesn't work without configuration, missing sensible defaults)
   - Does this add enterprise software patterns? (license keys, SSO, admin panels)
   - Does this complicate deployment? (new infrastructure dependencies, Docker requirements)
   - Does this make Anteroom a model host? (model management, benchmarking, serving)

2. Check against **Out of Scope** (hard no): cloud/SaaS, model training, mobile native, complex deployment, admin dashboards, recreating IDE functionality

3. Run the **Litmus Test**:
   - Can someone in a locked-down enterprise use this?
   - Does it work with `pip install`?
   - Is it lean?
   - Does it work in both interfaces?
   - Would the team use this daily?

4. Check for **complexity creep**: Does this issue add new dependencies, new config options, or new infrastructure requirements? If so, is each one justified?

**Report:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  🎯 Vision Alignment: #<N>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Supports:     <which core principles this advances>
  Guardrails:   ✅ / ⚠️ <any "Is Not" concerns>
  Litmus test:  ✅ / ⚠️ <any concerns>
  Scope:        ✅ / ❌
  Complexity:   ✅ / ⚠️ <new deps, config, or infra>

────────────────────────────────────────────
```

- If **[FAIL]**: explain the conflict, suggest alternatives, ask the user how to proceed. Do not continue.
- If **[WARN]**: show the concern, ask the user to confirm before proceeding.
- If all **[PASS]**: continue to Step 3.

### Step 3: Deep Code Exploration (parallel agents)

Launch parallel agents to understand the codebase context for this issue:

**Agent A — Architecture context (Sonnet):**
1. Read `CLAUDE.md` for architecture overview
2. Identify which layer(s) this issue touches (routers, services, tools, CLI, static, DB)
3. List the key files and patterns relevant to this change

**Agent B — Existing implementation (Sonnet):**
1. Based on the issue description and affected files, read the current code
2. Understand existing patterns: how similar features are implemented
3. Identify integration points and dependencies
4. Note any TODOs, FIXMEs, or comments related to this work

**Agent C — Test landscape (Sonnet):**
1. Find test files related to the affected modules
2. Understand testing patterns: fixtures, mocking approach, async test setup
3. Identify what new unit tests will be needed
4. Identify UX test needs per `.claude/rules/ux-testing.md`:
   - If web UI code is affected: check existing Playwright tests in `tests/e2e/test_ui_*.py`, identify new Playwright tests needed
   - If CLI UX code is affected: check existing integration tests in `tests/integration/`, identify new CLI integration tests needed
   - If JS files are affected: check for existing JS unit tests, identify new Vitest tests needed
   - If shared core is affected: flag both interfaces need UX coverage

### Step 4: Create Implementation Plan

Based on the exploration, create a structured plan:

```markdown
## Implementation Plan: #<N> — <title>

### Summary
<1-2 sentences on what this change does>

### Phasing
<If the issue is large, break it into phases. State which phase this plan covers and what is deferred.>

### Files to Create
- `src/anteroom/<path>` — <purpose>
- `tests/unit/test_<name>.py` — <what it tests>

### Files to Modify
| File | Change |
|------|--------|
| `src/anteroom/<path>` | <what changes and why> |
| `src/anteroom/<path>` | <what changes and why> |

### Implementation Steps
1. <First thing to do — be specific about what code to write/change>
2. <Next step>
3. <Continue...>
N. Run tests: `pytest tests/unit/ -v`
N+1. Run lint: `ruff check src/ tests/`

### Testing Strategy
- **Unit tests**: <what to test, how to test it>
- **UX tests**: <Playwright E2E for web UI changes, CLI integration for REPL changes, visual snapshots for renderer changes, JS unit tests for frontend logic — or "N/A: backend-only change">
- **Edge cases**: <edge cases to cover>
- **Integration points**: <integration points to verify>

### Risks & Considerations
- <Anything tricky, breaking changes, migration needs>
```

### Step 5: Update the Issue Body

Preserve the original issue description and append the implementation plan below it. Use a clear separator so the original context is not lost.

Update the issue body using `gh issue edit`:

```bash
gh issue edit <N> --body "<updated body>"
```

The updated body format:

```markdown
<original issue body>

---

## Implementation Plan

<plan from Step 4>

---
*Plan generated by `/plan-work` — awaiting senior review*
```

**IMPORTANT:** Read the current issue body first (`gh issue view <N> --json body --jq '.body'`), then prepend it to the plan. Never overwrite the original description.

### Step 6: Add Label and Report

Ensure the label exists, remove any stale approval, and add the review label:

```bash
gh label create "needs-senior-review" --color "FBCA04" --description "Awaiting senior reviewer sign-off" --force
gh label create "senior-approved" --color "0E8A16" --description "Senior reviewer has approved" --force
gh issue edit <N> --remove-label "senior-approved" --add-label "needs-senior-review"
```

Print the report:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  📋 Plan Ready: #<N> — <title>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  📋 Plan:       <number> steps across <number> files
  🧪 Unit tests: ~<number> existing across affected modules, ~<number> new needed
  🎭 UX tests:   <Playwright / CLI integration / snapshots / JS unit — or "N/A: backend-only">
  🎯 Vision:     ✅ supports <principles>
  🏷️  Status:     needs-senior-review

<The implementation plan from Step 4>

────────────────────────────────────────────
  ⏳ Awaiting senior review
  👉 Next: run /senior-review <N> to get sign-off,
           then /start-work <N> to begin
────────────────────────────────────────────
```

## Guidelines

- The plan should be detailed enough that another developer (or Claude session) could follow it
- Don't start coding — this skill only creates the plan
- If the issue description is vague or missing acceptance criteria, flag what's unclear and suggest criteria
- If the issue requires changes to the DB schema, call that out prominently
- If the issue touches security-sensitive code (auth, sessions, crypto, tools), note OWASP requirements
- If the issue already has a plan in the body (contains "## Implementation Plan"), ask the user if they want to replace it
