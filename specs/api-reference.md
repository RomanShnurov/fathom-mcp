# API Reference

Complete reference for all MCP tools, resources, and prompts.

---

## Tools

### list_collections

Browse document collections (folders) in the knowledge base.

**Input Schema:**
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

**Response:**
```json
{
  "current_path": "games",
  "collections": [
    {
      "name": "coop",
      "path": "games/coop",
      "document_count": 5,
      "subcollection_count": 0
    }
  ],
  "documents": [
    {
      "name": "Guide.pdf",
      "size_bytes": 153600,
      "modified": "2024-01-15T10:30:00"
    }
  ]
}
```

---

### find_document

Find documents by name across all collections.

**Input Schema:**
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
      "default": 10
    }
  },
  "required": ["query"]
}
```

**Response:**
```json
{
  "matches": [
    {
      "name": "Gloomhaven.pdf",
      "path": "games/coop/Gloomhaven.pdf",
      "collection": "games/coop",
      "size_bytes": 2457600,
      "score": 1.0
    }
  ],
  "total_found": 1
}
```

---

### search_documents

Search for text inside documents using boolean patterns.

**Input Schema:**
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
      "default": 5
    },
    "max_results": {
      "type": "integer",
      "default": 20
    },
    "fuzzy": {
      "type": "boolean",
      "default": false
    }
  },
  "required": ["query", "scope"]
}
```

**Query Syntax:**
| Syntax | Meaning | Example |
|--------|---------|---------|
| Space | AND | `attack armor` (both terms) |
| `\|` | OR | `move\|teleport` (either term) |
| `-` | NOT | `attack -ranged` (exclude ranged) |
| `""` | Exact phrase | `"end of turn"` |

**Response:**
```json
{
  "matches": [
    {
      "document": "games/coop/Gloomhaven.pdf",
      "line": 42,
      "text": "Movement allows a figure to move up to...",
      "context_before": ["previous lines..."],
      "context_after": ["following lines..."]
    }
  ],
  "total_matches": 5,
  "truncated": false
}
```

---

### search_multiple

Search for multiple terms in parallel within a document.

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "document_path": {
      "type": "string",
      "description": "Path to document"
    },
    "terms": {
      "type": "array",
      "items": { "type": "string" },
      "description": "List of search terms (max 10)",
      "maxItems": 10
    },
    "context_lines": {
      "type": "integer",
      "default": 5
    },
    "fuzzy": {
      "type": "boolean",
      "default": false
    }
  },
  "required": ["document_path", "terms"]
}
```

**Response:**
```json
{
  "results": {
    "movement": {
      "found": true,
      "match_count": 12,
      "excerpts": [
        { "text": "Movement allows...", "line": 42 }
      ]
    },
    "attack": {
      "found": true,
      "match_count": 25,
      "excerpts": [...]
    }
  },
  "search_duration_ms": 234
}
```

---

### read_document

Read full document content or specific pages.

**Input Schema:**
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
      "items": { "type": "integer" },
      "description": "Specific pages to read (1-indexed). Empty = all.",
      "default": []
    }
  },
  "required": ["path"]
}
```

**Response:**
```json
{
  "content": "--- Page 1 ---\n...",
  "pages_read": [1, 2, 3],
  "total_pages": 52,
  "truncated": false
}
```

---

### get_document_info

Get document metadata including TOC.

**Input Schema:**
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

**Response:**
```json
{
  "name": "Gloomhaven.pdf",
  "path": "games/coop/Gloomhaven.pdf",
  "collection": "games/coop",
  "format": "pdf",
  "size_bytes": 2457600,
  "pages": 52,
  "modified": "2024-01-15T10:30:00",
  "has_toc": true,
  "toc": [
    { "title": "Introduction", "page": 1 },
    {
      "title": "Gameplay",
      "page": 8,
      "children": [
        { "title": "Combat", "page": 12 }
      ]
    }
  ],
  "title": "Gloomhaven Rulebook",
  "author": "Isaac Childres"
}
```

---

### get_sync_status

Get sync status for configured remotes.

**Input Schema:**
```json
{
  "type": "object",
  "properties": {}
}
```

**Response:**
```json
{
  "rclone_installed": true,
  "sync_enabled": true,
  "remotes": {
    "gdrive": {
      "rclone_remote": "gdrive:Knowledge",
      "local_path": "(root)",
      "auto_sync": false,
      "interval_minutes": 0,
      "remote_configured": true
    }
  }
}
```

---

### check_remote_changes

Preview what would be synced without syncing.

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "remote_name": {
      "type": "string",
      "description": "Name of configured remote"
    }
  },
  "required": ["remote_name"]
}
```

**Response:**
```json
{
  "remote_name": "gdrive",
  "rclone_remote": "gdrive:Knowledge",
  "to_download": ["New File.pdf", "Updated.pdf"],
  "to_delete": [],
  "in_sync": false
}
```

---

### sync_remote

Sync documents from remote storage.

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "remote_name": {
      "type": "string",
      "description": "Name of configured remote"
    },
    "dry_run": {
      "type": "boolean",
      "description": "Preview without applying",
      "default": false
    }
  },
  "required": ["remote_name"]
}
```

**Response:**
```json
{
  "remote_name": "gdrive",
  "rclone_remote": "gdrive:Knowledge",
  "dry_run": false,
  "success": true,
  "changes": [
    { "path": "New File.pdf", "action": "download" }
  ],
  "stats": {
    "files_transferred": 1,
    "bytes_transferred": 1234567,
    "duration_seconds": 5
  },
  "error": null
}
```

---

## Resources

### knowledge://index

Root index of all collections.

**URI:** `knowledge://index`

**Response:**
```json
{
  "collections": [
    { "name": "games", "path": "games", "type": "collection" },
    { "name": "sport", "path": "sport", "type": "collection" }
  ],
  "root": "/data/knowledge"
}
```

### knowledge://{path}/index

Collection index.

**URI Template:** `knowledge://{path}/index`

**Example:** `knowledge://games/coop/index`

**Response:**
```json
{
  "items": [
    { "name": "Gloomhaven.pdf", "path": "games/coop/Gloomhaven.pdf", "type": "document", "format": "pdf" }
  ],
  "path": "games/coop"
}
```

### knowledge://{path}/info

Document info.

**URI Template:** `knowledge://{path}/info`

**Example:** `knowledge://games/coop/Gloomhaven.pdf/info`

**Response:** Same as `get_document_info` tool.

---

## Prompts

### answer_question

Answer a question using the knowledge base.

**Arguments:**
| Name | Required | Description |
|------|----------|-------------|
| question | Yes | The question to answer |
| collection | No | Limit search to specific collection |

**Generated Prompt:**
```
Answer this question using the knowledge base: {question}

Instructions:
1. First use list_collections to understand what documents are available
2. Use find_document if you need to locate a specific document
3. Use search_documents to find relevant content
4. Quote directly from the sources when possible
5. Include page numbers or section names in citations
...
```

### summarize_document

Summarize a document.

**Arguments:**
| Name | Required | Description |
|------|----------|-------------|
| document_path | Yes | Path to the document |

### compare_documents

Compare two documents on a topic.

**Arguments:**
| Name | Required | Description |
|------|----------|-------------|
| doc1 | Yes | Path to first document |
| doc2 | Yes | Path to second document |
| topic | Yes | Topic to compare |
