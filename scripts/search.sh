#!/bin/bash
# Wrapper script for search_cli.py

# Use uv if available, otherwise use python
if command -v uv &> /dev/null; then
    uv run python search_cli.py "$@"
else
    python search_cli.py "$@"
fi
