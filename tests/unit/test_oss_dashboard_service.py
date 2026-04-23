"""Unit tests for dashboard.services.oss_service."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from orch.db.models import ProjectOssJobStatus


class TestSseMessageFormatter:
    def _run_stream(self, factory, job_id, heartbeat_interval=0.01, timeout_sec=2.0):
        from dashboard.services.oss_service import job_event_stream

        events = []

        async def collect():
            nonlocal events
            gen = job_event_stream(factory, job_id, heartbeat_interval=heartbeat_interval)
            try:
                async for msg in gen:
                    events.append(msg)
                    if "event: complete" in msg:
                        break
            except asyncio.CancelledError:
                pass

        async def run_with_timeout():
            import asyncio

            try:
                await asyncio.wait_for(collect(), timeout=timeout_sec)
            except asyncio.TimeoutError:
                pass

        asyncio.run(run_with_timeout())
        return events

    def test_sse_status_event(self) -> None:
        mock_job = MagicMock()
        mock_job.id = 1
        mock_job.status = ProjectOssJobStatus.complete
        mock_job.stdout_tail = "line1\nline2\n"
        mock_job.scan_id = None
        mock_job.exit_code = 0

        def factory():
            m = MagicMock()
            m.query.return_value.filter.return_value.first.return_value = mock_job
            return m

        events = self._run_stream(factory, 1, heartbeat_interval=0.01)

        assert any("event: status" in m for m in events)
        assert any("event: complete" in m for m in events)

    def test_sse_progress_line_format(self) -> None:
        mock_job = MagicMock()
        mock_job.id = 1
        mock_job.status = ProjectOssJobStatus.running
        mock_job.stdout_tail = "building..."
        mock_job.scan_id = None
        mock_job.exit_code = None

        def factory():
            m = MagicMock()
            m.query.return_value.filter.return_value.first.return_value = mock_job
            return m

        events = self._run_stream(factory, 1, heartbeat_interval=0.01)

        for msg in events:
            if "event: progress" in msg:
                assert "data:" in msg


class TestFreshnessHelper:
    def test_compute_freshness_matches_head_sha(self) -> None:
        from dashboard.services.oss_service import compute_freshness

        mock_session = MagicMock()
        mock_project = MagicMock()
        mock_project.repo_root = "/tmp/test-repo"

        mock_session.query.return_value.filter.return_value.first.return_value = mock_project
        mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        with patch("dashboard.services.oss_service._git_head", return_value="abc123"):
            result = compute_freshness("test-proj", mock_session)

        assert result["current_sha"] == "abc123"
        assert result["last_scan_sha"] is None
        assert result["is_fresh"] is False
        assert result["message"] == "no scans yet"

    def test_compute_freshness_stale(self) -> None:
        from dashboard.services.oss_service import compute_freshness

        mock_session = MagicMock()
        mock_project = MagicMock()
        mock_project.repo_root = "/tmp/test-repo"

        mock_scan = MagicMock()
        mock_scan.head_sha = "abc123"

        mock_session.query.return_value.filter.return_value.first.return_value = mock_project
        mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_scan

        with patch("dashboard.services.oss_service._git_head", return_value="def456"):
            result = compute_freshness("test-proj", mock_session)

        assert result["is_fresh"] is False
        assert result["last_scan_sha"] == "abc123"
        assert result["current_sha"] == "def456"
        assert "HEAD has advanced" in result["message"]

    def test_compute_freshness_fresh(self) -> None:
        from dashboard.services.oss_service import compute_freshness

        mock_session = MagicMock()
        mock_project = MagicMock()
        mock_project.repo_root = "/tmp/test-repo"

        mock_scan = MagicMock()
        mock_scan.head_sha = "abc123"

        mock_session.query.return_value.filter.return_value.first.return_value = mock_project
        mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_scan

        with patch("dashboard.services.oss_service._git_head", return_value="abc123"):
            result = compute_freshness("test-proj", mock_session)

        assert result["is_fresh"] is True
        assert result["message"] == ""

    def test_compute_freshness_project_not_found(self) -> None:
        from dashboard.services.oss_service import compute_freshness

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = compute_freshness("nonexistent", mock_session)

        assert result["is_fresh"] is False
        assert result["message"] == "project not found"


class TestProbeTier1Dashboard:
    def test_probe_tier1_dashboard_returns_dict(self) -> None:
        from dashboard.services.oss_service import probe_tier1_dashboard

        with patch("dashboard.services.oss_service.probe_tier1") as mock_probe:
            mock_probe.return_value = {}
            result = probe_tier1_dashboard()

        assert isinstance(result, dict)


class TestTruncateTail:
    def test_truncate_tail_under_limit(self) -> None:
        from dashboard.services.oss_service import _truncate_tail

        content = "short content"
        result = _truncate_tail(content)
        assert result == content

    def test_truncate_tail_over_limit(self) -> None:
        from dashboard.services.oss_service import _STDOUT_TAIL_BYTES, _truncate_tail

        content = "x" * (_STDOUT_TAIL_BYTES + 100)
        result = _truncate_tail(content)
        assert len(result.encode("utf-8")) <= _STDOUT_TAIL_BYTES
        assert result.endswith("x" * 100) or len(result) < len(content)


class TestEnqueueJobUnit:
    def test_enqueue_job_string_kind_converts(self) -> None:
        from dashboard.services.oss_service import enqueue_job
        from orch.db.models import ProjectOssJobKind, ProjectOssJobStatus

        mock_session = MagicMock()
        mock_session.add = MagicMock()
        mock_session.flush = MagicMock()

        enqueue_job(mock_session, "proj-1", "scan")

        mock_session.add.assert_called_once()
        call_arg = mock_session.add.call_args[0][0]
        assert call_arg.kind == ProjectOssJobKind.scan
        assert call_arg.status == ProjectOssJobStatus.queued

    def test_enqueue_job_enum_kind_passes_through(self) -> None:
        from dashboard.services.oss_service import enqueue_job
        from orch.db.models import ProjectOssJobKind

        mock_session = MagicMock()
        mock_session.add = MagicMock()
        mock_session.flush = MagicMock()

        enqueue_job(mock_session, "proj-1", ProjectOssJobKind.install)

        call_arg = mock_session.add.call_args[0][0]
        assert call_arg.kind == ProjectOssJobKind.install
