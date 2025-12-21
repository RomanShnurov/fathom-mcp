"""Tests for read tools."""

import pytest

from file_knowledge_mcp.errors import McpError
from file_knowledge_mcp.tools.read import _read_document


@pytest.mark.asyncio
async def test_read_document_markdown(config):
    """Test reading a markdown document."""
    result = await _read_document(config, {"path": "games/Guide.md", "pages": []})

    assert "Game Guide" in result["content"]
    assert result["total_pages"] == 1
    assert result["pages_read"] == [1]
    assert not result["truncated"]


@pytest.mark.asyncio
async def test_read_document_not_found(config):
    """Test reading non-existent document."""
    with pytest.raises(McpError) as exc_info:
        await _read_document(config, {"path": "nonexistent.md", "pages": []})

    assert exc_info.value.code.value == "1002"  # DOCUMENT_NOT_FOUND


@pytest.mark.asyncio
async def test_read_document_truncation(config):
    """Test that very long documents are truncated."""
    # Create a large file
    large_content = "A" * 200_000  # Larger than max_document_read_chars
    large_file = config.knowledge.root / "large.txt"
    large_file.write_text(large_content)

    result = await _read_document(config, {"path": "large.txt", "pages": []})

    assert result["truncated"]
    assert len(result["content"]) <= config.limits.max_document_read_chars + 100
    assert "(truncated)" in result["content"]
