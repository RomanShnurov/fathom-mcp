"""Structured logging configuration for production.

Provides JSON-formatted logging with request IDs for production environments
and human-readable logging for development.
"""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging.

    Formats log records as JSON objects for easy parsing by log aggregation
    systems like ELK, Datadog, or CloudWatch.

    Features:
        - ISO 8601 timestamps in UTC
        - Request ID injection from log record
        - Exception stack traces
        - Custom extra fields support
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Args:
            record: Log record to format

        Returns:
            JSON string with log data
        """
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add request_id if available (from RequestIDMiddleware)
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add custom fields from extra parameter
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        return json.dumps(log_data)


def setup_structured_logging(
    level: str = "INFO",
    use_json: bool = False,
) -> None:
    """Setup structured logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        use_json: Use JSON formatter for production (default: False)

    Examples:
        Development (human-readable):
            >>> setup_structured_logging("INFO", use_json=False)

        Production (JSON):
            >>> setup_structured_logging("INFO", use_json=True)
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Create console handler
    handler = logging.StreamHandler(sys.stdout)

    if use_json:
        # Production: JSON formatter
        handler.setFormatter(StructuredFormatter())
    else:
        # Development: Human-readable formatter
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)

    root_logger.addHandler(handler)

    # Log setup complete
    logger = logging.getLogger(__name__)
    logger.info(
        f"Logging configured: level={level}, structured={use_json}",
        extra={"extra_fields": {"log_level": level, "structured": use_json}},
    )
