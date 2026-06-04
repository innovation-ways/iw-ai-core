"""Unit tests for dashboard.services.oss_service."""

from __future__ import annotations

import asyncio
import contextlib
from unittest.mock import MagicMock, patch

from orch.db.models import ProjectOssJobStatus


class TestSseMessageFormatter:
    """Tests for SseMessageFormatter scenarios."""

    def _run_stream(self, factory, job_id, heartbeat_interval=0.01, timeout_sec=2.0):
        """Return run stream."""
        from dashboard.services.oss_service import job_event_stream

        events = []

        async def collect():
            """Return collect."""
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
            """Return run with timeout."""
            import asyncio

            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(collect(), timeout=timeout_sec)

        asyncio.run(run_with_timeout())
        return events

    def test_sse_status_event(self) -> None:
        """Verifies that sse status event."""
        mock_job = MagicMock()
        mock_job.id = 1
        mock_job.status = ProjectOssJobStatus.complete
        mock_job.stdout_tail = "line1\nline2\n"
        mock_job.scan_id = None
        mock_job.exit_code = 0

        def factory():
            """Return factory."""
            m = MagicMock()
            m.query.return_value.filter.return_value.first.return_value = mock_job
            return m

        events = self._run_stream(factory, 1, heartbeat_interval=0.01)

        assert any("event: status" in m for m in events)
        assert any("event: complete" in m for m in events)

    def test_sse_progress_line_format(self) -> None:
        """Verifies that sse progress line format."""
        mock_job = MagicMock()
        mock_job.id = 1
        mock_job.status = ProjectOssJobStatus.running
        mock_job.stdout_tail = "building..."
        mock_job.scan_id = None
        mock_job.exit_code = None

        def factory():
            """Return factory."""
            m = MagicMock()
            m.query.return_value.filter.return_value.first.return_value = mock_job
            return m

        events = self._run_stream(factory, 1, heartbeat_interval=0.01)

        for msg in events:
            if "event: progress" in msg:
                assert "data:" in msg


class TestFreshnessHelper:
    """Tests for FreshnessHelper scenarios."""

    def test_compute_freshness_matches_head_sha(self) -> None:
        """Verifies that compute freshness matches head sha."""
        from dashboard.services.oss_service import compute_freshness

        mock_session = MagicMock()
        mock_project = MagicMock()
        mock_project.repo_root = "/tmp/test-repo"

        mock_session.query.return_value.filter.return_value.first.return_value = mock_project
        filtered = mock_session.query.return_value.filter.return_value
        filtered.order_by.return_value.first.return_value = None

        with patch("dashboard.services.oss_service._git_head", return_value="abc123"):
            result = compute_freshness("test-proj", mock_session)

        assert result["current_sha"] == "abc123"
        assert result["last_scan_sha"] is None
        assert result["is_fresh"] is False
        assert result["message"] == "no scans yet"

    def test_compute_freshness_stale(self) -> None:
        """Verifies that compute freshness stale."""
        from dashboard.services.oss_service import compute_freshness

        mock_session = MagicMock()
        mock_project = MagicMock()
        mock_project.repo_root = "/tmp/test-repo"

        mock_scan = MagicMock()
        mock_scan.head_sha = "abc123"

        mock_session.query.return_value.filter.return_value.first.return_value = mock_project
        filtered = mock_session.query.return_value.filter.return_value
        filtered.order_by.return_value.first.return_value = mock_scan

        with patch("dashboard.services.oss_service._git_head", return_value="def456"):
            result = compute_freshness("test-proj", mock_session)

        assert result["is_fresh"] is False
        assert result["last_scan_sha"] == "abc123"
        assert result["current_sha"] == "def456"
        assert "HEAD has advanced" in result["message"]

    def test_compute_freshness_fresh(self) -> None:
        """Verifies that compute freshness fresh."""
        from dashboard.services.oss_service import compute_freshness

        mock_session = MagicMock()
        mock_project = MagicMock()
        mock_project.repo_root = "/tmp/test-repo"

        mock_scan = MagicMock()
        mock_scan.head_sha = "abc123"

        mock_session.query.return_value.filter.return_value.first.return_value = mock_project
        filtered = mock_session.query.return_value.filter.return_value
        filtered.order_by.return_value.first.return_value = mock_scan

        with patch("dashboard.services.oss_service._git_head", return_value="abc123"):
            result = compute_freshness("test-proj", mock_session)

        assert result["is_fresh"] is True
        assert result["message"] == ""

    def test_compute_freshness_project_not_found(self) -> None:
        """Verifies that compute freshness project not found."""
        from dashboard.services.oss_service import compute_freshness

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = compute_freshness("nonexistent", mock_session)

        assert result["is_fresh"] is False
        assert result["message"] == "project not found"


class TestProbeTier1Dashboard:
    """Tests for ProbeTier1Dashboard scenarios."""

    def test_probe_tier1_dashboard_returns_dict(self) -> None:
        """Verifies that probe tier1 dashboard returns dict."""
        from dashboard.services.oss_service import probe_tier1_dashboard

        with patch("dashboard.services.oss_service.probe_tier1") as mock_probe:
            mock_probe.return_value = {}
            result = probe_tier1_dashboard()

        assert isinstance(result, dict)


class TestTruncateTail:
    """Tests for TruncateTail scenarios."""

    def test_truncate_tail_under_limit(self) -> None:
        """Verifies that truncate tail under limit."""
        from dashboard.services.oss_service import _truncate_tail

        content = "short content"
        result = _truncate_tail(content)
        assert result == content

    def test_truncate_tail_over_limit(self) -> None:
        """Verifies that truncate tail over limit."""
        from dashboard.services.oss_service import _STDOUT_TAIL_BYTES, _truncate_tail

        content = "x" * (_STDOUT_TAIL_BYTES + 100)
        result = _truncate_tail(content)
        assert len(result.encode("utf-8")) <= _STDOUT_TAIL_BYTES
        assert result.endswith("x" * 100) or len(result) < len(content)


class TestEnqueueJobUnit:
    """Tests for EnqueueJobUnit scenarios."""

    def test_enqueue_job_string_kind_converts(self) -> None:
        """Verifies that enqueue job string kind converts."""
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
        """Verifies that enqueue job enum kind passes through."""
        from dashboard.services.oss_service import enqueue_job
        from orch.db.models import ProjectOssJobKind

        mock_session = MagicMock()
        mock_session.add = MagicMock()
        mock_session.flush = MagicMock()

        enqueue_job(mock_session, "proj-1", ProjectOssJobKind.install)

        call_arg = mock_session.add.call_args[0][0]
        assert call_arg.kind == ProjectOssJobKind.install


class TestLegacyEvidenceFallback:
    """Pure-function tests for the modal's safety net.

    Old scans persisted per-hit data into ``evidence_json`` under ad-hoc keys
    (samples / sample_hits / violations / paths / large_objects /
    incompatible / non_noreply_emails) instead of populating
    ``oss_finding_detail``. ``_legacy_evidence_to_rows`` synthesizes detail
    rows from those keys so the user sees *where* the issues are without
    having to re-run the scan first.
    """

    def test_samples_parses_rg_lines(self) -> None:
        """Verifies that samples parses rg lines."""
        from dashboard.services.oss_service import _legacy_evidence_to_rows

        rows = _legacy_evidence_to_rows(
            {"samples": ["src/foo.py:42:host: 10.0.0.1"]},
            rule_fallback="OSS-REF-01",
        )
        assert rows == [
            {
                "file": "src/foo.py",
                "line": 42,
                "rule": "OSS-REF-01",
                "snippet_masked": "host: 10.0.0.1",
            }
        ]

    def test_violations_string_list(self) -> None:
        """Verifies that violations string list."""
        from dashboard.services.oss_service import _legacy_evidence_to_rows

        rows = _legacy_evidence_to_rows(
            {"violations": [".env", "secrets.pem"]},
            rule_fallback="OSS-HYG-02",
        )
        assert [r["file"] for r in rows] == [".env", "secrets.pem"]
        assert all(r["line"] is None for r in rows)
        assert all(r["rule"] == "OSS-HYG-02" for r in rows)

    def test_large_objects(self) -> None:
        """Verifies that large objects."""
        from dashboard.services.oss_service import _legacy_evidence_to_rows

        rows = _legacy_evidence_to_rows(
            {"large_objects": [{"size_bytes": 75 * 1024 * 1024, "path": "video.mp4"}]},
            rule_fallback="OSS-HYG-04",
        )
        assert rows[0]["file"] == "video.mp4"
        assert "75 MB" in rows[0]["snippet_masked"]

    def test_incompatible_deps(self) -> None:
        """Verifies that incompatible deps."""
        from dashboard.services.oss_service import _legacy_evidence_to_rows

        rows = _legacy_evidence_to_rows(
            {"incompatible": [{"name": "gpl-lib", "license": "GPL-3.0-only"}]},
            rule_fallback="OSS-DEP-01",
        )
        assert rows[0]["file"] == "gpl-lib"
        assert rows[0]["rule"] == "GPL-3.0-only"
        assert "GPL-3.0-only" in rows[0]["snippet_masked"]

    def test_non_noreply_emails(self) -> None:
        """Verifies that non noreply emails."""
        from dashboard.services.oss_service import _legacy_evidence_to_rows

        rows = _legacy_evidence_to_rows(
            {"non_noreply_emails": ["alice@corp.example", "bob@corp.example"]},
            rule_fallback="OSS-HIST-03",
        )
        assert [r["file"] for r in rows] == ["alice@corp.example", "bob@corp.example"]

    def test_unknown_evidence_returns_empty(self) -> None:
        """Verifies that unknown evidence returns empty."""
        from dashboard.services.oss_service import _legacy_evidence_to_rows

        assert (
            _legacy_evidence_to_rows(
                {"paths_checked": ["LICENSE"]},
                rule_fallback="OSS-LIC-01",
            )
            == []
        )
