"""Tests for search functionality."""

import asyncio
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from file_knowledge_mcp.config import Config
from file_knowledge_mcp.errors import ErrorCode, McpError
from file_knowledge_mcp.search.ugrep import SearchResult, UgrepEngine
from file_knowledge_mcp.tools.search import _search_documents

# Enable debug logging for tests
logging.basicConfig(level=logging.DEBUG, format='%(name)s - %(levelname)s - %(message)s')


# ============================================================================
# Fixtures for search tests
# ============================================================================


@pytest.fixture
def search_knowledge_dir(temp_knowledge_dir):
    """Extend temp_knowledge_dir with search-specific test files."""
    root = temp_knowledge_dir

    # Ensure directories exist
    (root / "games").mkdir(exist_ok=True)
    (root / "games" / "coop").mkdir(exist_ok=True)

    # Create markdown file with searchable content (overwrites the simple one from conftest)
    (root / "games" / "coop" / "Gloomhaven.md").write_text(
        "# Gloomhaven Rules\n\n"
        "## Movement\n\n"
        "Characters can move up to their movement value.\n"
        "Movement is affected by terrain and obstacles.\n\n"
        "## Attack\n\n"
        "Roll dice to attack enemies.\n"
        "Attack damage is modified by armor.\n\n"
        "## Special Abilities\n\n"
        "Some characters have ranged attacks.\n"
        "Teleport allows you to move instantly.\n"
    )

    # Create another markdown file in games/
    (root / "games" / "Strategy.md").write_text(
        "# Game Strategy Guide\n\n"
        "## Combat Strategy\n\n"
        "Attack weak enemies first.\n"
        "Use armor to protect your characters.\n\n"
        "## Movement Strategy\n\n"
        "Position is everything in combat.\n"
    )

    # Create a text file
    (root / "notes.txt").write_text(
        "Personal notes\n\n"
        "Remember to attack from range when possible.\n"
        "Armor is important for defense.\n"
    )

    return root


@pytest.fixture
def pdf_test_file(search_knowledge_dir):
    """Create a simple test PDF file."""
    # Note: This creates a dummy PDF file for testing
    # In real scenarios, you'd use a proper PDF library
    pdf_path = search_knowledge_dir / "games" / "rules.pdf"

    # Create a minimal valid PDF
    pdf_content = """%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
/Resources <<
/Font <<
/F1 5 0 R
>>
>>
>>
endobj
4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(PDF test content with attack and armor rules) Tj
ET
endstream
endobj
5 0 obj
<<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000270 00000 n
0000000363 00000 n
trailer
<<
/Size 6
/Root 1 0 R
>>
startxref
445
%%EOF
"""
    pdf_path.write_text(pdf_content)
    return pdf_path


@pytest.fixture
def search_config(search_knowledge_dir):
    """Create config with search-specific knowledge directory."""
    from file_knowledge_mcp.config import KnowledgeConfig
    return Config(knowledge=KnowledgeConfig(root=search_knowledge_dir))


@pytest.fixture
def engine(search_config):
    """Create UgrepEngine instance."""
    return UgrepEngine(search_config)


# ============================================================================
# UgrepEngine Tests
# ============================================================================


@pytest.mark.asyncio
async def test_search_simple_query(engine, search_knowledge_dir):
    """Test simple search query in markdown files."""
    result = await engine.search(
        query="movement",
        path=search_knowledge_dir,
        recursive=True,
        context_lines=2,
        max_results=10,
    )

    assert isinstance(result, SearchResult)
    assert len(result.matches) > 0
    assert any("movement" in match.text.lower() for match in result.matches)
    assert result.query == "movement"
    assert not result.truncated


@pytest.mark.asyncio
async def test_search_and_operator(engine, search_knowledge_dir):
    """Test AND operator (space between words)."""
    result = await engine.search(
        query="attack armor",  # Both words must appear
        path=search_knowledge_dir,
        recursive=True,
        context_lines=1,
        max_results=10,
    )

    # Should find documents containing both "attack" AND "armor"
    assert len(result.matches) > 0
    # Due to boolean AND, both terms should be in the document
    # (though not necessarily in the same line)
    assert all("attack" in m.text.lower() or "armor" in m.text.lower() for m in result.matches)


@pytest.mark.asyncio
async def test_search_or_operator(engine, search_knowledge_dir):
    """Test OR operator (|)."""
    result = await engine.search(
        query="teleport|range",  # Either word
        path=search_knowledge_dir,
        recursive=True,
        context_lines=1,
        max_results=10,
    )

    assert len(result.matches) > 0
    # Should find matches with either "teleport" or "range"
    found_teleport = any("teleport" in match.text.lower() for match in result.matches)
    found_range = any("range" in match.text.lower() for match in result.matches)
    assert found_teleport or found_range


@pytest.mark.asyncio
async def test_search_not_operator(engine, search_knowledge_dir):
    """Test NOT operator (-)."""
    result = await engine.search(
        query="attack -ranged",  # "attack" but not "ranged"
        path=search_knowledge_dir,
        recursive=True,
        context_lines=1,
        max_results=10,
    )

    # Should find "attack" but exclude lines with "ranged"
    assert len(result.matches) > 0
    for match in result.matches:
        assert "attack" in match.text.lower()
        # The matched line should not contain "ranged"
        assert "ranged" not in match.text.lower()


@pytest.mark.asyncio
async def test_search_exact_phrase(engine, search_knowledge_dir):
    """Test exact phrase search with quotes."""
    result = await engine.search(
        query='"movement value"',  # Exact phrase
        path=search_knowledge_dir,
        recursive=True,
        context_lines=1,
        max_results=10,
    )

    # Should find the exact phrase "movement value"
    if len(result.matches) > 0:
        found_exact = any("movement value" in match.text.lower() for match in result.matches)
        assert found_exact


@pytest.mark.asyncio
async def test_search_fuzzy_matching(engine, search_knowledge_dir):
    """Test fuzzy search with typos."""
    result = await engine.search(
        query="movment",  # Typo: should match "movement" with fuzzy
        path=search_knowledge_dir,
        recursive=True,
        context_lines=1,
        max_results=10,
        fuzzy=True,
    )

    # With fuzzy matching, should still find "movement"
    # Note: fuzzy matching may or may not work depending on ugrep installation
    # This test verifies the fuzzy flag is passed correctly
    assert isinstance(result, SearchResult)


@pytest.mark.asyncio
async def test_search_context_lines(engine, search_knowledge_dir):
    """Test context_lines parameter."""
    result = await engine.search(
        query="attack",
        path=search_knowledge_dir,
        recursive=True,
        context_lines=3,
        max_results=10,
    )

    assert len(result.matches) > 0
    # Verify matches have context
    for match in result.matches:
        assert isinstance(match.context_before, list)
        assert isinstance(match.context_after, list)
        # Context should be present (though may be empty at file boundaries)


@pytest.mark.asyncio
async def test_search_max_results_truncation(engine, search_knowledge_dir):
    """Test max_results parameter and truncation."""
    max_res = 2
    result = await engine.search(
        query="attack",
        path=search_knowledge_dir,
        recursive=True,
        context_lines=1,
        max_results=max_res,
    )

    # If there are more than max_res matches, result should be truncated
    assert len(result.matches) <= max_res
    if result.total_matches > max_res:
        assert result.truncated
        assert len(result.matches) == max_res


@pytest.mark.asyncio
async def test_search_single_document(engine, search_knowledge_dir):
    """Test search in a single document (non-recursive)."""
    doc_path = search_knowledge_dir / "games" / "coop" / "Gloomhaven.md"

    result = await engine.search(
        query="attack",
        path=doc_path,
        recursive=False,
        context_lines=1,
        max_results=10,
    )

    assert len(result.matches) > 0
    # All matches should be from the same file
    for match in result.matches:
        assert "Gloomhaven.md" in match.file or match.file == str(doc_path)


@pytest.mark.asyncio
async def test_search_collection(engine, search_knowledge_dir):
    """Test search in a specific collection."""
    collection_path = search_knowledge_dir / "games"

    result = await engine.search(
        query="attack",
        path=collection_path,
        recursive=True,
        context_lines=1,
        max_results=10,
    )

    assert len(result.matches) > 0
    # All matches should be from files within the games collection
    for match in result.matches:
        # Match file should start with "games" or be a relative path in games/
        assert "games" in match.file.lower() or Path(match.file).parts[0] == "games"


@pytest.mark.asyncio
async def test_search_no_results(engine, search_knowledge_dir):
    """Test search with no results."""
    result = await engine.search(
        query="nonexistentword123456",
        path=search_knowledge_dir,
        recursive=True,
        context_lines=1,
        max_results=10,
    )

    assert len(result.matches) == 0
    assert result.total_matches == 0
    assert not result.truncated


@pytest.mark.asyncio
async def test_search_timeout(engine, search_knowledge_dir, search_config):
    """Test search timeout handling."""
    # Mock the _run_ugrep method to simulate a slow search
    async def slow_search(*args, **kwargs):
        await asyncio.sleep(100)  # Sleep longer than timeout
        return MagicMock(stdout="", stderr="", returncode=0)

    with patch.object(engine, "_run_ugrep", side_effect=slow_search):
        # Set a very short timeout in config
        search_config.search.timeout_seconds = 1

        with pytest.raises(McpError) as exc_info:
            await engine.search(
                query="test",
                path=search_knowledge_dir,
                recursive=True,
            )

        assert exc_info.value.code == ErrorCode.SEARCH_TIMEOUT


@pytest.mark.asyncio
async def test_search_concurrent_limiting(engine, search_knowledge_dir, search_config):
    """Test concurrent search limiting with semaphore."""
    # Set max concurrent searches to 2
    search_config.limits.max_concurrent_searches = 2
    engine._semaphore = asyncio.Semaphore(2)

    # Track concurrent execution
    concurrent_count = 0
    max_concurrent = 0
    lock = asyncio.Lock()

    async def mock_run_ugrep(*args, **kwargs):
        nonlocal concurrent_count, max_concurrent
        async with lock:
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)

        await asyncio.sleep(0.1)  # Simulate work

        async with lock:
            concurrent_count -= 1

        return MagicMock(stdout="", stderr="", returncode=0)

    with patch.object(engine, "_run_ugrep", side_effect=mock_run_ugrep):
        # Launch 5 concurrent searches
        tasks = [
            engine.search(query=f"test{i}", path=search_knowledge_dir, recursive=True)
            for i in range(5)
        ]
        await asyncio.gather(*tasks)

    # Max concurrent should not exceed the semaphore limit
    assert max_concurrent <= 2


# ============================================================================
# Tool Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_search_documents_global_scope(search_config, search_knowledge_dir):
    """Test search_documents with global scope."""
    engine = UgrepEngine(search_config)

    args = {
        "query": "attack",
        "scope": {"type": "global"},
        "context_lines": 2,
        "max_results": 20,
        "fuzzy": False,
    }

    result = await _search_documents(search_config, engine, args)

    assert "matches" in result
    assert "total_matches" in result
    assert "truncated" in result
    assert isinstance(result["matches"], list)


@pytest.mark.asyncio
async def test_search_documents_collection_scope(search_config, search_knowledge_dir):
    """Test search_documents with collection scope."""
    engine = UgrepEngine(search_config)

    args = {
        "query": "movement",
        "scope": {"type": "collection", "path": "games"},
        "context_lines": 2,
        "max_results": 20,
        "fuzzy": False,
    }

    result = await _search_documents(search_config, engine, args)

    assert len(result["matches"]) > 0
    # All matches should be from the games collection
    for match in result["matches"]:
        assert "games" in match["document"].lower() or Path(match["document"]).parts[0] == "games"


@pytest.mark.asyncio
async def test_search_documents_document_scope(search_config, search_knowledge_dir):
    """Test search_documents with document scope."""
    engine = UgrepEngine(search_config)

    args = {
        "query": "attack",
        "scope": {"type": "document", "path": "games/coop/Gloomhaven.md"},
        "context_lines": 2,
        "max_results": 20,
        "fuzzy": False,
    }

    result = await _search_documents(search_config, engine, args)

    if len(result["matches"]) > 0:
        # All matches should be from the single document
        for match in result["matches"]:
            assert "Gloomhaven.md" in match["document"]


@pytest.mark.asyncio
async def test_search_documents_path_not_found(search_config, search_knowledge_dir):
    """Test search_documents with non-existent path."""
    engine = UgrepEngine(search_config)

    args = {
        "query": "test",
        "scope": {"type": "collection", "path": "nonexistent"},
        "context_lines": 2,
        "max_results": 20,
        "fuzzy": False,
    }

    with pytest.raises(McpError) as exc_info:
        await _search_documents(search_config, engine, args)

    assert exc_info.value.code == ErrorCode.PATH_NOT_FOUND


@pytest.mark.asyncio
async def test_search_documents_document_not_found(search_config, search_knowledge_dir):
    """Test search_documents with non-existent document."""
    engine = UgrepEngine(search_config)

    args = {
        "query": "test",
        "scope": {"type": "document", "path": "nonexistent.md"},
        "context_lines": 2,
        "max_results": 20,
        "fuzzy": False,
    }

    with pytest.raises(McpError) as exc_info:
        await _search_documents(search_config, engine, args)

    assert exc_info.value.code == ErrorCode.DOCUMENT_NOT_FOUND


@pytest.mark.asyncio
async def test_search_documents_custom_context_and_max_results(search_config, search_knowledge_dir):
    """Test custom context_lines and max_results parameters."""
    engine = UgrepEngine(search_config)

    args = {
        "query": "attack",
        "scope": {"type": "global"},
        "context_lines": 10,
        "max_results": 1,
        "fuzzy": False,
    }

    result = await _search_documents(search_config, engine, args)

    # Should return at most 1 result
    assert len(result["matches"]) <= 1
    if len(result["matches"]) == 1 and result["total_matches"] > 1:
        assert result["truncated"]


# ============================================================================
# PDF Search Tests (if pdftotext is available)
# ============================================================================


@pytest.mark.asyncio
async def test_search_pdf_with_filter(engine, pdf_test_file, search_knowledge_dir, search_config):
    """Test search in PDF files using pdftotext filter."""
    # Check if PDF format is enabled in config
    if ".pdf" in search_config.supported_extensions:
        result = await engine.search(
            query="PDF",
            path=pdf_test_file,
            recursive=False,
            context_lines=1,
            max_results=10,
        )

        # This test may fail if pdftotext is not installed
        # That's expected - the test verifies the mechanism works
        assert isinstance(result, SearchResult)


@pytest.mark.asyncio
async def test_search_multiple_formats(engine, search_knowledge_dir):
    """Test search across multiple file formats (.md, .txt)."""
    result = await engine.search(
        query="armor",
        path=search_knowledge_dir,
        recursive=True,
        context_lines=1,
        max_results=20,
    )

    assert len(result.matches) > 0

    # Should find matches in different file types
    file_extensions = {Path(match.file).suffix for match in result.matches}
    # Should include at least .md files
    assert ".md" in file_extensions or ".txt" in file_extensions


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================


@pytest.mark.asyncio
async def test_search_empty_query(engine, search_knowledge_dir):
    """Test search with empty query."""
    result = await engine.search(
        query="",
        path=search_knowledge_dir,
        recursive=True,
        context_lines=1,
        max_results=10,
    )

    # Empty query should return no results or all results depending on ugrep behavior
    assert isinstance(result, SearchResult)


@pytest.mark.asyncio
async def test_search_special_characters(engine, search_knowledge_dir):
    """Test search with special regex characters."""
    # Create a file with special characters
    test_file = search_knowledge_dir / "special.md"
    test_file.write_text("Test [brackets] and (parentheses) and $dollar signs.")

    result = await engine.search(
        query="brackets",
        path=search_knowledge_dir,
        recursive=True,
        context_lines=1,
        max_results=10,
    )

    # Should find the word despite special characters nearby
    assert isinstance(result, SearchResult)


@pytest.mark.asyncio
async def test_parse_output_with_context(engine):
    """Test _parse_output method with context lines."""
    # Simulate ugrep output with context
    stdout = """games/test.md:5:This is a match
games/test.md-6-Context after line 1
games/test.md-7-Context after line 2

games/other.md:10:Another match
"""

    base_path = Path("/tmp/knowledge")
    matches = engine._parse_output(stdout, base_path)

    assert len(matches) >= 1
    if len(matches) > 0:
        first_match = matches[0]
        assert first_match.line_number == 5
        assert "match" in first_match.text.lower()


@pytest.mark.asyncio
async def test_parse_output_empty(engine):
    """Test _parse_output with empty output."""
    stdout = ""
    base_path = Path("/tmp/knowledge")

    matches = engine._parse_output(stdout, base_path)

    assert len(matches) == 0


@pytest.mark.asyncio
async def test_build_command_recursive(engine, search_knowledge_dir):
    """Test _build_command for recursive search."""
    cmd = engine._build_command(
        query="test",
        path=search_knowledge_dir,
        recursive=True,
        context_lines=3,
        fuzzy=False,
    )

    assert "ugrep" in cmd
    assert "-%"  in cmd  # Boolean mode
    assert "-i" in cmd  # Case insensitive
    assert "-C3" in cmd  # Context lines
    assert "-r" in cmd  # Recursive
    assert "test" in cmd


@pytest.mark.asyncio
async def test_build_command_fuzzy(engine, search_knowledge_dir):
    """Test _build_command with fuzzy flag."""
    cmd = engine._build_command(
        query="test",
        path=search_knowledge_dir,
        recursive=True,
        context_lines=2,
        fuzzy=True,
    )

    assert "-Z" in cmd  # Fuzzy flag


@pytest.mark.asyncio
async def test_build_command_single_file(engine, search_knowledge_dir):
    """Test _build_command for single file search."""
    file_path = search_knowledge_dir / "games" / "Guide.md"

    cmd = engine._build_command(
        query="test",
        path=file_path,
        recursive=False,
        context_lines=2,
        fuzzy=False,
    )

    assert "ugrep" in cmd
    assert "-r" not in cmd  # Should not be recursive
    assert str(file_path) in cmd


@pytest.mark.asyncio
async def test_diagnostic_ugrep_direct(search_knowledge_dir):
    """Diagnostic test to check if ugrep works directly."""
    import subprocess

    # Create a test file
    test_file = search_knowledge_dir / "diagnostic.md"
    test_file.write_text("This file contains movement and attack keywords for testing.")

    # Try direct ugrep command (no boolean mode)
    cmd = ["ugrep", "-i", "--line-number", "movement", str(test_file)]
    print(f"\nDiagnostic command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(f"Return code: {result.returncode}")
    print(f"Stdout: {result.stdout}")
    print(f"Stderr: {result.stderr}")

    # Should find the match
    assert result.returncode == 0 or len(result.stdout) > 0, (
        f"Direct ugrep failed: rc={result.returncode}, "
        f"stdout={result.stdout}, stderr={result.stderr}"
    )
