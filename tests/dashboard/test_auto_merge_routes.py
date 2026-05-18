from __future__ import annotations

import re
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


def _extract_filter_chip_blocks(html: str) -> dict[str, str]:
    """Return {label: outer-<a>-tag-as-html} for each filter chip in the
    events-table fragment. Raises if not all 7 chips are found.
    """
    # The chips live inside <div class="flex flex-wrap gap-2">…</div>.
    # Each chip is an <a> whose body text is the label.
    pattern = re.compile(
        r"(<a\b[^>]*?>\s*([\w_]+)\s*</a>)",
        re.DOTALL,
    )
    out: dict[str, str] = {}
    for match in pattern.finditer(html):
        anchor, label = match.group(1), match.group(2)
        if "hx-get=" in anchor and "auto-merge/events" in anchor:
            out[label] = anchor
    expected = {
        "all",
        "resolved",
        "attempted",
        "failed",
        "skipped",
        "health_probe",
        "config_updated",
    }
    assert expected <= out.keys(), f"missing chips: {expected - out.keys()}"
    return out


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


# ---------------------------------------------------------------------------
# I-00092 — filter chip active-state regression tests
# ---------------------------------------------------------------------------


def test_filter_chip_resolved_is_highlighted_when_active(
    client: TestClient, test_project, db_session
) -> None:
    """AC1 / I-00092: 'resolved' chip carries bg-primary + aria-pressed=true
    when ?type=merge_auto_resolved is in the URL; no other chip is active."""
    _event(db_session, test_project.id, event_type="merge_auto_resolved")
    response = client.get(
        f"/project/{test_project.id}/auto-merge/events?page=0&page_size=10&type=merge_auto_resolved"
    )
    assert response.status_code == 200
    chips = _extract_filter_chip_blocks(response.text)

    # Attribute-scoped check (I-00067): bg-primary must appear inside the
    # class attribute of the 'resolved' chip's <a>, not just anywhere in HTML.
    assert re.search(r'class\s*=\s*"[^"]*\bbg-primary\b[^"]*"', chips["resolved"]), (
        f"'resolved' chip should carry bg-primary; got:\n{chips['resolved']}"
    )
    assert 'aria-pressed="true"' in chips["resolved"]

    for other in ("all", "attempted", "failed", "skipped", "health_probe", "config_updated"):
        assert "bg-primary" not in chips[other], (
            f"'{other}' should NOT carry bg-primary when 'resolved' is active; got:\n{chips[other]}"
        )
        assert 'aria-pressed="false"' in chips[other]


def test_filter_chip_all_is_highlighted_when_no_type_param(
    client: TestClient, test_project, db_session
) -> None:
    """AC2 / I-00092: 'all' chip is active when no ?type= param is provided."""
    _event(db_session, test_project.id)
    response = client.get(f"/project/{test_project.id}/auto-merge/events?page=0&page_size=10")
    assert response.status_code == 200
    chips = _extract_filter_chip_blocks(response.text)

    assert re.search(r'class\s*=\s*"[^"]*\bbg-primary\b[^"]*"', chips["all"]), (
        f"'all' chip should carry bg-primary; got:\n{chips['all']}"
    )
    assert 'aria-pressed="true"' in chips["all"]

    for other in ("resolved", "attempted", "failed", "skipped", "health_probe", "config_updated"):
        assert "bg-primary" not in chips[other], (
            f"'{other}' should NOT carry bg-primary when 'all' is active; got:\n{chips[other]}"
        )
        assert 'aria-pressed="false"' in chips[other]


def test_filter_chip_title_tooltips_match_event_types(
    client: TestClient, test_project, db_session
) -> None:
    """AC3 / I-00092: each chip's <a> title attribute matches its event_type."""
    _event(db_session, test_project.id)
    response = client.get(f"/project/{test_project.id}/auto-merge/events?page=0&page_size=10")
    assert response.status_code == 200
    chips = _extract_filter_chip_blocks(response.text)

    assert 'title="merge_auto_resolved"' in chips["resolved"]
    assert 'title="merge_auto_resolution_attempted"' in chips["attempted"]
    assert 'title="merge_auto_resolution_failed"' in chips["failed"]
    assert 'title="merge_auto_resolution_skipped"' in chips["skipped"]
    assert 'title="auto_merge_health_probe"' in chips["health_probe"]
    assert 'title="auto_merge_config_updated"' in chips["config_updated"]
    assert 'title="all event types"' in chips["all"]
