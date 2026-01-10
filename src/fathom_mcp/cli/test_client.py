"""Test client CLI for fathom-mcp connectivity and functional testing.

Usage:
    # Test stdio transport
    fathom-mcp-test --transport stdio --level basic

    # Test HTTP transport
    fathom-mcp-test --transport streamable-http \
        --url http://localhost:8765/mcp --level full
"""

import argparse
import asyncio
import logging
import sys
import time
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator
from pydantic_core import ValidationError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Exit Codes
# ============================================================================


class ExitCode(IntEnum):
    """Test client exit codes following POSIX conventions.

    Detailed exit codes for CI/CD integration.
    """

    SUCCESS = 0  # All tests passed
    TEST_FAILURES = 1  # Some tests failed
    FATAL_ERROR = 2  # Cannot connect or fatal error
    CONFIG_ERROR = 3  # Invalid configuration
    TIMEOUT_ERROR = 4  # Test timeout
    NETWORK_ERROR = 5  # Network/connection error
    PARTIAL_SUCCESS = 6  # Connectivity OK, but some tools failed


# ============================================================================
# Configuration
# ============================================================================


class TestClientConfig(BaseModel):
    """Test client configuration with Pydantic validation.

    Validates CLI arguments with helpful error messages.
    """

    transport: Literal["stdio", "streamable-http"]
    level: Literal["connectivity", "basic", "full"]

    # HTTP settings
    url: HttpUrl | None = None
    timeout: int = Field(default=30, ge=5, le=300)

    # Stdio settings
    command: str = "uv"
    args: list[str] = Field(default_factory=lambda: ["run", "fathom-mcp"])
    cwd: Path | None = None

    # Output
    verbose: bool = False

    @model_validator(mode="after")
    def validate_transport_requirements(self) -> "TestClientConfig":
        """Validate transport-specific requirements."""
        # Check URL requirement for HTTP transport
        if self.transport == "streamable-http" and self.url is None:
            raise ValueError(
                "--url is required for streamable-http transport. "
                "Example: --url http://localhost:8765/mcp"
            )

        # Warn if URL provided for stdio (will be ignored)
        if self.transport == "stdio" and self.url is not None:
            logger.warning("--url is ignored for stdio transport")

        # Check URL endpoint for streamable HTTP
        if self.url is not None and self.transport == "streamable-http":
            url_str = str(self.url)
            if not url_str.endswith("/mcp"):
                logger.warning(
                    f"Streamable HTTP URL should end with /mcp. Did you mean {url_str}/mcp?"
                )

        return self


# ============================================================================
# Test Results
# ============================================================================


@dataclass
class TestResult:
    """Test result with timing and error information."""

    name: str
    success: bool
    duration_ms: int
    error: str | None = None
    details: str | None = None


# ============================================================================
# Test Client
# ============================================================================


class MCPTestClient:
    """MCP test client with async resource management.

    Proper async context managers with guaranteed cleanup.
    Retry logic for transient failures.
    """

    def __init__(self, config: TestClientConfig):
        """Initialize test client.

        Args:
            config: Validated test configuration
        """
        self.config = config
        self.results: list[TestResult] = []
        self.mcp_session: Any = None  # ClientSession from mcp
        self.transport_context: AbstractAsyncContextManager[Any] | None = None

    async def __aenter__(self) -> "MCPTestClient":
        """Setup async resources."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Cleanup async resources with timeout."""
        await self.cleanup()

    async def cleanup(self) -> None:
        """Cleanup all async resources with timeout protection.

        Guaranteed cleanup even if resources hang.
        """
        # Cleanup MCP session
        if self.mcp_session:
            try:
                await asyncio.wait_for(
                    self.mcp_session.__aexit__(None, None, None),
                    timeout=5.0,
                )
                logger.debug("MCP session closed")
            except TimeoutError:
                logger.warning("MCP session cleanup timeout")
            except Exception as e:
                logger.error(f"Error cleaning up MCP session: {e}")
            finally:
                self.mcp_session = None

        # Cleanup transport context
        if self.transport_context:
            try:
                await asyncio.wait_for(
                    self.transport_context.__aexit__(None, None, None),
                    timeout=5.0,
                )
                logger.debug("Transport context closed")
            except TimeoutError:
                logger.warning("Transport context cleanup timeout")
            except Exception as e:
                logger.error(f"Error closing transport context: {e}")
            finally:
                self.transport_context = None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        reraise=True,
    )
    async def _connect(self) -> None:
        """Connect to server with retry logic.

        Automatic retry for transient connection failures.

        Raises:
            ConnectionError: If connection fails after retries
            TimeoutError: If connection times out
        """
        logger.info(f"Connecting to {self.config.transport} transport...")

        if self.config.transport == "stdio":
            await self._connect_stdio()
        elif self.config.transport == "streamable-http":
            await self._connect_streamable_http()

        logger.info("Connected successfully")

    async def _connect_stdio(self) -> None:
        """Connect via stdio transport."""
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        server_params = StdioServerParameters(
            command=self.config.command,
            args=self.config.args,
            cwd=str(self.config.cwd) if self.config.cwd else None,
        )

        # Keep the stdio context alive for the duration of testing
        self.transport_context = stdio_client(server_params)
        read, write = await self.transport_context.__aenter__()
        self.mcp_session = ClientSession(read, write)
        await self.mcp_session.__aenter__()

    async def _connect_streamable_http(self) -> None:
        """Connect via Streamable HTTP transport."""
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client

        # Keep the HTTP context alive for the duration of testing
        self.transport_context = streamable_http_client(str(self.config.url))
        read, write, _get_session_id = await self.transport_context.__aenter__()
        self.mcp_session = ClientSession(read, write)
        await self.mcp_session.__aenter__()

    async def run_tests(self) -> int:
        """Run test suite and return exit code.

        Returns detailed exit codes for different failure scenarios.

        Returns:
            Exit code indicating test results
        """
        try:
            # Connect with retry
            try:
                await self._connect()
            except TimeoutError:
                self._print_error("Connection timeout")
                return ExitCode.TIMEOUT_ERROR
            except (ConnectionError, OSError) as e:
                self._print_error(f"Network error: {e}")
                return ExitCode.NETWORK_ERROR

            # Run test suite based on level
            await self._run_test_suite()

            # Analyze results
            total = len(self.results)
            passed = sum(1 for r in self.results if r.success)
            failed = total - passed

            # Print summary
            self._print_summary()

            # Determine exit code
            if failed == 0:
                return ExitCode.SUCCESS

            # Check if connectivity passed
            connectivity_passed = any(r.name == "initialize" and r.success for r in self.results)

            if connectivity_passed and failed < total:
                self._print_warning("Connectivity OK, but some tools failed")
                return ExitCode.PARTIAL_SUCCESS

            if not connectivity_passed:
                self._print_error("Fatal: Cannot initialize MCP session")
                return ExitCode.FATAL_ERROR

            return ExitCode.TEST_FAILURES

        except Exception as e:
            self._print_error(f"Unexpected error: {e}")
            logger.exception("Unexpected error in test client")
            return ExitCode.FATAL_ERROR

    async def _run_test_suite(self) -> None:
        """Run tests based on configured level."""
        # Always test connectivity
        await self._test_initialize()

        # Basic level: add collection listing
        if self.config.level in ("basic", "full"):
            await self._test_list_tools()
            await self._test_list_collections()

        # Full level: add search
        if self.config.level == "full":
            await self._test_search_documents()

    async def _test_initialize(self) -> None:
        """Test MCP session initialization."""
        start = time.monotonic()

        try:
            result = await asyncio.wait_for(
                self.mcp_session.initialize(),
                timeout=self.config.timeout,
            )

            self.results.append(
                TestResult(
                    name="initialize",
                    success=True,
                    duration_ms=int((time.monotonic() - start) * 1000),
                    details=f"Server: {result.serverInfo.name} v{result.serverInfo.version}",
                )
            )

        except TimeoutError:
            self.results.append(
                TestResult(
                    name="initialize",
                    success=False,
                    duration_ms=int((time.monotonic() - start) * 1000),
                    error="Initialization timeout",
                )
            )

    async def _test_list_tools(self) -> None:
        """Test listing available tools."""
        start = time.monotonic()

        try:
            result = await self.mcp_session.list_tools()

            self.results.append(
                TestResult(
                    name="list_tools",
                    success=True,
                    duration_ms=int((time.monotonic() - start) * 1000),
                    details=f"Found {len(result.tools)} tools",
                )
            )

        except Exception as e:
            self.results.append(
                TestResult(
                    name="list_tools",
                    success=False,
                    duration_ms=int((time.monotonic() - start) * 1000),
                    error=str(e),
                )
            )

    async def _test_list_collections(self) -> None:
        """Test list_collections tool."""
        start = time.monotonic()

        try:
            await self.mcp_session.call_tool("list_collections", {})

            self.results.append(
                TestResult(
                    name="list_collections",
                    success=True,
                    duration_ms=int((time.monotonic() - start) * 1000),
                    details="Tool executed successfully",
                )
            )

        except Exception as e:
            self.results.append(
                TestResult(
                    name="list_collections",
                    success=False,
                    duration_ms=int((time.monotonic() - start) * 1000),
                    error=str(e),
                )
            )

    async def _test_search_documents(self) -> None:
        """Test search_documents tool."""
        start = time.monotonic()

        try:
            await self.mcp_session.call_tool(
                "search_documents",
                {"query": "test", "scope": "global"},
            )

            self.results.append(
                TestResult(
                    name="search_documents",
                    success=True,
                    duration_ms=int((time.monotonic() - start) * 1000),
                    details="Search executed successfully",
                )
            )

        except Exception as e:
            self.results.append(
                TestResult(
                    name="search_documents",
                    success=False,
                    duration_ms=int((time.monotonic() - start) * 1000),
                    error=str(e),
                )
            )

    def _print_summary(self) -> None:
        """Print test results summary."""
        print("\n" + "=" * 70)
        print("TEST RESULTS")
        print("=" * 70)

        for result in self.results:
            status = "✅ PASS" if result.success else "❌ FAIL"
            print(f"{status} {result.name} ({result.duration_ms}ms)")

            if result.details:
                print(f"     {result.details}")
            if result.error:
                print(f"     Error: {result.error}")

        print("=" * 70)
        passed = sum(1 for r in self.results if r.success)
        failed = len(self.results) - passed
        print(f"Passed: {passed}/{len(self.results)} | Failed: {failed}")
        print("=" * 70 + "\n")

    def _print_error(self, message: str) -> None:
        """Print error message."""
        print(f"❌ ERROR: {message}", file=sys.stderr)

    def _print_warning(self, message: str) -> None:
        """Print warning message."""
        print(f"⚠️  WARNING: {message}")


# ============================================================================
# CLI Entry Point
# ============================================================================


def main() -> int:
    """Main CLI entry point with Pydantic validation.

    Validates arguments before running tests.

    Returns:
        Exit code from test execution
    """
    parser = argparse.ArgumentParser(
        description="Test client for fathom-mcp connectivity and functionality",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test stdio transport
  fathom-mcp-test --transport stdio --level basic

  # Test HTTP transport
  fathom-mcp-test -t streamable-http -u http://localhost:8765/mcp -l full
        """,
    )

    parser.add_argument(
        "-t",
        "--transport",
        required=True,
        choices=["stdio", "streamable-http"],
        help="Transport type to test",
    )

    parser.add_argument(
        "-l",
        "--level",
        default="connectivity",
        choices=["connectivity", "basic", "full"],
        help="Test level (default: connectivity)",
    )

    parser.add_argument(
        "-u",
        "--url",
        help="Server URL for HTTP transports (e.g., http://localhost:8765/mcp)",
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Timeout per test in seconds (default: 30)",
    )

    parser.add_argument(
        "--command",
        default="uv",
        help="Command for stdio transport (default: uv)",
    )

    parser.add_argument(
        "--args",
        nargs="*",
        default=["run", "fathom-mcp"],
        help="Arguments for stdio command (default: run fathom-mcp)",
    )

    parser.add_argument(
        "--cwd",
        type=Path,
        help="Working directory for stdio transport",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose output",
    )

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="[%(levelname)s] %(message)s",
    )

    # Validate config with Pydantic
    try:
        config = TestClientConfig(**vars(args))
    except ValidationError as e:
        print("❌ Configuration error:", file=sys.stderr)
        for error in e.errors():
            field = " -> ".join(str(x) for x in error["loc"])
            print(f"  {field}: {error['msg']}", file=sys.stderr)
        return ExitCode.CONFIG_ERROR

    # Run tests
    async def run() -> int:
        async with MCPTestClient(config) as client:
            return await client.run_tests()

    return asyncio.run(run())


if __name__ == "__main__":
    sys.exit(main())
