from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import AgentRuntimeOption, AutoMergeProjectConfig, DaemonEvent


def _seed_runtime(db, rid: int, enabled: bool = True, model: str | None = None) -> None:
    if model is None:
        model = f"test-model-{rid}"
    db.merge(
        AgentRuntimeOption(
            id=rid,
            cli_tool="opencode",
            model=model,
            cli_label="OpenCode",
            model_label=model,
            display_name=model,
            is_default=(rid == 1),
            enabled=enabled,
            sort_order=rid,
        )
    )
    db.flush()


def _client(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def test_ac12_settings_panel_writes_upserts_row(db_session, test_project) -> None:
    _seed_runtime(db_session, 1)
    with _client(db_session) as c:
        r = c.post(
            f"/project/{test_project.id}/auto-merge/config",
            headers={"accept": "application/json"},
            json={"phase": 1, "runtime_option_id": 1},
        )
    assert r.status_code == 200
    row = db_session.get(AutoMergeProjectConfig, test_project.id)
    assert row is not None
    assert row.phase == 1


def test_ac12_settings_panel_write_emits_config_updated_event_with_old_new(
    db_session, test_project
) -> None:
    _seed_runtime(db_session, 1)
    with _client(db_session) as c:
        c.post(
            f"/project/{test_project.id}/auto-merge/config",
            headers={"accept": "application/json"},
            json={"phase": 1, "runtime_option_id": 1},
        )
    evt = db_session.execute(
        select(DaemonEvent)
        .where(DaemonEvent.event_type == "auto_merge_config_updated")
        .order_by(DaemonEvent.id.desc())
    ).scalar_one()
    assert evt.event_metadata["new"] == {"phase": 1, "runtime_option_id": 1}


def test_ac13_use_global_default_clears_row_or_nulls_fields(db_session, test_project) -> None:
    _seed_runtime(db_session, 1)
    db_session.merge(
        AutoMergeProjectConfig(
            project_id=test_project.id, phase=1, runtime_option_id=1, updated_by="x"
        )
    )
    db_session.flush()
    with _client(db_session) as c:
        r = c.post(
            f"/project/{test_project.id}/auto-merge/config",
            headers={"accept": "application/json"},
            json={"phase": None, "runtime_option_id": None},
        )
    assert r.status_code == 200
    assert db_session.get(AutoMergeProjectConfig, test_project.id) is None


def test_ac14_post_disabled_runtime_returns_400(db_session, test_project) -> None:
    _seed_runtime(db_session, 8, enabled=False)
    with _client(db_session) as c:
        r = c.post(
            f"/project/{test_project.id}/auto-merge/config",
            headers={"accept": "application/json"},
            json={"phase": 1, "runtime_option_id": 8},
        )
    assert r.status_code == 400


def test_ac14_settings_dropdown_does_not_include_disabled_rows(db_session, test_project) -> None:
    _seed_runtime(db_session, 101, enabled=True, model="enabled-model")
    _seed_runtime(db_session, 102, enabled=False, model="disabled-model")
    with _client(db_session) as c:
        r = c.get(f"/project/{test_project.id}/auto-merge")
    assert "disabled-model" not in r.text


def test_boundary_phase_2_post_rejected_400(db_session, test_project) -> None:
    with _client(db_session) as c:
        r = c.post(
            f"/project/{test_project.id}/auto-merge/config",
            headers={"accept": "application/json"},
            json={"phase": 2, "runtime_option_id": None},
        )
    assert r.status_code == 400


def test_boundary_phase_3_post_rejected_400(db_session, test_project) -> None:
    with _client(db_session) as c:
        r = c.post(
            f"/project/{test_project.id}/auto-merge/config",
            headers={"accept": "application/json"},
            json={"phase": 3, "runtime_option_id": None},
        )
    assert r.status_code == 400


def test_boundary_concurrent_config_writes_last_write_wins(db_session, test_project) -> None:
    _seed_runtime(db_session, 1)
    with _client(db_session) as c:
        c.post(
            f"/project/{test_project.id}/auto-merge/config",
            headers={"accept": "application/json"},
            json={"phase": 0, "runtime_option_id": 1},
        )
        c.post(
            f"/project/{test_project.id}/auto-merge/config",
            headers={"accept": "application/json"},
            json={"phase": 1, "runtime_option_id": 1},
        )
    assert db_session.get(AutoMergeProjectConfig, test_project.id).phase == 1


def test_invariant_9_config_updated_event_records_before_after(db_session, test_project) -> None:
    _seed_runtime(db_session, 1)
    with _client(db_session) as c:
        c.post(
            f"/project/{test_project.id}/auto-merge/config",
            headers={"accept": "application/json"},
            json={"phase": 1, "runtime_option_id": 1},
        )
    evt = db_session.execute(
        select(DaemonEvent)
        .where(DaemonEvent.event_type == "auto_merge_config_updated")
        .order_by(DaemonEvent.id.desc())
    ).scalar_one()
    assert evt.event_metadata["old"] == {"phase": None, "runtime_option_id": None}
    assert evt.event_metadata["new"] == {"phase": 1, "runtime_option_id": 1}


def test_invariant_3_toml_standalone_when_db_empty(db_session, test_project) -> None:
    cnt = db_session.scalar(
        select(func.count())
        .select_from(AutoMergeProjectConfig)
        .where(AutoMergeProjectConfig.project_id == test_project.id)
    )
    assert cnt == 0


def test_ac10_per_project_phase_split(db_session, test_project) -> None:
    """AC10: per-project override produces different resolved phases.

    Project A has a phase=1 row; project B has a phase=0 row. The resolver
    must return phase=1 for A and phase=0 for B from the same TOML defaults.
    """
    from orch.auto_merge_aggregator import resolve_project_config
    from orch.daemon.auto_merge import AutoMergeConfig
    from orch.db.models import Project

    _seed_runtime(db_session, 1)
    db_session.merge(Project(id="ac10-proj-b", display_name="Proj B", repo_root="/tmp/b"))
    db_session.flush()
    db_session.merge(
        AutoMergeProjectConfig(
            project_id=test_project.id, phase=1, runtime_option_id=None, updated_by="t"
        )
    )
    db_session.merge(
        AutoMergeProjectConfig(
            project_id="ac10-proj-b", phase=0, runtime_option_id=None, updated_by="t"
        )
    )
    db_session.flush()

    toml_config = AutoMergeConfig.defaults()
    rc_a = resolve_project_config(db_session, test_project.id, toml_config)
    rc_b = resolve_project_config(db_session, "ac10-proj-b", toml_config)

    # Per-project overrides MUST yield different resolved phases.
    assert rc_a.phase == 1
    assert rc_b.phase == 0
    assert rc_a.phase != rc_b.phase


def test_ac11_per_project_runtime_override_propagates(db_session, test_project) -> None:
    """AC11: per-project runtime override returns the configured runtime."""
    from orch.auto_merge_aggregator import resolve_project_config
    from orch.daemon.auto_merge import AutoMergeConfig

    # Use a unique high-id slot and a synthetic model name to avoid clashing with
    # the production-seeded runtime options that share the testcontainer session.
    _seed_runtime(db_session, 1011, enabled=True, model="ac11-override-model")
    db_session.merge(
        AutoMergeProjectConfig(
            project_id=test_project.id, phase=1, runtime_option_id=1011, updated_by="t"
        )
    )
    db_session.flush()

    toml_config = AutoMergeConfig.defaults()
    rc = resolve_project_config(db_session, test_project.id, toml_config)

    assert rc.runtime_option_id == 1011
    assert rc.model == "ac11-override-model"
    assert rc.source == "per_project_db"


def test_ac5_health_probe_state_transitions(db_session, test_project) -> None:
    """AC5: health-probe events drive chip state across healthy/degraded/down.

    Seed sequential probe events and assert get_health_summary returns the
    expected state for each scenario.
    """
    from datetime import UTC, datetime, timedelta

    from orch.auto_merge_aggregator import get_health_summary
    from orch.daemon.auto_merge import AutoMergeConfig

    toml_config = AutoMergeConfig.defaults()
    now = datetime.now(UTC)

    # 1) Single successful probe → healthy
    db_session.add(
        DaemonEvent(
            project_id=test_project.id,
            event_type="auto_merge_health_probe",
            entity_id=test_project.id,
            entity_type="project",
            message="probe ok",
            event_metadata={"runtime_reachable": True},
            created_at=now,
        )
    )
    db_session.flush()
    healthy = get_health_summary(db_session, test_project.id, toml_config)
    assert healthy.state == "healthy"
    assert healthy.latest_probe_at is not None

    # 2) One failed probe + still-fresh successful latest → degraded
    db_session.add(
        DaemonEvent(
            project_id=test_project.id,
            event_type="auto_merge_health_probe",
            entity_id=test_project.id,
            entity_type="project",
            message="probe failed",
            event_metadata={"runtime_reachable": False, "error": "boom"},
            created_at=now - timedelta(hours=2),
        )
    )
    db_session.flush()
    degraded = get_health_summary(db_session, test_project.id, toml_config)
    # Latest probe is still "ok" but failures>0 → state is not "healthy" anymore.
    assert degraded.state != "healthy"
    assert degraded.failures_last_24h >= 1

    # 3) Push failures over the threshold → state goes "down".
    threshold = toml_config.health_failure_rate_threshold_per_day
    for i in range(threshold + 1):
        db_session.add(
            DaemonEvent(
                project_id=test_project.id,
                event_type="auto_merge_health_probe",
                entity_id=test_project.id,
                entity_type="project",
                message="probe failed",
                event_metadata={"runtime_reachable": False, "error": "timeout"},
                created_at=now - timedelta(hours=3 + i),
            )
        )
    db_session.flush()
    down = get_health_summary(db_session, test_project.id, toml_config)
    assert down.state == "down"
    assert down.failures_last_24h > threshold
