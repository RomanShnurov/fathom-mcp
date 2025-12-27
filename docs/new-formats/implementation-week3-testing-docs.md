# Week 3 Implementation: Testing & Documentation

## Overview

**Timeline**: Week 3 (Days 15-21)
**Focus**: Real-world testing and comprehensive documentation
**Phases**: 2A (Integration Testing) + 2B (Documentation)
**Prerequisites**: Weeks 1-2 complete (configuration, search, and read tools ready)

---

## Goals

1. Set up Docker environment with all filter tools
2. Create real document fixtures
3. Run end-to-end integration tests
4. Write comprehensive user documentation
5. Create installation and troubleshooting guides
6. Update project documentation

---

## Phase 2A: Real-World Testing & Integration (Days 15-18)

### Task 1: Filter Tool Validation on Startup

**Create `src/contextfs/tools/validation.py`**:

```python
"""Filter tool validation for runtime detection."""

import asyncio
import shutil
from typing import Dict

from contextfs.config import Config
from contextfs.security import FilterSecurity
from contextfs.logging import logger


async def validate_filter_tools(config: Config) -> Dict[str, bool]:
    """Validate that required filter tools are available and working.

    Auto-disables formats when tools are unavailable.

    Args:
        config: Server configuration

    Returns:
        Dict mapping format name to availability status
    """
    results = {}

    for fmt_name, fmt_config in config.formats.items():
        if not fmt_config.enabled or not fmt_config.filter:
            results[fmt_name] = True  # No tool needed
            continue

        # Extract tool name from filter command
        tool_name = fmt_config.filter.split()[0]

        # Check if tool exists in PATH
        if not shutil.which(tool_name):
            results[fmt_name] = False
            logger.warning(
                f"Filter tool '{tool_name}' for format '{fmt_name}' not found. "
                f"Disabling {fmt_name} support."
            )
            # Auto-disable format
            fmt_config.enabled = False
            continue

        # Test tool works with simple input
        try:
            filter_security = FilterSecurity(config)
            test_input = b"test"
            filter_cmd_stdin = config.prepare_filter_for_stdin(fmt_config.filter)

            await asyncio.wait_for(
                filter_security.run_secure_filter(
                    filter_cmd_stdin,
                    test_input,
                ),
                timeout=5,
            )
            results[fmt_name] = True
            logger.debug(f"Filter tool '{tool_name}' for format '{fmt_name}' validated")

        except Exception as e:
            logger.warning(
                f"Filter tool test failed for '{fmt_name}': {e}. "
                f"Disabling {fmt_name} support."
            )
            fmt_config.enabled = False
            results[fmt_name] = False

    return results
```

**Update `src/contextfs/server.py`**:

```python
async def create_server(config: Config) -> Server:
    """Create MCP server instance.

    Args:
        config: Server configuration

    Returns:
        Configured MCP server
    """
    from contextfs.tools.validation import validate_filter_tools

    server = Server("contextfs")

    # Validate filter tools and auto-disable unavailable formats
    validation_results = await validate_filter_tools(config)
    enabled_count = sum(1 for available in validation_results.values() if available)
    total_count = len(validation_results)
    logger.info(f"Filter tools validated: {enabled_count}/{total_count} formats available")

    # Generate .ugrep config only if filters are available
    if config.needs_document_filters():
        try:
            ugrep_path = config.write_ugrep_config()
            logger.info(f"Generated .ugrep config: {ugrep_path}")
        except Exception as e:
            logger.warning(f"Failed to generate .ugrep config: {e}")
    else:
        logger.info("No document filters enabled, skipping .ugrep config generation")

    # Register tools
    register_all_tools(server, config)

    return server
```

### Task 2: Docker Test Environment

#### Create Dockerfile

**File**: `Dockerfile.test`

```dockerfile
FROM python:3.12-slim

# Install system dependencies and filter tools
RUN apt-get update && apt-get install -y \
    # ugrep
    ugrep \
    # PDF tools
    poppler-utils \
    # Document converters
    pandoc \
    antiword \
    catdoc \
    # Data tools
    jq \
    xmllint \
    # Build tools
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install package with dev dependencies
RUN pip install --no-cache-dir -e ".[dev]"

# Copy tests
COPY tests/ ./tests/
COPY config.example.yaml ./

# Run tests
CMD ["pytest", "tests/", "-v", "--cov=src/contextfs", "--cov-report=term-missing"]
```

#### Create Docker Compose for Testing

**File**: `docker-compose.test.yml`

```yaml
version: '3.8'

services:
  test:
    build:
      context: .
      dockerfile: Dockerfile.test
    volumes:
      - ./tests:/app/tests
      - ./src:/app/src
      - ./test-reports:/app/test-reports
    environment:
      - PYTHONPATH=/app/src
      - CFS_KNOWLEDGE__ROOT=/app/test-data
    command: >
      bash -c "
        echo 'Running format tests...' &&
        pytest tests/test_formats.py -v --cov=src/contextfs --cov-report=html:test-reports/coverage &&
        echo 'Running integration tests...' &&
        pytest tests/ -v -m integration
      "
```

#### Create CI/CD Workflow

**File**: `.github/workflows/test-formats.yml`

```yaml
name: Format Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test-formats:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install ugrep
        run: |
          sudo apt-get update
          sudo apt-get install -y ugrep

      - name: Install filter tools
        run: |
          sudo apt-get install -y \
            poppler-utils \
            pandoc \
            antiword \
            jq

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"

      - name: Verify filter tools
        run: |
          python scripts/verify-filters.py

      - name: Run format tests
        run: |
          pytest tests/test_formats.py -v --cov=src/contextfs

      - name: Upload coverage
        uses: codecov/codecov-action@v5
        with:
          file: ./coverage.xml
          flags: formats

  docker-test:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Build test image
        run: |
          docker build -f Dockerfile.test -t contextfs-test .

      - name: Run tests in Docker
        run: |
          docker run --rm contextfs-test

      - name: Extract coverage report
        run: |
          docker run --rm -v $(pwd)/test-reports:/app/test-reports contextfs-test \
            pytest tests/ -v --cov=src/contextfs --cov-report=html:/app/test-reports/coverage
```

### Task 2: Real Document Fixtures

#### Create Document Generator

**File**: `tests/fixtures/generate_documents.py`

```python
#!/usr/bin/env python3
"""Generate test documents for integration testing."""

from pathlib import Path


def generate_docx(output_path: Path):
    """Generate sample DOCX file."""
    try:
        from docx import Document
    except ImportError:
        print("Warning: python-docx not installed, skipping DOCX generation")
        return

    doc = Document()
    doc.add_heading("Sample DOCX Document", 0)
    doc.add_paragraph(
        "This is a test paragraph containing the keyword searchable for testing purposes."
    )
    doc.add_paragraph("Machine learning and artificial intelligence are important topics.")
    doc.add_paragraph("Python programming language is widely used in data science.")

    doc.save(output_path)
    print(f"Generated: {output_path}")


def generate_html(output_path: Path):
    """Generate sample HTML file."""
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Sample HTML Document</title>
</head>
<body>
    <h1>Sample HTML Document</h1>
    <p>This is a test paragraph containing the keyword <strong>searchable</strong>.</p>
    <p>Machine learning and artificial intelligence are important topics.</p>
    <p>Python programming language is widely used in data science.</p>
    <ul>
        <li>Item 1</li>
        <li>Item 2</li>
        <li>Item 3</li>
    </ul>
</body>
</html>
"""
    output_path.write_text(html)
    print(f"Generated: {output_path}")


def generate_json(output_path: Path):
    """Generate sample JSON file."""
    import json

    data = {
        "title": "Sample JSON Document",
        "content": "This is searchable content for testing purposes.",
        "keywords": ["machine learning", "artificial intelligence", "Python"],
        "metadata": {
            "author": "Test Author",
            "date": "2025-12-26",
            "version": "1.0",
        },
        "items": [
            {"id": 1, "name": "Item 1", "description": "First test item"},
            {"id": 2, "name": "Item 2", "description": "Second test item"},
        ],
    }

    output_path.write_text(json.dumps(data, indent=2))
    print(f"Generated: {output_path}")


def generate_xml(output_path: Path):
    """Generate sample XML file."""
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<document>
    <title>Sample XML Document</title>
    <content>This is searchable content for testing purposes.</content>
    <keywords>
        <keyword>machine learning</keyword>
        <keyword>artificial intelligence</keyword>
        <keyword>Python</keyword>
    </keywords>
    <metadata>
        <author>Test Author</author>
        <date>2025-12-26</date>
    </metadata>
    <items>
        <item id="1">
            <name>Item 1</name>
            <description>First test item</description>
        </item>
        <item id="2">
            <name>Item 2</name>
            <description>Second test item</description>
        </item>
    </items>
</document>
"""
    output_path.write_text(xml)
    print(f"Generated: {output_path}")


def generate_csv(output_path: Path):
    """Generate sample CSV file."""
    csv = """name,value,category,description
Item 1,100,searchable,First test item with machine learning
Item 2,200,analysis,Second test item with artificial intelligence
Item 3,300,programming,Third test item with Python development
"""
    output_path.write_text(csv)
    print(f"Generated: {output_path}")


def generate_markdown(output_path: Path):
    """Generate sample Markdown file."""
    md = """# Sample Markdown Document

This is a test paragraph containing the keyword **searchable**.

## Topics

- Machine learning
- Artificial intelligence
- Python programming

## Content

Machine learning and artificial intelligence are important topics in modern technology.
Python programming language is widely used in data science and web development.

### Code Example

```python
def hello_world():
    print("Hello, searchable world!")
```

## Conclusion

This document is for testing purposes.
"""
    output_path.write_text(md)
    print(f"Generated: {output_path}")


def main():
    """Generate all test documents."""
    fixtures_dir = Path(__file__).parent
    output_dir = fixtures_dir / "documents"
    output_dir.mkdir(exist_ok=True)

    print("Generating test documents...")
    print()

    generate_docx(output_dir / "sample.docx")
    generate_html(output_dir / "sample.html")
    generate_json(output_dir / "sample.json")
    generate_xml(output_dir / "sample.xml")
    generate_csv(output_dir / "sample.csv")
    generate_markdown(output_dir / "sample.md")

    print()
    print(f"✅ Test documents generated in {output_dir}")


if __name__ == "__main__":
    main()
```

#### Update conftest.py

**File**: `tests/conftest.py`

```python
import pytest
from pathlib import Path
import shutil


@pytest.fixture
def test_documents(tmp_path):
    """Copy test documents to temp directory."""
    fixtures_dir = Path(__file__).parent / "fixtures" / "documents"

    if not fixtures_dir.exists():
        pytest.skip("Test documents not generated. Run tests/fixtures/generate_documents.py")

    # Copy to temp directory
    dest_dir = tmp_path / "documents"
    shutil.copytree(fixtures_dir, dest_dir)

    return dest_dir


@pytest.fixture
def docx_file(test_documents):
    """Path to sample DOCX file."""
    return test_documents / "sample.docx"


@pytest.fixture
def html_file(test_documents):
    """Path to sample HTML file."""
    return test_documents / "sample.html"


@pytest.fixture
def json_file(test_documents):
    """Path to sample JSON file."""
    return test_documents / "sample.json"
```

### Task 3: Performance Benchmarks

**Add `pytest-benchmark` to test dependencies**:

```toml
# pyproject.toml
[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.21",
    "pytest-cov>=4.0",
    "pytest-benchmark>=4.0",  # NEW
    "ruff>=0.1.0",
]
```

**Create `tests/test_benchmarks.py`**:

```python
"""Performance benchmarks for multi-format support."""

import pytest
from pathlib import Path

from contextfs.config import Config
from contextfs.tools.read import _read_with_filter
from contextfs.search.ugrep import UgrepEngine


@pytest.mark.benchmark
def test_config_generation_performance(benchmark, config):
    """Benchmark .ugrep config generation."""
    config.formats["word_docx"].enabled = True
    config.formats["html"].enabled = True
    config.formats["json"].enabled = True

    result = benchmark(config.generate_ugrep_config)
    assert len(result) > 0
    # Should complete in <10ms
    assert benchmark.stats['mean'] < 0.01


@pytest.mark.benchmark
@pytest.mark.asyncio
async def test_filter_placeholder_performance(benchmark, config):
    """Benchmark filter placeholder replacement."""
    filter_cmd = "pandoc --wrap=preserve -f docx -t plain % -o -"

    result = benchmark(config.prepare_filter_for_stdin, filter_cmd)
    assert " - " in result
    # Should complete in <1ms
    assert benchmark.stats['mean'] < 0.001


@pytest.mark.benchmark
def test_needs_filters_check_performance(benchmark, config):
    """Benchmark filter detection performance."""
    config.formats["word_docx"].enabled = True

    result = benchmark(config.needs_document_filters)
    assert result is True
    # Should complete in <1ms
    assert benchmark.stats['mean'] < 0.001
```

### Task 4: Integration Tests with Retries

**Add `tenacity` for retry logic**:

```toml
# pyproject.toml
[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.21",
    "pytest-cov>=4.0",
    "pytest-benchmark>=4.0",
    "tenacity>=8.0",  # NEW: For test retries
    "ruff>=0.1.0",
]
```

**File**: `tests/test_integration_formats.py`

```python
"""Integration tests for multi-format support with real tools."""

import pytest
import shutil
from pathlib import Path
from tenacity import retry, stop_after_attempt, wait_fixed

from contextfs.config import Config
from contextfs.tools.read import _read_document, _get_document_info
from contextfs.search.ugrep import UgrepEngine


# Check which tools are available
PANDOC_AVAILABLE = shutil.which("pandoc") is not None
JQ_AVAILABLE = shutil.which("jq") is not None
UG_PLUS_AVAILABLE = shutil.which("ug+") is not None or shutil.which("ug") is not None


@pytest.mark.integration
@pytest.mark.skipif(not PANDOC_AVAILABLE, reason="pandoc not installed")
@pytest.mark.asyncio
@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
async def test_read_docx_real(config, docx_file):
    """Integration test: Read real DOCX file with retry.

    Retries up to 3 times to handle flaky filter tool behavior.
    """
    config.knowledge.root = str(docx_file.parent)
    config.formats["word_docx"].enabled = True

    # Read document
    content, total_pages, pages_read = await _read_document(
        docx_file, pages=None, config=config
    )

    # Verify content
    assert len(content) > 0
    assert "searchable" in content.lower()
    assert "machine learning" in content.lower()
    assert total_pages == 1


@pytest.mark.integration
@pytest.mark.skipif(not PANDOC_AVAILABLE, reason="pandoc not installed")
@pytest.mark.asyncio
async def test_read_html_real(config, html_file):
    """Integration test: Read real HTML file."""
    config.knowledge.root = str(html_file.parent)
    config.formats["html"].enabled = True

    # Read document
    content, total_pages, pages_read = await _read_document(
        html_file, pages=None, config=config
    )

    # Verify content
    assert len(content) > 0
    assert "Sample HTML Document" in content
    assert "searchable" in content.lower()


@pytest.mark.integration
@pytest.mark.skipif(not JQ_AVAILABLE, reason="jq not installed")
@pytest.mark.asyncio
async def test_read_json_real(config, json_file):
    """Integration test: Read real JSON file."""
    config.knowledge.root = str(json_file.parent)
    config.formats["json"].enabled = True

    # Read document
    content, total_pages, pages_read = await _read_document(
        json_file, pages=None, config=config
    )

    # Verify content
    assert len(content) > 0
    assert "Sample JSON Document" in content or "searchable" in content.lower()


@pytest.mark.integration
@pytest.mark.skipif(not PANDOC_AVAILABLE, reason="pandoc not installed")
@pytest.mark.asyncio
async def test_get_docx_info_real(config, docx_file):
    """Integration test: Get DOCX document info."""
    config.knowledge.root = str(docx_file.parent)
    config.formats["word_docx"].enabled = True

    # Get info
    info = await _get_document_info(docx_file, config)

    # Verify
    assert info["name"] == "sample.docx"
    assert info["format"] == ".docx"
    assert "filter" in info
    assert "pandoc" in info["filter"]
    assert "word_count" in info or "estimated_pages" in info


@pytest.mark.integration
@pytest.mark.skipif(not UG_PLUS_AVAILABLE or not PANDOC_AVAILABLE, reason="ug+ or pandoc not installed")
@pytest.mark.asyncio
async def test_search_multiformat_real(config, test_documents):
    """Integration test: Search across multiple formats."""
    config.knowledge.root = str(test_documents)
    config.formats["word_docx"].enabled = True
    config.formats["html"].enabled = True
    config.formats["json"].enabled = True

    # Generate .ugrep config
    config.write_ugrep_config()

    # Create search engine
    engine = UgrepEngine(config)

    # Search for common keyword
    results = await engine.search(
        query="searchable",
        path=test_documents,
        recursive=True,
    )

    # Should find matches in multiple formats
    assert len(results) > 0

    # Check we got matches from different file types
    file_types = {Path(r.file_path).suffix for r in results}
    assert len(file_types) >= 2  # At least 2 different formats


@pytest.mark.integration
@pytest.mark.skipif(not UG_PLUS_AVAILABLE or not PANDOC_AVAILABLE, reason="ug+ or pandoc not installed")
@pytest.mark.asyncio
async def test_boolean_search_multiformat(config, test_documents):
    """Integration test: Boolean search across formats."""
    config.knowledge.root = str(test_documents)
    config.formats["word_docx"].enabled = True
    config.formats["html"].enabled = True

    config.write_ugrep_config()
    engine = UgrepEngine(config)

    # Boolean AND query
    results = await engine.search(
        query="machine learning",
        path=test_documents,
        recursive=True,
    )

    # Should find matches
    assert len(results) > 0

    # Verify match content
    for result in results:
        content_lower = result.match_text.lower()
        assert "machine" in content_lower and "learning" in content_lower
```

### Deliverables

- [ ] Docker test environment created
- [ ] CI/CD workflow configured
- [ ] Real document fixtures generated
- [ ] Integration tests passing
- [ ] Performance benchmarks documented

---

## Phase 2B: Documentation & Polish (Days 19-21)

### Task 1: Create `docs/supported-formats.md`

```markdown
# Supported Document Formats

## Overview

contextfs supports searching and reading multiple document formats through the ugrep search engine and external filter tools. This document describes all supported formats, required tools, and installation instructions.

## Format Support Matrix

| Format | Extensions | Filter Tool | Required | Platform | Status |
|--------|------------|-------------|----------|----------|--------|
| **PDF** | .pdf | pdftotext | Yes | All | ✅ Default |
| **Markdown** | .md, .markdown | - | No | All | ✅ Default |
| **Text** | .txt, .rst | - | No | All | ✅ Default |
| **CSV** | .csv | - | No | All | ✅ Default |
| **Word (modern)** | .docx | pandoc | No | All | 🔧 Optional |
| **Word (legacy)** | .doc | antiword | No | Linux/macOS | 🔧 Optional |
| **OpenDocument** | .odt | pandoc | No | All | 🔧 Optional |
| **EPUB** | .epub | pandoc | No | All | 🔧 Optional |
| **HTML** | .html, .htm | pandoc | No | All | 🔧 Optional |
| **RTF** | .rtf | pandoc | No | All | 🔧 Optional |
| **JSON** | .json | jq | No | All | 🔧 Optional |
| **XML** | .xml | pandoc | No | All | 🔧 Optional |

**Legend**:
- ✅ Enabled by default (no external tools needed, or tool commonly installed)
- 🔧 Disabled by default (requires external tool installation and configuration)

## Installation

### Quick Start (Recommended)

For most use cases, install **pandoc** and **jq**:

```bash
# macOS
brew install pandoc jq

# Linux (Ubuntu/Debian)
sudo apt update
sudo apt install pandoc jq

# Windows (Chocolatey)
choco install pandoc jq
```

This enables: DOCX, ODT, EPUB, HTML, RTF, JSON, XML support.

### Full Installation

For complete format support including legacy .doc files:

```bash
# macOS
brew install pandoc jq antiword poppler

# Linux (Ubuntu/Debian)
sudo apt install pandoc jq antiword poppler-utils

# Windows (Chocolatey)
choco install pandoc jq poppler
# Note: antiword limited support on Windows
```

### Verification

After installation, verify tools are available:

```bash
python scripts/verify-filters.py
```

Expected output:
```
ContextFS Filter Tool Verification

✅ Installed     pdftotext       - Formats: PDF
✅ Installed     pandoc          - Formats: DOCX, ODT, EPUB, HTML, RTF, XML
✅ Installed     jq              - Formats: JSON
⚠️  Optional     antiword        - Install: antiword

Summary:
  Installed tools: 3/4
  ✅ All required tools installed
```

## Configuration

### Enable Formats

Edit `config.yaml` to enable desired formats:

```yaml
formats:
  word_docx:
    enabled: true  # Enable DOCX support

  html:
    enabled: true  # Enable HTML support

  json:
    enabled: true  # Enable JSON support
```

### Custom Filter Commands

Advanced users can customize filter commands:

```yaml
formats:
  html:
    enabled: true
    filter: "html2text -"  # Use html2text instead of pandoc
    extensions: [".html", ".htm"]
```

## How It Works

### ugrep+ and .ugrep Configuration

contextfs uses ugrep's `ug+` command which automatically applies document filters based on file extensions.

When the server starts, it generates a `.ugrep` configuration file in your knowledge root directory:

```
### Generated by contextfs MCP server
### Knowledge root: /path/to/documents

# Document filters
--filter="pdf:pdftotext % -"
--filter="docx,odt,epub,rtf:pandoc --wrap=preserve -t plain % -o -"
--filter="html,htm:pandoc --wrap=preserve -f html -t plain % -o -"
--filter="json:jq -r '.'"

# Performance settings
--context=3
--line-number
--with-filename
```

### Search Workflow

1. User searches for "machine learning"
2. contextfs runs: `ug+ -% "machine learning" /path/to/documents`
3. ugrep reads `.ugrep` config
4. For each file type:
   - .txt, .md, .csv: Search directly
   - .pdf: Filter through `pdftotext`, then search
   - .docx: Filter through `pandoc`, then search
5. Results returned with file paths and context

## Troubleshooting

### Filter tool not found

**Error**: `filter tool 'pandoc' not found`

**Solution**:
1. Install pandoc: `brew install pandoc` (macOS) or `apt install pandoc` (Linux)
2. Verify: `pandoc --version`
3. Restart contextfs server

### Timeout errors

**Error**: `Filter timeout reading document.docx (>30s)`

**Solution**:
Increase timeout in `config.yaml`:
```yaml
security:
  filter_timeout_seconds: 60  # Increase to 60 seconds
```

### Empty search results

**Issue**: No results even though document contains search term

**Possible causes**:
1. Format not enabled in config
2. Filter tool not installed
3. .ugrep file not generated

**Solution**:
```bash
# Check config
python scripts/verify-filters.py

# Verify .ugrep file exists
ls -la /path/to/knowledge/root/.ugrep

# Manually regenerate .ugrep
# (Will be regenerated on next server start)
```

### Permission errors

**Error**: `Permission denied writing .ugrep`

**Solution**:
Ensure contextfs has write permission to knowledge root directory:
```bash
chmod 755 /path/to/knowledge/root
```

## Security Considerations

### Filter Command Validation

All filter commands are validated before execution:
- Must be in whitelist (security.allowed_filter_commands)
- Commands use stdin (no file path exposure)
- Timeout enforcement prevents hanging processes
- Memory limits (platform-dependent)

### Safe Filter Commands

contextfs uses safe, well-established filter tools:
- **pdftotext**: From poppler-utils, mature and secure
- **pandoc**: Widely used, we only use plain text output
- **antiword**: Simple tool, text output only
- **jq**: JSON processor, identity filter only

### Recommendations

1. Keep filter tools updated
2. Monitor for security advisories (CVEs)
3. Use whitelist mode (default)
4. Review .ugrep file periodically
5. Consider sandboxing in production (Docker)

## Performance

### Typical Performance

| Format | File Size | Filter Time | Notes |
|--------|-----------|-------------|-------|
| PDF | 1 MB | ~0.5s | Fast with pdftotext |
| DOCX | 500 KB | ~1s | Depends on pandoc |
| HTML | 100 KB | ~0.3s | Very fast |
| JSON | 1 MB | ~0.2s | Fast with jq |

### Optimization Tips

1. **Enable only needed formats**: Fewer filters = faster searches
2. **Use file indexing**: For very large collections
3. **Increase timeout for large files**: Adjust filter_timeout_seconds
4. **Consider parallelism**: ugrep supports multi-threading

## FAQ

**Q: Can I add custom file formats?**

A: Yes, add to `formats` in config.yaml with appropriate filter command.

**Q: Do I need all filter tools installed?**

A: No, only install tools for formats you need. Others will be disabled automatically.

**Q: Can I use different filter tools (e.g., html2text instead of pandoc)?**

A: Yes, customize filter commands in config.yaml.

**Q: Will this slow down my searches?**

A: Minimal impact (<5%) if filters are properly installed and configured.

**Q: Can I disable filter caching?**

A: Search results are cached by default. Filters execute on-demand.

## Resources

- [ugrep Documentation](https://ugrep.com/)
- [Pandoc Manual](https://pandoc.org/MANUAL.html)
- [jq Manual](https://stedolan.github.io/jq/manual/)
- [Poppler Utils](https://poppler.freedesktop.org/)
```

### Task 2: Update `README.md`

Add supported formats section:

```markdown
## Supported Formats

contextfs supports searching and reading multiple document formats:

### Default (No Tools Required)
- Markdown (.md, .markdown)
- Plain Text (.txt, .rst)
- CSV (.csv)
- PDF (.pdf) - requires pdftotext

### Optional (Requires External Tools)
- Microsoft Word (.doc, .docx) - requires pandoc or antiword
- OpenDocument (.odt) - requires pandoc
- EPUB (.epub) - requires pandoc
- HTML (.html, .htm) - requires pandoc
- RTF (.rtf) - requires pandoc
- JSON (.json) - requires jq
- XML (.xml) - requires pandoc

See [docs/supported-formats.md](docs/supported-formats.md) for installation instructions.
```

### Task 3: Update `CLAUDE.md`

Add section about format handling:

```markdown
## Format Handling Patterns

### Adding New Document Format

1. Add format to `config.py` formats dict
2. Specify extensions and filter command
3. Add filter command to security whitelist (if needed)
4. Update `.ugrep` file (auto-generated)
5. Add tests to `test_formats.py`
6. Update documentation

Example:
```python
"new_format": FormatConfig(
    extensions=[".xyz"],
    filter="convert_tool % -",
    enabled=False,
),
```

### Filter Command Requirements

- Must read from stdin and write to stdout
- Use `%` placeholder for filename (replaced with `-` for stdin)
- Must output plain text
- Should handle errors gracefully
- Timeout: 30 seconds default
```

### Deliverables

- [ ] `docs/supported-formats.md` created
- [ ] `README.md` updated
- [ ] `CLAUDE.md` updated
- [ ] All documentation reviewed

---

## Week 3 Checklist

### Startup Validation (Day 15)
- [ ] Create `src/contextfs/tools/validation.py`
- [ ] Implement `validate_filter_tools()` function
- [ ] Update `server.py` to call validation on startup
- [ ] Add auto-disable for unavailable tools
- [ ] Add logging for validation results
- [ ] Test validation with missing tools

### Performance Benchmarks (Day 15)
- [ ] Add `pytest-benchmark` to dependencies
- [ ] Create `tests/test_benchmarks.py`
- [ ] Benchmark config generation (<10ms)
- [ ] Benchmark placeholder replacement (<1ms)
- [ ] Benchmark filter detection (<1ms)
- [ ] Run benchmarks and verify performance

### Docker & CI/CD (Day 16)
- [ ] Create `Dockerfile.test`
- [ ] Create `docker-compose.test.yml`
- [ ] Create `.github/workflows/test-formats.yml`
- [ ] Test Docker build locally
- [ ] Verify CI/CD workflow

### Test Fixtures (Day 16)
- [ ] Create `tests/fixtures/generate_documents.py`
- [ ] Generate DOCX fixture
- [ ] Generate HTML fixture
- [ ] Generate JSON fixture
- [ ] Generate XML fixture
- [ ] Generate CSV fixture
- [ ] Update `conftest.py` with fixtures

### Integration Tests with Retries (Days 17-18)
- [ ] Add `tenacity` to dependencies
- [ ] Create `tests/test_integration_formats.py`
- [ ] Add retry decorator to integration tests
- [ ] Test read DOCX (real) with retry
- [ ] Test read HTML (real)
- [ ] Test read JSON (real)
- [ ] Test multi-format search (real)
- [ ] Test boolean search across formats
- [ ] All integration tests passing

### Documentation (Days 19-21)
- [ ] Create `docs/supported-formats.md`
- [ ] Update `README.md`
- [ ] Update `CLAUDE.md`
- [ ] Review all documentation
- [ ] Check for broken links
- [ ] Verify code examples work

### Final Validation
- [ ] Run full test suite: `uv run pytest tests/ -v`
- [ ] Run integration tests: `pytest -m integration`
- [ ] Build Docker image
- [ ] Run tests in Docker
- [ ] Check test coverage (>90%)
- [ ] Review documentation completeness

---

## Expected Output After Week 3

1. **Startup Validation**: Auto-detection and auto-disable of unavailable filter tools
2. **Performance Benchmarks**: All operations <10ms, pytest-benchmark integrated
3. **Docker Environment**: Ready for testing with all tools
4. **CI/CD Pipeline**: Automated testing on all commits
5. **Integration Tests**: Passing with real documents and retry logic
6. **Documentation**: Complete user and developer guides
7. **Error Catalog**: Comprehensive error reference for troubleshooting

**Project Complete**: Multi-format document support fully implemented, tested, and documented with production-ready robustness!

---

## Performance Benchmarks

Expected performance after implementation:

| Operation | Format | File Size | Time | Notes |
|-----------|--------|-----------|------|-------|
| Search | Plain text | 100 KB | <10ms | Baseline |
| Search | PDF | 1 MB | ~500ms | pdftotext overhead |
| Search | DOCX | 500 KB | ~1s | pandoc overhead |
| Search | Multi-format (10 files) | 5 MB total | ~3s | Parallel execution |
| Read | PDF | 1 MB | ~500ms | With filter |
| Read | DOCX | 500 KB | ~1s | With pandoc |
| Read | HTML | 100 KB | ~300ms | With pandoc |

---

## Success Criteria

✅ All functional requirements met:
- 8 new formats searchable and readable
- ug+ command integration working
- .ugrep configuration auto-generated
- Graceful degradation when tools unavailable

✅ All quality requirements met:
- Test coverage >90%
- All tests passing (unit + integration)
- Documentation complete
- No security vulnerabilities

✅ All user experience requirements met:
- Clear error messages
- Installation guide complete
- Troubleshooting documentation
- Migration path documented

**Implementation Complete!**
