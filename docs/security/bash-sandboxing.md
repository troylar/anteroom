# Bash Sandboxing

The `bash` tool executes shell commands on behalf of the AI agent. Anteroom provides layered sandboxing controls to constrain what commands can do, where they can write, and how long they can run.

## Enable / Disable

The bash tool can be disabled entirely:

```yaml
safety:
  bash:
    enabled: false     # removes bash from the tool list
```

Or denied via the tool blocklist (keeps the tool definition but blocks execution):

```yaml
safety:
  denied_tools:
    - bash
```

## Execution Limits

### Timeout

Every bash invocation has a wall-clock timeout. If the command exceeds it, the process is killed.

```yaml
safety:
  bash:
    timeout: 120       # seconds (default), clamped to 1–600
```

### Output Truncation

Long command output is truncated to prevent context window exhaustion:

```yaml
safety:
  bash:
    max_output_chars: 100000   # default, minimum 1000
```

## Path Controls

### Blocked Paths

Commands referencing these paths are rejected before execution:

```yaml
safety:
  bash:
    blocked_paths:
      - /etc/production
      - /var/secrets
```

Path matching normalizes forward/backslash and is case-insensitive. Both the command text and the resolved path are checked.

### Allowed Paths

When set, commands referencing paths *outside* the allowed list are rejected:

```yaml
safety:
  bash:
    allowed_paths:
      - /home/user/project
      - /tmp
```

### Hardcoded Blocked Paths

These paths are always blocked by `validate_path()` in `tools/security.py`, regardless of configuration:

| Path | Type |
|---|---|
| `/etc/shadow` | Exact |
| `/etc/passwd` | Exact |
| `/etc/sudoers` | Exact |
| `/proc/*` | Prefix |
| `/sys/*` | Prefix |
| `/dev/*` | Prefix |

Symlinks are resolved before checking, preventing bypass via symlink indirection.

## Command Controls

### Blocked Commands

Custom command patterns (regex or literal) that should never execute:

```yaml
safety:
  bash:
    blocked_commands:
      - "heroku.*--force"
      - "terraform destroy"
```

### Hard-Block Patterns

These catastrophic commands are blocked unconditionally by `check_hard_block()` in `tools/security.py`. They cannot be overridden by any configuration, approval mode, or allowed_tools setting:

| Pattern | Description |
|---|---|
| `rm -rf` / `rm -fr` | Recursive forced deletion |
| `mkfs` | Disk formatting |
| `dd if=/dev/zero` / `dd if=/dev/urandom` | Disk overwrite |
| Fork bomb syntax `:(){ ...\|...& }; :` | Fork bomb |
| `fork bomb` (literal keyword) | Fork bomb keyword |
| `chmod -R 777 /` | Recursive chmod 777 on root |
| `curl\|sh`, `wget\|bash` | Pipe from network to shell |
| `curl\|sudo`, `wget\|sudo` | Pipe from network to sudo |
| `base64\|sh`, `base64\|bash` | Base64 decode piped to shell |
| `base64\|sudo` | Base64 decode piped to sudo |
| `python/perl/ruby -c ...os.system/popen/exec` | Scripted shell escape |
| `python/perl/ruby -c ...subprocess/__import__` | Scripted shell escape |
| `shred`, `srm` | Secure file erasure |
| `wipe -` | Secure file erasure (wipe) |
| `truncate -s 0` / `truncate --size=0` | File zeroing |
| `sudo rm` | sudo rm |

In interactive mode (CLI or web UI), the user sees an escalated warning and can choose to proceed. In auto mode with no approval channel, hard-blocked commands are silently blocked as a safety net.

### Destructive Patterns (Approval-Gated)

These patterns are detected by `check_bash_command()` in `tools/safety.py` and trigger approval prompts (except in `auto` mode):

| Pattern | What It Catches |
|---|---|
| `rm` | File deletion |
| `rmdir` | Directory deletion |
| `git push --force` / `-f` | Force push |
| `git reset --hard` | Hard reset |
| `git clean` | Working tree clean |
| `git checkout .` | Discard changes |
| `drop table` / `drop database` | SQL destruction |
| `truncate` | SQL truncation |
| `> /dev/` | Device redirection |
| `chmod 777` | Insecure permissions |
| `kill -9` | Process killing |

Custom patterns can be added via `safety.custom_patterns`:

```yaml
safety:
  custom_patterns:
    - "heroku.*--force"
    - "kubectl delete"
```

## Network Detection

When `allow_network` is `false`, commands using network tools are blocked:

```yaml
safety:
  bash:
    allow_network: false   # default: true
```

Detected network tools:

| Category | Tools |
|---|---|
| **Unix network** | `curl`, `wget`, `nc`, `ncat`, `socat`, `nmap` |
| **Remote connections** | `ssh`, `scp`, `rsync`, `sftp`, `ftp`, `telnet` |
| **PowerShell** | `Invoke-WebRequest`, `Invoke-RestMethod`, `iwr`, `irm`, `Start-BitsTransfer` |
| **.NET** | `Net.WebClient` |
| **DNS** | `nslookup`, `dig` |

## Package Install Detection

When `allow_package_install` is `false`, package installation commands are blocked:

```yaml
safety:
  bash:
    allow_package_install: false   # default: true
```

Detected package managers:

| Category | Tools |
|---|---|
| **Python** | `pip install`, `pip3 install`, `conda install` |
| **Node.js** | `npm install`, `yarn install/add`, `pnpm install/add` |
| **Ruby** | `gem install` |
| **Rust** | `cargo install` |
| **Go** | `go install` |
| **System** | `apt install`, `yum install`, `dnf install`, `pacman install`, `zypper install` |
| **macOS** | `brew install` |
| **Windows** | `choco install`, `winget install`, `scoop install` |

## Command Audit Logging

Enable logging of all bash commands to the structured audit log:

```yaml
safety:
  bash:
    log_all_commands: true   # default: false
```

When enabled, every bash invocation is recorded as an audit event with the command text, exit code, and truncated output. Requires [audit logging](audit-log.md) to be enabled.

## OS-Level Sandbox (Win32 Job Objects)

On Windows, Anteroom can assign bash subprocesses to a Win32 Job Object for kernel-level resource limits:

```yaml
safety:
  bash:
    sandbox:
      enabled: true            # auto-detected on Windows; null = auto
      max_memory_mb: 512       # default, minimum 64
      max_processes: 10        # default, range 1–1000
      cpu_time_limit: null     # CPU seconds, null = no limit
```

The sandbox:

- Limits peak memory consumption per job
- Caps the number of child processes
- Optionally enforces CPU time budgets
- No-op on non-Windows platforms (Linux/macOS)
- Uses ctypes for zero-dependency Win32 API access

## Configuration Reference

### `safety.bash.*`

| Field | Type | Default | Env Var | Description |
|---|---|---|---|---|
| `enabled` | bool | `true` | — | Enable/disable bash tool entirely |
| `timeout` | int | `120` | `AI_CHAT_BASH_TIMEOUT` | Per-command timeout in seconds (1–600) |
| `max_output_chars` | int | `100000` | `AI_CHAT_BASH_MAX_OUTPUT` | Max output characters (min 1000) |
| `blocked_paths` | list[str] | `[]` | `AI_CHAT_BASH_BLOCKED_PATHS` | Paths to reject (comma-separated for env var) |
| `allowed_paths` | list[str] | `[]` | `AI_CHAT_BASH_ALLOWED_PATHS` | Paths to allow (empty = allow all) |
| `blocked_commands` | list[str] | `[]` | `AI_CHAT_BASH_BLOCKED_COMMANDS` | Command patterns to reject |
| `allow_network` | bool | `true` | `AI_CHAT_BASH_ALLOW_NETWORK` | Allow network tool usage |
| `allow_package_install` | bool | `true` | `AI_CHAT_BASH_ALLOW_PACKAGE_INSTALL` | Allow package installation |
| `log_all_commands` | bool | `false` | `AI_CHAT_BASH_LOG_ALL_COMMANDS` | Log all commands to audit log |

### `safety.bash.sandbox.*`

| Field | Type | Default | Env Var | Description |
|---|---|---|---|---|
| `enabled` | bool\|null | `null` | `AI_CHAT_BASH_SANDBOX_ENABLED` | Enable OS sandbox (null = auto-detect) |
| `max_memory_mb` | int | `512` | `AI_CHAT_BASH_SANDBOX_MAX_MEMORY_MB` | Max memory per job (min 64 MB) |
| `max_processes` | int | `10` | `AI_CHAT_BASH_SANDBOX_MAX_PROCESSES` | Max child processes (1–1000) |
| `cpu_time_limit` | int\|null | `null` | `AI_CHAT_BASH_SANDBOX_CPU_TIME_LIMIT` | CPU seconds limit (null = none) |

## Examples

### Locked-Down Enterprise

```yaml
safety:
  approval_mode: ask
  bash:
    enabled: true
    timeout: 30
    max_output_chars: 10000
    allow_network: false
    allow_package_install: false
    log_all_commands: true
    blocked_paths:
      - /etc
      - /var
      - /opt
    blocked_commands:
      - "docker"
      - "kubectl"
    sandbox:
      enabled: true
      max_memory_mb: 256
      max_processes: 5
      cpu_time_limit: 30
```

### CI/CD Pipeline

```yaml
safety:
  approval_mode: auto
  bash:
    enabled: true
    timeout: 300
    max_output_chars: 50000
    allow_network: true
    allow_package_install: false
    log_all_commands: true
    allowed_paths:
      - /workspace
      - /tmp
```
