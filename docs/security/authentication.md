# Authentication

Anteroom uses a deterministic token system derived from Ed25519 cryptographic identity keys, with session management, CSRF protection, IP allowlisting, and concurrent session limits.

## Ed25519 Identity System

On first run, Anteroom auto-generates a cryptographic identity:

1. **Ed25519 keypair** — generated via the `cryptography` library
2. **UUID4 user ID** — unique per installation
3. **Display name** — from the OS username

The identity is stored in `~/.anteroom/config.yaml` with `0600` permissions (owner read/write only). The private key is serialized as PKCS8 PEM and never exposed via any API endpoint.

```yaml
# Auto-generated — do not edit
identity:
  user_id: "550e8400-e29b-41d4-a716-446655440000"
  display_name: "troy"
  public_key: "-----BEGIN PUBLIC KEY-----\n..."
  private_key: "-----BEGIN PRIVATE KEY-----\n..."
```

## Auth Token Derivation

The session auth token is derived deterministically from the Ed25519 private key:

```
HMAC-SHA256(private_key_pem, "anteroom-session-v1") → auth_token
```

This produces a **stable token that survives server restarts** — no re-authentication needed after rebooting. The token is set as an HttpOnly cookie on first visit.

If no identity is configured (e.g., during initial setup), Anteroom falls back to `secrets.token_urlsafe(32)`.

### Token Validation

- Token is hashed with SHA-256 before comparison
- Comparison uses `hmac.compare_digest` (timing-safe)
- Session ID is derived deterministically: `SHA-256(token)[:32]`

## Session Stores

Sessions can be stored in-memory or persisted to SQLite:

| Store | Persistence | Use Case |
|-------|-------------|----------|
| `memory` (default) | Volatile — lost on restart | Development, single-machine |
| `sqlite` | Durable — survives restarts | Production, enterprise |

```yaml
session:
  store: sqlite
```

### Session State

Each session tracks:

| Field | Description |
|---|---|
| `id` | Deterministic SHA-256 hash of token (32 chars) |
| `user_id` | From Ed25519 identity |
| `ip_address` | Client IP at session creation |
| `created_at` | Session creation timestamp |
| `last_activity_at` | Updated on every authenticated request |

## Session Lifecycle

1. **Creation**: On first successful auth, a session is created and logged (if `session.log_session_events` enabled)
2. **Activity tracking**: `last_activity_at` updated on every authenticated request
3. **Idle timeout**: Session expires after a configurable period of inactivity (default 30 minutes)
4. **Absolute timeout**: Session forcibly expires after a fixed duration (default 12 hours)
5. **Cleanup**: Expired sessions deleted on next request
6. **Logout**: `POST /api/logout` deletes the session and clears the cookie

## Concurrent Session Limits

Prevent token reuse and session proliferation:

```yaml
session:
  max_concurrent_sessions: 3   # 0 = unlimited (default)
```

When the limit is reached, new sessions return `429 Too Many Sessions`.

## IP Allowlisting

Network-level access control applied before session validation:

```yaml
session:
  allowed_ips:
    - "192.168.1.0/24"        # CIDR range
    - "10.0.0.5"              # Exact IP
    - "2001:db8::/32"         # IPv6 CIDR
```

| Behavior | Description |
|---|---|
| Empty list | No restrictions (allow all) |
| Non-empty list | Only listed IPs/ranges allowed |
| Invalid IP | Denied (fails closed) |
| Unlisted IP | Denied with `403 Forbidden` |

## Cookie Configuration

| Attribute | Value | Purpose |
|---|---|---|
| `HttpOnly` | `true` | Prevents JavaScript access |
| `Secure` | `true` (non-localhost) | HTTPS only |
| `SameSite` | `Strict` | Prevents cross-site requests |
| `Max-Age` | `absolute_timeout` value | Matches session lifetime |
| `Path` | `/api/` (session), `/` (CSRF) | Scoped appropriately |

## CSRF Protection

Anteroom uses the double-submit cookie pattern:

1. A CSRF token is generated per session
2. The token is stored in a cookie (`Path=/`) and must be sent as a request header
3. All `POST`, `PATCH`, `PUT`, `DELETE` requests are validated
4. Origin header is validated against the expected origin
5. Token comparison uses HMAC-SHA256 for timing-safe verification

## Session Expiry Handling (Web UI)

When the browser receives a 401 response (expired or invalid session):

1. The client redirects to `/` to obtain a fresh session cookie
2. Anti-loop protection: if two 401 redirects occur within 5 seconds, a fixed banner is shown instead of reloading
3. The banner instructs the user to manually refresh

## Configuration Reference

### `session.*`

| Field | Type | Default | Env Var | Description |
|---|---|---|---|---|
| `store` | string | `"memory"` | `AI_CHAT_SESSION_STORE` | `"memory"` or `"sqlite"` |
| `max_concurrent_sessions` | int | `0` | `AI_CHAT_SESSION_MAX_CONCURRENT` | Max active sessions (0 = unlimited) |
| `idle_timeout` | int | `1800` | `AI_CHAT_SESSION_IDLE_TIMEOUT` | Seconds of inactivity before expiry (min 60) |
| `absolute_timeout` | int | `43200` | `AI_CHAT_SESSION_ABSOLUTE_TIMEOUT` | Max session lifetime in seconds (min 300) |
| `allowed_ips` | list[str] | `[]` | `AI_CHAT_SESSION_ALLOWED_IPS` | IP allowlist (CIDR or exact; comma-separated for env var) |
