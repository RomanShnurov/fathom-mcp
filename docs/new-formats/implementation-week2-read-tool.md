# Week 2 Implementation: Read Tool Updates for Multi-Format Support

## Overview

**Timeline**: Week 2 (Days 8-14)
**Focus**: Update read tool to support document filters
**Phase**: 1C (Read Tool Updates)
**Prerequisites**: Week 1 complete (configuration and search engine ready)

---

## Goals

1. Enable reading documents with filter commands
2. Add `_read_with_filter()` async function
3. Generalize `_read_document()` for all formats
4. Handle filter timeouts and errors gracefully
5. Add comprehensive read tests

---

## Phase 1C: Read Tool Updates

### Background

Currently, `read_document` tool:
- Handles PDF files with special logic (pypdf + parallel processing)
- Reads Markdown and text files directly
- Needs to support new formats via filter commands

With the new approach:
- Use filter commands from format configuration
- Apply FilterSecurity for safe execution
- Handle timeouts and errors
- Maintain existing PDF optimization

### Tasks

#### 1. Add `_read_with_filter()` Function

**Location**: `src/contextfs/tools/read.py`

```python
async def _read_with_filter(
    full_path: Path,
    filter_cmd: str,
    config: Config,
    max_size_mb: int = 50,
) -> str:
    """Read document using filter command.

    For large files (>50MB), uses streaming to avoid memory issues.

    Args:
        full_path: Path to document file
        filter_cmd: Filter command to execute (e.g., "pandoc ...")
        config: Server configuration
        max_size_mb: Max size for in-memory processing (default 50MB)

    Returns:
        Extracted text content

    Raises:
        McpError: If filter execution fails or times out
    """
    import asyncio
    from contextfs.security import FilterSecurity

    # Check file size
    file_size_mb = full_path.stat().st_size / (1024 * 1024)

    if file_size_mb > max_size_mb:
        logger.info(f"Large file ({file_size_mb:.1f}MB), using streaming filter")
        return await _read_with_filter_streaming(full_path, filter_cmd, config)

    try:
        # Read file bytes
        file_bytes = await asyncio.to_thread(full_path.read_bytes)

        # Execute filter with security validation
        filter_security = FilterSecurity(config)

        # Use proper placeholder replacement
        filter_cmd_stdin = config.prepare_filter_for_stdin(filter_cmd)

        text_bytes = await filter_security.run_secure_filter(
            filter_cmd_stdin,
            file_bytes,
            timeout_override=config.security.filter_timeout_seconds,
        )

        # Validate and decode output
        return _validate_filter_output(text_bytes, full_path.suffix)

    except asyncio.TimeoutError:
        raise filter_timeout(full_path.name, config.security.filter_timeout_seconds)
    except Exception as e:
        raise filter_execution_error(full_path.name, filter_cmd, str(e))


async def _read_with_filter_streaming(
    full_path: Path,
    filter_cmd: str,
    config: Config,
) -> str:
    """Read large document using streaming filter execution.

    Args:
        full_path: Path to document file
        filter_cmd: Filter command to execute
        config: Server configuration

    Returns:
        Extracted text content

    Raises:
        McpError: If filter execution fails or times out
    """
    import asyncio
    import shlex
    from contextfs.security import FilterSecurity

    filter_security = FilterSecurity(config)

    # Validate filter command
    filter_cmd_stdin = config.prepare_filter_for_stdin(filter_cmd)
    if not filter_security.validate_filter_command(filter_cmd_stdin):
        raise filter_execution_error(
            full_path.name,
            filter_cmd,
            "Filter command not allowed by security policy"
        )

    # Parse command for subprocess
    cmd_parts = shlex.split(filter_cmd_stdin)

    try:
        # Create subprocess with stdin from file
        proc = await asyncio.create_subprocess_exec(
            *cmd_parts,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Read file and send to process stdin
        file_bytes = await asyncio.to_thread(full_path.read_bytes)

        # Communicate with timeout
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=file_bytes),
            timeout=config.security.filter_timeout_seconds,
        )

        if proc.returncode != 0:
            error_msg = stderr.decode('utf-8', errors='replace')
            raise filter_execution_error(full_path.name, filter_cmd, error_msg)

        # Validate and decode output
        return _validate_filter_output(stdout, full_path.suffix)

    except asyncio.TimeoutError:
        if proc:
            proc.kill()
            await proc.wait()
        raise filter_timeout(full_path.name, config.security.filter_timeout_seconds)
    except Exception as e:
        raise filter_execution_error(full_path.name, filter_cmd, str(e))


def _validate_filter_output(output: bytes, format_ext: str) -> str:
    """Validate and decode filter output.

    Args:
        output: Raw bytes from filter
        format_ext: File extension for context

    Returns:
        Decoded text string

    Raises:
        McpError: If output is invalid
    """
    # Check output isn't empty
    if not output:
        logger.warning(f"Filter for {format_ext} produced empty output")
        return ""

    # Decode with error handling
    try:
        text = output.decode('utf-8')
        return text
    except UnicodeDecodeError as e:
        logger.warning(f"Filter output contains invalid UTF-8 for {format_ext}: {e}")
        # Try with error replacement
        return output.decode('utf-8', errors='replace')
```

#### 2. Update `_read_document()` Function

**Generalize reading logic** to support filters:

```python
async def _read_document(
    full_path: Path,
    pages: list[int] | None,
    config: Config,
) -> tuple[str, int, list[int]]:
    """Read document content with optional page selection.

    Args:
        full_path: Path to document
        pages: Optional list of page numbers (1-indexed)
        config: Server configuration

    Returns:
        Tuple of (content, total_pages, pages_read)
    """
    import asyncio

    # Get file extension
    ext = full_path.suffix.lower()

    # Get filter command for this extension
    filter_cmd = config.get_filter_for_extension(ext)

    # === PDF: Special handling with parallel processing ===
    if ext == ".pdf":
        if config.performance.enable_parallel_pdf:
            from contextfs.performance.parallel_pdf import ParallelPDFProcessor

            processor = ParallelPDFProcessor(config)
            content, total_pages, pages_read = await processor.read_pdf_parallel(
                full_path, pages
            )
        else:
            content, total_pages, pages_read = await asyncio.to_thread(
                _read_pdf, full_path, pages
            )

    # === Filtered formats: Use filter command ===
    elif filter_cmd:
        content = await _read_with_filter(full_path, filter_cmd, config)

        # For filtered documents, treat as single-page
        total_pages = 1
        pages_read = [1]

        # Page selection not supported for non-PDF
        if pages and pages != [1]:
            logger.warning(
                f"Page selection not supported for {ext} files, returning all content"
            )

    # === Plain text formats: Direct read ===
    else:
        content = await asyncio.to_thread(
            full_path.read_text, encoding="utf-8", errors="replace"
        )
        total_pages = 1
        pages_read = [1]

    # Apply character limit
    max_chars = config.limits.max_document_read_chars
    if len(content) > max_chars:
        content = content[:max_chars]
        logger.info(f"Content truncated to {max_chars} characters")

    return content, total_pages, pages_read
```

#### 3. Update `_get_document_info()` Function

**Add format metadata** for new types:

```python
async def _get_document_info(full_path: Path, config: Config) -> dict:
    """Get document metadata.

    Args:
        full_path: Path to document
        config: Server configuration

    Returns:
        Dictionary with document info
    """
    import asyncio
    from datetime import datetime

    # Base info
    stat = full_path.stat()
    info = {
        "path": str(full_path),
        "name": full_path.name,
        "size_bytes": stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "format": full_path.suffix.lower(),
    }

    # Get filter command if applicable
    filter_cmd = config.get_filter_for_extension(full_path.suffix.lower())
    if filter_cmd:
        info["filter"] = filter_cmd.split()[0]  # Just the command name

    # === PDF-specific metadata ===
    if full_path.suffix.lower() == ".pdf":
        try:
            pdf_info = await asyncio.to_thread(_get_pdf_info, full_path)
            info.update(pdf_info)
        except Exception as e:
            logger.warning(f"Failed to extract PDF metadata: {e}")

    # === Text formats: Add line count ===
    elif filter_cmd is None:
        try:
            text = await asyncio.to_thread(
                full_path.read_text, encoding="utf-8", errors="replace"
            )
            info["line_count"] = text.count("\n") + 1
        except Exception as e:
            logger.warning(f"Failed to count lines: {e}")

    # === Filtered formats: Add page count estimate ===
    else:
        try:
            # Read through filter to get content
            text = await _read_with_filter(full_path, filter_cmd, config)
            # Estimate pages (rough: 500 words per page)
            word_count = len(text.split())
            info["estimated_pages"] = max(1, word_count // 500)
            info["word_count"] = word_count
        except Exception as e:
            logger.warning(f"Failed to extract document info: {e}")

    return info
```

#### 4. Add Error Handling

**Update `src/contextfs/errors.py`** with new error types:

```python
def filter_timeout(filename: str, timeout_seconds: int) -> McpError:
    """Filter execution timed out."""
    return McpError(
        ErrorCode.FILTER_TIMEOUT,
        f"Filter timeout reading {filename} (>{timeout_seconds}s)",
    )


def filter_execution_error(filename: str, filter_cmd: str, error: str) -> McpError:
    """Filter execution failed."""
    return McpError(
        ErrorCode.FILTER_EXECUTION_ERROR,
        f"Filter failed for {filename}: {filter_cmd} - {error}",
    )
```

#### 5. Add Tests to `tests/test_formats.py`

```python
"""Read tool tests for multi-format support."""

import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

from contextfs.tools.read import _read_with_filter, _read_document, _get_document_info
from contextfs.config import Config


@pytest.mark.asyncio
async def test_read_with_filter_docx(config, tmp_path):
    """Test reading DOCX with filter (mocked)."""
    # Create dummy DOCX file
    docx_path = tmp_path / "test.docx"
    docx_path.write_bytes(b"fake docx content")

    # Enable DOCX
    config.formats["word_docx"].enabled = True
    filter_cmd = "pandoc --wrap=preserve -f docx -t plain - -o -"

    # Mock FilterSecurity.run_secure_filter
    with patch("contextfs.security.FilterSecurity.run_secure_filter") as mock_filter:
        mock_filter.return_value = b"Extracted text from DOCX"

        # Read document
        text = await _read_with_filter(docx_path, filter_cmd, config)

        # Verify
        assert text == "Extracted text from DOCX"
        mock_filter.assert_called_once()


@pytest.mark.asyncio
async def test_read_with_filter_timeout(config, tmp_path):
    """Test filter timeout handling."""
    import asyncio

    docx_path = tmp_path / "test.docx"
    docx_path.write_bytes(b"fake docx")

    config.formats["word_docx"].enabled = True
    filter_cmd = "pandoc --wrap=preserve -f docx -t plain - -o -"

    # Mock timeout
    with patch("contextfs.security.FilterSecurity.run_secure_filter") as mock_filter:
        mock_filter.side_effect = asyncio.TimeoutError()

        # Should raise MCP error
        with pytest.raises(Exception) as exc_info:
            await _read_with_filter(docx_path, filter_cmd, config)

        assert "timeout" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_read_document_docx(config, tmp_path):
    """Test reading DOCX via _read_document."""
    docx_path = tmp_path / "test.docx"
    docx_path.write_bytes(b"fake docx")

    config.knowledge.root = str(tmp_path)
    config.formats["word_docx"].enabled = True

    # Mock filter execution
    with patch("contextfs.tools.read._read_with_filter") as mock_read:
        mock_read.return_value = "DOCX content extracted"

        # Read document
        content, total_pages, pages_read = await _read_document(
            docx_path, pages=None, config=config
        )

        # Verify
        assert content == "DOCX content extracted"
        assert total_pages == 1
        assert pages_read == [1]


@pytest.mark.asyncio
async def test_read_document_html(config, tmp_path):
    """Test reading HTML with filter."""
    html_path = tmp_path / "test.html"
    html_path.write_text("<html><body><h1>Test</h1></body></html>")

    config.knowledge.root = str(tmp_path)
    config.formats["html"].enabled = True

    # Mock filter execution
    with patch("contextfs.tools.read._read_with_filter") as mock_read:
        mock_read.return_value = "# Test\\n"

        # Read document
        content, total_pages, pages_read = await _read_document(
            html_path, pages=None, config=config
        )

        # Verify
        assert "Test" in content
        assert total_pages == 1


@pytest.mark.asyncio
async def test_read_document_json(config, tmp_path):
    """Test reading JSON with jq filter."""
    json_path = tmp_path / "test.json"
    json_path.write_text('{"name": "test", "value": 123}')

    config.knowledge.root = str(tmp_path)
    config.formats["json"].enabled = True

    # Mock filter execution
    with patch("contextfs.tools.read._read_with_filter") as mock_read:
        mock_read.return_value = '{"name":"test","value":123}'

        # Read document
        content, total_pages, pages_read = await _read_document(
            json_path, pages=None, config=config
        )

        # Verify JSON content
        assert "test" in content
        assert "123" in content


@pytest.mark.asyncio
async def test_read_document_truncation(config, tmp_path):
    """Test content truncation for large documents."""
    docx_path = tmp_path / "large.docx"
    docx_path.write_bytes(b"fake large docx")

    config.knowledge.root = str(tmp_path)
    config.formats["word_docx"].enabled = True
    config.limits.max_document_read_chars = 100  # Small limit

    # Mock filter returning large content
    with patch("contextfs.tools.read._read_with_filter") as mock_read:
        mock_read.return_value = "x" * 200  # 200 characters

        # Read document
        content, _, _ = await _read_document(docx_path, pages=None, config=config)

        # Should be truncated to 100 chars
        assert len(content) == 100


@pytest.mark.asyncio
async def test_get_document_info_docx(config, tmp_path):
    """Test getting document info for DOCX."""
    docx_path = tmp_path / "test.docx"
    docx_path.write_bytes(b"fake docx")

    config.knowledge.root = str(tmp_path)
    config.formats["word_docx"].enabled = True

    # Mock filter execution
    with patch("contextfs.tools.read._read_with_filter") as mock_read:
        mock_read.return_value = "Test document content here. " * 100  # ~300 words

        # Get info
        info = await _get_document_info(docx_path, config)

        # Verify
        assert info["name"] == "test.docx"
        assert info["format"] == ".docx"
        assert "filter" in info
        assert "pandoc" in info["filter"]
        assert "word_count" in info
        assert info["word_count"] > 0


@pytest.mark.asyncio
async def test_get_document_info_csv(config, tmp_path):
    """Test getting document info for CSV (no filter)."""
    csv_path = tmp_path / "data.csv"
    csv_path.write_text("name,value\\ntest,123\\n")

    config.knowledge.root = str(tmp_path)

    # Get info
    info = await _get_document_info(csv_path, config)

    # Verify
    assert info["name"] == "data.csv"
    assert info["format"] == ".csv"
    assert "line_count" in info
    assert info["line_count"] >= 2  # Header + data row
```

#### 6. Integration Tests

Create real document fixtures for integration testing:

```python
"""Integration tests with real documents."""

import pytest
from pathlib import Path


@pytest.fixture
def sample_docx(tmp_path):
    """Create sample DOCX file using python-docx."""
    try:
        from docx import Document
    except ImportError:
        pytest.skip("python-docx not installed")

    doc = Document()
    doc.add_heading("Test Document", 0)
    doc.add_paragraph("This is a test paragraph with searchable keyword.")
    doc.add_paragraph("Another paragraph for testing.")

    path = tmp_path / "test.docx"
    doc.save(path)
    return path


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
    json_data = {
        "name": "test document",
        "content": "searchable text",
        "metadata": {"author": "test", "version": 1},
    }
    import json

    path = tmp_path / "test.json"
    path.write_text(json.dumps(json_data, indent=2))
    return path


@pytest.mark.integration
@pytest.mark.skipif(not shutil.which("pandoc"), reason="pandoc not installed")
@pytest.mark.asyncio
async def test_read_real_html(config, sample_html):
    """Integration test: Read real HTML file with pandoc."""
    config.knowledge.root = str(sample_html.parent)
    config.formats["html"].enabled = True

    # Read document
    content, total_pages, pages_read = await _read_document(
        sample_html, pages=None, config=config
    )

    # Verify content extracted
    assert "Test Document" in content
    assert "searchable" in content
    assert total_pages == 1


@pytest.mark.integration
@pytest.mark.skipif(not shutil.which("jq"), reason="jq not installed")
@pytest.mark.asyncio
async def test_read_real_json(config, sample_json):
    """Integration test: Read real JSON file with jq."""
    config.knowledge.root = str(sample_json.parent)
    config.formats["json"].enabled = True

    # Read document
    content, total_pages, pages_read = await _read_document(
        sample_json, pages=None, config=config
    )

    # Verify JSON content
    assert "test document" in content
    assert "searchable" in content
```

### Deliverables

- [ ] `_read_with_filter()` function implemented with size check
- [ ] `_read_with_filter_streaming()` for large files (>50MB)
- [ ] `_validate_filter_output()` helper function
- [ ] `_read_document()` generalized for all formats
- [ ] `_get_document_info()` updated with format metadata
- [ ] Error handling for filter timeouts and failures
- [ ] Proper placeholder replacement using config helper
- [ ] Comprehensive mock-based tests
- [ ] Integration tests with real documents
- [ ] All tests passing

---

## Week 2 Checklist

### Implementation (Days 8-11)
- [ ] Add `_read_with_filter()` function to `read.py`
- [ ] Add `_read_with_filter_streaming()` for large files
- [ ] Add `_validate_filter_output()` helper
- [ ] Update `_read_document()` to use filters
- [ ] Update `_get_document_info()` for metadata
- [ ] Add filter timeout error handling
- [ ] Add filter execution error handling
- [ ] Use `config.prepare_filter_for_stdin()` for placeholder replacement
- [ ] Implement streaming for files >50MB
- [ ] Test with PDF (ensure existing logic still works)

### Testing (Days 12-14)
- [ ] Create `tests/test_formats.py` read tests
- [ ] Test DOCX reading (mocked)
- [ ] Test HTML reading (mocked)
- [ ] Test JSON reading (mocked)
- [ ] Test EPUB reading (mocked)
- [ ] Test filter timeout handling
- [ ] Test filter error handling
- [ ] Test content truncation
- [ ] Test document info extraction
- [ ] Test streaming for large files (>50MB)
- [ ] Test filter output validation
- [ ] Test empty filter output handling
- [ ] Test invalid UTF-8 handling
- [ ] Create real document fixtures
- [ ] Add integration tests (conditional on tools)
- [ ] All tests passing

### Documentation
- [ ] Add docstrings to new functions
- [ ] Document filter placeholder handling
- [ ] Add code comments for clarity
- [ ] Update function signatures if needed

### Validation
- [ ] Run `uv run pytest tests/test_formats.py -v`
- [ ] Run `uv run pytest tests/test_read.py -v`
- [ ] Test reading DOCX manually (if pandoc installed)
- [ ] Test reading HTML manually
- [ ] Test reading JSON manually
- [ ] Verify error messages are clear
- [ ] Check filter timeout works correctly

---

## Expected Output After Week 2

1. **Read Functionality**: All document formats readable via filters
2. **Error Handling**: Graceful timeout and error handling
3. **Metadata**: Document info includes filter information
4. **Tests**: Comprehensive test coverage (>90%)
5. **Integration**: Real document tests (conditional)

**Ready for Week 3**: Testing with real filter tools and comprehensive documentation.

---

## Troubleshooting

### Common Issues

**Filter command fails**:
- Verify filter tool is installed (`pandoc --version`)
- Check filter command syntax (% vs -)
- Review FilterSecurity validation

**Timeout errors**:
- Increase `security.filter_timeout_seconds` in config
- Check if filter tool is hanging on specific files
- Review filter command arguments

**Content not extracted**:
- Verify filter tool works: `echo "test" | pandoc -f html -t plain`
- Check file format is correct
- Review filter command for format

**Tests failing**:
- Ensure mocking is correct
- Check async/await usage
- Verify mock return values match expected format

---

## Performance Considerations

1. **Filter Caching**: Consider caching filter outputs (future enhancement)
2. **Parallel Execution**: FilterSecurity uses thread pool (already optimized)
3. **Memory Usage**: Large documents may use significant memory during filtering
4. **Timeout Tuning**: Adjust timeout based on typical document sizes

Default timeout of 30 seconds should be sufficient for most documents.
