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
        data={"details": details} if details else {},
    )


def file_too_large(path: str, size_mb: float, max_mb: int) -> McpError:
    return McpError(
        code=ErrorCode.FILE_TOO_LARGE,
        message=f"File too large: {size_mb:.1f}MB (max: {max_mb}MB)",
        data={"path": path, "size_mb": size_mb, "max_mb": max_mb},
    )
