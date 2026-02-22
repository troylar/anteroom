# Changelog

Release highlights for every Anteroom version. For full details including developer notes and upgrade instructions, see the linked GitHub Release.

---

## v1.24.3 — 2026-02-22

- **Replaced Snyk with open-source SAST tools** — CI no longer requires a `SNYK_TOKEN` secret or Node.js setup. Semgrep runs pattern-based security scanning 

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.24.3)

---

## v1.24.2 — 2026-02-22

- Fixed MCP tool argument validation that incorrectly blocked legitimate text content (newlines, parentheses, semicolons, etc.) when passed to MCP servers li
- Improved MCP tool error messages to include server name and tool context for easier debugging (#291)
- Sanitized MCP error output so raw server exceptions are logged server-side only, not exposed to the user (#291)

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.24.2)

---

## v1.24.1 — 2026-02-22

*Maintenance release — see GitHub Release for details.*

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.24.1)

---

## v1.24.0 — 2026-02-22

- **OpenAI-compatible proxy endpoint**: External tools using the OpenAI SDK can route requests through Anteroom to the configured upstream API (#285)
- Endpoints: `GET /v1/models` and `POST /v1/chat/completions` with full streaming support
- Opt-in via `proxy.enabled: true` — disabled by default for security

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.24.0)

---

## v1.23.0 — 2026-02-22

- **Iterative plan refinement**: `/plan edit` opens in `$EDITOR`, `/plan reject` triggers AI revision (#270, #271)
- **Inline planning**: `/plan <prompt>` enters planning mode in one command (#265)
- Auto-plan suggestions when tasks exceed tool-call threshold (#265)

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.23.0)

---

## v1.22.1 — 2026-02-22

- **Planning Mode**: AI can now generate a structured step-by-step plan before executing tasks. Start planning mode with `aroom chat --plan` or `/plan on` du
- **Plan Editing**: Open your plan in `$VISUAL`/`$EDITOR` with `/plan edit` to review and modify it before approving execution. (#270)
- Added a feature parity development rule ensuring all new features work equivalently in both the CLI and web UI (#275)

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.22.1)

---

## v1.22.0 — 2026-02-21

- **Built-in `/docs` skill**: Look up Anteroom documentation without leaving the CLI — covers config, flags, tools, skills, and architecture (#262)
- Embeds quick-reference tables for instant answers; consults 42 documentation files for deeper questions

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.22.0)

---

## v1.21.0 — 2026-02-21

- **Non-interactive exec mode**: `aroom exec "prompt"` for scripting and CI pipelines (#232)
- Supports stdin piping, `--json` output, timeout control, and conversation persistence

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.21.0)

---

## v1.20.1 — 2026-02-21

- Fixed stale thinking line text persisting after stream retry — the "Stream timed out" and "retrying in Ns" text no longer flashes or leaves ghost content o

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.20.1)

---

## v1.20.0 — 2026-02-21

- **ANTEROOM.md Project Conventions**: Anteroom now formally supports `ANTEROOM.md` as a project-level conventions file that the AI follows consistently acro
- Auto-discovers conventions walking up from your working directory (#215)
- **Web UI now loads ANTEROOM.md** — previously CLI-only, conventions now apply in both interfaces (#215)

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.20.0)

---

## v1.19.0 — 2026-02-20

- **Trust Prompts for Project Instructions**: Anteroom now prompts you before loading project-level `ANTEROOM.md` files into the AI context. This prevents pr
- Trust decisions are persisted with SHA-256 content hash verification — you only need to approve once per project (#219)
- If the file changes, you'll be re-prompted to review and approve the new content (#219)

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.19.0)

---

## v1.18.4 — 2026-02-20

- **Fixed CLI hang after pressing Escape** — pressing Escape to cancel a running command could leave the CLI unresponsive, requiring a force-quit. The REPL n

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.18.4)

---

## v1.18.3 — 2026-02-20

- **API error handling during streaming** — Previously, HTTP errors from the AI provider (like 500 Internal Server Error, 502 Bad Gateway, or 404 Not Found) 

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.18.3)

---

## v1.18.2 — 2026-02-20

- Fixed the CLI thinking indicator ("Thinking...") briefly flashing then dropping to a blank line on the very first message in a new REPL session. Subsequent

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.18.2)

---

## v1.18.1 — 2026-02-20

- **Fixed timeout enforcement on API connections** — The configured `request_timeout` (default 120s) was not enforced as a hard deadline during the initial A
- **Fixed Escape key ignored during connecting phase** — Pressing Escape while the API was connecting had no effect until the connection completed or timed o
- **Fixed cancel-during-retry loop** — If the user pressed Escape during a retry backoff delay, the retry loop could re-enter the connection attempt instead 

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.18.1)

---

## v1.18.0 — 2026-02-20

- **Escape during stalled stream now cancels cleanly** — Previously, pressing Escape while a stream was stalled would trigger a retry countdown instead of ca
- **Stalled streams abort faster** — Added per-chunk stall timeout (default 30s) so streams that go silent mid-response are aborted sooner instead of waiting
- **Configurable Timeouts and Thresholds**: Every timeout, threshold, and limit that was previously hardcoded is now a config field with a sensible default. 

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.18.0)

---

## v1.17.1 — 2026-02-20

- Fixed the CLI thinking spinner showing stale phase text ("waiting for first token", "streaming · N chars") and "esc to cancel" hint on the final line after
- Fixed the per-phase timer not always appearing during the "waiting for first token" phase. The timer now starts immediately when thinking begins, rather th

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.17.1)

---

## v1.17.0 — 2026-02-20

- **Real-Time Connection Health Monitor for CLI**: The CLI thinking spinner now shows live connection status so you always know what's happening during AI in
- **Phase tracking**: See "connecting", "connected · waiting for first token", and "streaming · N chars" as the request progresses (#221)
- **Per-phase timing**: Each phase shows how long it's been active (e.g., "waiting for first token (5s)")

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.17.0)

---

## v1.16.3 — 2026-02-20

- **Fixed confusing "HARD BLOCKED" message after approving dangerous commands.** Previously, when you approved a dangerous command like `rm -rf`, the system 

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.16.3)

---

## v1.16.2 — 2026-02-20

- **Smarter API timeouts**: Replaced the single 120-second timeout with three phase-aware timeouts — connect (5s), first-token (30s), and stream (120s). This
- **Automatic retry on transient errors**: When the API times out or drops a connection, Anteroom now automatically retries up to 3 times with exponential ba
- **Fixed phantom thinking timer after timeout**: Previously, if the API timed out, the thinking spinner would restart and keep counting up even after the er

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.16.2)

---

## v1.16.1 — 2026-02-20

- CLI no longer prints noisy tracebacks when pressing Ctrl+C with MCP servers connected. Shutdown errors are now suppressed from terminal output and logged a
- Fixed a test that would fail when `AI_CHAT_API_KEY` was set in the shell environment (#208)

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.16.1)

---

## v1.16.0 — 2026-02-20

- **Granular Request Lifecycle Phases in Thinking Indicator**: The thinking spinner now shows exactly where time is being spent during AI responses, making i
- **Connecting** — shown while establishing connection to the AI API (#203)
- **Waiting for first token** — shown after the request is sent, while waiting for the model to start responding (#203)

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.16.0)

---

## v1.15.0 — 2026-02-20

- **Rich Markdown in Resume Recap**: When resuming a conversation with `/last` or `/resume`, the assistant's last message is now rendered with full Rich Mark
- Long assistant messages truncate at line boundaries to preserve markdown structure
- Truncation limit increased from 300 to 500 characters for better context

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.15.0)

---

## v1.14.11 — 2026-02-20

- **Thinking spinner no longer freezes during API stalls** — The CLI thinking timer previously stuck at "1s" when the API was slow to respond between tool ca

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.14.11)

---

## v1.14.10 — 2026-02-20

- **Port-in-use errors now show actionable guidance** — when port 8080 (or your configured port) is already taken, Anteroom now prints a clear message with t
- **`--port` flag**: Override the configured port directly from the command line:
- **`AI_CHAT_PORT` environment variable**: Set a default port via environment variable, useful for scripts and containerized setups:

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.14.10)

---

## v1.14.9 — 2026-02-20

*Maintenance release — see GitHub Release for details.*

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.14.9)

---

## v1.14.8 — 2026-02-20

- **Fixed thinking indicator hanging indefinitely** — When an API stalls mid-stream (no chunks arriving), Anteroom now detects the stall and times out gracef

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.14.8)

---

## v1.14.7 — 2026-02-20

*Maintenance release — see GitHub Release for details.*

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.14.7)

---

## v1.14.6 — 2026-02-19

- API connection and authentication errors now show clear, actionable messages instead of raw Python tracebacks or generic "internal error" text (#121)

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.14.6)

---

## v1.14.5 — 2026-02-19

- **Fixed stacking approval prompts in CLI.** When multiple MCP tools needed approval at the same time, prompts would stack on top of each other and spam "te

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.14.5)

---

## v1.14.4 — 2026-02-19

- **ESC cancel hint on CLI thinking line**: When the AI is thinking for more than 3 seconds, a muted "esc to cancel" hint now appears on the thinking line. T

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.14.4)

---

## v1.14.3 — 2026-02-19

- **Embedding worker no longer retries unembeddable messages forever.** Previously, short messages (< 10 characters), messages that returned no embedding, an

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.14.3)

---

## v1.14.2 — 2026-02-19

- Fixed Ctrl+C causing unhandled `ExceptionGroup` errors during MCP server shutdown (#174). The MCP SDK uses `anyio` TaskGroups internally, which raise `Exce

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.14.2)

---

## v1.14.1 — 2026-02-19

- **File uploads now accept common document formats** — Uploading Office documents (.docx, .xlsx, .pptx, .doc, .xls, .ppt), Markdown files, JSON, YAML, TOML,
- **Markdown and text files upload correctly even when browsers send no MIME type** — When a browser sends `application/octet-stream` (no MIME type detected)

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.14.1)

---

## v1.14.0 — 2026-02-19

- **Knowledge Sources**: A global knowledge store for your projects — upload files, save text notes, and bookmark URLs that persist across conversations. Sou
- Create text, URL, and file-based knowledge sources (#180)
- Full web UI for browsing, creating, editing, and deleting sources (#181)

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.14.0)

---

## v1.13.0 — 2026-02-19

- **Local Embeddings — No API Key Required**: Anteroom now generates vector embeddings locally using [fastembed](https://github.com/qdrant/fastembed), an ONN
- Default model: `BAAI/bge-small-en-v1.5` (384 dimensions, ~50MB download on first use)
- Install with: `pip install anteroom[embeddings]`

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.13.0)

---

## v1.12.3 — 2026-02-19

- MCP server connection failures are now logged cleanly without a raw traceback. When an MCP server rejects a connection or fails the handshake, Anteroom pre

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.12.3)

---

## v1.12.2 — 2026-02-19

- **Fixed CLI crash when reviewing codebases with special tokens**: The CLI would crash with a tiktoken error when message content contained special token pa

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.12.2)

---

## v1.12.1 — 2026-02-19

- **Narration cadence now actually works**: The narration cadence feature (introduced in v1.11.0) was not producing any output for modern models like GPT-4o 
- Narration now fires reliably regardless of model behavior (#169)
- Default cadence unchanged: every 5 tool calls (`ai.narration_cadence: 5`)

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.12.1)

---

## v1.12.0 — 2026-02-19

- **Configurable Tool Call Dedup**: When the AI makes many consecutive tool calls of the same type (e.g., editing 10 files in a row), they're now automatical
- CLI: consecutive same-type tool calls collapse with a count summary (e.g., "... edited 5 files total") (#59)
- Web UI: consecutive same-type tool calls group into a collapsible `<details>` element with count (e.g., "edit_file × 5") (#59)

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.12.0)

---

## v1.11.0 — 2026-02-18

- **Progress Updates During Long Agentic Runs**: When the AI executes many tool calls in sequence (editing files, running tests, exploring code), it now give
- Configurable via `ai.narration_cadence` in config.yaml (default: every 5 tool calls) (#157)
- Set to `0` to disable and restore the previous silent behavior

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.11.0)

---

## v1.10.2 — 2026-02-18

- **API timeout recovery**: After a timeout, the next request no longer hangs indefinitely. Previously, a timeout would leave the httpx connection pool in a 

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.10.2)

---

## v1.10.0 — 2026-02-18

- **Claude Code-Quality System Instructions**: The default system prompt for `aroom chat` has been completely rewritten to match the quality and structure of
- **Tool preference hierarchy**: The AI now strongly prefers dedicated tools (read_file, edit_file, grep, glob_files) over bash for file operations, reducing
- **Code modification guidelines**: Instructions to read before editing, match codebase conventions, avoid over-engineering, and produce working code — not p

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.10.0)

---

## v1.9.4 — 2026-02-18

- **Tool call notifications no longer disappear mid-session.** In multi-iteration agent loops (where the AI calls tools, thinks, then calls more tools), tool

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.9.4)

---

## v1.9.3 — 2026-02-18

- **Embedding worker no longer retries forever** when the embedding API returns a permanent error (e.g., model not found, invalid credentials). Previously, t
- **Permanent errors** (404 model not found, 422 unprocessable, failed auth) immediately disable the worker with a clear log message
- **Transient errors** (429 rate limit, 503 server error, timeouts) trigger exponential backoff: 30s → 60s → 120s → up to 300s

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.9.3)

---

## v1.9.2 — 2026-02-18

- Fixed CLI completion menu using white-on-black colors that clashed with the dark terminal theme — now uses the dark palette (gold highlight, chrome text on
- Added above-cursor positioning attempt for the completion menu to reduce clipping when the prompt is near the terminal bottom (best-effort — full fix comin

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.9.2)

---

## v1.9.1 — 2026-02-18

- Optimized `/code-review` and `/submit-pr` Claude Code skills to eliminate redundant agent work during deploy cycles, reducing token usage by ~170k per depl

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.9.1)

---

## v1.9.0 — 2026-02-18

- **Sub-Agent Loading Indicator**: When a sub-agent is running in the Web UI, you now see a distinctive loading state instead of the generic tool call panel
- A pulsing accent border that animates while the sub-agent works
- A prompt preview showing what the sub-agent is doing

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.9.0)

---

## v1.8.0 — 2026-02-18

- **MCP Tools in Sub-Agents**: Sub-agents spawned via `run_agent` can now access MCP (Model Context Protocol) tools from connected servers. Previously, child
- MCP tool definitions are merged into the child agent's tool list (#100)
- Child agents can call MCP tools through real MCP servers (e.g., time, filesystem, databases)

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.8.0)

---

## v1.7.0 — 2026-02-18

- **CLI text readability on dark terminals**: Rich's `[dim]` style (SGR 2 faint) was nearly invisible on most dark terminal themes, making tool results, appr
- Replaced all `[dim]` and `grey62` markup with a defined color palette that meets WCAG AA contrast ratios (#140)
- Four named constants: `GOLD` (accents), `SLATE` (labels), `MUTED` (secondary text), `CHROME` (UI chrome)

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.7.0)

---

## v1.6.0 — 2026-02-18

- **Sub-Agent Orchestration**: The AI can now spawn parallel child agents using the `run_agent` tool to break complex tasks into independent subtasks. Each s
- Sub-agents execute in parallel with concurrency control via `asyncio.Semaphore` (#95)
- Configurable limits: max concurrent (5), max total (10), max depth (3), max iterations (15), wall-clock timeout (120s)

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.6.0)

---

## v1.5.1 — 2026-02-18

- Remove stale test count tracking from CLAUDE.md and skill definitions — the hardcoded count went stale constantly and skills wasted cycles checking/updatin

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.5.1)

---

## v1.5.0 — 2026-02-18

- **Issue Lifecycle Management**: Three new Claude Code skills for managing the issue → branch → PR → deploy lifecycle, plus seven GitHub labels for tracking
- `/next` — Prioritized work queue sorted by priority labels and VISION.md direction areas. Shows what to work on next with rationale (#136)
- `/triage` — Set priority on individual issues or AI-reassess all open issues against VISION.md. Optionally updates ROADMAP.md (#136)

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.5.0)

---

## v1.4.11 — 2026-02-18

*Maintenance release — see GitHub Release for details.*

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.4.11)

---

## v1.4.10 — 2026-02-18

- **Stale Auth Cookie Recovery on Upgrade**: Users upgrading from pre-identity versions (before v1.4.5) could get stuck in an authentication loop where the b
- Server now attaches a fresh session cookie to 401 responses, so browsers auto-recover without a manual page refresh (#128)
- Partial identity configs (user_id present but missing private_key) are now auto-repaired on server startup (#128)

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.4.10)

---

## v1.4.9 — 2026-02-18

- **CLI Startup Progress Feedback**: The CLI no longer sits silently during bootstrap. Dim animated spinners now show activity during the three slow startup 
- MCP server connections (#122)
- AI service validation (#122)

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.4.9)

---

## v1.4.8 — 2026-02-18

- Fixed the web UI "stuck thinking" animation that would never dismiss after a response completed. The thinking indicator was being created multiple times bu
- Fixed 401 authentication errors for users upgrading from pre-identity versions. The chat stream now properly handles expired sessions instead of showing an
- Fixed SSE EventSource reconnect loop — persistent auth failures (3+ consecutive) now trigger session recovery instead of reconnecting indefinitely. (#128)

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.4.8)

---

## v1.4.7 — 2026-02-18

- **CI: Snyk security scan now passes green** — the Snyk SCA scan was crashing due to a dependency resolver bug in the Snyk Docker container (not an actual v

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.4.7)

---

## v1.4.6 — 2026-02-18

- Fixed Windows mapped network drive paths resolving to blocked UNC paths. On Windows, accessing files on mapped drives (e.g., `X:	est` where `X:` maps to a 

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.4.6)

---

## v1.4.5 — 2026-02-18

- Hardened deploy workflow to handle recurring merge failures — auto-rebases, waits for CI, uses `--admin` only when non-required checks fail (#120)
- Fixed pre-push hook blocking version bump pushes with `--no-verify` (#120)
- Fixed zsh glob expansion error on `*.egg-info` cleanup (#120)

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.4.5)

---

## v1.4.4 — 2026-02-18

- Fixed Rich markup injection in approval output — tool names containing brackets or colons (common with MCP tools) are now properly escaped (#111)

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.4.4)

---

## v1.4.3 — 2026-02-18

- **UI hangs after MCP tool approval (#110)**: After approving MCP tool calls, the web UI could become completely unresponsive. This release fixes five inter
- **Stale stream detection** — when a browser tab disconnects or times out, the server now detects the stale SSE stream and cleans it up instead of blocking 
- **Thinking spinner stuck forever** — the "thinking" animation now correctly dismisses on all completion paths including errors and canvas operations (#110)

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.4.3)

---

## v1.4.2 — 2026-02-17

*Maintenance release — see GitHub Release for details.*

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.4.2)

---

## v1.4.1 — 2026-02-17

- **MCP tool approval flow no longer stalls after clicking Allow.** Previously, after approving an MCP tool in the web UI, there was no visual feedback that 
- **CLI approval prompt now accepts keyboard input.** The tool approval prompt in the CLI REPL was unresponsive — you couldn't type y/n/a/s. Fixed by integra
- CLI banner now correctly shows **ANTEROOM** instead of the old project name, with the updated tagline "the secure AI gateway."

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.4.1)

---

## v1.4.0 — 2026-02-17

- **Tool Approval System**: A Claude Code-style safety gate for AI tool execution. Every tool is assigned a risk tier (read, write, execute, destructive), an
- **4 risk tiers**: read (safe), write (modifies files), execute (runs code), destructive (irreversible)
- **4 approval modes**: `auto` (no prompts), `ask_for_dangerous` (destructive only), `ask_for_writes` (default — write+execute+destructive), `ask` (alias)

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.4.0)

---

## v1.3.1 — 2026-02-17

- **New Chat button broken** — Clicking "New Chat" in the Web UI failed with a 415 error when no project was selected. The Content-Type header was only sent 
- **CSP inline script blocked** — The Content Security Policy hash for the theme initialization script was stale, causing the browser to block it. Updated to

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.3.1)

---

## v1.3.0 — 2026-02-17

- **Canvas Tools with Real-Time Streaming**: Anteroom now includes a canvas panel for AI-generated content alongside chat. When the AI writes code, documents
- **Create canvas** — AI can open a canvas panel with any content (#89)
- **Update canvas** — Full content replacement for major revisions (#89)

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.3.0)

---

## v1.2.0 — 2026-02-16

- **Semantic Search**: Anteroom now supports vector similarity search across your conversation history, powered by sqlite-vec. Search finds semantically rela
- Semantic search API endpoints: `/api/search/semantic` and `/api/search/hybrid` (#82)
- Background embedding worker processes messages automatically using any OpenAI-compatible embedding API (#82)

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.2.0)

---

## v1.1.0 — 2026-02-16

- **Cryptographic Identity (#68)**: Every Anteroom user now gets a unique cryptographic identity — a UUID paired with an Ed25519 keypair. This is the foundat
- UUID + Ed25519 keypair generated automatically on first run or via `aroom init` (#68)
- Private key stored securely in `config.yaml` (file permissions set to 0600) (#68)

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v1.1.0)

---

## v0.9.1 — 2026-02-15

*Maintenance release — see GitHub Release for details.*

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v0.9.1)

---

## v0.9.0 — 2026-02-15

*Maintenance release — see GitHub Release for details.*

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v0.9.0)

---

## v0.8.3 — 2026-02-15

*Maintenance release — see GitHub Release for details.*

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v0.8.3)

---

## v0.8.2 — 2026-02-15

*Maintenance release — see GitHub Release for details.*

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v0.8.2)

---

## v0.8.1 — 2026-02-15

*Maintenance release — see GitHub Release for details.*

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v0.8.1)

---

## v0.8.0 — 2026-02-15

- **Verbosity system**: Three display modes for tool calls — compact (default), detailed, and verbose
- **`/detail` command**: Replay last turn's tool calls with full arguments and output on demand
- **Live tool spinners**: Each tool call shows an animated spinner while executing

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v0.8.0)

---

## v0.7.2 — 2026-02-15

- Connection failures now show descriptive error context instead of generic messages

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v0.7.2)

---

## v0.7.1 — 2026-02-15

*Maintenance release — see GitHub Release for details.*

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v0.7.1)

---

## v0.7.0 — 2026-02-14

*Maintenance release — see GitHub Release for details.*

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v0.7.0)

---

## v0.6.9 — 2026-02-14

*Maintenance release — see GitHub Release for details.*

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v0.6.9)

---

## v0.6.8 — 2026-02-14

*Maintenance release — see GitHub Release for details.*

[GitHub Release](https://github.com/troylar/anteroom/releases/tag/v0.6.8)
