"""Regression guard for F-00071 — security scanning surface."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = REPO_ROOT / "Makefile"
PYPROJECT = REPO_ROOT / "pyproject.toml"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "security-scan.yml"
TRIVYIGNORE = REPO_ROOT / ".trivyignore"

REQUIRED_MAKE_TARGETS = (
    "security-deps",
    "security-iac",
    "security-image-",
    "security-all",
    "security-report",
)

REQUIRED_DEV_DEPS = ("pip-audit", "bandit")

SHA_RE = re.compile(r"^[0-9a-f]{40}$")


@pytest.mark.parametrize("target", REQUIRED_MAKE_TARGETS)
def test_makefile_target_present(target: str) -> None:
    text = MAKEFILE.read_text()
    found = bool(re.search(rf"^{re.escape(target)}[\w-]*:\s", text, re.MULTILINE))
    assert found, f"Makefile target '{target}*' missing — see F-00071"


def test_workflow_file_exists() -> None:
    assert WORKFLOW.is_file()


def test_workflow_required_jobs() -> None:
    data = yaml.safe_load(WORKFLOW.read_text())
    assert "deps-audit" in data["jobs"]
    assert "iac-scan" in data["jobs"]


def test_workflow_permissions_minimal() -> None:
    data = yaml.safe_load(WORKFLOW.read_text())
    perms = data.get("permissions", {})
    assert perms.get("contents") == "read"
    assert perms.get("security-events") == "write"
    extras = set(perms.keys()) - {"contents", "security-events"}
    assert not extras, f"Unexpected permissions: {extras}"


def test_workflow_actions_pinned_to_sha() -> None:
    text = WORKFLOW.read_text()
    pattern = re.compile(r"uses:\s*([\w./-]+)@([\w./-]+)")
    for action, ref in pattern.findall(text):
        assert SHA_RE.match(ref), (
            f"Action {action!r} pinned to non-SHA ref {ref!r} — must be a 40-char commit SHA"
        )


def test_workflow_triggers_pr_push_schedule() -> None:
    data = yaml.safe_load(WORKFLOW.read_text())
    on = data.get(True, data.get("on"))
    assert "pull_request" in on
    assert "push" in on
    assert "schedule" in on


@pytest.mark.parametrize("dep", REQUIRED_DEV_DEPS)
def test_dev_dep_present(dep: str) -> None:
    data = tomllib.loads(PYPROJECT.read_text())
    dev_deps = data["dependency-groups"]["dev"]
    found = any(item.startswith(dep) for item in dev_deps)
    assert found, f"Dev dep '{dep}' missing from [dependency-groups] dev — see F-00071"


def test_bandit_config_excludes_tests() -> None:
    data = tomllib.loads(PYPROJECT.read_text())
    bandit = data.get("tool", {}).get("bandit", {})
    excludes = set(bandit.get("exclude_dirs", []))
    assert "tests" in excludes
    assert "scripts" in excludes


def test_trivyignore_exists() -> None:
    assert TRIVYIGNORE.is_file()
    text = TRIVYIGNORE.read_text()
    non_comment_lines = [
        line for line in text.splitlines() if line.strip() and not line.strip().startswith("#")
    ]
    assert not non_comment_lines, (
        f".trivyignore has active ignores without justification: {non_comment_lines}"
    )
