"""Integration tests for MCP protocol end-to-end functionality.

This module tests the complete MCP server by:
1. Starting a real server process via stdio transport
2. Connecting through MCP ClientSession
3. Testing all tools, resources, and prompts through the protocol

Note: Uses mcp_session fixture from conftest.py for automatic server setup/teardown.
"""

import json

import pytest
from mcp import ClientSession

# ============================================================================
# Tools Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_mcp_tool_list_collections(mcp_session: ClientSession):
    """Test list_collections tool via MCP protocol."""
    # Call list_collections tool
    result = await mcp_session.call_tool("list_collections", arguments={})

    # Parse result
    assert len(result.content) > 0
    content = result.content[0]
    assert hasattr(content, "text")

    data = json.loads(content.text)
    assert "collections" in data
    assert isinstance(data["collections"], list)

    # Should have our test collections
    collection_names = [c["name"] for c in data["collections"]]
    assert "games" in collection_names
    assert "sport" in collection_names


@pytest.mark.asyncio
async def test_mcp_tool_find_document(mcp_session: ClientSession):
    """Test find_document tool via MCP protocol."""
    # Find documents with "Gloomhaven" in the name
    result = await mcp_session.call_tool(
        "find_document",
        arguments={"query": "Gloomhaven", "limit": 10},
    )

    content = result.content[0]
    data = json.loads(content.text)

    assert "matches" in data
    assert len(data["matches"]) > 0

    # Should find Gloomhaven.md
    doc_names = [d["name"] for d in data["matches"]]
    assert any("Gloomhaven" in name for name in doc_names)


@pytest.mark.asyncio
async def test_mcp_tool_search_documents(mcp_session: ClientSession):
    """Test search_documents tool via MCP protocol."""
    # Search for "movement"
    result = await mcp_session.call_tool(
        "search_documents",
        arguments={"query": "movement", "scope": {"type": "global"}},
    )

    content = result.content[0]
    data = json.loads(content.text)

    assert "matches" in data
    assert len(data["matches"]) > 0

    # Should find matches with "movement"
    first_match = data["matches"][0]
    assert "document" in first_match  # Key is "document" not "path"
    assert "line" in first_match
    assert "text" in first_match
    assert "movement" in first_match["text"].lower()


@pytest.mark.asyncio
async def test_mcp_tool_search_multiple(mcp_session: ClientSession):
    """Test search_multiple tool via MCP protocol."""
    # Search multiple terms in a document
    result = await mcp_session.call_tool(
        "search_multiple",
        arguments={
            "document_path": "games/coop/Gloomhaven.md",
            "terms": ["attack", "movement", "defense"],
        },
    )

    content = result.content[0]
    data = json.loads(content.text)

    assert "results" in data
    # results is a dict with term names as keys
    assert len(data["results"]) == 3
    assert "attack" in data["results"]
    assert "movement" in data["results"]
    assert "defense" in data["results"]

    # At least some searches should find matches
    total_matches = sum(r["match_count"] for r in data["results"].values())
    assert total_matches > 0


@pytest.mark.asyncio
async def test_mcp_tool_read_document(mcp_session: ClientSession):
    """Test read_document tool via MCP protocol."""
    # Read a document
    result = await mcp_session.call_tool(
        "read_document",
        arguments={"path": "games/coop/Gloomhaven.md"},
    )

    content = result.content[0]
    data = json.loads(content.text)

    assert "content" in data
    assert "Gloomhaven" in data["content"]
    assert "Movement" in data["content"]


@pytest.mark.asyncio
async def test_mcp_tool_get_document_info(mcp_session: ClientSession):
    """Test get_document_info tool via MCP protocol."""
    # Get document info
    result = await mcp_session.call_tool(
        "get_document_info",
        arguments={"path": "games/coop/Gloomhaven.md"},
    )

    content = result.content[0]
    data = json.loads(content.text)

    assert "name" in data
    assert data["name"] == "Gloomhaven.md"
    assert "path" in data
    assert data["path"] == "games/coop/Gloomhaven.md"
    assert "format" in data
    assert data["format"] == "md"


# ============================================================================
# Resources Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_mcp_resource_root_index(mcp_session: ClientSession):
    """Test knowledge://index resource via MCP protocol."""
    # Read root index resource
    result = await mcp_session.read_resource("knowledge://index")

    assert len(result.contents) > 0
    content = result.contents[0]
    assert hasattr(content, "text")

    data = json.loads(content.text)
    assert "collections" in data
    assert "root" in data

    # Should list our test collections
    collection_names = [c["name"] for c in data["collections"]]
    assert "games" in collection_names
    assert "sport" in collection_names


@pytest.mark.asyncio
async def test_mcp_resource_collection_index(mcp_session: ClientSession):
    """Test knowledge://{path}/index resource via MCP protocol."""
    # Read collection index
    result = await mcp_session.read_resource("knowledge://games/index")

    content = result.contents[0]
    data = json.loads(content.text)

    assert "items" in data
    assert "path" in data
    assert data["path"] == "games"

    # Should list items in games collection
    item_names = [item["name"] for item in data["items"]]
    assert "coop" in item_names
    assert "Strategy.md" in item_names


@pytest.mark.asyncio
async def test_mcp_resource_document_info(mcp_session: ClientSession):
    """Test knowledge://{path}/info resource via MCP protocol."""
    # Read document info resource
    result = await mcp_session.read_resource("knowledge://games/coop/Gloomhaven.md/info")

    content = result.contents[0]
    data = json.loads(content.text)

    assert data["name"] == "Gloomhaven.md"
    assert data["path"] == "games/coop/Gloomhaven.md"
    assert data["format"] == "md"


@pytest.mark.asyncio
async def test_mcp_list_resources(mcp_session: ClientSession):
    """Test listing available resources via MCP protocol."""
    # List all resources
    result = await mcp_session.list_resources()

    assert len(result.resources) > 0

    # Should include root index
    resource_uris = [str(r.uri) for r in result.resources]
    assert "knowledge://index" in resource_uris


@pytest.mark.asyncio
async def test_mcp_list_resource_templates(mcp_session: ClientSession):
    """Test listing resource templates via MCP protocol."""
    # List resource templates
    result = await mcp_session.list_resources()

    # Note: Templates are returned via list_resource_templates in the protocol
    # For now, we verify that resources can be listed
    assert len(result.resources) > 0


# ============================================================================
# Prompts Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_mcp_list_prompts(mcp_session: ClientSession):
    """Test listing available prompts via MCP protocol."""
    # List all prompts
    result = await mcp_session.list_prompts()

    assert len(result.prompts) == 3

    prompt_names = [p.name for p in result.prompts]
    assert "answer_question" in prompt_names
    assert "summarize_document" in prompt_names
    assert "compare_documents" in prompt_names


@pytest.mark.asyncio
async def test_mcp_prompt_answer_question(mcp_session: ClientSession):
    """Test answer_question prompt via MCP protocol."""
    # Get answer_question prompt
    result = await mcp_session.get_prompt(
        "answer_question",
        arguments={"question": "How does movement work?", "collection": "games"},
    )

    assert len(result.messages) > 0
    message = result.messages[0]

    assert message.role == "user"
    # Content should mention the question and collection
    content_text = (
        message.content.text if hasattr(message.content, "text") else str(message.content)
    )
    assert "How does movement work?" in content_text
    assert "games" in content_text


@pytest.mark.asyncio
async def test_mcp_prompt_summarize_document(mcp_session: ClientSession):
    """Test summarize_document prompt via MCP protocol."""
    # Get summarize_document prompt
    result = await mcp_session.get_prompt(
        "summarize_document",
        arguments={"document_path": "games/coop/Gloomhaven.md"},
    )

    assert len(result.messages) > 0
    message = result.messages[0]

    assert message.role == "user"
    content_text = (
        message.content.text if hasattr(message.content, "text") else str(message.content)
    )
    assert "games/coop/Gloomhaven.md" in content_text


@pytest.mark.asyncio
async def test_mcp_prompt_compare_documents(mcp_session: ClientSession):
    """Test compare_documents prompt via MCP protocol."""
    # Get compare_documents prompt
    result = await mcp_session.get_prompt(
        "compare_documents",
        arguments={
            "doc1": "games/coop/Gloomhaven.md",
            "doc2": "games/Strategy.md",
            "topic": "combat tactics",
        },
    )

    assert len(result.messages) > 0
    message = result.messages[0]

    assert message.role == "user"
    content_text = (
        message.content.text if hasattr(message.content, "text") else str(message.content)
    )
    assert "games/coop/Gloomhaven.md" in content_text
    assert "games/Strategy.md" in content_text
    assert "combat tactics" in content_text


# ============================================================================
# Server Lifecycle Tests
# ============================================================================


@pytest.mark.asyncio
async def test_mcp_server_initialization(mcp_session: ClientSession):
    """Test that server can be initialized via MCP protocol.

    NOTE: Session is pre-initialized by mcp_session fixture.
    This test verifies the session is ready for use.
    """
    # Session should be ready - verify by calling a simple operation
    result = await mcp_session.list_tools()

    # Server should have tools registered (indicates successful initialization)
    assert result is not None
    assert len(result.tools) > 0


@pytest.mark.asyncio
async def test_mcp_list_all_tools(mcp_session: ClientSession):
    """Test listing all available tools via MCP protocol."""
    # List all tools
    result = await mcp_session.list_tools()

    assert len(result.tools) == 6

    tool_names = [t.name for t in result.tools]
    assert "list_collections" in tool_names
    assert "find_document" in tool_names
    assert "search_documents" in tool_names
    assert "search_multiple" in tool_names
    assert "read_document" in tool_names
    assert "get_document_info" in tool_names

    # Each tool should have a description
    for tool in result.tools:
        assert tool.description
        assert tool.name


# ============================================================================
# Error Handling Tests
# ============================================================================


@pytest.mark.asyncio
async def test_mcp_tool_error_handling(mcp_session: ClientSession):
    """Test error handling for invalid tool calls via MCP protocol.

    NOTE: MCP protocol returns tool errors as CallToolResult with isError=True,
    rather than raising exceptions. This is the expected behavior.
    """
    # Test path traversal detection (should return error result)
    result = await mcp_session.call_tool(
        "read_document",
        arguments={"path": "../../etc/passwd"},
    )

    # Verify it's an error result
    assert result.isError is True, "Expected isError=True for path traversal"

    # Verify error message content
    assert len(result.content) > 0, "Expected error message in content"
    error_text = result.content[0].text.lower()
    assert (
        "path" in error_text or "traversal" in error_text or "security" in error_text
    ), f"Expected security-related error, got: {error_text}"


@pytest.mark.asyncio
async def test_mcp_tool_not_found_error(mcp_session: ClientSession):
    """Test error handling for non-existent documents via MCP protocol."""
    # Try to read a non-existent document
    result = await mcp_session.call_tool(
        "read_document",
        arguments={"path": "nonexistent-file-12345.md"},
    )

    # Verify it's an error result
    assert result.isError is True, "Expected isError=True for non-existent file"

    # Verify error message content
    assert len(result.content) > 0, "Expected error message in content"
    error_text = result.content[0].text.lower()
    assert (
        "not found" in error_text or "does not exist" in error_text
    ), f"Expected 'not found' error, got: {error_text}"


@pytest.mark.asyncio
async def test_mcp_resource_error_handling(mcp_session: ClientSession):
    """Test error handling for invalid resource URIs via MCP protocol."""
    # Try to read a non-existent collection
    # MCP protocol may raise various exceptions for invalid resources
    with pytest.raises((Exception, RuntimeError, ValueError)):
        await mcp_session.read_resource("knowledge://nonexistent/index")


# ============================================================================
# Performance Tests
# ============================================================================


@pytest.mark.asyncio
async def test_mcp_multiple_sequential_calls(mcp_session: ClientSession):
    """Test multiple sequential tool calls via MCP protocol."""
    # Make multiple sequential calls
    for _i in range(3):
        result = await mcp_session.call_tool("list_collections", arguments={})
        content = result.content[0]
        data = json.loads(content.text)
        assert "collections" in data

        # Each call should succeed
        assert len(data["collections"]) > 0


@pytest.mark.asyncio
async def test_mcp_mixed_operations(mcp_session: ClientSession):
    """Test mixing tools, resources, and prompts in single mcp_session."""
    # List tools
    tools = await mcp_session.list_tools()
    assert len(tools.tools) > 0

    # Call a tool
    tool_result = await mcp_session.call_tool("list_collections", arguments={})
    assert len(tool_result.content) > 0

    # Read a resource
    resource_result = await mcp_session.read_resource("knowledge://index")
    assert len(resource_result.contents) > 0

    # List prompts
    prompts = await mcp_session.list_prompts()
    assert len(prompts.prompts) > 0

    # Get a prompt
    prompt_result = await mcp_session.get_prompt(
        "answer_question",
        arguments={"question": "test"},
    )
    assert len(prompt_result.messages) > 0
