"""CR-00023 AC4: daemon read paths prefer DB columns; fall back to manifest for legacy NULL rows.

Three call sites are covered:
  - orch/daemon/batch_manager.py:_build_claude_prompt
  - orch/daemon/batch_manager.py:_compute_qv_baselines (DB-first selection)
  - orch/daemon/fix_cycle.py:_get_gate_name_and_command
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from orch.daemon.fix_cycle import _get_gate_name_and_command
from orch.db.models import StepStatus, StepType, WorkflowStep

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _make_step(**overrides: Any) -> WorkflowStep:
    """Build a detached WorkflowStep instance for unit-ish tests.

    Uses the model class without persistence — these tests only need the
    attribute reads of the daemon code paths.
    """
    defaults: dict[str, Any] = {
        "id": 1,
        "project_id": "test-proj",
        "work_item_id": "I-99100",
        "step_number": 1,
        "step_id": "S01",
        "agent_label": "Backend",
        "opencode_agent": "backend-impl",
        "step_type": StepType.implementation,
        "step_label": None,
        "description": None,
        "status": StepStatus.pending,
        "prompt_file": None,
        "report_file": None,
        "report_content": None,
        "started_at": None,
        "completed_at": None,
        "command": None,
        "gate": None,
        "timeout_secs": None,
    }
    defaults.update(overrides)
    return WorkflowStep(**defaults)


def _write_manifest(worktree: Path, item_id: str, payload: dict[str, Any]) -> Path:
    design_dir = worktree / "ai-dev" / "active" / item_id
    design_dir.mkdir(parents=True, exist_ok=True)
    manifest = design_dir / "workflow-manifest.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    return manifest


# ---------------------------------------------------------------------------
# _get_gate_name_and_command
# ---------------------------------------------------------------------------


def test_get_gate_name_and_command_returns_db_values_when_populated(
    tmp_path: Path,
) -> None:
    """DB-first: a populated row never reads the manifest."""
    step = _make_step(
        step_id="S05",
        step_type=StepType.quality_validation,
        agent_label="QvGate",
        opencode_agent="qv-gate",
        command="make lint",
        gate="lint",
    )
    # Manifest has DIFFERENT values; we must not see them.
    _write_manifest(
        tmp_path,
        step.work_item_id,
        {
            "steps": [
                {"step": "S05", "agent": "qv-gate", "gate": "DIFFERENT", "command": "DIFFERENT"}
            ]
        },
    )

    gate, command = _get_gate_name_and_command(step, str(tmp_path))
    assert gate == "lint"
    assert command == "make lint"


def test_get_gate_name_and_command_falls_back_to_manifest(tmp_path: Path) -> None:
    """Legacy row (NULL columns): manifest values are returned."""
    step = _make_step(
        step_id="S05",
        step_type=StepType.quality_validation,
        agent_label="QvGate",
        opencode_agent="qv-gate",
        command=None,
        gate=None,
    )
    _write_manifest(
        tmp_path,
        step.work_item_id,
        {"steps": [{"step": "S05", "agent": "qv-gate", "gate": "lint", "command": "make lint"}]},
    )

    gate, command = _get_gate_name_and_command(step, str(tmp_path))
    assert gate == "lint"
    assert command == "make lint"


def test_get_gate_name_and_command_no_manifest_returns_none(tmp_path: Path) -> None:
    """Both DB and manifest empty → (None, None) so caller can short-circuit."""
    step = _make_step(
        step_id="S05",
        step_type=StepType.quality_validation,
        agent_label="QvGate",
        opencode_agent="qv-gate",
        command=None,
        gate=None,
    )
    # No manifest written.
    gate, command = _get_gate_name_and_command(step, str(tmp_path))
    assert gate is None
    assert command is None


# ---------------------------------------------------------------------------
# _build_claude_prompt
# ---------------------------------------------------------------------------


def _build_prompt(step: WorkflowStep, worktree: Path) -> str:
    """Call _build_claude_prompt without instantiating a full BatchManager.

    The method only uses `step` and `worktree_path`; `self` is unused in the
    relevant body (we still pass a SimpleNamespace to satisfy the signature).
    """
    from orch.daemon.batch_manager import BatchManager

    return BatchManager._build_claude_prompt(  # type: ignore[arg-type]
        SimpleNamespace(),  # type: ignore[arg-type]
        step,
        str(worktree),
    )


def test_build_claude_prompt_db_first_for_qv_gate(tmp_path: Path) -> None:
    """DB-populated qv-gate step: prompt is built from DB values, not manifest."""
    step = _make_step(
        step_id="S05",
        step_type=StepType.quality_validation,
        agent_label="QvGate",
        opencode_agent="qv-gate",
        command="make lint",
        gate="lint",
        description="QV: lint",
    )
    _write_manifest(
        tmp_path,
        step.work_item_id,
        {"steps": [{"step": "S05", "agent": "qv-gate", "gate": "WRONG", "command": "WRONG-CMD"}]},
    )

    prompt = _build_prompt(step, tmp_path)
    assert "make lint" in prompt
    assert "lint" in prompt
    assert "WRONG" not in prompt
    assert "WRONG-CMD" not in prompt


def test_build_claude_prompt_falls_back_to_manifest_for_null_columns(tmp_path: Path) -> None:
    """AC4 — legacy item: prompt falls back to manifest read for NULL rows."""
    step = _make_step(
        step_id="S05",
        step_type=StepType.quality_validation,
        agent_label="QvGate",
        opencode_agent="qv-gate",
        command=None,
        gate=None,
    )
    _write_manifest(
        tmp_path,
        step.work_item_id,
        {
            "steps": [
                {
                    "step": "S05",
                    "agent": "qv-gate",
                    "gate": "lint",
                    "command": "make lint",
                    "description": "QV: lint",
                }
            ]
        },
    )

    prompt = _build_prompt(step, tmp_path)
    assert "make lint" in prompt
    assert "lint" in prompt


def test_build_claude_prompt_implementation_step_uses_db_prompt_file(tmp_path: Path) -> None:
    """An implementation step with prompt_file populated reads from that file (DB-first)."""
    item_id = "I-99110"
    design_dir = tmp_path / "ai-dev" / "active" / item_id
    design_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = design_dir / "prompts" / "I-99110_S01_Backend_prompt.md"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text("# This is the DB-pointed prompt body\n", encoding="utf-8")

    step = _make_step(
        work_item_id=item_id,
        step_id="S01",
        step_type=StepType.implementation,
        agent_label="Backend",
        opencode_agent="backend-impl",
        prompt_file="prompts/I-99110_S01_Backend_prompt.md",
    )

    prompt = _build_prompt(step, tmp_path)
    assert "DB-pointed prompt body" in prompt


# ---------------------------------------------------------------------------
# _compute_qv_baselines DB-first selection
# ---------------------------------------------------------------------------


def test_compute_qv_baselines_uses_db_first_when_populated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When DB has populated values, _compute_qv_baselines uses them.

    The on-disk manifest carries different values; we assert the DB wins.
    """
    from orch.daemon import batch_manager as bm

    # Build a minimal BatchManager-like object with just enough to run the
    # gate-selection branch. We monkeypatch the helpers it calls so we can
    # observe which command/gate values get passed downstream.
    captured: dict[str, Any] = {}

    def fake_run_gate_command(_self: Any, command: str, _worktree: str, gate: str) -> str:
        captured["command"] = command
        captured["gate"] = gate
        return ""

    monkeypatch.setattr(bm.BatchManager, "_run_gate_command", fake_run_gate_command)

    # Simulate the parser registry — accept "lint" as a known gate.
    from orch.daemon import qv_baseline as qvb

    monkeypatch.setitem(qvb.GATE_PARSERS, "lint", lambda _output: ())  # type: ignore[arg-type]

    def _noop_upsert(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(bm.BatchManager, "_upsert_qv_baseline", _noop_upsert)

    def _fake_base_sha(*_args: Any, **_kwargs: Any) -> str:
        return "deadbeef"

    monkeypatch.setattr(bm.BatchManager, "_resolve_worktree_base_sha", _fake_base_sha)

    def _fake_manifest(*_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
        return [{"step": "S05", "agent": "qv-gate", "gate": "WRONG", "command": "WRONG-CMD"}]

    monkeypatch.setattr(bm.BatchManager, "_read_workflow_manifest", _fake_manifest)

    step = _make_step(
        step_id="S05",
        step_type=StepType.quality_validation,
        agent_label="QvGate",
        opencode_agent="qv-gate",
        command="make lint",
        gate="lint",
    )

    class _FakeQuery:
        def __init__(self, rows: list[Any]) -> None:
            self._rows = rows

        def filter(self, *_args: Any, **_kwargs: Any) -> _FakeQuery:
            return self

        def all(self) -> list[Any]:
            return self._rows

    class _FakeDB:
        def query(self, _model: Any) -> _FakeQuery:
            return _FakeQuery([step])

        def commit(self) -> None:
            pass

    manager = bm.BatchManager(
        project_id="test-proj",
        project_config=SimpleNamespace(),  # type: ignore[arg-type]
        session_factory=lambda: None,
        config=SimpleNamespace(baseline_qv_enabled=True),  # type: ignore[arg-type]
    )
    manager._compute_qv_baselines(
        _FakeDB(),  # type: ignore[arg-type]
        SimpleNamespace(work_item_id="I-99100"),  # type: ignore[arg-type]
        {"path": str(tmp_path)},
    )

    assert captured["command"] == "make lint", "DB-first failed; fell back to manifest"
    assert captured["gate"] == "lint"
