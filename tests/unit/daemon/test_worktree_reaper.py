"""Unit tests for orch.daemon.worktree_reaper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from orch.daemon.worktree_reaper import (
    ReaperFinding,
    classify,
    scan,
)
from orch.db.models import BatchItem, BatchItemStatus


class TestScan:
    """Tests for docker container scanning."""

    def test_scan_returns_empty_list_when_docker_ps_fails(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="docker not running", stdout="")
            findings = scan()
        assert findings == []

    def test_scan_parses_json_output(self) -> None:
        json_line = (
            '{"ID":"abc123","Names":"container-1",'
            '"Labels":"iwcore.batch_item=123,iwcore.project=test-proj,iwcore.role=worktree"}'
        )
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json_line + "\n", stderr="")
            findings = scan()

        assert len(findings) == 1
        assert findings[0].container_id == "abc123"
        assert findings[0].batch_item_id == "123"
        assert findings[0].project_id == "test-proj"

    def test_scan_handles_dict_labels(self) -> None:
        json_line = (
            '{"ID":"abc123","Names":"container-1",'
            '"Labels":{"iwcore.batch_item":"456","iwcore.project":"proj2","iwcore.role":"worktree"}}'
        )
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=json_line + "\n", stderr="")
            findings = scan()

        assert len(findings) == 1
        assert findings[0].batch_item_id == "456"
        assert findings[0].project_id == "proj2"


class TestClassify:
    """Tests for container classification based on DB state."""

    def test_classify_running_with_active_batchitem_is_active(self) -> None:
        finding = ReaperFinding(
            container_id="abc123",
            batch_item_id="123",
            project_id="test-proj",
            classification="malformed",
            labels={},
        )

        mock_item = MagicMock(spec=BatchItem)
        mock_item.status = BatchItemStatus.executing

        db = MagicMock()
        db.get.return_value = mock_item

        result = classify(finding, db)
        assert result == "active"

    def test_classify_running_with_terminal_batchitem_is_stale(self) -> None:
        finding = ReaperFinding(
            container_id="abc123",
            batch_item_id="123",
            project_id="test-proj",
            classification="malformed",
            labels={},
        )

        mock_item = MagicMock(spec=BatchItem)
        mock_item.status = BatchItemStatus.merged

        db = MagicMock()
        db.get.return_value = mock_item

        result = classify(finding, db)
        assert result == "stale"

    @pytest.mark.parametrize(
        "terminal_status",
        [
            BatchItemStatus.merged,
            BatchItemStatus.failed,
            BatchItemStatus.stalled,
            BatchItemStatus.skipped,
            BatchItemStatus.migration_invalid,
            BatchItemStatus.migration_rolled_back,
            BatchItemStatus.migration_rebase_failed,
            BatchItemStatus.setup_failed,
        ],
    )
    def test_classify_running_with_each_terminal_status_is_stale(
        self, terminal_status: BatchItemStatus
    ) -> None:
        """AC4 — all terminal BatchItemStatus values classify container as stale."""
        finding = ReaperFinding(
            container_id="abc123",
            batch_item_id="123",
            project_id="test-proj",
            classification="malformed",
            labels={},
        )

        mock_item = MagicMock(spec=BatchItem)
        mock_item.status = terminal_status

        db = MagicMock()
        db.get.return_value = mock_item

        result = classify(finding, db)
        assert result == "stale"

    def test_classify_running_with_no_batchitem_is_orphan(self) -> None:
        finding = ReaperFinding(
            container_id="abc123",
            batch_item_id="999",
            project_id="test-proj",
            classification="malformed",
            labels={},
        )

        db = MagicMock()
        db.get.return_value = None

        result = classify(finding, db)
        assert result == "orphan"

    def test_classify_with_malformed_label_is_malformed(self) -> None:
        finding = ReaperFinding(
            container_id="abc123",
            batch_item_id=None,
            project_id="test-proj",
            classification="malformed",
            labels={},
        )

        db = MagicMock()
        result = classify(finding, db)
        assert result == "malformed"

    def test_classify_with_non_numeric_batch_item_id_is_malformed(self) -> None:
        finding = ReaperFinding(
            container_id="abc123",
            batch_item_id="NOT-A-NUMBER",
            project_id="test-proj",
            classification="malformed",
            labels={},
        )

        db = MagicMock()
        result = classify(finding, db)
        assert result == "malformed"


class TestReapIntegration:
    """Integration tests for reap() with mocked scan and compose down."""

    def test_reap_only_acts_on_stale_and_orphan(self) -> None:
        active_finding = ReaperFinding(
            container_id="active-1",
            batch_item_id="100",
            project_id="test-proj",
            classification="malformed",
            labels={},
        )
        stale_finding = ReaperFinding(
            container_id="stale-1",
            batch_item_id="101",
            project_id="test-proj",
            classification="malformed",
            labels={},
        )
        orphan_finding = ReaperFinding(
            container_id="orphan-1",
            batch_item_id="102",
            project_id="test-proj",
            classification="malformed",
            labels={},
        )

        mock_active_item = MagicMock(spec=BatchItem)
        mock_active_item.status = BatchItemStatus.executing
        mock_stale_item = MagicMock(spec=BatchItem)
        mock_stale_item.status = BatchItemStatus.merged

        db = MagicMock()
        db.get.side_effect = lambda _, pk: (
            mock_active_item if pk == 100 else mock_stale_item if pk == 101 else None
        )

        with (
            patch(
                "orch.daemon.worktree_reaper.scan",
                return_value=[active_finding, stale_finding, orphan_finding],
            ),
            patch("orch.daemon.worktree_compose.down") as mock_down,
        ):
            from orch.daemon.worktree_reaper import reap

            reaped = reap(db)

        assert len(reaped) == 2
        reaped_ids = {f.container_id for f in reaped}
        assert "stale-1" in reaped_ids
        assert "orphan-1" in reaped_ids
        assert mock_down.call_count == 2

    def test_reaper_idempotent_on_already_torn_down_stack(self) -> None:
        orphan_finding = ReaperFinding(
            container_id="orphan-1",
            batch_item_id="999",
            project_id="test-proj",
            classification="malformed",
            labels={},
        )

        db = MagicMock()
        db.get.return_value = None

        with (
            patch("orch.daemon.worktree_reaper.scan", return_value=[orphan_finding]),
            patch("orch.daemon.worktree_compose.down") as mock_down,
        ):
            from orch.daemon.worktree_reaper import reap

            reaped = reap(db)

        assert len(reaped) == 1
        mock_down.assert_called_once()

    def test_reap_does_not_act_on_active(self) -> None:
        """Invariant #7 — active containers must NOT be reaped even if found by scan."""
        active_finding = ReaperFinding(
            container_id="active-1",
            batch_item_id="100",
            project_id="test-proj",
            classification="malformed",
            labels={},
        )

        mock_active_item = MagicMock(spec=BatchItem)
        mock_active_item.status = BatchItemStatus.executing

        db = MagicMock()
        db.get.return_value = mock_active_item

        with (
            patch(
                "orch.daemon.worktree_reaper.scan",
                return_value=[active_finding],
            ),
            patch("orch.daemon.worktree_compose.down") as mock_down,
        ):
            from orch.daemon.worktree_reaper import reap

            reaped = reap(db)

        assert len(reaped) == 0
        mock_down.assert_not_called()

    def test_reaper_emits_daemon_event_per_reap_action(self) -> None:
        """AC4 — each reap emits exactly one DaemonEvent with classification and metadata."""
        orphan_finding = ReaperFinding(
            container_id="orphan-1",
            batch_item_id="999",
            project_id="test-proj",
            classification="malformed",
            labels={"iwcore.batch_item": "999"},
        )

        db = MagicMock()
        db.get.return_value = None
        db.add = MagicMock()
        db.commit = MagicMock()

        with (
            patch("orch.daemon.worktree_reaper.scan", return_value=[orphan_finding]),
            patch("orch.daemon.worktree_compose.down"),
        ):
            from orch.daemon.worktree_reaper import reap

            reaped = reap(db)

        assert len(reaped) == 1
        assert reaped[0].classification == "orphan"
        db.add.assert_called_once()
        commit_call = db.add.call_args[0][0]
        assert commit_call.event_type == "worktree_compose"
        assert commit_call.event_metadata["phase"] == "reap"
        assert commit_call.event_metadata["classification"] == "orphan"

    def test_reaper_uses_label_filter_in_docker_ps_call(self) -> None:
        """AC4 — scan() passes label=iwcore.role filter to docker ps."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            from orch.daemon.worktree_reaper import scan

            scan()

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "--filter" in call_args
        filter_idx = call_args.index("--filter")
        assert call_args[filter_idx + 1] == "label=iwcore.role"
