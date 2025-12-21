# file-knowledge-mcp: Specification

Open-source MCP server для file-first knowledge base с поиском через ugrep.

## Project Overview

**Название:** `file-knowledge-mcp`

**Цель:** Универсальный MCP сервер, который позволяет AI/LLM работать с локальными документами (PDF, MD, TXT) через file-first подход вместо RAG.

**Ключевые особенности:**
- Иерархия коллекций (папки = коллекции)
- Boolean search через ugrep
- Опциональная синхронизация с облаком (rclone)
- Zero-config старт (положил файлы - работает)

## Architecture

```
┌─────────────────┐         JSON-RPC 2.0        ┌─────────────────────────┐
│   MCP Client    │◄──────────────────────────► │   file-knowledge-mcp    │
│                 │         over stdio          │                         │
│ • Claude Desktop│                             │  Tools:                 │
│ • Claude Code   │                             │  • list_collections     │
│ • Custom Bot    │                             │  • find_document        │
│                 │                             │  • search_documents     │
│                 │                             │  • search_multiple      │
│                 │                             │  • read_document        │
│                 │                             │  • get_document_info    │
│                 │                             │  • sync_remote          │
└─────────────────┘                             └───────────┬─────────────┘
                                                            │
                                                   ┌────────▼────────┐
                                                   │     ugrep       │
                                                   │   (search)      │
                                                   └────────┬────────┘
                                                            │
                                                   ┌────────▼────────┐
                                                   │  /knowledge/    │
                                                   │  ├── games/     │
                                                   │  ├── sport/     │
                                                   │  └── history/   │
                                                   └─────────────────┘
```

## Phases

| Phase | Name | Description | Status |
|-------|------|-------------|--------|
| 1 | [Foundation](./phase-1-foundation.md) | MVP: config, core tools, CLI | Not started |
| 2 | [Enhanced](./phase-2-enhanced.md) | Parallel search, metadata, resources | Not started |
| 3 | [Sync](./phase-3-sync.md) | Cloud sync via rclone | Not started |
| 4 | [Distribution](./phase-4-distribution.md) | Docker, PyPI, docs | Not started |

## Quick Links

- [API Reference](./api-reference.md) - All tools, resources, prompts
- [Configuration](./configuration.md) - Full config reference
- [Error Codes](./error-codes.md) - Error handling

## Tech Stack

- **Python 3.12+**
- **mcp** - Model Context Protocol SDK
- **pydantic** / **pydantic-settings** - Configuration
- **ugrep** - Search engine (system dependency)
- **pypdf** - PDF metadata extraction
- **rclone** - Cloud sync (optional, system dependency)

## Installation (target)

```bash
# PyPI
pip install file-knowledge-mcp

# With sync support
pip install file-knowledge-mcp[sync]

# Docker
docker run -v ./docs:/knowledge ghcr.io/user/file-knowledge-mcp
```

## Usage (target)

```bash
# Zero-config (current directory)
file-knowledge-mcp --root ./documents

# With config file
file-knowledge-mcp --config config.yaml

# Claude Desktop integration
# Add to claude_desktop_config.json:
{
  "mcpServers": {
    "knowledge": {
      "command": "file-knowledge-mcp",
      "args": ["--root", "/path/to/documents"]
    }
  }
}
```
