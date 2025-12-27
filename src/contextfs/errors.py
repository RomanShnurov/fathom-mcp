"""Error definitions for MCP server."""

from enum import Enum
from typing import Any


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
    """Base error with MCP-compatible response."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        data: dict[str, Any] | None = None,
    ):
        self.code = code
        self.message = message
        self.data = data or {}
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


# Convenience factory functions
def path_not_found(path: str) -> McpError:
    return McpError(
        code=ErrorCode.PATH_NOT_FOUND,
        message=f"Path not found: {path}",
        data={"path": path},
    )


def document_not_found(path: str, suggestions: list[str] | None = None) -> McpError:
    return McpError(
        code=ErrorCode.DOCUMENT_NOT_FOUND,
        message=f"Document not found: {path}",
        data={"path": path, "suggestions": suggestions or []},
    )


def search_timeout(query: str, timeout_sec: int) -> McpError:
    return McpError(
        code=ErrorCode.SEARCH_TIMEOUT,
        message=f"Search timed out after {timeout_sec}s",
        data={"query": query, "timeout_seconds": timeout_sec},
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
    )


def filter_execution_error(filename: str, filter_cmd: str, error: str) -> McpError:
    """Filter execution failed."""
    return McpError(
        ErrorCode.FILTER_EXECUTION_ERROR,
        f"Filter failed for {filename}: {filter_cmd} - {error}",
        data={"filename": filename, "filter_cmd": filter_cmd, "error": error},
    )
