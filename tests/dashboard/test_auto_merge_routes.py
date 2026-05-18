from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING

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
    Project,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


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


# ---------------------------------------------------------------------------
# I-00091 — settings form sync regression tests
# ---------------------------------------------------------------------------


def _extract_select_block(html: str, name: str) -> str:
    """Return the inner HTML of <select name=\"{name}\">...</select>.

    Raises AssertionError if the select is missing — that itself is a useful failure.
    """
    pattern = re.compile(
        rf"<select\b[^>]*\bname=\"{re.escape(name)}\"[^>]*>(.*?)</select>",
        re.DOTALL,
    )
    match = pattern.search(html)
    assert match is not None, f'<select name="{name}"> not found in response'
    return match.group(1)


def test_settings_form_reflects_phase_only_override(
    client: TestClient, test_project, db_session
) -> None:
    """Phase-only override: Phase=1 selected, Runtime stays on global.

    DB row: phase=1, runtime_option_id=NULL
    Expected: Phase block has value="1" selected; Runtime block has value="global" selected.
    """
    db_session.merge(
        AutoMergeProjectConfig(
            project_id=test_project.id,
            phase=1,
            runtime_option_id=None,
            updated_by="test-fixture",
        )
    )
    db_session.flush()

    response = client.get(f"/project/{test_project.id}/auto-merge")
    assert response.status_code == 200
    html = response.text

    phase_block = _extract_select_block(html, name="phase")
    assert 'value="1" selected' in phase_block, f"Phase should be 1; got:\n{phase_block}"
    assert 'value="global" selected' not in phase_block

    runtime_block = _extract_select_block(html, name="runtime_option_id")
    assert 'value="global" selected' in runtime_block

    # Footer shows "Last changed" (not "Using global default")
    assert "Last changed:" in html
    assert "Using global default" not in html


def test_settings_form_reflects_runtime_only_override(
    client: TestClient, test_project, db_session
) -> None:
    """Runtime-only override: Runtime=<id> selected, Phase stays on global.

    DB row: phase=NULL, runtime_option_id=<enabled row>
    Expected: Phase block has value="global" selected; Runtime block has that id selected.
    """
    _runtime(db_session, rid=5, enabled=True)
    db_session.merge(
        AutoMergeProjectConfig(
            project_id=test_project.id,
            phase=None,
            runtime_option_id=5,
            updated_by="test-fixture",
        )
    )
    db_session.flush()

    response = client.get(f"/project/{test_project.id}/auto-merge")
    assert response.status_code == 200
    html = response.text

    phase_block = _extract_select_block(html, name="phase")
    assert 'value="global" selected' in phase_block
    assert 'value="1" selected' not in phase_block

    runtime_block = _extract_select_block(html, name="runtime_option_id")
    assert 'value="5" selected' in runtime_block, f"Runtime should be 5; got:\n{runtime_block}"
    assert 'value="global" selected' not in runtime_block

    # Footer shows "Last changed"
    assert "Last changed:" in html
    assert "Using global default" not in html


def test_settings_form_reflects_both_axes_override(
    client: TestClient, test_project, db_session
) -> None:
    """Both axes overridden: Phase=1 and Runtime=<id> both selected.

    DB row: phase=1, runtime_option_id=<enabled>
    Expected: Phase block has value="1" selected; Runtime block has that id selected.
    """
    _runtime(db_session, rid=6, enabled=True)
    db_session.merge(
        AutoMergeProjectConfig(
            project_id=test_project.id,
            phase=1,
            runtime_option_id=6,
            updated_by="test-fixture",
        )
    )
    db_session.flush()

    response = client.get(f"/project/{test_project.id}/auto-merge")
    assert response.status_code == 200
    html = response.text

    phase_block = _extract_select_block(html, name="phase")
    assert 'value="1" selected' in phase_block, f"Phase should be 1; got:\n{phase_block}"
    assert 'value="global" selected' not in phase_block

    runtime_block = _extract_select_block(html, name="runtime_option_id")
    assert 'value="6" selected' in runtime_block, f"Runtime should be 6; got:\n{runtime_block}"
    assert 'value="global" selected' not in runtime_block

    # Footer shows "Last changed"
    assert "Last changed:" in html
    assert "Using global default" not in html


def test_settings_form_clears_back_to_global(client: TestClient, test_project, db_session) -> None:
    """No DB row: both dropdowns render as 'Use global default'.

    No AutoMergeProjectConfig row.
    Expected: Phase block has value="global" selected; Runtime block has value="global" selected.
    Footer reads 'Using global default'.
    """
    response = client.get(f"/project/{test_project.id}/auto-merge")
    assert response.status_code == 200
    html = response.text

    phase_block = _extract_select_block(html, name="phase")
    assert 'value="global" selected' in phase_block
    assert 'value="1" selected' not in phase_block
    assert 'value="0" selected' not in phase_block

    runtime_block = _extract_select_block(html, name="runtime_option_id")
    assert 'value="global" selected' in runtime_block

    # Footer reads "Using global default"
    assert "Using global default" in html
    assert "Last changed:" not in html


# ---------------------------------------------------------------------------
# I-00097 — Auto-merge polish regression tests
# Token cost zero formatting + entity_id linkification
# ---------------------------------------------------------------------------


def test_token_cost_zero_renders_as_dollar_zero(client: TestClient, test_project) -> None:
    """AC1: exact-zero cost must NOT render with 6 decimal places — renders as '$0'."""
    response = client.get(f"/project/{test_project.id}/auto-merge/rollup?window=7d")
    assert response.status_code == 200
    html = response.text
    # The noisy form must not appear
    assert "$0.000000" not in html, "exact zero must not render with 6 decimal places"
    # The cost line format is: in: N · out: N · $VALUE
    cost_line = re.search(r"<p\b[^>]*>\s*in:\s*\d+\s*·\s*out:\s*\d+\s*·\s*\$(\S+)\s*</p>", html)
    assert cost_line, f"cost line not found in:\n{html[:1000]}"
    assert cost_line.group(1) == "0", f"expected '$0'; got '${cost_line.group(1)}'"


def test_token_cost_nonzero_keeps_precision(client: TestClient, test_project, db_session) -> None:
    """AC2: small non-zero cost keeps meaningful precision — no trailing zeros."""
    # Seed an event with llm_calls metadata that produces a small non-zero cost.
    # MODEL_PRICING includes claude-sonnet-4-6 at $3/M in, $15/M out.
    # 1000 input + 100 output tokens of sonnet → cost = 0.003 + 0.0015 = 0.0045
    e = DaemonEvent(
        project_id=test_project.id,
        event_type="merge_auto_resolved",
        entity_id="W",
        entity_type="work_item",
        message="x",
        event_metadata={
            "llm_calls": [
                {"model": "claude-sonnet-4-6", "input_tokens": 1000, "output_tokens": 100}
            ]
        },
    )
    db_session.add(e)
    db_session.flush()

    response = client.get(f"/project/{test_project.id}/auto-merge/rollup?window=7d")
    assert response.status_code == 200
    html = response.text
    cost_line = re.search(r"in:\s*\d+\s*·\s*out:\s*\d+\s*·\s*\$(\S+)\s*</p>", html)
    assert cost_line, f"cost line not found in:\n{html[:1000]}"
    val = cost_line.group(1)
    # The value must be non-zero and not have 6 trailing zeros (no spurious precision)
    assert val != "0", f"expected non-zero cost; got '${val}'"
    assert not val.endswith("000000"), f"trailing zeros not trimmed; got '${val}'"


def test_entity_id_renders_as_link_for_work_item_ids(
    client: TestClient, db_session: Session
) -> None:
    """AC3: entity_id matching work-item ID pattern is a link to /project/{id}/item/{eid}."""
    # Use project_id='iw-ai-core' to match the URL pattern used in the template
    project = db_session.merge(
        Project(id="iw-ai-core", display_name="IW Core", repo_root="/x", config={})
    )
    db_session.flush()

    e = DaemonEvent(
        project_id=project.id,
        event_type="merge_auto_resolved",
        entity_id="CR-00057",
        entity_type="work_item",
        message="step launched",
        event_metadata={},
    )
    db_session.add(e)
    db_session.flush()

    response = client.get(f"/project/{project.id}/auto-merge/events?page=0&page_size=10")
    assert response.status_code == 200
    html = response.text

    # The entity_id cell must contain a link to /project/iw-ai-core/item/CR-00057
    # (singular 'item' — matches dashboard/routers/items.py route convention)
    assert re.search(
        r'<a\b[^>]*\bhref="/project/iw-ai-core/item/CR-00057"[^>]*>\s*CR-00057\s*</a>',
        html,
    ), f"entity_id should be a link; got snippet:\n{html[:2000]}"


def test_entity_id_renders_plain_when_not_work_item_id(
    client: TestClient, db_session: Session
) -> None:
    """AC4: entity_id that is not a work-item ID renders as plain text (no /item/ link)."""
    project = db_session.merge(
        Project(id="iw-ai-core", display_name="IW Core", repo_root="/x", config={})
    )
    db_session.flush()

    e = DaemonEvent(
        project_id=project.id,
        event_type="auto_merge_config_updated",
        entity_id="iw-ai-core",  # project_id — not a work item
        entity_type="project",
        message="config updated",
        event_metadata={},
    )
    db_session.add(e)
    db_session.flush()

    response = client.get(f"/project/{project.id}/auto-merge/events?page=0&page_size=10")
    assert response.status_code == 200
    html = response.text

    # 'iw-ai-core' must appear as text
    assert "iw-ai-core" in html
    # But it must NOT be wrapped in an /item/ link
    assert not re.search(r'href="/project/[^"]+/item/iw-ai-core"', html)


def test_entity_id_renders_dash_when_null(client: TestClient, test_project, db_session) -> None:
    """AC5: null entity_id renders as '—' (preserved existing behaviour)."""
    e = DaemonEvent(
        project_id=test_project.id,
        event_type="auto_merge_health_probe",
        entity_id=None,
        entity_type=None,
        message="probe",
        event_metadata={},
    )
    db_session.add(e)
    db_session.flush()

    response = client.get(f"/project/{test_project.id}/auto-merge/events?page=0&page_size=10")
    assert response.status_code == 200
    html = response.text

    # The entity_id cell must show '—' for null entity_id.
    # Scope to the font-mono td (the entity_id column) to avoid matching other cells.
    assert re.search(r"<td[^>]*\bfont-mono\b[^>]*>\s*—\s*</td>", html), (
        "entity_id cell should render '—' for null; got:\n" + html[:2000]
    )
