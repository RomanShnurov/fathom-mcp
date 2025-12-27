"""Filter tool validation for runtime detection."""

import asyncio
import logging
import shutil

from ..config import Config
from ..security import FilterSecurity

logger = logging.getLogger(__name__)


async def validate_filter_tools(config: Config) -> dict[str, bool]:
    """Validate that required filter tools are available and working.

    Auto-disables formats when tools are unavailable.

    Args:
        config: Server configuration

    Returns:
        Dict mapping format name to availability status
    """
    results = {}

    for fmt_name, fmt_config in config.formats.items():
        if not fmt_config.enabled or not fmt_config.filter:
            results[fmt_name] = True  # No tool needed
            continue

        # Extract tool name from filter command
        tool_name = fmt_config.filter.split()[0]

        # Check if tool exists in PATH
        if not shutil.which(tool_name):
            results[fmt_name] = False
            logger.warning(
                f"Filter tool '{tool_name}' for format '{fmt_name}' not found. "
                f"Disabling {fmt_name} support."
            )
            # Auto-disable format
            fmt_config.enabled = False
            continue

        # Test tool works with simple input
        try:
            filter_security = FilterSecurity(config)
            test_input = b"test"
            filter_cmd_stdin = config.prepare_filter_for_stdin(fmt_config.filter)

            await asyncio.wait_for(
                filter_security.run_secure_filter(
                    filter_cmd_stdin,
                    test_input,
                ),
                timeout=5,
            )
            results[fmt_name] = True
            logger.debug(f"Filter tool '{tool_name}' for format '{fmt_name}' validated")

        except Exception as e:
            logger.warning(
                f"Filter tool test failed for '{fmt_name}': {e}. Disabling {fmt_name} support."
            )
            fmt_config.enabled = False
            results[fmt_name] = False

    return results
