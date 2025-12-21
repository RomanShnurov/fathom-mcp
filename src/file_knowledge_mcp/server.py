"""MCP Server setup and lifecycle."""

import logging

from mcp.server import Server
from mcp.server.stdio import stdio_server

from .config import Config
from .tools import register_all_tools

logger = logging.getLogger(__name__)


def create_server(config: Config) -> Server:
    """Create and configure MCP server.

    Args:
        config: Server configuration

    Returns:
        Configured Server instance
    """
    server = Server(config.server.name)

    # Register server info
    @server.list_resources()
    async def list_resources():
        return []  # Phase 2

    @server.list_prompts()
    async def list_prompts():
        return []  # Phase 2

    # Register tools
    register_all_tools(server, config)

    logger.info(f"Server '{config.server.name}' created")
    logger.info(f"Knowledge root: {config.knowledge.root}")

    return server


async def run_server(config: Config) -> None:
    """Run server with stdio transport.

    Args:
        config: Server configuration
    """
    server = create_server(config)

    logger.info("Starting MCP server on stdio...")

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )
