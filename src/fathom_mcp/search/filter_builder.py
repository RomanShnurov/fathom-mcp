"""Builder for ugrep filter command-line arguments.

This module constructs --filter arguments programmatically instead of using
a .ugrep configuration file, providing better transparency and cross-platform
compatibility.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import Config

logger = logging.getLogger(__name__)


class FilterArgumentsBuilder:
    """Constructs ugrep filter arguments programmatically.

    This class converts format configurations into command-line arguments
    that can be passed directly to ugrep, avoiding the need for external
    configuration files.

    Example:
        >>> builder = FilterArgumentsBuilder(config)
        >>> args = builder.build_filter_args()
        >>> # Returns: ['--filter=pdf:pdftotext % -', '--filter=docx:pandoc ...']
    """

    def __init__(self, config: "Config"):
        """Initialize the filter arguments builder.

        Args:
            config: Server configuration with format definitions
        """
        self.config = config

    def build_filter_args(self) -> list[str]:
        """Build --filter arguments for all enabled formats.

        Constructs ugrep --filter arguments in the format:
            --filter=extensions:command

        Where:
        - extensions: Comma-separated list without dots (e.g., "pdf,PDF")
        - command: Shell command with % placeholder for filename

        Returns:
            List of --filter arguments ready for ugrep command line

        Example:
            >>> builder.build_filter_args()
            ['--filter=pdf:pdftotext % -',
             '--filter=docx:pandoc --wrap=preserve -f docx -t plain % -o -']
        """
        filter_args = []

        for fmt_name, fmt_config in self.config.formats.items():
            # Skip disabled formats or formats without filters
            if not fmt_config.enabled or not fmt_config.filter:
                continue

            # Build extension list (remove leading dots)
            # Example: [".pdf", ".PDF"] -> "pdf,PDF"
            exts = ",".join(ext.lstrip(".") for ext in fmt_config.extensions)

            # Build filter specification: "extensions:command"
            # Example: "pdf:pdftotext % -"
            filter_spec = f"{exts}:{fmt_config.filter}"

            # Add as --filter argument
            # Note: We don't quote the entire filter_spec here because ugrep
            # expects it as a single argument after --filter=
            # The shlex.quote() is applied at subprocess level if needed
            filter_args.append(f"--filter={filter_spec}")

            logger.debug(f"Added filter for {fmt_name}: {filter_spec}")

        return filter_args

    def get_filter_extensions(self) -> list[str]:
        """Get list of all file extensions that have filters.

        Returns:
            List of extensions with filters (including leading dot)

        Example:
            >>> builder.get_filter_extensions()
            ['.pdf', '.docx', '.odt']
        """
        extensions = []
        for fmt_config in self.config.formats.values():
            if fmt_config.enabled and fmt_config.filter:
                extensions.extend(fmt_config.extensions)
        return extensions

    def has_filters(self) -> bool:
        """Check if any filters are configured.

        Returns:
            True if at least one format has a filter enabled
        """
        return any(fmt.enabled and fmt.filter is not None for fmt in self.config.formats.values())

    def validate_filters(self) -> dict[str, bool]:
        """Validate all filter commands against security policy.

        Returns:
            Dictionary mapping format names to validation status

        Example:
            >>> builder.validate_filters()
            {'pdf': True, 'docx': True, 'word_doc': False}
        """
        from ..security import FilterSecurity

        filter_security = FilterSecurity(self.config)
        results = {}

        for fmt_name, fmt_config in self.config.formats.items():
            if not fmt_config.enabled or not fmt_config.filter:
                results[fmt_name] = True  # No filter = no validation needed
                continue

            is_valid = filter_security.validate_filter_command(fmt_config.filter)
            results[fmt_name] = is_valid

            if not is_valid:
                logger.warning(
                    f"Filter for {fmt_name} failed security validation: {fmt_config.filter}"
                )

        return results

    def get_filter_summary(self) -> str:
        """Get human-readable summary of configured filters.

        Returns:
            Multi-line string describing all configured filters

        Example:
            >>> print(builder.get_filter_summary())
            Configured document filters:
              - pdf (.pdf): pdftotext % -
              - docx (.docx): pandoc --wrap=preserve -f docx -t plain % -o -
        """
        lines = ["Configured document filters:"]

        for fmt_name, fmt_config in self.config.formats.items():
            if not fmt_config.enabled or not fmt_config.filter:
                continue

            exts = ", ".join(fmt_config.extensions)
            lines.append(f"  - {fmt_name} ({exts}): {fmt_config.filter}")

        if len(lines) == 1:
            lines.append("  (none)")

        return "\n".join(lines)
