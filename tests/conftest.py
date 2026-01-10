"""Shared pytest fixtures."""

import contextlib
import shutil
import tempfile
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from fathom_mcp.config import Config, KnowledgeConfig
from fathom_mcp.search.ugrep import UgrepEngine


@pytest.fixture
def temp_knowledge_dir() -> AsyncGenerator[Path, None]:
    """Create temporary knowledge directory with sample files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Create structure
        (root / "games").mkdir()
        (root / "games" / "coop").mkdir()
        (root / "sport").mkdir()

        # Create sample files
        (root / "games" / "Guide.md").write_text("# Game Guide\n\nWelcome to games!")
        (root / "games" / "coop" / "Gloomhaven.md").write_text(
            "# Gloomhaven\n\n## Movement\n\nYou can move up to your speed.\n\n"
            "## Attack\n\nRoll dice to attack."
        )
        (root / "sport" / "Football.md").write_text(
            "# Football Rules\n\n## Offside\n\nA player is offside if..."
        )

        yield root


@pytest.fixture
def config(temp_knowledge_dir: Path) -> Config:
    """Create config with temp directory."""
    return Config(knowledge=KnowledgeConfig(root=temp_knowledge_dir))


# ============================================================================
# Shared Fixtures
# ============================================================================


@pytest.fixture
def rich_knowledge_dir(temp_knowledge_dir: Path) -> Path:
    """Extend temp_knowledge_dir with additional test files."""
    root = temp_knowledge_dir

    # Ensure directories exist
    (root / "games").mkdir(exist_ok=True)
    (root / "games" / "coop").mkdir(exist_ok=True)
    (root / "sport").mkdir(exist_ok=True)

    # Create comprehensive test file with multiple concepts
    (root / "games" / "coop" / "Gloomhaven.md").write_text(
        "# Gloomhaven Rules\n\n"
        "## Movement\n\n"
        "Characters can move up to their movement value.\n"
        "Movement is affected by terrain and obstacles.\n"
        "Flying characters ignore terrain penalties during movement.\n\n"
        "## Attack\n\n"
        "Roll dice to attack enemies.\n"
        "Attack damage is modified by armor.\n"
        "Critical hits deal double damage.\n\n"
        "## Defense\n\n"
        "Armor reduces incoming damage.\n"
        "Shield cards provide extra defense.\n\n"
        "## Special Abilities\n\n"
        "Some characters have ranged attacks.\n"
        "Teleport allows you to move instantly.\n"
        "Healing restores hit points.\n"
    )

    # Create another test file
    (root / "games" / "Strategy.md").write_text(
        "# Game Strategy Guide\n\n"
        "## Combat Strategy\n\n"
        "Attack weak enemies first.\n"
        "Use healing wisely.\n\n"
        "## Movement Strategy\n\n"
        "Position is everything in combat.\n"
        "Flying units have mobility advantages.\n"
    )

    # Create a multi-line document for metadata tests
    (root / "sport" / "Rules.txt").write_text(
        "Line 1\n" * 100  # 100 lines
    )

    return root


@pytest.fixture
def rich_config(rich_knowledge_dir: Path) -> Config:
    """Create config with extended knowledge directory."""
    return Config(knowledge=KnowledgeConfig(root=rich_knowledge_dir))


@pytest.fixture
def search_engine(rich_config: Config) -> UgrepEngine:
    """Create UgrepEngine instance for extended tests."""
    return UgrepEngine(rich_config)


@pytest.fixture
def pdf_with_toc(rich_knowledge_dir: Path) -> Path:
    """Create a PDF file with table of contents for testing."""
    from pypdf import PdfWriter

    pdf_path = rich_knowledge_dir / "games" / "manual.pdf"

    writer = PdfWriter()

    # Add 3 pages
    for _i in range(3):
        writer.add_blank_page(width=612, height=792)

    # Add metadata
    writer.add_metadata({"/Title": "Game Manual", "/Author": "Test Author"})

    # Add bookmarks (TOC)
    writer.add_outline_item("Introduction", 0)
    writer.add_outline_item("Setup", 1)
    gameplay = writer.add_outline_item("Gameplay", 2)
    writer.add_outline_item("Combat", 2, parent=gameplay)

    with open(pdf_path, "wb") as f:
        writer.write(f)

    return pdf_path


# ============================================================================
# Week 3 Multi-Format Test Fixtures
# ============================================================================


@pytest.fixture
def test_documents(tmp_path: Path) -> Path:
    """Copy test documents to temp directory."""
    fixtures_dir = Path(__file__).parent / "fixtures" / "documents"

    if not fixtures_dir.exists():
        pytest.skip("Test documents not generated. Run tests/fixtures/generate_documents.py")

    # Copy to temp directory
    dest_dir = tmp_path / "documents"
    shutil.copytree(fixtures_dir, dest_dir)

    return dest_dir


@pytest.fixture
def docx_file(test_documents: Path) -> Path:
    """Path to sample DOCX file."""
    return test_documents / "sample.docx"


@pytest.fixture
def html_file(test_documents: Path) -> Path:
    """Path to sample HTML file."""
    return test_documents / "sample.html"


@pytest.fixture
def json_file(test_documents: Path) -> Path:
    """Path to sample JSON file."""
    return test_documents / "sample.json"


@pytest.fixture
def xml_file(test_documents: Path) -> Path:
    """Path to sample XML file."""
    return test_documents / "sample.xml"


@pytest.fixture
def csv_file(test_documents: Path) -> Path:
    """Path to sample CSV file."""
    return test_documents / "sample.csv"


@pytest.fixture
def markdown_file(test_documents: Path) -> Path:
    """Path to sample Markdown file."""
    return test_documents / "sample.md"


# ============================================================================
# MCP Integration Test Fixtures
# ============================================================================


@pytest.fixture
def server_params(rich_knowledge_dir: Path) -> StdioServerParameters:
    """Create StdioServerParameters for connecting to Fathom MCP server.

    Args:
        rich_knowledge_dir: Path to test knowledge directory

    Returns:
        Configured StdioServerParameters for MCP server connection
    """
    project_root = Path(__file__).parent.parent

    return StdioServerParameters(
        command="uv",
        args=["run", "fathom-mcp", "--root", str(rich_knowledge_dir)],
        cwd=str(project_root),
    )


@pytest_asyncio.fixture(scope="function")
async def mcp_session(server_params: StdioServerParameters) -> AsyncGenerator[ClientSession, None]:
    """Create and initialize MCP client session.

    This fixture automatically:
    - Starts the MCP server via stdio transport
    - Creates and initializes a ClientSession
    - Yields the session for test usage
    - Cleans up resources on test completion

    Args:
        server_params: Server connection parameters

    Yields:
        Initialized ClientSession ready for tool/resource/prompt calls

    Example:
        async def test_my_tool(mcp_session):
            result = await mcp_session.call_tool("list_collections", arguments={})
            assert result is not None

    Note:
        Suppresses anyio cancel scope errors during cleanup due to pytest-asyncio
        event loop management. This is a known limitation of nested async context
        managers with anyio TaskGroups.
    """
    try:
        async with stdio_client(server_params) as streams:
            read_stream, write_stream = streams
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                yield session
    except RuntimeError as e:
        # Suppress cancel scope errors during teardown
        if "cancel scope" not in str(e):
            raise


# ============================================================================
# HTTP Server Fixture
# ============================================================================


@pytest_asyncio.fixture(loop_scope="function")
async def http_server(tmp_path: Path, monkeypatch):
    """Start HTTP server in background for integration testing.

    Proper server lifecycle with health check wait.

    Yields:
        Dict with server URL and config
    """
    import asyncio

    import httpx
    import uvicorn

    from fathom_mcp.config import Config
    from fathom_mcp.server import create_server
    from fathom_mcp.transports import create_http_app

    # Setup test config
    knowledge_root = tmp_path / "knowledge"
    knowledge_root.mkdir()
    (knowledge_root / "test.md").write_text("# Test Document\n\nTest content")

    monkeypatch.setenv("FMCP_KNOWLEDGE__ROOT", str(knowledge_root))
    monkeypatch.setenv("FMCP_TRANSPORT__TYPE", "streamable-http")
    monkeypatch.setenv("FMCP_TRANSPORT__HOST", "127.0.0.1")
    monkeypatch.setenv("FMCP_TRANSPORT__PORT", "18765")

    config = Config()

    # Create server and app
    server = await create_server(config)
    app = await create_http_app(server, config)

    # Start uvicorn in background
    uvicorn_config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=18765,
        log_level="error",
    )
    uvicorn_server = uvicorn.Server(uvicorn_config)
    server_task = asyncio.create_task(uvicorn_server.serve())

    # Wait for server to be ready
    async def wait_for_server(timeout: float = 5.0) -> None:
        """Wait for server health check."""
        start = asyncio.get_event_loop().time()
        async with httpx.AsyncClient() as client:
            while True:
                try:
                    response = await client.get("http://127.0.0.1:18765/_health")
                    if response.status_code == 200:
                        return
                except httpx.ConnectError:
                    pass

                if asyncio.get_event_loop().time() - start > timeout:
                    raise TimeoutError("Server failed to start")

                await asyncio.sleep(0.1)

    try:
        await wait_for_server()
        yield {
            "url": "http://127.0.0.1:18765",
            "config": config,
        }
    finally:
        # Graceful shutdown
        uvicorn_server.should_exit = True
        try:
            await asyncio.wait_for(server_task, timeout=5.0)
        except TimeoutError:
            server_task.cancel()


# ============================================================================
# HTTP Client Fixtures
# ============================================================================


@pytest_asyncio.fixture(loop_scope="function")
async def http_client():
    """HTTP client with test timeouts.

    Reusable HTTP client for tests.
    """
    import httpx

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(10.0, connect=5.0),
        follow_redirects=True,
    ) as client:
        yield client


@pytest_asyncio.fixture(loop_scope="function")
async def mcp_http_session(http_server):
    """MCP ClientSession over HTTP transport.

    Pre-initialized MCP session for tests.

    Note: Uses manual context manager handling to avoid pytest-asyncio
    teardown issues with nested async context managers.
    """
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    url = f"{http_server['url']}/mcp"

    # Manually manage context managers to avoid teardown issues
    http_ctx = streamable_http_client(url)
    read, write, _get_session_id = await http_ctx.__aenter__()

    session_ctx = ClientSession(read, write)
    session = await session_ctx.__aenter__()
    await session.initialize()

    try:
        yield session
    finally:
        # Clean up in reverse order
        with contextlib.suppress(Exception):
            await session_ctx.__aexit__(None, None, None)
        with contextlib.suppress(Exception):
            await http_ctx.__aexit__(None, None, None)


# ============================================================================
# Async Cleanup Verification
# ============================================================================


@pytest_asyncio.fixture(autouse=True, loop_scope="function")
async def verify_no_leaked_tasks():
    """Ensure no async tasks leaked after each test.

    Catches resource leaks early.
    """
    import asyncio

    yield

    # Get all running tasks
    tasks = [t for t in asyncio.all_tasks() if not t.done()]

    # Exclude current task
    current_task = asyncio.current_task()
    tasks = [t for t in tasks if t != current_task]

    if tasks:
        # Cancel leaked tasks
        for task in tasks:
            task.cancel()

        # Wait for cancellation
        await asyncio.gather(*tasks, return_exceptions=True)

        # Fail test
        pytest.fail(f"Test leaked {len(tasks)} async tasks: {[t.get_name() for t in tasks]}")
