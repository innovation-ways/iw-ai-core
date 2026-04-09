"""Shared utilities for the iw CLI — pure functions with no DB or I/O dependencies."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import NoReturn

import click

# ---------------------------------------------------------------------------
# Project auto-detection
# ---------------------------------------------------------------------------


def find_project_root(start: Path) -> tuple[str, Path] | None:
    """Walk up from start looking for .iw-orch.json.

    Returns (project_id, repo_root) or None if not found.
    """
    current = start.resolve()
    while True:
        config_file = current / ".iw-orch.json"
        if config_file.exists():
            try:
                data = json.loads(config_file.read_text())
                project_id = data.get("project_id")
                if project_id and isinstance(project_id, str):
                    return project_id, current
            except (json.JSONDecodeError, OSError):
                pass
        parent = current.parent
        if parent == current:
            return None
        current = parent


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def output_error(ctx: click.Context, message: str, code: int) -> NoReturn:
    """Print error in human or JSON format then exit with code."""
    if ctx.obj and ctx.obj.get("json"):
        click.echo(json.dumps({"error": message, "code": code}))
    else:
        click.echo(f"Error: {message}", err=True)
    sys.exit(code)


# ---------------------------------------------------------------------------
# Project resolution
# ---------------------------------------------------------------------------


def resolve_project(ctx: click.Context) -> str:
    """Resolve project_id from context (--project flag or .iw-orch.json)."""
    project_id: str | None = ctx.obj.get("project_id") if ctx.obj else None
    if project_id:
        return project_id

    result = find_project_root(Path.cwd())
    if result is None:
        output_error(ctx, "No .iw-orch.json found in directory tree", 3)

    pid, repo_root = result
    ctx.obj["project_id"] = pid
    ctx.obj["repo_root"] = str(repo_root)
    return pid


# ---------------------------------------------------------------------------
# ID formatting & validation
# ---------------------------------------------------------------------------

TYPE_TO_PREFIX: dict[str, str] = {
    "feature": "F",
    "incident": "I",
    "cr": "CR",
    "batch": "BATCH",
}

# Prefixes used when validating work item IDs (no batch type here)
TYPE_TO_ID_PREFIX: dict[str, str] = {
    "feature": "F-",
    "incident": "I-",
    "cr": "CR-",
}


def format_id(prefix: str, number: int) -> str:
    """Format a sequential ID with dash separator and 5-digit zero-padding."""
    return f"{prefix}-{number:05d}"


def validate_id_prefix(item_id: str, item_type: str) -> bool:
    """Return True if item_id starts with the expected prefix for item_type.

    Expected format: ``PREFIX-DIGITS`` (e.g. ``I-00001``, ``CR-00042``).
    """
    expected = TYPE_TO_ID_PREFIX.get(item_type)
    if expected is None:
        return False
    rest = item_id[len(expected) :]
    return item_id.startswith(expected) and len(rest) >= 1 and rest.isdigit()
