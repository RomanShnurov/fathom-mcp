"""Read tools: read_document, get_document_info."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from mcp.types import TextContent, Tool
from pypdf import PdfReader

from ..config import Config
from ..errors import document_not_found, file_too_large, filter_execution_error, filter_timeout
from ..pdf.parallel import ParallelPDFProcessor
from ..security import FileAccessControl

logger = logging.getLogger(__name__)


def get_read_tools() -> list[Tool]:
    """Get read tool definitions."""
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
        Tool(
            name="get_document_info",
            description="""Get document metadata including size, page count, and TOC.
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


def _validate_filter_output(output: bytes, format_ext: str) -> str:
    """Validate and decode filter output.

    Args:
        output: Raw bytes from filter
        format_ext: File extension for context

    Returns:
        Decoded text string

    Raises:
        McpError: If output is invalid
    """
    # Check output isn't empty
    if not output:
        logger.warning(f"Filter for {format_ext} produced empty output")
        return ""

    # Decode with error handling
    try:
        text = output.decode("utf-8")
        return text
    except UnicodeDecodeError as e:
        logger.warning(f"Filter output contains invalid UTF-8 for {format_ext}: {e}")
        # Try with error replacement
        return output.decode("utf-8", errors="replace")


async def _read_with_filter_streaming(
    full_path: Path,
    filter_cmd: str,
    config: Config,
) -> str:
    """Read large document using streaming filter execution.

    Args:
        full_path: Path to document file
        filter_cmd: Filter command to execute
        config: Server configuration

    Returns:
        Extracted text content

    Raises:
        McpError: If filter execution fails or times out
    """
    import asyncio
    import shlex

    from ..security import FilterSecurity

    filter_security = FilterSecurity(config)

    # Validate filter command
    filter_cmd_stdin = config.prepare_filter_for_stdin(filter_cmd)
    if not filter_security.validate_filter_command(filter_cmd_stdin):
        raise filter_execution_error(
            full_path.name, filter_cmd, "Filter command not allowed by security policy"
        )

    # Parse command for subprocess
    cmd_parts = shlex.split(filter_cmd_stdin)

    try:
        # Create subprocess with stdin from file
        proc = await asyncio.create_subprocess_exec(
            *cmd_parts,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Read file and send to process stdin
        file_bytes = await asyncio.to_thread(full_path.read_bytes)

        # Communicate with timeout
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=file_bytes),
            timeout=config.security.filter_timeout_seconds,
        )

        if proc.returncode != 0:
            error_msg = stderr.decode("utf-8", errors="replace")
            raise filter_execution_error(full_path.name, filter_cmd, error_msg)

        # Validate and decode output
        return _validate_filter_output(stdout, full_path.suffix)

    except TimeoutError as te:
        if proc:
            proc.kill()
            await proc.wait()
        raise filter_timeout(full_path.name, config.security.filter_timeout_seconds) from te
    except Exception as e:
        if not isinstance(e, filter_execution_error.__class__):
            raise filter_execution_error(full_path.name, filter_cmd, str(e)) from e
        raise


async def _read_with_filter(
    full_path: Path,
    filter_cmd: str,
    config: Config,
    max_size_mb: int = 50,
) -> str:
    """Read document using filter command.

    For large files (>50MB), uses streaming to avoid memory issues.

    Args:
        full_path: Path to document file
        filter_cmd: Filter command to execute (e.g., "pandoc ...")
        config: Server configuration
        max_size_mb: Max size for in-memory processing (default 50MB)

    Returns:
        Extracted text content

    Raises:
        McpError: If filter execution fails or times out
    """
    import asyncio

    from ..security import FilterSecurity

    # Check file size
    file_size_mb = full_path.stat().st_size / (1024 * 1024)

    if file_size_mb > max_size_mb:
        logger.info(f"Large file ({file_size_mb:.1f}MB), using streaming filter")
        return await _read_with_filter_streaming(full_path, filter_cmd, config)

    try:
        # Read file bytes
        file_bytes = await asyncio.to_thread(full_path.read_bytes)

        # Execute filter with security validation
        filter_security = FilterSecurity(config)

        # Use proper placeholder replacement
        filter_cmd_stdin = config.prepare_filter_for_stdin(filter_cmd)

        text_bytes = await filter_security.run_secure_filter(
            filter_cmd_stdin,
            file_bytes,
            timeout_override=config.security.filter_timeout_seconds,
        )

        # Validate and decode output
        return _validate_filter_output(text_bytes, full_path.suffix)

    except TimeoutError as te:
        raise filter_timeout(full_path.name, config.security.filter_timeout_seconds) from te
    except Exception as e:
        if not isinstance(e, filter_execution_error.__class__):
            raise filter_execution_error(full_path.name, filter_cmd, str(e)) from e
        raise


async def handle_read_tool(
    name: str, arguments: dict[str, Any], config: Config
) -> list[TextContent]:
    """Handle read tool calls."""
    if name == "read_document":
        result = await _read_document(config, arguments)
        return [TextContent(type="text", text=format_result(result))]
    elif name == "get_document_info":
        result = await _get_document_info(config, arguments)
        return [TextContent(type="text", text=format_result(result))]

    raise ValueError(f"Unknown tool: {name}")


async def _read_document(config: Config, args: dict[str, Any]) -> dict[str, Any]:
    """Read document content."""
    import asyncio

    path = args["path"]
    pages = args.get("pages", [])

    # Validate path using FileAccessControl
    access_control = FileAccessControl(config.knowledge.root, config)
    full_path = access_control.validate_path(path)

    if not full_path.exists():
        raise document_not_found(path)

    # Check file size
    size_mb = full_path.stat().st_size / (1024 * 1024)
    max_mb = config.search.max_file_size_mb
    if size_mb > max_mb:
        raise file_too_large(path, size_mb, max_mb)

    # Get file extension
    ext = full_path.suffix.lower()

    # Get filter command for this extension
    filter_cmd = config.get_filter_for_extension(ext)

    # === PDF: Special handling with parallel processing ===
    if ext == ".pdf":
        if config.performance.enable_parallel_pdf:
            processor = ParallelPDFProcessor(max_workers=config.performance.max_pdf_workers)
            try:
                content = await processor.extract_text_parallel(
                    full_path, pages=pages if pages else None, include_page_markers=True
                )
                reader = PdfReader(full_path)
                total_pages = len(reader.pages)

                # Determine which pages were read
                if pages:
                    pages_read = [p for p in pages if 0 < p <= total_pages]
                else:
                    pages_read = list(range(1, total_pages + 1))
            finally:
                processor.shutdown()
        else:
            content, total_pages, pages_read = await asyncio.to_thread(_read_pdf, full_path, pages)

    # === Filtered formats: Use filter command ===
    elif filter_cmd:
        content = await _read_with_filter(full_path, filter_cmd, config)

        # For filtered documents, treat as single-page
        total_pages = 1
        pages_read = [1]

        # Page selection not supported for non-PDF
        if pages and pages != [1]:
            logger.warning(f"Page selection not supported for {ext} files, returning all content")

    # === Plain text formats: Direct read ===
    else:
        content = await asyncio.to_thread(full_path.read_text, encoding="utf-8", errors="replace")
        total_pages = 1
        pages_read = [1]

    # Apply character limit
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


async def _get_document_info(config: Config, args: dict[str, Any]) -> dict[str, Any]:
    """Get document metadata and TOC."""
    import asyncio

    path = args["path"]

    # Validate path using FileAccessControl
    access_control = FileAccessControl(config.knowledge.root, config)
    full_path = access_control.validate_path(path)

    if not full_path.exists():
        raise document_not_found(path)

    # Base info
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

    # Get filter command if applicable
    filter_cmd = config.get_filter_for_extension(ext)
    if filter_cmd:
        info["filter"] = filter_cmd.split()[0]  # Just the command name

    # === PDF-specific metadata ===
    if ext == ".pdf":
        # Use parallel PDF processor if enabled for metadata extraction
        if config.performance.enable_parallel_pdf:
            processor = ParallelPDFProcessor(max_workers=config.performance.max_pdf_workers)
            try:
                pdf_info = await processor.extract_metadata(full_path)
                info.update(pdf_info)
            finally:
                processor.shutdown()
        else:
            pdf_info = await asyncio.to_thread(_extract_pdf_info, full_path)
            info.update(pdf_info)

    # === Text formats: Add line count ===
    elif filter_cmd is None:
        try:
            content = await asyncio.to_thread(
                full_path.read_text, encoding="utf-8", errors="replace"
            )
            info["pages"] = 1
            info["lines"] = content.count("\n") + 1
            info["has_toc"] = False
            info["toc"] = None
        except Exception as e:
            logger.warning(f"Failed to read text file for line count: {e}")

    # === Filtered formats: Add page count estimate ===
    else:
        try:
            # Read through filter to get content
            text = await _read_with_filter(full_path, filter_cmd, config)
            # Estimate pages (rough: 500 words per page)
            word_count = len(text.split())
            info["estimated_pages"] = max(1, word_count // 500)
            info["word_count"] = word_count
        except Exception as e:
            logger.warning(f"Failed to extract document info: {e}")

    return info


def _extract_pdf_info(path: Path) -> dict[str, Any]:
    """Extract PDF metadata and TOC."""
    reader = PdfReader(path)

    info: dict[str, Any] = {
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


def _parse_outlines(reader: PdfReader, outlines: Any, depth: int = 0) -> list[dict[str, Any]]:
    """Recursively parse PDF outlines into TOC structure."""
    if depth > 5:  # Limit depth
        return []

    toc: list[dict[str, Any]] = []

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


def format_result(result: dict[str, Any]) -> str:
    import json

    return json.dumps(result, indent=2, ensure_ascii=False)
