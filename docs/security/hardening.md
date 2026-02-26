# Deployment Hardening

Security controls and configuration recommendations for production deployments.

## Security Headers

Applied to every response by `SecurityHeadersMiddleware`:

| Header | Value | Purpose |
|---|---|---|
| `Content-Security-Policy` | `script-src 'self'; frame-ancestors 'none'` | Prevents XSS and clickjacking |
| `X-Frame-Options` | `DENY` | Prevents clickjacking |
| `X-Content-Type-Options` | `nosniff` | Prevents MIME sniffing |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Controls referrer information |
| `Permissions-Policy` | Restrictive | Limits browser feature access |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | Enforces HTTPS (when TLS enabled) |
| `Cache-Control` | `no-store` | Prevents caching of API responses |

Server identification headers (`Server`, `X-Powered-By`) are not exposed.

## TLS

Anteroom generates self-signed ECDSA P-256 certificates for localhost HTTPS:

```yaml
app:
  tls: true
```

When TLS is enabled:

- Self-signed cert auto-generated on first run
- HSTS header enforced on all responses
- `Secure` flag set on all cookies
- SSL verification enabled by default for AI backend connections (`ai.verify_ssl: true`)

For production, use a reverse proxy (nginx, Caddy) with proper certificates instead of the built-in self-signed certs.

## Subresource Integrity (SRI)

All vendor scripts (marked.js, highlight.js, KaTeX, DOMPurify) include SHA-384 hashes. If a CDN or file is tampered with, the browser refuses to execute it.

## Rate Limiting

- **120 requests per minute** per IP address
- Uses LRU eviction for the IP tracking map
- Applied to all endpoints

## Request Size Limits

| Limit | Value |
|---|---|
| Max request body | 15 MB |
| Max file attachment | 10 MB |
| Max files per message | 10 |

## CORS

- Locked to the configured origin (no wildcards)
- Explicit method allowlist (`GET`, `POST`, `PATCH`, `PUT`, `DELETE`)
- Explicit header allowlist
- Authenticated endpoints never use `Access-Control-Allow-Origin: *`

## API Surface Reduction

- OpenAPI/Swagger documentation disabled in production
- Server version headers not exposed
- Error responses return generic messages (no stack traces, no SQL errors)

## File Upload Security

- MIME type allowlist with magic-byte verification (using `filetype` library)
- Filenames sanitized: path components stripped, special characters replaced
- Non-image files force-download (never rendered in-browser)
- Attachments stored outside webroot with path traversal prevention

## Database Security

- Column-allowlisted SQL builder prevents injection
- All queries use parameterized statements (`?` placeholders)
- Database files created with `0600` permissions (owner-only)
- Data directory created with `0700` permissions
- UUID validation on all ID parameters

## Read-Only Mode

Restrict the AI to read-only operations in untrusted or shared environments:

```yaml
safety:
  read_only: true
```

When enabled:

- Only READ-tier tools are available (`read_file`, `glob_files`, `grep`, `introspect`, `ask_user`, canvas tools, `invoke_skill`)
- All WRITE, EXECUTE, and DESTRUCTIVE tools are blocked
- AI cannot modify files, run bash commands, or spawn sub-agents
- Toggle at runtime: `aroom chat --read-only` or `AI_CHAT_READ_ONLY=true`

## Token Budget Enforcement

Denial-of-wallet prevention via configurable token consumption limits:

```yaml
cli:
  usage:
    budgets:
      enabled: true
      max_tokens_per_request: 50000
      max_tokens_per_conversation: 500000
      max_tokens_per_day: 2000000
      warn_threshold_percent: 80
      action_on_exceed: block        # "block" or "warn"
```

### Budget Config Reference

| Field | Type | Default | Env Var | Description |
|---|---|---|---|---|
| `enabled` | bool | `false` | `AI_CHAT_BUDGET_ENABLED` | Enable budget enforcement |
| `max_tokens_per_request` | int | `0` | `AI_CHAT_BUDGET_MAX_TOKENS_PER_REQUEST` | Per-request limit (0 = unlimited) |
| `max_tokens_per_conversation` | int | `0` | `AI_CHAT_BUDGET_MAX_TOKENS_PER_CONVERSATION` | Per-conversation limit (0 = unlimited) |
| `max_tokens_per_day` | int | `0` | `AI_CHAT_BUDGET_MAX_TOKENS_PER_DAY` | Daily limit (0 = unlimited) |
| `warn_threshold_percent` | int | `80` | `AI_CHAT_BUDGET_WARN_THRESHOLD_PERCENT` | Warning at this % of limit |
| `action_on_exceed` | string | `"block"` | `AI_CHAT_BUDGET_ACTION_ON_EXCEED` | `"block"` or `"warn"` |

## Sub-Agent Safety

The `run_agent` tool spawns isolated child AI sessions. Multiple layers prevent abuse:

```yaml
safety:
  subagent:
    max_concurrent: 5          # simultaneous sub-agents
    max_total: 10              # total per root request
    max_depth: 3               # nesting levels
    max_iterations: 15         # tool calls per sub-agent
    timeout: 120               # wall-clock seconds (10–600)
    max_output_chars: 4000     # output truncation
    max_prompt_chars: 32000    # prompt size cap
```

### Sub-Agent Config Reference

| Field | Type | Default | Range | Description |
|---|---|---|---|---|
| `max_concurrent` | int | `5` | 1–20 | Simultaneous sub-agents |
| `max_total` | int | `10` | 1–50 | Total per root request |
| `max_depth` | int | `3` | 1–10 | Nesting depth |
| `max_iterations` | int | `15` | 1–100 | Tool calls per sub-agent |
| `timeout` | int | `120` | 10–600 | Wall-clock timeout (seconds) |
| `max_output_chars` | int | `4000` | 100–100,000 | Output truncation |
| `max_prompt_chars` | int | `32000` | 100–100,000 | Prompt size cap |

### Sub-Agent Isolation

- Each sub-agent gets a deep-copied `AIService` config (no shared mutable state)
- Sub-agents have their own message history (cannot see parent conversation)
- Defensive system prompt constrains sub-agent behavior
- At max depth, `run_agent` is removed from the child's available tools
- Parent's approval callback propagates to children (same safety gates)
- Model ID is regex-validated (`^[a-zA-Z0-9._:/-]{1,128}$`)

## MCP Tool Safety

MCP tools are gated by the same safety system as built-in tools, with additional protections:

- **Default tier**: All MCP tools default to `EXECUTE` tier (requires approval in `ask_for_writes` mode)
- **SSRF protection**: DNS resolution validates that target URLs don't point to private IP addresses
- **Shell metacharacter rejection**: Tool arguments sanitized to prevent command injection
- **Tool filtering**: Per-server `tools_include` / `tools_exclude` with fnmatch patterns
- **Trust levels**: Per-server `trust_level` controls [prompt injection defense](prompt-injection-defense.md) envelope wrapping

```yaml
mcp_servers:
  - name: internal-tools
    command: npx
    args: ["-y", "@my-org/tools"]
    trust_level: trusted
    tools_include:
      - "search_*"
      - "read_*"

  - name: external-api
    command: npx
    args: ["-y", "@third-party/api"]
    trust_level: untrusted       # default
    tools_exclude:
      - "admin_*"
```

## Team Config Enforcement

Team administrators can lock security settings across all team members:

```yaml
# team-config.yaml
enforce:
  - safety.approval_mode
  - safety.bash.allow_network
  - safety.bash.allow_package_install
  - safety.denied_tools
  - audit.enabled

safety:
  approval_mode: ask
  bash:
    allow_network: false
    allow_package_install: false
  denied_tools:
    - dangerous_tool

audit:
  enabled: true
```

Enforced fields cannot be overridden by personal config, project config, or environment variables. Project configs require SHA-256 trust verification before being applied.

## Hardening Checklist

!!! tip "Recommended Steps for Production Deployments"

    - [ ] Enable TLS (`app.tls: true`) or use a reverse proxy with proper certificates
    - [ ] Set `session.store: sqlite` for durable sessions
    - [ ] Configure `session.allowed_ips` to restrict access
    - [ ] Set `session.max_concurrent_sessions` to a reasonable limit
    - [ ] Set `safety.approval_mode: ask` or `ask_for_dangerous`
    - [ ] Disable network access in bash: `safety.bash.allow_network: false`
    - [ ] Disable package installs: `safety.bash.allow_package_install: false`
    - [ ] Enable audit logging: `audit.enabled: true`
    - [ ] Enable command audit: `safety.bash.log_all_commands: true`
    - [ ] Configure token budgets to prevent runaway costs
    - [ ] Set up IP allowlisting for known networks
    - [ ] Use team config enforcement for shared security policies
    - [ ] Review MCP server trust levels (default `untrusted` is correct for external servers)
    - [ ] Run `pip-audit` regularly to check for dependency vulnerabilities
