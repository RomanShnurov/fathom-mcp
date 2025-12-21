# Error Codes

All errors follow the MCP/JSON-RPC error format:

```json
{
  "error": {
    "code": "1001",
    "message": "Human-readable message",
    "data": {
      "additional": "context"
    }
  }
}
```

---

## Standard JSON-RPC Errors

| Code | Name | Description |
|------|------|-------------|
| -32700 | PARSE_ERROR | Invalid JSON |
| -32600 | INVALID_REQUEST | Invalid request object |
| -32601 | METHOD_NOT_FOUND | Method/tool not found |
| -32602 | INVALID_PARAMS | Invalid parameters |
| -32603 | INTERNAL_ERROR | Internal server error |

---

## Knowledge Base Errors (1xxx)

| Code | Name | Description | Data Fields |
|------|------|-------------|-------------|
| 1001 | PATH_NOT_FOUND | Path does not exist | `path` |
| 1002 | DOCUMENT_NOT_FOUND | Document not found | `path`, `suggestions[]` |
| 1003 | COLLECTION_NOT_FOUND | Collection not found | `path` |
| 1004 | FORMAT_NOT_SUPPORTED | File format not supported | `path`, `format`, `supported_formats[]` |

### Examples

**PATH_NOT_FOUND:**
```json
{
  "error": {
    "code": "1001",
    "message": "Path not found: games/invalid",
    "data": {
      "path": "games/invalid"
    }
  }
}
```

**DOCUMENT_NOT_FOUND with suggestions:**
```json
{
  "error": {
    "code": "1002",
    "message": "Document not found: games/Gloomhavn.pdf",
    "data": {
      "path": "games/Gloomhavn.pdf",
      "suggestions": [
        "games/coop/Gloomhaven.pdf",
        "games/coop/Gloomhaven JOTL.pdf"
      ]
    }
  }
}
```

---

## Search Errors (2xxx)

| Code | Name | Description | Data Fields |
|------|------|-------------|-------------|
| 2001 | SEARCH_TIMEOUT | Search timed out | `query`, `timeout_seconds` |
| 2002 | SEARCH_ENGINE_ERROR | ugrep failed | `details`, `stderr` |
| 2003 | INVALID_QUERY | Invalid search query | `query`, `reason` |

### Examples

**SEARCH_TIMEOUT:**
```json
{
  "error": {
    "code": "2001",
    "message": "Search timed out after 30s",
    "data": {
      "query": "complex query with many terms",
      "timeout_seconds": 30
    }
  }
}
```

**SEARCH_ENGINE_ERROR:**
```json
{
  "error": {
    "code": "2002",
    "message": "Search engine error: ugrep failed",
    "data": {
      "details": "pdftotext: command not found",
      "stderr": "sh: pdftotext: command not found"
    }
  }
}
```

---

## Sync Errors (3xxx)

| Code | Name | Description | Data Fields |
|------|------|-------------|-------------|
| 3001 | SYNC_NOT_CONFIGURED | Sync not enabled | - |
| 3002 | REMOTE_NOT_FOUND | Remote not configured | `remote`, `available_remotes[]` |
| 3003 | RCLONE_NOT_INSTALLED | rclone not installed | `install_url` |
| 3004 | RCLONE_ERROR | rclone command failed | `stderr` |
| 3005 | SYNC_IN_PROGRESS | Another sync running | `remote` |
| 3006 | SYNC_TIMEOUT | Sync timed out | `remote`, `timeout_seconds` |

### Examples

**RCLONE_NOT_INSTALLED:**
```json
{
  "error": {
    "code": "3003",
    "message": "rclone is not installed",
    "data": {
      "install_url": "https://rclone.org/install/"
    }
  }
}
```

**REMOTE_NOT_FOUND:**
```json
{
  "error": {
    "code": "3002",
    "message": "Remote not found: dropbox",
    "data": {
      "remote": "dropbox",
      "available_remotes": ["gdrive", "s3"]
    }
  }
}
```

---

## Limit Errors (4xxx)

| Code | Name | Description | Data Fields |
|------|------|-------------|-------------|
| 4001 | FILE_TOO_LARGE | File exceeds size limit | `path`, `size_mb`, `max_mb` |
| 4002 | RESULT_TRUNCATED | Results were truncated | `returned`, `total` |
| 4003 | RATE_LIMITED | Too many requests | `retry_after_seconds` |

### Examples

**FILE_TOO_LARGE:**
```json
{
  "error": {
    "code": "4001",
    "message": "File too large: 150.5MB (max: 100MB)",
    "data": {
      "path": "huge_document.pdf",
      "size_mb": 150.5,
      "max_mb": 100
    }
  }
}
```

---

## Error Handling Best Practices

### For Tool Implementers

```python
from file_knowledge_mcp.errors import (
    McpError,
    ErrorCode,
    path_not_found,
    document_not_found,
)

async def my_tool(path: str) -> dict:
    full_path = config.knowledge.root / path

    if not full_path.exists():
        # Use factory function for common errors
        raise path_not_found(path)

    if some_complex_condition:
        # Or create custom error
        raise McpError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Something went wrong",
            data={"debug_info": "..."},
        )

    return {"result": "..."}
```

### For Clients

```python
try:
    result = await client.call_tool("search_documents", {...})
except McpError as e:
    if e.code == "2001":  # SEARCH_TIMEOUT
        # Retry with smaller scope
        pass
    elif e.code == "1002":  # DOCUMENT_NOT_FOUND
        # Show suggestions to user
        suggestions = e.data.get("suggestions", [])
        print(f"Did you mean: {suggestions}?")
    else:
        # Generic error handling
        print(f"Error: {e.message}")
```

---

## Graceful Degradation

When non-critical errors occur, tools may return partial results with warnings:

```json
{
  "matches": [...],
  "total_matches": 50,
  "truncated": true,
  "warnings": [
    "Some files could not be searched: permission denied"
  ]
}
```

This is not an error - the tool succeeded but with limitations.
