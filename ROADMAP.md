# Anteroom Roadmap

Aligned with [VISION.md](VISION.md). Updated 2026-03-01.

Directions match VISION.md Section "Direction (Current)." Issues are sorted by priority within each section. Checked items are completed.

## Governance and Audit

*Making Anteroom the AI gateway that CISOs and CCOs can approve for the entire organization.*

### High

- [ ] #624 — Enforce token budget limits per request and session
- [ ] #213 — feat(agent): auto-validate edits with lint and test feedback loop
- [ ] #231 — feat(tools): add OS-level sandboxing for command execution (macOS/Linux)

### Medium

- [ ] #99 — Store sub-agent tool calls in database for audit trail
- [ ] #627 — Emit audit events for egress domain checks
- [ ] #626 — Add /healthz endpoint for operational monitoring
- [ ] #230 — feat(tools): add glob-pattern bash permission rules
- [x] #310 — Add token budget warnings for usage self-regulation
- [x] #297 — feat(tools): OS-level sandboxing for command execution (Windows)

## Enterprise Knowledge Work

*Making Anteroom useful beyond developers — document generation, presentations, data analysis, reporting.*

### High

- [ ] #629 — feat(packs): add Office document Packs for Word, Excel, and PowerPoint workflows
- [ ] #630 — feat(packs): add shareable Pack templates for common enterprise tasks

### Medium

- [ ] #632 — feat: add data analysis workflow with CSV/Excel ingestion and summary generation
- [ ] #633 — feat(static): add web UI onboarding flow for non-technical users
- [ ] #607 — Enrich XLSX and DOCX read output with formatting context + add missing actions
- [ ] #592 — Add file extension validation to Office tools
- [x] #178 — Add document source scanning with folder watch and Confluence connector

### Low

- [ ] #634 — feat: add report generation skill for Markdown, Word, and PDF output
- [ ] #635 — feat(packs): add template-driven document generation via Packs

## Extensibility

*MCP ecosystem, custom tool authoring, shareable Packs. Making it easy for teams to build and distribute department-specific AI capabilities.*

### High

- [ ] #224 — feat(tools): add drop-in custom tool authoring via Python scripts
- [ ] #233 — feat(mcp): add MCP server mode so Anteroom can be used as a tool
- [ ] #284 — feat(routers): expose OpenAI-compatible proxy API with agentic capabilities
- [ ] #323 — feat: call_mcp meta-tool for code-execution-with-MCP pattern
- [ ] #623 — Add MCP SSE/HTTP transport for remote tool servers
- [ ] #631 — feat(packs): add Pack discovery and sharing workflow
- [ ] #500 — Add skill support to web UI
- [x] #319 — feat: deferred MCP tool loading to reduce context token overhead

### Medium

- [ ] #216 — feat: add lifecycle hooks for agent loop events
- [ ] #322 — feat: hybrid skills that declare MCP tool dependencies for on-demand loading
- [ ] #324 — feat: adaptive tool context — dynamically load/unload tools by topic
- [ ] #499 — Wire up references.skills config to skill loader
- [x] #321 — feat: track and warn on tool definition token overhead

### Low

- [ ] #320 — feat: skill-as-API-guide pattern for lightweight service integrations
- [x] #96 — Load .parlor/commands/ as Anteroom skills

## Knowledge Management

*Notebooks, documents, semantic search, RAG. Making Anteroom a second brain that remembers and retrieves context.*

### High

- [ ] #350 — Add message-level FTS5 keyword search
- [ ] #360 — Add unified CLI /search command across full knowledge base
- [x] #109 — feat: default embeddings to disabled, improve separate endpoint config

### Medium

- [ ] #78 — feat: Transparent Markdown-based memory with sqlite-vec index
- [ ] #83 — feat: Knowledge notebooks — conversation types for logs, docs, and searchable content
- [ ] #217 — feat(tools): add save_memory tool for agent-initiated cross-session persistence
- [ ] #225 — feat(tools): add built-in web fetch and search tools
- [ ] #394 — Add recall tool for AI-mediated conversation retrieval
- [ ] #373 — Add context budget tracking with per-component visibility
- [ ] #625 — Add memory retention policy and eviction strategy
- [x] #212 — feat: add tree-sitter codebase index for token-efficient context
- [x] #310 — Add token budget warnings for usage self-regulation

### Low

- [x] #72 — feat: Markdown journaling with auto-export and Obsidian compatibility

## Developer Workflow

*VS Code extension, Git integration, project management tools. Deeper agentic capabilities: autonomous workflows, approval gates, long-running tasks, sub-agent orchestration.*

### High

- [ ] #218 — feat(cli): add structured JSON output mode for agent events
- [ ] #266 — feat(cli): render live plan checklist with execution progress
- [ ] #272 — feat(web): add plan mode approval flow to web UI
- [ ] #608 — feat(cli): migrate streaming pipeline to fullscreen output pane
- [ ] #621 — feat(agent): add checkpoint/rollback for agent file modifications
- [x] #159 — fix(cli): collapse_long_input shows raw ANSI codes when pasting multiline content
- [x] #267 — feat(cli): auto-invoke skills from natural language prompts

### Medium

- [ ] #114 — CLI: accessibility improvements (NO_COLOR, text markers, screen reader compat)
- [ ] #228 — feat(config): add agent configuration profiles
- [ ] #248 — feat(vscode): add @file/@folder mentions and partial file pasting in chat
- [ ] #282 — Add API conversation type for tracking external tool calls
- [ ] #298 — Add file change cards to web UI for write_file and edit_file results
- [ ] #301 — feat(routers): add live plan checklist to web UI chat
- [ ] #610 — Fix mypy type-check errors across codebase (499 errors)
- [x] #243 — Add VS Code extension for Anteroom
- [x] #257 — feat(cli): redesign prompt with persistent status header and context bar
- [x] #268 — feat: multi-pane AI-managed context panels for CLI and web
- [x] #274 — Store working directory in conversations for cross-interface continuity

### Low

- [ ] #235 — feat(cli): add conversation forking for branching explorations
- [ ] #237 — feat: add VS Code extension with chat, code assistant, and conversation sync
- [ ] #273 — Add real-time conversation sync between web UI and CLI
- [x] #74 — feat: Conversation templates for recurring workflows
- [x] #77 — feat: Scheduled/background conversations
- [x] #79 — feat: Heartbeat agent — proactive AI that doesn't wait for you
- [x] #80 — feat: Live multi-user agent sessions — collaborative prompting
- [x] #81 — feat: Multi-session task harness — delegate work that spans days
- [x] #167 — feat(cli): persistent task panel above prompt box using prompt_toolkit layout
- [x] #176 — feat: add webhook agent backend for n8n and external endpoints
- [x] #199 — feat(cli): compressed paste blocks with atomic delete
- [x] #214 — feat: multi-model pipeline with reasoning and editing roles
- [x] #227 — feat(tools): add undo/redo for file modifications
- [x] #229 — feat(cli): add LSP integration for codebase-aware context
- [x] #258 — feat: build anteroom-shell (ashell) — cross-platform AI shell on xonsh

## Other

### Medium

- [ ] #113 — Web UI: WCAG 2.2 AA compliance (ARIA, focus, contrast)

### Low

- [ ] #48 — Add MkDocs Material documentation site and /write-docs skill
- [ ] #112 — Add WCAG 2.2 AA accessibility rules and PR validation
- [ ] #116 — Add color theme support to CLI with color-blindness safe themes
- [x] #57 — Web UI: infinite scroll for conversation list
- [x] #58 — Web UI: bulk operations on conversations
- [x] #60 — Web UI: conversation import from markdown
- [x] #65 — Real-time collaboration on shared databases
- [x] #75 — feat: Conversation branching UI with tree visualization
