"""HTTP middleware for security, logging, and request tracking."""

import logging
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all HTTP responses.

    Headers added:
        - X-Content-Type-Options: nosniff (prevent MIME sniffing)
        - X-Frame-Options: DENY (prevent clickjacking)
        - X-XSS-Protection: 1; mode=block (XSS protection)
        - Content-Security-Policy: Strict CSP
        - Strict-Transport-Security: HSTS for HTTPS
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Add security headers to response.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler

        Returns:
            Response with security headers
        """
        response = await call_next(request)

        # Prevent MIME sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # XSS protection (legacy but still useful)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Content Security Policy (strict)
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        )

        # Only add HSTS if using HTTPS
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Add request ID to all requests for tracing.

    Implements request ID tracking for distributed tracing.

    Features:
        - Generates UUID for each request
        - Accepts X-Request-ID header from client
        - Stores in request.state for handlers
        - Adds to response headers
        - Logs all requests with ID
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Add request ID and log request.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler

        Returns:
            Response with X-Request-ID header
        """
        # Generate or extract request ID
        # Validate client-provided request ID to ensure it's a valid UUID
        # This prevents injection of arbitrary strings into logs
        client_request_id = request.headers.get("X-Request-ID")
        if client_request_id:
            try:
                # Validate UUID format (raises ValueError if invalid)
                uuid.UUID(client_request_id)
                request_id = client_request_id
            except ValueError:
                # Invalid format, generate new one and log warning
                logger.debug(
                    f"Invalid X-Request-ID format received: {client_request_id[:50]}, generating new ID"
                )
                request_id = str(uuid.uuid4())
        else:
            request_id = str(uuid.uuid4())

        # Store in request state for handlers
        request.state.request_id = request_id

        # Process request
        try:
            response = await call_next(request)

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            # Log successful request
            logger.info(
                "HTTP request processed",
                extra={
                    "extra_fields": {
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                    }
                },
            )

            return response

        except Exception as e:
            # Log failed request
            logger.error(
                f"Request failed: {e}",
                extra={
                    "extra_fields": {
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                    }
                },
                exc_info=True,
            )
            raise


async def error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global error handler for HTTP transport.

    Structured error responses with HTTP status mapping.

    Args:
        request: HTTP request that caused error
        exc: Exception that was raised

    Returns:
        JSON error response with appropriate status code
    """
    from starlette.exceptions import HTTPException

    from fathom_mcp.errors import McpError

    # Get request ID if available
    request_id = getattr(request.state, "request_id", None)

    # Handle MCP errors with structured response
    if isinstance(exc, McpError):
        logger.warning(
            f"MCP error: {exc.code} - {exc.message}",
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "error_code": exc.code.value,
                    "retry_able": exc.retry_able,
                }
            },
        )

        return JSONResponse(
            status_code=exc.http_status,
            content={
                "error": {
                    "code": exc.code.value,
                    "message": exc.message,
                    "category": exc.category.value,
                    "retry_able": exc.retry_able,
                    "request_id": request_id,
                }
            },
        )

    # Handle Starlette HTTP exceptions
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": "HTTP_ERROR",
                    "message": exc.detail,
                    "request_id": request_id,
                }
            },
        )

    # Handle unexpected errors (don't leak details)
    logger.error(
        f"Unexpected error: {exc}",
        extra={"extra_fields": {"request_id": request_id}},
        exc_info=True,
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "request_id": request_id,
            }
        },
    )
