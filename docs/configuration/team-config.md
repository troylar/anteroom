# Team Configuration

Team configuration allows organizations to define shared settings that apply to all users on a team. A team config file uses the same YAML schema as personal config files, with an optional `enforce` list to lock specific settings.

## Overview

Team config solves the problem of enforcing organizational policies (API endpoints, approval modes, allowed tools) across multiple users without requiring manual configuration on each machine.

## Discovery

Anteroom looks for a team config file using this priority order:

1. **CLI flag**: `aroom --team-config /path/to/team.yaml`
2. **Environment variable**: `AI_CHAT_TEAM_CONFIG=/path/to/team.yaml`
3. **Personal config field**: `team_config_path: /path/to/team.yaml` in `~/.anteroom/config.yaml`
4. **Walk-up from cwd**: Looks for `.anteroom/team.yaml` or `anteroom.team.yaml` walking up from the current directory to the filesystem root

If a team config is found, it is used as the base configuration. Personal config overlays on top, then CLI flags override both.

## Configuration Merging

The configuration precedence is:

1. **Defaults** (lowest)
2. **Team config** (if present)
3. **Personal config** (`~/.anteroom/config.yaml`)
4. **Environment variables**
5. **CLI flags** (highest)

**Exception**: Fields listed in the `enforce` section bypass all other sources and cannot be overridden.

## Enforcement

To lock a setting so users cannot override it, add an `enforce` list to the team config:

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

Enforced fields:
- Override personal config
- Override environment variables
- Override CLI flags
- Use dot-notation to reference nested fields (e.g., `ai.base_url`, `safety.approval_mode`)

## Example Team Config

```yaml
# API endpoint (shared across team)
ai:
  base_url: https://api.company.com/v1
  model: gpt-4-turbo
  system_prompt: You are a helpful assistant. Follow company security policies.
  timeout: 120

# Safety policy (all users must ask for writes)
safety:
  approval_mode: ask_for_writes
  allowed_tools:
    - read_file
    - write_file
    - bash
    - glob_files
    - grep

# MCP servers available to the team
mcp_servers:
  company_tools:
    stdio:
      command: /usr/local/bin/company-tools-server
    tools_include: ["*"]

# Enforce these fields so users can't override
enforce:
  - ai.base_url
  - ai.model
  - safety.approval_mode
```

## Trust Model

When a team config is first encountered (or modified), Anteroom prompts the user to trust it. This prevents injection attacks from modified team config files on shared filesystems.

- In **interactive mode** (CLI): user is prompted to confirm trust
- In **non-interactive mode** (web UI): untrusted configs are silently skipped
- Trust decisions are stored in `~/.anteroom/trusted_folders.json` with SHA-256 hashes

Once trusted, subsequent runs skip the prompt unless the file hash changes.

## Typical Workflows

### Enforce API Endpoint + Safety Policy

```yaml
ai:
  base_url: https://api.openai.com/v1
  model: gpt-4

safety:
  approval_mode: ask_for_writes

enforce:
  - ai.base_url
  - ai.model
  - safety.approval_mode
```

### Share MCP Servers

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

### Multi-Team Setup

Teams can place team configs in shared directories and reference them via environment variables:

```bash
# Team A
export AI_CHAT_TEAM_CONFIG=/etc/anteroom/team-a.yaml
aroom chat

# Team B
export AI_CHAT_TEAM_CONFIG=/etc/anteroom/team-b.yaml
aroom chat
```

## Recommended File Locations

- **Shared filesystem** (NFS, network drive): `/mnt/team-config/anteroom.yaml`
- **Git repository** (for monorepos): `.anteroom/team.yaml` in repo root
- **System directory** (Linux): `/etc/anteroom/team.yaml`
- **User home** (single-user fallback): `~/.anteroom/team.yaml`
