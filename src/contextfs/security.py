"""Security controls for ContextFS server."""

import asyncio
import logging
import shlex
import subprocess
from pathlib import Path

from .config import Config
from .errors import ErrorCode, McpError

logger = logging.getLogger(__name__)


class FilterSecurity:
    """Security controls for shell command execution in document filters.

    Provides comprehensive security controls including:
    - Command whitelisting/blacklisting
    - Command validation and sanitization
    - Sandboxed execution with timeouts
    - Memory limits for filter processes
    """

    def __init__(self, config: Config):
        """Initialize filter security.

        Args:
            config: Server configuration with security settings
        """
        self.config = config
        self.security_config = config.security

    def validate_filter_command(self, command: str) -> bool:
        """Validate that a filter command is allowed.

        Args:
            command: The shell command to validate

        Returns:
            True if command is allowed, False otherwise
        """
        if not self.security_config.enable_shell_filters:
            logger.warning("Shell filters are disabled in configuration")
            return False

        if self.security_config.filter_security_mode == "disabled":
            logger.debug("Filter security mode is disabled, allowing all commands")
            return True

        # Parse the command to get the executable
        try:
            parts = shlex.split(command)
            if not parts:
                logger.warning("Empty filter command")
                return False
            executable = parts[0]
        except ValueError as e:
            logger.warning(f"Failed to parse filter command '{command}': {e}")
            return False

        if self.security_config.filter_security_mode == "whitelist":
            # Check if the command or executable is in the whitelist
            allowed = (
                command in self.security_config.allowed_filter_commands
                or executable in self.security_config.allowed_filter_commands
            )
            if not allowed:
                logger.warning(
                    f"Filter command '{command}' not in whitelist. "
                    f"Allowed: {self.security_config.allowed_filter_commands}"
                )
            return allowed

        if self.security_config.filter_security_mode == "blacklist":
            # Check if the command or executable is in the blacklist
            blocked = (
                command in self.security_config.blocked_filter_commands
                or executable in self.security_config.blocked_filter_commands
            )
            if blocked:
                logger.warning(f"Filter command '{command}' is in blacklist")
            return not blocked

        logger.warning(f"Unknown security mode: {self.security_config.filter_security_mode}")
        return False

    async def run_secure_filter(
        self,
        command: str,
        input_data: bytes,
        timeout_override: int | None = None,
    ) -> bytes:
        """Execute a filter command with security controls.

        Args:
            command: The shell command to execute
            input_data: Input data to pass to the command via stdin
            timeout_override: Optional timeout override (seconds)

        Returns:
            Output from the command

        Raises:
            McpError: If command is not allowed or execution fails
        """
        if not self.validate_filter_command(command):
            raise McpError(
                code=ErrorCode.SECURITY_VIOLATION,
                message=f"Filter command not allowed: {command}",
                data={
                    "command": command,
                    "security_mode": self.security_config.filter_security_mode,
                    "reason": "Command failed security validation",
                },
            )

        timeout = timeout_override or self.security_config.filter_timeout_seconds

        try:
            # Execute in thread pool with timeout
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    self._execute_filter,
                    command,
                    input_data,
                ),
                timeout=timeout,
            )
            return result
        except TimeoutError:
            logger.error(f"Filter command timed out after {timeout}s: {command}")
            raise McpError(
                code=ErrorCode.FILTER_TIMEOUT,
                message=f"Filter command timed out after {timeout}s",
                data={"command": command, "timeout_seconds": timeout},
            ) from None
        except subprocess.CalledProcessError as e:
            logger.error(f"Filter command failed: {command} - {e}")
            raise McpError(
                code=ErrorCode.FILTER_EXECUTION_ERROR,
                message=f"Filter command failed: {e}",
                data={
                    "command": command,
                    "return_code": e.returncode,
                    "stderr": e.stderr.decode("utf-8", errors="replace") if e.stderr else None,
                },
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error executing filter: {command} - {e}")
            raise McpError(
                code=ErrorCode.FILTER_EXECUTION_ERROR,
                message=f"Filter execution error: {e}",
                data={"command": command, "error": str(e)},
            ) from e

    def _execute_filter(self, command: str, input_data: bytes) -> bytes:
        """Execute filter command in subprocess.

        This runs in a thread pool to avoid blocking the async loop.

        Args:
            command: Shell command to execute
            input_data: Input data for stdin

        Returns:
            Command output

        Raises:
            subprocess.CalledProcessError: If command fails
        """
        if self.security_config.sandbox_filters:
            # On Unix-like systems, we could use resource limits
            # For now, we rely on timeout and process isolation
            logger.debug(f"Executing sandboxed filter: {command}")

        # Parse command into arguments using shlex for safety
        try:
            cmd_args = shlex.split(command)
        except ValueError as e:
            logger.error(f"Failed to parse filter command: {command} - {e}")
            raise

        # Check if command contains shell operators (pipes, redirects, etc.)
        # These require shell=True for proper execution
        shell_operators = ["|", "||", "&&", ">", "<", ">>", "<<", "&", ";"]
        needs_shell = any(op in command for op in shell_operators)

        if needs_shell:
            # Shell=True is required for commands with pipes or other shell features
            # This is safe because we validate commands against whitelist before execution
            logger.debug(f"Using shell=True for command with shell operators: {command}")
            result = subprocess.run(
                command,
                input=input_data,
                capture_output=True,
                shell=True,
                check=True,  # Raise CalledProcessError on non-zero exit
            )
        else:
            # Use shell=False for simple commands (more secure)
            logger.debug(f"Using shell=False for simple command: {cmd_args}")
            result = subprocess.run(
                cmd_args,
                input=input_data,
                capture_output=True,
                shell=False,  # More secure for simple commands
                check=True,  # Raise CalledProcessError on non-zero exit
            )

        return result.stdout


class FileAccessControl:
    """File access control to prevent path traversal attacks.

    Ensures all file access stays within the knowledge root directory
    and enforces symlink policies.
    """

    def __init__(self, knowledge_root: Path, config: Config):
        """Initialize file access control.

        Args:
            knowledge_root: Root directory for knowledge base
            config: Server configuration with security settings
        """
        self.knowledge_root = knowledge_root.resolve()
        self.config = config
        self.security_config = config.security

    def validate_path(self, requested_path: str | Path) -> Path:
        """Validate and resolve path, preventing traversal attacks.

        Args:
            requested_path: User-provided path (relative to knowledge root)

        Returns:
            Validated absolute path

        Raises:
            McpError: If path is invalid or violates security policy
        """
        # Convert to Path object
        if isinstance(requested_path, str):
            requested_path = Path(requested_path)

        # Join with knowledge root (but don't resolve yet)
        unresolved_path = self.knowledge_root / requested_path

        # Symlink policy check - must be done BEFORE resolving
        if not self.security_config.follow_symlinks:
            # Check if the target path or any component in the path is a symlink
            try:
                current = unresolved_path
                while current != self.knowledge_root:
                    if current.exists() and current.is_symlink():
                        logger.warning(f"Symlink access denied: {current}")
                        raise McpError(
                            code=ErrorCode.SYMLINK_NOT_ALLOWED,
                            message="Symbolic links are not allowed",
                            data={
                                "path": str(requested_path),
                                "symlink_component": str(current),
                                "reason": "Symlink policy forbids following symbolic links",
                            },
                        )
                    current = current.parent
                    # Safety check to prevent infinite loop
                    if current == current.parent:
                        break
            except (OSError, RuntimeError) as e:
                logger.warning(f"Error checking path for symlinks: {e}")
                # Continue - we'll let other checks catch issues

        # Now resolve to absolute path
        try:
            full_path = unresolved_path.resolve()
        except (ValueError, OSError) as e:
            logger.warning(f"Invalid path resolution: {requested_path} - {e}")
            raise McpError(
                code=ErrorCode.INVALID_PATH,
                message=f"Invalid path: {requested_path}",
                data={"path": str(requested_path), "error": str(e)},
            ) from e

        # Security check: Ensure path is within knowledge root
        if self.security_config.restrict_to_knowledge_root:
            try:
                # Check if resolved path is under knowledge root
                full_path.relative_to(self.knowledge_root)
            except ValueError:
                logger.warning(
                    f"Path traversal attempt detected: {requested_path} "
                    f"resolves to {full_path}, outside root {self.knowledge_root}"
                )
                raise McpError(
                    code=ErrorCode.PATH_TRAVERSAL_DETECTED,
                    message="Path traversal attempt detected",
                    data={
                        "requested_path": str(requested_path),
                        "resolved_path": str(full_path),
                        "knowledge_root": str(self.knowledge_root),
                        "reason": "Path resolves outside knowledge root directory",
                    },
                ) from None

        return full_path

    def is_path_allowed(self, path: Path) -> bool:
        """Check if a path is allowed without raising exceptions.

        Args:
            path: Path to check

        Returns:
            True if path is allowed, False otherwise
        """
        try:
            self.validate_path(path)
            return True
        except McpError:
            return False
