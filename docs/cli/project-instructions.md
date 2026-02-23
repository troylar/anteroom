# Project Instructions (ANTEROOM.md / CLAUDE.md)

Project instructions let you inject context into every CLI conversation. By placing an instruction file in your project root, you tell the AI about your tech stack, conventions, patterns, and anything else it needs to write correct code for your project.

## Supported File Names

Anteroom recognizes these instruction file names (checked in this order at each directory level):

| File | Notes |
|---|---|
| `.anteroom.md` | Hidden file (preferred) |
| `ANTEROOM.md` | Standard visible file |
| `.claude.md` | Claude Code compatible |
| `CLAUDE.md` | Claude Code compatible |

The `.anteroom` and `.claude` variants are interchangeable — Anteroom treats them identically. If you have an existing `.claude` code project with a `CLAUDE.md`, Anteroom will pick it up automatically. The first match wins at each directory level, so if both `.anteroom.md` and `CLAUDE.md` exist in the same directory, `.anteroom.md` takes precedence.

## Discovery

Anteroom walks **up** from the current working directory to find the nearest instruction file. At each directory level, it checks for the supported file names in order and returns the first match.

```
my-project/
├── ANTEROOM.md              ← Found when working anywhere in the project
├── src/
│   └── backend/
│       └── main.py          ← Working here? Walk-up finds ../../ANTEROOM.md
└── tests/
```

The walk-up continues to the filesystem root, so instruction files in parent directories apply to all subdirectories.

### Global Instructions

A global instruction file at `~/.anteroom/ANTEROOM.md` (or `~/.anteroom/.anteroom.md`) applies to **all** projects. If both global and project instructions exist, both are loaded — global comes first, then project-specific.

The global file is useful for personal preferences that apply everywhere:

```markdown title="~/.anteroom/ANTEROOM.md"
## My Preferences
- Always use type hints
- Prefer functional style
- Write tests for all new code
```

### How Both Are Combined

When both global and project instructions are found, they are concatenated in this order:

1. **Global instructions** — prefixed with `# Global Instructions`
2. **Project instructions** — prefixed with `# Project Instructions`

This means project instructions can override or refine anything in the global file.

## System Prompt Construction

The CLI builds the full system prompt from three sources, concatenated in this order:

```
┌──────────────────────────────────────────────────────────────────┐
│  1. Working directory context                                    │
│     "You are an AI coding assistant working in: /path/to/project"│
│     + tool usage guidance                                        │
├──────────────────────────────────────────────────────────────────┤
│  2. ANTEROOM.md / CLAUDE.md instructions (global + project)      │
│     Injected as-is into the system prompt                        │
├──────────────────────────────────────────────────────────────────┤
│  3. system_prompt from config.yaml                               │
│     Your configured system prompt (default: "You are a helpful   │
│     assistant.")                                                 │
└──────────────────────────────────────────────────────────────────┘
```

## Trust Model

Project instruction files are verified before loading to prevent prompt injection from untrusted repositories.

**How trust works:**

1. When an instruction file is found for the first time, Anteroom computes its **SHA-256 hash**.
2. In **interactive mode** (CLI chat, CLI exec with TTY): you are prompted to confirm trust.
3. In **non-interactive mode** (web UI, piped input): untrusted files are **silently skipped** (fail-closed).
4. Trust decisions are stored in `~/.anteroom/trusted_folders.json` with the file path and content hash.
5. If the file changes (hash mismatch), you are prompted again to re-trust.

```
$ aroom chat
Found project instructions: /path/to/project/ANTEROOM.md
Trust this file? [y/N] y
```

Once trusted, subsequent runs skip the prompt unless the file content changes.

### Recursive Trust

When you trust a directory's instruction file, that trust extends to subdirectories. This means if you trust `/path/to/monorepo/ANTEROOM.md`, working in any subdirectory of that repo will use the trusted file without re-prompting.

### Non-Interactive Environments

In non-interactive mode (web UI, CI/CD, piped input), untrusted instruction files are **silently skipped**. This is a deliberate security choice — fail-closed prevents untrusted content from being injected into prompts.

To use instruction files in CI/CD:
1. First trust them interactively: `aroom chat` (prompts once)
2. The trust decision persists in `~/.anteroom/trusted_folders.json`
3. Subsequent non-interactive runs will use the trusted file

### CLI Flags

Two flags control instruction loading:

| Flag | Effect |
|---|---|
| `--trust-project` | Auto-trust the found instruction file without prompting |
| `--no-project-context` | Skip loading project instructions entirely |

```bash
aroom chat --trust-project        # Trust without prompting
aroom chat --no-project-context   # Ignore instruction files
```

## Token Estimation

Anteroom estimates the token count of instruction files using a simple heuristic: **1 token per 4 characters**. If the estimated count exceeds **4,000 tokens**, a warning is shown:

```
⚠️ Conventions file is ~5,200 tokens (threshold: 4,000). Large files reduce prompt effectiveness.
```

Large instruction files consume context window space, leaving less room for conversation history and tool calls. Keep instructions focused and concise.

## Web UI Support

The web UI also loads instruction files through the conventions API:

- `GET /api/conventions` returns the active instruction file's content, path, source (`project`, `global`, or `none`), estimated tokens, and any warning.
- The web UI displays instruction file status in the settings panel.

## Example

```markdown title="ANTEROOM.md"
# Project: my-api

## Tech Stack
- Python 3.12, FastAPI 0.104, SQLAlchemy 2.0
- PostgreSQL 16, Redis 7
- pytest, ruff, mypy

## Conventions
- All functions must have type hints
- Use conventional commits: type(scope): description (#issue)
- Tests required for all new features
- Use parameterized queries only (no string formatting in SQL)

## File Structure
- src/app/routers/ — API endpoints
- src/app/services/ — business logic
- src/app/models/ — SQLAlchemy models
- tests/unit/ — unit tests (mocked, no I/O)
- tests/integration/ — integration tests (real DB)

## Patterns
- All endpoints return Pydantic response models
- Async handlers with `async def`
- Dependency injection for DB sessions
- Background tasks for email/notifications
```

## Best Practices

- **Keep it focused**: Include only what the AI needs to write correct code — tech stack, conventions, patterns, structure.
- **Keep it concise**: Stay under 4,000 estimated tokens. Cut prose; use bullet points.
- **Be specific**: "Use conventional commits" is vague. "Use `type(scope): description (#issue)` format" is actionable.
- **Update it**: When your project conventions change, update the instruction file. Anteroom will detect the change and re-verify trust.
- **Use global for personal preferences**: Put project-agnostic preferences (coding style, tool preferences) in `~/.anteroom/ANTEROOM.md` so they apply everywhere.

## Compatibility

The `.anteroom` and `.claude` file names are fully interchangeable. This means:

- A project with `CLAUDE.md` works with Anteroom out of the box
- A project with `ANTEROOM.md` follows the same discovery and trust model
- If you use both tools, you only need one instruction file
- `.anteroom.md` (hidden) takes precedence over `ANTEROOM.md` (visible) and both take precedence over `.claude.md` / `CLAUDE.md`
