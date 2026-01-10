"""Integration tests for HTTP transport.

Tests with proper server lifecycle management.
"""

import httpx
import pytest


@pytest.mark.asyncio
async def test_http_server_startup(http_server):
    """Test that HTTP server starts and responds to health check."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{http_server['url']}/_health")

        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["transport"] == "streamable-http"


@pytest.mark.asyncio
async def test_http_server_security_headers(http_server):
    """Test that security headers are present."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{http_server['url']}/_health")

        # Check security headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        assert "Content-Security-Policy" in response.headers


@pytest.mark.asyncio
async def test_http_server_request_id(http_server):
    """Test that request ID is added to responses (CRITICAL #24)."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{http_server['url']}/_health")

        assert "X-Request-ID" in response.headers


@pytest.mark.asyncio
async def test_mcp_session_initialize(mcp_http_session):
    """Test MCP session initialization over HTTP."""
    # Session already initialized by fixture
    # Just verify it's working
    tools_result = await mcp_http_session.list_tools()
    assert len(tools_result.tools) > 0


@pytest.mark.asyncio
async def test_mcp_tool_call_list_collections(mcp_http_session):
    """Test calling list_collections tool over HTTP."""
    result = await mcp_http_session.call_tool("list_collections", {})

    assert len(result.content) > 0


@pytest.mark.asyncio
async def test_mcp_tool_call_search(mcp_http_session):
    """Test calling search_documents tool over HTTP."""
    result = await mcp_http_session.call_tool(
        "search_documents",
        {"query": "test", "scope": "global"},
    )

    assert len(result.content) > 0
