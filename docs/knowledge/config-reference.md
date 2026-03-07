# Configuration Reference

All configuration knobs for embeddings and RAG.

## embeddings

Controls the embedding provider and model used for vector search.

```yaml title="~/.anteroom/config.yaml"
embeddings:
  enabled: true                          # null=auto-detect, true=force on, false=disable
  provider: "local"                      # "local" (fastembed) or "api" (OpenAI-compatible)
  model: "text-embedding-3-small"        # Model name for API provider
  dimensions: 0                          # 0=auto-detect from model
  local_model: "BAAI/bge-small-en-v1.5"  # Model name for local provider
  base_url: ""                           # API endpoint (for API provider)
  api_key: ""                            # API key (for API provider)
  api_key_command: ""                    # Shell command to fetch API key dynamically
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | bool/null | `null` | Tri-state: `null` = auto-detect (enable if provider works), `true` = force on, `false` = disable |
| `provider` | string | `"local"` | `"local"` for fastembed (offline, no API calls) or `"api"` for OpenAI-compatible endpoint |
| `model` | string | `"text-embedding-3-small"` | Model name when using API provider |
| `dimensions` | integer | `0` | Embedding dimensions; `0` = auto-detect from model (384 for local, 1536 for OpenAI) |
| `local_model` | string | `"BAAI/bge-small-en-v1.5"` | Fastembed model name; downloaded automatically on first use |
| `base_url` | string | `""` | API endpoint URL (uses main `ai.base_url` if empty) |
| `api_key` | string | `""` | API key (uses main `ai.api_key` if empty) |
| `api_key_command` | string | `""` | Shell command to fetch API key dynamically (runs on each request) |

**Environment variables:** `AI_CHAT_EMBEDDINGS_ENABLED`, `AI_CHAT_EMBEDDINGS_PROVIDER`, `AI_CHAT_EMBEDDINGS_MODEL`, `AI_CHAT_EMBEDDINGS_DIMENSIONS`, `AI_CHAT_EMBEDDINGS_LOCAL_MODEL`, `AI_CHAT_EMBEDDINGS_BASE_URL`, `AI_CHAT_EMBEDDINGS_API_KEY`, `AI_CHAT_EMBEDDINGS_API_KEY_COMMAND`

### Auto-detection

When `enabled` is `null` (the default), Anteroom probes the embedding provider on startup:

- **Local provider**: checks if fastembed is importable
- **API provider**: sends a test embedding request

If the probe succeeds, embeddings are enabled. If it fails, embeddings are silently disabled and RAG returns no results.

### Dimension Auto-detection

When `dimensions` is `0`:

| Provider | Model | Dimensions |
|----------|-------|-----------|
| local | `BAAI/bge-small-en-v1.5` | 384 |
| local | `BAAI/bge-base-en-v1.5` | 768 |
| local | `BAAI/bge-large-en-v1.5` | 1024 |
| api | (any) | 1536 |

---

## rag

Controls the RAG retrieval pipeline --- what gets searched, how many results, and filtering thresholds.

```yaml title="~/.anteroom/config.yaml"
rag:
  enabled: true                  # Master toggle for RAG
  max_chunks: 10                 # Maximum chunks to retrieve per query
  max_tokens: 2000               # Token budget for RAG context
  similarity_threshold: 0.5      # Maximum cosine distance (lower = stricter)
  include_sources: true          # Search knowledge source chunks
  include_conversations: true    # Search past conversation messages
  exclude_current: true          # Exclude current conversation from results
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | bool | `true` | Master toggle; `false` disables RAG entirely |
| `max_chunks` | integer | `10` | Maximum number of chunks to retrieve per query |
| `max_tokens` | integer | `2000` | Token budget for injected RAG context (estimated as chars / 4) |
| `similarity_threshold` | float | `0.5` | Maximum cosine distance; results above this threshold are dropped. Lower values = stricter matching |
| `include_sources` | bool | `true` | Whether to search knowledge source chunks |
| `include_conversations` | bool | `true` | Whether to search past conversation messages |
| `exclude_current` | bool | `true` | Whether to exclude the current conversation from message search results |

**Environment variables:** `AI_CHAT_RAG_ENABLED`, `AI_CHAT_RAG_MAX_CHUNKS`, `AI_CHAT_RAG_MAX_TOKENS`, `AI_CHAT_RAG_SIMILARITY_THRESHOLD`

### Tuning the Threshold

The `similarity_threshold` is a cosine distance (not cosine similarity). Lower values mean stricter matching:

| Value | Effect |
|-------|--------|
| `0.3` | Very strict --- only highly relevant content surfaces |
| `0.5` | Default --- good balance of relevance and recall |
| `0.7` | Loose --- more content surfaces, may include less relevant results |
| `1.0` | Everything matches (not recommended) |

### Token Budget

The `max_tokens` setting controls how much RAG context is injected into the system prompt. The estimate uses `characters / 4` as a rough token approximation.

If retrieved chunks exceed the budget, the least relevant chunks (highest distance) are dropped until the budget is met.

---

## storage (RAG-related fields)

```yaml title="~/.anteroom/config.yaml"
storage:
  purge_embeddings: true    # Delete embeddings when conversations are purged
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `purge_embeddings` | bool | `true` | When `retention_days` is set and conversations are purged, also delete their embeddings from the vector index |

---

## Example Configurations

### Offline / Air-gapped

```yaml
embeddings:
  provider: "local"
  # Everything runs locally, no network needed
```

### OpenAI Embeddings

```yaml
embeddings:
  provider: "api"
  model: "text-embedding-3-small"
  base_url: "https://api.openai.com/v1"
  api_key: "sk-..."
```

### Disable RAG

```yaml
rag:
  enabled: false
```

### Strict Matching with Small Context

```yaml
rag:
  similarity_threshold: 0.3
  max_chunks: 5
  max_tokens: 1000
```

### Sources Only (No Conversation History)

```yaml
rag:
  include_conversations: false
  include_sources: true
```
