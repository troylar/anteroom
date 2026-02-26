# Output Content Filtering

Anteroom includes configurable output content filtering to detect and prevent system prompt leaks and forbidden content in LLM responses. This mitigates OWASP LLM07 (System Prompt Leaking) attacks.

## Overview

Output filtering scans LLM responses for:

1. **System prompt leaks** — Detects when the LLM accidentally includes fragments of its system prompt in responses via n-gram similarity analysis
2. **Forbidden content patterns** — Custom regex patterns for domain-specific forbidden outputs (e.g., unsafe code, credentials, etc.)

The filter applies configurable actions: allow with logging (`warn`), replace matches (`redact`), or reject entirely (`block`).

## Configuration

Enable output filtering in your config file or via environment variables:

```yaml
output_filter:
  enabled: true
  system_prompt_leak_detection: true   # Enable leak detection (default: true)
  leak_threshold: 0.4                  # N-gram similarity threshold (0.0–1.0)
  action: "warn"                       # "warn", "redact", or "block"
  redaction_string: "[FILTERED]"       # Replacement string for redact mode
  log_detections: true                 # Log to security logger (default: true)
  custom_patterns: []                  # Add forbidden patterns
```

## System Prompt Leak Detection

The filter builds n-grams (8-word sequences) from your system prompt and compares them against the LLM output. If enough of the output text matches the system prompt n-grams (above `leak_threshold`), it's flagged as a potential leak.

### How It Works

1. System prompt is tokenized into lowercase words
2. N-grams are extracted (sliding window of 8 words)
3. LLM output is tokenized the same way
4. Output n-grams are compared against system prompt n-grams
5. If match percentage exceeds `leak_threshold`, the output is flagged

### Threshold Tuning

- **`leak_threshold: 0.2`** — Aggressive; catches even small prompt fragments but may have false positives
- **`leak_threshold: 0.4`** — Default; balances detection with false positive avoidance
- **`leak_threshold: 0.8`** — Permissive; only flags substantial prompt leaks

Thresholds only apply if the system prompt is at least 15 words long (to avoid false positives on short prompts).

## Forbidden Content Patterns

Add custom patterns to block or warn on specific outputs:

```yaml
output_filter:
  enabled: true
  action: "block"                    # Block any matches
  custom_patterns:
    - name: "eval_usage"
      pattern: '\beval\s*\('         # Catch eval() calls
      description: "Unsafe eval() usage"
    - name: "sql_injection"
      pattern: "(?i)(drop|delete|truncate)\\s+(table|database)"
      description: "Destructive SQL commands"
    - name: "hardcoded_secret"
      pattern: "(?i)(password|secret|api_key)\\s*=\\s*['\"]([^'\"]+)['\"]"
      description: "Hardcoded credentials"
```

## Actions

### Warn (default)

Matches are allowed through but logged as security events:

```
Output: "To solve this, use eval(user_input) in Python"
Action: Output passes through, match logged as warning
```

Useful for monitoring without disrupting conversations.

### Redact

Matches are replaced with `redaction_string`:

```
Output:  "To solve this, use eval(user_input) in Python"
Redacted: "To solve this, use [FILTERED](user_input) in Python"
```

The redaction string defaults to `[FILTERED]` and can be customized.

### Block

The LLM response is rejected entirely if any matches are found:

```
Output: "To solve this, use eval(user_input)"
Result: Error response; output discarded
Log:    "Output filter blocked response: 1 eval_usage pattern detected"
```

Use this in high-security environments where forbidden content is unacceptable.

## Behavior

- **Final-text scanning**: The filter scans the fully assembled response text after streaming completes. This ensures n-gram leak detection has sufficient context. If `action: block`, the response is discarded before display.
- **Per-request**: Filter is instantiated per-request with the current system prompt context for leak detection.
- **Logging**: All detections are logged to the security logger (`anteroom.security`) with match details.
- **Performance**: N-gram matching and regex scanning have minimal overhead.

## Events

The agent loop emits two output filter–related events:

- **`output_filter_blocked`**: Fired when `action: block` and matches are found. Blocks response from being returned to the user.
- **`output_filter_warning`**: Fired when `action: warn` and matches are found. Response is allowed.

Both events include:
- `direction`: Always `"output"` (filtering only applies to responses)
- `matches`: List of matched rule names (e.g., `["eval_usage", "leak_detection"]`)
- `match_count`: Total number of pattern matches

## Examples

### Prevent System Prompt Leaking in Multi-User Scenario

```yaml
output_filter:
  enabled: true
  system_prompt_leak_detection: true
  leak_threshold: 0.75              # Moderate sensitivity
  action: "block"                   # Hard block leaks
  log_detections: true
```

When the LLM accidentally outputs system prompt fragments, the response is blocked before reaching the user.

### Monitor for Unsafe Code Patterns

```yaml
output_filter:
  enabled: true
  system_prompt_leak_detection: false  # Disable leak detection
  action: "warn"                       # Log but allow
  log_detections: true
  custom_patterns:
    - name: "subprocess_shell"
      pattern: "subprocess\\.[a-z_]+\\(.*shell\\s*=\\s*True"
      description: "Unsafe subprocess with shell=True"
    - name: "pickle_loads"
      pattern: "pickle\\.loads\\("
      description: "Unsafe pickle deserialization"
```

Dangerous patterns are logged for review without blocking valid responses.

### Redact Sensitive Data in Responses

```yaml
output_filter:
  enabled: true
  action: "redact"
  redaction_string: "[DATA_REMOVED]"
  custom_patterns:
    - name: "database_uri"
      pattern: "(?i)(postgresql|mysql|mongodb):\\/\\/[^\\s]+"
      description: "Database connection strings"
```

Connection strings and other sensitive data are replaced before returning responses.

## Security Considerations

Output filtering provides defense-in-depth but is not foolproof:

- **Evasion**: Sophisticated LLMs or attackers can obscure patterns (e.g., line breaks in code, reformatted strings). Use `block` mode for sensitive environments.
- **False positives**: Custom patterns may over-match. Test regex patterns thoroughly before deployment.
- **N-gram limitations**: Paraphrased system prompt leaks (rephrasing the same concept) may not be detected. The filter catches verbatim or near-verbatim leaks.
- **Incomplete coverage**: Output filtering is one layer. Defense-in-depth also includes prompt injection defense (see [Prompt Injection Defense](./prompt-injection-defense.md)), DLP scanning (see [Data Loss Prevention](./dlp.md)), and audit logging.

## Team Configuration

Lock output filter settings in team config to enforce compliance:

```yaml
enforce:
  - output_filter.enabled
  - output_filter.action
  - output_filter.leak_threshold
```

This prevents individual users from disabling filtering or weakening thresholds.

## Comparison with Other Controls

| Control | Purpose | Coverage |
|---------|---------|----------|
| **Output Filter** | Prevent system prompt leaks and forbidden content | Streamed and final output |
| **DLP Scanning** | Prevent sensitive data disclosure (PII, credentials) | Input + output patterns |
| **Prompt Injection Defense** | Prevent attacker-controlled input poisoning | RAG + tool output wrapping |
| **Audit Logging** | Record security events for compliance | All API calls and tool use |

Use all controls in combination for comprehensive security.
