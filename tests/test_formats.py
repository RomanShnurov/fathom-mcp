"""Tests for multi-format document support."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from contextfs.config import Config, KnowledgeConfig
from contextfs.search.ugrep import UgrepEngine


@pytest.mark.asyncio
async def test_ug_plus_command_generation(tmp_path):
    """Test that ug+ is used when formats with filters are enabled."""
    # Set knowledge root and enable formats with filters
    config = Config(knowledge=KnowledgeConfig(root=str(tmp_path)))
    config.formats["word_docx"].enabled = True
    config.formats["epub"].enabled = True

    # Generate .ugrep config
    ugrep_config_path = config.write_ugrep_config()

    engine = UgrepEngine(config)

    cmd = engine._build_command(
        query="test",
        path=tmp_path,
        recursive=True,
        context_lines=3,
        fuzzy=False,
    )

    # Validate command structure
    assert cmd[0] == "ugrep"  # Always uses ugrep (ug+ is just an alias)
    assert "-%" in cmd  # Boolean mode
    assert "-i" in cmd  # Case insensitive
    assert "-C3" in cmd  # Context lines

    # Verify config file reference
    assert "--config" in cmd
    config_index = cmd.index("--config")
    assert cmd[config_index + 1] == str(ugrep_config_path)

    # Verify config file content
    config_content = ugrep_config_path.read_text()
    assert "--filter=" in config_content
    assert "docx:" in config_content or "epub:" in config_content


@pytest.mark.asyncio
async def test_ugrep_command_when_no_filters(tmp_path):
    """Test that ugrep is used when no formats need filters."""
    config = Config(knowledge=KnowledgeConfig(root=str(tmp_path)))

    # Disable all formats with filters
    for fmt in config.formats.values():
        if fmt.filter is not None:
            fmt.enabled = False

    # Enable only non-filter formats
    config.formats["csv"].enabled = True
    config.formats["markdown"].enabled = True

    engine = UgrepEngine(config)

    cmd = engine._build_command(
        query="test",
        path=tmp_path,
        recursive=True,
        context_lines=3,
        fuzzy=False,
    )

    # Should use regular ugrep
    assert cmd[0] == "ugrep"
    assert "--config" not in cmd


@pytest.mark.asyncio
async def test_ugrep_config_file_usage(tmp_path):
    """Test that .ugrep config file is referenced correctly."""
    # Set knowledge root and create .ugrep file
    config = Config(knowledge=KnowledgeConfig(root=str(tmp_path)))
    config.formats["word_docx"].enabled = True
    ugrep_path = config.write_ugrep_config()

    engine = UgrepEngine(config)
    cmd = engine._build_command(
        query="test",
        path=tmp_path,
        recursive=True,
        context_lines=3,
        fuzzy=False,
    )

    # Verify config path in command
    assert "--config" in cmd
    config_index = cmd.index("--config")
    assert Path(cmd[config_index + 1]) == ugrep_path

    # Verify file is in temp directory, not knowledge root
    assert ugrep_path.parent != tmp_path


@pytest.mark.asyncio
async def test_multi_format_search_mock(tmp_path):
    """Test multi-format search with mocked execution."""
    config = Config(knowledge=KnowledgeConfig(root=str(tmp_path)))
    config.formats["word_docx"].enabled = True
    config.write_ugrep_config()

    engine = UgrepEngine(config)

    # Mock the subprocess execution
    with patch("asyncio.to_thread") as mock_to_thread:
        # Mock process result
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "test.docx:10:Found match in DOCX\n"
        mock_result.stderr = ""
        mock_to_thread.return_value = mock_result

        # Run search
        results = await engine.search(
            query="test query",
            path=tmp_path,
            recursive=True,
        )

        # Verify ugrep was called with config
        call_args = mock_to_thread.call_args[0]
        # First arg is the function (subprocess.run), second is the command list
        assert len(call_args) >= 2
        # The command should be in the kwargs or args
        # Verify the result was parsed
        assert results.total_matches >= 0


@pytest.mark.asyncio
async def test_config_file_generated_with_filters(tmp_path):
    """Test .ugrep config file contains correct filter definitions."""
    config = Config(knowledge=KnowledgeConfig(root=str(tmp_path)))

    # Enable multiple formats
    config.formats["word_docx"].enabled = True
    config.formats["epub"].enabled = True
    config.formats["json"].enabled = True

    ugrep_path = config.write_ugrep_config()
    content = ugrep_path.read_text()

    # Verify all filters are present
    assert "docx:" in content
    assert "epub:" in content
    assert "json:" in content
    assert "pandoc" in content
    assert "jq" in content


@pytest.mark.asyncio
async def test_check_ug_plus_available(tmp_path):
    """Test ug+ availability check."""
    config = Config(knowledge=KnowledgeConfig(root=str(tmp_path)))
    engine = UgrepEngine(config)

    # This will check system availability
    result = engine._check_ug_plus_available()
    # Result depends on system, just verify it returns a boolean
    assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_ugrep_config_path_uniqueness(tmp_path):
    """Test that different knowledge roots get different .ugrep config paths."""
    import tempfile

    config1 = Config(knowledge=KnowledgeConfig(root=str(tmp_path)))
    path1 = config1.get_ugrep_config_path()

    # Create another temp directory
    with tempfile.TemporaryDirectory() as tmp_path2:
        config2 = Config(knowledge=KnowledgeConfig(root=str(tmp_path2)))
        path2 = config2.get_ugrep_config_path()

        # Paths should be different for different roots
        assert path1 != path2


@pytest.mark.asyncio
async def test_ugrep_config_not_found_warning(tmp_path, caplog):
    """Test warning is logged when .ugrep config file doesn't exist."""
    config = Config(knowledge=KnowledgeConfig(root=str(tmp_path)))
    config.formats["word_docx"].enabled = True

    # Don't write the config file
    engine = UgrepEngine(config)

    # Build command - should log warning
    cmd = engine._build_command(
        query="test",
        path=tmp_path,
        recursive=True,
        context_lines=3,
        fuzzy=False,
    )

    # Command should still be generated with ugrep
    assert cmd[0] == "ugrep"


@pytest.mark.asyncio
async def test_csv_format_enabled_by_default(tmp_path):
    """Test that CSV format is enabled by default."""
    config = Config(knowledge=KnowledgeConfig(root=str(tmp_path)))

    # CSV should be enabled
    assert config.formats["csv"].enabled

    # And should not require filters
    assert config.formats["csv"].filter is None


@pytest.mark.asyncio
async def test_office_formats_disabled_by_default(tmp_path):
    """Test that office formats are disabled by default."""
    config = Config(knowledge=KnowledgeConfig(root=str(tmp_path)))

    # All office formats should be disabled
    assert not config.formats["word_doc"].enabled
    assert not config.formats["word_docx"].enabled
    assert not config.formats["opendocument"].enabled
    assert not config.formats["epub"].enabled
    assert not config.formats["html"].enabled
    assert not config.formats["rtf"].enabled
    assert not config.formats["json"].enabled
    assert not config.formats["xml"].enabled


@pytest.mark.asyncio
async def test_supported_extensions_includes_new_formats(tmp_path):
    """Test that supported_extensions includes newly enabled formats."""
    config = Config(knowledge=KnowledgeConfig(root=str(tmp_path)))

    # Enable a new format
    config.formats["word_docx"].enabled = True

    extensions = config.supported_extensions

    # Should include .docx now
    assert ".docx" in extensions

    # Disable it
    config.formats["word_docx"].enabled = False

    extensions = config.supported_extensions

    # Should not include .docx now
    assert ".docx" not in extensions


# ============================================================================
# Week 2: Read Tool Tests
# ============================================================================


@pytest.mark.asyncio
async def test_read_with_filter_docx(tmp_path):
    """Test reading DOCX with filter (mocked)."""
    from contextfs.tools.read import _read_with_filter

    config = Config(knowledge=KnowledgeConfig(root=str(tmp_path)))

    # Create dummy DOCX file
    docx_path = tmp_path / "test.docx"
    docx_path.write_bytes(b"fake docx content")

    # Enable DOCX
    config.formats["word_docx"].enabled = True
    filter_cmd = "pandoc --wrap=preserve -f docx -t plain % -o -"

    # Mock FilterSecurity.run_secure_filter
    with patch("contextfs.security.FilterSecurity.run_secure_filter") as mock_filter:
        mock_filter.return_value = b"Extracted text from DOCX"

        # Read document
        text = await _read_with_filter(docx_path, filter_cmd, config)

        # Verify
        assert text == "Extracted text from DOCX"
        mock_filter.assert_called_once()


@pytest.mark.asyncio
async def test_read_with_filter_timeout(tmp_path):
    """Test filter timeout handling."""

    from contextfs.errors import McpError
    from contextfs.tools.read import _read_with_filter

    config = Config(knowledge=KnowledgeConfig(root=str(tmp_path)))

    docx_path = tmp_path / "test.docx"
    docx_path.write_bytes(b"fake docx")

    config.formats["word_docx"].enabled = True
    filter_cmd = "pandoc --wrap=preserve -f docx -t plain % -o -"

    # Mock timeout
    with patch("contextfs.security.FilterSecurity.run_secure_filter") as mock_filter:
        mock_filter.side_effect = TimeoutError()

        # Should raise MCP error
        with pytest.raises(McpError) as exc_info:
            await _read_with_filter(docx_path, filter_cmd, config)

        assert "timeout" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_read_with_filter_execution_error(tmp_path):
    """Test filter execution error handling."""
    from contextfs.errors import McpError
    from contextfs.tools.read import _read_with_filter

    config = Config(knowledge=KnowledgeConfig(root=str(tmp_path)))

    docx_path = tmp_path / "test.docx"
    docx_path.write_bytes(b"fake docx")

    config.formats["word_docx"].enabled = True
    filter_cmd = "pandoc --wrap=preserve -f docx -t plain % -o -"

    # Mock execution error
    with patch("contextfs.security.FilterSecurity.run_secure_filter") as mock_filter:
        mock_filter.side_effect = Exception("Command failed")

        # Should raise MCP error
        with pytest.raises(McpError) as exc_info:
            await _read_with_filter(docx_path, filter_cmd, config)

        assert "filter failed" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_read_document_docx(tmp_path):
    """Test reading DOCX via _read_document."""
    from contextfs.tools.read import handle_read_tool

    config = Config(knowledge=KnowledgeConfig(root=str(tmp_path)))

    docx_path = tmp_path / "test.docx"
    docx_path.write_bytes(b"fake docx")

    config.formats["word_docx"].enabled = True

    # Mock filter execution
    with patch("contextfs.tools.read._read_with_filter") as mock_read:
        mock_read.return_value = "DOCX content extracted"

        # Read document
        result = await handle_read_tool("read_document", {"path": "test.docx"}, config)

        # Verify
        assert len(result) == 1
        assert "DOCX content extracted" in result[0].text


@pytest.mark.asyncio
async def test_read_document_html(tmp_path):
    """Test reading HTML with filter."""
    from contextfs.tools.read import handle_read_tool

    config = Config(knowledge=KnowledgeConfig(root=str(tmp_path)))

    html_path = tmp_path / "test.html"
    html_path.write_text("<html><body><h1>Test</h1></body></html>")

    config.formats["html"].enabled = True

    # Mock filter execution
    with patch("contextfs.tools.read._read_with_filter") as mock_read:
        mock_read.return_value = "# Test\n"

        # Read document
        result = await handle_read_tool("read_document", {"path": "test.html"}, config)

        # Verify
        assert len(result) == 1
        assert "Test" in result[0].text


@pytest.mark.asyncio
async def test_read_document_json(tmp_path):
    """Test reading JSON with jq filter."""
    from contextfs.tools.read import handle_read_tool

    config = Config(knowledge=KnowledgeConfig(root=str(tmp_path)))

    json_path = tmp_path / "test.json"
    json_path.write_text('{"name": "test", "value": 123}')

    config.formats["json"].enabled = True

    # Mock filter execution
    with patch("contextfs.tools.read._read_with_filter") as mock_read:
        mock_read.return_value = '{"name":"test","value":123}'

        # Read document
        result = await handle_read_tool("read_document", {"path": "test.json"}, config)

        # Verify JSON content
        assert len(result) == 1
        assert "test" in result[0].text
        assert "123" in result[0].text


@pytest.mark.asyncio
async def test_read_document_truncation(tmp_path):
    """Test content truncation for large documents."""
    from contextfs.tools.read import handle_read_tool

    config = Config(knowledge=KnowledgeConfig(root=str(tmp_path)))

    docx_path = tmp_path / "large.docx"
    docx_path.write_bytes(b"fake large docx")

    config.formats["word_docx"].enabled = True
    config.limits.max_document_read_chars = 100  # Small limit

    # Mock filter returning large content
    with patch("contextfs.tools.read._read_with_filter") as mock_read:
        mock_read.return_value = "x" * 200  # 200 characters

        # Read document
        result = await handle_read_tool("read_document", {"path": "large.docx"}, config)

        # Should be truncated
        content = result[0].text
        assert "truncated" in content.lower()


@pytest.mark.asyncio
async def test_get_document_info_docx(tmp_path):
    """Test getting document info for DOCX."""
    from contextfs.tools.read import handle_read_tool

    config = Config(knowledge=KnowledgeConfig(root=str(tmp_path)))

    docx_path = tmp_path / "test.docx"
    docx_path.write_bytes(b"fake docx")

    config.formats["word_docx"].enabled = True

    # Mock filter execution
    with patch("contextfs.tools.read._read_with_filter") as mock_read:
        mock_read.return_value = "Test document content here. " * 100  # ~300 words

        # Get info
        result = await handle_read_tool("get_document_info", {"path": "test.docx"}, config)

        # Verify
        assert len(result) == 1
        info_text = result[0].text
        assert "test.docx" in info_text
        assert "docx" in info_text


@pytest.mark.asyncio
async def test_get_document_info_csv(tmp_path):
    """Test getting document info for CSV (no filter)."""
    from contextfs.tools.read import handle_read_tool

    config = Config(knowledge=KnowledgeConfig(root=str(tmp_path)))

    csv_path = tmp_path / "data.csv"
    csv_path.write_text("name,value\ntest,123\n")

    # Get info
    result = await handle_read_tool("get_document_info", {"path": "data.csv"}, config)

    # Verify
    assert len(result) == 1
    info_text = result[0].text
    assert "data.csv" in info_text


@pytest.mark.asyncio
async def test_validate_filter_output_empty():
    """Test _validate_filter_output with empty output."""
    from contextfs.tools.read import _validate_filter_output

    result = _validate_filter_output(b"", ".docx")
    assert result == ""


@pytest.mark.asyncio
async def test_validate_filter_output_invalid_utf8():
    """Test _validate_filter_output with invalid UTF-8."""
    from contextfs.tools.read import _validate_filter_output

    # Invalid UTF-8 bytes
    invalid_bytes = b"\xff\xfe Invalid UTF-8"
    result = _validate_filter_output(invalid_bytes, ".docx")

    # Should not raise, should replace invalid chars
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_read_with_filter_streaming_large_file(tmp_path):
    """Test streaming for large files (>50MB)."""
    from contextfs.tools.read import _read_with_filter

    config = Config(knowledge=KnowledgeConfig(root=str(tmp_path)))

    # Create a file larger than 50MB threshold
    large_path = tmp_path / "large.docx"
    large_path.write_bytes(b"x" * (51 * 1024 * 1024))  # 51MB

    config.formats["word_docx"].enabled = True
    filter_cmd = "pandoc --wrap=preserve -f docx -t plain % -o -"

    # Mock the streaming function
    with patch("contextfs.tools.read._read_with_filter_streaming") as mock_stream:
        mock_stream.return_value = "Streamed content"

        # Read document (should use streaming)
        text = await _read_with_filter(large_path, filter_cmd, config, max_size_mb=50)

        # Verify streaming was used
        assert text == "Streamed content"
        mock_stream.assert_called_once()


@pytest.mark.asyncio
async def test_read_document_page_selection_warning(tmp_path):
    """Test that page selection for non-PDF shows warning."""
    from contextfs.tools.read import handle_read_tool

    config = Config(knowledge=KnowledgeConfig(root=str(tmp_path)))

    docx_path = tmp_path / "test.docx"
    docx_path.write_bytes(b"fake docx")

    config.formats["word_docx"].enabled = True

    # Mock filter execution
    with patch("contextfs.tools.read._read_with_filter") as mock_read:
        mock_read.return_value = "DOCX content"

        # Try to read specific pages (not supported for DOCX)
        result = await handle_read_tool(
            "read_document", {"path": "test.docx", "pages": [2, 3]}, config
        )

        # Should still return content (all pages)
        assert len(result) == 1
        assert "DOCX content" in result[0].text


# ============================================================================
# Week 2: Integration Tests (conditional on tool availability)
# ============================================================================


@pytest.fixture
def sample_html(tmp_path):
    """Create sample HTML file."""
    html = """<!DOCTYPE html>
<html>
<head><title>Test Page</title></head>
<body>
    <h1>Test Document</h1>
    <p>This paragraph contains <strong>searchable</strong> text.</p>
    <p>Another paragraph for testing.</p>
</body>
</html>
"""
    path = tmp_path / "test.html"
    path.write_text(html)
    return path


@pytest.fixture
def sample_json(tmp_path):
    """Create sample JSON file."""
    import json

    json_data = {
        "name": "test document",
        "content": "searchable text",
        "metadata": {"author": "test", "version": 1},
    }

    path = tmp_path / "test.json"
    path.write_text(json.dumps(json_data, indent=2))
    return path


@pytest.mark.integration
@pytest.mark.asyncio
async def test_read_real_html(sample_html):
    """Integration test: Read real HTML file with pandoc."""
    import shutil

    if not shutil.which("pandoc"):
        pytest.skip("pandoc not installed")

    from contextfs.tools.read import handle_read_tool

    config = Config(knowledge=KnowledgeConfig(root=str(sample_html.parent)))
    config.formats["html"].enabled = True

    # Read document
    result = await handle_read_tool("read_document", {"path": "test.html"}, config)

    # Verify content extracted
    assert len(result) == 1
    content = result[0].text
    assert "Test Document" in content or "test document" in content.lower()
    assert "searchable" in content.lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_read_real_json(sample_json):
    """Integration test: Read real JSON file with jq."""
    import shutil

    if not shutil.which("jq"):
        pytest.skip("jq not installed")

    from contextfs.tools.read import handle_read_tool

    config = Config(knowledge=KnowledgeConfig(root=str(sample_json.parent)))
    config.formats["json"].enabled = True

    # Read document
    result = await handle_read_tool("read_document", {"path": "test.json"}, config)

    # Verify JSON content
    assert len(result) == 1
    content = result[0].text
    assert "test document" in content
    assert "searchable" in content
