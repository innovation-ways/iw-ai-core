"""Tests for the keep-alive runs table — diagnostic columns render correctly for NULL and populated
rows.
"""

from __future__ import annotations

import re
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import KeepAliveRun


@pytest.fixture
def db(db_session):
    """Alias fixture that returns the shared test db_session."""
    return db_session


@pytest.fixture
def client(db) -> Generator[TestClient, None, None]:
    """Provide a TestClient with keep-alive config seeded and get_db overridden."""
    from orch.keep_alive_service import get_config

    get_config(db)
    db.commit()

    def override_get_db():
        """Return the test db_session for FastAPI dependency injection."""
        return db

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


def test_recent_runs_table_renders_em_dash_for_null_diagnostic_fields(client, db):
    """I-00112: pre-fix rows (NULL stdout/elapsed_ms) render as '—' without crashing."""
    db.add(KeepAliveRun(slot_id=None, slot_time="05:00", status="success", error=None))
    db.commit()

    resp = client.get("/api/keep-alive/runs")

    assert resp.status_code == 200
    html = resp.text
    assert ">Elapsed<" in html
    assert ">Output<" in html
    assert html.count("—") >= 2
    assert re.search(
        r"<td class=\"px-4 py-2 font-mono text-xs whitespace-nowrap\">\s*—\s*</td>", html
    )
    assert re.search(r"<td class=\"px-4 py-2 text-xs\">\s*—\s*</td>", html)


def test_recent_runs_table_renders_populated_diagnostic_fields(client, db):
    """I-00112: post-fix rows render elapsed_ms and stdout snippet."""
    db.add(
        KeepAliveRun(
            slot_id=None,
            slot_time="05:00",
            status="success",
            error=None,
            stdout="OK reply",
            stderr="",
            elapsed_ms=3500,
            returncode=0,
        )
    )
    db.commit()

    resp = client.get("/api/keep-alive/runs")

    assert resp.status_code == 200
    html = resp.text
    assert re.search(r">\s*3500 ms\s*<", html)
    assert 'title="OK reply"' in html
    assert ">OK reply" in html
