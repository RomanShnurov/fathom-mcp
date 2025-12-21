"""Tests for configuration."""

import tempfile
from pathlib import Path

import pytest
import yaml

from file_knowledge_mcp.config import Config, ConfigError, KnowledgeConfig, load_config


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

        assert config.server.name == "file-knowledge-mcp"
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
        assert pdf_filter == "pdftotext - -"

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
