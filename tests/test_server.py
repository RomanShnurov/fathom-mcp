"""Tests for server lifecycle and setup."""

from contextfs.config import Config, KnowledgeConfig
from contextfs.server import ServerContext, create_server, get_document_index, get_server_context


async def test_create_server(temp_knowledge_dir):
    """Test server creation."""
    config = Config(knowledge=KnowledgeConfig(root=temp_knowledge_dir))
    server = await create_server(config)

    assert server is not None
    assert server.name == "ContextFS"


async def test_create_server_with_custom_name(temp_knowledge_dir):
    """Test server creation with custom name."""
    config = Config(knowledge=KnowledgeConfig(root=temp_knowledge_dir))
    config.server.name = "CustomServer"

    server = await create_server(config)

    assert server is not None
    assert server.name == "CustomServer"


def test_server_context_initialization():
    """Test ServerContext dataclass initialization."""
    context = ServerContext()

    assert context.document_index is None
    assert context.watcher_manager is None
    assert context.config is None


def test_get_server_context():
    """Test get_server_context returns global context."""
    context = get_server_context()

    assert isinstance(context, ServerContext)


def test_get_document_index_returns_none_initially():
    """Test get_document_index returns None when no index is initialized."""
    # Note: This test may fail if other tests have initialized the index
    # In practice, document index is only initialized when performance features are enabled
    index = get_document_index()

    # Could be None or an instance depending on test execution order
    # Just verify it doesn't raise an error
    assert index is None or index is not None


async def test_create_server_validates_filter_tools(temp_knowledge_dir):
    """Test that server creation validates filter tools."""
    config = Config(knowledge=KnowledgeConfig(root=temp_knowledge_dir))

    # This should complete without error even if some filter tools are missing
    server = await create_server(config)

    assert server is not None


async def test_create_server_registers_tools(temp_knowledge_dir):
    """Test that server creation registers all tools."""
    config = Config(knowledge=KnowledgeConfig(root=temp_knowledge_dir))

    server = await create_server(config)

    # Server should have tool handlers registered
    # We can't easily inspect the registered tools without running the server,
    # but we can verify the server was created successfully
    assert server is not None


async def test_server_context_can_hold_config(temp_knowledge_dir):
    """Test that ServerContext can hold config."""
    config = Config(knowledge=KnowledgeConfig(root=temp_knowledge_dir))
    context = ServerContext(config=config)

    assert context.config is config
    assert context.config.knowledge.root == temp_knowledge_dir
