# Security Policy

Anteroom is designed with security as a core principle, targeting **OWASP ASVS v5.0 Level 2** compliance. This document outlines the security posture, threat model, and compliance status.

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.x     | Yes       |
| 0.9.x   | Yes       |
| < 0.9   | No        |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do not** open a public GitHub issue
2. Email security concerns to the repository maintainer
3. Include steps to reproduce, impact assessment, and any suggested fixes
4. Allow 90 days for a fix before public disclosure

## Threat Model

Anteroom is a **single-user, local-first application** intended to run on a user's machine or behind a corporate firewall. The threat model reflects this:

| Threat | Mitigation | Status |
|--------|-----------|--------|
| Unauthorized local access | Ed25519-derived HMAC-SHA256 auth token via HttpOnly cookie | Implemented |
| Session hijacking | Session expiry (12h absolute, 30min idle), concurrent session limits | Implemented |
| Session proliferation | Configurable max concurrent sessions, IP tracking | Implemented |
| Network-level access | IP allowlisting (CIDR + exact, IPv4/IPv6, fails closed) | Implemented |
| Cross-site request forgery | Double-submit cookie pattern + origin validation | Implemented |
| Cross-site scripting | Content Security Policy, DOMPurify sanitization, SRI | Implemented |
| Clickjacking | X-Frame-Options: DENY, frame-ancestors 'none' | Implemented |
| MIME sniffing | X-Content-Type-Options: nosniff | Implemented |
| Transport security | HSTS (max-age=31536000; includeSubDomains), TLS with ECDSA P-256 | Implemented |
| File upload abuse | MIME allowlist + magic-byte verification (filetype) | Implemented |
| Path traversal | Filename sanitization, resolved path validation, symlink resolution | Implemented |
| Destructive AI tool use | 4 risk tiers, 4 approval modes, 16 hard-block patterns | Implemented |
| Bash command injection | Sandboxing: timeout, output limits, path/command/network blocking | Implemented |
| Indirect prompt injection | Trust classification, defensive XML envelopes, tag sanitization | Implemented |
| Malicious MCP servers (SSRF) | DNS resolution validation, private IP rejection | Implemented |
| MCP tool injection | Shell metacharacter rejection, per-server tool filtering | Implemented |
| Runaway AI costs | Token budgets (per-request, per-conversation, per-day) | Implemented |
| Tool abuse / DoS | Tool rate limiting (per-minute, per-conversation, consecutive failures) | Implemented |
| Sub-agent abuse | Concurrency, depth, iteration, timeout, and output limits | Implemented |
| Audit tampering | HMAC-SHA256 chain, append-only JSONL, fcntl locking, fsync | Implemented |
| Dependency vulnerabilities | pip-audit in CI, Dependabot enabled | Implemented |
| Request flooding | Per-IP rate limiting (120 req/min) | Implemented |
| Oversized payloads | 15 MB request body limit, 10 MB attachment limit | Implemented |
| Information leakage | Generic error messages, no stack traces in responses | Implemented |
| Sensitive data in cache | Cache-Control: no-store on all API responses | Implemented |
| API key exposure | Token provider with in-memory caching, no logging of secrets | Implemented |
| Identity key exposure | Private key in 0600 config file, never exposed via API | Implemented |
| Identity spoofing in shared DBs | Ed25519 keypair per user, public key registered on connect | Implemented |
| Team config bypass | Enforced fields, SHA-256 trust verification for project configs | Implemented |

## OWASP ASVS v5.0 Compliance

Anteroom targets **ASVS Level 2** (Standard) compliance.

### V1: Architecture & Threat Modeling

| Requirement | Status | Notes |
|------------|--------|-------|
| V1.1 Secure architecture | Pass | Layered middleware stack, server-side security decisions |
| V1.2 Third-party components | Pass | pip-audit, Dependabot, minimal dependencies |

### V2: Authentication

| Requirement | Status | Notes |
|------------|--------|-------|
| V2.1 Password security | N/A | Token-based auth, no passwords |
| V2.5 Credential recovery | N/A | Single-user, deterministic token from Ed25519 key |
| V2.7 Session binding | Pass | HttpOnly, Secure, SameSite=Strict cookies |
| V2.8 Session expiry | Pass | 12h absolute + 30min idle timeout, concurrent limits |
| V2.10 Logout invalidation | Pass | Session deletion on POST /api/logout, cookie cleared |

### V3: Session Management

| Requirement | Status | Notes |
|------------|--------|-------|
| V3.1 Session token entropy | Pass | HMAC-SHA256 derived from Ed25519 key (256-bit) |
| V3.2 Cookie security flags | Pass | HttpOnly, Secure (non-localhost), SameSite=Strict |
| V3.4 Session timeout | Pass | Absolute + idle timeouts enforced, configurable |
| V3.5 Server-side validation | Pass | Hash comparison via hmac.compare_digest |
| V3.6 Session stores | Pass | Memory (volatile) or SQLite (durable) backends |
| V3.7 Concurrent sessions | Pass | Configurable limit, IP tracking per session |

### V3 (Web Frontend Security — new in ASVS v5.0)

| Requirement | Status | Notes |
|------------|--------|-------|
| V3.1 Content Security Policy | Pass | `script-src 'self'; frame-ancestors 'none'` |
| V3.2 Subresource Integrity | Pass | SHA-384 hashes on all vendor scripts |
| V3.3 Cross-origin isolation | Partial | X-Frame-Options DENY; COOP/COEP not yet applied |

### V4: Access Control

| Requirement | Status | Notes |
|------------|--------|-------|
| V4.1 Authorization checks | Pass | All /api/ endpoints require valid token |
| V4.2 CSRF protection | Pass | Double-submit cookie + origin validation |
| V4.3 IP-based access control | Pass | Configurable allowlist (CIDR + exact), fails closed |

### V5: Validation, Sanitization, Encoding

| Requirement | Status | Notes |
|------------|--------|-------|
| V5.1 Input validation | Pass | Server-side validation, max_length constraints |
| V5.2 Sanitization | Pass | DOMPurify for HTML, filename sanitization |
| V5.3 Output encoding | Pass | JSON serialization, CSP headers |
| V5.4 Parameterized queries | Pass | Column-allowlisted SQL builder, ? placeholders |
| V5.5 File upload validation | Pass | MIME allowlist + magic-byte verification |

### V6: Cryptography

| Requirement | Status | Notes |
|------------|--------|-------|
| V6.1 Algorithm strength | Pass | Ed25519, HMAC-SHA256, HKDF-SHA256 |
| V6.2 Random values | Pass | secrets.token_urlsafe, CSPRNG-backed |
| V6.3 Secret management | Pass | API keys via env vars or api_key_command, never hardcoded |
| V6.4 Identity keys | Pass | Ed25519 via cryptography lib, PKCS8 PEM, 0600 permissions |

### V7: Error Handling and Logging

| Requirement | Status | Notes |
|------------|--------|-------|
| V7.1 Generic error messages | Pass | No stack traces or internal details exposed |
| V7.2 Security event logging | Pass | Structured audit log with HMAC chain integrity |
| V7.3 No sensitive data in logs | Pass | Content redaction, API keys/tokens never logged |

### V8: Data Protection

| Requirement | Status | Notes |
|------------|--------|-------|
| V8.1 Sensitive data in transit | Pass | Secure cookie flag, HTTPS support, HSTS |
| V8.2 Anti-caching | Pass | Cache-Control: no-store on API responses |
| V8.3 Sensitive data in responses | Pass | API key shown as boolean presence, never exposed |

### V9: Communication

| Requirement | Status | Notes |
|------------|--------|-------|
| V9.1 TLS for external calls | Pass | verify_ssl default: enabled, HSTS enforced |
| V9.2 HSTS | Pass | max-age=31536000; includeSubDomains |

### V9 (Self-Contained Tokens — new in ASVS v5.0)

| Requirement | Status | Notes |
|------------|--------|-------|
| V9.1 Token validation | Pass | HMAC-SHA256 signature validation on every request |
| V9.2 Token expiry | Pass | Absolute + idle timeouts enforced server-side |

### V10 (OAuth 2.0 / OIDC — new in ASVS v5.0)

| Requirement | Status | Notes |
|------------|--------|-------|
| V10 | N/A | Anteroom uses direct token auth, not OAuth/OIDC |

### V13: API Security

| Requirement | Status | Notes |
|------------|--------|-------|
| V13.1 Rate limiting | Pass | 120 requests/minute per IP |
| V13.2 Request size limits | Pass | 15 MB body limit, 10 MB attachment limit |
| V13.3 Content-Type validation | Pass | Explicit content-type handling |
| V13.4 Tool rate limiting | Pass | Per-minute, per-conversation, consecutive failure caps |

### V14: Configuration

| Requirement | Status | Notes |
|------------|--------|-------|
| V14.1 Security headers | Pass | CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy, HSTS |
| V14.2 Dependency management | Pass | pip-audit in CI, Dependabot for automated updates |
| V14.3 Server identification | Pass | Server and X-Powered-By headers not exposed |
| V14.4 HTTP security headers | Pass | Full suite applied via SecurityHeadersMiddleware |

## Security Architecture

```
Browser ──HTTPS──▶ Anteroom (FastAPI)
                      │
                      ├── IP Allowlist (CIDR / exact)
                      ├── BearerTokenMiddleware (Ed25519-derived auth)
                      ├── Session Store (memory or SQLite)
                      ├── RateLimitMiddleware (120/min per IP)
                      ├── MaxBodySizeMiddleware (15 MB)
                      ├── SecurityHeadersMiddleware (CSP, HSTS, etc.)
                      ├── CSRF validation (double-submit + origin)
                      │
                      ├──▶ Agent Loop
                      │      ├── Tool Safety Gate (4 tiers, 4 modes)
                      │      ├── Hard-block patterns (14 catastrophic)
                      │      ├── Bash Sandbox (timeout, paths, network)
                      │      ├── Tool Rate Limiter
                      │      ├── Context Trust (prompt injection defense)
                      │      └── Sub-agent Limiter
                      │
                      ├──▶ SQLite (local, 0600 perms, parameterized queries)
                      ├──▶ AI Backend (OpenAI-compatible, verify_ssl)
                      │      └── TokenProvider (auto-refresh on 401)
                      ├──▶ MCP Servers (SSRF-protected, metachar rejection)
                      └──▶ Audit Log (HMAC-chained JSONL, fcntl locking)
```

## API Key Management

Anteroom supports two methods for API key configuration:

1. **Static key**: Set `ai.api_key` in config.yaml or `AI_CHAT_API_KEY` env var
2. **Dynamic key via command**: Set `ai.api_key_command` to run an external command

The `api_key_command` feature:

- Executed via `subprocess.run()` with `shlex.split()` — **no shell=True**, preventing shell injection
- 30-second execution timeout prevents hanging commands
- Token cached in memory only, never written to disk or logged
- On HTTP 401, command re-run automatically with transparent retry
- Empty output and non-zero exit codes rejected with clear error messages

## Configuration Hardening

For production deployments, see the [Deployment Hardening](https://anteroom.readthedocs.io/en/latest/security/hardening/) guide, which includes a comprehensive hardening checklist.

## Dependency Security

- **Automated scanning**: `pip-audit` runs in CI on every push and PR
- **SAST**: Semgrep and CodeQL scans in CI
- **Automated updates**: Dependabot monitors pip and GitHub Actions dependencies weekly
- **Minimal dependencies**: Only essential packages included to reduce attack surface

## Detailed Documentation

For comprehensive security documentation, see:

- [Security Overview](https://anteroom.readthedocs.io/en/latest/security/)
- [Authentication](https://anteroom.readthedocs.io/en/latest/security/authentication/)
- [Tool Safety](https://anteroom.readthedocs.io/en/latest/security/tool-safety/)
- [Bash Sandboxing](https://anteroom.readthedocs.io/en/latest/security/bash-sandboxing/)
- [Audit Log](https://anteroom.readthedocs.io/en/latest/security/audit-log/)
- [Prompt Injection Defense](https://anteroom.readthedocs.io/en/latest/security/prompt-injection-defense/)
- [Deployment Hardening](https://anteroom.readthedocs.io/en/latest/security/hardening/)
