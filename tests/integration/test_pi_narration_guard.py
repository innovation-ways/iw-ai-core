from __future__ import annotations

import inspect
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from orch.daemon.batch_manager import _build_initial_command
from orch.db.models import (
    Project,
    RunStatus,
    StepRun,
    StepStatus,
    StepType,
    WorkflowStep,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)


def _ensure_cli_project(db_session: Session) -> str:
    project_id = "iw-ai-core"
    if db_session.get(Project, project_id) is None:
        db_session.add(
            Project(
                id=project_id,
                display_name="IW AI Core",
                repo_root="/repo/iw-ai-core",
                config={},
            )
        )
        db_session.flush()
    return project_id


def _seed_step(db_session: Session, project_id: str, *, status: StepStatus) -> tuple[str, str, int]:
    item_id = f"I-00114-T-{status.value}"
    step_id = "S04"
    item = WorkItem(
        project_id=project_id,
        id=item_id,
        type=WorkItemType.Issue,
        title="narration guard test",
        status=WorkItemStatus.in_progress,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
        impacted_paths=[],
    )
    db_session.add(item)
    db_session.flush()

    step = WorkflowStep(
        project_id=project_id,
        work_item_id=item_id,
        step_number=1,
        step_id=step_id,
        agent_label="Tests",
        step_type=StepType.implementation,
        status=status,
    )
    db_session.add(step)
    db_session.flush()

    run = StepRun(step_id=step.id, run_number=1, status=RunStatus.running)
    db_session.add(run)
    db_session.commit()
    return item_id, step_id, step.id


def _install_pi_stub(tmp_path: Path, monkeypatch) -> tuple[Path, Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    pi_script = bin_dir / "pi"
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    counter_file = tmp_path / "counter.txt"
    counter_file.write_text("0", encoding="utf-8")

    shim = (
        "#!/usr/bin/env bash\n"
        f'"{sys.executable}" "{Path("tests/integration/_stub_pi.py").resolve()}" "$@"\n'
    )
    pi_script.write_text(shim, encoding="utf-8")
    pi_script.chmod(pi_script.stat().st_mode | stat.S_IEXEC)

    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ.get('PATH', '')}")
    monkeypatch.setenv("PI_CODING_AGENT_SESSION_DIR", str(tmp_path / "sessions"))
    monkeypatch.setenv("STUB_PI_MARKER_DIR", str(marker_dir))
    monkeypatch.setenv("STUB_PI_COUNTER_FILE", str(counter_file))

    return marker_dir, counter_file


def _run_guard(
    item_id: str,
    step_id: str,
    *,
    cwd: Path,
    project_id: str = "iw-ai-core",
    max_reprompts: int = 5,
) -> subprocess.CompletedProcess[str]:
    """Run the narration guard against the seeded step, hermetically.

    The guard shells out to ``uv run iw item-status`` which resolves the project
    from a ``.iw-orch.json`` found by walking up from its working directory — in
    production that file lives in the agent's worktree. To keep the test
    independent of the (gitignored) repo-root ``.iw-orch.json`` that only exists
    on developer machines, we write a throwaway ``.iw-orch.json`` into ``cwd``
    and launch the guard there, while pinning ``uv`` to the real project via
    ``UV_PROJECT`` so ``uv run`` still finds the ``iw`` entry point.

    Args:
        item_id: Seeded work item ID to poll.
        step_id: Seeded step ID to poll.
        cwd: Hermetic working directory the guard runs in (gets a ``.iw-orch.json``).
        project_id: Project ID written into the throwaway ``.iw-orch.json``.
        max_reprompts: Reprompt cap passed to the guard.

    Returns:
        The completed guard subprocess.
    """
    repo_root = Path.cwd()
    (cwd / ".iw-orch.json").write_text(json.dumps({"project_id": project_id}), encoding="utf-8")

    env = os.environ.copy()
    for key in ("HOST", "PORT", "NAME", "USER", "PASSWORD"):
        env[f"IW_CORE_ORCH_DB_{key}"] = env[f"IW_CORE_DB_{key}"]
    env["IW_CORE_OPERATOR_APPLY"] = "true"
    env["UV_PROJECT"] = str(repo_root)

    return subprocess.run(
        [
            "python",
            str(repo_root / "executor" / "pi_narration_guard.py"),
            "--item-id",
            item_id,
            "--step-id",
            step_id,
            "--max-reprompts",
            str(max_reprompts),
            "--",
            "pi",
            "-p",
            "prompt",
            "--model",
            "openai-codex/gpt-5.3-codex",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
        cwd=str(cwd),
        env=env,
    )


def _narration_events(db_session: Session, project_id: str, item_id: str) -> list[dict]:
    rows = db_session.execute(
        text(
            "SELECT metadata FROM daemon_events "
            "WHERE project_id=:project_id "
            "AND entity_id=:item_id "
            "AND event_type='step_narration_exit' "
            "ORDER BY id"
        ),
        {"project_id": project_id, "item_id": item_id},
    ).fetchall()
    return [row[0] for row in rows]


def test_narration_exit_emits_event_and_reprompts(
    db_session: Session, tmp_path: Path, monkeypatch
) -> None:
    """RED anchor: pre-fix F-00089 S05 exited on [thinking,text] and burned retries."""
    project_id = _ensure_cli_project(db_session)
    item_id, step_id, step_pk = _seed_step(db_session, project_id, status=StepStatus.in_progress)
    marker_dir, _ = _install_pi_stub(tmp_path, monkeypatch)
    monkeypatch.setenv("STUB_PI_EXIT_CODE", "0")
    monkeypatch.setenv("STUB_PI_WRITE_SESSION", "1")
    monkeypatch.setenv("STUB_PI_SESSION_KIND", "narration")

    result = _run_guard(item_id, step_id, cwd=tmp_path, project_id=project_id)

    assert result.returncode == 0, result.stderr
    narration_events = _narration_events(db_session, project_id, item_id)
    assert len(narration_events) == 5, result.stderr
    assert [e["reprompt_attempt"] for e in narration_events] == [1, 2, 3, 4, 5]
    assert all(e["max_reprompts"] == 5 for e in narration_events)
    assert "I'll now run tests" in narration_events[0]["last_assistant_text"]
    run_count = db_session.execute(
        text("SELECT COUNT(*) FROM step_runs WHERE step_id=:step_id"), {"step_id": step_pk}
    ).scalar_one()
    assert run_count == 1
    assert len(list(marker_dir.glob("invocation-*.txt"))) == 6


def test_clean_exit_with_step_done_does_not_reprompt(
    db_session: Session, tmp_path: Path, monkeypatch
) -> None:
    project_id = _ensure_cli_project(db_session)
    item_id, step_id, _ = _seed_step(db_session, project_id, status=StepStatus.completed)
    marker_dir, _ = _install_pi_stub(tmp_path, monkeypatch)
    monkeypatch.setenv("STUB_PI_EXIT_CODE", "0")
    monkeypatch.setenv("STUB_PI_SESSION_KIND", "narration")

    result = _run_guard(item_id, step_id, cwd=tmp_path, project_id=project_id)

    assert result.returncode == 0, result.stderr
    assert _narration_events(db_session, project_id, item_id) == []
    assert len(list(marker_dir.glob("invocation-*.txt"))) == 1


def test_non_zero_pi_exit_does_not_reprompt(
    db_session: Session, tmp_path: Path, monkeypatch
) -> None:
    project_id = _ensure_cli_project(db_session)
    item_id, step_id, _ = _seed_step(db_session, project_id, status=StepStatus.in_progress)
    marker_dir, _ = _install_pi_stub(tmp_path, monkeypatch)
    monkeypatch.setenv("STUB_PI_EXIT_CODE", "42")

    result = _run_guard(item_id, step_id, cwd=tmp_path, project_id=project_id)

    assert result.returncode == 42
    assert _narration_events(db_session, project_id, item_id) == []
    assert len(list(marker_dir.glob("invocation-*.txt"))) == 1


def test_guard_falls_back_after_5_reprompts(
    db_session: Session, tmp_path: Path, monkeypatch
) -> None:
    project_id = _ensure_cli_project(db_session)
    item_id, step_id, _ = _seed_step(db_session, project_id, status=StepStatus.in_progress)
    marker_dir, _ = _install_pi_stub(tmp_path, monkeypatch)
    monkeypatch.setenv("STUB_PI_EXIT_CODE", "0")
    monkeypatch.setenv("STUB_PI_SESSION_KIND", "narration")

    result = _run_guard(item_id, step_id, cwd=tmp_path, project_id=project_id, max_reprompts=5)

    assert result.returncode == 0, result.stderr
    assert len(_narration_events(db_session, project_id, item_id)) == 5, result.stderr
    assert len(list(marker_dir.glob("invocation-*.txt"))) == 6


def test_opencode_launch_does_not_use_guard() -> None:
    base_kwargs = {
        "prompt_file": "/wt/.tmp/I-00114_S04.prompt",
        "worktree_path": "/wt",
    }
    if "item_id" in inspect.signature(_build_initial_command).parameters:
        base_kwargs["item_id"] = "I-00114"
        base_kwargs["step_id"] = "S04"

    opencode_cmd = _build_initial_command(
        cli_tool="opencode",
        resolved_model="minimax/MiniMax-M2.7",
        agent_args="--agent backend-impl",
        **base_kwargs,
    )
    claude_cmd = _build_initial_command(
        cli_tool="claude",
        resolved_model="anthropic/claude-sonnet-4-6",
        agent_args="",
        **base_kwargs,
    )

    assert "pi_narration_guard" not in opencode_cmd
    assert "pi_narration_guard" not in claude_cmd
    assert opencode_cmd.startswith("opencode run ")
    assert claude_cmd.startswith("claude -p ")
