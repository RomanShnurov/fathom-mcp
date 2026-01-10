"""MCP Server setup and lifecycle."""

import asyncio
import contextlib
import logging
from dataclasses import dataclass

from mcp.server import Server
from mcp.server.stdio import stdio_server

from .config import Config
from .prompts import register_prompts
from .resources import register_resources
from .search.index import DocumentIndex
from .search.watcher import WatcherManager
from .tools import register_all_tools

logger = logging.getLogger(__name__)


@dataclass
class ServerContext:
    """Context holding server state and dependencies.

    This encapsulates global state to enable better testing and dependency injection.
    """

    document_index: DocumentIndex | None = None
    watcher_manager: WatcherManager | None = None
    config: Config | None = None


# Global server context instance
_server_context: ServerContext = ServerContext()


async def create_server(config: Config) -> Server:
    """Create and configure MCP server.

    Args:
        config: Server configuration

    Returns:
        Configured Server instance
    """
    from .tools.validation import validate_filter_tools

    server = Server(config.server.name)

    # Validate filter tools and auto-disable unavailable formats
    validation_results = await validate_filter_tools(config)
    enabled_count = sum(1 for available in validation_results.values() if available)
    total_count = len(validation_results)
    logger.info(f"Filter tools validated: {enabled_count}/{total_count} formats available")

    # Log configured filters (no file generation needed - filters are built programmatically)
    if config.needs_document_filters():
        from .search.filter_builder import FilterArgumentsBuilder

        builder = FilterArgumentsBuilder(config)
        logger.info("Document filters configured:")
        for line in builder.get_filter_summary().split("\n")[1:]:  # Skip header
            if line.strip() and line.strip() != "(none)":
                logger.info(line)
    else:
        logger.info("No document filters enabled")

    # Register tools, resources, and prompts
    register_all_tools(server, config)
    register_resources(server, config)
    register_prompts(server, config)

    logger.info(f"Server '{config.server.name}' created")
    logger.info(f"Knowledge root: {config.knowledge.root}")

    return server


async def _initialize_performance_features(config: Config) -> None:
    """Initialize performance features (indexing, file watching).

    Args:
        config: Server configuration
    """
    global _server_context

    # Initialize document index if enabled
    if config.performance.enable_indexing:
        logger.info("Initializing document index...")
        index_path = config.knowledge.root / config.performance.index_path
        _server_context.document_index = DocumentIndex(config.knowledge.root, index_path)

        # Try to load existing index
        loaded = await _server_context.document_index.load_index()

        if loaded:
            logger.info("Loaded existing document index")
        else:
            logger.info("No existing index found")

        # Rebuild index on startup if configured
        if config.performance.rebuild_index_on_startup or not loaded:
            logger.info("Building document index...")
            result = await _server_context.document_index.build_index(
                formats=config.performance.index_formats,
                exclude_patterns=config.exclude.patterns,
            )
            logger.info(
                f"Index built: {result['documents_indexed']} documents, "
                f"{result['total_terms']} terms"
            )

        # Start file watching if enabled
        if config.performance.enable_file_watching:
            logger.info("Starting file watcher for automatic index updates...")
            _server_context.watcher_manager = WatcherManager(
                config.knowledge.root, _server_context.document_index
            )
            await _server_context.watcher_manager.start(
                watch_extensions=config.performance.index_formats
            )
            logger.info("File watcher started")


async def _cleanup_performance_features() -> None:
    """Cleanup performance features on shutdown."""
    global _server_context

    if _server_context.watcher_manager:
        logger.info("Stopping file watcher...")
        await _server_context.watcher_manager.stop()

    if _server_context.document_index:
        logger.info("Saving document index...")
        try:
            await _server_context.document_index._save_index()
        except Exception as e:
            logger.error(f"Failed to save index: {e}")


async def run_server(config: Config) -> None:
    """Run server with configured transport.

    Supports stdio (default) and Streamable HTTP.

    Args:
        config: Server configuration
    """
    server = await create_server(config)

    # Initialize performance features for stdio
    if config.transport.type == "stdio":
        await _initialize_performance_features(config)

    try:
        if config.transport.type == "stdio":
            await _run_stdio_transport(server, config)
        else:
            await _run_http_transport(server, config)
    finally:
        # Cleanup for stdio (HTTP handled by lifecycle manager)
        if config.transport.type == "stdio":
            await _cleanup_performance_features()


async def _run_stdio_transport(server: Server, config: Config) -> None:
    """Run server with stdio transport (existing implementation).

    Args:
        server: MCP server instance
        config: Server configuration
    """
    logger.info("Starting MCP server on stdio...")

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


async def _run_http_transport(server: Server, config: Config) -> None:
    """Run server with HTTP transport and graceful shutdown.

    Implements graceful shutdown for Docker.

    Args:
        server: MCP server instance
        config: Server configuration
    """
    import signal
    from typing import Any

    import uvicorn

    from fathom_mcp.transports import create_http_app

    logger.info(
        f"Starting MCP server with {config.transport.type} transport "
        f"at {config.transport.host}:{config.transport.port}"
    )

    # Additional security reminder for production deployments
    if config.transport.host == "0.0.0.0":
        logger.info(
            "Security reminder: Server is accessible from network. "
            "Ensure reverse proxy or VPN is configured. "
            "See docs/security.md"
        )

    app = await create_http_app(server, config)

    uvicorn_config = uvicorn.Config(
        app,
        host=config.transport.host,
        port=config.transport.port,
        log_level=config.transport.log_level.lower(),
        access_log=config.transport.access_log,
        reload=config.transport.reload,
        # Graceful shutdown settings
        timeout_keep_alive=5,
        timeout_graceful_shutdown=30,
    )

    uvicorn_server = uvicorn.Server(uvicorn_config)

    # Setup signal handlers for graceful shutdown
    shutdown_event = asyncio.Event()

    def handle_signal(sig: int, frame: Any) -> None:
        logger.info(f"Received signal {sig}, starting graceful shutdown...")
        shutdown_event.set()

    # Register signal handlers (cross-platform)
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    # Run server with shutdown monitoring
    server_task = asyncio.create_task(uvicorn_server.serve())
    shutdown_task = asyncio.create_task(shutdown_event.wait())

    try:
        # Wait for either server to finish or shutdown signal
        done, pending = await asyncio.wait(
            {server_task, shutdown_task},
            return_when=asyncio.FIRST_COMPLETED,
        )

        if shutdown_event.is_set():
            logger.info("Shutdown signal received, stopping server...")
            uvicorn_server.should_exit = True
            await server_task  # Wait for graceful shutdown

    finally:
        # Cancel pending tasks
        for task in pending:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


def get_document_index() -> DocumentIndex | None:
    """Get the global document index instance.

    Returns:
        DocumentIndex instance if indexing is enabled, None otherwise
    """
    return _server_context.document_index


def get_server_context() -> ServerContext:
    """Get the global server context.

    Returns:
        Global ServerContext instance
    """
    return _server_context
