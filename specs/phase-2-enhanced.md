# Phase 2: Enhanced Features

## Prerequisites

- Phase 1 completed
- Core tools working (list_collections, find_document, search_documents, read_document)

## Goals

1. **Parallel search** - search multiple terms efficiently
2. **Document metadata** - TOC extraction, detailed info
3. **MCP Resources** - expose knowledge structure as resources
4. **MCP Prompts** - predefined prompts for common tasks

---

## Task 2.1: Parallel Search Tool

### Why

When answering complex questions, the agent needs to search for multiple concepts. Sequential searches are slow. Parallel search is more efficient.

### src/file_knowledge_mcp/tools/search.py (additions)

```python
# Add to existing search.py

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        # ... existing search_documents tool ...
        Tool(
            name="search_multiple",
            description="""Search for multiple terms in parallel within a document.
More efficient than calling search_documents multiple times.
Useful for complex questions involving several concepts.

Each term can use boolean syntax (space=AND, |=OR, -=NOT).""",
            inputSchema={
                "type": "object",
                "properties": {
                    "document_path": {
                        "type": "string",
                        "description": "Path to document",
                    },
                    "terms": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of search terms (max 10)",
                        "maxItems": 10,
                    },
                    "context_lines": {
                        "type": "integer",
                        "default": 5,
                    },
                    "fuzzy": {
                        "type": "boolean",
                        "default": False,
                    },
                },
                "required": ["document_path", "terms"],
            },
        ),
    ]


async def _search_multiple(
    config: Config,
    engine: UgrepEngine,
    document_path: str,
    terms: list[str],
    context_lines: int = 5,
    fuzzy: bool = False,
) -> dict:
    """Search multiple terms in parallel."""
    import asyncio
    import time

    if not terms:
        return {"error": "No search terms provided"}

    if len(terms) > 10:
        terms = terms[:10]

    full_path = config.knowledge.root / document_path
    if not full_path.exists():
        raise document_not_found(document_path)

    start_time = time.monotonic()

    # Launch all searches in parallel
    tasks = [
        engine.search(
            query=term,
            path=full_path,
            recursive=False,
            context_lines=context_lines,
            max_results=10,  # Limit per-term
            fuzzy=fuzzy,
        )
        for term in terms
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Build result dictionary
    result_dict = {}
    for term, result in zip(terms, results):
        if isinstance(result, Exception):
            result_dict[term] = {
                "found": False,
                "error": str(result),
            }
        else:
            result_dict[term] = {
                "found": result.total_matches > 0,
                "match_count": result.total_matches,
                "excerpts": [
                    {
                        "text": m.text,
                        "line": m.line_number,
                    }
                    for m in result.matches[:5]  # Top 5 per term
                ],
            }

    duration_ms = int((time.monotonic() - start_time) * 1000)

    return {
        "results": result_dict,
        "search_duration_ms": duration_ms,
    }
```

### Checklist

- [ ] Add search_multiple tool definition
- [ ] Implement parallel search with asyncio.gather
- [ ] Test with 3-5 terms
- [ ] Test error handling (one term fails)
- [ ] Add unit test

---

## Task 2.2: Document Info Tool

### Why

Before searching, agent may want to understand document structure. TOC helps navigate large documents.

### src/file_knowledge_mcp/tools/read.py (additions)

```python
# Add to existing read.py

from pypdf import PdfReader
from datetime import datetime


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        # ... existing read_document tool ...
        Tool(
            name="get_document_info",
            description="""Get document metadata including size, page count, and table of contents.
TOC is only available for PDFs with embedded bookmarks.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to document",
                    },
                },
                "required": ["path"],
            },
        ),
    ]


async def _get_document_info(config: Config, path: str) -> dict:
    """Get document metadata and TOC."""
    import asyncio

    full_path = config.knowledge.root / path
    if not full_path.exists():
        raise document_not_found(path)

    stat = full_path.stat()
    ext = full_path.suffix.lower()

    info = {
        "name": full_path.name,
        "path": path,
        "collection": str(Path(path).parent) if Path(path).parent != Path(".") else "",
        "format": ext.lstrip("."),
        "size_bytes": stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
    }

    if ext == ".pdf":
        pdf_info = await asyncio.to_thread(_extract_pdf_info, full_path)
        info.update(pdf_info)
    else:
        # For text files, count lines
        content = await asyncio.to_thread(full_path.read_text, encoding="utf-8")
        info["pages"] = 1
        info["lines"] = content.count("\n") + 1
        info["has_toc"] = False
        info["toc"] = None

    return info


def _extract_pdf_info(path: Path) -> dict:
    """Extract PDF metadata and TOC."""
    reader = PdfReader(path)

    info = {
        "pages": len(reader.pages),
        "has_toc": False,
        "toc": None,
    }

    # Try to extract TOC from outlines (bookmarks)
    try:
        outlines = reader.outline
        if outlines:
            info["has_toc"] = True
            info["toc"] = _parse_outlines(reader, outlines)
    except Exception:
        pass  # Some PDFs don't have valid outlines

    # PDF metadata
    if reader.metadata:
        meta = reader.metadata
        info["title"] = meta.get("/Title", None)
        info["author"] = meta.get("/Author", None)

    return info


def _parse_outlines(reader: PdfReader, outlines, depth: int = 0) -> list[dict]:
    """Recursively parse PDF outlines into TOC structure."""
    if depth > 5:  # Limit depth
        return []

    toc = []

    for item in outlines:
        if isinstance(item, list):
            # Nested outlines
            if toc:
                toc[-1]["children"] = _parse_outlines(reader, item, depth + 1)
        else:
            # Outline item
            entry = {
                "title": item.title if hasattr(item, "title") else str(item),
                "page": None,
            }

            # Try to get page number
            try:
                if hasattr(item, "page"):
                    page_obj = item.page
                    if page_obj:
                        for i, page in enumerate(reader.pages):
                            if page == page_obj:
                                entry["page"] = i + 1
                                break
            except Exception:
                pass

            toc.append(entry)

    return toc
```

### Example Response

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
    {"title": "Introduction", "page": 1},
    {"title": "Setup", "page": 3},
    {
      "title": "Gameplay",
      "page": 8,
      "children": [
        {"title": "Combat", "page": 12},
        {"title": "Movement", "page": 18}
      ]
    }
  ],
  "title": "Gloomhaven Rulebook",
  "author": "Isaac Childres"
}
```

### Checklist

- [ ] Add get_document_info tool
- [ ] Implement PDF metadata extraction
- [ ] Implement TOC extraction from bookmarks
- [ ] Handle PDFs without bookmarks
- [ ] Handle non-PDF files
- [ ] Add unit tests

---

## Task 2.3: Search Result Caching

### Why

Same searches may be repeated. Caching reduces latency and load.

### src/file_knowledge_mcp/search/cache.py

```python
"""Simple in-memory cache for search results."""

import asyncio
import hashlib
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class CacheEntry:
    """Cached search result."""

    result: Any
    created_at: float
    hits: int = 0


class SearchCache:
    """LRU-style cache for search results."""

    def __init__(self, max_size: int = 100, ttl_seconds: int = 300):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()

    def _make_key(self, query: str, path: str, **kwargs) -> str:
        """Generate cache key from search parameters."""
        key_data = f"{query}:{path}:{sorted(kwargs.items())}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]

    async def get(self, query: str, path: str, **kwargs) -> Any | None:
        """Get cached result if exists and not expired."""
        key = self._make_key(query, path, **kwargs)

        async with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                return None

            # Check TTL
            if time.time() - entry.created_at > self.ttl_seconds:
                del self._cache[key]
                return None

            entry.hits += 1
            return entry.result

    async def set(self, query: str, path: str, result: Any, **kwargs) -> None:
        """Cache search result."""
        key = self._make_key(query, path, **kwargs)

        async with self._lock:
            # Evict if at capacity
            if len(self._cache) >= self.max_size:
                self._evict_oldest()

            self._cache[key] = CacheEntry(
                result=result,
                created_at=time.time(),
            )

    def _evict_oldest(self) -> None:
        """Remove oldest entry."""
        if not self._cache:
            return

        oldest_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k].created_at,
        )
        del self._cache[oldest_key]

    async def clear(self) -> None:
        """Clear all cached entries."""
        async with self._lock:
            self._cache.clear()

    @property
    def stats(self) -> dict:
        """Get cache statistics."""
        total_hits = sum(e.hits for e in self._cache.values())
        return {
            "entries": len(self._cache),
            "max_size": self.max_size,
            "total_hits": total_hits,
        }
```

### Integration with UgrepEngine

```python
# In search/ugrep.py

class UgrepEngine:
    def __init__(self, config: Config, cache: SearchCache | None = None):
        self.config = config
        self.cache = cache or SearchCache()
        self._semaphore = asyncio.Semaphore(config.limits.max_concurrent_searches)

    async def search(self, query: str, path: Path, **kwargs) -> SearchResult:
        # Check cache first
        cached = await self.cache.get(query, str(path), **kwargs)
        if cached is not None:
            return cached

        # Execute search
        result = await self._execute_search(query, path, **kwargs)

        # Cache result
        await self.cache.set(query, str(path), result, **kwargs)

        return result
```

### Checklist

- [ ] Create search/cache.py
- [ ] Integrate with UgrepEngine
- [ ] Add cache stats endpoint (optional)
- [ ] Test cache hit/miss
- [ ] Test TTL expiration
- [ ] Test eviction

---

## Task 2.4: MCP Resources

### Why

Resources allow clients to discover and read knowledge base structure without tool calls.

### src/file_knowledge_mcp/resources.py

```python
"""MCP Resources for knowledge base."""

import json
from pathlib import Path

from mcp.server import Server
from mcp.types import Resource, ResourceTemplate

from .config import Config


def register_resources(server: Server, config: Config) -> None:
    """Register MCP resources."""

    @server.list_resources()
    async def list_resources() -> list[Resource]:
        """List available resources."""
        return [
            Resource(
                uri="knowledge://index",
                name="Knowledge Base Index",
                description="Root index of all collections",
                mimeType="application/json",
            ),
        ]

    @server.list_resource_templates()
    async def list_resource_templates() -> list[ResourceTemplate]:
        """List resource URI templates."""
        return [
            ResourceTemplate(
                uriTemplate="knowledge://{path}/index",
                name="Collection Index",
                description="List of documents in a collection",
                mimeType="application/json",
            ),
            ResourceTemplate(
                uriTemplate="knowledge://{path}/info",
                name="Document Info",
                description="Document metadata and TOC",
                mimeType="application/json",
            ),
        ]

    @server.read_resource()
    async def read_resource(uri: str) -> str:
        """Read resource content."""
        # Parse URI: knowledge://path/type
        if not uri.startswith("knowledge://"):
            raise ValueError(f"Invalid URI scheme: {uri}")

        path_and_type = uri[len("knowledge://"):]

        if path_and_type == "index":
            return await _get_root_index(config)

        if path_and_type.endswith("/index"):
            path = path_and_type[:-6]  # Remove "/index"
            return await _get_collection_index(config, path)

        if path_and_type.endswith("/info"):
            path = path_and_type[:-5]  # Remove "/info"
            return await _get_document_info_resource(config, path)

        raise ValueError(f"Unknown resource: {uri}")


async def _get_root_index(config: Config) -> str:
    """Get root index as JSON."""
    root = config.knowledge.root

    collections = []
    for item in sorted(root.iterdir()):
        if item.is_dir() and not item.name.startswith("."):
            collections.append({
                "name": item.name,
                "path": item.name,
                "type": "collection",
            })

    return json.dumps({
        "collections": collections,
        "root": str(root),
    }, indent=2)


async def _get_collection_index(config: Config, path: str) -> str:
    """Get collection index as JSON."""
    full_path = config.knowledge.root / path

    if not full_path.exists() or not full_path.is_dir():
        raise ValueError(f"Collection not found: {path}")

    items = []
    for item in sorted(full_path.iterdir()):
        if item.name.startswith("."):
            continue

        if item.is_dir():
            items.append({
                "name": item.name,
                "path": f"{path}/{item.name}",
                "type": "collection",
            })
        elif item.suffix.lower() in config.supported_extensions:
            items.append({
                "name": item.name,
                "path": f"{path}/{item.name}",
                "type": "document",
                "format": item.suffix.lower().lstrip("."),
            })

    return json.dumps({"items": items, "path": path}, indent=2)


async def _get_document_info_resource(config: Config, path: str) -> str:
    """Get document info as JSON."""
    from .tools.read import _get_document_info

    info = await _get_document_info(config, path)
    return json.dumps(info, indent=2)
```

### Update server.py

```python
# In server.py, add:

from .resources import register_resources

def create_server(config: Config) -> Server:
    server = Server(config.server.name)

    register_all_tools(server, config)
    register_resources(server, config)  # Add this

    return server
```

### Checklist

- [ ] Create resources.py
- [ ] Register resources in server.py
- [ ] Test knowledge://index
- [ ] Test knowledge://{path}/index
- [ ] Test knowledge://{path}/info
- [ ] Test from Claude Desktop

---

## Task 2.5: MCP Prompts

### Why

Prompts provide pre-built templates for common tasks, making it easier for users to interact.

### src/file_knowledge_mcp/prompts.py

```python
"""MCP Prompts for common knowledge base tasks."""

from mcp.server import Server
from mcp.types import Prompt, PromptArgument, PromptMessage, TextContent

from .config import Config


def register_prompts(server: Server, config: Config) -> None:
    """Register MCP prompts."""

    @server.list_prompts()
    async def list_prompts() -> list[Prompt]:
        return [
            Prompt(
                name="answer_question",
                description="Answer a question using the knowledge base",
                arguments=[
                    PromptArgument(
                        name="question",
                        description="The question to answer",
                        required=True,
                    ),
                    PromptArgument(
                        name="collection",
                        description="Limit search to specific collection (optional)",
                        required=False,
                    ),
                ],
            ),
            Prompt(
                name="summarize_document",
                description="Summarize a document from the knowledge base",
                arguments=[
                    PromptArgument(
                        name="document_path",
                        description="Path to the document",
                        required=True,
                    ),
                ],
            ),
            Prompt(
                name="compare_documents",
                description="Compare two documents on a specific topic",
                arguments=[
                    PromptArgument(
                        name="doc1",
                        description="Path to first document",
                        required=True,
                    ),
                    PromptArgument(
                        name="doc2",
                        description="Path to second document",
                        required=True,
                    ),
                    PromptArgument(
                        name="topic",
                        description="Topic to compare",
                        required=True,
                    ),
                ],
            ),
        ]

    @server.get_prompt()
    async def get_prompt(name: str, arguments: dict | None) -> list[PromptMessage]:
        args = arguments or {}

        if name == "answer_question":
            return _answer_question_prompt(args)
        elif name == "summarize_document":
            return _summarize_document_prompt(args)
        elif name == "compare_documents":
            return _compare_documents_prompt(args)
        else:
            raise ValueError(f"Unknown prompt: {name}")


def _answer_question_prompt(args: dict) -> list[PromptMessage]:
    """Generate answer_question prompt."""
    question = args.get("question", "")
    collection = args.get("collection", "")

    scope_instruction = ""
    if collection:
        scope_instruction = f"\n\nLimit your search to the '{collection}' collection."

    return [
        PromptMessage(
            role="user",
            content=TextContent(
                type="text",
                text=f"""Answer this question using the knowledge base: {question}
{scope_instruction}
Instructions:
1. First use list_collections to understand what documents are available
2. Use find_document if you need to locate a specific document
3. Use search_documents to find relevant content
4. Quote directly from the sources when possible
5. Include page numbers or section names in citations
6. If the answer is not found, say so clearly

Format your answer with:
- Direct quotes from sources (in quotation marks)
- Source citations (document name, page/section)
- Brief explanation if the quote needs clarification""",
            ),
        )
    ]


def _summarize_document_prompt(args: dict) -> list[PromptMessage]:
    """Generate summarize_document prompt."""
    document_path = args.get("document_path", "")

    return [
        PromptMessage(
            role="user",
            content=TextContent(
                type="text",
                text=f"""Summarize the document at: {document_path}

Instructions:
1. Use get_document_info to see the document structure and TOC
2. Use read_document to get the content (you may need to read in chunks)
3. Provide a structured summary including:
   - Main topic/purpose of the document
   - Key sections and their main points
   - Important concepts or definitions
   - Any notable tables, figures, or examples

Format: Use markdown with headers for each major section.""",
            ),
        )
    ]


def _compare_documents_prompt(args: dict) -> list[PromptMessage]:
    """Generate compare_documents prompt."""
    doc1 = args.get("doc1", "")
    doc2 = args.get("doc2", "")
    topic = args.get("topic", "")

    return [
        PromptMessage(
            role="user",
            content=TextContent(
                type="text",
                text=f"""Compare these two documents on the topic of "{topic}":
- Document 1: {doc1}
- Document 2: {doc2}

Instructions:
1. Use search_documents to find content about "{topic}" in both documents
2. Use search_multiple if you need to search for related concepts
3. Compare how each document addresses the topic
4. Note similarities and differences
5. Quote specific passages to support your comparison

Format your response as:
## Summary
Brief overview of how each document covers the topic

## Similarities
- Point 1 (with quotes)
- Point 2 (with quotes)

## Differences
- Point 1 (with quotes from each)
- Point 2 (with quotes from each)

## Conclusion
Which document is more comprehensive/clear/etc.""",
            ),
        )
    ]
```

### Update server.py

```python
# In server.py, add:

from .prompts import register_prompts

def create_server(config: Config) -> Server:
    server = Server(config.server.name)

    register_all_tools(server, config)
    register_resources(server, config)
    register_prompts(server, config)  # Add this

    return server
```

### Checklist

- [ ] Create prompts.py
- [ ] Register prompts in server.py
- [ ] Test answer_question prompt
- [ ] Test summarize_document prompt
- [ ] Test compare_documents prompt
- [ ] Verify prompts appear in Claude Desktop

---

## Completion Criteria

Phase 2 is complete when:

- [ ] `search_multiple` searches terms in parallel
- [ ] `get_document_info` returns metadata and TOC
- [ ] Search caching reduces repeated search latency
- [ ] Resources expose knowledge structure (knowledge://...)
- [ ] Prompts available for common tasks
- [ ] All new features have tests
- [ ] README updated with new features
