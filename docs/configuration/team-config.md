# Team Configuration

Team configuration allows organizations to define shared settings that apply to all team members. A team config file uses the same YAML schema as personal config, with an optional `enforce` list to lock specific settings so they cannot be overridden.

## Why Team Config?

In organizations, you often need to ensure that every developer:

- Connects to the same API endpoint (e.g., a corporate proxy or self-hosted LLM)
- Uses an approved model
- Cannot disable safety approval gates
- Has access to shared MCP tool servers

Without team config, each developer must manually configure these settings and nothing prevents them from changing values. Team config solves this by providing a shared configuration layer with optional enforcement.

## How It Works

Team config sits between defaults and personal config in the [configuration precedence](index.md):

```
defaults → team config → personal config → env vars → CLI flags
```

The team config acts as a **base layer**. Personal config overlays on top (personal values win for non-enforced fields). Environment variables and CLI flags can further override.

The exception is the `enforce` list: any field listed there is **locked** to the team-specified value, regardless of what personal config, environment variables, or CLI flags say.

## Discovery

Anteroom searches for a team config file using this priority order (first match wins):

### 1. CLI Flag

```bash
aroom --team-config /path/to/team.yaml chat
```

If the file does not exist, Anteroom warns and proceeds without team config.

### 2. Environment Variable

```bash
export AI_CHAT_TEAM_CONFIG=/path/to/team.yaml
aroom chat
```

### 3. Personal Config Field

Add `team_config_path` to your personal `~/.anteroom/config.yaml`:

```yaml
team_config_path: /mnt/shared/anteroom/team.yaml

ai:
  api_key: sk-personal-key
```

### 4. Walk-Up from Current Directory

If none of the above are set, Anteroom walks up from the current working directory, checking each directory level for:

1. `.anteroom/team.yaml` (preferred)
2. `.claude/team.yaml` (Claude Code compatible)
3. `anteroom.team.yaml` (flat file alternative)

The `.anteroom` and `.claude` directories are interchangeable — Anteroom treats them identically. If both exist at the same directory level, `.anteroom/team.yaml` takes precedence.

The walk-up stops at the user's home directory (`$HOME`) to prevent traversal into system directories.

This is useful for monorepos where the team config lives at the repository root:

```
my-monorepo/
├── .anteroom/
│   └── team.yaml          ← Found when working anywhere in the repo
├── service-a/
│   └── src/
└── service-b/
    └── src/               ← Working here? Walk-up finds ../../.anteroom/team.yaml
```

## Trust Model

Team config files are verified before loading to prevent injection attacks from modified files on shared filesystems.

**How trust works:**

1. When a team config is encountered for the first time, Anteroom computes its SHA-256 hash.
2. In **interactive mode** (CLI chat, CLI exec with TTY): the user is prompted to confirm trust.
3. In **non-interactive mode** (web UI, piped input): untrusted configs are **silently skipped** (fail-closed).
4. Trust decisions are stored in `~/.anteroom/trusted_folders.json` with the file path and content hash.
5. If the file changes (hash mismatch), the user is prompted again to re-trust.

```
$ aroom chat
Found team config file: /mnt/shared/anteroom/team.yaml
Trust this file? [y/N] y
```

Once trusted, subsequent runs skip the prompt unless the file content changes.

## Configuration Merging

The merge process uses **deep merge** with these rules:

- **Nested dicts** merge recursively (team and personal keys are combined)
- **Lists** in personal config replace team config lists wholesale (no append)
- **Scalars** in personal config overwrite team config values

### Example

Team config:
```yaml
ai:
  base_url: https://api.company.com/v1
  model: gpt-4

safety:
  approval_mode: ask_for_writes
  denied_tools:
    - bash
```

Personal config:
```yaml
ai:
  api_key: sk-personal
  model: gpt-4o

safety:
  denied_tools: []
```

Merged result (before enforcement):
```yaml
ai:
  base_url: https://api.company.com/v1   # from team (not in personal)
  api_key: sk-personal                    # from personal
  model: gpt-4o                           # personal overrides team

safety:
  approval_mode: ask_for_writes           # from team (not in personal)
  denied_tools: []                        # personal replaces team list
```

## Enforcement

To lock settings so they cannot be overridden, add an `enforce` list to the team config. Each entry is a dot-path to a config field.

```yaml
ai:
  base_url: https://api.company.com/v1
  model: gpt-4

safety:
  approval_mode: ask_for_writes

enforce:
  - ai.base_url
  - ai.model
  - safety.approval_mode
```

### What Enforcement Does

After all merging is complete (team + personal + env vars), Anteroom re-applies the team value for each enforced field. This means:

| Source | Non-enforced field | Enforced field |
|---|---|---|
| Personal config | Overrides team value | **Ignored** |
| Environment variable | Overrides config file | **Ignored** |
| CLI flag (`--approval-mode`) | Overrides env var | **Ignored** (with warning) |
| Web UI PATCH `/api/config` | Applies change | **Rejected** (HTTP 403) |

When a CLI flag targets an enforced field, Anteroom prints a warning:

```
WARNING: --approval-mode ignored; 'safety.approval_mode' is enforced by team config.
```

### Dot-Path Format

Enforce paths use dot notation to reference nested YAML fields:

| Dot-path | YAML field |
|---|---|
| `ai.base_url` | `ai: { base_url: ... }` |
| `ai.model` | `ai: { model: ... }` |
| `safety.approval_mode` | `safety: { approval_mode: ... }` |
| `app.port` | `app: { port: ... }` |

**Validation rules:**

- Only lowercase letters, digits, and underscores (`[a-z0-9_]`)
- Segments separated by dots
- Maximum 4 segments (e.g., `a.b.c.d`)
- Invalid paths are silently ignored with a log warning

### Web UI Enforcement

The web UI config API also respects enforcement:

- `GET /api/config` returns an `enforced_fields` list so the UI can show which settings are locked
- `PATCH /api/config` returns HTTP 403 if you try to change an enforced field (e.g., changing `model` when `ai.model` is enforced)

## Examples

### Lock API Endpoint and Safety Policy

The most common use case: ensure everyone uses the corporate API and cannot disable safety gates.

```yaml
ai:
  base_url: https://api.company.com/v1
  model: gpt-4-turbo

safety:
  approval_mode: ask_for_writes

enforce:
  - ai.base_url
  - ai.model
  - safety.approval_mode
```

Users can still set their own `api_key`, `system_prompt`, and other non-enforced settings.

### Share MCP Servers

Provide team-wide access to shared MCP tool servers:

```yaml
mcp_servers:
  postgres:
    stdio:
      command: node /opt/mcp-servers/postgres.js
      args:
        - --db-host=db.company.com
        - --db-port=5432

  slack:
    stdio:
      command: /opt/mcp-servers/slack.sh

enforce:
  - mcp_servers
```

### Set Defaults Without Enforcing

Team config without an `enforce` list provides sensible defaults that users can override:

```yaml
ai:
  base_url: https://api.company.com/v1
  model: gpt-4

safety:
  approval_mode: ask_for_writes

# No enforce list — all values are overridable
```

### Multi-Team Setup

Different teams can use different configs via environment variables:

```bash
# Team A
export AI_CHAT_TEAM_CONFIG=/etc/anteroom/team-a.yaml
aroom chat

# Team B
export AI_CHAT_TEAM_CONFIG=/etc/anteroom/team-b.yaml
aroom chat
```

### CI/CD Environments

In CI, use the environment variable and note that trust prompting is skipped in non-interactive mode:

```bash
export AI_CHAT_TEAM_CONFIG=/etc/anteroom/ci-config.yaml
# Must pre-trust the file, or the CI config will be silently skipped.
# Trust is stored per-user in ~/.anteroom/trusted_folders.json
aroom exec "Run the test suite"
```

## Recommended File Locations

| Scenario | Location | Discovery Method |
|---|---|---|
| Git monorepo | `.anteroom/team.yaml` in repo root | Walk-up (automatic) |
| Shared filesystem (NFS) | `/mnt/team-config/anteroom.yaml` | Env var or personal config field |
| System directory (Linux) | `/etc/anteroom/team.yaml` | Env var |
| Per-team on shared host | `/etc/anteroom/team-{name}.yaml` | Env var per team |

## Troubleshooting

### Team config is not loading

1. **Check discovery**: Run with `--debug` to see team config discovery logs:
   ```bash
   aroom --debug chat
   ```
   Look for lines like `Team config path from --team-config does not exist` or `Skipping untrusted team config`.

2. **Check trust**: If the file exists but is not trusted, you'll see `Skipping untrusted team config (non-interactive)` in debug output. Trust the file interactively first:
   ```bash
   aroom chat  # Will prompt to trust
   ```

3. **Check walk-up**: Walk-up stops at `$HOME`. If your team config is above your home directory, use an explicit path instead.

### Enforced field is not working

1. **Check the dot-path**: Paths must be lowercase with max 4 segments. `AI.base_url` (uppercase) is invalid. Run with `--debug` to see `Ignoring invalid enforce dot-path` warnings.

2. **Check the field exists in team config**: If you enforce `ai.model` but don't set `ai.model` in the team config, the enforcement is skipped with a warning.

3. **Check the web UI**: The `GET /api/config` endpoint returns `enforced_fields` --- verify the field appears there.
