"""CLI entry point."""

import argparse
import asyncio
import contextlib
import logging
import os
import sys

from .config import Config, ConfigError, load_config
from .search.ugrep import check_ugrep_installed
from .server import run_server

logger = logging.getLogger(__name__)


def setup_event_loop() -> None:
    """Setup event loop with Windows compatibility.

    On Windows, uses WindowsProactorEventLoopPolicy for better
    subprocess and network support.

    Returns:
        None
    """
    if sys.platform == "win32":
        # Use ProactorEventLoop on Windows (default in 3.8+)
        # Fallback for older Python versions that don't have WindowsProactorEventLoopPolicy
        with contextlib.suppress(AttributeError):
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    # Set event loop for the main thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)


def validate_permissions(config: Config) -> None:
    """Validate runtime permissions.

    Check file access and port binding permissions.

    Args:
        config: Server configuration

    Raises:
        SystemExit: If permissions are insufficient
    """
    # Check knowledge root access
    if not os.access(config.knowledge.root, os.R_OK):
        logger.error(
            f"Cannot read knowledge root: {config.knowledge.root}. Check volume mount permissions."
        )
        sys.exit(1)

    # Security warning if running as root
    if hasattr(os, "getuid") and os.getuid() == 0:
        logger.warning(
            "⚠️  Running as root user. "
            "This is not recommended for security reasons. "
            "Consider using non-root user in production."
        )

    # Security warning for HTTP transport on 0.0.0.0 without authentication
    if config.transport.type == "streamable-http" and config.transport.host == "0.0.0.0":
        logger.warning(
            "\n"
            "═══════════════════════════════════════════════════════════════════════\n"
            "⚠️  SECURITY WARNING: HTTP server accessible from ALL network interfaces\n"
            "═══════════════════════════════════════════════════════════════════════\n"
            "\n"
            "Your MCP server is listening on 0.0.0.0 WITHOUT built-in authentication.\n"
            "This exposes your document collection to anyone who can reach this server.\n"
            "\n"
            "RECOMMENDED ACTIONS:\n"
            "  1. Use reverse proxy with authentication (Nginx, Caddy, Traefik)\n"
            "  2. Use VPN (Tailscale, WireGuard) to isolate network access\n"
            "  3. Change host to '127.0.0.1' for localhost-only access\n"
            "  4. Use 'stdio' transport for local AI agents (Claude Desktop)\n"
            "\n"
            "See docs/security.md for detailed setup instructions.\n"
            "═══════════════════════════════════════════════════════════════════════\n"
        )

    # Check port binding for HTTP transports
    if (
        config.transport.type == "streamable-http"
        and hasattr(os, "getuid")
        and config.transport.port < 1024
        and os.getuid() != 0
    ):
        logger.error(
            f"Cannot bind to privileged port {config.transport.port} "
            f"as non-root user. Use port >= 1024 or run as root (not recommended)."
        )
        sys.exit(1)


def main() -> None:
    """Main entry point."""
    setup_event_loop()

    parser = argparse.ArgumentParser(description="File-first knowledge base MCP server")
    parser.add_argument(
        "--config",
        "-c",
        help="Path to config.yaml",
        default=None,
    )
    parser.add_argument(
        "--root",
        "-r",
        help="Knowledge base root directory (overrides config)",
        default=None,
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=None,
        help="Log level (overrides config)",
    )

    args = parser.parse_args()

    # Check ugrep
    if not check_ugrep_installed():
        print("ERROR: ugrep is not installed.", file=sys.stderr)
        print(
            "Install with: apt install ugrep (Linux) or brew install ugrep (macOS)",
            file=sys.stderr,
        )
        sys.exit(1)

    # Load config
    try:
        # If --root provided without config, create minimal config
        if args.root and not args.config:
            from .config import Config, KnowledgeConfig

            config = Config(knowledge=KnowledgeConfig(root=args.root))
        else:
            config = load_config(args.config)
            # Override root if provided
            if args.root:
                config.knowledge.root = args.root
    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)

    # Override log level if provided
    log_level = args.log_level or config.server.log_level
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    validate_permissions(config)

    # Run server
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(run_server(config))


if __name__ == "__main__":
    main()
