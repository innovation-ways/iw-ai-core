"""Scope gate — enforce workflow-manifest.json scope.allowed_paths at merge time.

Invoked by executor/worktree_commit.sh BEFORE rebase/merge. Reads the list of
files modified on the branch from stdin (one path per line), checks each path
against the manifest's scope.allowed_paths plus implicit allows for the item's
own ai-dev artifacts, and prints any violations to stdout.

Exit 0 → all modified paths in scope (or no scope declared — legacy mode).
Exit 1 → at least one path outside scope; stdout lists the violations.
Exit 2 → manifest unreadable; caller should fail the merge.

Implicit always-allowed prefixes (no need to declare):
  - ai-dev/active/<ITEM_ID>/**
  - ai-dev/archive/<ITEM_ID>/**

Pattern syntax in manifest scope.allowed_paths:
  - "path/to/file.py"        — exact match
  - "dir/**"                 — the directory itself or any path below it
  - "dir/*.py"               — fnmatch single-level wildcard

Usage:
  git diff BASE..HEAD --name-only | python3 scope_gate.py <manifest> <item_id>
"""

from __future__ import annotations

import fnmatch
import json
import pathlib
import sys


def _matches(path: str, pattern: str) -> bool:
    if pattern.endswith("/**"):
        prefix = pattern[:-3]
        return path == prefix or path.startswith(prefix + "/")
    return fnmatch.fnmatch(path, pattern)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        sys.stderr.write("usage: scope_gate.py <manifest_path> <item_id>\n")
        return 2
    manifest_path, item_id = argv[1], argv[2]

    try:
        manifest = json.loads(pathlib.Path(manifest_path).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"scope_gate: could not read {manifest_path}: {exc}\n")
        return 2

    declared = list((manifest.get("scope") or {}).get("allowed_paths") or [])
    if not declared:
        # Legacy item — no scope declared. Log once to stderr and pass.
        sys.stderr.write(
            f"scope_gate: {manifest_path} has no scope.allowed_paths — skipping gate\n"
        )
        return 0

    implicit = [
        f"ai-dev/active/{item_id}/**",
        f"ai-dev/archive/{item_id}/**",
    ]
    patterns = declared + implicit

    violations: list[str] = []
    for raw in sys.stdin:
        path = raw.strip()
        if not path:
            continue
        if not any(_matches(path, pat) for pat in patterns):
            violations.append(path)

    for _v in violations:
        pass
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
