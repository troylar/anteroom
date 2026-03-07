# Knowledge Sources

Sources are documents, URLs, or text notes you add to Anteroom's knowledge base. Once added, their content is chunked, embedded, and available for RAG retrieval across conversations.

## Source Types

| Type | Description | Example |
|------|-------------|---------|
| **text** | Plain text content | Meeting notes, code snippets, reference material |
| **url** | A URL reference with optional content | API documentation links, wiki page references |
| **file** | An uploaded file | PDFs, code files, markdown docs |

!!! note "URL sources are metadata by default"
    URL sources store the URL as a reference. They are only chunked and embedded if you also provide `content` in the request body. Anteroom does not automatically fetch URL content.

## Creating Sources

=== "Web UI"

    Click **+** in the sources panel to add text or URL sources. Drag-and-drop files or click to upload.

=== "API"

    **Text source:**
    ```bash
    curl -X POST http://localhost:8080/api/sources \
      -H "Content-Type: application/json" \
      -d '{
        "type": "text",
        "title": "Deployment Guide",
        "content": "Step 1: Run migrations..."
      }'
    ```

    **File upload:**
    ```bash
    curl -X POST http://localhost:8080/api/sources/upload \
      -F "file=@docs/api-spec.md" \
      -F "title=API Specification"
    ```

## How Sources Are Processed

When a source is created with text content (applies to `text` and `file` types, and `url` type only if `content` is provided):

1. **Chunk**: Content is split into ~1000-character segments at sentence boundaries (`.` `!` `?`) with 200-character overlap between chunks
2. **Embed**: Each chunk is sent to the embedding provider (local fastembed or API)
3. **Index**: Embeddings are stored in the usearch vector index for fast similarity search
4. **Metadata**: Chunk metadata (content hash, source ID, status) is stored in SQLite

The chunking overlap ensures that information spanning a sentence boundary isn't lost --- both adjacent chunks contain the boundary region.

!!! note "Minimum content length"
    Chunks shorter than 10 characters are marked as "skipped" and not embedded. This avoids noise from trivial fragments.

## Organizing Sources

### Tags

Tags are labels you attach to sources for organization and filtering.

```bash
# Tag a source
curl -X POST http://localhost:8080/api/sources/{source_id}/tags/{tag_id}

# List sources by tag
curl http://localhost:8080/api/sources?tag_id={tag_id}
```

Tags also enable **tag-filter linkage** to spaces --- link a tag to a space, and all sources with that tag are automatically included in that space's RAG context.

### Source Groups

Groups are named collections of sources. Link a group to a space to include all its sources in RAG.

```bash
# Create a group
curl -X POST http://localhost:8080/api/source-groups \
  -H "Content-Type: application/json" \
  -d '{"name": "API Documentation"}'

# Add a source to the group
curl -X POST http://localhost:8080/api/source-groups/{group_id}/sources/{source_id}
```

### Linking Sources to Spaces

Sources become space-scoped by linking them to a space. Three linkage modes:

| Mode | How to Link | Effect |
|------|-------------|--------|
| **Direct** | Link a specific source | That source's chunks appear in RAG for that space |
| **Group** | Link a source group | All sources in the group appear in RAG |
| **Tag filter** | Link a tag | All sources with that tag appear in RAG |

```bash
# Direct link
curl -X POST http://localhost:8080/api/spaces/{space_id}/sources \
  -H "Content-Type: application/json" \
  -d '{"source_id": "..."}'

# Group link
curl -X POST http://localhost:8080/api/spaces/{space_id}/sources \
  -H "Content-Type: application/json" \
  -d '{"group_id": "..."}'
```

When a conversation is in a space, RAG only retrieves chunks from sources linked to that space. Sources not linked to any space are available in global (non-space) conversations.

## Updating and Re-embedding

When you update a source's content:

```bash
curl -X PATCH http://localhost:8080/api/sources/{source_id} \
  -H "Content-Type: application/json" \
  -d '{"content": "Updated content..."}'
```

Anteroom:

1. Removes old chunks and their embeddings from the vector index
2. Re-chunks the new content
3. Re-embeds all new chunks

All old chunks are deleted and the content is re-chunked and re-embedded from scratch.

## Deleting Sources

```bash
curl -X DELETE http://localhost:8080/api/sources/{source_id}
```

Deleting a source removes:

- The source record
- All associated chunks
- All chunk embeddings from the vector index
- All chunk embedding metadata from SQLite
- The uploaded file from disk (for file sources)

## Data Retention

When `storage.retention_days` is configured, the retention worker purges old conversations and their embeddings. Source embeddings are controlled separately via `storage.purge_embeddings` (default: true).

See [Configuration](config-reference.md) for all retention settings.
