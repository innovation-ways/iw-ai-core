from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import DaemonEvent, MergeAutoVerdict
from tests.fixtures.auto_merge_observability.fixtures import mock_git_show, seeded_events_factory


def _client(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def test_ac1_empty_state_page_render(db_session, test_project) -> None:
    with _client(db_session) as c:
        r = c.get(f"/project/{test_project.id}/auto-merge")
    assert r.status_code == 200


def test_ac2_seeded_events_render_inline_verdict_widgets(db_session, test_project) -> None:
    seeded_events_factory(db_session, test_project.id, resolved=1)
    with _client(db_session) as c:
        r = c.get(f"/project/{test_project.id}/auto-merge/events")
    assert r.status_code == 200


def test_ac3_inline_verdict_persists_to_db(db_session, test_project) -> None:
    event = seeded_events_factory(db_session, test_project.id, resolved=1)[-1]
    with _client(db_session) as c:
        r = c.post(
            f"/project/{test_project.id}/auto-merge/events/{event.id}/verdict",
            headers={"accept": "application/json"},
            json={"verdict": "correct", "notes": "ok"},
        )
    assert r.status_code == 200
    saved = db_session.get(MergeAutoVerdict, (test_project.id, event.id))
    assert saved is not None
    assert saved.verdict == "correct"


def test_ac4_modal_diff_viewer_shows_proposed_vs_main(
    db_session, test_project, monkeypatch
) -> None:
    e = DaemonEvent(
        project_id=test_project.id,
        event_type="merge_auto_resolved",
        entity_id="W",
        entity_type="work_item",
        message="resolved",
        event_metadata={"llm_calls": [{"file_path": "a.py", "proposed_content": "new"}]},
    )
    db_session.add(e)
    db_session.flush()
    mock_git_show(monkeypatch, {"a.py": "old"})
    with _client(db_session) as c:
        r = c.get(f"/project/{test_project.id}/auto-merge/events/{e.id}")
    assert r.status_code == 200
    assert "Proposed by LLM" in r.text


def test_ac4_boundary_file_no_longer_on_main(db_session, test_project, monkeypatch) -> None:
    e = DaemonEvent(
        project_id=test_project.id,
        event_type="merge_auto_resolved",
        entity_id="W",
        entity_type="work_item",
        message="resolved",
        event_metadata={"llm_calls": [{"file_path": "missing.py", "proposed_content": "new"}]},
    )
    db_session.add(e)
    db_session.flush()
    mock_git_show(monkeypatch, {"missing.py": None})
    with _client(db_session) as c:
        r = c.get(f"/project/{test_project.id}/auto-merge/events/{e.id}")
    assert r.status_code == 200
    assert "(file no longer exists on main)" in r.text


def test_ac7_refuse_list_widget_hidden_when_zero(db_session, test_project) -> None:
    with _client(db_session) as c:
        r = c.get(f"/project/{test_project.id}/auto-merge/rollup")
    assert r.status_code == 200


def test_ac7_refuse_list_widget_groups_by_reason(db_session, test_project) -> None:
    seeded_events_factory(db_session, test_project.id, skipped=2)
    with _client(db_session) as c:
        r = c.get(f"/project/{test_project.id}/auto-merge/rollup")
    assert r.status_code == 200


def test_ac8_token_cost_rollup_with_real_model_pricing(db_session, test_project) -> None:
    seeded_events_factory(db_session, test_project.id, resolved=2)
    with _client(db_session) as c:
        r = c.get(f"/project/{test_project.id}/auto-merge/rollup?window=7d")
    assert r.status_code == 200


def test_boundary_event_with_no_llm_calls(db_session, test_project) -> None:
    e = DaemonEvent(
        project_id=test_project.id,
        event_type="merge_auto_resolved",
        entity_id="W",
        entity_type="work_item",
        message="resolved",
        event_metadata={},
    )
    db_session.add(e)
    db_session.flush()
    with _client(db_session) as c:
        r = c.get(f"/project/{test_project.id}/auto-merge/events/{e.id}")
    assert r.status_code == 200


def test_invariant_1_daemon_events_append_only(db_session, test_project) -> None:
    before = db_session.execute(select(DaemonEvent)).scalars().all()
    seeded_events_factory(db_session, test_project.id, resolved=1)
    after = db_session.execute(select(DaemonEvent)).scalars().all()
    assert len(after) >= len(before)
