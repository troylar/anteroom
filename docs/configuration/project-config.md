# Project Configuration

Project configuration allows per-project settings that activate automatically when you work in a project directory. A project config uses the same YAML schema as personal and team configs, with support for required keys and shared references.

## Why Project Config?

Different projects have different needs:

- **Project A** uses GPT-4o with a specific MCP database server
- **Project B** uses a local Ollama model with code analysis tools
- **Project C** requires team-specific API keys and safety rules

Without project config, you'd need to manually switch settings or use environment variables each time you change projects. Project config handles this automatically.

## How It Works

Project config sits between personal config and environment variables in the [configuration precedence](index.md):

```
defaults < team config < personal config < project config < env vars < CLI flags
```

When you run `aroom chat` from a project directory, Anteroom walks up from your current working directory looking for a project config file. If found and trusted, it overlays your personal config.

**Team enforcement still applies.** If the team config enforces a field (e.g., `ai.base_url`), no project config can override it.

## Config File Location

Place a `config.yaml` inside a `.anteroom`, `.claude`, or `.parlor` directory at your project root:

```
my-project/
├── .anteroom/
│   └── config.yaml     ← Project config (preferred)
├── src/
│   └── main.py
└── README.md
```

### Discovery

Anteroom searches for project config by walking up from the current working directory:

1. Check current directory for `.anteroom/config.yaml`
2. If not found, check for `.claude/config.yaml`
3. If not found, check for `.parlor/config.yaml`
4. If not found at this level, move to the parent directory and repeat
5. Stop at the user's home directory (`$HOME`)

The first match wins. If both `.anteroom/config.yaml` and `.claude/config.yaml` exist at the same level, `.anteroom` takes precedence.

```
~/projects/my-app/
├── .anteroom/
│   └── config.yaml          ← Found when working anywhere below
├── packages/
│   ├── frontend/
│   │   └── src/              ← Working here? Walk-up finds ../../.anteroom/config.yaml
│   └── backend/
│       └── src/              ← Working here? Same config applies
```

### Explicit Path

You can also pass a project config path explicitly in `load_config()`:

```python
config, enforced = load_config(project_config_path=Path("/path/to/project/.anteroom/config.yaml"))
```

## Trust Verification

Project config files must be trusted before they take effect. This prevents a malicious repository from silently injecting configuration (e.g., changing your API endpoint to an attacker-controlled server).

**How trust works:**

1. When a project config is found, Anteroom computes its SHA-256 content hash.
2. The hash is checked against the trust store (`~/.anteroom/trusted_folders.json`).
3. If the file is **untrusted** or the hash has **changed**, the config is **silently skipped** (fail-closed).
4. To trust a project config, use `aroom init` or manually trust via the CLI when prompted for team configs.

Once trusted, the config loads automatically on subsequent runs until the file content changes.

## Configuration Merging

Project config merges on top of your personal config using **deep merge**:

- **Nested dicts** merge recursively (project keys add to or override personal keys)
- **Lists** in project config replace personal config lists wholesale
- **Scalars** in project config override personal config values

### Example

Personal config (`~/.anteroom/config.yaml`):
```yaml
ai:
  base_url: https://api.openai.com/v1
  api_key: sk-personal-key
  model: gpt-4o

mcp_servers:
  - name: filesystem
    transport: stdio
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem"]
```

Project config (`.anteroom/config.yaml`):
```yaml
ai:
  model: llama3

mcp_servers:
  - name: project-db
    transport: stdio
    command: python
    args: ["-m", "mcp_postgres", "--db", "project.db"]
```

Merged result:
```yaml
ai:
  base_url: https://api.openai.com/v1   # from personal (not in project)
  api_key: sk-personal-key               # from personal (not in project)
  model: llama3                           # project overrides personal

mcp_servers:                              # project list REPLACES personal list
  - name: project-db
    transport: stdio
    command: python
    args: ["-m", "mcp_postgres", "--db", "project.db"]
```

Note that `mcp_servers` is a list, so the project config **replaces** the personal list entirely. If you want both personal and project MCP servers, list them all in the project config.

## Required Keys

Project configs can declare values that must exist in the developer's personal config before the project config takes effect. This is useful for project-specific API keys or credentials.

```yaml
# .anteroom/config.yaml (project config)
ai:
  model: llama3

required:
  - path: ai.api_key
    description: "Your API key for the project's AI endpoint"
  - path: custom.db_password
    description: "Database password for the project DB"
```

### How Required Keys Work

1. After loading the project config, Anteroom checks each `required` entry against the personal config.
2. Each entry needs a `path` (dot-separated config path) and an optional `description`.
3. Missing keys are also checked against environment variables (`AI_CHAT_` prefix, e.g., `AI_CHAT_AI_API_KEY`).
4. If keys are missing in **interactive mode** (terminal), the user is prompted to enter values.
5. Sensitive fields (containing `key`, `secret`, `password`, `token`, or `passphrase`) use masked input via `getpass`.
6. Entered values are saved to the personal config file with restrictive permissions (0600).
7. In **non-interactive mode**, missing required keys produce an error message listing the missing paths and their env var equivalents.

### Prompt Flow

```
$ aroom chat
--- Required Configuration ---
The following config values are required but not set:

  ai.api_key — Your API key for the project's AI endpoint
  Enter value (hidden): ****

  custom.db_password — Database password for the project DB
  Enter value (hidden): ****

  Updated ~/.anteroom/config.yaml with 2 value(s).
```

## Shared References

Project configs can reference external instruction, rule, and skill files that should be loaded for this project:

```yaml
# .anteroom/config.yaml (project config)
references:
  instructions:
    - project-instructions.md
    - coding-standards.md
  rules:
    - rules/no-eval.md
    - rules/test-requirements.md
  skills:
    - skills/deploy.md
    - skills/review.md
```

Paths are relative to the config file that declares them. This allows projects to maintain their own instructions, rules, and skills that are loaded automatically when working in the project.

## Interaction with Team Config

The full precedence chain with all layers:

```
┌─────────────────────────────────────────────────────┐
│  Enforced team config fields (cannot be overridden) │  ← Highest
├─────────────────────────────────────────────────────┤
│  CLI flags (--port, --approval-mode, etc.)          │
├─────────────────────────────────────────────────────┤
│  Environment variables (AI_CHAT_*)                  │
├─────────────────────────────────────────────────────┤
│  Project config (.anteroom/config.yaml)             │  ← NEW
├─────────────────────────────────────────────────────┤
│  Personal config file (~/.anteroom/config.yaml)     │
├─────────────────────────────────────────────────────┤
│  Team config file (.anteroom/team.yaml)             │
├─────────────────────────────────────────────────────┤
│  Built-in defaults                                  │  ← Lowest
└─────────────────────────────────────────────────────┘
```

Key rules:

- Project config **can** override personal config values (e.g., change the model per project)
- Project config **cannot** override team-enforced fields (enforcement is re-applied after project merge)
- Project config **can** add MCP servers, references, and other settings
- Required keys in project config prompt the user to fill in personal config values

### Example: Team Enforces Endpoint, Project Changes Model

Team config:
```yaml
ai:
  base_url: https://api.company.com/v1
enforce:
  - ai.base_url
```

Project config:
```yaml
ai:
  base_url: https://attacker.com/v1  # This will be IGNORED (enforced by team)
  model: llama3                       # This WILL apply
```

Result: `ai.base_url` stays as the team value, `ai.model` becomes `llama3`.

## Config Validation

All config files (personal, team, and project) are validated before parsing. The validator checks:

- **Unknown keys** — warns about unrecognized config keys (typos, old fields)
- **Type mismatches** — warns when values have the wrong type (string where int expected)
- **Range violations** — warns when numeric values are outside valid bounds
- **MCP server structure** — errors for missing required fields (`name`, `command`/`url`)
- **Structural problems** — errors for non-dict root, wrong section types

Warnings are non-blocking (the parser handles fallbacks). Errors prevent the config from loading.

## Live Reload

Config files are monitored for changes via mtime polling. When you save a config file:

1. Anteroom detects the mtime change
2. The new content is parsed and validated
3. **Valid changes** are applied without restarting
4. **Invalid changes** are rejected — the previous valid config remains active
5. Warning-level issues are logged but the change is accepted

This means you can edit project configs while Anteroom is running, and changes take effect within a few seconds.

## Examples

### Per-Project Model Override

```yaml
# .anteroom/config.yaml
ai:
  model: claude-3-sonnet
```

### Project with Custom MCP Servers

```yaml
# .anteroom/config.yaml
mcp_servers:
  - name: project-postgres
    transport: stdio
    command: python
    args: ["-m", "mcp_postgres", "--db", "postgresql://localhost/myproject"]

  - name: project-docs
    transport: stdio
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem", "--root", "./docs"]
```

### Project with Required Credentials

```yaml
# .anteroom/config.yaml
ai:
  model: gpt-4o

required:
  - path: ai.api_key
    description: "OpenAI API key for this project"
  - path: custom.slack_token
    description: "Slack bot token for the deploy skill"
```

### Project with Shared Instructions and Rules

```yaml
# .anteroom/config.yaml
references:
  instructions:
    - CONTRIBUTING.md
    - docs/architecture.md
  rules:
    - .anteroom/rules/no-force-push.md
    - .anteroom/rules/test-coverage.md
  skills:
    - .anteroom/skills/deploy.md
```

### Full Project Config

```yaml
# .anteroom/config.yaml
ai:
  model: llama3

safety:
  approval_mode: ask_for_writes
  denied_tools:
    - bash  # Disable bash in this project

mcp_servers:
  - name: project-db
    transport: stdio
    command: python
    args: ["-m", "mcp_postgres", "--db", "project.db"]

required:
  - path: ai.api_key
    description: "API key for the project endpoint"

references:
  instructions:
    - project-instructions.md
  rules:
    - rules/security-policy.md
```

## Troubleshooting

### Project config is not loading

1. **Check discovery**: Ensure the config file is at `.anteroom/config.yaml`, `.claude/config.yaml`, or `.parlor/config.yaml` in or above your current directory.

2. **Check trust**: Project configs must be trusted. If the file exists but isn't loading, it may not be trusted yet. Check debug logs for `Skipping untrusted` messages.

3. **Check validation**: If the YAML is invalid or has structural errors, the config will be silently skipped. Run with `--debug` to see validation error messages.

4. **Check working directory**: Project config discovery only runs when `working_dir` is explicitly set. In the CLI, this is automatic (uses cwd). In tests, you need to pass `working_dir` to `load_config()`.

### Required keys keep prompting

1. **Check the path**: Ensure the `path` in the required key matches the actual config structure. `ai.api_key` looks for `ai: { api_key: ... }`.

2. **Check env vars**: Required keys also check environment variables with the `AI_CHAT_` prefix. `ai.api_key` checks for `AI_CHAT_AI_API_KEY`.

3. **Check file permissions**: The personal config file should be writable so prompted values can be saved.

### Project config overrides being ignored

Check if the field is team-enforced:

```yaml
# Team config
enforce:
  - ai.model  # Project config can't change this
```

Team-enforced fields are re-applied after project config merging, so project values for those fields are effectively ignored.
