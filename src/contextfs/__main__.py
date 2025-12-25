"""CLI entry point."""

import argparse
import asyncio
import logging
import sys

from .config import ConfigError, load_config
from .search.ugrep import check_ugrep_installed
from .server import run_server


def main() -> None:
    """Main entry point."""
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

    # Run server
    try:
        asyncio.run(run_server(config))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
