# Tools Reference

Detailed documentation for all MCP tools provided by the contextfs server.

---

## Overview

The server provides 6 tools for browsing, searching, and reading documents:

| Tool | Purpose | Use Case |
|------|---------|----------|
| `list_collections` | Browse folder structure | Navigate document hierarchy |
| `find_document` | Find documents by name | Locate specific files |
| `search_documents` | Full-text search | Find content in documents |
| `search_multiple` | Parallel multi-term search | Fast multi-query search |
| `read_document` | Read document content | View full document |
| `get_document_info` | Get metadata and TOC | Understand document structure |

---

## list_collections

Browse document collections (folders) in the knowledge base.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "path": {
      "type": "string",
      "description": "Path relative to knowledge root. Empty for root.",
      "default": ""
    }
  }
}
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `path` | string | No | `""` | Path to collection (empty = root) |

### Response

```json
{
  "current_path": "games/coop",
  "collections": [
    {
      "name": "legacy",
      "path": "games/coop/legacy",
      "document_count": 3,
      "subcollection_count": 0
    }
  ],
  "documents": [
    {
      "name": "Gloomhaven.pdf",
      "path": "games/coop/Gloomhaven.pdf",
      "size_bytes": 2457600,
      "modified": "2024-01-15T10:30:00"
    }
  ]
}
```

### Examples

**Browse root:**
```json
{
  "path": ""
}
```

**Browse specific collection:**
```json
{
  "path": "programming/python"
}
```

### Error Codes

- `COLLECTION_NOT_FOUND` - Path doesn't exist
- `PATH_TRAVERSAL_DETECTED` - Invalid path (e.g., `../`)
- `NOT_A_DIRECTORY` - Path is a file, not a collection

---

## find_document

Find documents by name across all collections.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "Document name or part of it"
    },
    "limit": {
      "type": "integer",
      "description": "Max results",
      "default": 10,
      "minimum": 1,
      "maximum": 100
    }
  },
  "required": ["query"]
}
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | Yes | - | Document name pattern |
| `limit` | integer | No | `10` | Maximum results (1-100) |

### Response

```json
{
  "matches": [
    {
      "name": "Gloomhaven.pdf",
      "path": "games/coop/Gloomhaven.pdf",
      "collection": "games/coop",
      "size_bytes": 2457600,
      "modified": "2024-01-15T10:30:00",
      "score": 1.0
    }
  ],
  "total_found": 1
}
```

### Examples

**Find by exact name:**
```json
{
  "query": "tutorial.pdf"
}
```

**Find by partial name:**
```json
{
  "query": "async",
  "limit": 20
}
```

### Notes

- Search is case-insensitive
- Matches anywhere in the filename
- Results sorted by relevance (exact match > prefix match > contains)

---

## search_documents

Search for text inside documents using boolean patterns.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "Search query with boolean operators"
    },
    "scope": {
      "type": "object",
      "properties": {
        "type": {
          "type": "string",
          "enum": ["global", "collection", "document"]
        },
        "path": {
          "type": "string",
          "description": "Path for collection/document scope"
        }
      },
      "required": ["type"]
    },
    "context_lines": {
      "type": "integer",
      "default": 5,
      "minimum": 0,
      "maximum": 50
    },
    "max_results": {
      "type": "integer",
      "default": 20,
      "minimum": 1,
      "maximum": 500
    },
    "fuzzy": {
      "type": "boolean",
      "default": false
    }
  },
  "required": ["query", "scope"]
}
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | Yes | - | Search query with operators |
| `scope` | object | Yes | - | Search scope |
| `context_lines` | integer | No | `5` | Context lines (0-50) |
| `max_results` | integer | No | `20` | Max results (1-500) |
| `fuzzy` | boolean | No | `false` | Enable fuzzy matching |

### Scope Types

**Global** - Search all documents:
```json
{
  "type": "global"
}
```

**Collection** - Search within a folder:
```json
{
  "type": "collection",
  "path": "programming/python"
}
```

**Document** - Search single document:
```json
{
  "type": "document",
  "path": "guides/tutorial.pdf"
}
```

### Query Syntax

| Syntax | Meaning | Example |
|--------|---------|---------|
| Space | AND (both terms) | `attack armor` |
| `\|` | OR (either term) | `move\|teleport` |
| `-` | NOT (exclude term) | `attack -ranged` |
| `""` | Exact phrase | `"end of turn"` |

### Response

```json
{
  "matches": [
    {
      "document": "games/coop/Gloomhaven.pdf",
      "line": 42,
      "text": "Movement allows a figure to move up to...",
      "context_before": [
        "## Movement Rules",
        ""
      ],
      "context_after": [
        "Each movement point allows moving one hex.",
        ""
      ]
    }
  ],
  "total_matches": 5,
  "truncated": false,
  "query": "movement"
}
```

### Examples

**Simple search:**
```json
{
  "query": "authentication",
  "scope": { "type": "global" }
}
```

**Boolean AND:**
```json
{
  "query": "jwt token",
  "scope": { "type": "collection", "path": "docs/api" }
}
```

**Boolean OR:**
```json
{
  "query": "async|asynchronous",
  "scope": { "type": "global" }
}
```

**Boolean NOT:**
```json
{
  "query": "security -deprecated",
  "scope": { "type": "global" }
}
```

**Exact phrase:**
```json
{
  "query": "\"end of turn\"",
  "scope": { "type": "document", "path": "games/rulebook.pdf" }
}
```

**Complex query:**
```json
{
  "query": "(authentication|authorization) security -deprecated",
  "scope": { "type": "collection", "path": "docs" },
  "context_lines": 10,
  "max_results": 50
}
```

### Error Codes

- `SEARCH_TIMEOUT` - Search exceeded timeout
- `INVALID_QUERY` - Malformed search query
- `SCOPE_NOT_FOUND` - Specified path doesn't exist

---

## search_multiple

Search for multiple queries in parallel for faster results.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "queries": {
      "type": "array",
      "items": { "type": "string" },
      "description": "List of search queries",
      "minItems": 1,
      "maxItems": 10
    },
    "scope": {
      "type": "object",
      "properties": {
        "type": {
          "type": "string",
          "enum": ["global", "collection", "document"]
        },
        "path": {
          "type": "string"
        }
      },
      "required": ["type"]
    },
    "context_lines": {
      "type": "integer",
      "default": 5
    },
    "max_results_per_query": {
      "type": "integer",
      "default": 20
    }
  },
  "required": ["queries", "scope"]
}
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `queries` | array[string] | Yes | - | Search queries (1-10) |
| `scope` | object | Yes | - | Search scope |
| `context_lines` | integer | No | `5` | Context lines |
| `max_results_per_query` | integer | No | `20` | Max results per query |

### Response

```json
{
  "results": {
    "authentication": {
      "query": "authentication",
      "matches": [...],
      "total_matches": 12,
      "truncated": false
    },
    "authorization": {
      "query": "authorization",
      "matches": [...],
      "total_matches": 8,
      "truncated": false
    }
  },
  "search_duration_ms": 234,
  "queries_completed": 2,
  "queries_failed": 0
}
```

### Examples

**Search multiple terms:**
```json
{
  "queries": ["authentication", "authorization", "security"],
  "scope": { "type": "collection", "path": "docs/api" }
}
```

**Multiple queries in a document:**
```json
{
  "queries": ["movement", "attack", "defense"],
  "scope": { "type": "document", "path": "games/rulebook.pdf" },
  "context_lines": 3
}
```

### Notes

- Queries run in parallel for speed
- Each query is independent
- Failed queries don't stop others
- Results keyed by original query

---

## read_document

Read full document content or specific pages.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "path": {
      "type": "string",
      "description": "Path to document"
    },
    "pages": {
      "type": "array",
      "items": { "type": "integer", "minimum": 1 },
      "description": "Specific pages to read (1-indexed). Empty = all.",
      "default": []
    }
  },
  "required": ["path"]
}
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `path` | string | Yes | - | Path to document |
| `pages` | array[integer] | No | `[]` | Specific pages (empty = all) |

### Response

```json
{
  "content": "--- Page 1 ---\n\nIntroduction\n...\n\n--- Page 2 ---\n...",
  "pages_read": [1, 2, 3],
  "total_pages": 52,
  "format": "pdf",
  "truncated": false,
  "char_count": 15234
}
```

### Examples

**Read entire document:**
```json
{
  "path": "guides/tutorial.md"
}
```

**Read specific PDF pages:**
```json
{
  "path": "manuals/reference.pdf",
  "pages": [1, 2, 5, 10]
}
```

**Read page range (pages 10-15):**
```json
{
  "path": "books/manual.pdf",
  "pages": [10, 11, 12, 13, 14, 15]
}
```

### Notes

- For PDFs, pages are 1-indexed
- For text/markdown files, `pages` parameter is ignored
- Content may be truncated based on `max_document_read_chars` limit
- Page separators inserted for multi-page documents

### Error Codes

- `DOCUMENT_NOT_FOUND` - Document doesn't exist
- `UNSUPPORTED_FORMAT` - File format not supported
- `PAGE_OUT_OF_RANGE` - Requested page doesn't exist
- `FILTER_FAILED` - Text extraction failed

---

## get_document_info

Get document metadata including table of contents.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "path": {
      "type": "string",
      "description": "Path to document"
    }
  },
  "required": ["path"]
}
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `path` | string | Yes | Path to document |

### Response

```json
{
  "name": "Gloomhaven.pdf",
  "path": "games/coop/Gloomhaven.pdf",
  "collection": "games/coop",
  "format": "pdf",
  "size_bytes": 2457600,
  "size_human": "2.4 MB",
  "pages": 52,
  "modified": "2024-01-15T10:30:00",
  "has_toc": true,
  "toc": [
    {
      "title": "Introduction",
      "page": 1,
      "level": 1
    },
    {
      "title": "Gameplay",
      "page": 8,
      "level": 1,
      "children": [
        {
          "title": "Movement",
          "page": 10,
          "level": 2
        },
        {
          "title": "Combat",
          "page": 12,
          "level": 2
        }
      ]
    }
  ],
  "metadata": {
    "title": "Gloomhaven Rulebook",
    "author": "Isaac Childres",
    "created": "2023-05-10T00:00:00",
    "keywords": ["board game", "rules"]
  }
}
```

### Examples

**Get PDF info:**
```json
{
  "path": "manuals/reference.pdf"
}
```

**Get markdown info:**
```json
{
  "path": "docs/api-guide.md"
}
```

### Notes

- Table of contents (TOC) extracted from PDF outline/bookmarks
- For markdown, TOC extracted from headers (`#`, `##`, etc.)
- Not all PDFs have embedded TOC
- Metadata availability depends on document format

### Error Codes

- `DOCUMENT_NOT_FOUND` - Document doesn't exist
- `UNSUPPORTED_FORMAT` - File format not supported
- `METADATA_EXTRACTION_FAILED` - Could not extract metadata

---

## Error Handling

All tools return errors in this format:

```json
{
  "error": {
    "code": "DOCUMENT_NOT_FOUND",
    "message": "Document not found: guides/missing.pdf",
    "details": {
      "path": "guides/missing.pdf"
    }
  }
}
```

### Common Error Codes

| Code | Description | Recovery |
|------|-------------|----------|
| `DOCUMENT_NOT_FOUND` | Document doesn't exist | Check path with find_document |
| `COLLECTION_NOT_FOUND` | Collection doesn't exist | Use list_collections to browse |
| `PATH_TRAVERSAL_DETECTED` | Invalid path (security) | Use paths within knowledge root |
| `SEARCH_TIMEOUT` | Search took too long | Reduce scope or increase timeout |
| `UNSUPPORTED_FORMAT` | File format not supported | Check formats config |
| `FILTER_FAILED` | Text extraction failed | Check filter command |
| `SECURITY_VIOLATION` | Security check failed | Review security config |

See [error-codes.md](../specs/error-codes.md) for complete list.

---

## Performance Tips

1. **Use appropriate scope**: Search in `collection` or `document` rather than `global` when possible
2. **Limit results**: Set `max_results` to only what you need
3. **Parallel search**: Use `search_multiple` for multiple terms
4. **Reduce context**: Lower `context_lines` for faster searches
5. **Fuzzy matching**: Disable unless needed (slower)

---

## Best Practices

### Browsing Documents

```
1. list_collections("") → Browse root
2. list_collections("games") → Drill down
3. read_document("games/rulebook.pdf") → Read found document
```

### Finding Content

```
1. find_document("tutorial") → Find by name
2. search_documents("async patterns", scope=collection) → Search in collection
3. read_document(path, pages=[1,2,3]) → Read relevant pages
```

### Multi-term Research

```
1. search_multiple(["concept1", "concept2", "concept3"])
2. get_document_info(top_match) → Get structure
3. read_document(path, pages=relevant_pages) → Read details
```
