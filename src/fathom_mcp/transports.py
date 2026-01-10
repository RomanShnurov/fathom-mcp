"""HTTP transport implementations using MCP SDK.

Uses app.state for context (NOT global variables).
Proper async context manager patterns with strategy pattern for extensibility.
Integrates MCP SDK TransportSecuritySettings.
"""

import contextlib
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Protocol

from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

if TYPE_CHECKING:
    from mcp.server import Server
    from starlette.requests import Request

    from fathom_mcp.config import Config

logger = logging.getLogger(__name__)


# ============================================================================
# Transport Factory Protocol
# ============================================================================


class TransportFactory(Protocol):
    """Protocol for transport factory implementations.

    Strategy pattern for transport extensibility.
    """

    async def create_app(self, server: "Server", config: "Config") -> Starlette:
        """Create Starlette app for this transport.

        Args:
            server: MCP server instance
            config: Server configuration

        Returns:
            Configured Starlette application
        """
        ...


# ============================================================================
# Streamable HTTP Transport Factory
# ============================================================================


class StreamableHTTPTransportFactory:
    """Streamable HTTP transport implementation.

    Uses StreamableHTTPSessionManager to properly manage MCP server sessions
    over HTTP transport.
    """

    async def create_app(self, server: "Server", config: "Config") -> Starlette:
        """Create Streamable HTTP app with session manager."""
        # Create session manager with MCP server
        # This manages the lifecycle of MCP sessions over HTTP
        session_manager = StreamableHTTPSessionManager(app=server)

        # CRITICAL: Mount session manager as ASGI app
        # session_manager.handle_request is a complete ASGI application
        routes: list[Route | Mount] = [
            Mount(config.transport.base_path, app=session_manager.handle_request),
        ]

        return await self._build_app(routes, config, session_manager)

    async def _build_app(
        self,
        routes: list[Route | Mount],
        config: "Config",
        session_manager: StreamableHTTPSessionManager,
    ) -> Starlette:
        """Build app with session manager lifecycle."""

        from fathom_mcp.middleware import (
            RequestIDMiddleware,
            SecurityHeadersMiddleware,
            error_handler,
        )

        # Healthcheck
        routes.append(
            Route(
                config.transport.healthcheck_endpoint,
                self._health_check,
                methods=["GET"],
            )
        )

        # Lifespan context manager to run session manager
        @contextlib.asynccontextmanager
        async def lifespan(app: Starlette) -> AsyncIterator[None]:
            """Manage session manager lifecycle."""
            async with session_manager.run():
                yield

        app = Starlette(
            routes=routes,
            lifespan=lifespan,
            exception_handlers={Exception: error_handler},
        )

        app.add_middleware(SecurityHeadersMiddleware)
        app.add_middleware(RequestIDMiddleware)

        if config.transport.enable_cors:
            from starlette.middleware.cors import CORSMiddleware

            app.add_middleware(
                CORSMiddleware,
                allow_origins=config.transport.allowed_origins,
                allow_methods=config.transport.allowed_methods,
                allow_headers=config.transport.allowed_headers,
                allow_credentials=False,
                max_age=config.transport.max_age,
            )

        return app

    async def _health_check(self, request: "Request") -> JSONResponse:
        """Healthcheck endpoint."""
        checks = {
            "status": "healthy",
            "transport": "streamable-http",
            "timestamp": datetime.now(UTC).isoformat(),
        }

        return JSONResponse(checks, status_code=200)


# ============================================================================
# Factory Registry
# ============================================================================

TRANSPORT_FACTORIES: dict[str, type[TransportFactory]] = {
    "streamable-http": StreamableHTTPTransportFactory,
}


# ============================================================================
# Main Entry Point
# ============================================================================


async def create_http_app(server: "Server", config: "Config") -> Starlette:
    """Create Starlette app for HTTP transport.

    Uses strategy pattern for extensibility.

    Creates a configured Starlette application with:
    - Transport-specific routes (Streamable HTTP)
    - CORS middleware (if enabled)
    - Security headers middleware
    - Request ID middleware for tracing
    - Error handlers for graceful error responses
    - Lifecycle handlers (startup/shutdown)

    Args:
        server: MCP server instance created by create_server()
        config: Server configuration with transport settings

    Returns:
        Configured Starlette application ready for uvicorn

    Raises:
        ValueError: If transport.type is not "streamable-http"
        RuntimeError: If app initialization fails

    Examples:
        Create Streamable HTTP app with CORS:
            >>> config = Config(
            ...     transport=TransportConfig(
            ...         type="streamable-http",
            ...         enable_cors=True,
            ...         allowed_origins=["https://app.example.com"],
            ...     )
            ... )
            >>> server = await create_server(config)
            >>> app = await create_http_app(server, config)

    Security:
        - CORS is disabled by default
        - Never use wildcard origins (*) in production
        - MCP SDK security settings are automatically applied

    See Also:
        - ServerLifecycleManager: Lifecycle management
        - SecurityHeadersMiddleware: Security headers
        - RequestIDMiddleware: Request ID tracking
    """
    factory_class = TRANSPORT_FACTORIES.get(config.transport.type)
    if not factory_class:
        raise ValueError(
            f"Unknown transport type: {config.transport.type}. "
            f"Available: {list(TRANSPORT_FACTORIES.keys())}"
        )

    factory = factory_class()
    app = await factory.create_app(server, config)

    logger.info(
        f"HTTP app created for {config.transport.type} transport",
        extra={
            "extra_fields": {
                "transport": config.transport.type,
                "host": config.transport.host,
                "port": config.transport.port,
            }
        },
    )

    return app
