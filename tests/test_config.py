"""Tests for configuration."""

import tempfile
from pathlib import Path

import pytest
import yaml

from fathom_mcp.config import Config, ConfigError, KnowledgeConfig, load_config


def test_knowledge_config_validation():
    """Test KnowledgeConfig validates root exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Valid directory
        config = KnowledgeConfig(root=tmpdir)
        assert config.root.exists()
        assert config.root.is_dir()

    # Non-existent path
    with pytest.raises(ValueError, match="does not exist"):
        KnowledgeConfig(root="/nonexistent/path")


def test_config_defaults():
    """Test Config has sensible defaults."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = Config(knowledge=KnowledgeConfig(root=tmpdir))

        assert config.server.name == "fathom-mcp"
        assert config.server.log_level == "INFO"
        assert config.search.context_lines == 5
        assert config.search.max_results == 50
        assert ".pdf" in config.supported_extensions
        assert ".md" in config.supported_extensions


def test_config_supported_extensions():
    """Test supported_extensions property."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = Config(knowledge=KnowledgeConfig(root=tmpdir))

        exts = config.supported_extensions
        assert ".pdf" in exts
        assert ".md" in exts
        assert ".txt" in exts


def test_config_get_filter_for_extension():
    """Test get_filter_for_extension method."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = Config(knowledge=KnowledgeConfig(root=tmpdir))

        # PDF has filter
        pdf_filter = config.get_filter_for_extension(".pdf")
        assert pdf_filter == "pdftotext % -"

        # Markdown has no filter
        md_filter = config.get_filter_for_extension(".md")
        assert md_filter is None


def test_load_config_from_yaml():
    """Test loading config from YAML file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Create test config
        config_file = root / "test_config.yaml"
        config_data = {
            "knowledge": {"root": str(root)},
            "server": {"log_level": "DEBUG"},
            "search": {"max_results": 100},
        }
        config_file.write_text(yaml.dump(config_data))

        # Load config
        config = load_config(config_file)

        assert config.knowledge.root == root
        assert config.server.log_level == "DEBUG"
        assert config.search.max_results == 100


def test_load_config_file_not_found():
    """Test loading non-existent config file."""
    with pytest.raises(ConfigError, match="not found"):
        load_config("/nonexistent/config.yaml")


def test_needs_document_filters():
    """Test checking if document filters are needed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = Config(knowledge=KnowledgeConfig(root=tmpdir))

        # Default: pdf has filter and is enabled
        assert config.needs_document_filters()

        # Disable all formats first
        for fmt in config.formats.values():
            fmt.enabled = False

        # No filters needed
        assert not config.needs_document_filters()

        # Enable format without filter (CSV)
        config.formats["csv"].enabled = True
        assert not config.needs_document_filters()

        # Enable format with filter (DOCX)
        config.formats["word_docx"].enabled = True
        assert config.needs_document_filters()


def test_get_filter_for_extension_with_and_without_dot():
    """Test getting filter command for extension with and without dot."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = Config(knowledge=KnowledgeConfig(root=tmpdir))
        config.formats["word_docx"].enabled = True

        # Test with dot
        assert config.get_filter_for_extension(".docx") is not None
        assert "pandoc" in config.get_filter_for_extension(".docx")

        # Test without dot
        assert config.get_filter_for_extension("docx") is not None

        # Test disabled format
        config.formats["word_docx"].enabled = False
        assert config.get_filter_for_extension(".docx") is None

        # Test unknown extension
        assert config.get_filter_for_extension(".xyz") is None


def test_prepare_filter_for_stdin():
    """Test filter placeholder replacement."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = Config(knowledge=KnowledgeConfig(root=tmpdir))

        # Test with space-separated placeholder
        cmd = "pandoc --wrap=preserve -f docx -t plain % -o -"
        result = config.prepare_filter_for_stdin(cmd)
        assert result == "pandoc --wrap=preserve -f docx -t plain - -o -"

        # Test with trailing placeholder
        cmd = "antiword -t -w 0 %"
        result = config.prepare_filter_for_stdin(cmd)
        assert result == "antiword -t -w 0 -"

        # Test without placeholder
        cmd = "jq -r '.'"
        result = config.prepare_filter_for_stdin(cmd)
        assert result == "jq -r '.'"


def test_new_formats_defined():
    """Test that all 8 new formats are defined."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = Config(knowledge=KnowledgeConfig(root=tmpdir))

        # Verify all new formats exist
        assert "word_doc" in config.formats
        assert "word_docx" in config.formats
        assert "opendocument" in config.formats
        assert "epub" in config.formats
        assert "html" in config.formats
        assert "rtf" in config.formats
        assert "csv" in config.formats
        assert "json" in config.formats
        assert "xml" in config.formats

        # Verify they are disabled by default (except CSV)
        assert not config.formats["word_doc"].enabled
        assert not config.formats["word_docx"].enabled
        assert not config.formats["opendocument"].enabled
        assert not config.formats["epub"].enabled
        assert not config.formats["html"].enabled
        assert not config.formats["rtf"].enabled
        assert config.formats["csv"].enabled  # CSV is enabled
        assert not config.formats["json"].enabled
        assert not config.formats["xml"].enabled
