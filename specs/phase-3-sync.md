# Phase 3: Cloud Sync

## Prerequisites

- Phase 1 & 2 completed
- rclone installed and configured on target system
- At least one rclone remote configured (e.g., `rclone config` → add Google Drive)

## Goals

1. **Sync tools** - manual sync from cloud storage
2. **Sync status** - check what's synced, what's pending
3. **Background sync** - optional auto-sync daemon

---

## Task 3.1: Configuration Extensions

### Update src/file_knowledge_mcp/config.py

```python
# Add to existing config.py

class RemoteConfig(BaseModel):
    """Single remote sync configuration."""

    rclone_remote: str  # e.g., "gdrive:MyKnowledge"
    local_path: str = ""  # relative to knowledge.root, "" = root
    auto_sync: bool = False  # sync on startup
    interval_minutes: int = Field(default=0, ge=0)  # 0 = manual only


class SyncConfig(BaseModel):
    """Cloud sync configuration."""

    enabled: bool = False
    remotes: dict[str, RemoteConfig] = Field(default_factory=dict)

    @property
    def has_remotes(self) -> bool:
        return bool(self.remotes)


# Update main Config class
class Config(BaseSettings):
    # ... existing fields ...

    sync: SyncConfig = Field(default_factory=SyncConfig)
```

### Example config.yaml with sync

```yaml
knowledge:
  root: "/data/knowledge"

# Sync configuration
sync:
  enabled: true
  remotes:
    # Google Drive remote
    gdrive:
      rclone_remote: "gdrive:Knowledge"  # rclone remote name:path
      local_path: ""                      # sync to root
      auto_sync: false                    # don't sync on startup
      interval_minutes: 0                 # manual sync only

    # Dropbox remote for specific collection
    dropbox-games:
      rclone_remote: "dropbox:BoardGames/Rules"
      local_path: "games"                 # sync to knowledge/games/
      auto_sync: true                     # sync on startup
      interval_minutes: 30                # sync every 30 min
```

### Checklist

- [ ] Add RemoteConfig and SyncConfig to config.py
- [ ] Update config.example.yaml with sync section
- [ ] Validate rclone remote format
- [ ] Test config loading with sync enabled

---

## Task 3.2: Rclone Wrapper

### src/file_knowledge_mcp/sync/rclone.py

```python
"""Rclone subprocess wrapper."""

import asyncio
import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..errors import McpError, ErrorCode

logger = logging.getLogger(__name__)


class RcloneNotInstalledError(McpError):
    """Rclone is not installed."""

    def __init__(self):
        super().__init__(
            code=ErrorCode("3003"),
            message="rclone is not installed",
            data={"install_url": "https://rclone.org/install/"},
        )


class RcloneRemoteNotFoundError(McpError):
    """Rclone remote not configured."""

    def __init__(self, remote: str, available: list[str]):
        super().__init__(
            code=ErrorCode("3002"),
            message=f"Remote not found: {remote}",
            data={"remote": remote, "available_remotes": available},
        )


class RcloneError(McpError):
    """Rclone command failed."""

    def __init__(self, message: str, stderr: str | None = None):
        super().__init__(
            code=ErrorCode("3004"),
            message=f"rclone error: {message}",
            data={"stderr": stderr} if stderr else {},
        )


@dataclass
class SyncChange:
    """Single file change from sync."""

    path: str
    action: str  # "download", "upload", "delete"
    size_bytes: int = 0


@dataclass
class SyncResult:
    """Result of sync operation."""

    success: bool
    changes: list[SyncChange]
    stats: dict
    error: str | None = None


def check_rclone_installed() -> bool:
    """Check if rclone is available."""
    return shutil.which("rclone") is not None


async def get_configured_remotes() -> list[str]:
    """Get list of configured rclone remotes."""
    if not check_rclone_installed():
        raise RcloneNotInstalledError()

    result = await asyncio.to_thread(
        subprocess.run,
        ["rclone", "listremotes"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RcloneError("Failed to list remotes", result.stderr)

    # Parse output: each line is "remotename:"
    remotes = []
    for line in result.stdout.strip().split("\n"):
        if line.strip():
            remotes.append(line.strip().rstrip(":"))

    return remotes


class RcloneWrapper:
    """Wrapper for rclone operations."""

    def __init__(self, knowledge_root: Path):
        self.knowledge_root = knowledge_root
        self._sync_lock = asyncio.Lock()

    async def check_remote(self, remote: str) -> bool:
        """Check if remote is configured and accessible."""
        if not check_rclone_installed():
            raise RcloneNotInstalledError()

        remotes = await get_configured_remotes()
        remote_name = remote.split(":")[0]

        if remote_name not in remotes:
            raise RcloneRemoteNotFoundError(remote_name, remotes)

        return True

    async def sync(
        self,
        remote: str,
        local_path: str = "",
        dry_run: bool = False,
    ) -> SyncResult:
        """Sync from remote to local.

        Args:
            remote: rclone remote path (e.g., "gdrive:Knowledge")
            local_path: Local subdirectory (relative to knowledge root)
            dry_run: If True, only check what would change

        Returns:
            SyncResult with changes and stats
        """
        if not check_rclone_installed():
            raise RcloneNotInstalledError()

        local_dir = self.knowledge_root / local_path if local_path else self.knowledge_root

        # Ensure local directory exists
        local_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            "rclone",
            "sync",
            remote,
            str(local_dir),
            "--verbose",
            "--stats-one-line",
        ]

        if dry_run:
            cmd.append("--dry-run")

        logger.info(f"Running: {' '.join(cmd)}")

        async with self._sync_lock:  # Only one sync at a time
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout
            )

        if result.returncode != 0:
            return SyncResult(
                success=False,
                changes=[],
                stats={},
                error=result.stderr,
            )

        # Parse output for changes
        changes = self._parse_sync_output(result.stderr)
        stats = self._parse_stats(result.stderr)

        return SyncResult(
            success=True,
            changes=changes,
            stats=stats,
        )

    async def check_changes(self, remote: str, local_path: str = "") -> dict:
        """Check what would be synced without actually syncing.

        Returns dict with to_download, to_upload, to_delete lists.
        """
        if not check_rclone_installed():
            raise RcloneNotInstalledError()

        local_dir = self.knowledge_root / local_path if local_path else self.knowledge_root

        cmd = [
            "rclone",
            "check",
            remote,
            str(local_dir),
            "--one-way",  # Only check remote -> local
            "--combined", "-",  # Output differences to stdout
        ]

        result = await asyncio.to_thread(
            subprocess.run,
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )

        # Parse differences
        # Format: "= path" (match), "+ path" (only in remote), "- path" (only in local)
        to_download = []
        to_delete = []

        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue

            if line.startswith("+ "):
                to_download.append(line[2:])
            elif line.startswith("- "):
                to_delete.append(line[2:])

        return {
            "to_download": to_download,
            "to_delete": to_delete,
            "in_sync": result.returncode == 0 and not to_download and not to_delete,
        }

    def _parse_sync_output(self, stderr: str) -> list[SyncChange]:
        """Parse rclone verbose output for changes."""
        changes = []

        for line in stderr.split("\n"):
            # Look for lines like: "Copied: file.pdf"
            if ": Copied" in line:
                # Extract filename
                parts = line.split(":")
                if len(parts) >= 2:
                    filename = parts[0].strip()
                    changes.append(SyncChange(
                        path=filename,
                        action="download",
                    ))
            elif ": Deleted" in line:
                parts = line.split(":")
                if len(parts) >= 2:
                    filename = parts[0].strip()
                    changes.append(SyncChange(
                        path=filename,
                        action="delete",
                    ))

        return changes

    def _parse_stats(self, stderr: str) -> dict:
        """Parse rclone stats from output."""
        stats = {
            "files_transferred": 0,
            "bytes_transferred": 0,
            "duration_seconds": 0,
        }

        for line in stderr.split("\n"):
            if "Transferred:" in line:
                # Parse: "Transferred: 5 / 5, 100%, 1.2 MiB/s, ETA 0s"
                try:
                    parts = line.split(",")
                    if "/" in parts[0]:
                        count = parts[0].split(":")[1].strip().split("/")[0].strip()
                        stats["files_transferred"] = int(count)
                except (IndexError, ValueError):
                    pass

        return stats
```

### Checklist

- [ ] Create sync/rclone.py
- [ ] Test check_rclone_installed()
- [ ] Test get_configured_remotes()
- [ ] Test sync with dry_run=True
- [ ] Test actual sync
- [ ] Test check_changes()
- [ ] Handle rclone not installed gracefully

---

## Task 3.3: Sync Tools

### src/file_knowledge_mcp/tools/sync.py

```python
"""Sync tools for cloud storage integration."""

import logging
from mcp.server import Server
from mcp.types import Tool, TextContent

from ..config import Config
from ..sync.rclone import RcloneWrapper, check_rclone_installed

logger = logging.getLogger(__name__)


def register_sync_tools(server: Server, config: Config) -> None:
    """Register sync-related tools (only if sync is enabled)."""

    if not config.sync.enabled:
        logger.info("Sync tools disabled (sync.enabled=false)")
        return

    if not config.sync.has_remotes:
        logger.info("Sync tools disabled (no remotes configured)")
        return

    rclone = RcloneWrapper(config.knowledge.root)

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        tools = []

        # Only add sync tools if rclone is installed
        if check_rclone_installed():
            tools.extend([
                Tool(
                    name="get_sync_status",
                    description="""Get sync status for configured remotes.
Shows which remotes are configured and their last sync status.""",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                    },
                ),
                Tool(
                    name="check_remote_changes",
                    description="""Check what would be synced from a remote without actually syncing.
Returns lists of files to download/delete.""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "remote_name": {
                                "type": "string",
                                "description": "Name of configured remote",
                                "enum": list(config.sync.remotes.keys()),
                            },
                        },
                        "required": ["remote_name"],
                    },
                ),
                Tool(
                    name="sync_remote",
                    description="""Sync documents from a remote storage.
Downloads new/updated files from the remote to local knowledge base.""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "remote_name": {
                                "type": "string",
                                "description": "Name of configured remote",
                                "enum": list(config.sync.remotes.keys()),
                            },
                            "dry_run": {
                                "type": "boolean",
                                "description": "Preview changes without applying",
                                "default": False,
                            },
                        },
                        "required": ["remote_name"],
                    },
                ),
            ])

        return tools

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        if name == "get_sync_status":
            result = await _get_sync_status(config)
            return [TextContent(type="text", text=format_result(result))]

        elif name == "check_remote_changes":
            remote_name = arguments["remote_name"]
            result = await _check_remote_changes(config, rclone, remote_name)
            return [TextContent(type="text", text=format_result(result))]

        elif name == "sync_remote":
            remote_name = arguments["remote_name"]
            dry_run = arguments.get("dry_run", False)
            result = await _sync_remote(config, rclone, remote_name, dry_run)
            return [TextContent(type="text", text=format_result(result))]

        raise ValueError(f"Unknown tool: {name}")


async def _get_sync_status(config: Config) -> dict:
    """Get status of all configured remotes."""
    from ..sync.rclone import get_configured_remotes, check_rclone_installed

    status = {
        "rclone_installed": check_rclone_installed(),
        "sync_enabled": config.sync.enabled,
        "remotes": {},
    }

    if not status["rclone_installed"]:
        status["error"] = "rclone is not installed"
        return status

    available_remotes = await get_configured_remotes()

    for name, remote_config in config.sync.remotes.items():
        remote_name = remote_config.rclone_remote.split(":")[0]
        status["remotes"][name] = {
            "rclone_remote": remote_config.rclone_remote,
            "local_path": remote_config.local_path or "(root)",
            "auto_sync": remote_config.auto_sync,
            "interval_minutes": remote_config.interval_minutes,
            "remote_configured": remote_name in available_remotes,
        }

    return status


async def _check_remote_changes(
    config: Config,
    rclone: RcloneWrapper,
    remote_name: str,
) -> dict:
    """Check pending changes from remote."""
    if remote_name not in config.sync.remotes:
        return {"error": f"Remote not configured: {remote_name}"}

    remote_config = config.sync.remotes[remote_name]

    changes = await rclone.check_changes(
        remote=remote_config.rclone_remote,
        local_path=remote_config.local_path,
    )

    return {
        "remote_name": remote_name,
        "rclone_remote": remote_config.rclone_remote,
        **changes,
    }


async def _sync_remote(
    config: Config,
    rclone: RcloneWrapper,
    remote_name: str,
    dry_run: bool,
) -> dict:
    """Execute sync from remote."""
    if remote_name not in config.sync.remotes:
        return {"error": f"Remote not configured: {remote_name}"}

    remote_config = config.sync.remotes[remote_name]

    result = await rclone.sync(
        remote=remote_config.rclone_remote,
        local_path=remote_config.local_path,
        dry_run=dry_run,
    )

    return {
        "remote_name": remote_name,
        "rclone_remote": remote_config.rclone_remote,
        "dry_run": dry_run,
        "success": result.success,
        "changes": [
            {"path": c.path, "action": c.action}
            for c in result.changes
        ],
        "stats": result.stats,
        "error": result.error,
    }


def format_result(result: dict) -> str:
    import json
    return json.dumps(result, indent=2, ensure_ascii=False)
```

### Update tools/__init__.py

```python
# Add sync tools registration

from .sync import register_sync_tools

def register_all_tools(server: Server, config: Config) -> None:
    register_browse_tools(server, config)
    register_search_tools(server, config)
    register_read_tools(server, config)
    register_sync_tools(server, config)  # Add this
```

### Checklist

- [ ] Create tools/sync.py
- [ ] Register sync tools conditionally
- [ ] Test get_sync_status
- [ ] Test check_remote_changes
- [ ] Test sync_remote with dry_run
- [ ] Test actual sync
- [ ] Verify tools hidden when sync disabled

---

## Task 3.4: Background Sync (Optional)

### src/file_knowledge_mcp/sync/daemon.py

```python
"""Background sync daemon."""

import asyncio
import logging
from datetime import datetime
from typing import Callable

from ..config import Config
from .rclone import RcloneWrapper, SyncResult

logger = logging.getLogger(__name__)


class SyncDaemon:
    """Background sync daemon for auto-syncing remotes."""

    def __init__(
        self,
        config: Config,
        on_sync_complete: Callable[[str, SyncResult], None] | None = None,
    ):
        self.config = config
        self.rclone = RcloneWrapper(config.knowledge.root)
        self.on_sync_complete = on_sync_complete

        self._tasks: dict[str, asyncio.Task] = {}
        self._last_sync: dict[str, datetime] = {}
        self._running = False

    async def start(self) -> None:
        """Start background sync for all auto-sync remotes."""
        if not self.config.sync.enabled:
            logger.info("Sync daemon not starting (sync disabled)")
            return

        self._running = True

        for name, remote_config in self.config.sync.remotes.items():
            if remote_config.auto_sync and remote_config.interval_minutes > 0:
                task = asyncio.create_task(
                    self._sync_loop(name, remote_config.interval_minutes)
                )
                self._tasks[name] = task
                logger.info(
                    f"Started auto-sync for '{name}' "
                    f"every {remote_config.interval_minutes} minutes"
                )

            # Initial sync if auto_sync enabled
            if remote_config.auto_sync:
                asyncio.create_task(self._do_sync(name))

    async def stop(self) -> None:
        """Stop all background sync tasks."""
        self._running = False

        for name, task in self._tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            logger.info(f"Stopped auto-sync for '{name}'")

        self._tasks.clear()

    async def _sync_loop(self, remote_name: str, interval_minutes: int) -> None:
        """Sync loop for a single remote."""
        while self._running:
            await asyncio.sleep(interval_minutes * 60)

            if not self._running:
                break

            await self._do_sync(remote_name)

    async def _do_sync(self, remote_name: str) -> None:
        """Execute sync for a remote."""
        try:
            remote_config = self.config.sync.remotes[remote_name]

            logger.info(f"Auto-syncing '{remote_name}'...")

            result = await self.rclone.sync(
                remote=remote_config.rclone_remote,
                local_path=remote_config.local_path,
                dry_run=False,
            )

            self._last_sync[remote_name] = datetime.now()

            if result.success:
                logger.info(
                    f"Auto-sync '{remote_name}' complete: "
                    f"{len(result.changes)} changes"
                )
            else:
                logger.error(f"Auto-sync '{remote_name}' failed: {result.error}")

            if self.on_sync_complete:
                self.on_sync_complete(remote_name, result)

        except Exception as e:
            logger.exception(f"Auto-sync '{remote_name}' error: {e}")

    def get_status(self) -> dict:
        """Get daemon status."""
        return {
            "running": self._running,
            "active_tasks": list(self._tasks.keys()),
            "last_sync": {
                name: dt.isoformat()
                for name, dt in self._last_sync.items()
            },
        }
```

### Integration with server

```python
# In server.py

from .sync.daemon import SyncDaemon

async def run_server(config: Config) -> None:
    """Run server with optional sync daemon."""
    server = create_server(config)

    # Start sync daemon if configured
    daemon = None
    if config.sync.enabled:
        daemon = SyncDaemon(config)
        await daemon.start()

    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
    finally:
        if daemon:
            await daemon.stop()
```

### Checklist

- [ ] Create sync/daemon.py
- [ ] Integrate with server lifecycle
- [ ] Test auto-sync on startup
- [ ] Test interval-based sync
- [ ] Test graceful shutdown
- [ ] Add daemon status to get_sync_status tool

---

## Task 3.5: Error Codes for Sync

### Update src/file_knowledge_mcp/errors.py

```python
# Add sync-specific error codes

class ErrorCode(str, Enum):
    # ... existing codes ...

    # Sync errors (3xxx)
    SYNC_NOT_CONFIGURED = "3001"
    REMOTE_NOT_FOUND = "3002"
    RCLONE_NOT_INSTALLED = "3003"
    RCLONE_ERROR = "3004"
    SYNC_IN_PROGRESS = "3005"
    SYNC_TIMEOUT = "3006"
```

### Checklist

- [ ] Add sync error codes
- [ ] Use consistent error format
- [ ] Document error codes in README

---

## Completion Criteria

Phase 3 is complete when:

- [ ] Sync config section documented and working
- [ ] `get_sync_status` shows remote configuration
- [ ] `check_remote_changes` previews pending sync
- [ ] `sync_remote` downloads from cloud
- [ ] Dry-run mode works correctly
- [ ] Background sync daemon starts/stops cleanly
- [ ] Graceful handling when rclone not installed
- [ ] All sync features have tests
- [ ] README updated with sync documentation

---

## Usage Examples

### Check sync status

```
User: What's the sync status?
Agent: [calls get_sync_status]

Response:
{
  "rclone_installed": true,
  "sync_enabled": true,
  "remotes": {
    "gdrive": {
      "rclone_remote": "gdrive:Knowledge",
      "local_path": "(root)",
      "auto_sync": false,
      "interval_minutes": 0,
      "remote_configured": true
    }
  }
}
```

### Sync from Google Drive

```
User: Sync my documents from Google Drive
Agent: [calls check_remote_changes first]

Pending changes:
- New files: ["New Game Rules.pdf", "Updated FAQ.pdf"]
- Files to delete: []

Agent: [calls sync_remote with dry_run=false]

Sync complete:
- Downloaded: 2 files
- Deleted: 0 files
```
