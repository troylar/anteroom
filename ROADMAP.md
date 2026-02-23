# Anteroom Roadmap

Aligned with [VISION.md](VISION.md). Updated 2026-02-23.

## Knowledge Management

### High

- [ ] #109 — feat: default embeddings to disabled, improve separate endpoint config

### Medium

- [ ] #78 — feat: Transparent Markdown-based memory with sqlite-vec index
- [ ] #83 — feat: Knowledge notebooks — conversation types for logs, docs, and searchable content
- [ ] #212 — feat: add tree-sitter codebase index for token-efficient context
- [ ] #217 — feat(tools): add save_memory tool for agent-initiated cross-session persistence
- [ ] #225 — feat(tools): add built-in web fetch and search tools
- [ ] #310 — Add token budget warnings for usage self-regulation

### Low

- [ ] #72 — feat: Markdown journaling with auto-export and Obsidian compatibility
- [ ] #178 — Add document source scanning with folder watch and Confluence connector

## Deeper Agentic Capabilities

### High

- [ ] #213 — feat(agent): auto-validate edits with lint and test feedback loop
- [ ] #231 — feat(tools): add OS-level sandboxing for command execution (macOS/Linux)
- [ ] #266 — feat(cli): render live plan checklist with execution progress
- [ ] #272 — feat(web): add plan mode approval flow to web UI

### Medium

- [ ] #99 — Store sub-agent tool calls in database for audit trail
- [ ] #228 — feat(config): add agent configuration profiles
- [ ] #230 — feat(tools): add glob-pattern bash permission rules
- [ ] #257 — feat(cli): redesign prompt with persistent status header and context bar
- [ ] #268 — feat: multi-pane AI-managed context panels for CLI and web
- [ ] #282 — Add API conversation type for tracking external tool calls
- [ ] #297 — feat(tools): OS-level sandboxing for command execution (Windows)
- [ ] #298 — Add file change cards to web UI for write_file and edit_file results
- [ ] #301 — feat(routers): add live plan checklist to web UI chat

### Low

- [ ] #77 — feat: Scheduled/background conversations
- [ ] #79 — feat: Heartbeat agent — proactive AI that doesn't wait for you
- [ ] #80 — feat: Live multi-user agent sessions — collaborative prompting
- [ ] #81 — feat: Multi-session task harness — delegate work that spans days
- [ ] #176 — feat: add webhook agent backend for n8n and external endpoints
- [ ] #214 — feat: multi-model pipeline with reasoning and editing roles
- [ ] #227 — feat(tools): add undo/redo for file modifications
- [ ] #235 — feat(cli): add conversation forking for branching explorations
- [ ] #273 — Add real-time conversation sync between web UI and CLI

## Extensibility

### High

- [ ] #224 — feat(tools): add drop-in custom tool authoring via Python scripts
- [ ] #233 — feat(mcp): add MCP server mode so Anteroom can be used as a tool
- [ ] #284 — feat(routers): expose OpenAI-compatible proxy API with agentic capabilities
- [ ] #319 — feat: deferred MCP tool loading to reduce context token overhead
- [ ] #323 — feat: call_mcp meta-tool for code-execution-with-MCP pattern

### Medium

- [ ] #216 — feat: add lifecycle hooks for agent loop events
- [ ] #321 — feat: track and warn on tool definition token overhead
- [ ] #322 — feat: hybrid skills that declare MCP tool dependencies for on-demand loading
- [ ] #324 — feat: adaptive tool context — dynamically load/unload tools by topic

### Low

- [ ] #96 — Load .parlor/commands/ as Anteroom skills
- [ ] #320 — feat: skill-as-API-guide pattern for lightweight service integrations

## Developer Workflow

### High

- [ ] #159 — fix(cli): collapse_long_input shows raw ANSI codes when pasting multiline content
- [ ] #218 — feat(cli): add structured JSON output mode for agent events
- [ ] #267 — feat(cli): auto-invoke skills from natural language prompts

### Medium

- [ ] #114 — CLI: accessibility improvements (NO_COLOR, text markers, screen reader compat)
- [ ] #243 — Add VS Code extension for Anteroom
- [ ] #248 — feat(vscode): add @file/@folder mentions and partial file pasting in chat
- [ ] #274 — Store working directory in conversations for cross-interface continuity

### Low

- [ ] #74 — feat: Conversation templates for recurring workflows
- [ ] #167 — feat(cli): persistent task panel above prompt box using prompt_toolkit layout
- [ ] #199 — feat(cli): compressed paste blocks with atomic delete
- [ ] #229 — feat(cli): add LSP integration for codebase-aware context
- [ ] #237 — feat: add VS Code extension with chat, code assistant, and conversation sync
- [ ] #258 — feat: build anteroom-shell (ashell) — cross-platform AI shell on xonsh

## Other

### Medium

- [ ] #113 — Web UI: WCAG 2.2 AA compliance (ARIA, focus, contrast)

### Low

- [ ] #48 — Add MkDocs Material documentation site and /write-docs skill
- [ ] #57 — Web UI: infinite scroll for conversation list
- [ ] #58 — Web UI: bulk operations on conversations
- [ ] #60 — Web UI: conversation import from markdown
- [ ] #65 — Real-time collaboration on shared databases
- [ ] #75 — feat: Conversation branching UI with tree visualization
- [ ] #112 — Add WCAG 2.2 AA accessibility rules and PR validation
- [ ] #116 — Add color theme support to CLI with color-blindness safe themes
