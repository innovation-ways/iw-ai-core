"""Unit tests for run_pre_merge_dry_run's per-project parameterisation.

The Phase-1 dry-run must spin the *project's* DB image and exercise the
*project's* migrations dir (plus any bootstrap SQL), rather than the hard-coded
``postgres:15-alpine`` + ``orch/db/migrations`` it used before I-00131. These
tests patch out the testcontainer + alembic layers so they stay fast and
hermetic — they assert wiring, not real migrations.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from orch.daemon.migration_pipeline import run_pre_merge_dry_run


def _dry_run_result(*, success: bool = True) -> object:
    """Build a DryRunResult as returned by safe_migrate.dry_run."""
    from orch.db.safe_migrate import DryRunResult

    return DryRunResult(
        revisions_applied=["0005_graphrag_age"],
        success=success,
        duration_ms=12,
        stdout_tail="",
        stderr_tail="",
        error_message=None if success else "boom",
    )


class TestDryRunParameterisation:
    """run_pre_merge_dry_run honours db_image, script_location, and bootstrap_sql."""

    def test_uses_provided_db_image(self) -> None:
        """The testcontainer is started from the project's configured image."""
        with (
            patch("testcontainers.postgres.PostgresContainer") as mock_cls,
            patch(
                "orch.daemon.migration_pipeline.safe_dry_run",
                return_value=_dry_run_result(),
            ),
            patch("orch.daemon.migration_pipeline._run_bootstrap_sql"),
        ):
            mock_cls.return_value.get_connection_url.return_value = (
                "postgresql+psycopg2://u:p@localhost:5/db"
            )
            run_pre_merge_dry_run(
                "BATCH-00145",
                worktree_path="/wt/I-00131",
                db_image="paradedb/paradedb:latest",
                script_location="/wt/I-00131/alembic",
            )
        mock_cls.assert_called_once_with("paradedb/paradedb:latest")

    def test_uses_provided_script_location(self) -> None:
        """safe_dry_run is pointed at the explicit project migrations dir."""
        with (
            patch("testcontainers.postgres.PostgresContainer") as mock_cls,
            patch(
                "orch.daemon.migration_pipeline.safe_dry_run",
                return_value=_dry_run_result(),
            ) as mock_dry,
            patch("orch.daemon.migration_pipeline._run_bootstrap_sql"),
        ):
            mock_cls.return_value.get_connection_url.return_value = (
                "postgresql+psycopg2://u:p@localhost:5/db"
            )
            run_pre_merge_dry_run(
                "BATCH-00145",
                worktree_path="/wt/I-00131",
                db_image="paradedb/paradedb:latest",
                script_location="/wt/I-00131/alembic",
            )
        assert mock_dry.call_args.kwargs["script_location"] == "/wt/I-00131/alembic"

    def test_falls_back_to_orch_layout_without_explicit_script_location(self) -> None:
        """With no explicit script_location, the orch layout is derived from worktree."""
        with (
            patch("testcontainers.postgres.PostgresContainer") as mock_cls,
            patch(
                "orch.daemon.migration_pipeline.safe_dry_run",
                return_value=_dry_run_result(),
            ) as mock_dry,
            patch("orch.daemon.migration_pipeline._run_bootstrap_sql"),
        ):
            mock_cls.return_value.get_connection_url.return_value = (
                "postgresql+psycopg2://u:p@localhost:5/db"
            )
            run_pre_merge_dry_run("BATCH-1", worktree_path="/wt/x")
        assert mock_dry.call_args.kwargs["script_location"] == "/wt/x/orch/db/migrations"
        mock_cls.assert_called_once_with("postgres:15-alpine")

    def test_bootstrap_sql_runs_before_upgrade(self) -> None:
        """Configured bootstrap SQL is executed against the fresh container."""
        stmts = ("CREATE EXTENSION IF NOT EXISTS vector",)
        with (
            patch("testcontainers.postgres.PostgresContainer") as mock_cls,
            patch(
                "orch.daemon.migration_pipeline.safe_dry_run",
                return_value=_dry_run_result(),
            ),
            patch("orch.daemon.migration_pipeline._run_bootstrap_sql") as mock_boot,
        ):
            mock_cls.return_value.get_connection_url.return_value = (
                "postgresql+psycopg2://u:p@localhost:5/db"
            )
            run_pre_merge_dry_run(
                "BATCH-1",
                worktree_path="/wt/x",
                script_location="/wt/x/alembic",
                bootstrap_sql=stmts,
            )
        mock_boot.assert_called_once()
        assert mock_boot.call_args.args[1] == stmts

    def test_no_bootstrap_call_when_empty(self) -> None:  # noqa: assertion-scanner
        """No bootstrap call is made when bootstrap_sql is empty."""
        with (
            patch("testcontainers.postgres.PostgresContainer") as mock_cls,
            patch(
                "orch.daemon.migration_pipeline.safe_dry_run",
                return_value=_dry_run_result(),
            ),
            patch("orch.daemon.migration_pipeline._run_bootstrap_sql") as mock_boot,
        ):
            mock_cls.return_value.get_connection_url.return_value = (
                "postgresql+psycopg2://u:p@localhost:5/db"
            )
            run_pre_merge_dry_run("BATCH-1", worktree_path="/wt/x", script_location="/wt/x/alembic")
        mock_boot.assert_not_called()

    def test_psycopg2_url_is_normalised_to_psycopg(self) -> None:
        """The psycopg2 testcontainer URL is rewritten to psycopg for safe_dry_run."""
        with (
            patch("testcontainers.postgres.PostgresContainer") as mock_cls,
            patch(
                "orch.daemon.migration_pipeline.safe_dry_run",
                return_value=_dry_run_result(),
            ) as mock_dry,
            patch("orch.daemon.migration_pipeline._run_bootstrap_sql"),
        ):
            mock_cls.return_value.get_connection_url.return_value = (
                "postgresql+psycopg2://u:p@localhost:5/db"
            )
            run_pre_merge_dry_run("BATCH-1", worktree_path="/wt/x", script_location="/wt/x/alembic")
        assert mock_dry.call_args.args[0] == "postgresql+psycopg://u:p@localhost:5/db"
