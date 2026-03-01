# Anteroom Roadmap

Aligned with [VISION.md](VISION.md). Updated 2026-03-01.

Directions match VISION.md Section "Direction (Current)." Issues are sorted by priority within each section. Checked items are completed. Enterprise Infrastructure is the **critical path** — other directions progress in parallel where they don't depend on it.

## Enterprise Infrastructure *(Critical Path)*

*Server mode, Postgres, multi-user, SSO, RBAC, admin dashboard, Docker/K8s. Table stakes for getting Anteroom through a bank's architecture review.*

**Build order is sequential — each item depends on the ones above it:**

### Phase 1: Foundation

- [ ] #646 — feat(config): add deployment mode switch for local vs server behavior
- [ ] #642 — feat(db): add Postgres backend for server-mode multi-user deployment
- [ ] #626 — Add /healthz endpoint for operational monitoring

### Phase 2: Identity & Isolation

*Depends on: Phase 1 (#646, #642)*

- [ ] #645 — feat(app): add multi-user support with session isolation and per-user storage
- [ ] #639 — feat(auth): add SSO integration with SAML and OIDC
- [ ] #647 — feat(cli): add device-flow auth for CLI connections to server-mode Anteroom

### Phase 3: Authorization & Governance

*Depends on: Phase 2 (#645, #639)*

- [ ] #640 — feat(auth): add RBAC with per-role tool access, token budgets, and approval modes
- [ ] #657 — feat(services): invalidate active sessions on role change or account deactivation
- [ ] #624 — Enforce token budget limits per request, session, and per-user

### Phase 4: Admin & Deployment

*Depends on: Phase 3 (#640)*

- [ ] #641 — feat(routers): add admin dashboard for security controls, config, and audit visibility
- [ ] #644 — feat(audit): add log forwarding for Splunk, ELK, and SIEM integration
- [ ] #643 — feat(deploy): add Docker image and Kubernetes manifests for enterprise deployment

### Phase 5: Onboarding & Provisioning

*Depends on: Phase 2-3*

- [ ] #654 — feat: design solo-to-server migration path for enterprise onboarding
- [ ] #656 — feat(auth): add SCIM user provisioning for enterprise identity lifecycle

### Supporting

- [ ] #628 — Add air-gapped installation documentation

## Governance and Audit

*DLP hardening, MCP governance, data isolation, audit enrichment, regulatory compliance. Making Anteroom the AI gateway that CISOs and CCOs can approve for the entire organization.*

### High

- [ ] #649 — feat(services): harden DLP for server-mode with block-by-default and industry patterns
- [ ] #650 — feat(services): restrict MCP server configuration to admin role in server mode
- [ ] #648 — feat(services): add RAG and vector search tenant isolation for multi-user mode
- [ ] #651 — feat(services): add minimum audit retention floor and extended default for server mode
- [ ] #231 — feat(tools): add OS-level sandboxing for command execution (macOS/Linux)

### Medium

- [ ] #652 — feat(services): add automated audit chain integrity verification with alerting
- [ ] #653 — feat(services): add periodic access review export for compliance reporting
- [ ] #655 — feat: add self-service token budget visibility for non-admin users
- [ ] #99 — Store sub-agent tool calls in database for audit trail
- [ ] #627 — Emit audit events for egress domain checks (+ enforcement in server mode)
- [ ] #230 — feat(tools): add glob-pattern bash permission rules
- [ ] #501 — Surface error when project MCP servers are skipped due to untrusted config
- [x] #310 — Add token budget warnings for usage self-regulation
- [x] #297 — feat(tools): OS-level sandboxing for command execution (Windows)

## Accessibility

*Section 508 compliance for government-adjacent enterprises. Required for enterprise adoption, not optional.*

### Medium

- [ ] #113 — Web UI: WCAG 2.2 AA compliance (ARIA, focus, contrast)
- [ ] #114 — CLI: accessibility improvements (NO_COLOR, text markers, screen reader compat)
- [ ] #116 — Add color theme support to CLI with color-blindness safe themes

## Enterprise Knowledge Work

*Making Anteroom useful beyond developers — document generation, presentations, data analysis, reporting.*

### High

- [ ] #629 — feat(packs): add Office document Packs for Word, Excel, and PowerPoint workflows
- [ ] #630 — feat(packs): add shareable Pack templates for common enterprise tasks
- [ ] #633 — feat(static): add web UI onboarding flow for non-technical users

### Medium

- [ ] #632 — feat: add data analysis workflow with CSV/Excel ingestion and summary generation
- [ ] #607 — Enrich XLSX and DOCX read output with formatting context + add missing actions
- [ ] #592 — Add file extension validation to Office tools
- [x] #178 — Add document source scanning with folder watch and Confluence connector

### Low

- [ ] #634 — feat: add report generation skill for Markdown, Word, and PDF output
- [ ] #635 — feat(packs): add template-driven document generation via Packs

## Extensibility

*MCP ecosystem (with admin governance in server mode), custom tool authoring, shareable Packs.*

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

*Notebooks, documents, semantic search, RAG (with tenant isolation in server mode). Making Anteroom a second brain.*

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
- [ ] #336 — Return message-level search results with context
- [ ] #345 — feat(cli): add note/document message editing and type conversion
- [ ] #359 — Add conversation-to-knowledge extraction workflow
- [ ] #456 — Add passive recall: surface related past conversations without explicit query
- [ ] #457 — Epic: three-layer conversation memory (active, explicit, and passive recall)
- [x] #212 — feat: add tree-sitter codebase index for token-efficient context
- [x] #310 — Add token budget warnings for usage self-regulation

### Low

- [ ] #358 — Add knowledge base export and import
- [x] #72 — feat: Markdown journaling with auto-export and Obsidian compatibility

## Developer Workflow

*VS Code extension, Git integration, project management tools. Deeper agentic capabilities.*

### High

- [ ] #213 — feat(agent): auto-validate edits with lint and test feedback loop
- [ ] #218 — feat(cli): add structured JSON output mode for agent events
- [ ] #266 — feat(cli): render live plan checklist with execution progress
- [ ] #272 — feat(web): add plan mode approval flow to web UI
- [ ] #621 — feat(agent): add checkpoint/rollback for agent file modifications
- [x] #608 — feat(cli): migrate streaming pipeline to fullscreen output pane
- [x] #159 — fix(cli): collapse_long_input shows raw ANSI codes when pasting multiline content
- [x] #267 — feat(cli): auto-invoke skills from natural language prompts

### Medium

- [ ] #228 — feat(config): add agent configuration profiles
- [ ] #282 — Add API conversation type for tracking external tool calls
- [ ] #298 — Add file change cards to web UI for write_file and edit_file results
- [ ] #301 — feat(routers): add live plan checklist to web UI chat
- [ ] #610 — Fix mypy type-check errors across codebase (499 errors)
- [ ] #341 — feat(cli): add source management commands
- [ ] #346 — feat(cli): add file attachments to chat messages
- [ ] #347 — feat(cli): add database switching mid-session
- [ ] #385 — Add favorite/starred support to conversations
- [ ] #387 — Add conversation management to web UI sidebar
- [ ] #393 — Add unified @ autocomplete for files and conversations
- [x] #243 — Add VS Code extension for Anteroom
- [x] #257 — feat(cli): redesign prompt with persistent status header and context bar
- [x] #268 — feat: multi-pane AI-managed context panels for CLI and web
- [x] #274 — Store working directory in conversations for cross-interface continuity

### Low

- [ ] #237 — feat: add VS Code extension with chat, code assistant, and conversation sync
- [ ] #273 — Add real-time conversation sync between web UI and CLI
- [ ] #328 — feat(cli): add config/instruction hierarchy visualization command
- [ ] #342 — feat(cli): add conversation fork, export, and cross-DB copy
- [ ] #343 — feat(cli): add folder and tag management commands
- [ ] #348 — feat(cli): add canvas rendering with Rich panels
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

### Low

- [ ] #48 — Add MkDocs Material documentation site and /write-docs skill
- [x] #57 — Web UI: infinite scroll for conversation list
- [x] #58 — Web UI: bulk operations on conversations
- [x] #60 — Web UI: conversation import from markdown
- [x] #65 — Real-time collaboration on shared databases
- [x] #75 — feat: Conversation branching UI with tree visualization
