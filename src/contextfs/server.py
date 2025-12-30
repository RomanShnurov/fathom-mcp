"""MCP Server setup and lifecycle."""

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

    # Generate .ugrep config only if filters are available
    if config.needs_document_filters():
        try:
            ugrep_path = config.write_ugrep_config()
            logger.info(f"Generated .ugrep config: {ugrep_path}")
        except Exception as e:
            logger.warning(f"Failed to generate .ugrep config: {e}")
    else:
        logger.info("No document filters enabled, skipping .ugrep config generation")

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
    """Run server with stdio transport.

    Args:
        config: Server configuration
    """
    server = await create_server(config)

    # Initialize performance features
    await _initialize_performance_features(config)

    logger.info("Starting MCP server on stdio...")

    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
    finally:
        # Cleanup on shutdown
        await _cleanup_performance_features()


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
