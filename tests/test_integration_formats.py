"""Integration tests for multi-format support with real tools."""

import shutil
from pathlib import Path

import pytest
from tenacity import retry, stop_after_attempt, wait_fixed

from fathom_mcp.config import Config, KnowledgeConfig
from fathom_mcp.search.ugrep import UgrepEngine
from fathom_mcp.tools.read import handle_read_tool

# Check which tools are available
PANDOC_AVAILABLE = shutil.which("pandoc") is not None
JQ_AVAILABLE = shutil.which("jq") is not None
UG_AVAILABLE = shutil.which("ug") is not None or shutil.which("ugrep") is not None


@pytest.mark.integration
@pytest.mark.skipif(not PANDOC_AVAILABLE, reason="pandoc not installed")
@pytest.mark.asyncio
@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
async def test_read_docx_real(docx_file) -> None:
    """Integration test: Read real DOCX file with retry.

    Retries up to 3 times to handle flaky filter tool behavior.
    """
    config = Config(knowledge=KnowledgeConfig(root=docx_file.parent))
    config.formats["word_docx"].enabled = True

    # Read document
    result = await handle_read_tool("read_document", {"path": "sample.docx", "pages": []}, config)

    # Verify result
    assert len(result) > 0
    content = result[0].text

    # Parse JSON result
    import json

    data = json.loads(content)

    # Verify content
    assert len(data["content"]) > 0
    assert "searchable" in data["content"].lower()
    assert "machine learning" in data["content"].lower()


@pytest.mark.integration
@pytest.mark.skipif(not PANDOC_AVAILABLE, reason="pandoc not installed")
@pytest.mark.asyncio
async def test_read_html_real(html_file) -> None:
    """Integration test: Read real HTML file."""
    config = Config(knowledge=KnowledgeConfig(root=html_file.parent))
    config.formats["html"].enabled = True

    # Read document
    result = await handle_read_tool("read_document", {"path": "sample.html", "pages": []}, config)

    # Verify result
    assert len(result) > 0
    content = result[0].text

    # Parse JSON result
    import json

    data = json.loads(content)

    # Verify content
    assert len(data["content"]) > 0
    assert "Sample HTML Document" in data["content"] or "searchable" in data["content"].lower()


@pytest.mark.integration
@pytest.mark.skipif(not JQ_AVAILABLE, reason="jq not installed")
@pytest.mark.asyncio
async def test_read_json_real(json_file) -> None:
    """Integration test: Read real JSON file."""
    config = Config(knowledge=KnowledgeConfig(root=json_file.parent))
    config.formats["json"].enabled = True

    # Read document
    result = await handle_read_tool("read_document", {"path": "sample.json", "pages": []}, config)

    # Verify result
    assert len(result) > 0
    content = result[0].text

    # Parse JSON result
    import json

    data = json.loads(content)

    # Verify content
    assert len(data["content"]) > 0
    assert "Sample JSON Document" in data["content"] or "searchable" in data["content"].lower()


@pytest.mark.integration
@pytest.mark.skipif(not PANDOC_AVAILABLE, reason="pandoc not installed")
@pytest.mark.asyncio
async def test_get_docx_info_real(docx_file) -> None:
    """Integration test: Get DOCX document info."""
    config = Config(knowledge=KnowledgeConfig(root=docx_file.parent))
    config.formats["word_docx"].enabled = True

    # Get info
    result = await handle_read_tool("get_document_info", {"path": "sample.docx"}, config)

    # Verify result
    assert len(result) > 0
    content = result[0].text

    # Parse JSON result
    import json

    data = json.loads(content)

    # Verify
    assert data["name"] == "sample.docx"
    assert data["format"] == "docx"
    assert "filter" in data
    assert "pandoc" in data["filter"]


@pytest.mark.integration
@pytest.mark.skipif(
    not UG_AVAILABLE or not PANDOC_AVAILABLE, reason="ugrep or pandoc not installed"
)
@pytest.mark.asyncio
async def test_search_multiformat_real(test_documents) -> None:
    """Integration test: Search across multiple formats."""
    config = Config(knowledge=KnowledgeConfig(root=test_documents))
    config.formats["word_docx"].enabled = True
    config.formats["html"].enabled = True
    config.formats["json"].enabled = True

    # Create search engine
    engine = UgrepEngine(config)

    # Search for common keyword
    results = await engine.search(
        query="searchable",
        path=test_documents,
        recursive=True,
    )

    # Should find matches in multiple formats
    assert len(results.matches) > 0

    # Check we got matches from different file types
    file_types = {Path(match.file).suffix for match in results.matches}
    assert len(file_types) >= 2  # At least 2 different formats


@pytest.mark.integration
@pytest.mark.skipif(
    not UG_AVAILABLE or not PANDOC_AVAILABLE, reason="ugrep or pandoc not installed"
)
@pytest.mark.asyncio
async def test_boolean_search_multiformat(test_documents) -> None:
    """Integration test: Boolean search across formats."""
    config = Config(knowledge=KnowledgeConfig(root=test_documents))
    config.formats["word_docx"].enabled = True
    config.formats["html"].enabled = True

    engine = UgrepEngine(config)

    # Boolean AND query
    results = await engine.search(
        query="machine learning",
        path=test_documents,
        recursive=True,
    )

    # Should find matches
    assert len(results.matches) > 0

    # Verify match content
    for match in results.matches:
        content_lower = match.text.lower()
        assert "machine" in content_lower and "learning" in content_lower


@pytest.mark.integration
@pytest.mark.asyncio
async def test_read_csv_direct(csv_file) -> None:
    """Integration test: Read CSV file directly (no filter)."""
    config = Config(knowledge=KnowledgeConfig(root=csv_file.parent))
    config.formats["csv"].enabled = True

    # Read document
    result = await handle_read_tool("read_document", {"path": "sample.csv", "pages": []}, config)

    # Verify result
    assert len(result) > 0
    content = result[0].text

    # Parse JSON result
    import json

    data = json.loads(content)

    # Verify content
    assert len(data["content"]) > 0
    assert "searchable" in data["content"].lower()
    assert "machine learning" in data["content"].lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_read_markdown_direct(markdown_file) -> None:
    """Integration test: Read Markdown file directly (no filter)."""
    config = Config(knowledge=KnowledgeConfig(root=markdown_file.parent))
    config.formats["markdown"].enabled = True

    # Read document
    result = await handle_read_tool("read_document", {"path": "sample.md", "pages": []}, config)

    # Verify result
    assert len(result) > 0
    content = result[0].text

    # Parse JSON result
    import json

    data = json.loads(content)

    # Verify content
    assert len(data["content"]) > 0
    assert "searchable" in data["content"].lower()
    assert "Machine learning" in data["content"]
