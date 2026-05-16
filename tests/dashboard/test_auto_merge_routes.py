from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import (
    AgentRuntimeOption,
    AutoMergeProjectConfig,
    DaemonEvent,
    MergeAutoVerdict,
)


def _force_phase_0(db_session, project_id: str) -> None:
    """Override the TOML default (phase=1) with a per-project phase=0 row so
    AC6 / Inv 6 tests assert against the intended state."""
    db_session.merge(
        AutoMergeProjectConfig(
            project_id=project_id,
            phase=0,
            runtime_option_id=None,
            updated_by="test-fixture",
        )
    )
    db_session.flush()


@pytest.fixture
def client(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _runtime(db_session, rid=1, enabled=True):
    db_session.merge(
        AgentRuntimeOption(
            id=rid,
            cli_tool="opencode",
            model=f"m-{rid}",
            cli_label="OpenCode",
            model_label=f"M{rid}",
            display_name=f"M{rid}",
            is_default=(rid == 1),
            enabled=enabled,
            sort_order=rid,
        )
    )
    db_session.flush()


def _event(db_session, project_id: str, event_type: str = "merge_auto_resolved") -> DaemonEvent:
    e = DaemonEvent(
        project_id=project_id,
        event_type=event_type,
        entity_id="W",
        entity_type="work_item",
        message="event",
        event_metadata={"llm_calls": [{"file_path": "a.py", "proposed_content": "new"}]},
    )
    db_session.add(e)
    db_session.flush()
    return e


def test_page_render(client: TestClient, test_project) -> None:
    assert client.get(f"/project/{test_project.id}/auto-merge").status_code == 200


def test_status_fragment(client: TestClient, test_project, db_session) -> None:
    _runtime(db_session)
    assert client.get(f"/project/{test_project.id}/auto-merge/status").status_code == 200


def test_events_fragment(client: TestClient, test_project, db_session) -> None:
    _event(db_session, test_project.id)
    assert client.get(f"/project/{test_project.id}/auto-merge/events").status_code == 200


def test_event_detail(client: TestClient, test_project, db_session) -> None:
    e = _event(db_session, test_project.id)
    assert client.get(f"/project/{test_project.id}/auto-merge/events/{e.id}").status_code == 200


def test_verdict_post_valid(client: TestClient, test_project, db_session) -> None:
    e = _event(db_session, test_project.id)
    r = client.post(
        f"/project/{test_project.id}/auto-merge/events/{e.id}/verdict",
        headers={"accept": "application/json"},
        json={"verdict": "correct", "notes": "ok"},
    )
    assert r.status_code == 200


def test_verdict_post_invalid_verdict(client: TestClient, test_project, db_session) -> None:
    e = _event(db_session, test_project.id)
    assert (
        client.post(
            f"/project/{test_project.id}/auto-merge/events/{e.id}/verdict",
            headers={"accept": "application/json"},
            json={"verdict": "nope", "notes": ""},
        ).status_code
        == 400
    )


def test_verdict_post_oversize_notes(client: TestClient, test_project, db_session) -> None:
    e = _event(db_session, test_project.id)
    assert (
        client.post(
            f"/project/{test_project.id}/auto-merge/events/{e.id}/verdict",
            headers={"accept": "application/json"},
            json={"verdict": "wrong", "notes": "x" * 9000},
        ).status_code
        == 413
    )


def test_verdict_post_non_resolved_event(client: TestClient, test_project, db_session) -> None:
    e = _event(db_session, test_project.id, event_type="merge_auto_resolution_attempted")
    assert (
        client.post(
            f"/project/{test_project.id}/auto-merge/events/{e.id}/verdict",
            headers={"accept": "application/json"},
            json={"verdict": "wrong", "notes": ""},
        ).status_code
        == 400
    )


def test_config_post_valid(client: TestClient, test_project, db_session) -> None:
    _runtime(db_session)
    assert (
        client.post(
            f"/project/{test_project.id}/auto-merge/config",
            headers={"accept": "application/json"},
            json={"phase": 1, "runtime_option_id": 1},
        ).status_code
        == 200
    )


def test_config_post_disabled_runtime(client: TestClient, test_project, db_session) -> None:
    _runtime(db_session, rid=9, enabled=False)
    assert (
        client.post(
            f"/project/{test_project.id}/auto-merge/config",
            headers={"accept": "application/json"},
            json={"phase": 1, "runtime_option_id": 9},
        ).status_code
        == 400
    )


def test_config_post_phase_2(client: TestClient, test_project) -> None:
    assert (
        client.post(
            f"/project/{test_project.id}/auto-merge/config",
            headers={"accept": "application/json"},
            json={"phase": 2, "runtime_option_id": None},
        ).status_code
        == 400
    )


def test_rollup_fragment(client: TestClient, test_project, db_session) -> None:
    e = _event(db_session, test_project.id)
    db_session.merge(
        MergeAutoVerdict(
            project_id=test_project.id,
            daemon_event_id=e.id,
            verdict="pending",
            verdict_notes="",
            verdicted_by="x",
            verdicted_at=datetime.now(UTC),
        )
    )
    db_session.flush()
    assert client.get(f"/project/{test_project.id}/auto-merge/rollup").status_code == 200


def test_ac6_phase_0_hides_chip_in_header_html(
    client: TestClient, test_project, db_session
) -> None:
    _force_phase_0(db_session, test_project.id)
    r = client.get(f"/project/{test_project.id}/auto-merge/status?compact=true")
    assert r.status_code == 200
    # Compact status endpoint MUST return an empty body when phase == 0 so the
    # header chip placeholder disappears entirely (Inv 6).
    assert r.text.strip() == ""


def test_ac6_phase_0_page_shows_plumbing_only_message(
    client: TestClient, test_project, db_session
) -> None:
    _force_phase_0(db_session, test_project.id)
    r = client.get(f"/project/{test_project.id}/auto-merge")
    assert r.status_code == 200
    # AC6 requires the plumbing-only friendly message when phase == 0.
    assert "plumbing-only" in r.text.lower() or "Use Settings" in r.text


def test_invariant_6_chip_dom_element_absent_in_phase_0_html(
    client: TestClient, test_project, db_session
) -> None:
    _force_phase_0(db_session, test_project.id)
    # The chip must be absent server-side (not just CSS-hidden) on adjacent
    # per-project pages when phase resolves to 0.
    r = client.get(f"/project/{test_project.id}/queue")
    assert r.status_code == 200
    assert "auto-merge-chip-header" not in r.text


def test_invariant_8_verdict_upsert_is_idempotent(
    client: TestClient, test_project, db_session
) -> None:
    e = _event(db_session, test_project.id)
    client.post(
        f"/project/{test_project.id}/auto-merge/events/{e.id}/verdict",
        headers={"accept": "application/json"},
        json={"verdict": "pending", "notes": "a"},
    )
    client.post(
        f"/project/{test_project.id}/auto-merge/events/{e.id}/verdict",
        headers={"accept": "application/json"},
        json={"verdict": "wrong", "notes": "b"},
    )
    rows = (
        db_session.execute(
            select(MergeAutoVerdict).where(
                MergeAutoVerdict.project_id == test_project.id,
                MergeAutoVerdict.daemon_event_id == e.id,
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].verdict == "wrong"


@pytest.mark.parametrize(
    "suffix",
    [
        "queue",
        "history",
        "batches",
        "code",
        "docs",
        "tests",
        "quality",
        "jobs",
        "healthz/identity",
    ],
)
def test_ac9_existing_routes_unaffected(client: TestClient, test_project, suffix: str) -> None:
    if suffix == "healthz/identity":
        r = client.get("/healthz/identity")
        assert r.status_code in (200, 503)
        payload = r.json()
        assert payload["mode"] in {"bootstrap", "match", "mismatch"}
        # Identity response must always carry the expected fingerprint key.
        assert "expected" in payload
    else:
        r = client.get(f"/project/{test_project.id}/{suffix}")
        assert r.status_code == 200
        # AC9: existing per-project pages must render a non-empty HTML body.
        # The middleware must not have raised — if it crashes, FastAPI would
        # propagate a 500 instead of 200.
        body = r.text
        assert "<!DOCTYPE html>" in body or "<html" in body
        assert len(body) > 256
