"""Regression guard for .pre-commit-config.yaml — F-00070."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / ".pre-commit-config.yaml"

EXPECTED_HOOK_IDS = {
    # Existing
    "ruff",
    "ruff-format",
    "mypy",
    # Added by F-00070
    "trailing-whitespace",
    "end-of-file-fixer",
    "check-yaml",
    "check-json",
    "check-toml",
    "check-added-large-files",
    "detect-private-key",
    "check-merge-conflict",
    "check-case-conflict",
}


def _all_hook_ids(config_path: Path) -> set[str]:
    data = yaml.safe_load(config_path.read_text())
    ids: set[str] = set()
    for repo in data.get("repos", []):
        for hook in repo.get("hooks", []):
            ids.add(hook["id"])
    return ids


def test_precommit_config_exists() -> None:
    assert CONFIG_PATH.is_file(), f".pre-commit-config.yaml missing at {CONFIG_PATH}"


@pytest.mark.parametrize("hook_id", sorted(EXPECTED_HOOK_IDS))
def test_expected_hook_present(hook_id: str) -> None:
    assert hook_id in _all_hook_ids(CONFIG_PATH), (
        f"Hook '{hook_id}' missing from .pre-commit-config.yaml — see F-00070 design doc"
    )


def test_pre_commit_hooks_repo_rev_pinned() -> None:
    """Reject HEAD / latest / branch refs."""
    data = yaml.safe_load(CONFIG_PATH.read_text())
    for repo in data.get("repos", []):
        url = str(repo.get("repo", ""))
        if url == "local":
            continue
        rev = str(repo.get("rev", ""))
        assert rev, f"Repo {url} has no rev pin"
        assert rev.lower() not in {"head", "latest", "main", "master"}, (
            f"Repo {url} uses unpinned rev '{rev}' — pin to a tag"
        )


def test_large_files_threshold_set() -> None:
    data = yaml.safe_load(CONFIG_PATH.read_text())
    for repo in data.get("repos", []):
        for hook in repo.get("hooks", []):
            if hook.get("id") == "check-added-large-files":
                args = " ".join(hook.get("args", []))
                assert "--maxkb=" in args, "check-added-large-files needs --maxkb=<n>"
                return
    pytest.fail("check-added-large-files hook not found")
