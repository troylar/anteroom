# Security Documentation Maintenance

When modifying security-related source files, the corresponding documentation pages must be updated to stay in sync.

## Source File → Doc Page Mapping

| Source File | Documentation Page | What to Update |
|---|---|---|
| `tools/safety.py` | `docs/security/tool-safety.md` | Destructive patterns list, SafetyVerdict fields |
| `tools/security.py` | `docs/security/tool-safety.md`, `docs/security/bash-sandboxing.md` | Hard-block patterns list (count and descriptions), network patterns, package patterns, blocked paths |
| `tools/tiers.py` | `docs/security/tool-safety.md` | Risk tiers, default tier assignments, approval modes |
| `services/audit.py` | `docs/security/audit-log.md` | AuditEntry fields, HMAC chain details, rotation behavior |
| `services/context_trust.py` | `docs/security/prompt-injection-defense.md` | Trust constants, envelope format, defensive instruction text, sanitization rules |
| `services/session_store.py` | `docs/security/authentication.md` | Session state fields, store behavior |
| `services/ip_allowlist.py` | `docs/security/authentication.md` | IP allowlist behavior |
| `services/tool_rate_limit.py` | `docs/security/tool-safety.md` | Rate limit behavior |
| `app.py` (middleware) | `docs/security/hardening.md`, `docs/security/index.md` | Security headers, middleware stack order |
| `config.py` (safety dataclasses) | All security doc pages | Config reference tables (field names, types, defaults, env vars) |
| `config.py` (`BashSandboxConfig`) | `docs/security/bash-sandboxing.md` | Bash sandbox config reference table |
| `config.py` (`AuditConfig`) | `docs/security/audit-log.md` | Audit config reference table |
| `config.py` (`SessionConfig`) | `docs/security/authentication.md` | Session config reference table |
| `config.py` (`SafetyConfig`) | `docs/security/tool-safety.md` | Safety config reference table |
| `config.py` (`SubagentConfig`) | `docs/security/hardening.md` | Sub-agent config reference table |
| `config.py` (`BudgetConfig`) | `docs/security/hardening.md` | Budget config reference table |

## What to Check

When a mapped source file changes:

1. **Config reference tables**: Ensure field names, types, defaults, and env var names match the dataclass
2. **Pattern lists**: Count hard-block patterns (currently 16) and destructive patterns (currently 12) — update if changed
3. **Feature grid** in `docs/security/index.md`: Verify the overview table matches current capabilities
4. **ASVS compliance** in `SECURITY.md`: Update status if a security control is added or modified

## When This Applies

- Adding or removing a hard-block pattern in `security.py`
- Adding or removing a destructive pattern in `safety.py`
- Adding, removing, or renaming a config field in any security-related dataclass
- Changing default values for security config fields
- Adding new middleware or changing the middleware stack order
- Adding or modifying audit event types
- Changing trust classification behavior
