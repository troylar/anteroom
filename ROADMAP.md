# Anteroom Roadmap

Aligned with [VISION.md](VISION.md). Updated 2026-02-22.

## Deeper Agentic Capabilities

### High
- [ ] #218 — Structured JSON output mode for agent events
- [ ] #266 — Render live plan checklist with execution progress
- [ ] #166 — Render execution plan as live checklist during agentic runs
- [ ] #272 — Add plan mode approval flow to web UI
- [ ] #281 — Add code changes summary after tool execution
- [ ] #231 — OS-level sandboxing for command execution

### Medium
- [ ] #268 — Multi-pane AI-managed context panels for CLI and web
- [ ] #230 — Glob-pattern bash permission rules
- [ ] #225 — Built-in web fetch and search tools
- [ ] #284 — Expose OpenAI-compatible proxy API with agentic capabilities
- [ ] #282 — Add API conversation type for tracking external tool calls
- [ ] #99 — Store sub-agent tool calls in database for audit trail

### Low
- [ ] #81 — Multi-session task harness: delegate work that spans days
- [ ] #79 — Heartbeat agent: proactive AI that doesn't wait for you
- [ ] #77 — Scheduled/background conversations
- [ ] #216 — Lifecycle hooks for agent loop events
- [ ] #214 — Multi-model pipeline with reasoning and editing roles
- [ ] #235 — Conversation forking for branching explorations
- [ ] #227 — Undo/redo for file modifications

## Knowledge Management

### High
- [ ] #179 — Document upload to knowledgebase with global and project scope

### Medium
- [ ] #217 — save_memory tool for agent-initiated cross-session persistence
- [ ] #212 — Tree-sitter codebase index for token-efficient context
- [ ] #78 — Transparent Markdown-based memory with sqlite-vec index

### Low
- [ ] #72 — Markdown journaling with auto-export and Obsidian compatibility
- [ ] #75 — Conversation branching UI with tree visualization
- [ ] #74 — Conversation templates for recurring workflows
- [ ] #60 — Web UI: conversation import from markdown
- [ ] #178 — Document source scanning with folder watch and Confluence connector

## Extensibility

### High
- [ ] #224 — Drop-in custom tool authoring via Python scripts
- [ ] #233 — MCP server mode so Anteroom can be used as a tool
- [ ] #109 — Default embeddings to disabled, improve separate endpoint config

### Medium
- [ ] #228 — Agent configuration profiles

### Low
- [ ] #96 — Load .parlor/commands/ as Anteroom skills
- [ ] #65 — Real-time collaboration on shared databases
- [ ] #80 — Live multi-user agent sessions: collaborative prompting

## Developer Workflow

### High
- [ ] #243 — Add VS Code extension for Anteroom
- [ ] #213 — Auto-validate edits with lint and test feedback loop

### Medium
- [ ] #237 — VS Code extension with chat, code assistant, and conversation sync
- [ ] #248 — VS Code @file/@folder mentions and partial file pasting
- [ ] #274 — Store working directory in conversations for cross-interface continuity
- [ ] #226 — Usage stats command for token and cost tracking

### Low
- [ ] #48 — MkDocs Material documentation site and /write-docs skill
- [ ] #229 — LSP integration for codebase-aware context
- [ ] #167 — Persistent task panel above prompt box

## Other

### Medium
- [ ] #114 — CLI: accessibility improvements (NO_COLOR, text markers, screen reader compat)
- [ ] #113 — Web UI: WCAG 2.2 AA compliance (ARIA, focus, contrast)

### Low
- [ ] #258 — anteroom-shell (ashell) on xonsh *(vision-review)*
- [ ] #199 — Compressed paste blocks with atomic delete
- [ ] #116 — Color theme support for CLI with color-blindness safe themes
- [ ] #112 — WCAG 2.2 AA accessibility rules and PR validation
- [ ] #273 — Real-time conversation sync between web UI and CLI
- [ ] #57 — Web UI: infinite scroll for conversation list
- [ ] #58 — Web UI: bulk operations on conversations
