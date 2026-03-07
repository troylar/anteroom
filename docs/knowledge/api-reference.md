# API Reference

REST endpoints for managing knowledge sources and semantic search.

## Sources

### List Sources

```
GET /api/sources
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `search` | string | | Full-text search filter |
| `type` | string | | Filter by type: `file`, `text`, or `url` |
| `tag_id` | string | | Filter by tag |
| `group_id` | string | | Filter by source group |
| `limit` | integer | `100` | Results per page (1--500) |
| `offset` | integer | `0` | Pagination offset |

**Response:**
```json
{
  "sources": [
    {
      "id": "uuid",
      "type": "text",
      "title": "Deployment Guide",
      "content": "...",
      "created_at": "2025-01-15T10:30:00Z",
      "updated_at": "2025-01-15T10:30:00Z"
    }
  ]
}
```

### Create Source

```
POST /api/sources
Content-Type: application/json
```

```json
{
  "type": "text",
  "title": "My Document",
  "content": "Document content here...",
  "url": null
}
```

- `type`: Required. One of `text`, `url`, `file`.
- `title`: Required.
- `content`: Text content (for `text` type).
- `url`: URL reference (for `url` type).

On creation, the content is automatically chunked and queued for embedding.

**Response:** `201 Created` with the source object.

### Upload Source File

```
POST /api/sources/upload
Content-Type: multipart/form-data
```

| Field | Type | Description |
|-------|------|-------------|
| `file` | file | The file to upload |
| `title` | string | Optional title (defaults to filename) |

Text is extracted from the file, chunked, and embedded.

**Response:** `201 Created` with the source object.

### Get Source

```
GET /api/sources/{source_id}
```

**Response:** The source object, or `404` if not found.

### Update Source

```
PATCH /api/sources/{source_id}
Content-Type: application/json
```

```json
{
  "title": "Updated Title",
  "content": "New content..."
}
```

If `content` is changed, the source is re-chunked and re-embedded. Old chunks and their embeddings are removed first.

**Response:** The updated source object, or `404`.

### Delete Source

```
DELETE /api/sources/{source_id}
```

Removes the source, its chunks, embeddings, and any uploaded file.

**Response:** `{"status": "deleted"}` or `404`.

---

## Source Tags

### Tag a Source

```
POST /api/sources/{source_id}/tags/{tag_id}
```

**Response:** `201 Created` with `{"status": "tagged"}`.

### Untag a Source

```
DELETE /api/sources/{source_id}/tags/{tag_id}
```

**Response:** `{"status": "untagged"}`.

---

## Source Groups

### List Groups

```
GET /api/source-groups
```

**Response:**
```json
{
  "groups": [
    {
      "id": "uuid",
      "name": "API Documentation",
      "description": "All API-related docs"
    }
  ]
}
```

### Create Group

```
POST /api/source-groups
Content-Type: application/json
```

```json
{
  "name": "API Documentation",
  "description": "All API-related docs"
}
```

**Response:** `201 Created` with the group object.

### Update Group

```
PATCH /api/source-groups/{group_id}
Content-Type: application/json
```

### Delete Group

```
DELETE /api/source-groups/{group_id}
```

### Add Source to Group

```
POST /api/source-groups/{group_id}/sources/{source_id}
```

### Remove Source from Group

```
DELETE /api/source-groups/{group_id}/sources/{source_id}
```

---

## Search

### Semantic Search

```
GET /api/search/semantic
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `q` | string | | Search query (required) |
| `limit` | integer | `20` | Maximum results (1--100) |
| `conversation_id` | string | | Filter to a specific conversation |

Requires embeddings and usearch to be available. Searches both messages and source chunks in a single request.

**Response:**
```json
{
  "results": [
    {
      "conversation_id": "uuid",
      "title": "Conversation title",
      "type": "chat",
      "messages": [
        {
          "id": "uuid",
          "content": "...",
          "role": "assistant",
          "distance": 0.23
        }
      ]
    }
  ],
  "source_results": [
    {
      "source_id": "uuid",
      "title": "Source title",
      "chunks": [
        {
          "chunk_id": "uuid",
          "content": "...",
          "chunk_index": 0,
          "distance": 0.31
        }
      ]
    }
  ]
}
```

Returns `503` if embeddings or usearch are not available.

### Unified Search

```
GET /api/search
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `q` | string | | Search query (required) |
| `mode` | string | `"auto"` | Search mode: `auto`, `keyword`, or `semantic` |
| `limit` | integer | `20` | Maximum results (1--100) |
| `type` | string | | Filter by conversation type: `chat`, `note`, or `document` |

In `auto` mode, uses semantic search if available, falls back to keyword. In `semantic` mode, returns `503` if unavailable.

**Semantic mode response:**
```json
{
  "mode": "semantic",
  "results": [
    {
      "message_id": "uuid",
      "conversation_id": "uuid",
      "content": "...",
      "role": "assistant",
      "distance": 0.23,
      "conversation_type": "chat"
    }
  ],
  "source_results": [
    {
      "chunk_id": "uuid",
      "source_id": "uuid",
      "content": "...",
      "chunk_index": 0,
      "distance": 0.31
    }
  ]
}
```

**Keyword mode response:**
```json
{
  "mode": "keyword",
  "results": [
    {
      "conversation_id": "uuid",
      "title": "Conversation title",
      "type": "chat",
      "message_count": 5
    }
  ]
}
```

---

## Space Source Linking

See [Spaces API Reference](../spaces/api-reference.md) for endpoints to link sources, groups, and tags to spaces.
