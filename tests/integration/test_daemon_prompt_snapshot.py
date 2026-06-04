"""CR-00056 AC2/AC3: daemon snapshots prompt content into StepRun at launch.

Tests that the daemon captures the prompt content:
- AC2: initial step run → StepRun.prompt_text == prompt file contents (or fallback)
- AC3: fix-cycle retry → StepRun.fix_prompt_text == fix-prompt file contents
                     + StepRun.prompt_text == base prompt contents (backwards-traceability)

The S01 schema migration is already applied by the testcontainer fixture
(db_engine runs alembic upgrade). The new columns exist but are NULL before
the fix is implemented.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from orch.daemon.batch_manager import BatchManager
from orch.db.models import (
    Project,
    RunStatus,
    StepRun,
    StepStatus,
    StepType,
    WorkflowStep,
    WorkItem,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from orch.config import DaemonConfig
    from orch.daemon.project_registry import ProjectConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def project_config(test_project: Project, tmp_path: Path) -> ProjectConfig:
    """Minimal ProjectConfig for BatchManager."""
    from orch.daemon.project_registry import ProjectConfig

    return ProjectConfig(
        id=test_project.id,
        display_name=test_project.display_name,
        repo_root="/repos/test",
        enabled=True,
        cli_tool="iw",
        model="minimax",
        worktree_base=str(tmp_path / "worktrees"),
        config={},
    )


@pytest.fixture
def daemon_config(tmp_path: Path) -> DaemonConfig:
    """Minimal DaemonConfig for BatchManager."""
    from orch.config import DaemonConfig

    projects_toml = tmp_path / "projects.toml"
    projects_toml.write_text("")
    return DaemonConfig(
        db_host="localhost",
        db_port=5433,
        db_name="test",
        db_user="test",
        db_password="test",  # noqa: S106
        db_url="postgresql+psycopg://test:test@localhost:5433/test",
        dashboard_host="0.0.0.0",  # noqa: S104 test fixture
        dashboard_port=9900,
        poll_interval=60,
        stall_threshold=600,
        pid_file=str(tmp_path / "daemon.pid"),
        archive_dir=str(tmp_path / "archive"),
        archive_ttl=90,
        log_level="DEBUG",
        log_file=str(tmp_path / "daemon.log"),
        projects_toml=projects_toml,
    )


@pytest.fixture
def batch_manager(
    db_session: Session,
    test_project: Project,
    project_config: ProjectConfig,
    daemon_config: DaemonConfig,
    tmp_path: Path,
) -> BatchManager:
    """BatchManager wired to the test DB session."""

    @contextmanager
    def session_factory():
        yield db_session

    return BatchManager(
        project_id=test_project.id,
        project_config=project_config,
        session_factory=session_factory,
        config=daemon_config,
    )


@pytest.fixture
def worktree_path(tmp_path: Path) -> Path:
    """A real on-disk directory that mimics a worktree for prompt-file reads."""
    wt = tmp_path / "worktrees" / "CR-00056-WT"
    wt.mkdir(parents=True, exist_ok=True)
    # Minimal git worktree marker
    (wt / ".git").write_text("gitdir: /real/repo/.git/worktrees/CR-00056-WT\n")
    return wt


@pytest.fixture
def worktree_with_prompt(worktree_path: Path) -> tuple[Path, str]:
    """Create a worktree with a prompt file. Returns (worktree_path, raw_prompt_content)."""
    item_id = "CR-00056"
    design_dir = worktree_path / "ai-dev" / "active" / item_id
    design_dir.mkdir(parents=True, exist_ok=True)

    raw_content = "This is the EXPECTED prompt content for step S04."
    prompt_file = design_dir / "prompts" / "CR-00056_S04_Backend_prompt.md"
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text(raw_content, encoding="utf-8")

    # Also write a manifest so legacy fallback works if needed
    manifest = design_dir / "workflow-manifest.json"
    manifest.write_text(
        '{"steps":[{"step":"S04","prompt":"prompts/CR-00056_S04_Backend_prompt.md"}]}',
        encoding="utf-8",
    )
    return worktree_path, raw_content


@pytest.fixture
def worktree_info(worktree_path: Path) -> dict:
    return {"path": str(worktree_path), "branch": "agent/CR-00056", "created_at": "now"}


def _make_step(
    db_session: Session,
    test_project: Project,
    work_item: WorkItem,
    step_id: str = "S04",
    prompt_file: str | None = None,
    step_type: StepType = StepType.implementation,
) -> WorkflowStep:
    """Create and flush a WorkflowStep row."""
    step = WorkflowStep(
        project_id=test_project.id,
        work_item_id=work_item.id,
        step_id=step_id,
        step_number=4,
        step_type=step_type,
        agent_label="Backend",
        prompt_file=prompt_file,
        status=StepStatus.pending,
    )
    db_session.add(step)
    db_session.flush()
    return step


def _make_work_item(
    db_session: Session,
    project_id: str,
    item_id: str = "CR-00056",
) -> WorkItem:
    """Create and flush a WorkItem row."""
    wi = WorkItem(
        id=item_id,
        project_id=project_id,
        type=WorkItemType.Feature,
        title="Test CR-00056",
        status=WorkItemStatus.approved,
        design_doc_path="ai-dev/active/CR-00056/CR-00056_CR_Design.md",
    )
    db_session.add(wi)
    db_session.flush()
    return wi


def _start_mocks(worktree_path: Path) -> list:
    """Start all common mocks. Returns list for later stop()."""
    from orch.db.alembic_guard import GuardStatus

    ok = GuardStatus(
        current_rev="abc",
        head_rev="abc",
        pending=[],
        multiple_heads=[],
        ok=True,
    )
    fake_wt = {
        "path": str(worktree_path),
        "branch": "agent/test",
        "created_at": "now",
    }
    mocks = [
        patch("orch.daemon.batch_manager.check_db_at_head", return_value=ok),
        patch.object(BatchManager, "_setup_worktree", return_value=fake_wt),
        patch("orch.daemon.batch_manager.subprocess.Popen"),
        patch.object(BatchManager, "_complete_item"),
    ]
    for m in mocks:
        m.start()
    return mocks


def _stop_mocks(mocks: list) -> None:
    for m in reversed(mocks):
        m.stop()


# ---------------------------------------------------------------------------
# AC2: initial run captures prompt_text
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_initial_run_snapshots_prompt_text(
    db_session: Session,
    test_project: Project,
    batch_manager: BatchManager,
    worktree_with_prompt: tuple[Path, str],
    worktree_info: dict,
) -> None:
    """AC2: StepRun.prompt_text contains the wrapped prompt at initial launch."""
    worktree_path, raw_prompt = worktree_with_prompt

    wi = _make_work_item(db_session, test_project.id)
    step = _make_step(
        db_session,
        test_project,
        wi,
        step_id="S04",
        prompt_file="prompts/CR-00056_S04_Backend_prompt.md",
        step_type=StepType.implementation,
    )

    mocks = _start_mocks(worktree_path)
    try:
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        with (
            patch("orch.daemon.batch_manager.subprocess.Popen", return_value=mock_proc),
            patch("orch.agent_runtime.resolver.resolve_runtime") as mock_resolve,
        ):
            mock_option = MagicMock()
            mock_option.cli_tool = "opencode"
            mock_option.model = "minimax"
            mock_option.id = 1
            mock_resolve.return_value = mock_option
            batch_manager._launch_step(db_session, step, worktree_info)
    finally:
        _stop_mocks(mocks)

    db_session.expire_all()

    run: StepRun | None = (
        db_session.query(StepRun)
        .filter(StepRun.step_id == step.id)
        .order_by(StepRun.run_number)
        .first()
    )
    assert run is not None, "StepRun was not created"
    # The snapshot is the full prompt returned by _build_claude_prompt, which
    # wraps the raw file content with step-instructions header + lifecycle cmds.
    # We check that the raw prompt content is embedded in the snapshot.
    assert raw_prompt in (run.prompt_text or ""), (
        f"Expected prompt content to be embedded in snapshot. "
        f"Got: {run.prompt_text!r}\nExpected substring: {raw_prompt!r}"
    )
    assert run.fix_prompt_text is None, "fix_prompt_text must be NULL on initial run"


# ---------------------------------------------------------------------------
# AC3: fix-cycle retry captures fix_prompt_text AND base prompt_text
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_fix_cycle_snapshots_fix_prompt_text_and_base_prompt_text(
    db_session: Session,
    test_project: Project,
    worktree_path: Path,
    worktree_info: dict,
) -> None:
    """AC3: fix-cycle StepRun has fix_prompt_text + base prompt_text (backwards-traceability)."""
    # Setup worktree with a base prompt file
    item_id = "CR-00056"
    design_dir = worktree_path / "ai-dev" / "active" / item_id
    design_dir.mkdir(parents=True, exist_ok=True)

    base_prompt_content = "This is the BASE prompt for S04."
    base_prompt_file = design_dir / "prompts" / "CR-00056_S04_prompt.md"
    base_prompt_file.parent.mkdir(parents=True, exist_ok=True)
    base_prompt_file.write_text(base_prompt_content, encoding="utf-8")

    fix_prompt_content = "This is the FIX-CYCLE prompt for step S04."

    wi = _make_work_item(db_session, test_project.id, item_id)
    step = _make_step(
        db_session,
        test_project,
        wi,
        step_id="S04",
        prompt_file="prompts/CR-00056_S04_prompt.md",
        step_type=StepType.implementation,
    )

    # Simulate a failed first run
    now = datetime.now(UTC)
    first_run = StepRun(
        step_id=step.id,
        run_number=1,
        status=RunStatus.failed,
        error_message="Simulated failure for test",
        started_at=now,
        completed_at=now,
    )
    db_session.add(first_run)
    db_session.flush()  # Ensure _next_run_number sees the first run

    # Write the fix prompt file (simulating what _generate_fix_prompt does)
    fix_dir = worktree_path / "ai-dev" / "active" / item_id / "fix-cycles"
    fix_dir.mkdir(parents=True, exist_ok=True)
    fix_prompt_path = fix_dir / f"{item_id}_S04_FIX_cycle1_prompt.md"
    fix_prompt_path.write_text(fix_prompt_content, encoding="utf-8")

    # _next_run_number needs to count existing runs.  Since we're working with a
    # real db_session (not mocked), this count query will see the flushed first_run.
    # The test calls _launch_fix_agent directly (not via BatchManager) so we also
    # need to patch subprocess.Popen to prevent actual process spawn.
    from orch.daemon.fix_cycle import _launch_fix_agent
    from orch.daemon.project_registry import ProjectConfig

    project_config = ProjectConfig(
        id=test_project.id,
        display_name=test_project.display_name,
        repo_root="/repos/test",
        enabled=True,
        cli_tool="iw",
        model="minimax",
        worktree_base=str(worktree_path.parent.parent),
        config={},
    )
    daemon_config = MagicMock()
    daemon_config.poll_interval = 60
    daemon_config.stall_threshold = 600

    with (
        patch("orch.daemon.fix_cycle.subprocess.Popen") as mock_popen,
        patch("orch.agent_runtime.resolver.resolve_runtime") as mock_resolve,
    ):
        mock_proc = MagicMock()
        mock_proc.pid = 54321
        mock_popen.return_value = mock_proc
        mock_option = MagicMock()
        mock_option.cli_tool = "opencode"
        mock_option.model = "minimax"
        mock_option.id = 1
        mock_resolve.return_value = mock_option

        _launch_fix_agent(
            db_session,
            step,
            str(worktree_path),
            fix_prompt_path,
            project_config,
            daemon_config,
            cycle_number=1,
        )

    db_session.expire_all()

    runs = (
        db_session.query(StepRun)
        .filter(StepRun.step_id == step.id)
        .order_by(StepRun.run_number)
        .all()
    )
    assert len(runs) >= 2, f"Expected at least 2 runs, got {len(runs)}"

    # Latest run is the fix-cycle retry (run_number=2)
    retry_run: StepRun = runs[-1]
    assert retry_run.run_number == 2, f"Expected run_number=2, got {retry_run.run_number}"

    # AC3: fix_prompt_text is the fix-cycle prompt content
    assert retry_run.fix_prompt_text == fix_prompt_content, (
        f"Expected fix_prompt_text to be captured. Got: {retry_run.fix_prompt_text!r}"
    )

    # AC3: prompt_text is the base prompt content (backwards-traceability)
    assert retry_run.prompt_text == base_prompt_content, (
        f"Expected prompt_text (base) to be captured. Got: {retry_run.prompt_text!r}"
    )


# ---------------------------------------------------------------------------
# AC3 edge: missing base prompt file on fix-cycle → NULL (not an error)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_fix_cycle_missing_base_prompt_file_sets_null_not_error(
    db_session: Session,
    test_project: Project,
    worktree_path: Path,
    worktree_info: dict,
) -> None:
    """When the base prompt file is gone on a fix-cycle retry, base prompt_text is NULL."""
    item_id = "CR-00056-NOMINAL"
    design_dir = worktree_path / "ai-dev" / "active" / item_id
    design_dir.mkdir(parents=True, exist_ok=True)

    # Write ONLY the fix prompt file — no base prompt file
    fix_dir = worktree_path / "ai-dev" / "active" / item_id / "fix-cycles"
    fix_dir.mkdir(parents=True, exist_ok=True)
    fix_prompt_path = fix_dir / f"{item_id}_S04_FIX_cycle1_prompt.md"
    fix_prompt_content = "Fix prompt when base is gone."
    fix_prompt_path.write_text(fix_prompt_content, encoding="utf-8")

    wi = _make_work_item(db_session, test_project.id, item_id)
    step = _make_step(
        db_session,
        test_project,
        wi,
        step_id="S04",
        prompt_file="prompts/CR-00056_S04_prompt.md",  # doesn't exist on disk
        step_type=StepType.implementation,
    )

    now = datetime.now(UTC)
    first_run = StepRun(
        step_id=step.id,
        run_number=1,
        status=RunStatus.failed,
        error_message="Simulated failure",
        started_at=now,
        completed_at=now,
    )
    db_session.add(first_run)
    db_session.flush()  # Ensure _next_run_number sees the first run

    from orch.daemon.fix_cycle import _launch_fix_agent
    from orch.daemon.project_registry import ProjectConfig

    project_config = ProjectConfig(
        id=test_project.id,
        display_name=test_project.display_name,
        repo_root="/repos/test",
        enabled=True,
        cli_tool="iw",
        model="minimax",
        worktree_base=str(worktree_path.parent.parent),
        config={},
    )
    daemon_config = MagicMock()
    daemon_config.poll_interval = 60
    daemon_config.stall_threshold = 600

    with (
        patch("orch.daemon.fix_cycle.subprocess.Popen") as mock_popen,
        patch("orch.agent_runtime.resolver.resolve_runtime") as mock_resolve,
    ):
        mock_proc = MagicMock()
        mock_proc.pid = 54321
        mock_popen.return_value = mock_proc
        mock_option = MagicMock()
        mock_option.cli_tool = "opencode"
        mock_option.model = "minimax"
        mock_option.id = 1
        mock_resolve.return_value = mock_option

        _launch_fix_agent(
            db_session,
            step,
            str(worktree_path),
            fix_prompt_path,
            project_config,
            daemon_config,
            cycle_number=1,
        )

    db_session.expire_all()

    runs = (
        db_session.query(StepRun)
        .filter(StepRun.step_id == step.id)
        .order_by(StepRun.run_number)
        .all()
    )
    retry_run: StepRun = runs[-1]

    # fix_prompt_text is set (the fix prompt file exists and was read)
    assert retry_run.fix_prompt_text == fix_prompt_content, (
        f"Expected fix_prompt_text to be set. Got: {retry_run.fix_prompt_text!r}"
    )
    # prompt_text (base) is NULL because the base file didn't exist
    assert retry_run.prompt_text is None, (
        f"Expected prompt_text (base) to be NULL when base file missing. "
        f"Got: {retry_run.prompt_text!r}"
    )


# ---------------------------------------------------------------------------
# AC2 edge: missing prompt file → NULL (graceful degradation, not an error)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_initial_run_with_missing_prompt_file_creates_step_run_with_fallback_prompt(
    db_session: Session,
    test_project: Project,
    batch_manager: BatchManager,
    worktree_path: Path,
    worktree_info: dict,
) -> None:
    """When the prompt_file path does not exist, the daemon creates StepRun with a fallback prompt.

    The daemon does NOT raise — it generates a fallback prompt (the ## Step Instructions
    block) so the step can still execute. This is the 'graceful degradation' behaviour.
    The fallback prompt is NOT NULL — it contains the step-instructions block.
    The test verifies:
    1. No exception is raised (graceful degradation)
    2. StepRun is created
    3. prompt_text is a non-empty fallback string (not NULL)
    """
    item_id = "CR-00056-NO-FILE"
    design_dir = worktree_path / "ai-dev" / "active" / item_id
    design_dir.mkdir(parents=True, exist_ok=True)

    # Do NOT create the prompt file — simulate a missing file scenario
    wi = _make_work_item(db_session, test_project.id, item_id)
    step = _make_step(
        db_session,
        test_project,
        wi,
        step_id="S04",
        prompt_file="prompts/CR-00056_S04_Missing_prompt.md",  # doesn't exist on disk
        step_type=StepType.implementation,
    )

    mocks = _start_mocks(worktree_path)
    try:
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        with (
            patch("orch.daemon.batch_manager.subprocess.Popen", return_value=mock_proc),
            patch("orch.agent_runtime.resolver.resolve_runtime") as mock_resolve,
        ):
            mock_option = MagicMock()
            mock_option.cli_tool = "opencode"
            mock_option.model = "minimax"
            mock_option.id = 1
            mock_resolve.return_value = mock_option
            # Must not raise — the daemon handles missing prompt files gracefully
            batch_manager._launch_step(db_session, step, worktree_info)
    finally:
        _stop_mocks(mocks)

    db_session.expire_all()

    run: StepRun | None = (
        db_session.query(StepRun)
        .filter(StepRun.step_id == step.id)
        .order_by(StepRun.run_number)
        .first()
    )
    assert run is not None, "StepRun should be created even when prompt file is missing"
    # The daemon generates a fallback prompt (## Step Instructions block), not NULL
    assert run.prompt_text is not None, (
        "Expected fallback prompt text (daemon generates step-instructions block), "
        "but got NULL. This means the daemon is not handling missing files gracefully."
    )
    assert len(run.prompt_text) > 0, "Fallback prompt should be non-empty"
    assert "CR-00056-NO-FILE" in run.prompt_text, (
        f"Expected fallback prompt to contain item ID, got: {run.prompt_text[:100]!r}"
    )
    assert run.fix_prompt_text is None, "fix_prompt_text must remain NULL on initial run"


# ---------------------------------------------------------------------------
# QV-gate step (no prompt file) → NULL prompt columns
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_qv_gate_step_run_has_null_prompt_text(
    db_session: Session,
    test_project: Project,
    batch_manager: BatchManager,
    worktree_path: Path,
    worktree_info: dict,
) -> None:
    """Gate/QV-style steps (command=..., no prompt_file) create StepRun with NULL prompt columns."""
    item_id = "CR-00056-QV-GATE"
    design_dir = worktree_path / "ai-dev" / "active" / item_id
    design_dir.mkdir(parents=True, exist_ok=True)

    wi = _make_work_item(db_session, test_project.id, item_id)

    # Gate step: has command but no prompt_file
    gate_step = WorkflowStep(
        project_id=test_project.id,
        work_item_id=wi.id,
        step_id="S03",
        step_number=3,
        step_type=StepType.quality_validation,  # Gate-style step (no prompt file)
        agent_label="QV Gate",
        prompt_file=None,  # Gate steps don't use prompt files
        command="make quality",  # gate-style command
        status=StepStatus.pending,
    )
    db_session.add(gate_step)
    db_session.flush()

    mocks = _start_mocks(worktree_path)
    try:
        mock_proc = MagicMock()
        mock_proc.pid = 99999
        with (
            patch("orch.daemon.batch_manager.subprocess.Popen", return_value=mock_proc),
            patch("orch.agent_runtime.resolver.resolve_runtime") as mock_resolve,
        ):
            mock_option = MagicMock()
            mock_option.cli_tool = "opencode"
            mock_option.model = "minimax"
            mock_option.id = 1
            mock_resolve.return_value = mock_option
            batch_manager._launch_step(db_session, gate_step, worktree_info)
    finally:
        _stop_mocks(mocks)

    db_session.expire_all()

    run: StepRun | None = (
        db_session.query(StepRun)
        .filter(StepRun.step_id == gate_step.id)
        .order_by(StepRun.run_number)
        .first()
    )
    assert run is not None, "StepRun for gate step should be created"
    # Gate steps don't snapshot prompts
    assert run.prompt_text is None, (
        f"Expected NULL prompt_text for gate step, got: {run.prompt_text!r}"
    )
    assert run.fix_prompt_text is None, "fix_prompt_text must be NULL for gate step"
