"""Unit tests for middleware."""

import uuid

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from fathom_mcp.middleware import (
    RequestIDMiddleware,
    SecurityHeadersMiddleware,
)


def test_security_headers_middleware():
    """Test that security headers are added."""

    async def homepage(request):
        return JSONResponse({"status": "ok"})

    app = Starlette(routes=[Route("/", homepage)])
    app.add_middleware(SecurityHeadersMiddleware)

    client = TestClient(app)
    response = client.get("/")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-XSS-Protection"] == "1; mode=block"


def test_request_id_middleware():
    """Test that request ID is added (CRITICAL #24)."""

    async def homepage(request):
        # Request ID should be in request.state
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse({"request_id": request_id})

    app = Starlette(routes=[Route("/", homepage)])
    app.add_middleware(RequestIDMiddleware)

    client = TestClient(app)
    response = client.get("/")

    # Check response header
    assert "X-Request-ID" in response.headers

    # Check response body
    data = response.json()
    assert data["request_id"] is not None
    assert data["request_id"] == response.headers["X-Request-ID"]


def test_request_id_middleware_accepts_valid_client_uuid():
    """Test that middleware accepts valid UUID from client."""

    async def homepage(request):
        return JSONResponse({"status": "ok"})

    app = Starlette(routes=[Route("/", homepage)])
    app.add_middleware(RequestIDMiddleware)

    client = TestClient(app)
    valid_uuid = str(uuid.uuid4())
    response = client.get("/", headers={"X-Request-ID": valid_uuid})

    # Should accept valid UUID from client
    assert response.headers["X-Request-ID"] == valid_uuid


def test_request_id_middleware_rejects_invalid_client_id():
    """Test that middleware rejects invalid UUID format and generates new one."""

    async def homepage(request):
        return JSONResponse({"status": "ok"})

    app = Starlette(routes=[Route("/", homepage)])
    app.add_middleware(RequestIDMiddleware)

    client = TestClient(app)
    invalid_id = "not-a-valid-uuid-123"
    response = client.get("/", headers={"X-Request-ID": invalid_id})

    # Should generate new UUID instead of using invalid one
    assert response.headers["X-Request-ID"] != invalid_id

    # Should be a valid UUID
    returned_id = response.headers["X-Request-ID"]
    try:
        uuid.UUID(returned_id)  # Should not raise
    except ValueError:
        pytest.fail(f"Response should contain valid UUID, got: {returned_id}")
