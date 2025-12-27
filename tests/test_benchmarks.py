"""Performance benchmarks for multi-format support."""

import pytest


@pytest.mark.benchmark
def test_config_generation_performance(benchmark, config) -> None:
    """Benchmark .ugrep config generation."""
    config.formats["word_docx"].enabled = True
    config.formats["html"].enabled = True
    config.formats["json"].enabled = True

    result = benchmark(config.generate_ugrep_config)
    assert len(result) > 0
    # Should complete in <10ms
    assert benchmark.stats["mean"] < 0.01


@pytest.mark.benchmark
def test_filter_placeholder_performance(benchmark, config) -> None:
    """Benchmark filter placeholder replacement."""
    filter_cmd = "pandoc --wrap=preserve -f docx -t plain % -o -"

    result = benchmark(config.prepare_filter_for_stdin, filter_cmd)
    assert " - " in result
    # Should complete in <1ms
    assert benchmark.stats["mean"] < 0.001


@pytest.mark.benchmark
def test_needs_filters_check_performance(benchmark, config) -> None:
    """Benchmark filter detection performance."""
    config.formats["word_docx"].enabled = True

    result = benchmark(config.needs_document_filters)
    assert result is True
    # Should complete in <1ms
    assert benchmark.stats["mean"] < 0.001


@pytest.mark.benchmark
def test_supported_extensions_performance(benchmark, config) -> None:
    """Benchmark supported extensions retrieval."""
    config.formats["word_docx"].enabled = True
    config.formats["html"].enabled = True
    config.formats["json"].enabled = True

    result = benchmark(lambda: config.supported_extensions)
    assert len(result) > 0
    # Should complete in <1ms
    assert benchmark.stats["mean"] < 0.001


@pytest.mark.benchmark
def test_get_filter_for_extension_performance(benchmark, config) -> None:
    """Benchmark filter lookup by extension."""
    config.formats["word_docx"].enabled = True

    result = benchmark(config.get_filter_for_extension, ".docx")
    assert result is not None
    # Should complete in <1ms
    assert benchmark.stats["mean"] < 0.001
