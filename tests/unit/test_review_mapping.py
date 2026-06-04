"""Unit tests for orch/daemon/review_mapping.py."""

from __future__ import annotations

from pathlib import Path

from orch.daemon.review_mapping import load_review_mapping, review_agents_for

# ---------------------------------------------------------------------------
# load_review_mapping
# ---------------------------------------------------------------------------


def test_load_review_mapping_returns_empty_when_file_missing(tmp_path: Path) -> None:
    """Missing review-mapping.toml → empty list (graceful no-op)."""
    result = load_review_mapping(tmp_path)
    assert result == []


def test_load_review_mapping_parses_well_formed_toml(tmp_path: Path) -> None:
    """Well-formed TOML with two mapping entries is parsed correctly."""
    config_dir = tmp_path / "ai-dev" / "iw-config"
    config_dir.mkdir(parents=True)
    toml_content = """\
[[mapping]]
review_agent = "backend-review"
glob = ["orch/daemon/**", "orch/*.py"]

[[mapping]]
review_agent = "frontend-review"
glob = ["dashboard/templates/**", "dashboard/static/**"]
"""
    (config_dir / "review-mapping.toml").write_text(toml_content)

    result = load_review_mapping(tmp_path)

    assert len(result) == 2
    assert result[0] == ("backend-review", ["orch/daemon/**", "orch/*.py"])
    assert result[1] == ("frontend-review", ["dashboard/templates/**", "dashboard/static/**"])


def test_load_review_mapping_skips_malformed_entries(tmp_path: Path) -> None:
    """Entries missing 'review_agent' or with a non-list 'glob' are silently skipped."""
    config_dir = tmp_path / "ai-dev" / "iw-config"
    config_dir.mkdir(parents=True)
    toml_content = """\
[[mapping]]
review_agent = "backend-review"
glob = ["orch/*.py"]

[[mapping]]
glob = ["orch/db/**"]

[[mapping]]
review_agent = "api-review"
glob = "not-a-list"

[[mapping]]
review_agent = "tests-review"
glob = ["tests/**"]
"""
    (config_dir / "review-mapping.toml").write_text(toml_content)

    result = load_review_mapping(tmp_path)

    # Only the well-formed entries survive
    agent_names = [r[0] for r in result]
    assert "backend-review" in agent_names
    assert "tests-review" in agent_names
    # Missing review_agent and wrong glob type are both excluded
    assert len(result) == 2


def test_load_review_mapping_returns_empty_on_invalid_toml(tmp_path: Path) -> None:
    """Unreadable / invalid TOML → empty list (warning logged, no exception raised)."""
    config_dir = tmp_path / "ai-dev" / "iw-config"
    config_dir.mkdir(parents=True)
    (config_dir / "review-mapping.toml").write_bytes(b"\xff\xfe invalid bytes that are not utf-8")

    # Should not raise; returns empty list
    result = load_review_mapping(tmp_path)
    assert result == []


# ---------------------------------------------------------------------------
# review_agents_for
# ---------------------------------------------------------------------------


def test_review_agents_for_single_glob_match() -> None:
    """A changed file that matches one agent's glob returns that agent."""
    mapping = [("backend-review", ["orch/daemon/**"])]
    result = review_agents_for(["orch/daemon/fix_cycle.py"], mapping)
    assert result == {"backend-review"}


def test_review_agents_for_multi_glob_union() -> None:
    """A changed file matching multiple agents returns all matching agents."""
    mapping = [
        ("backend-review", ["orch/daemon/**"]),
        ("api-review", ["dashboard/routers/actions.py"]),
    ]
    result = review_agents_for(
        ["orch/daemon/fix_cycle.py", "dashboard/routers/actions.py"],
        mapping,
    )
    assert result == {"backend-review", "api-review"}


def test_review_agents_for_no_match_returns_empty_set() -> None:
    """No changed files match any glob → empty set."""
    mapping = [("backend-review", ["orch/daemon/**"])]
    result = review_agents_for(["dashboard/templates/base.html"], mapping)
    assert result == set()


def test_review_agents_for_handles_nested_paths_with_double_star() -> None:
    """Globs with ** match files in nested subdirectories."""
    mapping = [
        ("frontend-review", ["dashboard/templates/**"]),
        ("tests-review", ["tests/**"]),
    ]
    # Nested template path
    result1 = review_agents_for(["dashboard/templates/pages/project/batch_detail.html"], mapping)
    assert "frontend-review" in result1

    # Nested tests path
    result2 = review_agents_for(["tests/integration/test_fix_cycle.py"], mapping)
    assert "tests-review" in result2


def test_review_agents_for_empty_changed_files() -> None:
    """Empty changed-files list → empty set."""
    mapping = [("backend-review", ["orch/daemon/**"])]
    result = review_agents_for([], mapping)
    assert result == set()


def test_review_agents_for_empty_mapping() -> None:
    """Empty mapping → empty set regardless of changed files."""
    result = review_agents_for(["orch/daemon/fix_cycle.py"], [])
    assert result == set()
