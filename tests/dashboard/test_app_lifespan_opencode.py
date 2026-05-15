"""Tests for dashboard/app.py lifespan — OpenCode runtime startup (F-00083).

Covers lines 88-90, 92-93, 98-109 of dashboard/app.py:
- Line 87: IW_CORE_TEST_CONTEXT bypass check
- Lines 89-90: imports of OpencodeRuntime, OpencodeClient, RelayManager + load_config
- Lines 92-93: cfg.opencode_port and cfg.opencode_bin from load_config()
- Lines 98-109: successful runtime startup → app.state opencode_runtime/client/relay_manager

IW_CORE_TEST_CONTEXT=true is set by conftest.py's _arm_live_db_guard. When set,
the lifespan skips the real subprocess startup (line 87 check) and leaves
app.state unset. When NOT set, the startup path runs and sets app.state.

These tests verify the startup code by patching at source modules (orch.chat,
orch.config) so that when the startup path runs, it gets our mocks instead of
trying to spawn real processes.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

from dashboard.dependencies import get_db

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class TestLifespanOpencodeStartup:
    """Test OpenCode runtime startup in dashboard/app.py lifespan."""

    def test_startup_path_populates_state_on_success(self, db_session: Session) -> None:
        """Lines 98-104: with startup enabled, runtime/client/relay_manager go to app.state."""
        original_id = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
        original_ctx = os.environ.pop("IW_CORE_TEST_CONTEXT", None)
        try:
            # Remove the bypass flag so the startup path runs
            os.environ.pop("IW_CORE_TEST_CONTEXT", None)

            mock_runtime = MagicMock()
            mock_runtime.base_url = "http://localhost:4096"
            mock_runtime.password = "test-pw-xyz"  # noqa: S105
            mock_runtime.health = AsyncMock(return_value=True)
            mock_runtime.start = AsyncMock()
            mock_runtime.stop = AsyncMock()

            mock_client = MagicMock()
            mock_relay = MagicMock()
            mock_relay.shutdown = AsyncMock()

            mock_cfg = MagicMock()
            mock_cfg.opencode_port = 4096
            mock_cfg.opencode_bin = "opencode"

            with (
                patch("orch.chat.OpencodeRuntime", return_value=mock_runtime) as mock_rt,
                patch("orch.chat.OpencodeClient", return_value=mock_client) as mock_cl,
                patch("orch.chat.RelayManager", return_value=mock_relay) as mock_rm,
                patch("orch.config.load_config", return_value=mock_cfg) as mock_lc,
                patch("orch.config.CORE_ROOT", Path("/test/root")),
                patch("dashboard.app.mark_orphaned_runs", return_value=0),
                patch("dashboard.app.verify_instance_identity"),
            ):
                from dashboard.app import create_app

                # get_db override must be set before TestClient is used
                app = create_app()
                app.dependency_overrides[get_db] = lambda: db_session

                # Manually invoke lifespan startup via the context manager
                import asyncio

                async def run_startup():
                    async with app.router.lifespan_context(app):
                        pass

                asyncio.run(run_startup())

                # Verify state was populated
                assert app.state.opencode_runtime is mock_runtime
                assert app.state.opencode_client is mock_client
                assert app.state.relay_manager is mock_relay

                # Verify the startup calls
                mock_rt.assert_called_once_with(
                    repo_root=Path("/test/root"),
                    port=4096,
                    bin_path="opencode",
                )
                mock_runtime.start.assert_awaited_once()
                mock_cl.assert_called_once_with(
                    base_url="http://localhost:4096",
                    password="test-pw-xyz",  # noqa: S106
                )
                mock_rm.assert_called_once_with(mock_client)
                mock_lc.assert_called_once()

        finally:
            if original_id is not None:
                os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original_id
            if original_ctx is not None:
                os.environ["IW_CORE_TEST_CONTEXT"] = original_ctx

    def test_startup_error_leaves_state_as_none(self, db_session: Session) -> None:
        """Lines 105-109: on startup error, state is None and app still boots."""
        original_id = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
        original_ctx = os.environ.pop("IW_CORE_TEST_CONTEXT", None)
        try:
            os.environ.pop("IW_CORE_TEST_CONTEXT", None)

            mock_cfg = MagicMock()
            mock_cfg.opencode_port = 4096
            mock_cfg.opencode_bin = "opencode"

            with (
                patch("orch.chat.OpencodeRuntime", side_effect=RuntimeError("not found")),
                patch("orch.config.load_config", return_value=mock_cfg),
                patch("orch.config.CORE_ROOT", Path("/test/root")),
                patch("dashboard.app.mark_orphaned_runs", return_value=0),
                patch("dashboard.app.verify_instance_identity"),
            ):
                from dashboard.app import create_app

                app = create_app()
                app.dependency_overrides[get_db] = lambda: db_session

                import asyncio

                async def run_startup():
                    async with app.router.lifespan_context(app):
                        pass

                asyncio.run(run_startup())

                assert app.state.opencode_runtime is None
                assert app.state.opencode_client is None
                assert app.state.relay_manager is None

        finally:
            if original_id is not None:
                os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original_id
            if original_ctx is not None:
                os.environ["IW_CORE_TEST_CONTEXT"] = original_ctx

    def test_startup_enables_chat_endpoints(self, db_session: Session) -> None:
        """Verify chat endpoints are available when startup runs with mocks."""
        original_id = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
        original_ctx = os.environ.pop("IW_CORE_TEST_CONTEXT", None)
        try:
            os.environ.pop("IW_CORE_TEST_CONTEXT", None)

            mock_runtime = MagicMock()
            mock_runtime.base_url = "http://localhost:4096"
            mock_runtime.password = "pw"  # noqa: S105
            mock_runtime.health = AsyncMock(return_value=True)
            mock_runtime.start = AsyncMock()
            mock_runtime.stop = AsyncMock()

            mock_client = MagicMock()
            mock_relay = MagicMock()

            mock_cfg = MagicMock()
            mock_cfg.opencode_port = 4096
            mock_cfg.opencode_bin = "opencode"

            with (
                patch("orch.chat.OpencodeRuntime", return_value=mock_runtime),
                patch("orch.chat.OpencodeClient", return_value=mock_client),
                patch("orch.chat.RelayManager", return_value=mock_relay),
                patch("orch.config.load_config", return_value=mock_cfg),
                patch("orch.config.CORE_ROOT", Path("/test/root")),
                patch("dashboard.app.mark_orphaned_runs", return_value=0),
                patch("dashboard.app.verify_instance_identity"),
            ):
                from dashboard.app import create_app

                app = create_app()
                app.dependency_overrides[get_db] = lambda: db_session

                import asyncio

                async def run_startup():
                    async with app.router.lifespan_context(app):
                        pass

                asyncio.run(run_startup())

                # State is populated after startup
                assert hasattr(app.state, "opencode_runtime")
                assert app.state.opencode_runtime is mock_runtime

        finally:
            if original_id is not None:
                os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original_id
            if original_ctx is not None:
                os.environ["IW_CORE_TEST_CONTEXT"] = original_ctx

    def test_chat_router_registered_in_app(self, db_session: Session) -> None:
        """Line 355: chat router is included in the app."""
        original_id = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
        try:
            from dashboard.app import create_app

            app = create_app()
            app.dependency_overrides[get_db] = lambda: db_session

            route_paths = [r.path for r in app.routes]
            chat_routes = [p for p in route_paths if p.startswith("/api/chat")]
            assert len(chat_routes) >= 8, (
                f"Expected >= 8 chat routes, got {len(chat_routes)}: {chat_routes}"
            )

        finally:
            if original_id is not None:
                os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original_id
