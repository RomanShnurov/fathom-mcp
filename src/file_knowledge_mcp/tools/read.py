"""Read tools: read_document."""

import logging
from pathlib import Path

from mcp.server import Server
from mcp.types import TextContent, Tool
from pypdf import PdfReader

from ..config import Config
from ..errors import document_not_found, file_too_large

logger = logging.getLogger(__name__)


def register_read_tools(server: Server, config: Config) -> None:
    """Register read-related tools."""

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="read_document",
                description="""Read full document content or specific pages.
Use as fallback when search doesn't find what you need.
WARNING: Can return large amounts of text, prefer search when possible.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to document (relative to knowledge root)",
                        },
                        "pages": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Specific pages to read (1-indexed). Empty = all.",
                            "default": [],
                        },
                    },
                    "required": ["path"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        if name == "read_document":
            result = await _read_document(config, arguments)
            return [TextContent(type="text", text=format_result(result))]

        raise ValueError(f"Unknown tool: {name}")


async def _read_document(config: Config, args: dict) -> dict:
    """Read document content."""
    import asyncio

    path = args["path"]
    pages = args.get("pages", [])

    full_path = config.knowledge.root / path

    if not full_path.exists():
        raise document_not_found(path)

    # Check file size
    size_mb = full_path.stat().st_size / (1024 * 1024)
    max_mb = config.search.max_file_size_mb
    if size_mb > max_mb:
        raise file_too_large(path, size_mb, max_mb)

    # Read based on format
    ext = full_path.suffix.lower()

    if ext == ".pdf":
        content, total_pages, pages_read = await asyncio.to_thread(
            _read_pdf, full_path, pages
        )
    else:
        content = await asyncio.to_thread(full_path.read_text, encoding="utf-8")
        total_pages = 1
        pages_read = [1]

    # Truncate if needed
    max_chars = config.limits.max_document_read_chars
    truncated = len(content) > max_chars
    if truncated:
        content = content[:max_chars] + "\n...(truncated)"

    return {
        "content": content,
        "pages_read": pages_read,
        "total_pages": total_pages,
        "truncated": truncated,
    }


def _read_pdf(path: Path, pages: list[int]) -> tuple[str, int, list[int]]:
    """Read PDF content."""
    reader = PdfReader(path)
    total_pages = len(reader.pages)

    # Determine which pages to read
    if pages:
        # Convert to 0-indexed, filter valid
        page_indices = [p - 1 for p in pages if 0 < p <= total_pages]
    else:
        page_indices = list(range(total_pages))

    text_parts = []
    for idx in page_indices:
        page_num = idx + 1
        text_parts.append(f"--- Page {page_num} ---")
        text_parts.append(reader.pages[idx].extract_text() or "")

    return "\n".join(text_parts), total_pages, [i + 1 for i in page_indices]


def format_result(result: dict) -> str:
    import json
    return json.dumps(result, indent=2, ensure_ascii=False)
