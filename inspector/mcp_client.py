"""MCP client wrapper for contextfs server."""

from __future__ import annotations

import asyncio
import io
import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, TextIO

import nest_asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Enable nested event loops for Streamlit compatibility
nest_asyncio.apply()

# Setup logging
logger = logging.getLogger("mcp_inspector")


@dataclass
class LogEntry:
    """A single log entry."""

    timestamp: datetime
    level: str
    source: str  # "client" or "server"
    message: str

    def format(self) -> str:
        ts = self.timestamp.strftime("%H:%M:%S.%f")[:-3]
        return f"[{ts}] [{self.level}] [{self.source}] {self.message}"


class LogCollector:
    """Collects logs from client and server."""

    def __init__(self, max_entries: int = 500):
        self.entries: list[LogEntry] = []
        self.max_entries = max_entries
        self._lock = threading.Lock()

    def add(self, level: str, source: str, message: str) -> None:
        entry = LogEntry(
            timestamp=datetime.now(),
            level=level,
            source=source,
            message=message,
        )
        with self._lock:
            self.entries.append(entry)
            if len(self.entries) > self.max_entries:
                self.entries = self.entries[-self.max_entries :]

    def client_log(self, level: str, message: str) -> None:
        self.add(level, "client", message)

    def server_log(self, message: str) -> None:
        # Parse log level from message if present
        level = "INFO"
        if "ERROR" in message or "error" in message.lower():
            level = "ERROR"
        elif "WARNING" in message or "warning" in message.lower():
            level = "WARN"
        elif "DEBUG" in message or "debug" in message.lower():
            level = "DEBUG"
        self.add(level, "server", message.strip())

    def get_all(self) -> list[LogEntry]:
        with self._lock:
            return list(self.entries)

    def clear(self) -> None:
        with self._lock:
            self.entries.clear()


# Global log collector
_log_collector = LogCollector()


def get_log_collector() -> LogCollector:
    """Get the global log collector."""
    return _log_collector


@dataclass
class ServerConfig:
    """Configuration for connecting to contextfs MCP server."""

    root_path: str
    command: str = "uv"
    working_dir: str = ""

    def __post_init__(self) -> None:
        if not self.working_dir:
            # Use the contextfs project directory
            self.working_dir = str(Path(__file__).parent.parent)

    @property
    def args(self) -> list[str]:
        return ["run", "contextfs", "--root", self.root_path]

    def to_params(self) -> StdioServerParameters:
        return StdioServerParameters(
            command=self.command,
            args=self.args,
            cwd=self.working_dir,
        )


@dataclass
class ToolInfo:
    """Information about an MCP tool."""

    name: str
    description: str
    schema: dict[str, Any]


@dataclass
class ResourceInfo:
    """Information about an MCP resource."""

    uri: str
    name: str
    description: str | None = None
    mime_type: str | None = None


@dataclass
class PromptInfo:
    """Information about an MCP prompt."""

    name: str
    description: str | None = None
    arguments: list[dict[str, Any]] = field(default_factory=list)


class MCPClientError(Exception):
    """Error during MCP client operation."""

    pass


class LogCapturingTextIO(io.TextIOBase):
    """TextIO wrapper that captures writes to LogCollector."""

    def __init__(self, collector: LogCollector):
        self.collector = collector
        self._buffer = ""

    def write(self, s: str) -> int:
        if not s:
            return 0

        # Buffer and process line by line
        self._buffer += s
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            if line.strip():
                self.collector.server_log(line)

        return len(s)

    def flush(self) -> None:
        # Flush remaining buffer
        if self._buffer.strip():
            self.collector.server_log(self._buffer)
            self._buffer = ""

    def readable(self) -> bool:
        return False

    def writable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return False


def _get_errlog() -> TextIO:
    """Get a TextIO that captures server logs."""
    return LogCapturingTextIO(get_log_collector())


async def _list_tools(config: ServerConfig) -> list[ToolInfo]:
    """Fetch all tools from MCP server."""
    collector = get_log_collector()
    collector.client_log("INFO", f"Connecting to server: {config.command} {' '.join(config.args)}")

    async with stdio_client(config.to_params(), errlog=_get_errlog()) as streams:
        read_stream, write_stream = streams
        collector.client_log("DEBUG", "Connection established, initializing session...")

        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            collector.client_log("DEBUG", "Session initialized, listing tools...")

            result = await session.list_tools()
            tools = [
                ToolInfo(
                    name=t.name,
                    description=t.description or "",
                    schema=t.inputSchema if hasattr(t, "inputSchema") else {},
                )
                for t in result.tools
            ]
            collector.client_log("INFO", f"Found {len(tools)} tools: {[t.name for t in tools]}")
            return tools


async def _call_tool(config: ServerConfig, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Call a tool and return the result."""
    collector = get_log_collector()
    collector.client_log("INFO", f"Calling tool: {name}")
    collector.client_log("DEBUG", f"Arguments: {json.dumps(args, ensure_ascii=False)}")

    async with stdio_client(config.to_params(), errlog=_get_errlog()) as streams:
        read_stream, write_stream = streams
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(name, arguments=args)

            # Parse TextContent result
            if result.content and len(result.content) > 0:
                content = result.content[0]
                if hasattr(content, "text"):
                    try:
                        parsed = json.loads(content.text)
                        collector.client_log("INFO", f"Tool {name} returned successfully")
                        collector.client_log(
                            "DEBUG",
                            f"Response preview: {content.text[:200]}..."
                            if len(content.text) > 200
                            else f"Response: {content.text}",
                        )
                        return parsed
                    except json.JSONDecodeError:
                        collector.client_log("WARN", "Response is not valid JSON")
                        return {"raw": content.text}

            collector.client_log("WARN", f"Empty or unexpected response from {name}")
            return {"raw": str(result)}


async def _list_resources(config: ServerConfig) -> list[ResourceInfo]:
    """Fetch all resources from MCP server."""
    collector = get_log_collector()
    collector.client_log("INFO", "Listing resources...")

    async with stdio_client(config.to_params(), errlog=_get_errlog()) as streams:
        read_stream, write_stream = streams
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.list_resources()
            resources = [
                ResourceInfo(
                    uri=str(r.uri),
                    name=r.name,
                    description=r.description if hasattr(r, "description") else None,
                    mime_type=r.mimeType if hasattr(r, "mimeType") else None,
                )
                for r in result.resources
            ]
            collector.client_log("INFO", f"Found {len(resources)} resources")
            return resources


async def _read_resource(config: ServerConfig, uri: str) -> str:
    """Read a resource content."""
    collector = get_log_collector()
    collector.client_log("INFO", f"Reading resource: {uri}")

    async with stdio_client(config.to_params(), errlog=_get_errlog()) as streams:
        read_stream, write_stream = streams
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.read_resource(uri)

            if result.contents and len(result.contents) > 0:
                content = result.contents[0]
                if hasattr(content, "text"):
                    collector.client_log("INFO", f"Resource read: {len(content.text)} chars")
                    return content.text

            collector.client_log("WARN", "Empty resource content")
            return str(result)


async def _list_prompts(config: ServerConfig) -> list[PromptInfo]:
    """Fetch all prompts from MCP server."""
    collector = get_log_collector()
    collector.client_log("INFO", "Listing prompts...")

    async with stdio_client(config.to_params(), errlog=_get_errlog()) as streams:
        read_stream, write_stream = streams
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.list_prompts()
            prompts = [
                PromptInfo(
                    name=p.name,
                    description=p.description if hasattr(p, "description") else None,
                    arguments=list(p.arguments) if hasattr(p, "arguments") and p.arguments else [],
                )
                for p in result.prompts
            ]
            collector.client_log("INFO", f"Found {len(prompts)} prompts")
            return prompts


async def _get_prompt(
    config: ServerConfig, name: str, args: dict[str, str]
) -> list[dict[str, Any]]:
    """Get a prompt with arguments."""
    collector = get_log_collector()
    collector.client_log("INFO", f"Getting prompt: {name}")

    async with stdio_client(config.to_params(), errlog=_get_errlog()) as streams:
        read_stream, write_stream = streams
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.get_prompt(name, arguments=args)

            messages = []
            for msg in result.messages:
                content_text = ""
                if hasattr(msg.content, "text"):
                    content_text = msg.content.text
                elif isinstance(msg.content, str):
                    content_text = msg.content
                messages.append({"role": msg.role, "content": content_text})

            collector.client_log("INFO", f"Prompt returned {len(messages)} messages")
            return messages


# Sync wrappers for Streamlit


def list_tools(config: ServerConfig) -> list[ToolInfo]:
    """Get list of available tools (sync wrapper)."""
    collector = get_log_collector()
    try:
        return asyncio.run(_list_tools(config))
    except Exception as e:
        collector.client_log("ERROR", f"Failed to list tools: {e}")
        raise MCPClientError(f"Failed to list tools: {e}") from e


def call_tool(config: ServerConfig, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Call a tool (sync wrapper)."""
    collector = get_log_collector()
    try:
        return asyncio.run(_call_tool(config, name, args))
    except Exception as e:
        collector.client_log("ERROR", f"Failed to call tool '{name}': {e}")
        raise MCPClientError(f"Failed to call tool '{name}': {e}") from e


def list_resources(config: ServerConfig) -> list[ResourceInfo]:
    """Get list of available resources (sync wrapper)."""
    collector = get_log_collector()
    try:
        return asyncio.run(_list_resources(config))
    except Exception as e:
        collector.client_log("ERROR", f"Failed to list resources: {e}")
        raise MCPClientError(f"Failed to list resources: {e}") from e


def read_resource(config: ServerConfig, uri: str) -> str:
    """Read a resource (sync wrapper)."""
    collector = get_log_collector()
    try:
        return asyncio.run(_read_resource(config, uri))
    except Exception as e:
        collector.client_log("ERROR", f"Failed to read resource '{uri}': {e}")
        raise MCPClientError(f"Failed to read resource '{uri}': {e}") from e


def list_prompts(config: ServerConfig) -> list[PromptInfo]:
    """Get list of available prompts (sync wrapper)."""
    collector = get_log_collector()
    try:
        return asyncio.run(_list_prompts(config))
    except Exception as e:
        collector.client_log("ERROR", f"Failed to list prompts: {e}")
        raise MCPClientError(f"Failed to list prompts: {e}") from e


def get_prompt(config: ServerConfig, name: str, args: dict[str, str]) -> list[dict[str, Any]]:
    """Get a prompt (sync wrapper)."""
    collector = get_log_collector()
    try:
        return asyncio.run(_get_prompt(config, name, args))
    except Exception as e:
        collector.client_log("ERROR", f"Failed to get prompt '{name}': {e}")
        raise MCPClientError(f"Failed to get prompt '{name}': {e}") from e
