<p align="center">
  <img src="https://img.shields.io/pypi/v/parlor?style=flat-square&color=blue" alt="PyPI Version">
  <img src="https://img.shields.io/pypi/pyversions/parlor?style=flat-square" alt="Python Versions">
  <img src="https://img.shields.io/github/actions/workflow/status/troylar/parlor/test.yml?style=flat-square&label=tests" alt="Tests">
  <img src="https://img.shields.io/github/license/troylar/parlor?style=flat-square" alt="License">
</p>

<h1 align="center">Parlor</h1>
<p align="center"><strong>A private parlor for AI conversation.</strong></p>
<p align="center">
Self-hosted ChatGPT-style web UI that connects to any OpenAI-compatible API.<br>
Install with pip. Run locally. Own your data.
</p>

---

## Why Parlor?

Parlor is a **security-first**, locally-run chat interface built to [OWASP ASVS L1](SECURITY.md) standards. It connects to **any** OpenAI-compatible endpoint --- your company's internal API, OpenAI, Azure, Ollama, LM Studio, or anything else that speaks the OpenAI protocol.

- **Enterprise security** --- OWASP ASVS L1 compliant: CSRF protection, session management, CSP, rate limiting, MIME verification, input sanitization ([full matrix](SECURITY.md))
- **One command install** --- `pip install parlor`
- **Zero cloud dependency** --- everything runs on your machine
- **Conversations persist** --- SQLite database, local filesystem
- **MCP tool support** --- extend your AI with external tools

---

## Quick Start

```bash
pip install parlor
```

Create `~/.ai-chat/config.yaml`:

```yaml
ai:
  base_url: "https://your-ai-endpoint/v1"
  api_key: "your-api-key"
  model: "gpt-4"
```

Test your connection:

```bash
parlor --test
```

Launch:

```bash
parlor
```

Your browser opens automatically to `http://127.0.0.1:8080`.

---

## Features

### Conversations

- Create, rename, search, export, and delete conversations
- Full-text search across all messages and titles
- Export any conversation to Markdown
- Auto-generated titles from your first message
- Keyboard shortcuts: `Ctrl+Shift+N` (new), `Escape` (stop generation)

### Rich Rendering

- **Markdown** with full GFM support
- **Code blocks** with syntax highlighting and one-click copy
- **LaTeX math** rendering (inline and display)
- **Tables, lists, blockquotes** --- all rendered beautifully

### File Attachments

- Drag-and-drop or click to attach
- Supports 30+ file types: code, documents, images, data files
- Up to 10 files per message, 10 MB each
- Image previews inline

### MCP Tool Integration

- Connect stdio or SSE-based MCP servers
- AI can call tools during conversation
- Tool calls displayed with expandable input/output
- Configure multiple servers in `config.yaml`

### Streaming

- Real-time token-by-token streaming via SSE
- Stop generation mid-response with Escape or the stop button
- Thinking indicator while the AI processes

---

## Configuration

### Config File

`~/.ai-chat/config.yaml`

```yaml
ai:
  base_url: "https://your-ai-endpoint/v1"
  api_key: "your-api-key"
  model: "gpt-4"
  system_prompt: "You are a helpful assistant."
  verify_ssl: true  # set false for self-signed certs

app:
  host: "127.0.0.1"
  port: 8080
  data_dir: "~/.ai-chat"

# Optional: MCP tool servers
mcp_servers:
  - name: "my-tools"
    transport: "stdio"
    command: "npx"
    args: ["-y", "@my-org/mcp-tools"]

  - name: "remote-tools"
    transport: "sse"
    url: "https://mcp-server.example.com/sse"
```

### Environment Variables

Every config option has an env var override:

| Variable | Default | Description |
|---|---|---|
| `AI_CHAT_BASE_URL` | --- | AI API endpoint (required) |
| `AI_CHAT_API_KEY` | --- | API authentication key (required) |
| `AI_CHAT_MODEL` | `gpt-4` | Model name |
| `AI_CHAT_SYSTEM_PROMPT` | `You are a helpful assistant.` | System prompt |
| `AI_CHAT_VERIFY_SSL` | `true` | SSL certificate verification |

### Settings UI

Click the gear icon in the sidebar to change model and system prompt at runtime. Available models are fetched live from your API.

---

## CLI

```
parlor              # Start the server and open browser
parlor --test       # Test connection: list models, send a test prompt, exit
parlor --help       # Show help
```

### `--test` Output

```
Config:
  Endpoint: https://your-ai-endpoint/v1
  Model:    gpt-4
  SSL:      enabled

1. Listing models...
   OK - 12 model(s) available
     - gpt-4
     - gpt-4-turbo
     - gpt-3.5-turbo
     ...

2. Sending test prompt to gpt-4...
   OK - Response: Hello! How can I help you today?

All checks passed.
```

---

## Security

Parlor is hardened for use on corporate networks and shared machines.

| Layer | Protection |
|---|---|
| **Authentication** | Random session token with HttpOnly cookies, HMAC-SHA256 timing-safe comparison |
| **Content Security Policy** | `script-src 'self'`, `frame-ancestors 'none'`, no inline scripts |
| **Headers** | X-Frame-Options DENY, X-Content-Type-Options nosniff, strict Referrer-Policy, Permissions-Policy |
| **Input Sanitization** | DOMPurify on all rendered HTML, parameterized SQL, UUID validation |
| **Rate Limiting** | 120 req/min per IP with LRU eviction |
| **Body Size Limit** | 15 MB max request size |
| **CORS** | Locked to configured origin, explicit method/header allowlist |
| **File Safety** | MIME type allowlist, path traversal prevention, forced download for non-image types |
| **MCP Safety** | SSRF protection with DNS resolution, shell metacharacter rejection in tool args |
| **Subresource Integrity** | SHA-384 hashes on all vendor scripts |
| **API Surface** | OpenAPI/Swagger docs disabled in production |

---

## Data Storage

All data stays on your machine:

```
~/.ai-chat/
  config.yaml          # Your configuration (permissions: 0600)
  chat.db              # SQLite database with WAL journaling
  attachments/         # Uploaded files organized by conversation
```

The data directory is created with `0700` permissions (owner-only access).

---

## Supported File Types

**Code:** `.py` `.js` `.ts` `.java` `.c` `.cpp` `.h` `.hpp` `.rs` `.go` `.rb` `.php` `.sh` `.bat` `.ps1` `.sql` `.css`

**Data:** `.json` `.yaml` `.yml` `.csv` `.xml` `.toml` `.ini` `.cfg` `.log`

**Documents:** `.txt` `.md` `.pdf`

**Images:** `.png` `.jpg` `.jpeg` `.gif` `.webp`

---

## API

Parlor exposes a REST API on the same port. All endpoints require authentication.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/conversations` | List conversations (with optional `?search=`) |
| `POST` | `/api/conversations` | Create new conversation |
| `GET` | `/api/conversations/:id` | Get conversation with messages |
| `PATCH` | `/api/conversations/:id` | Rename conversation |
| `DELETE` | `/api/conversations/:id` | Delete conversation and attachments |
| `GET` | `/api/conversations/:id/export` | Download as Markdown |
| `POST` | `/api/conversations/:id/chat` | Stream chat (SSE) |
| `POST` | `/api/conversations/:id/stop` | Cancel active generation |
| `GET` | `/api/attachments/:id` | Download attachment |
| `GET` | `/api/config` | Get current config |
| `PATCH` | `/api/config` | Update model/system prompt |
| `POST` | `/api/config/validate` | Test connection and list models |
| `GET` | `/api/mcp/tools` | List available MCP tools |

---

## Development

```bash
git clone https://github.com/troylar/parlor.git
cd parlor
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Lint & format
ruff check src/ tests/
ruff format src/ tests/
```

### Tech Stack

| Component | Technology |
|---|---|
| Backend | Python 3.10+, FastAPI, Uvicorn |
| Frontend | Vanilla JS, marked.js, highlight.js, KaTeX, DOMPurify |
| Database | SQLite with FTS5 full-text search |
| AI SDK | OpenAI Python SDK (async) |
| MCP | Model Context Protocol SDK |
| Streaming | Server-Sent Events (SSE) |

---

## License

MIT
