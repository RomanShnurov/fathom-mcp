"""Tests for security error handling."""

from pathlib import Path

import pytest

from contextfs.config import Config, KnowledgeConfig, SecurityConfig
from contextfs.errors import ErrorCode, McpError
from contextfs.security import FileAccessControl, FilterSecurity


class TestFileAccessControlErrors:
    """Test FileAccessControl security errors."""

    def test_path_traversal_detected(self, temp_knowledge_dir: Path):
        """Test PATH_TRAVERSAL_DETECTED error (5002)."""
        config = Config(knowledge=KnowledgeConfig(root=temp_knowledge_dir))
        fac = FileAccessControl(temp_knowledge_dir, config)

        # Attempt to access outside knowledge root
        with pytest.raises(McpError) as exc_info:
            fac.validate_path("../../etc/passwd")

        assert exc_info.value.code == ErrorCode.PATH_TRAVERSAL_DETECTED
        assert "Path traversal attempt detected" in exc_info.value.message
        assert "requested_path" in exc_info.value.data
        # Path may be normalized on Windows, so just check it contains the path
        assert "etc" in exc_info.value.data["requested_path"]
        assert "passwd" in exc_info.value.data["requested_path"]

    def test_symlink_not_allowed(self, temp_knowledge_dir: Path):
        """Test SYMLINK_NOT_ALLOWED error (5003)."""
        config = Config(
            knowledge=KnowledgeConfig(root=temp_knowledge_dir),
            security=SecurityConfig(follow_symlinks=False),
        )
        fac = FileAccessControl(temp_knowledge_dir, config)

        # Create symlink
        target = temp_knowledge_dir / "test.txt"
        target.write_text("content")
        symlink = temp_knowledge_dir / "link.txt"
        try:
            symlink.symlink_to(target)
        except OSError:
            pytest.skip("Cannot create symlinks on this system")

        with pytest.raises(McpError) as exc_info:
            fac.validate_path("link.txt")

        assert exc_info.value.code == ErrorCode.SYMLINK_NOT_ALLOWED
        assert "Symbolic links are not allowed" in exc_info.value.message

    def test_invalid_path(self, temp_knowledge_dir: Path):
        """Test INVALID_PATH error (5004)."""
        import sys

        # Skip on Windows as null bytes are handled differently
        if sys.platform == "win32":
            pytest.skip("Null bytes in paths handled differently on Windows")

        config = Config(knowledge=KnowledgeConfig(root=temp_knowledge_dir))
        fac = FileAccessControl(temp_knowledge_dir, config)

        # Use invalid path with null bytes
        with pytest.raises(McpError) as exc_info:
            fac.validate_path("file\x00.txt")

        assert exc_info.value.code == ErrorCode.INVALID_PATH


class TestFilterSecurityErrors:
    """Test FilterSecurity errors."""

    def test_security_violation_blacklist(self, temp_knowledge_dir: Path):
        """Test SECURITY_VIOLATION error (5001) in blacklist mode."""
        config = Config(
            knowledge=KnowledgeConfig(root=temp_knowledge_dir),
            security=SecurityConfig(
                filter_security_mode="blacklist",
                blocked_filter_commands=["rm", "curl"],
            ),
        )
        fs = FilterSecurity(config)

        # validate_filter_command returns False, not raises error
        # We need to check it returns False
        assert not fs.validate_filter_command("rm -rf /")
        assert not fs.validate_filter_command("curl http://evil.com")

    def test_security_violation_whitelist(self, temp_knowledge_dir: Path):
        """Test SECURITY_VIOLATION error (5001) in whitelist mode."""
        config = Config(
            knowledge=KnowledgeConfig(root=temp_knowledge_dir),
            security=SecurityConfig(
                filter_security_mode="whitelist",
                allowed_filter_commands=["pdftotext - -"],
            ),
        )
        fs = FilterSecurity(config)

        # validate_filter_command returns False for non-whitelisted commands
        assert not fs.validate_filter_command("malicious-command")

    @pytest.mark.asyncio
    async def test_security_violation_raised(self, temp_knowledge_dir: Path):
        """Test SECURITY_VIOLATION error (5001) raised by run_secure_filter."""
        config = Config(
            knowledge=KnowledgeConfig(root=temp_knowledge_dir),
            security=SecurityConfig(
                filter_security_mode="whitelist",
                allowed_filter_commands=["pdftotext - -"],
            ),
        )
        fs = FilterSecurity(config)

        with pytest.raises(McpError) as exc_info:
            await fs.run_secure_filter("malicious-command", b"input")

        assert exc_info.value.code == ErrorCode.SECURITY_VIOLATION
        assert "Filter command not allowed" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_filter_timeout(self, temp_knowledge_dir: Path):
        """Test FILTER_TIMEOUT error (5005)."""
        # Skip on Windows as sleep command works differently
        import sys

        if sys.platform == "win32":
            pytest.skip("Sleep command not available on Windows in same way")

        config = Config(
            knowledge=KnowledgeConfig(root=temp_knowledge_dir),
            security=SecurityConfig(
                filter_security_mode="whitelist",
                allowed_filter_commands=["sleep 10", "sleep"],
                filter_timeout_seconds=1,  # 1 second
            ),
        )
        fs = FilterSecurity(config)

        with pytest.raises(McpError) as exc_info:
            await fs.run_secure_filter("sleep 10", b"input")

        assert exc_info.value.code == ErrorCode.FILTER_TIMEOUT
        assert "timed out" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_filter_execution_error(self, temp_knowledge_dir: Path):
        """Test FILTER_EXECUTION_ERROR error (5006)."""
        config = Config(
            knowledge=KnowledgeConfig(root=temp_knowledge_dir),
            security=SecurityConfig(
                filter_security_mode="whitelist",
                allowed_filter_commands=["nonexistent-command-12345"],
            ),
        )
        fs = FilterSecurity(config)

        with pytest.raises(McpError) as exc_info:
            await fs.run_secure_filter("nonexistent-command-12345", b"input")

        assert exc_info.value.code == ErrorCode.FILTER_EXECUTION_ERROR
