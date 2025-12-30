"""Tests for MCP resources functionality."""

import json
import sys

import pytest

from contextfs.errors import ErrorCode, McpError
from contextfs.resources import (
    _get_collection_index,
    _get_document_info_resource,
    _get_root_index,
)

# ============================================================================
# MCP Resources Tests
# ============================================================================


@pytest.mark.asyncio
async def test_resources_root_index(rich_config):
    """Test knowledge://index resource."""
    result_json = await _get_root_index(rich_config)
    result = json.loads(result_json)

    assert "collections" in result
    assert "root" in result
    assert isinstance(result["collections"], list)

    # Should list top-level collections
    collection_names = [c["name"] for c in result["collections"]]
    assert "games" in collection_names
    assert "sport" in collection_names

    # Check collection structure
    games_collection = next(c for c in result["collections"] if c["name"] == "games")
    assert games_collection["type"] == "collection"
    assert games_collection["path"] == "games"


@pytest.mark.asyncio
async def test_resources_collection_index(rich_config):
    """Test knowledge://{path}/index resource."""
    result_json = await _get_collection_index(rich_config, "games")
    result = json.loads(result_json)

    assert "items" in result
    assert "path" in result
    assert result["path"] == "games"

    # Should list items in games collection
    item_names = [item["name"] for item in result["items"]]
    assert "coop" in item_names  # subdirectory
    assert "Strategy.md" in item_names  # file


@pytest.mark.asyncio
async def test_resources_collection_index_with_subcollection(rich_config):
    """Test collection index for nested collection."""
    result_json = await _get_collection_index(rich_config, "games/coop")
    result = json.loads(result_json)

    assert result["path"] == "games/coop"

    # Should list documents in games/coop
    item_names = [item["name"] for item in result["items"]]
    assert "Gloomhaven.md" in item_names


@pytest.mark.asyncio
async def test_resources_collection_index_nonexistent(rich_config):
    """Test collection index for non-existent collection."""
    with pytest.raises(McpError) as exc_info:
        await _get_collection_index(rich_config, "nonexistent")

    assert exc_info.value.code == ErrorCode.COLLECTION_NOT_FOUND


@pytest.mark.asyncio
async def test_resources_document_info(rich_config):
    """Test knowledge://{path}/info resource."""
    result_json = await _get_document_info_resource(rich_config, "games/coop/Gloomhaven.md")
    result = json.loads(result_json)

    assert result["name"] == "Gloomhaven.md"
    assert result["path"] == "games/coop/Gloomhaven.md"
    assert result["format"] == "md"


@pytest.mark.asyncio
async def test_resources_filters_hidden_files(rich_knowledge_dir, rich_config):
    """Test that resources filter out hidden files and directories."""
    # Create hidden file and directory
    (rich_knowledge_dir / "games" / ".hidden_file.md").write_text("Hidden content")
    (rich_knowledge_dir / "games" / ".hidden_dir").mkdir(exist_ok=True)

    result_json = await _get_collection_index(rich_config, "games")
    result = json.loads(result_json)

    item_names = [item["name"] for item in result["items"]]
    assert ".hidden_file.md" not in item_names
    assert ".hidden_dir" not in item_names


# ============================================================================
# Security Tests - Path Traversal Prevention
# ============================================================================


@pytest.mark.asyncio
async def test_resources_collection_path_traversal_blocked(rich_config):
    """Test that path traversal attempts are blocked for collections."""
    # Unix-style paths (work on all platforms)
    traversal_paths = [
        "../",
        "../../",
        "../../../etc",
        "games/../..",
        "games/../../etc/passwd",
    ]

    # Windows-style paths (only work on Windows)
    if sys.platform == "win32":
        traversal_paths.extend(
            [
                "..\\..\\",
                "games\\..\\..\\",
            ]
        )

    for path in traversal_paths:
        with pytest.raises(McpError) as exc_info:
            await _get_collection_index(rich_config, path)

        assert (
            exc_info.value.code == ErrorCode.PATH_TRAVERSAL_DETECTED
        ), f"Path traversal not detected for: {path}"


@pytest.mark.asyncio
async def test_resources_document_path_traversal_blocked(rich_config):
    """Test that path traversal attempts are blocked for document info."""
    # Unix-style paths (work on all platforms)
    traversal_paths = [
        "../secret.txt",
        "../../etc/passwd",
        "games/../../secret.md",
    ]

    # Windows-style paths (only work on Windows)
    if sys.platform == "win32":
        traversal_paths.append("..\\..\\secret.txt")

    for path in traversal_paths:
        with pytest.raises(McpError) as exc_info:
            await _get_document_info_resource(rich_config, path)

        assert (
            exc_info.value.code == ErrorCode.PATH_TRAVERSAL_DETECTED
        ), f"Path traversal not detected for: {path}"


@pytest.mark.asyncio
async def test_resources_document_info_nonexistent(rich_config):
    """Test document info for non-existent document."""
    with pytest.raises(McpError) as exc_info:
        await _get_document_info_resource(rich_config, "games/nonexistent.md")

    assert exc_info.value.code == ErrorCode.DOCUMENT_NOT_FOUND


@pytest.mark.asyncio
async def test_resources_document_info_on_directory(rich_config):
    """Test document info when path points to a directory instead of file."""
    with pytest.raises(McpError) as exc_info:
        await _get_document_info_resource(rich_config, "games")

    assert exc_info.value.code == ErrorCode.DOCUMENT_NOT_FOUND


@pytest.mark.asyncio
async def test_resources_collection_index_on_file(rich_config):
    """Test collection index when path points to a file instead of directory."""
    with pytest.raises(McpError) as exc_info:
        await _get_collection_index(rich_config, "games/Strategy.md")

    assert exc_info.value.code == ErrorCode.COLLECTION_NOT_FOUND
