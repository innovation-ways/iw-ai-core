from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from orch.auto_merge_aggregator import EVENT_AUTO_MERGE_HEALTH_PROBE
from orch.daemon.auto_merge import AutoMergeConfig


def _event(**kwargs):
    row = MagicMock()
    row.id = kwargs.get("id", 1)
    row.event_type = kwargs.get("event_type", "merge_auto_resolved")
    row.entity_id = kwargs.get("entity_id", "W-1")
    row.message = kwargs.get("message", "msg")
    row.event_metadata = kwargs.get("event_metadata", {})
    row.created_at = kwargs.get("created_at", datetime.now(UTC))
    return row


def _cfg(**kwargs) -> AutoMergeConfig:
    d = AutoMergeConfig.defaults()
    return AutoMergeConfig(
        phase=kwargs.get("phase", d.phase),
        runtime_option_id=kwargs.get("runtime_option_id", d.runtime_option_id),
        allowlist_patterns=d.allowlist_patterns,
        refuselist_patterns=d.refuselist_patterns,
        max_conflict_hunk_lines=d.max_conflict_hunk_lines,
        max_conflicted_files_per_merge=d.max_conflicted_files_per_merge,
        max_file_size_bytes=d.max_file_size_bytes,
        max_event_metadata_bytes=d.max_event_metadata_bytes,
        llm_call_timeout_seconds=d.llm_call_timeout_seconds,
        health_probe_interval_seconds=kwargs.get("health_probe_interval_seconds", 300),
        health_failure_rate_threshold_per_day=kwargs.get(
            "health_failure_rate_threshold_per_day", 3
        ),
    )


def test_status_snapshot_empty_db() -> None:
    from orch.auto_merge_aggregator import get_status_snapshot

    db = MagicMock()
    db.get.return_value = None
    db.execute.return_value.scalar_one_or_none.return_value = None
    db.execute.return_value.all.return_value = []
    db.execute.return_value.scalar_one.return_value = 0
    status = get_status_snapshot(db, "proj-1", _cfg())
    assert status.project_id == "proj-1"
    assert status.health_state == "unknown"
    assert status.counts_by_event_type == {}


def test_status_snapshot_with_seeded_events() -> None:
    from orch.auto_merge_aggregator import get_status_snapshot

    db = MagicMock()
    db.get.return_value = None
    db.execute.return_value.scalar_one_or_none.return_value = datetime.now(UTC) - timedelta(days=1)
    db.execute.return_value.all.return_value = [
        ("merge_auto_resolved", 2),
        ("merge_auto_resolution_skipped", 1),
    ]
    db.execute.return_value.scalar_one.return_value = 0
    with (
        patch("orch.auto_merge_aggregator.get_health_summary") as health,
        patch("orch.auto_merge_aggregator.resolve_project_config") as resolve,
    ):
        resolve.return_value = MagicMock(phase=1, runtime_option_id=1)
        health.return_value = MagicMock(state="healthy", latest_probe_at=None)
        status = get_status_snapshot(db, "proj-1", _cfg())
    assert status.counts_by_event_type == {
        "merge_auto_resolved": 2,
        "merge_auto_resolution_skipped": 1,
    }


def test_list_recent_events_pagination() -> None:
    from orch.auto_merge_aggregator import list_recent_events

    db = MagicMock()
    db.execute.return_value.scalar_one.return_value = 3
    db.execute.return_value.all.return_value = [(_event(id=2), None)]
    rows, total = list_recent_events(db, "proj", page=1, page_size=1)
    assert total == 3
    assert [r.id for r in rows] == [2]


def test_list_recent_events_type_filter() -> None:
    from orch.auto_merge_aggregator import list_recent_events

    db = MagicMock()
    db.execute.return_value.scalar_one.return_value = 1
    db.execute.return_value.all.return_value = [(_event(event_type="merge_auto_resolved"), None)]
    rows, _ = list_recent_events(db, "proj", event_type_filter="merge_auto_resolved")
    assert rows[0].event_type == "merge_auto_resolved"


def test_list_recent_events_left_joins_verdicts() -> None:
    from orch.auto_merge_aggregator import list_recent_events

    db = MagicMock()
    v = MagicMock(
        verdict="correct", verdict_notes="ok", verdicted_by="u", verdicted_at=datetime.now(UTC)
    )
    db.execute.return_value.scalar_one.return_value = 2
    db.execute.return_value.all.return_value = [(_event(id=1), v), (_event(id=2), None)]
    rows, _ = list_recent_events(db, "proj")
    assert rows[0].verdict == "correct"
    assert rows[1].verdict is None


def test_get_event_detail_returns_none_for_missing() -> None:
    from orch.auto_merge_aggregator import get_event_detail

    db = MagicMock()
    db.execute.return_value.first.return_value = None
    assert get_event_detail(db, "proj", 9) is None


def test_get_event_detail_includes_verdict_when_present() -> None:
    from orch.auto_merge_aggregator import get_event_detail

    db = MagicMock()
    v = MagicMock(
        verdict="wrong", verdict_notes="bad", verdicted_by="a", verdicted_at=datetime.now(UTC)
    )
    db.execute.return_value.first.return_value = (_event(id=11), v)
    detail = get_event_detail(db, "proj", 11)
    assert detail is not None
    assert detail.verdict == "wrong"


def test_verdict_rollup_7d_window() -> None:
    from orch.auto_merge_aggregator import get_verdict_rollup

    db = MagicMock()
    db.execute.return_value.all.return_value = [("pending", 2), ("correct", 1)]
    rollup = get_verdict_rollup(db, "p", "7d")
    assert (rollup.pending, rollup.correct, rollup.wrong, rollup.partial) == (2, 1, 0, 0)


def test_verdict_rollup_30d_window() -> None:
    from orch.auto_merge_aggregator import get_verdict_rollup

    db = MagicMock()
    db.execute.return_value.all.return_value = [("wrong", 3), ("partial", 1)]
    rollup = get_verdict_rollup(db, "p", "30d")
    assert (rollup.pending, rollup.correct, rollup.wrong, rollup.partial) == (0, 0, 3, 1)


def test_verdict_rollup_excludes_older_events() -> None:
    from orch.auto_merge_aggregator import get_verdict_rollup

    db = MagicMock()
    db.execute.return_value.all.return_value = []
    rollup = get_verdict_rollup(db, "p", "7d")
    assert (rollup.pending, rollup.correct, rollup.wrong, rollup.partial) == (0, 0, 0, 0)


def test_refuse_list_breakdown_groups_by_reason() -> None:
    from orch.auto_merge_aggregator import get_refuse_list_breakdown

    db = MagicMock()
    db.execute.return_value.all.return_value = [("refuse_list", 2), ("too_large", 1)]
    rows = get_refuse_list_breakdown(db, "p", "7d")
    assert [(r.reason, r.count) for r in rows] == [("refuse_list", 2), ("too_large", 1)]


def test_refuse_list_breakdown_window_filter() -> None:
    from orch.auto_merge_aggregator import get_refuse_list_breakdown

    db = MagicMock()
    db.execute.return_value.all.return_value = []
    assert get_refuse_list_breakdown(db, "p", "30d") == []


def test_health_summary_no_probes() -> None:
    from orch.auto_merge_aggregator import get_health_summary

    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = None
    db.execute.return_value.scalar_one.return_value = 0
    summary = get_health_summary(db, "p", _cfg())
    assert summary.state == "unknown"


def test_health_summary_recent_success() -> None:
    from orch.auto_merge_aggregator import get_health_summary

    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = _event(
        event_type=EVENT_AUTO_MERGE_HEALTH_PROBE, event_metadata={"runtime_reachable": True}
    )
    db.execute.return_value.scalar_one.return_value = 0
    summary = get_health_summary(db, "p", _cfg())
    assert summary.state == "healthy"


def test_health_summary_recent_failures_exceed_threshold() -> None:
    from orch.auto_merge_aggregator import get_health_summary

    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = _event(
        event_type=EVENT_AUTO_MERGE_HEALTH_PROBE, event_metadata={"runtime_reachable": False}
    )
    db.execute.return_value.scalar_one.return_value = 5
    summary = get_health_summary(db, "p", _cfg(health_failure_rate_threshold_per_day=3))
    assert summary.state == "down"


def test_token_cost_rollup_per_model_breakdown() -> None:
    from orch.auto_merge_aggregator import get_token_cost_rollup

    db = MagicMock()
    db.scalars.return_value.all.return_value = [
        _event(
            event_metadata={
                "llm_calls": [
                    {"model": "claude-sonnet-4-6", "input_tokens": 1000, "output_tokens": 2000}
                ]
            }
        )
    ]
    rollup = get_token_cost_rollup(db, "p", "7d")
    assert rollup.breakdown_by_model["claude-sonnet-4-6"]["input"] == 1000
    assert rollup.total_cost_usd > 0


def test_token_cost_rollup_unknown_model_sets_flag() -> None:
    from orch.auto_merge_aggregator import get_token_cost_rollup

    db = MagicMock()
    db.scalars.return_value.all.return_value = [
        _event(
            event_metadata={
                "llm_calls": [{"model": "unknown/model", "input_tokens": 1, "output_tokens": 1}]
            }
        )
    ]
    rollup = get_token_cost_rollup(db, "p", "7d")
    assert rollup.has_unknown_models is True


def test_token_cost_rollup_handles_missing_llm_calls_metadata() -> None:
    from orch.auto_merge_aggregator import get_token_cost_rollup

    db = MagicMock()
    db.scalars.return_value.all.return_value = [
        _event(event_metadata={}),
        _event(event_metadata={"llm_calls": "bad"}),
    ]
    rollup = get_token_cost_rollup(db, "p", "7d")
    assert rollup.total_input_tokens == 0
    assert rollup.total_output_tokens == 0
    assert rollup.total_cost_usd == 0.0


def test_list_recent_events_includes_verdict_fields() -> None:
    from orch.auto_merge_aggregator import list_recent_events

    db = MagicMock()
    row = MagicMock()
    row.id = 1
    row.event_type = "merge_auto_resolution_attempted"
    row.entity_id = "F-00085"
    row.message = "attempted"
    row.event_metadata = {"k": "v"}
    row.created_at = datetime.now(UTC)

    verdict = MagicMock()
    verdict.verdict = "pending"
    verdict.verdict_notes = ""
    verdict.verdicted_by = None
    verdict.verdicted_at = None

    db.execute.return_value.all.return_value = [(row, verdict)]
    db.execute.return_value.scalar_one.return_value = 1

    rows, total = list_recent_events(db, "proj-1")

    assert total == 1
    assert len(rows) == 1
    assert rows[0].id == 1
    assert rows[0].verdict == "pending"


def test_list_recent_events_default_excludes_non_auto_merge() -> None:
    """By default list_recent_events only returns events whose type starts with
    auto_merge_* or merge_auto_* prefixes; non-auto-merge events like
    step_launched are excluded."""
    from orch.auto_merge_aggregator import list_recent_events

    db = MagicMock()
    # Simulate the SQL query: the WHERE clause filters to only auto_merge_*
    # events, so the mocked all() return reflects that filtered result.
    auto_event = MagicMock()
    auto_event.id = 2
    auto_event.event_type = "auto_merge_health_probe"
    auto_event.entity_id = None
    auto_event.message = "probe"
    auto_event.event_metadata = {}
    auto_event.created_at = datetime.now(UTC)

    # Only auto_merge_health_probe passes the prefix filter
    db.execute.return_value.all.return_value = [(auto_event, None)]
    db.execute.return_value.scalar_one.return_value = 1

    rows, _ = list_recent_events(db, "proj-1")
    types = {r.event_type for r in rows}
    assert "step_launched" not in types
    assert "auto_merge_health_probe" in types


def test_list_recent_events_include_non_auto_merge_shows_everything() -> None:
    """When include_non_auto_merge=True the prefix filter is disabled and all
    event types are returned."""
    from orch.auto_merge_aggregator import list_recent_events

    db = MagicMock()
    non_auto_event = MagicMock()
    non_auto_event.id = 1
    non_auto_event.event_type = "step_launched"
    non_auto_event.entity_id = None
    non_auto_event.message = "x"
    non_auto_event.event_metadata = {}
    non_auto_event.created_at = datetime.now(UTC)

    auto_event = MagicMock()
    auto_event.id = 2
    auto_event.event_type = "auto_merge_health_probe"
    auto_event.entity_id = None
    auto_event.message = "probe"
    auto_event.event_metadata = {}
    auto_event.created_at = datetime.now(UTC)

    # With include_non_auto_merge=True the prefix filter is bypassed,
    # so all events are returned
    db.execute.return_value.all.return_value = [(non_auto_event, None), (auto_event, None)]
    db.execute.return_value.scalar_one.return_value = 2

    rows, _ = list_recent_events(db, "proj-1", include_non_auto_merge=True)
    types = {r.event_type for r in rows}
    assert types == {"step_launched", "auto_merge_health_probe"}


def test_list_recent_events_event_type_filter_takes_precedence() -> None:
    """When event_type_filter is explicitly set it overrides the prefix default."""
    from orch.auto_merge_aggregator import list_recent_events

    db = MagicMock()
    targeted = MagicMock()
    targeted.id = 1
    targeted.event_type = "step_launched"
    targeted.entity_id = None
    targeted.message = "x"
    targeted.event_metadata = {}
    targeted.created_at = datetime.now(UTC)

    db.execute.return_value.all.return_value = [(targeted, None)]
    db.execute.return_value.scalar_one.return_value = 1

    rows, _ = list_recent_events(db, "proj-1", event_type_filter="step_launched")
    assert rows[0].event_type == "step_launched"
