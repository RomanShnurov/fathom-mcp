"""Unit tests for HTTP transports."""

import os

import pytest
from pydantic import ValidationError

from fathom_mcp.config import TransportConfig


def test_transport_config_defaults():
    """Test TransportConfig default values."""
    config = TransportConfig()

    assert config.type == "stdio"
    assert config.host == "127.0.0.1"
    assert config.port == 8765
    assert config.enable_cors is False
    assert config.allowed_origins == []


def test_transport_config_cors_wildcard_blocked_in_production():
    """Test that wildcard CORS is blocked in production (CRITICAL #7)."""
    os.environ["ENVIRONMENT"] = "production"

    with pytest.raises(ValidationError) as exc_info:
        TransportConfig(
            enable_cors=True,
            allowed_origins=["*"],
        )

    assert "FORBIDDEN in production" in str(exc_info.value)


def test_transport_config_cors_wildcard_allowed_in_development():
    """Test that wildcard CORS is allowed in development."""
    os.environ["ENVIRONMENT"] = "development"

    config = TransportConfig(
        enable_cors=True,
        allowed_origins=["*"],
    )

    assert "*" in config.allowed_origins


def test_transport_config_invalid_origin_format():
    """Test that invalid origin format is rejected."""
    with pytest.raises(ValidationError) as exc_info:
        TransportConfig(
            enable_cors=True,
            allowed_origins=["example.com"],  # Missing protocol
        )

    assert "must start with http://" in str(exc_info.value)


def test_transport_config_http_methods_validation():
    """Test HTTP methods validation."""
    with pytest.raises(ValidationError) as exc_info:
        TransportConfig(
            allowed_methods=["INVALID_METHOD"],
        )

    assert "Invalid HTTP method" in str(exc_info.value)


def test_transport_config_http_methods_normalization():
    """Test that HTTP methods are normalized to uppercase."""
    config = TransportConfig(
        allowed_methods=["get", "post", "options"],
    )

    assert config.allowed_methods == ["GET", "POST", "OPTIONS"]


@pytest.mark.asyncio
async def test_transport_factory_registry():
    """Test that transport factories are registered."""
    from fathom_mcp.transports import TRANSPORT_FACTORIES

    assert "sse" not in TRANSPORT_FACTORIES
    assert "streamable-http" in TRANSPORT_FACTORIES
    assert set(TRANSPORT_FACTORIES.keys()) == {"streamable-http"}
