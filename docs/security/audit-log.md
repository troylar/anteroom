# Audit Log

Anteroom includes a structured audit logging system designed for enterprise compliance and SIEM integration. Logs are written in append-only JSONL format with optional HMAC-SHA256 chain tamper protection.

## Overview

When enabled, Anteroom records security-relevant events (authentication, tool calls) to daily JSONL files. Each entry is a self-contained JSON object on its own line, ready for ingestion by Splunk, ELK/OpenSearch, or any SIEM that supports JSONL.

```yaml
audit:
  enabled: true
```

## JSONL Format

Each line is a JSON object with these fields:

| Field | Type | Description |
|---|---|---|
| `timestamp` | string | ISO 8601 UTC timestamp |
| `event_type` | string | Event category (e.g., `auth.login`, `tool_calls.bash`) |
| `severity` | string | `info`, `warning`, `error`, or `critical` |
| `session_id` | string | Session identifier |
| `user_id` | string | User identifier (from Ed25519 identity) |
| `source_ip` | string | Client IP address |
| `conversation_id` | string | Conversation UUID |
| `tool_name` | string | Tool name (for tool call events) |
| `details` | object | Event-specific metadata |
| `_prev_hmac` | string | Previous entry's HMAC (when tamper protection enabled) |
| `_hmac` | string | This entry's HMAC (when tamper protection enabled) |

Example entry:

```json
{"timestamp":"2026-02-26T14:30:00+00:00","event_type":"tool_calls.bash","severity":"info","session_id":"abc123","user_id":"user-uuid","source_ip":"127.0.0.1","conversation_id":"conv-uuid","tool_name":"bash","details":{"command":"[REDACTED]"},"_prev_hmac":"genesis","_hmac":"dGhpcyBpcyBhIGJhc2U2NCBleGFtcGxl"}
```

## Event Types

Events are organized by category. Each category can be independently toggled:

```yaml
audit:
  events:
    auth: true          # authentication events (default: true)
    tool_calls: true    # tool execution events (default: true)
```

| Category | Event Types | Description |
|---|---|---|
| `auth` | `auth.login`, `auth.logout`, `auth.failed`, `auth.session_expired` | Authentication lifecycle |
| `tool_calls` | `tool_calls.<tool_name>` | Tool execution, approval, denial |

When a category is disabled, events in that category are silently dropped. Unknown categories default to enabled.

## Tamper Protection

### HMAC-SHA256 Chain

When `tamper_protection: hmac` (the default), each entry is chained to the previous via HMAC-SHA256:

1. **Key derivation**: A dedicated HMAC key is derived from the Ed25519 identity private key via HKDF-SHA256 with salt `anteroom-audit-hmac-salt-v1` and info `anteroom-audit-v1`
2. **Genesis entry**: The first entry in each day's log uses `"genesis"` as the previous HMAC value
3. **Chain computation**: `HMAC-SHA256(key, prev_hmac || "|" || entry_json)` where `entry_json` is the entry without HMAC fields
4. **Result**: Each entry stores `_prev_hmac` (the previous entry's HMAC) and `_hmac` (its own computed HMAC)

Any modification, deletion, or reordering of entries breaks the chain and is detectable via verification.

### Disabling Tamper Protection

```yaml
audit:
  tamper_protection: none   # no HMAC chain
```

## Content Redaction

By default, message content and tool I/O are redacted from audit entries to prevent sensitive data leakage:

```yaml
audit:
  redact_content: true   # default
```

When enabled, the following `details` fields are replaced with `[REDACTED]`:

- `message_content`
- `tool_input`
- `tool_output`
- `prompt`
- `response`

Metadata (timestamps, event types, session IDs, tool names) is always preserved.

## Rotation

### Daily Rotation (Default)

A new log file is created each day:

```
~/.anteroom/audit/audit-2026-02-26.jsonl
~/.anteroom/audit/audit-2026-02-27.jsonl
```

The HMAC chain resets to `"genesis"` at each day boundary.

### Size-Based Rotation

When logs exceed a size threshold, the file is rotated with a timestamp suffix:

```yaml
audit:
  rotation: size
  rotate_size_bytes: 10485760   # 10 MB default, minimum 1 MB
```

Rotated files: `audit-2026-02-26.1709000000000.jsonl`

## Retention

Old log files are automatically purged based on file modification time:

```yaml
audit:
  retention_days: 90   # default; 0 = keep forever
```

Purge can also be triggered manually:

```bash
aroom audit purge
```

## File Security

- **Directory permissions**: `0700` (owner-only) on the audit log directory
- **File permissions**: `0600` (owner read/write only) on each log file
- **File locking**: `fcntl.flock(LOCK_EX)` on Unix prevents concurrent write corruption
- **Write safety**: Each entry is flushed and fsynced immediately for crash resilience
- **Graceful degradation**: `fcntl` is optional; on Windows, writes proceed without locking

## CLI Commands

### Verify Chain Integrity

```bash
aroom audit verify
```

Reads the current day's audit log and verifies every entry's HMAC chain. Reports:

- Total entries verified
- Valid/invalid entry count
- Line numbers of any broken chain links

### Purge Old Logs

```bash
aroom audit purge
```

Deletes audit log files older than `retention_days`. Reports the number of files deleted.

## SIEM Integration

### Splunk

Configure a file monitor input pointing to the audit directory:

```
[monitor:///home/user/.anteroom/audit/]
sourcetype = anteroom:audit
index = security
```

### ELK / OpenSearch

Use Filebeat with a JSONL input:

```yaml
filebeat.inputs:
  - type: log
    paths:
      - /home/user/.anteroom/audit/audit-*.jsonl
    json.keys_under_root: true
    json.add_error_key: true
```

### General Guidance

- Each line is a complete, parseable JSON object (no framing needed)
- Timestamps are ISO 8601 UTC for consistent time zone handling
- Event types use dot notation for hierarchical filtering (e.g., `tool_calls.*`)
- Session and user IDs enable cross-event correlation

## Configuration Reference

### `audit.*`

| Field | Type | Default | Env Var | Description |
|---|---|---|---|---|
| `enabled` | bool | `false` | `AI_CHAT_AUDIT_ENABLED` | Enable audit logging |
| `log_path` | string | `""` | `AI_CHAT_AUDIT_LOG_PATH` | Custom log directory (empty = `data_dir/audit/`) |
| `tamper_protection` | string | `"hmac"` | `AI_CHAT_AUDIT_TAMPER_PROTECTION` | `"hmac"` or `"none"` |
| `rotation` | string | `"daily"` | — | `"daily"` or `"size"` |
| `rotate_size_bytes` | int | `10485760` | — | Size threshold for rotation (min 1 MB) |
| `retention_days` | int | `90` | `AI_CHAT_AUDIT_RETENTION_DAYS` | Days to retain logs (0 = forever) |
| `redact_content` | bool | `true` | `AI_CHAT_AUDIT_REDACT_CONTENT` | Strip message/tool content from entries |
| `events.auth` | bool | `true` | — | Log authentication events |
| `events.tool_calls` | bool | `true` | — | Log tool call events |
