"""Server lifecycle management with graceful shutdown."""

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from starlette.applications import Starlette

    from fathom_mcp.config import Config

logger = logging.getLogger(__name__)


class ServerLifecycleManager:
    """Manages server lifecycle with graceful shutdown.

    Handles:
        - Server startup initialization
        - Performance features (indexing, file watching)
        - Active session tracking
        - Graceful shutdown with timeout
        - Resource cleanup

    Uses app.state for context storage (NOT global variables).
    Implements graceful shutdown with timeout protection.
    """

    def __init__(self, config: "Config"):
        """Initialize lifecycle manager.

        Args:
            config: Server configuration
        """
        self.config = config
        self.active_sessions: set[asyncio.Task[None]] = set()
        self.shutdown_timeout = 30.0  # seconds

    async def startup(self, app: "Starlette") -> None:
        """Initialize server resources.

        Stores server context in app.state (NOT global).

        Args:
            app: Starlette application instance

        Raises:
            RuntimeError: If server startup fails
        """
        logger.info("Starting server lifecycle...")

        try:
            # Use app.state instead of global context
            from fathom_mcp.server import ServerContext

            app.state.server_context = ServerContext()

            # Initialize performance features
            await self._init_performance_features(app)

            logger.info("Server lifecycle started successfully")

        except Exception as e:
            logger.error(f"Failed to start server: {e}", exc_info=True)
            raise RuntimeError(f"Server startup failed: {e}") from e

    async def shutdown(self, app: "Starlette") -> None:
        """Gracefully shutdown server resources.

        Implements timeout protection for shutdown.

        Args:
            app: Starlette application instance
        """
        logger.info("Starting graceful shutdown...")

        try:
            # Wait for active sessions with timeout
            if self.active_sessions:
                logger.info(f"Waiting for {len(self.active_sessions)} active sessions...")
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*self.active_sessions, return_exceptions=True),
                        timeout=self.shutdown_timeout,
                    )
                except TimeoutError:
                    logger.warning(f"Shutdown timeout after {self.shutdown_timeout}s, forcing...")

            # Cleanup resources
            await self._cleanup_performance_features(app)

            logger.info("Graceful shutdown completed")

        except TimeoutError:
            logger.warning(f"Shutdown timeout after {self.shutdown_timeout}s, forcing...")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)

    async def _init_performance_features(self, app: "Starlette") -> None:
        """Initialize indexing and file watching.

        Args:
            app: Starlette application with server context in state
        """
        context = app.state.server_context
        config = self.config

        # Initialize document index if enabled
        if config.performance.enable_indexing:
            from fathom_mcp.search.index import DocumentIndex

            index_path = config.knowledge.root / config.performance.index_path
            context.document_index = DocumentIndex(
                config.knowledge.root,
                index_path,
            )

            logger.info(f"Building document index at {index_path}...")
            await context.document_index.build_index()
            logger.info("Document index built successfully")

        # Initialize file watcher if enabled
        if config.performance.enable_file_watching:
            from fathom_mcp.search.watcher import WatcherManager

            context.watcher_manager = WatcherManager(config.knowledge.root, context.document_index)
            await context.watcher_manager.start()
            logger.info("File watcher started")

    async def _cleanup_performance_features(self, app: "Starlette") -> None:
        """Cleanup indexing and file watching.

        Args:
            app: Starlette application with server context in state
        """
        if not hasattr(app.state, "server_context"):
            return

        context = app.state.server_context

        # Stop file watcher
        if context.watcher_manager:
            logger.info("Stopping file watcher...")
            try:
                await asyncio.wait_for(
                    context.watcher_manager.stop(),
                    timeout=5.0,
                )
                logger.info("File watcher stopped")
            except TimeoutError:
                logger.warning("File watcher stop timeout, forcing...")

        # Save document index
        if context.document_index:
            logger.info("Saving document index...")
            try:
                await asyncio.wait_for(
                    context.document_index._save_index(),
                    timeout=10.0,
                )
                logger.info("Document index saved")
            except TimeoutError:
                logger.warning("Index save timeout, data may be lost")
            except Exception as e:
                logger.error(f"Failed to save index: {e}")
