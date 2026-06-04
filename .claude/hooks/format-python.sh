#!/bin/bash
# Auto-format Python files after Write/Edit tool calls.
# Reads JSON input from stdin (PostToolUse hook contract).

input=$(cat)
file_path=$(echo "$input" | jq -r '.tool_input.file_path // empty')

# Only format if it's a Python file
if [[ -n "$file_path" ]] && [[ "$file_path" == *.py ]]; then
    uv run ruff format "$file_path" 2>/dev/null
    uv run ruff check --fix "$file_path" 2>/dev/null
fi
