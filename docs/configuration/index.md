# Configuration

Anteroom is configured through layered sources: YAML config files, environment variables, CLI flags, and optional team config with enforcement.

## How Configuration Works

When Anteroom starts, it builds its configuration by merging multiple sources. Each layer can override the previous one, except for team-enforced fields which lock settings regardless of other sources.

```
┌─────────────────────────────────────────────────────┐
│  Enforced team config fields (cannot be overridden) │  ← Highest
├─────────────────────────────────────────────────────┤
│  CLI flags (--port, --approval-mode, etc.)          │
├─────────────────────────────────────────────────────┤
│  Environment variables (AI_CHAT_*)                  │
├─────────────────────────────────────────────────────┤
│  Personal config file (~/.anteroom/config.yaml)     │
├─────────────────────────────────────────────────────┤
│  Team config file (.anteroom/team.yaml)             │
├─────────────────────────────────────────────────────┤
│  Built-in defaults                                  │  ← Lowest
└─────────────────────────────────────────────────────┘
```

### Processing Order

Here is exactly what happens when you run `aroom` or `aroom chat`:

1. **Load personal config** --- Read `~/.anteroom/config.yaml` (or `~/.parlor/config.yaml` for backward compatibility) into a raw YAML dict.

2. **Discover team config** --- Search for a team config file using this priority:
    1. `--team-config /path` CLI flag
    2. `AI_CHAT_TEAM_CONFIG` environment variable
    3. `team_config_path` field in personal config
    4. Walk up from cwd looking for `.anteroom/team.yaml`, `.claude/team.yaml`, or `anteroom.team.yaml`

3. **Trust-verify team config** --- If a team config is found, verify its SHA-256 hash against the trust store (`~/.anteroom/trusted_folders.json`). In interactive mode (CLI), prompt the user to trust new or changed files. In non-interactive mode (web UI), silently skip untrusted files.

4. **Merge configs** --- Deep-merge the team config (base) with personal config (overlay). Nested dicts merge recursively; lists and scalars in personal config replace team config values.

5. **Apply enforcement** --- For each dot-path in the team config's `enforce` list, re-apply the team value, overriding whatever the personal config set.

6. **Apply environment variables** --- `AI_CHAT_*` environment variables override the merged result. For example, `AI_CHAT_MODEL=gpt-4o` overrides the `ai.model` field.

7. **Build config object** --- Convert the raw dict into typed dataclass objects (`AIConfig`, `AppSettings`, `SafetyConfig`, etc.) with validation and clamping.

8. **Apply CLI flag overrides** --- Flags like `--port`, `--approval-mode`, `--allowed-tools` are applied last. If a flag targets an enforced field, the override is rejected with a warning.

9. **Return** --- The final `AppConfig` object and the list of `enforced_fields` are returned. Both the web UI and CLI use this same config object.

## Quick Reference

| Setting | Config Key | Env Var | Default |
|---|---|---|---|
| API endpoint | `ai.base_url` | `AI_CHAT_BASE_URL` | --- (required) |
| API key | `ai.api_key` | `AI_CHAT_API_KEY` | --- (required) |
| Model | `ai.model` | `AI_CHAT_MODEL` | `gpt-4` |
| System prompt | `ai.system_prompt` | `AI_CHAT_SYSTEM_PROMPT` | `You are a helpful assistant.` |
| SSL verification | `ai.verify_ssl` | `AI_CHAT_VERIFY_SSL` | `true` |
| Request timeout | `ai.request_timeout` | `AI_CHAT_REQUEST_TIMEOUT` | `120` |
| Host | `app.host` | --- | `127.0.0.1` |
| Port | `app.port` | `AI_CHAT_PORT` | `8080` |
| Data directory | `app.data_dir` | --- | `~/.anteroom` |
| TLS | `app.tls` | --- | `false` |
| Built-in tools | `cli.builtin_tools` | --- | `true` |
| Max tool iterations | `cli.max_tool_iterations` | --- | `50` |
| Context warn threshold | `cli.context_warn_tokens` | --- | `80000` |
| Context auto-compact threshold | `cli.context_auto_compact_tokens` | --- | `100000` |
| Approval mode | `safety.approval_mode` | `AI_CHAT_SAFETY_APPROVAL_MODE` | `ask_for_writes` |
| Team config path | --- | `AI_CHAT_TEAM_CONFIG` | --- |
| Log level | --- | `AI_CHAT_LOG_LEVEL` | `WARNING` |

## Pages

- [Config File](config-file.md) --- full `config.yaml` YAML schema reference
- [Environment Variables](environment-variables.md) --- all `AI_CHAT_*` env vars and precedence rules
- [Team Configuration](team-config.md) --- shared team config with enforced settings
- [MCP Servers](mcp-servers.md) --- MCP server setup (stdio + SSE)
- [TLS](tls.md) --- HTTPS with self-signed certificates

## Directory Equivalence

Throughout the configuration system, `.anteroom` and `.claude` directories are interchangeable. This applies to team config discovery (`.anteroom/team.yaml` vs `.claude/team.yaml`), skills, rules, and instruction files. See [Concepts](../getting-started/concepts.md#directory-equivalence) for the full mapping.

## Related

- [Project Instructions](../cli/project-instructions.md) --- how `ANTEROOM.md` / `CLAUDE.md` files inject context into conversations
- [Skills](../cli/skills.md) --- reusable prompt templates (`/commit`, `/review`, custom skills)
- [Concepts](../getting-started/concepts.md) --- architecture overview and how the config feeds into the agent loop
