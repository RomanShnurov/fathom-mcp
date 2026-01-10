"""Docker healthcheck script for fathom-mcp.

Lightweight healthcheck for Docker containers running fathom-mcp server.
Supports both stdio and HTTP transports with appropriate checks.

Environment Variables:
    FMCP_TRANSPORT__TYPE: Transport type (stdio, streamable-http)
    FMCP_TRANSPORT__PORT: Server port for HTTP transport (default: 8765)
    FMCP_TRANSPORT__HEALTHCHECK_ENDPOINT: Health endpoint path (default: /_health)
    FMCP_HEALTHCHECK_TIMEOUT: HTTP request timeout in seconds (default: 2.5)
    FMCP_HEALTHCHECK_VERBOSE: Enable verbose logging (default: false)

Exit Codes:
    0: Healthy
    1: Unhealthy
    2: Configuration error

Usage:
    python healthcheck.py
"""

import logging
import os
import sys


# Configure logging (stderr for Docker visibility)
def setup_logging() -> logging.Logger:
    """Set up logging for healthcheck.

    Logs to stderr for Docker container visibility.
    Only logs warnings/errors by default (unless verbose mode enabled).

    Returns:
        Configured logger instance
    """
    verbose = os.getenv("FMCP_HEALTHCHECK_VERBOSE", "false").lower() in (
        "true",
        "1",
        "yes",
    )
    level = logging.INFO if verbose else logging.WARNING

    logging.basicConfig(
        level=level,
        format="%(asctime)s [HEALTHCHECK] %(levelname)s: %(message)s",
        stream=sys.stderr,
    )
    return logging.getLogger(__name__)


logger = setup_logging()


def check_stdio() -> bool:
    """Check stdio transport health (module import only).

    For stdio transport, we can only verify the module is importable.
    The actual server process runs as a subprocess of the MCP client
    (e.g., Claude Desktop), so we cannot directly check its health
    from a separate healthcheck process.

    This basic check ensures:
    - Python environment is correctly set up
    - Module is installed and importable
    - Core dependencies are available

    Returns:
        True if fathom_mcp module can be imported successfully
    """
    try:
        import fathom_mcp  # noqa: F401

        logger.info("fathom_mcp module imported successfully")
        return True
    except ImportError as e:
        logger.error(f"Failed to import fathom_mcp: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error importing fathom_mcp: {e}", exc_info=True)
        return False


def check_http() -> bool:
    """Check HTTP transport health via healthcheck endpoint.

    Sends GET request to the configured health endpoint and validates:
    - HTTP 200 status code
    - Response body indicates healthy status (if JSON)
    - Connection succeeds within timeout

    Returns:
        True if health endpoint returns 200 and server is healthy
    """
    # Check httpx availability
    try:
        import httpx
    except ImportError:
        logger.error(
            "httpx not installed - cannot check HTTP health. "
            "This should not happen in Docker container. "
            "Verify pyproject.toml includes httpx in dependencies."
        )
        return False

    # Get and validate port configuration
    try:
        port = int(os.getenv("FMCP_TRANSPORT__PORT", "8765"))
        if not (1024 <= port <= 65535):
            logger.error(f"Invalid port number: {port} (must be 1024-65535)")
            return False
    except ValueError as e:
        logger.error(f"Invalid port in FMCP_TRANSPORT__PORT: {e}")
        return False

    # Get health endpoint path (support customization)
    healthcheck_path = os.getenv("FMCP_TRANSPORT__HEALTHCHECK_ENDPOINT", "/_health")

    # Get timeout (faster timeout for healthcheck - default 2.5s)
    try:
        timeout = float(os.getenv("FMCP_HEALTHCHECK_TIMEOUT", "2.5"))
        if timeout <= 0 or timeout > 10:
            logger.warning(f"Invalid timeout {timeout}s, using default 2.5s")
            timeout = 2.5
    except ValueError:
        logger.warning("Invalid FMCP_HEALTHCHECK_TIMEOUT, using default 2.5s")
        timeout = 2.5

    # Build health URL (localhost since healthcheck runs inside container)
    health_url = f"http://localhost:{port}{healthcheck_path}"
    logger.info(f"Checking health at {health_url} (timeout={timeout}s)")

    # Perform health check with specific error handling
    try:
        response = httpx.get(health_url, timeout=timeout)

        if response.status_code != 200:
            logger.warning(
                f"Health endpoint returned {response.status_code}: {response.text[:200]}"
            )
            return False

        # Optional: Validate response body if JSON
        try:
            health_data = response.json()
            status = health_data.get("status", "unknown")

            if status != "healthy":
                logger.warning(f"Server reports unhealthy status: {status}")
                return False

            logger.info(f"Server is healthy: {health_data}")

        except Exception:
            # JSON parsing optional - 200 status is sufficient
            logger.debug("Health endpoint returned 200 (non-JSON response)")

        return True

    except httpx.TimeoutException:
        logger.warning(f"Health check timed out after {timeout}s")
        return False

    except httpx.ConnectError as e:
        logger.warning(f"Cannot connect to server at {health_url}: {e}")
        return False

    except httpx.HTTPStatusError as e:
        logger.warning(f"HTTP status error: {e}")
        return False

    except httpx.RequestError as e:
        logger.warning(f"Request error during health check: {e}")
        return False

    except OSError as e:
        logger.warning(f"OS error during health check: {e}")
        return False

    except Exception as e:
        # Unexpected error - log with traceback for debugging
        logger.error(f"Unexpected error during health check: {e}", exc_info=True)
        return False


def main() -> int:
    """Main healthcheck logic.

    Validates configuration and runs appropriate health check
    based on transport type.

    Returns:
        0 if healthy, 1 if unhealthy, 2 if configuration error
    """
    # Get transport type from environment
    transport_type = os.getenv("FMCP_TRANSPORT__TYPE", "stdio")

    # Validate transport type
    if transport_type not in ("stdio", "streamable-http"):
        logger.error(
            f"Invalid FMCP_TRANSPORT__TYPE: '{transport_type}'. "
            f"Must be 'stdio' or 'streamable-http'"
        )
        return 2

    logger.info(f"Checking health for transport: {transport_type}")

    # Run appropriate health check
    healthy = check_stdio() if transport_type == "stdio" else check_http()

    # Return exit code
    if healthy:
        logger.info("Health check PASSED")
        return 0
    else:
        logger.warning("Health check FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
