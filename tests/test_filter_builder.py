"""Tests for filter arguments builder."""

import pytest

from fathom_mcp.config import Config, FormatConfig
from fathom_mcp.search.filter_builder import FilterArgumentsBuilder


@pytest.fixture
def test_config_with_filters(temp_knowledge_dir):
    """Config with multiple filter formats enabled."""
    return Config(
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
            "markdown": FormatConfig(
                extensions=[".md"],
                filter=None,  # No filter
                enabled=True,
            ),
            "odt": FormatConfig(
                extensions=[".odt"],
                filter="pandoc --wrap=preserve -f odt -t plain % -o -",
                enabled=False,  # Disabled
            ),
        },
    )


@pytest.fixture
def test_config_no_filters(temp_knowledge_dir):
    """Config with no filters enabled."""
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


def test_build_filter_args_multiple_formats(test_config_with_filters):
    """Test building filter args with multiple enabled formats."""
    builder = FilterArgumentsBuilder(test_config_with_filters)
    args = builder.build_filter_args()

    # Should have 2 filters (pdf and docx)
    assert len(args) == 2

    # Check PDF filter
    pdf_filter = next((a for a in args if "pdf:" in a), None)
    assert pdf_filter is not None
    assert pdf_filter == "--filter=pdf:pdftotext % -"

    # Check DOCX filter
    docx_filter = next((a for a in args if "docx:" in a), None)
    assert docx_filter is not None
    assert docx_filter == "--filter=docx:pandoc --wrap=preserve -f docx -t plain % -o -"


def test_build_filter_args_no_filters(test_config_no_filters):
    """Test building filter args when no filters are enabled."""
    builder = FilterArgumentsBuilder(test_config_no_filters)
    args = builder.build_filter_args()

    assert len(args) == 0
    assert args == []


def test_has_filters_true(test_config_with_filters):
    """Test has_filters returns True when filters exist."""
    builder = FilterArgumentsBuilder(test_config_with_filters)
    assert builder.has_filters() is True


def test_has_filters_false(test_config_no_filters):
    """Test has_filters returns False when no filters exist."""
    builder = FilterArgumentsBuilder(test_config_no_filters)
    assert builder.has_filters() is False


def test_get_filter_extensions(test_config_with_filters):
    """Test getting list of extensions with filters."""
    builder = FilterArgumentsBuilder(test_config_with_filters)
    extensions = builder.get_filter_extensions()

    # Should include pdf and docx, but not md (no filter) or odt (disabled)
    assert ".pdf" in extensions
    assert ".docx" in extensions
    assert ".md" not in extensions
    assert ".odt" not in extensions


def test_get_filter_summary(test_config_with_filters):
    """Test generating human-readable filter summary."""
    builder = FilterArgumentsBuilder(test_config_with_filters)
    summary = builder.get_filter_summary()

    assert "Configured document filters:" in summary
    assert "pdf" in summary
    assert "pdftotext" in summary
    assert "docx" in summary
    assert "pandoc" in summary
    # Disabled format should not be included
    assert "odt" not in summary or "(.odt):" not in summary


def test_get_filter_summary_empty(test_config_no_filters):
    """Test filter summary when no filters configured."""
    builder = FilterArgumentsBuilder(test_config_no_filters)
    summary = builder.get_filter_summary()

    assert "Configured document filters:" in summary
    assert "(none)" in summary


def test_validate_filters(test_config_with_filters):
    """Test filter validation against security policy."""
    builder = FilterArgumentsBuilder(test_config_with_filters)
    results = builder.validate_filters()

    # PDF should validate (pdftotext is in whitelist)
    assert results["pdf"] is True

    # Markdown has no filter, should be True
    assert results["markdown"] is True

    # ODT is disabled, should still validate as True (no validation needed)
    assert results["odt"] is True


def test_filter_multiple_extensions():
    """Test filter with multiple extensions for same format."""
    config = Config(
        knowledge={"root": "."},
        formats={
            "text": FormatConfig(
                extensions=[".txt", ".text", ".log"],
                filter="cat %",
                enabled=True,
            ),
        },
    )

    builder = FilterArgumentsBuilder(config)
    args = builder.build_filter_args()

    assert len(args) == 1
    # Should combine all extensions
    assert "txt,text,log:" in args[0]


def test_filter_complex_command():
    """Test filter with complex shell command."""
    config = Config(
        knowledge={"root": "."},
        formats={
            "docx": FormatConfig(
                extensions=[".docx"],
                filter="pandoc --wrap=preserve -f docx -t plain % -o -",
                enabled=True,
            ),
        },
    )

    builder = FilterArgumentsBuilder(config)
    args = builder.build_filter_args()

    assert len(args) == 1
    assert "--filter=docx:pandoc --wrap=preserve -f docx -t plain % -o -" in args[0]


def test_filter_disabled_format():
    """Test that disabled formats are not included in filter args."""
    config = Config(
        knowledge={"root": "."},
        formats={
            "pdf": FormatConfig(
                extensions=[".pdf"],
                filter="pdftotext % -",
                enabled=False,  # Disabled
            ),
        },
    )

    builder = FilterArgumentsBuilder(config)
    args = builder.build_filter_args()

    assert len(args) == 0


def test_filter_with_special_characters():
    """Test filter commands with special characters are handled correctly."""
    config = Config(
        knowledge={"root": "."},
        formats={
            "json": FormatConfig(
                extensions=[".json"],
                filter="jq -r '.'",  # Contains quotes
                enabled=True,
            ),
        },
    )

    builder = FilterArgumentsBuilder(config)
    args = builder.build_filter_args()

    assert len(args) == 1
    # Should preserve the quotes
    assert "--filter=json:jq -r '.'" in args[0]
