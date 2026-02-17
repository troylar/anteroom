# Tool Safety

Two layers of protection prevent accidental damage from AI tool use.

## Destructive Command Confirmation

The following patterns in bash commands trigger an interactive `Proceed? [y/N]` prompt before execution:

- `rm`, `rmdir`
- `git push --force`, `git push -f`
- `git reset --hard`
- `git clean`
- `git checkout .`
- `drop table`, `drop database`
- `truncate`
- `> /dev/`
- `chmod 777`
- `kill -9`

## Path and Command Blocking

Hardcoded blocks that cannot be bypassed:

### Blocked Paths

- `/etc/shadow`
- `/etc/passwd`
- `/etc/sudoers`
- Anything under `/proc/`, `/sys/`, `/dev/` (follows symlinks)

### Blocked Commands

- `rm -rf /`
- `mkfs`
- `dd if=/dev/zero`
- Fork bombs

### Additional Protections

- **Null byte injection**: Rejected in all paths, commands, and glob patterns
- **Path traversal**: Blocked in all file operations
- **Symlink resolution**: `os.path.realpath` is used to resolve symlinks before path checks

## Write Path Safety

`check_write_path()` in `tools/safety.py` inspects the destination path for `write_file` calls and returns a `SafetyVerdict` before any bytes are written. Paths that trigger confirmation include:

- `.env` files and directories
- `.ssh/` and `.gnupg/` directories
- System paths under `/etc/`, `/proc/`, `/sys/`, and `/dev/`
- Any path added to `safety.sensitive_paths` in config

Like `check_bash_command()`, this function is pure — no I/O, no side effects.

## Web UI Approval Flow

When a destructive operation is detected in the Web UI, the agent loop pauses and emits an `approval_required` SSE event containing a unique `approval_id`. The browser renders an inline approve/deny prompt inside the tool call panel.

The user responds by clicking Approve or Deny, which sends:

```
POST /api/approvals/{approval_id}/respond
Content-Type: application/json

{"approved": true}
```

The approval ID is regex-validated on receipt. The handler uses an atomic `dict.pop()` on the in-memory `pending_approvals` store (capped at 100 entries) to prevent TOCTOU races — a second response to the same ID is silently ignored.

The waiting agent loop side uses an `asyncio.Event` with a configurable timeout (default 120 s). If the timeout expires with no response, the operation is blocked (fails closed). If no approval channel exists — for example, when running headless — the operation is also blocked.

## Configuration

Safety gate behavior is controlled by the `safety` section in `config.yaml`. See [Config File](../configuration/config-file.md#safety) for the full field reference.

Quick example — disable safety entirely (not recommended):

```yaml
safety:
  enabled: false
```

Add a custom bash pattern and a sensitive path:

```yaml
safety:
  custom_patterns:
    - "heroku.*--force"
  sensitive_paths:
    - "~/.config/gh"
```

## MCP Tool Safety

MCP tool arguments are also protected:

- **SSRF protection**: DNS resolution validates that target URLs don't point to private IP addresses
- **Shell metacharacter rejection**: Tool arguments are sanitized to prevent command injection
