"""Unit tests for test client."""

import pytest
from pydantic_core import ValidationError

from fathom_mcp.cli.test_client import ExitCode, TestClientConfig


def test_test_client_config_validation_missing_url():
    """Test that URL is required for HTTP transports.

    The model_validator now correctly enforces that URL must be provided
    for streamable-http transport at configuration time.
    """
    # Configuration should raise ValidationError when URL is missing for HTTP transport
    with pytest.raises(ValidationError) as exc_info:
        TestClientConfig(
            transport="streamable-http",
            level="connectivity",
        )

    # Verify the error message is helpful
    assert "--url is required for streamable-http transport" in str(exc_info.value)


def test_test_client_config_validation_valid():
    """Test valid test client configuration."""
    config = TestClientConfig(
        transport="streamable-http",
        level="connectivity",
        url="http://localhost:8765/mcp",
    )

    assert config.url is not None
    assert str(config.url) == "http://localhost:8765/mcp"


def test_test_client_config_url_ignored_for_stdio():
    """Test that URL is ignored for stdio transport."""
    config = TestClientConfig(
        transport="stdio",
        level="connectivity",
        url="http://localhost:8765",  # Should be ignored
    )

    assert config.transport == "stdio"


def test_exit_codes():
    """Test exit code values."""
    assert ExitCode.SUCCESS == 0
    assert ExitCode.TEST_FAILURES == 1
    assert ExitCode.FATAL_ERROR == 2
    assert ExitCode.CONFIG_ERROR == 3
    assert ExitCode.TIMEOUT_ERROR == 4
    assert ExitCode.NETWORK_ERROR == 5
    assert ExitCode.PARTIAL_SUCCESS == 6
