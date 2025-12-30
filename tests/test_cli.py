"""Tests for CLI entry point."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from contextfs.__main__ import main


def test_main_requires_ugrep():
    """Test that main exits if ugrep is not installed."""
    with patch("contextfs.__main__.check_ugrep_installed", return_value=False):
        with pytest.raises(SystemExit) as exc_info:
            with patch.object(sys, "argv", ["contextfs", "--root", "/tmp"]):
                main()

        assert exc_info.value.code == 1


def test_main_with_invalid_config():
    """Test that main exits with error for invalid config."""
    from contextfs.config import ConfigError

    with patch("contextfs.__main__.check_ugrep_installed", return_value=True):
        with patch("contextfs.__main__.load_config", side_effect=ConfigError("Config error")):
            with pytest.raises(SystemExit) as exc_info:
                with patch.object(sys, "argv", ["contextfs", "--config", "invalid.yaml"]):
                    main()

            assert exc_info.value.code == 1


def test_main_with_root_argument(temp_knowledge_dir):
    """Test main with --root argument."""
    with patch("contextfs.__main__.check_ugrep_installed", return_value=True):
        with patch("contextfs.__main__.run_server", new_callable=AsyncMock):
            with patch("contextfs.__main__.asyncio.run") as mock_asyncio_run:
                with patch.object(sys, "argv", ["contextfs", "--root", str(temp_knowledge_dir)]):
                    main()

                # Verify asyncio.run was called with run_server
                mock_asyncio_run.assert_called_once()


def test_main_with_config_argument(temp_knowledge_dir, tmp_path):
    """Test main with --config argument."""
    # Create a minimal config file
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        f"""
knowledge:
  root: {temp_knowledge_dir}
"""
    )

    with patch("contextfs.__main__.check_ugrep_installed", return_value=True):
        with patch("contextfs.__main__.run_server", new_callable=AsyncMock):
            with patch("contextfs.__main__.asyncio.run") as mock_asyncio_run:
                with patch.object(sys, "argv", ["contextfs", "--config", str(config_file)]):
                    main()

                mock_asyncio_run.assert_called_once()


def test_main_with_log_level_argument(temp_knowledge_dir):
    """Test main with --log-level argument."""
    import logging

    with patch("contextfs.__main__.check_ugrep_installed", return_value=True):
        with patch("contextfs.__main__.run_server", new_callable=AsyncMock):
            with patch("contextfs.__main__.asyncio.run"):
                with patch("contextfs.__main__.logging.basicConfig") as mock_logging:
                    with patch.object(
                        sys,
                        "argv",
                        ["contextfs", "--root", str(temp_knowledge_dir), "--log-level", "DEBUG"],
                    ):
                        main()

                    # Verify logging was configured with DEBUG level
                    mock_logging.assert_called_once()
                    call_kwargs = mock_logging.call_args[1]
                    assert call_kwargs["level"] == logging.DEBUG


def test_main_handles_keyboard_interrupt(temp_knowledge_dir):
    """Test that main handles KeyboardInterrupt gracefully."""
    with (
        patch("contextfs.__main__.check_ugrep_installed", return_value=True),
        patch("contextfs.__main__.asyncio.run", side_effect=KeyboardInterrupt) as mock_asyncio_run,
    ):
        # Should not raise, just exit gracefully
        with patch.object(sys, "argv", ["contextfs", "--root", str(temp_knowledge_dir)]):
            main()

        mock_asyncio_run.assert_called_once()


def test_main_root_overrides_config(temp_knowledge_dir, tmp_path):
    """Test that --root argument overrides config file root."""
    # Create a config with different root
    other_dir = tmp_path / "other"
    other_dir.mkdir()

    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        f"""
knowledge:
  root: {other_dir}
"""
    )

    with patch("contextfs.__main__.check_ugrep_installed", return_value=True):
        with patch("contextfs.__main__.run_server", new_callable=AsyncMock) as mock_run:
            with (
                patch("contextfs.__main__.asyncio.run"),
                patch.object(
                    sys,
                    "argv",
                    [
                        "contextfs",
                        "--config",
                        str(config_file),
                        "--root",
                        str(temp_knowledge_dir),
                    ],
                ),
            ):
                main()

            # Check that run_server was called with the correct config
            mock_run.assert_called_once()
            config_arg = mock_run.call_args[0][0]
            assert str(config_arg.knowledge.root) == str(temp_knowledge_dir)


def test_main_creates_minimal_config_with_root_only(temp_knowledge_dir):
    """Test that main creates minimal config when only --root is provided."""
    with patch("contextfs.__main__.check_ugrep_installed", return_value=True):
        with patch("contextfs.__main__.run_server", new_callable=AsyncMock) as mock_run:
            with patch("contextfs.__main__.asyncio.run"):
                with patch.object(sys, "argv", ["contextfs", "--root", str(temp_knowledge_dir)]):
                    main()

            # Verify config was created with the provided root
            mock_run.assert_called_once()
            config_arg = mock_run.call_args[0][0]
            assert config_arg.knowledge.root == Path(temp_knowledge_dir)
