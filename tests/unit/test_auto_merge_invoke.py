"""Unit tests for orch.daemon.auto_merge — invoke_llm_for_file and related paths.

Patches subprocess.run at the Python boundary so no real subprocess or LLM
is invoked. Covers lines 679-800 (invoke_llm_for_file internals) plus the
reload_config error path (line 287) and _is_binary_file OSError (309-310).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _default_config():
    from orch.daemon.auto_merge import PHASE_DRY_RUN, AutoMergeConfig

    return AutoMergeConfig(
        phase=PHASE_DRY_RUN,
        runtime_option_id=None,
        allowlist_patterns=("tests/**/*.py",),
        refuselist_patterns=("orch/db/migrations/versions/*.py",),
        max_conflict_hunk_lines=80,
        max_conflicted_files_per_merge=5,
        max_file_size_bytes=256_000,
        max_event_metadata_bytes=262_144,
        llm_call_timeout_seconds=10,
    )


def _common_kwargs(worktree_path: str = "/tmp/wt") -> dict:
    return {
        "worktree_path": worktree_path,
        "file_path": "tests/unit/test_foo.py",
        "main_sha": "deadbeef",
        "branch_name": "agent/F-00001",
        "item_id": "F-00001",
        "item_title": "Test Item",
        "item_description": "A test work item.",
        "cli_tool": "opencode",
        "model": "test-model",
        "config": _default_config(),
    }


def _fake_completed_process(returncode: int = 0, stdout: str = "", stderr: str = ""):
    cp = MagicMock(spec=subprocess.CompletedProcess)
    cp.returncode = returncode
    cp.stdout = stdout
    cp.stderr = stderr
    return cp


# ---------------------------------------------------------------------------
# invoke_llm_for_file: success path
# ---------------------------------------------------------------------------


def test_invoke_llm_success_returns_proposed_content(tmp_path: Path) -> None:
    """invoke_llm_for_file with exit=0 and non-ABSTAIN output → proposed_content."""
    from orch.daemon.auto_merge import invoke_llm_for_file

    resolved = "def test_foo():\n    assert 1 == 1\n"

    with (
        patch("orch.daemon.auto_merge.subprocess.run") as mock_run,
        patch("orch.daemon.auto_merge.build_resolution_prompt", return_value="FAKE PROMPT"),
    ):
        mock_run.return_value = _fake_completed_process(returncode=0, stdout=resolved)
        result = invoke_llm_for_file(**_common_kwargs(str(tmp_path)))

    assert result.abstained is False
    assert result.error is None
    assert result.proposed_content == resolved.strip()
    assert result.output_hash is not None
    assert result.prompt_hash is not None
    assert result.model == "test-model"
    assert result.cli_tool == "opencode"


def test_invoke_llm_success_output_hash_changes_with_content(tmp_path: Path) -> None:
    """Different outputs produce different output_hash values."""
    from orch.daemon.auto_merge import invoke_llm_for_file

    with (
        patch("orch.daemon.auto_merge.subprocess.run") as mock_run,
        patch("orch.daemon.auto_merge.build_resolution_prompt", return_value="PROMPT"),
    ):
        mock_run.return_value = _fake_completed_process(returncode=0, stdout="content_A")
        r1 = invoke_llm_for_file(**_common_kwargs(str(tmp_path)))

        mock_run.return_value = _fake_completed_process(returncode=0, stdout="content_B")
        r2 = invoke_llm_for_file(**_common_kwargs(str(tmp_path)))

    assert r1.output_hash != r2.output_hash


# ---------------------------------------------------------------------------
# invoke_llm_for_file: ABSTAIN path
# ---------------------------------------------------------------------------


def test_invoke_llm_abstain_returns_abstained_true(tmp_path: Path) -> None:
    """ABSTAIN response → LLMCallResult.abstained=True, proposed_content=None."""
    from orch.daemon.auto_merge import invoke_llm_for_file

    with (
        patch("orch.daemon.auto_merge.subprocess.run") as mock_run,
        patch("orch.daemon.auto_merge.build_resolution_prompt", return_value="PROMPT"),
    ):
        mock_run.return_value = _fake_completed_process(returncode=0, stdout="ABSTAIN")
        result = invoke_llm_for_file(**_common_kwargs(str(tmp_path)))

    assert result.abstained is True
    assert result.proposed_content is None
    assert result.error is None
    assert result.output_hash is None


def test_invoke_llm_abstain_case_insensitive(tmp_path: Path) -> None:
    """ABSTAIN detection is case-insensitive (both 'abstain' and 'ABSTAIN' work)."""
    from orch.daemon.auto_merge import invoke_llm_for_file

    with (
        patch("orch.daemon.auto_merge.subprocess.run") as mock_run,
        patch("orch.daemon.auto_merge.build_resolution_prompt", return_value="PROMPT"),
    ):
        mock_run.return_value = _fake_completed_process(returncode=0, stdout="abstain\nsome note")
        result = invoke_llm_for_file(**_common_kwargs(str(tmp_path)))

    assert result.abstained is True


# ---------------------------------------------------------------------------
# invoke_llm_for_file: non-zero exit
# ---------------------------------------------------------------------------


def test_invoke_llm_nonzero_exit_returns_error(tmp_path: Path) -> None:
    """Non-zero exit code → LLMCallResult.error contains the exit code."""
    from orch.daemon.auto_merge import invoke_llm_for_file

    with (
        patch("orch.daemon.auto_merge.subprocess.run") as mock_run,
        patch("orch.daemon.auto_merge.build_resolution_prompt", return_value="PROMPT"),
    ):
        mock_run.return_value = _fake_completed_process(
            returncode=1, stdout="", stderr="bash: command not found"
        )
        result = invoke_llm_for_file(**_common_kwargs(str(tmp_path)))

    assert result.abstained is False
    assert result.proposed_content is None
    assert result.error is not None
    assert "exit code 1" in result.error


# ---------------------------------------------------------------------------


def test_invoke_llm_timeout_returns_error(tmp_path: Path) -> None:
    """TimeoutExpired → LLMCallResult.error contains 'timed out'."""
    from orch.daemon.auto_merge import invoke_llm_for_file

    with (
        patch("orch.daemon.auto_merge.subprocess.run") as mock_run,
        patch("orch.daemon.auto_merge.build_resolution_prompt", return_value="PROMPT"),
    ):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="bash", timeout=10)
        result = invoke_llm_for_file(**_common_kwargs(str(tmp_path)))

    assert result.abstained is False
    assert result.proposed_content is None
    assert result.error is not None
    assert "timed out" in result.error.lower() or "timeout" in result.error.lower()


# ---------------------------------------------------------------------------


def test_invoke_llm_generic_exception_returns_error(tmp_path: Path) -> None:
    """Any other exception from subprocess → LLMCallResult.error with the message."""
    from orch.daemon.auto_merge import invoke_llm_for_file

    with (
        patch("orch.daemon.auto_merge.subprocess.run") as mock_run,
        patch("orch.daemon.auto_merge.build_resolution_prompt", return_value="PROMPT"),
    ):
        mock_run.side_effect = OSError("executor script missing")
        result = invoke_llm_for_file(**_common_kwargs(str(tmp_path)))

    assert result.abstained is False
    assert result.proposed_content is None
    assert result.error is not None
    assert "executor script missing" in result.error


# ---------------------------------------------------------------------------


def test_invoke_llm_prompt_hash_stable_across_calls(tmp_path: Path) -> None:
    """Same prompt → same prompt_hash (deterministic)."""
    from orch.daemon.auto_merge import invoke_llm_for_file

    with (
        patch("orch.daemon.auto_merge.subprocess.run") as mock_run,
        patch("orch.daemon.auto_merge.build_resolution_prompt", return_value="STABLE PROMPT"),
    ):
        mock_run.return_value = _fake_completed_process(returncode=0, stdout="resolved")
        r1 = invoke_llm_for_file(**_common_kwargs(str(tmp_path)))
        r2 = invoke_llm_for_file(**_common_kwargs(str(tmp_path)))

    assert r1.prompt_hash == r2.prompt_hash


# ---------------------------------------------------------------------------
# reload_config: error path (line 287)
# ---------------------------------------------------------------------------


def test_reload_config_error_keeps_previous_cache(tmp_path: Path) -> None:
    """reload_config with malformed TOML keeps the previous cached config."""
    from orch.daemon import auto_merge as am

    good_toml = tmp_path / "good.toml"
    good_toml.write_text("phase = 0\n")

    bad_toml = tmp_path / "bad.toml"
    bad_toml.write_text("phase = [not valid toml\n")

    # Load a good config first (sets the cache)
    good_config = am.reload_config(str(good_toml))
    assert good_config.phase == 0

    # Now load the bad TOML — should keep the previous cache
    cached_before = am._cached_config
    am.reload_config(str(bad_toml))

    # The returned config is the defaults (not cached), but cache is unchanged
    assert am._cached_config is cached_before


# ---------------------------------------------------------------------------
# _is_binary_file: OSError path (lines 309-310)
# ---------------------------------------------------------------------------


def test_is_binary_file_oserror_returns_false(tmp_path: Path) -> None:
    """_is_binary_file returns False if the file cannot be read (OSError)."""
    from orch.daemon.auto_merge import _is_binary_file

    nonexistent = tmp_path / "does_not_exist.py"
    # No binary suffix, file does not exist → OSError → False
    result = _is_binary_file(nonexistent)
    assert result is False


# ---------------------------------------------------------------------------
# emit_event convenience wrapper (lines 1130-1139)
# ---------------------------------------------------------------------------


def test_emit_event_wrapper_commits(tmp_path: Path) -> None:
    """emit_event convenience wrapper calls _emit_event and commits."""
    from unittest.mock import MagicMock

    from orch.daemon.auto_merge import emit_event

    mock_db = MagicMock()
    mock_db.add = MagicMock()
    mock_db.commit = MagicMock()
    mock_db.flush = MagicMock()

    with patch("orch.daemon.auto_merge._emit_event") as mock_emit:
        emit_event(
            mock_db,
            project_id="test-proj",
            item_id="F-00001",
            event_type="merge_auto_resolution_skipped",
            metadata={"reason": "phase_0"},
        )

    mock_emit.assert_called_once()
    call_kwargs = mock_emit.call_args
    assert call_kwargs[0][2] == "merge_auto_resolution_skipped"
    mock_db.commit.assert_called_once()
