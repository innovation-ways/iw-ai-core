"""Integration tests for manifest drift detection + auto-refresh (I-00102).

These tests exercise the full register -> drift -> approve pipeline by invoking
the real `iw` Click commands against a PostgreSQL testcontainer. No mocks of
the DB; no live DB.

CRITICAL: assertions are SEMANTIC (specific values), not shape-only.
- GOOD: assert [s.step_id for s in rows] == ["S01", "S02", "S03"]
- BAD:  assert len(workflow_steps) > 0   <- passes even if refresh did nothing

The reproduction test mirrors the CR-00067/S08 scenario: register a 2-step
manifest, edit on disk to 3 steps (new S01 inserted, others renumbered),
approve, and assert the DB exactly reflects the current manifest -- not the
stale registered copy. It would FAIL against the pre-I-00102 code (approve
silently no-ops, workflow_steps stay at the v1 layout).
"""

from __future__ import annotations

import json
import subprocess
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

import pytest
from click.testing import CliRunner

from orch.cli.item_commands import _compute_manifest_digest
from orch.cli.main import cli
from orch.db.models import DaemonEvent, WorkflowStep, WorkItem, WorkItemStatus

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from sqlalchemy.orm import Session

# All test items live in the reserved I-99NNN range so they never collide with
# the production ID sequence (see tests/CLAUDE.md, cross-project isolation).
_PROJECT_ID = "test-proj"


# ---------------------------------------------------------------------------
# On-disk design-package scaffolding
# ---------------------------------------------------------------------------


def _write_design_and_manifest_v1(base: Path, item_id: str) -> None:
    """Write the design package + 2-step manifest v1: S01 Backend, S02 QV.

    Includes the design doc and a functional doc because approve's
    ``ensure_active_files_committed`` git-adds a fixed design-package file set.
    """
    item_dir = base / "ai-dev" / "active" / item_id
    item_dir.mkdir(parents=True, exist_ok=True)

    design_path = item_dir / f"{item_id}_Issue_Design.md"
    design_path.write_text(
        f"# {item_id}\n\n**Type**: Issue\n\n## Impacted Paths\n- `orch/cli/item_commands.py`\n",
        encoding="utf-8",
    )
    (item_dir / f"{item_id}_Functional.md").write_text(
        f"# {item_id} — Functional\n\nTest scaffolding.\n", encoding="utf-8"
    )

    manifest_path = item_dir / "workflow-manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "title": f"{item_id} test drift",
                "steps": [
                    {
                        "step": "S01",
                        "agent": "backend-impl",
                        "prompt": f"prompts/{item_id}_S01_Backend_prompt.md",
                        "description": "Implement the fix",
                    },
                    {
                        "step": "S02",
                        "agent": "qv-gate",
                        "gate": "unit-tests",
                        "prompt": f"prompts/{item_id}_S02_QV_prompt.md",
                        "description": "QV gate",
                    },
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    prompts_dir = item_dir / "prompts"
    prompts_dir.mkdir(exist_ok=True)
    (prompts_dir / f"{item_id}_S01_Backend_prompt.md").write_text("Implement.", encoding="utf-8")
    (prompts_dir / f"{item_id}_S02_QV_prompt.md").write_text("Run unit tests.", encoding="utf-8")


def _write_design_and_manifest_v2(base: Path, item_id: str) -> None:
    """Overwrite the manifest to 3-step v2: S01 Database, S02 Backend, S03 QV.

    Mirrors the CR-00067 scenario: a new step is inserted at the head and every
    subsequent step is renumbered, with prompt files renamed to match.
    """
    item_dir = base / "ai-dev" / "active" / item_id
    manifest_path = item_dir / "workflow-manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "title": f"{item_id} test drift v2",
                "steps": [
                    {
                        "step": "S01",
                        "agent": "database-impl",
                        "prompt": f"prompts/{item_id}_S01_Database_prompt.md",
                        "description": "Database changes",
                    },
                    {
                        "step": "S02",
                        "agent": "backend-impl",
                        "prompt": f"prompts/{item_id}_S02_Backend_prompt.md",
                        "description": "Implement the fix",
                    },
                    {
                        "step": "S03",
                        "agent": "qv-gate",
                        "gate": "unit-tests",
                        "prompt": f"prompts/{item_id}_S03_QV_prompt.md",
                        "description": "QV gate",
                    },
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    prompts_dir = item_dir / "prompts"
    prompts_dir.mkdir(exist_ok=True)
    (prompts_dir / f"{item_id}_S01_Database_prompt.md").write_text("DB changes.", encoding="utf-8")
    (prompts_dir / f"{item_id}_S02_Backend_prompt.md").write_text("Implement.", encoding="utf-8")
    (prompts_dir / f"{item_id}_S03_QV_prompt.md").write_text("Run unit tests.", encoding="utf-8")

    for stale in (
        prompts_dir / f"{item_id}_S01_Backend_prompt.md",
        prompts_dir / f"{item_id}_S02_QV_prompt.md",
    ):
        stale.unlink(missing_ok=True)


def _git_init(base: Path) -> None:
    """Make ``base`` a git repo so approve's ensure_active_files_committed works."""
    for cmd in (
        ["git", "init"],
        ["git", "config", "user.email", "test@test.com"],
        ["git", "config", "user.name", "Test"],
        ["git", "add", "."],
        ["git", "commit", "-m", "initial"],
    ):
        subprocess.run(cmd, cwd=base, capture_output=True, check=False)


def _manifest_digest_on_disk(base: Path, item_id: str) -> str:
    """Digest of the current on-disk manifest, via the production helper."""
    manifest_path = base / "ai-dev" / "active" / item_id / "workflow-manifest.json"
    steps = json.loads(manifest_path.read_text(encoding="utf-8"))["steps"]
    return _compute_manifest_digest(steps)


# ---------------------------------------------------------------------------
# CLI harness
# ---------------------------------------------------------------------------


def _make_get_session(db_session: Session) -> Callable[[], Any]:
    """Build a get_session factory mirroring production transaction semantics.

    Each CLI invocation runs inside a SAVEPOINT that is released on success and
    rolled back on any exception. This lets ``test_approve_drift_rebuild_is_
    atomic_on_failure`` observe a real mid-rebuild rollback while keeping the
    outer per-test transaction (and its fixtures) intact.
    """

    @contextmanager
    def _factory() -> Any:
        savepoint = db_session.begin_nested()
        try:
            yield db_session
        except BaseException:
            if savepoint.is_active:
                savepoint.rollback()
            raise
        else:
            if savepoint.is_active:
                savepoint.commit()

    return _factory


def _invoke_iw(
    args: list[str],
    *,
    get_session: Callable[[], Any],
    repo_root: Path,
    expect_exit: int = 0,
) -> Any:
    """Run an `iw` CLI command with a test-supplied session and repo_root.

    Returns the CliRunner result; fails the test on an unexpected exit code.
    """
    runner = CliRunner()
    obj = {"get_session": get_session, "repo_root": str(repo_root)}
    result = runner.invoke(
        cli,
        ["--project", _PROJECT_ID, *args],
        obj=obj,
        catch_exceptions=False,
    )
    if result.exit_code != expect_exit:
        pytest.fail(
            f"`iw {' '.join(args)}` exited {result.exit_code}, expected {expect_exit}\n"
            f"stdout: {result.output}\nstderr: {result.stderr}"
        )
    return result


def _register_args(item_id: str, title: str) -> list[str]:
    """Build `register` argv with repo-root-relative design-doc / manifest paths.

    Tests chdir into the temp repo root, so register resolves these against the
    temp tree (and stores the relative design_doc_path that approve re-resolves).
    """
    item_dir = f"ai-dev/active/{item_id}"
    return [
        "register",
        item_id,
        title,
        "--type",
        "incident",
        "--design-doc",
        f"{item_dir}/{item_id}_Issue_Design.md",
        "--steps-from",
        f"{item_dir}/workflow-manifest.json",
    ]


def _combined_output(result: Any) -> str:
    """stdout + stderr, lower-cased, for error-message assertions."""
    return f"{result.output}\n{result.stderr}".lower()


# ---------------------------------------------------------------------------
# DB query helpers
# ---------------------------------------------------------------------------


def _workflow_steps(session: Session, item_id: str) -> list[WorkflowStep]:
    return (
        session.query(WorkflowStep)
        .filter(
            WorkflowStep.project_id == _PROJECT_ID,
            WorkflowStep.work_item_id == item_id,
        )
        .order_by(WorkflowStep.step_number)
        .all()
    )


def _refresh_events(session: Session, item_id: str) -> list[DaemonEvent]:
    return (
        session.query(DaemonEvent)
        .filter(
            DaemonEvent.project_id == _PROJECT_ID,
            DaemonEvent.entity_id == item_id,
            DaemonEvent.event_type == "manifest_refreshed",
        )
        .order_by(DaemonEvent.created_at)
        .all()
    )


def _work_item(session: Session, item_id: str) -> WorkItem:
    item = (
        session.query(WorkItem)
        .filter(WorkItem.project_id == _PROJECT_ID, WorkItem.id == item_id)
        .first()
    )
    assert item is not None, f"work item {item_id} not found"
    return item


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_approve_auto_refreshes_workflow_steps_when_manifest_drifted_after_register(
    db_session: Session, test_project: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """I-00102 reproduction (mirrors CR-00067/S08).

    Register manifest v1 (S01 Backend, S02 QV), edit the on-disk manifest to v2
    (S01 Database, S02 Backend, S03 QV), then approve. Approve must atomically
    replace workflow_steps to match v2 and emit a manifest_refreshed event.
    This FAILS on the pre-fix code where approve silently no-ops.
    """
    item_id = "I-99102"
    get_session = _make_get_session(db_session)

    _write_design_and_manifest_v1(tmp_path, item_id)
    _git_init(tmp_path)
    monkeypatch.chdir(tmp_path)

    _invoke_iw(
        _register_args(item_id, "Test drift"),
        get_session=get_session,
        repo_root=tmp_path,
    )
    db_session.expire_all()

    rows_v1 = _workflow_steps(db_session, item_id)
    assert [r.step_id for r in rows_v1] == ["S01", "S02"]
    assert [r.agent_label for r in rows_v1] == ["Backend", "QvGate"]

    item_before = _work_item(db_session, item_id)
    v1_digest = item_before.manifest_digest
    assert v1_digest is not None, "manifest_digest must be populated at register time"
    assert len(v1_digest) == 64, f"digest must be 64-char sha256 hex, got {len(v1_digest)}"

    # Drift: overwrite the on-disk manifest with the renumbered v2 layout.
    _write_design_and_manifest_v2(tmp_path, item_id)
    expected_v2_digest = _manifest_digest_on_disk(tmp_path, item_id)
    assert expected_v2_digest != v1_digest, "v2 manifest must genuinely differ from v1"

    _invoke_iw(["approve", item_id], get_session=get_session, repo_root=tmp_path)
    db_session.expire_all()

    # The DB now reflects manifest v2 exactly -- step IDs and agent labels.
    rows_v2 = _workflow_steps(db_session, item_id)
    assert [r.step_id for r in rows_v2] == ["S01", "S02", "S03"]
    assert [r.agent_label for r in rows_v2] == ["Database", "Backend", "QvGate"]

    # Invariant: the DB's prompt_file column must match the on-disk manifest's
    # prompt paths exactly.  This verifies the rebuild pulled from the real
    # manifest (not a phantom/partial one).  The actual on-disk files may not
    # exist yet if they're untracked in git (tracked by the chore-commit path
    # in ensure_active_files_committed / I-00083), so we assert the DB values
    # match the manifest declaration rather than the filesystem.
    manifest_v2 = json.loads(
        (tmp_path / "ai-dev" / "active" / item_id / "workflow-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    manifest_prompts = {s["step"]: s["prompt"] for s in manifest_v2["steps"]}
    db_prompts = {s.step_id: s.prompt_file for s in rows_v2}
    assert db_prompts == manifest_prompts, (
        f"DB prompt_file values must match manifest prompt declarations: "
        f"{db_prompts!r} != {manifest_prompts!r}"
    )

    # Exactly one manifest_refreshed audit event, naming the real change.
    events = _refresh_events(db_session, item_id)
    assert len(events) == 1, f"expected exactly one manifest_refreshed event, got {len(events)}"
    meta = events[0].event_metadata
    assert meta["old_step_count"] == 2
    assert meta["new_step_count"] == 3
    assert meta["trigger"] == "approve"
    assert meta["old_digest"] == v1_digest
    assert meta["new_digest"] == expected_v2_digest
    assert meta["new_digest"] != meta["old_digest"]

    item_after = _work_item(db_session, item_id)
    assert item_after.manifest_digest == expected_v2_digest
    assert item_after.status == WorkItemStatus.approved


def test_approve_no_drift_does_not_emit_refresh_event(
    db_session: Session, test_project: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Happy path: register then approve with no on-disk edits -> no refresh."""
    item_id = "I-99103"
    get_session = _make_get_session(db_session)

    _write_design_and_manifest_v1(tmp_path, item_id)
    _git_init(tmp_path)
    monkeypatch.chdir(tmp_path)

    _invoke_iw(
        _register_args(item_id, "No drift"),
        get_session=get_session,
        repo_root=tmp_path,
    )
    db_session.expire_all()
    digest_after_register = _work_item(db_session, item_id).manifest_digest

    _invoke_iw(["approve", item_id], get_session=get_session, repo_root=tmp_path)
    db_session.expire_all()

    assert _refresh_events(db_session, item_id) == [], (
        "no manifest_refreshed event must be emitted when disk == DB"
    )
    item = _work_item(db_session, item_id)
    assert item.status == WorkItemStatus.approved
    assert item.manifest_digest == digest_after_register, "digest must be unchanged on no-drift"
    assert [r.step_id for r in _workflow_steps(db_session, item_id)] == ["S01", "S02"]


def test_register_stores_initial_digest(
    db_session: Session, test_project: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """After register, WorkItem.manifest_digest equals the on-disk manifest digest."""
    item_id = "I-99104"
    get_session = _make_get_session(db_session)

    _write_design_and_manifest_v1(tmp_path, item_id)
    _git_init(tmp_path)
    monkeypatch.chdir(tmp_path)

    _invoke_iw(
        _register_args(item_id, "Digest on register"),
        get_session=get_session,
        repo_root=tmp_path,
    )
    db_session.expire_all()

    item = _work_item(db_session, item_id)
    assert item.manifest_digest is not None, "manifest_digest must be non-NULL after register"
    assert item.manifest_digest == _manifest_digest_on_disk(tmp_path, item_id)
    assert len(item.manifest_digest) == 64


def test_approve_with_null_digest_treats_as_drift_and_refreshes(
    db_session: Session, test_project: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC5: pre-I-00102 items have NULL digest; the first approve refreshes."""
    item_id = "I-99105"
    get_session = _make_get_session(db_session)

    # Scaffold the full design package, then drift the manifest to the 3-step
    # v2 layout so register stores the v2 digest.
    _write_design_and_manifest_v1(tmp_path, item_id)
    _write_design_and_manifest_v2(tmp_path, item_id)
    _git_init(tmp_path)
    monkeypatch.chdir(tmp_path)

    _invoke_iw(
        _register_args(item_id, "Null digest backfill"),
        get_session=get_session,
        repo_root=tmp_path,
    )
    db_session.expire_all()
    assert _work_item(db_session, item_id).manifest_digest is not None

    # Simulate a pre-fix legacy row: blank the stored digest.
    db_session.query(WorkItem).filter(
        WorkItem.project_id == _PROJECT_ID, WorkItem.id == item_id
    ).update({"manifest_digest": None})
    db_session.flush()
    db_session.expire_all()

    _invoke_iw(["approve", item_id], get_session=get_session, repo_root=tmp_path)
    db_session.expire_all()

    events = _refresh_events(db_session, item_id)
    assert len(events) == 1, f"NULL digest must trigger one refresh, got {len(events)}"
    assert events[0].event_metadata["old_digest"] is None
    assert events[0].event_metadata["new_digest"] == _manifest_digest_on_disk(tmp_path, item_id)
    assert events[0].event_metadata["trigger"] == "approve"

    item = _work_item(db_session, item_id)
    assert item.manifest_digest == _manifest_digest_on_disk(tmp_path, item_id)
    assert item.status == WorkItemStatus.approved


def test_approve_with_missing_manifest_fails_loudly(
    db_session: Session, test_project: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Error path: a deleted manifest makes approve fail without touching state."""
    item_id = "I-99106"
    get_session = _make_get_session(db_session)

    _write_design_and_manifest_v1(tmp_path, item_id)
    _git_init(tmp_path)
    monkeypatch.chdir(tmp_path)

    _invoke_iw(
        _register_args(item_id, "Missing manifest"),
        get_session=get_session,
        repo_root=tmp_path,
    )
    db_session.expire_all()

    (tmp_path / "ai-dev" / "active" / item_id / "workflow-manifest.json").unlink()

    result = _invoke_iw(
        ["approve", item_id],
        get_session=get_session,
        repo_root=tmp_path,
        expect_exit=1,
    )
    assert "manifest" in _combined_output(result), (
        f"error must name the missing manifest; got: {result.output}{result.stderr}"
    )
    db_session.expire_all()

    # No refresh event, workflow_steps untouched, item still in draft.
    assert _refresh_events(db_session, item_id) == []
    assert [r.step_id for r in _workflow_steps(db_session, item_id)] == ["S01", "S02"]
    assert _work_item(db_session, item_id).status == WorkItemStatus.draft


def test_approve_on_non_draft_item_does_not_refresh(
    db_session: Session, test_project: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC3: the draft-only status guard fires before any drift/refresh logic.

    Register v1 -> approve once -> drift the manifest to v2 -> approve again.
    The second approve must fail on the status guard with NO manifest_refreshed
    event and NO change to workflow_steps or the stored digest.
    """
    item_id = "I-99107"
    get_session = _make_get_session(db_session)

    _write_design_and_manifest_v1(tmp_path, item_id)
    _git_init(tmp_path)
    monkeypatch.chdir(tmp_path)

    _invoke_iw(
        _register_args(item_id, "Non-draft guard"),
        get_session=get_session,
        repo_root=tmp_path,
    )
    db_session.expire_all()
    v1_digest = _work_item(db_session, item_id).manifest_digest

    _invoke_iw(["approve", item_id], get_session=get_session, repo_root=tmp_path)
    db_session.expire_all()
    assert _work_item(db_session, item_id).status == WorkItemStatus.approved

    # Drift the manifest, then attempt a second approve.
    _write_design_and_manifest_v2(tmp_path, item_id)
    result = _invoke_iw(
        ["approve", item_id],
        get_session=get_session,
        repo_root=tmp_path,
        expect_exit=1,
    )
    # The error names the non-draft status the guard rejected.
    assert "approved" in _combined_output(result), (
        f"error must name the non-draft status; got: {result.output}{result.stderr}"
    )
    db_session.expire_all()

    assert _refresh_events(db_session, item_id) == [], (
        "the status guard must fire before the drift/refresh path"
    )
    rows = _workflow_steps(db_session, item_id)
    assert [r.step_id for r in rows] == ["S01", "S02"]
    assert [r.agent_label for r in rows] == ["Backend", "QvGate"]
    assert _work_item(db_session, item_id).manifest_digest == v1_digest


def test_approve_drift_rebuild_is_atomic_on_failure(
    db_session: Session, test_project: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Transaction safety: a crash mid-rebuild rolls back the whole refresh.

    _insert_workflow_steps_from_manifest is monkeypatched to raise after approve
    has already DELETEd the existing rows. The savepoint must roll the DELETE
    back: original workflow_steps, digest and status all unchanged, no event.
    """
    item_id = "I-99108"
    get_session = _make_get_session(db_session)

    _write_design_and_manifest_v1(tmp_path, item_id)
    _git_init(tmp_path)
    monkeypatch.chdir(tmp_path)

    _invoke_iw(
        _register_args(item_id, "Atomicity"),
        get_session=get_session,
        repo_root=tmp_path,
    )
    db_session.expire_all()

    item_before = _work_item(db_session, item_id)
    v1_digest = item_before.manifest_digest
    rows_before = _workflow_steps(db_session, item_id)
    step_ids_before = [r.step_id for r in rows_before]
    agents_before = [r.agent_label for r in rows_before]

    # Drift to v2 so approve enters the rebuild path.
    _write_design_and_manifest_v2(tmp_path, item_id)

    # Make the re-insert raise -- this runs AFTER approve's DELETE.
    import orch.cli.item_commands as item_mod

    def _insert_that_crashes(*_args: Any, **_kwargs: Any) -> int:
        raise RuntimeError("simulated mid-rebuild crash for atomicity test")

    monkeypatch.setattr(item_mod, "_insert_workflow_steps_from_manifest", _insert_that_crashes)

    _invoke_iw(
        ["approve", item_id],
        get_session=get_session,
        repo_root=tmp_path,
        expect_exit=1,
    )
    db_session.expire_all()

    # The DELETE was rolled back -- rows are byte-for-byte intact.
    rows_after = _workflow_steps(db_session, item_id)
    assert [r.step_id for r in rows_after] == step_ids_before
    assert [r.agent_label for r in rows_after] == agents_before

    # No refresh event, digest and status unchanged.
    assert _refresh_events(db_session, item_id) == []
    item_after = _work_item(db_session, item_id)
    assert item_after.manifest_digest == v1_digest
    assert item_after.status == WorkItemStatus.draft
