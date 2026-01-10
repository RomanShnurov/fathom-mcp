"""Error definitions for MCP server."""

from enum import Enum
from typing import Any


class ErrorCategory(str, Enum):
    """Error categories for HTTP status code mapping.

    Used by HTTP transport to map MCP errors to appropriate HTTP responses.
    """

    CLIENT_ERROR = "client_error"  # 4xx - Client mistake
    SERVER_ERROR = "server_error"  # 5xx - Server problem
    TRANSIENT_ERROR = "transient"  # Temporary, retry-able
    FATAL_ERROR = "fatal"  # Permanent, non-retry-able


class ErrorCode(str, Enum):
    """Error codes following JSON-RPC conventions."""

    # JSON-RPC standard errors
    INVALID_PARAMS = "-32602"
    INTERNAL_ERROR = "-32603"

    # Knowledge base errors (1xxx)
    PATH_NOT_FOUND = "1001"
    DOCUMENT_NOT_FOUND = "1002"
    COLLECTION_NOT_FOUND = "1003"
    FORMAT_NOT_SUPPORTED = "1004"

    # Search errors (2xxx)
    SEARCH_TIMEOUT = "2001"
    SEARCH_ENGINE_ERROR = "2002"
    INVALID_QUERY = "2003"

    # Limit errors (4xxx)
    FILE_TOO_LARGE = "4001"
    RESULT_TRUNCATED = "4002"
    RATE_LIMITED = "4003"

    # Security errors (5xxx)
    SECURITY_VIOLATION = "5001"
    PATH_TRAVERSAL_DETECTED = "5002"
    SYMLINK_NOT_ALLOWED = "5003"
    INVALID_PATH = "5004"
    FILTER_TIMEOUT = "5005"
    FILTER_EXECUTION_ERROR = "5006"


class McpError(Exception):
    """Base MCP error with HTTP status code mapping.

    Adds HTTP status mapping and retry-ability indicator.

    Attributes:
        code: Error code (e.g., ErrorCode.DOCUMENT_NOT_FOUND)
        message: Human-readable error message
        category: Error category for HTTP mapping
        http_status: HTTP status code (for HTTP transport)
        retry_able: Whether error is transient and retry-able
        data: Additional error data
    """

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        data: dict[str, Any] | None = None,
        category: ErrorCategory = ErrorCategory.SERVER_ERROR,
        http_status: int = 500,
        retry_able: bool = False,
    ):
        self.code = code
        self.message = message
        self.data = data or {}
        self.category = category
        self.http_status = http_status
        self.retry_able = retry_able
        super().__init__(message)

    def to_response(self) -> dict[str, Any]:
        """Convert to MCP error response format."""
        return {
            "error": {
                "code": self.code.value,
                "message": self.message,
                "data": self.data,
            }
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert error to dictionary for JSON serialization.

        Returns:
            Dict with error details
        """
        return {
            "code": self.code.value,
            "message": self.message,
            "category": self.category.value,
            "retry_able": self.retry_able,
        }


# Convenience factory functions
def path_not_found(path: str) -> McpError:
    return McpError(
        code=ErrorCode.PATH_NOT_FOUND,
        message=f"Path not found: {path}",
        data={"path": path},
        category=ErrorCategory.CLIENT_ERROR,
        http_status=404,
        retry_able=False,
    )


def document_not_found(path: str, suggestions: list[str] | None = None) -> McpError:
    return McpError(
        code=ErrorCode.DOCUMENT_NOT_FOUND,
        message=f"Document not found: {path}",
        data={"path": path, "suggestions": suggestions or []},
        category=ErrorCategory.CLIENT_ERROR,
        http_status=404,
        retry_able=False,
    )


def search_timeout(query: str, timeout_sec: int) -> McpError:
    return McpError(
        code=ErrorCode.SEARCH_TIMEOUT,
        message=f"Search timed out after {timeout_sec}s",
        data={"query": query, "timeout_seconds": timeout_sec},
        category=ErrorCategory.TRANSIENT_ERROR,
        http_status=504,
        retry_able=True,
    )


def search_engine_error(message: str, details: str | None = None) -> McpError:
    return McpError(
        code=ErrorCode.SEARCH_ENGINE_ERROR,
        message=f"Search engine error: {message}",
        data={"details": details, "stderr": details} if details else {},
    )


def file_too_large(path: str, size_mb: float, max_mb: int) -> McpError:
    return McpError(
        code=ErrorCode.FILE_TOO_LARGE,
        message=f"File too large: {size_mb:.1f}MB (max: {max_mb}MB)",
        data={"path": path, "size_mb": size_mb, "max_mb": max_mb},
    )


def collection_not_found(path: str) -> McpError:
    """Collection not found error."""
    return McpError(
        code=ErrorCode.COLLECTION_NOT_FOUND,
        message=f"Collection not found: {path}",
        data={"path": path},
        category=ErrorCategory.CLIENT_ERROR,
        http_status=404,
        retry_able=False,
    )


def format_not_supported(path: str, format_ext: str, supported_formats: list[str]) -> McpError:
    """Format not supported error."""
    return McpError(
        code=ErrorCode.FORMAT_NOT_SUPPORTED,
        message=f"File format not supported: {format_ext}",
        data={
            "path": path,
            "format": format_ext,
            "supported_formats": supported_formats,
        },
    )


def invalid_query(query: str, reason: str) -> McpError:
    """Invalid search query error."""
    return McpError(
        code=ErrorCode.INVALID_QUERY,
        message=f"Invalid search query: {reason}",
        data={"query": query, "reason": reason},
    )


def rate_limited(retry_after_seconds: int) -> McpError:
    """Rate limited error."""
    return McpError(
        code=ErrorCode.RATE_LIMITED,
        message="Too many requests",
        data={"retry_after_seconds": retry_after_seconds},
    )


def filter_timeout(filename: str, timeout_seconds: int) -> McpError:
    """Filter execution timed out."""
    return McpError(
        ErrorCode.FILTER_TIMEOUT,
        f"Filter timeout reading {filename} (>{timeout_seconds}s)",
        data={"filename": filename, "timeout_seconds": timeout_seconds},
        category=ErrorCategory.TRANSIENT_ERROR,
        http_status=504,
        retry_able=True,
    )


def filter_execution_error(filename: str, filter_cmd: str, error: str) -> McpError:
    """Filter execution failed."""
    return McpError(
        ErrorCode.FILTER_EXECUTION_ERROR,
        f"Filter failed for {filename}: {filter_cmd} - {error}",
        data={"filename": filename, "filter_cmd": filter_cmd, "error": error},
        category=ErrorCategory.SERVER_ERROR,
        http_status=500,
        retry_able=False,
    )
