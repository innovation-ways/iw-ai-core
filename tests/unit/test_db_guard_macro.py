"""Regression guard for dashboard/templates/macros/db_guard.html.

The `write_button_attrs` macro emits a constant pre-quoted HTML attribute string
when `is_db_stale(request)` is True, and an empty string when False. This test
locks both outputs.

This invariant is what justifies CR-00051's project-wide Makefile `--exclude-rule`
for `generic.html-templates.security.unquoted-attribute-var.unquoted-attribute-var`:
the rule fires at every macro callsite, but is a false positive because the macro
output is a constant string. If a future edit changes the macro to interpolate
user input, this test fails and forces the team to revisit the exclude flag.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from jinja2 import Environment, FileSystemLoader

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = REPO_ROOT / "dashboard" / "templates"

EXPECTED_STALE = (
    'disabled aria-disabled="true" '
    "title=\"Orch DB schema mismatch — run 'make db-migrate' to fix.\""
)
EXPECTED_FRESH = ""


def _make_env() -> Environment:
    """Build a fresh Jinja2 Environment pointing at the dashboard templates.

    `is_db_stale` is registered as a callable that inspects the request's
    `.stale` attribute. The test controls the rendered branch by passing
    a SimpleNamespace(stale=True|False) as `request`. This mirrors how the
    real `dashboard.app` registers `is_db_stale` as a Jinja global (see
    dashboard/app.py:234) without spinning up the FastAPI app.
    """
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=True,
    )
    env.globals["is_db_stale"] = lambda request: bool(getattr(request, "stale", False))
    return env


def _render(env: Environment, *, stale: bool) -> str:
    tmpl = env.from_string(
        "{% from 'macros/db_guard.html' import write_button_attrs %}"
        "{{ write_button_attrs(request) }}"
    )
    return tmpl.render(request=SimpleNamespace(stale=stale)).strip()


@pytest.fixture
def jinja_env() -> Environment:
    return _make_env()


def test_write_button_attrs_when_db_is_fresh(jinja_env: Environment) -> None:
    rendered = _render(jinja_env, stale=False)
    assert rendered == EXPECTED_FRESH, f"Expected empty output when DB is fresh, got: {rendered!r}"


def test_write_button_attrs_when_db_is_stale(jinja_env: Environment) -> None:
    rendered = _render(jinja_env, stale=True)
    assert rendered == EXPECTED_STALE, (
        f"Expected pre-quoted attributes when DB is stale, got: {rendered!r}"
    )


def test_write_button_attrs_output_is_well_formed_html_attrs(
    jinja_env: Environment,
) -> None:
    """Sanity: every attribute value in the stale branch is wrapped in matched
    double-quotes.

    The exact constant has two quoted values: aria-disabled="true" and title="...".
    """
    rendered = _render(jinja_env, stale=True)
    open_count = rendered.count('="')
    assert open_count == 2, f"Expected 2 quoted attributes, found {open_count} in: {rendered!r}"
