"""MCP Tools registration."""

from mcp.server import Server

from ..config import Config
from .browse import register_browse_tools
from .read import register_read_tools
from .search import register_search_tools


def register_all_tools(server: Server, config: Config) -> None:
    """Register all tools with the MCP server."""
    register_browse_tools(server, config)
    register_search_tools(server, config)
    register_read_tools(server, config)
