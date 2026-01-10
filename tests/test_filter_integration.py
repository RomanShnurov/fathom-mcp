"""Integration tests for filter arguments in search."""

import pytest

from fathom_mcp.config import Config, FormatConfig
from fathom_mcp.search.ugrep import UgrepEngine


@pytest.fixture
def config_with_pdf_filter(temp_knowledge_dir):
    """Config with PDF filter enabled."""
    return Config(
        knowledge={"root": temp_knowledge_dir},
        formats={
            "pdf": FormatConfig(
                extensions=[".pdf"],
                filter="pdftotext % -",
                enabled=True,
            ),
            "markdown": FormatConfig(
                extensions=[".md"],
                filter=None,
                enabled=True,
            ),
        },
    )


@pytest.fixture
def config_without_filters(temp_knowledge_dir):
    """Config without any filters."""
    return Config(
        knowledge={"root": temp_knowledge_dir},
        formats={
            "markdown": FormatConfig(
                extensions=[".md"],
                filter=None,
                enabled=True,
            ),
            "text": FormatConfig(
                extensions=[".txt"],
                filter=None,
                enabled=True,
            ),
        },
    )


@pytest.mark.asyncio
async def test_ugrep_engine_builds_filter_args(config_with_pdf_filter, temp_knowledge_dir):
    """Test that UgrepEngine correctly builds filter arguments."""
    engine = UgrepEngine(config_with_pdf_filter)

    # Build command for search
    cmd = engine._build_command(
        query="test",
        path=temp_knowledge_dir,
        recursive=True,
        context_lines=2,
        fuzzy=False,
    )

    # Should contain filter argument
    filter_args = [arg for arg in cmd if arg.startswith("--filter=")]
    assert len(filter_args) == 1
    assert "pdf:pdftotext % -" in filter_args[0]

    # Should not have --config argument (deprecated approach)
    config_args = [arg for arg in cmd if arg == "--config"]
    assert len(config_args) == 0


@pytest.mark.asyncio
async def test_ugrep_engine_without_filters(config_without_filters, temp_knowledge_dir):
    """Test that UgrepEngine works without filters."""
    engine = UgrepEngine(config_without_filters)

    # Build command for search
    cmd = engine._build_command(
        query="test",
        path=temp_knowledge_dir,
        recursive=True,
        context_lines=2,
        fuzzy=False,
    )

    # Should not contain filter arguments
    filter_args = [arg for arg in cmd if arg.startswith("--filter=")]
    assert len(filter_args) == 0


@pytest.mark.asyncio
async def test_search_integration_with_filters(config_with_pdf_filter, temp_knowledge_dir):
    """Test full search integration with filters."""
    # Create test markdown file
    test_file = temp_knowledge_dir / "test.md"
    test_file.write_text("This is a test document with searchable content.")

    engine = UgrepEngine(config_with_pdf_filter)

    # Search should work
    result = await engine.search(
        query="searchable",
        path=temp_knowledge_dir,
        recursive=True,
    )

    # Should find the match
    assert len(result.matches) >= 1
    assert any("searchable" in match.text.lower() for match in result.matches)


@pytest.mark.asyncio
async def test_multiple_filters_in_command(temp_knowledge_dir):
    """Test that multiple format filters are all included in command."""
    config = Config(
        knowledge={"root": temp_knowledge_dir},
        formats={
            "pdf": FormatConfig(
                extensions=[".pdf"],
                filter="pdftotext % -",
                enabled=True,
            ),
            "docx": FormatConfig(
                extensions=[".docx"],
                filter="pandoc --wrap=preserve -f docx -t plain % -o -",
                enabled=True,
            ),
            "odt": FormatConfig(
                extensions=[".odt"],
                filter="pandoc --wrap=preserve -f odt -t plain % -o -",
                enabled=True,
            ),
        },
    )

    engine = UgrepEngine(config)
    cmd = engine._build_command(
        query="test",
        path=temp_knowledge_dir,
        recursive=True,
        context_lines=2,
        fuzzy=False,
    )

    # Should have 3 filter arguments
    filter_args = [arg for arg in cmd if arg.startswith("--filter=")]
    assert len(filter_args) == 3

    # Check each filter is present
    filter_str = " ".join(filter_args)
    assert "pdf:pdftotext" in filter_str
    assert "docx:pandoc" in filter_str
    assert "odt:pandoc" in filter_str


def test_command_structure_with_filters(config_with_pdf_filter, temp_knowledge_dir):
    """Test the complete structure of ugrep command with filters."""
    engine = UgrepEngine(config_with_pdf_filter)

    cmd = engine._build_command(
        query="test query",
        path=temp_knowledge_dir,
        recursive=True,
        context_lines=5,
        fuzzy=True,
    )

    # Verify command structure
    assert cmd[0] == "ugrep"
    assert "-%" in cmd  # Boolean mode
    assert "-i" in cmd  # Case insensitive
    assert "-C5" in cmd  # Context lines
    assert "--line-number" in cmd
    assert "--with-filename" in cmd
    assert "-Z" in cmd  # Fuzzy mode
    assert "-r" in cmd  # Recursive

    # Filter should come before query
    filter_idx = next(i for i, arg in enumerate(cmd) if arg.startswith("--filter="))
    query_idx = cmd.index("test query")
    assert filter_idx < query_idx

    # Path should be last
    assert str(temp_knowledge_dir) == cmd[-1]


def test_command_structure_without_filters(config_without_filters, temp_knowledge_dir):
    """Test command structure when no filters are configured."""
    engine = UgrepEngine(config_without_filters)

    cmd = engine._build_command(
        query="test query",
        path=temp_knowledge_dir,
        recursive=True,
        context_lines=2,
        fuzzy=False,
    )

    # Should have basic structure
    assert cmd[0] == "ugrep"
    assert "-%" in cmd
    assert "-i" in cmd

    # Should NOT have filter arguments
    assert not any(arg.startswith("--filter=") for arg in cmd)

    # Query and path should still be present
    assert "test query" in cmd
    assert str(temp_knowledge_dir) == cmd[-1]


@pytest.mark.asyncio
async def test_filter_security_integration(temp_knowledge_dir):
    """Test that filter security validation is integrated."""
    from fathom_mcp.search.filter_builder import FilterArgumentsBuilder

    config = Config(
        knowledge={"root": temp_knowledge_dir},
        formats={
            "pdf": FormatConfig(
                extensions=[".pdf"],
                filter="pdftotext % -",
                enabled=True,
            ),
        },
    )

    builder = FilterArgumentsBuilder(config)

    # Validate filters against security policy
    results = builder.validate_filters()

    # PDF filter should pass validation (pdftotext is whitelisted)
    assert results["pdf"] is True

    # Validation should work without errors
    filter_args = builder.build_filter_args()
    assert len(filter_args) == 1
