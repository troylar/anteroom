# UX Testing Requirements

> Vision principle: **"Multiple interfaces, one engine."** Both the web UI and CLI are first-class interfaces. User-facing behavior must be tested at the UX level — not just at the unit level — to catch rendering, interaction, and flow regressions.

## When UX Tests Are Required

| Code Changed | Required UX Tests |
|---|---|
| `routers/`, `static/js/`, `static/css/`, `static/index.html` | Playwright E2E tests in `tests/e2e/` |
| `cli/repl.py`, `cli/commands.py`, `cli/layout.py`, `cli/renderer.py`, `cli/event_handlers.py`, `cli/pickers.py`, `cli/dialogs.py` | CLI integration tests (PipeInput or pexpect) in `tests/integration/` |
| `cli/layout.py`, `cli/renderer.py` | Visual snapshot tests (Syrupy) in `tests/unit/` |
| `services/agent_loop.py`, `tools/` | Both Playwright and CLI integration tests (shared core affects both interfaces) |
| `static/js/*.js` | JavaScript unit tests (Vitest) for logic-heavy modules |

## What Constitutes a UX Test

UX tests verify **what the user sees and experiences**, not just internal correctness:

- **Playwright E2E**: real browser interaction — click, type, wait for SSE events, assert on rendered DOM
- **CLI integration**: real REPL interaction — send commands, assert on terminal output, verify prompt state
- **Visual snapshots**: serialized Rich Console output compared against known-good baselines
- **JS unit tests**: SSE parsing, DOM manipulation, event handling, validation logic

UX tests are distinct from unit tests. A unit test for `chat.py` mocks the HTTP layer and checks return values. A Playwright test loads the page, sends a message, and verifies the response stream renders correctly in the browser.

## What Doesn't Need UX Tests

- Backend-only changes (storage, config parsing, crypto, embeddings) with no UI impact
- Internal refactors that don't change user-visible behavior
- Test infrastructure changes
- Documentation-only changes

## Test Locations

| Type | Location | Framework |
|---|---|---|
| Playwright E2E | `tests/e2e/test_ui_*.py` | pytest-playwright |
| CLI integration | `tests/integration/test_repl_*.py` | prompt_toolkit PipeInput or pexpect |
| Visual snapshots | `tests/unit/test_*_snapshot.py` | Syrupy |
| JavaScript unit | `static/js/__tests__/` or `tests/js/` | Vitest + jsdom |

## Before Committing

When your change touches UI code, verify:

1. Existing UX tests still pass
2. New user-visible behavior has a corresponding UX test
3. Both interfaces are covered if shared code changed (see feature-parity rule)
