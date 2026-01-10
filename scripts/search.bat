@echo off
REM Wrapper script for search_cli.py on Windows

REM Use uv if available, otherwise use python
where uv >nul 2>nul
if %errorlevel% equ 0 (
    uv run python search_cli.py %*
) else (
    python search_cli.py %*
)
