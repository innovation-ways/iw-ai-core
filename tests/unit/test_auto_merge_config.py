"""Unit tests for orch.daemon.auto_merge — AutoMergeConfig loading.

Covers: defaults, phase constants, TOML parsing, malformed-TOML fallback,
null runtime_option_id, allowlist/refuselist defaults, limits defaults, and
consumer-level phase>=2 enforcement.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_phase_constants() -> None:
    """Phase constants must have the correct integer values."""
    from orch.daemon.auto_merge import (
        PHASE_BROADER,
        PHASE_DISABLED,
        PHASE_DRY_RUN,
        PHASE_TESTS_ONLY,
    )

    assert PHASE_DISABLED == 0
    assert PHASE_DRY_RUN == 1
    assert PHASE_TESTS_ONLY == 2
    assert PHASE_BROADER == 3


def test_load_defaults_when_file_missing(tmp_path: Path) -> None:
    """Loading from a nonexistent path returns (defaults, None)."""
    from orch.daemon.auto_merge import PHASE_DISABLED, AutoMergeConfig

    config, error = AutoMergeConfig.load(str(tmp_path / "nonexistent.toml"))

    assert error is None
    assert config.phase == PHASE_DISABLED
    defaults = AutoMergeConfig.defaults()
    assert config.phase == defaults.phase
    assert config.max_conflict_hunk_lines == defaults.max_conflict_hunk_lines
    assert config.max_conflicted_files_per_merge == defaults.max_conflicted_files_per_merge
    assert config.max_file_size_bytes == defaults.max_file_size_bytes
    assert config.max_event_metadata_bytes == defaults.max_event_metadata_bytes
    assert config.llm_call_timeout_seconds == defaults.llm_call_timeout_seconds


def test_load_phase_0(tmp_path: Path) -> None:
    """Loading a TOML with phase=0 yields PHASE_DISABLED."""
    from orch.daemon.auto_merge import PHASE_DISABLED, AutoMergeConfig

    toml_file = tmp_path / "auto_merge.toml"
    toml_file.write_text("phase = 0\n")

    config, error = AutoMergeConfig.load(str(toml_file))

    assert error is None
    assert config.phase == PHASE_DISABLED
    assert config.phase == 0


def test_load_phase_1(tmp_path: Path) -> None:
    """Loading a TOML with phase=1 yields PHASE_DRY_RUN."""
    from orch.daemon.auto_merge import PHASE_DRY_RUN, AutoMergeConfig

    toml_file = tmp_path / "auto_merge.toml"
    toml_file.write_text("phase = 1\n")

    config, error = AutoMergeConfig.load(str(toml_file))

    assert error is None
    assert config.phase == PHASE_DRY_RUN
    assert config.phase == 1


def test_load_phase_2_reserved_consumer_rejects(tmp_path: Path) -> None:
    """phase=2 loaded successfully by loader; consumer (attempt_resolution) raises ValueError."""
    from orch.daemon.auto_merge import AutoMergeConfig, attempt_resolution

    toml_file = tmp_path / "auto_merge.toml"
    toml_file.write_text("phase = 2\n")

    config, error = AutoMergeConfig.load(str(toml_file))

    # Loader itself succeeds — no error
    assert error is None
    assert config.phase == 2

    # Consumer must reject phase>=2 with ValueError
    with pytest.raises(ValueError, match="reserved"):
        attempt_resolution(
            db=None,  # type: ignore[arg-type]
            project_id="test-proj",
            item_id="F-00001",
            item_title="title",
            item_description="desc",
            worktree_path="/tmp/fake",
            main_sha="abc",
            branch_name="agent/F-00001",
            eligible_files=["tests/test_foo.py"],
            config=config,
        )


def test_load_malformed_toml(tmp_path: Path) -> None:
    """Malformed TOML returns (defaults, error_string); no exception escapes."""
    from orch.daemon.auto_merge import PHASE_DISABLED, AutoMergeConfig

    toml_file = tmp_path / "bad.toml"
    toml_file.write_text("phase = [this is not valid toml")

    config, error = AutoMergeConfig.load(str(toml_file))

    # No exception; error string is non-empty
    assert error is not None
    assert isinstance(error, str)
    assert len(error) > 0
    assert "TOML" in error or "parse" in error.lower() or "error" in error.lower()

    # Falls back to phase=0
    assert config.phase == PHASE_DISABLED


def test_load_runtime_option_id_null(tmp_path: Path) -> None:
    """Default config has runtime_option_id=None."""
    from orch.daemon.auto_merge import AutoMergeConfig

    config = AutoMergeConfig.defaults()

    assert config.runtime_option_id is None


def test_load_runtime_option_id_null_from_toml(tmp_path: Path) -> None:
    """runtime_option_id = null in TOML maps to None in config."""
    from orch.daemon.auto_merge import AutoMergeConfig

    toml_content = textwrap.dedent("""\
        phase = 0
        runtime_option_id = null
    """)

    toml_file = tmp_path / "auto_merge.toml"
    toml_file.write_text(toml_content)

    config, error = AutoMergeConfig.load(str(toml_file))

    assert error is None
    assert config.runtime_option_id is None


def test_load_runtime_option_id_int(tmp_path: Path) -> None:
    """Explicit integer runtime_option_id loads correctly."""
    from orch.daemon.auto_merge import AutoMergeConfig

    toml_file = tmp_path / "auto_merge.toml"
    toml_file.write_text("phase = 1\nruntime_option_id = 42\n")

    config, error = AutoMergeConfig.load(str(toml_file))

    assert error is None
    assert config.runtime_option_id == 42
    assert isinstance(config.runtime_option_id, int)


def test_load_allowlist_patterns_default() -> None:
    """Default allowlist contains tests/**/*.py and docs/**/*.md."""
    from orch.daemon.auto_merge import AutoMergeConfig

    config = AutoMergeConfig.defaults()

    assert "tests/**/*.py" in config.allowlist_patterns
    assert "docs/**/*.md" in config.allowlist_patterns
    # Also check ai-dev report patterns
    assert any("ai-dev" in p for p in config.allowlist_patterns)


def test_load_refuselist_patterns_default() -> None:
    """Default refuse-list contains migration files, .gitleaks.toml, binary suffixes."""
    from orch.daemon.auto_merge import AutoMergeConfig

    config = AutoMergeConfig.defaults()

    assert len(config.refuselist_patterns) >= 6
    assert "orch/db/migrations/versions/*.py" in config.refuselist_patterns
    assert ".gitleaks.toml" in config.refuselist_patterns
    assert ".env" in config.refuselist_patterns
    assert "*.png" in config.refuselist_patterns
    assert "*.db" in config.refuselist_patterns
    assert "uv.lock" in config.refuselist_patterns


def test_load_limits_defaults() -> None:
    """Default limits: max_conflict_hunk_lines=80, max_conflicted_files_per_merge=5."""
    from orch.daemon.auto_merge import AutoMergeConfig

    config = AutoMergeConfig.defaults()

    assert config.max_conflict_hunk_lines == 80
    assert config.max_conflicted_files_per_merge == 5
    assert config.max_file_size_bytes == 256_000
    assert config.max_event_metadata_bytes == 262_144
    assert config.llm_call_timeout_seconds == 120


def test_load_from_valid_toml(tmp_path: Path) -> None:
    """Loading a valid TOML returns a correctly-populated AutoMergeConfig."""
    from orch.daemon.auto_merge import AutoMergeConfig

    toml_content = textwrap.dedent("""\
        phase = 1
        runtime_option_id = 42

        [allowlist]
        patterns = ["tests/**/*.py", "docs/**/*.md"]

        [refuselist]
        patterns = ["orch/db/migrations/versions/*.py", ".env"]

        [limits]
        max_conflict_hunk_lines = 50
        max_conflicted_files_per_merge = 3
        max_file_size_bytes = 128000
        max_event_metadata_bytes = 131072
        llm_call_timeout_seconds = 90
    """)

    toml_file = tmp_path / "auto_merge.toml"
    toml_file.write_text(toml_content)

    config, error = AutoMergeConfig.load(str(toml_file))

    assert error is None
    assert config.phase == 1
    assert config.runtime_option_id == 42
    assert config.allowlist_patterns == ("tests/**/*.py", "docs/**/*.md")
    assert config.refuselist_patterns == ("orch/db/migrations/versions/*.py", ".env")
    assert config.max_conflict_hunk_lines == 50
    assert config.max_conflicted_files_per_merge == 3
    assert config.max_file_size_bytes == 128000
    assert config.max_event_metadata_bytes == 131072
    assert config.llm_call_timeout_seconds == 90


def test_defaults_returns_phase_zero() -> None:
    """defaults() returns a frozen config with phase=0."""
    from orch.daemon.auto_merge import PHASE_DISABLED, AutoMergeConfig

    defaults = AutoMergeConfig.defaults()
    assert defaults.phase == PHASE_DISABLED


def test_config_is_frozen() -> None:
    """AutoMergeConfig is frozen — mutation must raise FrozenInstanceError."""
    from orch.daemon.auto_merge import AutoMergeConfig

    config = AutoMergeConfig.defaults()
    with pytest.raises(AttributeError):
        config.phase = 1  # type: ignore[misc]


def test_load_toml_null_runtime_option(tmp_path: Path) -> None:
    """runtime_option_id = null in TOML maps to None in config."""
    from orch.daemon.auto_merge import AutoMergeConfig

    toml_content = textwrap.dedent("""\
        phase = 0
        runtime_option_id = null

        [allowlist]
        patterns = []

        [refuselist]
        patterns = []

        [limits]
        max_conflict_hunk_lines = 80
        max_conflicted_files_per_merge = 5
        max_file_size_bytes = 256000
        max_event_metadata_bytes = 262144
        llm_call_timeout_seconds = 120
    """)

    toml_file = tmp_path / "auto_merge.toml"
    toml_file.write_text(toml_content)

    config, error = AutoMergeConfig.load(str(toml_file))

    assert error is None
    assert config.runtime_option_id is None


def test_load_actual_auto_merge_toml() -> None:
    """Loading the actual executor/auto_merge.toml succeeds with phase=0."""
    from pathlib import Path

    from orch.daemon.auto_merge import PHASE_DISABLED, AutoMergeConfig

    toml_path = Path(__file__).resolve().parent.parent.parent / "executor" / "auto_merge.toml"
    if not toml_path.exists():
        pytest.skip("executor/auto_merge.toml not found")

    config, error = AutoMergeConfig.load(str(toml_path))

    assert error is None
    assert config.phase == PHASE_DISABLED
    assert config.runtime_option_id is None
    assert len(config.allowlist_patterns) > 0
    assert len(config.refuselist_patterns) > 0
