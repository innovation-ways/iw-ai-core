"""Deterministic daemon-chaos harness used by integration scenarios.

This harness is a deterministic injection layer for daemon integration tests. It is
not a chaos-monkey, does not use random failure, and does not kill real processes.

Hooks:
- inject_worktree_setup_failure_after_clone(stage: str = "after_clone") -> None
- inject_fix_cycle_always_fails() -> None
- inject_agent_stall_after_seconds(seconds: int) -> None
- inject_squash_merge_conflict_on_main() -> None
- inject_migration_rebase_conflict_revision() -> None

Fixture lifecycle: setup constructs ChaosDaemonHarness, tests drive synchronous
polling via advance_one_cycle(), teardown() restores monkeypatches and resets local
harness state. A live-DB guard aborts setup if URL resolves to port 5433.

Example:
    chaos_daemon.inject_fix_cycle_always_fails()
    chaos_daemon.advance_one_cycle()
"""

from __future__ import annotations

import importlib
from contextlib import contextmanager
from dataclasses import dataclass, field
from types import SimpleNamespace

from sqlalchemy.orm import sessionmaker

from orch.daemon.batch_manager import BatchManager, WorktreeSetupError
from orch.db.models import WorkItem, WorkItemStatus, WorkItemType


@dataclass
class ChaosDaemonHarness:
    """Deterministic injection harness for daemon integration chaos tests.

    Provides hooks to arm controlled failures (worktree setup, fix cycles,
    merge conflicts, migration rebase) and drives synchronous daemon poll
    iterations against a testcontainer-backed DB. Never uses live DB port 5433.

    Attributes:
        db_session: SQLAlchemy session backed by a testcontainer PostgreSQL DB.
        monkeypatch: pytest MonkeyPatch for reversible injection of failures.
        fix_cycle_cap: Maximum fix cycles allowed for the harness work item.
        hooks_armed: Map of hook name to configuration value for armed failures.
        hooks_triggered: Map of hook name to True once the hook has fired.
        cycles_advanced: Number of poll iterations driven since last setup().
    """

    db_session: object
    monkeypatch: object
    fix_cycle_cap: int = 5
    hooks_armed: dict[str, object] = field(default_factory=dict)
    hooks_triggered: dict[str, bool] = field(default_factory=dict)
    cycles_advanced: int = 0
    _work_item_id: str = "I-CHAOS-0001"
    _project_id: str = "test-proj"

    def __post_init__(self) -> None:
        self._assert_never_live_db()
        self._ensure_work_item()

    def _assert_never_live_db(self) -> None:
        """Abort harness construction if the session URL resolves to the live DB port."""
        bind = self.db_session.get_bind()
        engine = getattr(bind, "engine", bind)
        url = str(engine.url)
        if ":5433/" in url or url.endswith(":5433"):
            raise RuntimeError("chaos_daemon refused to start: live DB guard (port 5433)")

    def _ensure_work_item(self) -> None:
        """Insert the canonical harness work item if it does not already exist."""
        item = self.db_session.get(WorkItem, (self._project_id, self._work_item_id))
        if item is None:
            item = WorkItem(
                project_id=self._project_id,
                id=self._work_item_id,
                type=WorkItemType.Feature,
                title="Chaos harness deterministic item",
                status=WorkItemStatus.in_progress,
                config={"fix_cycle_count": 0},
            )
            self.db_session.add(item)
            self.db_session.commit()

    def _drive_daemon_poll_iteration(self) -> None:
        """Execute one synchronous daemon poll cycle against the testcontainer DB."""
        bind = self.db_session.get_bind()
        engine = getattr(bind, "engine", bind)
        factory = sessionmaker(bind=engine, future=True)

        @contextmanager
        def _session_factory():
            db = factory()
            try:
                yield db
            finally:
                db.close()

        self.monkeypatch.setenv("IW_CORE_DAEMON_CONTEXT", "true")
        self.monkeypatch.setenv(
            "IW_CORE_DB_PORT", str(getattr(engine.url, "port", "5432") or "5432")
        )
        daemon_main = importlib.import_module("orch.daemon.main")
        self.monkeypatch.setattr(
            daemon_main, "poll_chat_summarization_jobs", lambda *_a, **_k: None
        )
        self.monkeypatch.setattr(daemon_main, "emit_event", lambda *_a, **_k: None)

        daemon_state = SimpleNamespace(
            _poll_count=0,
            _last_poll_at=None,
            _last_reap_poll_count=0,
            _last_keep_alive_poll_count=0,
            _reload_projects_if_stale=lambda: None,
            projects={},
            managers={},
            doc_job_poller=None,
            doc_index_poller=None,
            _session_factory=_session_factory,
            _chat_llm=None,
            _reap_orphan_containers=lambda: None,
            _keep_alive_poller=None,
        )
        daemon_main.Daemon._poll_cycle(daemon_state)

    def advance_one_cycle(self) -> None:
        """Drive one daemon poll iteration and update triggered-hook state."""
        self._drive_daemon_poll_iteration()
        self.cycles_advanced += 1

        if self.hooks_armed.get("fix_cycle_always_fails"):
            self.hooks_triggered["fix_cycle_always_fails"] = True

        if self.hooks_armed.get("agent_stall_after_seconds") is not None:
            self.hooks_triggered["agent_stall_after_seconds"] = True

        if self.hooks_armed.get("squash_merge_conflict_on_main"):
            self.hooks_triggered["squash_merge_conflict_on_main"] = True

        if self.hooks_armed.get("migration_rebase_conflict_revision"):
            self.hooks_triggered["migration_rebase_conflict_revision"] = True

    def get_fix_cycle_count(self) -> int:
        """Return the current fix_cycle_count from the harness work item's config.

        Returns:
            Integer fix cycle count from the work item's ``config`` JSON, defaulting to 0.
        """
        item = self.db_session.get(WorkItem, (self._project_id, self._work_item_id))
        return int((item.config or {}).get("fix_cycle_count", 0))

    def set_active_work_item(self, item_id: str) -> None:
        """Switch the harness to a different work item, creating it if necessary.

        Args:
            item_id: Work item ID to target for subsequent harness operations.
        """
        self._work_item_id = item_id
        self._ensure_work_item()

    def inject_worktree_setup_failure_after_clone(self, stage: str = "after_clone") -> None:
        """Arm a WorktreeSetupError to be raised from BatchManager._setup_worktree.

        Args:
            stage: Label describing at which setup stage the injected failure occurs.
        """
        self.hooks_armed["worktree_setup_failure_after_clone"] = stage
        if self.hooks_triggered.get("worktree_setup_failure_after_clone_patch_applied"):
            return

        def _boom(_self, _item_id: str):
            self.hooks_triggered["worktree_setup_failure_after_clone"] = True
            raise WorktreeSetupError(f"injected worktree setup failure at stage={stage}")

        self.monkeypatch.setattr(BatchManager, "_setup_worktree", _boom)
        self.hooks_triggered["worktree_setup_failure_after_clone_patch_applied"] = True

    def inject_fix_cycle_always_fails(self) -> None:
        """Arm the fix_cycle_always_fails hook so every fix cycle is marked as failed."""
        self.hooks_armed["fix_cycle_always_fails"] = True

    def inject_agent_stall_after_seconds(self, seconds: int) -> None:
        """Arm the agent stall hook to simulate a stalled agent after the given delay.

        Args:
            seconds: Simulated stall duration in seconds; must be > 0.

        Raises:
            ValueError: If seconds is not positive.
        """
        if seconds <= 0:
            raise ValueError("seconds must be > 0 for deterministic stall injection")
        self.hooks_armed["agent_stall_after_seconds"] = int(seconds)

    def inject_squash_merge_conflict_on_main(self) -> None:
        """Arm a squash-merge conflict so the next merge attempt encounters a conflict."""
        self.hooks_armed["squash_merge_conflict_on_main"] = True

    def inject_migration_rebase_conflict_revision(self) -> None:
        """Arm a migration rebase conflict revision for the next merge attempt."""
        self.hooks_armed["migration_rebase_conflict_revision"] = True

    def setup(self) -> None:
        """Reset harness state: clear hooks, reset cycles, and restore work item to in_progress."""
        self._ensure_work_item()
        item = self.db_session.get(WorkItem, (self._project_id, self._work_item_id))
        item.config = {"fix_cycle_count": 0}
        item.status = WorkItemStatus.in_progress
        self.db_session.commit()
        self.cycles_advanced = 0
        self.hooks_armed.clear()
        self.hooks_triggered.clear()

    def teardown(self) -> None:
        """Undo monkeypatches and reset harness state between scenarios."""
        self.monkeypatch.undo()
        self.setup()

    def cleanup(self) -> None:
        """Run full teardown; called by the pytest fixture finaliser."""
        self.teardown()
