"""Unit tests for favicon serving and template integration."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from dashboard.app import create_app


def test_favicon_served_at_static_path() -> None:
    """GET /static/favicon.svg returns the SVG favicon."""
    client = TestClient(create_app())
    resp = client.get("/static/favicon.svg")

    assert resp.status_code == 200
    assert "svg" in resp.headers["content-type"]
    assert "<svg" in resp.text


def test_base_template_contains_favicon_link() -> None:
    """base.html includes a <link rel="icon"> pointing to the favicon."""
    template_path = Path(__file__).resolve().parents[2] / "dashboard" / "templates" / "base.html"
    html = template_path.read_text()

    assert 'rel="icon"' in html
    assert 'href="/static/favicon.svg"' in html
