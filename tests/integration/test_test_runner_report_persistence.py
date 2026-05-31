"""Integration tests for report-dir persistence in launch_test_run.

Asserts that ``run.allure_report_dir`` is set ONLY after a real
allure-report directory is generated (no dangling pointer when no
results are produced), and that ``run.summary`` is populated when
parsing succeeds.  No real subprocess runs.

These tests cover the secondary fix from I-00121 S01: gating
``run.allure_report_dir`` on ``_generate_allure_report`` return value.

Why the import is deferred (inside the test function)
-------------------------------------------------------
``orch.test_runner`` imports ``orch.db.session`` which calls
``get_db_url()`` to build its engine.  At pytest *collection* time,
the env vars are not yet patched by ``db_engine``, so ``get_db_url()``
returns the LIVE orch DB URL.  The live DB host:port matches the live DB,
and ``IW_CORE_TEST_CONTEXT=true`` → ``live_db_guard`` raises
``LiveDbConnectionRefusedError`` during collection.

By importing ``launch_test_run`` inside the test function, we defer the
engine-creation until after ``db_engine`` has patched env vars.  The
deferred import reads the testcontainer URL from env, passes
``is_live_db_url()`` (host:port are the testcontainer's, not the live
orch's), and creates a valid engine.

The session module cache is reset before each deferred import so every
test gets a fresh engine on its own testcontainer clone.
"""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from orch.db import live_db_guard as _ldg
from orch.db.models import Project, TestRun, TestRunStatus


# Reset the cached globals in ``orch.db.session`` so that each deferred
# ``from orch.test_runner import launch_test_run`` creates a fresh engine
# with the testcontainer URL.  Without this, the second test re-uses the
# first test's engine (module-level cache), pointing at a stale clone.
def _reset_session_cache() -> None:
    import orch.db.session as _sm

    _sm._engine = None
    _sm._session_local = None
    _sm._orch_engine = None
    _sm._orch_session_local = None


# ``_SingleSessionLocal`` always returns the same session instance.
# ``expire_on_commit=False`` keeps objects usable after commit (the test
# re-queries via scalar() anyway).
class _SingleSessionLocal:
    __slots__ = ("_session",)

    def __init__(self, session: Session) -> None:
        object.__setattr__(self, "_session", session)

    def __call__(self) -> Session:
        return object.__getattribute__(self, "_session")


class TestAllureReportPersistence:
    """report_dir is persisted only when _generate_allure_report succeeds."""

    def test_report_dir_set_when_results_exist_and_report_generated(
        self, db_session: Session
    ) -> None:
        """When the allure-results dir exists and report generation succeeds,
        ``run.allure_report_dir`` is set to the expected category path
        and ``run.summary`` is populated."""
        _reset_session_cache()

        session_bind = db_session.get_bind()
        session_engine = session_bind if hasattr(session_bind, "url") else session_bind.engine

        project_id = f"i00121-test-{uuid.uuid4().hex[:8]}"
        # test_session_factory produces new sessions on the shared engine so
        # that launch_test_run's SessionLocal (patched to single_factory)
        # reads/writes the same clone as the test code.
        test_session_factory = sessionmaker(bind=session_engine, autocommit=False, autoflush=False)
        test_session = test_session_factory()

        try:
            proj = Project(
                id=project_id,
                display_name="I00121 Test Project",
                repo_root="/tmp",
                config={
                    "test_config": {
                        "allure_results_dir": "allure-results",
                        "allure_report_dir": "allure-report",
                        "categories": {
                            "make-test": {
                                "label": "make-test",
                                "command": "make make-test",
                            },
                        },
                    },
                },
            )
            test_session.add(proj)
            test_session.flush()

            run = TestRun(
                project_id=project_id,
                category="make-test",
                command="make make-test",
                run_type="test",
                status=TestRunStatus.pending,
            )
            test_session.add(run)
            test_session.flush()
            run_id = run.id
            test_session.commit()

            with tempfile.TemporaryDirectory() as tmp:
                # Replace the config dict entirely so SQLAlchemy change-tracking
                # picks up the modification (in-place dict mutation is not tracked).
                proj = test_session.get(Project, project_id)
                new_config: dict = dict(proj.config)
                new_config["test_config"] = dict(new_config.get("test_config", {}))
                new_config["test_config"]["execution_dir"] = tmp
                proj.config = new_config
                test_session.commit()

                # Pre-create the results dir so the Popen mock can skip creation.
                Path(tmp).joinpath(f"allure-results-{run_id}").mkdir(parents=True, exist_ok=True)

                report_base = "allure-report"
                expected_report_dir = f"{tmp}/{report_base}/make-test"

                mock_proc = MagicMock()
                mock_proc.pid = 99999
                mock_proc.wait.return_value = 0

                def fake_popen(*_args, **_kwargs) -> MagicMock:
                    return mock_proc

                fake_summary = {
                    "statistic": {
                        "total": 10,
                        "passed": 8,
                        "failed": 1,
                        "skipped": 1,
                        "broken": 0,
                    },
                    "time": {"duration": 5000},
                }

                def fake_generate(
                    results_dir: str,
                    report_dir: str | None,
                    cwd: str,  # noqa: ARG001
                ) -> bool:
                    if report_dir:
                        Path(report_dir).mkdir(parents=True, exist_ok=True)
                        (Path(report_dir) / "index.html").write_text(
                            "<html><body>fake</body></html>",
                            encoding="utf-8",
                        )
                        widgets = Path(report_dir) / "widgets"
                        widgets.mkdir(parents=True, exist_ok=True)
                        (widgets / "statistic.json").write_text(
                            '{"total":10,"passed":8,"failed":1,"skipped":1,"broken":0}',
                            encoding="utf-8",
                        )
                    return True

                single_factory = _SingleSessionLocal(test_session)

                with (
                    patch.object(_ldg, "is_live_db_url", lambda *_a, **_kw: False),
                    patch("orch.db.session.SessionLocal", single_factory),
                    patch("orch.db.session._session_local", single_factory),
                    patch("orch.test_runner.SessionLocal", single_factory),
                    patch("orch.test_runner.subprocess.Popen", side_effect=fake_popen),
                    patch(
                        "orch.test_runner._generate_allure_report",
                        side_effect=fake_generate,
                    ),
                    patch(
                        "orch.test_runner.parse_allure_summary",
                        lambda _d: fake_summary if _d else None,
                    ),
                ):
                    from orch.test_runner import launch_test_run

                    launch_test_run(run_id)

            # Verify through a fresh session on the same engine.
            verify_session = sessionmaker(bind=session_engine, expire_on_commit=False)()
            try:
                run = verify_session.scalar(select(TestRun).where(TestRun.id == run_id))
            finally:
                verify_session.close()

            assert run is not None
            assert run.status == TestRunStatus.passed
            assert run.exit_code == 0
            # primary fix: report_dir set only after generation (no dangling ptr):
            assert run.allure_report_dir == expected_report_dir
            # secondary fix: summary populated:
            assert run.summary == fake_summary
        finally:
            test_session.close()

    def test_report_dir_null_when_no_results_dir(self, db_session: Session) -> None:
        """When the allure-results dir is never created ``run.allure_report_dir``
        must remain NULL — no dangling pointer."""
        _reset_session_cache()

        session_bind = db_session.get_bind()
        session_engine = session_bind if hasattr(session_bind, "url") else session_bind.engine

        project_id = f"i00121-test-{uuid.uuid4().hex[:8]}"
        test_session_factory = sessionmaker(bind=session_engine, autocommit=False, autoflush=False)
        test_session = test_session_factory()

        try:
            proj = Project(
                id=project_id,
                display_name="I00121 Test Project",
                repo_root="/tmp",
                config={
                    "test_config": {
                        "allure_results_dir": "allure-results",
                        "allure_report_dir": "allure-report",
                        "categories": {
                            "make-test-2": {
                                "label": "make-test-2",
                                "command": "make make-test-2",
                            },
                        },
                    },
                },
            )
            test_session.add(proj)
            test_session.flush()

            run = TestRun(
                project_id=project_id,
                category="make-test-2",
                command="make make-test-2",
                run_type="test",
                status=TestRunStatus.pending,
            )
            test_session.add(run)
            test_session.flush()
            run_id = run.id
            test_session.commit()

            with tempfile.TemporaryDirectory() as tmp:
                proj = test_session.get(Project, project_id)
                new_config: dict = dict(proj.config)
                new_config["test_config"] = dict(new_config.get("test_config", {}))
                new_config["test_config"]["execution_dir"] = tmp
                proj.config = new_config
                test_session.commit()

                fake_proc = MagicMock()
                fake_proc.pid = 88888
                fake_proc.wait.return_value = 0

                def fake_popen_no_results(*_args, **_kwargs) -> MagicMock:
                    # Deliberately do NOT create the results directory.
                    return fake_proc

                single_factory = _SingleSessionLocal(test_session)

                with (
                    patch.object(_ldg, "is_live_db_url", lambda *_a, **_kw: False),
                    patch("orch.db.session.SessionLocal", single_factory),
                    patch("orch.db.session._session_local", single_factory),
                    patch("orch.test_runner.SessionLocal", single_factory),
                    patch(
                        "orch.test_runner.subprocess.Popen",
                        side_effect=fake_popen_no_results,
                    ),
                    patch(
                        "orch.test_runner._generate_allure_report",
                        side_effect=lambda *_a, **_kw: False,
                    ),
                    patch(
                        "orch.test_runner.parse_allure_summary",
                        lambda _d: None,
                    ),
                ):
                    from orch.test_runner import launch_test_run

                    launch_test_run(run_id)

            verify_session = sessionmaker(bind=session_engine, expire_on_commit=False)()
            try:
                run = verify_session.scalar(select(TestRun).where(TestRun.id == run_id))
            finally:
                verify_session.close()

            assert run is not None
            assert run.status == TestRunStatus.passed
            # dangling pointer gone — no results dir → no report set:
            assert run.allure_report_dir is None
        finally:
            test_session.close()

    def test_quality_run_never_sets_report_dir(self, db_session: Session) -> None:
        """Quality runs must never set ``allure_report_dir`` regardless of
        whether a results dir exists (the guard is inside launch_test_run)."""
        _reset_session_cache()

        session_bind = db_session.get_bind()
        session_engine = session_bind if hasattr(session_bind, "url") else session_bind.engine

        project_id = f"i00121-test-{uuid.uuid4().hex[:8]}"
        test_session_factory = sessionmaker(bind=session_engine, autocommit=False, autoflush=False)
        test_session = test_session_factory()

        try:
            proj = Project(
                id=project_id,
                display_name="I00121 Test Project",
                repo_root="/tmp",
                config={
                    "quality_config": {
                        "categories": {
                            "guard-test": {
                                "label": "guard-test",
                                "command": "make guard-test",
                            },
                        },
                    },
                },
            )
            test_session.add(proj)
            test_session.flush()

            run = TestRun(
                project_id=project_id,
                category="guard-test",
                command="make guard-test",
                run_type="quality",
                status=TestRunStatus.pending,
            )
            test_session.add(run)
            test_session.flush()
            run_id = run.id
            test_session.commit()

            with tempfile.TemporaryDirectory() as tmp:
                proj = test_session.get(Project, project_id)
                new_config: dict = dict(proj.config)
                new_config["quality_config"] = dict(new_config.get("quality_config", {}))
                new_config["quality_config"]["execution_dir"] = tmp
                proj.config = new_config
                test_session.commit()

                fake_proc = MagicMock()
                fake_proc.pid = 77777
                fake_proc.wait.return_value = 0

                def fake_popen_with_results(*_args, **_kwargs) -> MagicMock:
                    # Create results dir — proving it's the quality guard
                    # (not the is_dir() guard) that blocks report generation.
                    Path(f"{tmp}/allure-results-{run_id}").mkdir(parents=True, exist_ok=True)
                    return fake_proc

                single_factory = _SingleSessionLocal(test_session)

                with (
                    patch.object(_ldg, "is_live_db_url", lambda *_a, **_kw: False),
                    patch("orch.db.session.SessionLocal", single_factory),
                    patch("orch.db.session._session_local", single_factory),
                    patch("orch.test_runner.SessionLocal", single_factory),
                    patch(
                        "orch.test_runner.subprocess.Popen",
                        side_effect=fake_popen_with_results,
                    ),
                    patch(
                        "orch.test_runner._generate_allure_report",
                        side_effect=lambda *_a, **_kw: True,
                    ),
                    patch(
                        "orch.test_runner.parse_allure_summary",
                        lambda _d: {"statistic": {"total": 0}, "time": {}},
                    ),
                ):
                    from orch.test_runner import launch_test_run

                    launch_test_run(run_id)

            verify_session = sessionmaker(bind=session_engine, expire_on_commit=False)()
            try:
                run = verify_session.scalar(select(TestRun).where(TestRun.id == run_id))
            finally:
                verify_session.close()

            assert run is not None
            assert run.status == TestRunStatus.passed
            # quality: report_dir is never set:
            assert run.allure_report_dir is None
        finally:
            test_session.close()
