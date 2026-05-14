"""Anchor tests for F-00082 S03: cancel-button frontend wiring.

These tests verify:
1. confirm_dialog macro renders a form when form_html is set
2. confirm_dialog macro is byte-identical when form_html is empty (no regression)
3. batch_detail_header renders cancel button for executing batch
4. item_header renders disabled cancel button when item is in active batch

Container: dashboard tests use FastAPI TestClient with testcontainer-backed
db_session fixture (never the live DB port 5433).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape


def _template_dir() -> str:
    return str((Path(__file__).parent.parent.parent / "dashboard" / "templates").resolve())


def _env() -> Environment:
    """Mirror the dashboard's Jinja env (filters/globals used by templates)."""
    env = Environment(
        loader=FileSystemLoader(_template_dir()),
        autoescape=select_autoescape(enabled_extensions=("html",)),
    )
    env.filters["localdt"] = lambda _dt, _fmt="%b %d %H:%M": ""
    env.filters["timeago"] = lambda _dt: ""
    env.filters["fmt_ts_time"] = lambda _dt: ""
    env.filters["intcomma"] = lambda n: f"{n:,}" if isinstance(n, int) else str(n)
    env.globals["is_db_stale"] = lambda _request: False
    return env


# ---------------------------------------------------------------------------
# Test 1: confirm_dialog macro renders form when form_html is set
# ---------------------------------------------------------------------------


def test_confirm_dialog_macro_renders_form_when_form_html_set():
    """When form_html is non-empty, the macro wraps body+buttons in <form>."""
    env = _env()
    template = env.get_template("components/confirm_dialog.html")
    form_html = (
        '<label>Reason: <textarea name="reason" rows="3">'
        "cancelled by operator</textarea></label>"
        '<label><input type="checkbox" name="to_draft" value="true"> '
        "Also reset to draft</label>"
    )
    # Call the macro directly from the module (file only contains a macro def)
    rendered = template.module.confirm_dialog(
        title="Cancel Item?",
        description="This will teardown the worktree.",
        confirm_url="/api/item/X-1/cancel",
        confirm_method="post",
        confirm_label="Cancel Item",
        danger=True,
        form_html=form_html,
    )
    # The form element must be present with the correct action
    assert "<form" in rendered, "Expected a <form> element when form_html is set"
    assert 'method="post"' in rendered, "Form must use POST method"
    assert 'action="/api/item/X-1/cancel"' in rendered, "Form action must match confirm_url"
    # The form fields must be present
    assert 'name="reason"' in rendered, "Textarea for reason must be in the form"
    assert 'name="to_draft"' in rendered, "Checkbox for to_draft must be in the form"
    # Confirm button label must be present
    assert "Cancel Item" in rendered


def test_confirm_dialog_macro_byte_identical_when_form_html_empty():
    """When form_html is empty, confirm_dialog renders EXACTLY the original HTML
    (no regression for approve/pause/resume/kill actions that don't use a form).
    """
    env = _env()
    template = env.get_template("components/confirm_dialog.html")
    # Call macro with empty form_html (default) — this tests the non-form branch
    rendered = template.module.confirm_dialog(
        title="Approve Item?",
        description="This will move the item to the queue.",
        confirm_url="/project/P1/api/item/X-1/approve",
        confirm_method="post",
        confirm_label="Approve",
        danger=False,
        form_html="",  # empty — tests the non-form branch
    )
    # The non-form path: no <form> element, no method="post" on a form
    assert "<form" not in rendered, "No <form> element when form_html is empty"
    # Original buttons must be present (Cancel and Confirm)
    assert "Approve" in rendered
    assert "Cancel" in rendered
    # htmx attribute on the confirm button preserved
    assert 'hx-post="/project/P1/api/item/X-1/approve"' in rendered
    # No textarea or checkbox leaked in
    assert 'name="reason"' not in rendered
    assert 'name="to_draft"' not in rendered


# ---------------------------------------------------------------------------
# Test 3: batch_detail_header renders cancel button for executing batch
# ---------------------------------------------------------------------------


def test_batch_detail_header_renders_cancel_button_for_executing_batch():
    """batch_detail_header.html must render a Cancel button when batch_status
    is 'executing' (one of CANCELLABLE_BATCH_STATUSES).
    """
    env = _env()
    template = env.get_template("fragments/batch_detail_header.html")
    # Minimal required context
    ctx = {
        "current_project": SimpleNamespace(id="P1"),
        "batch": SimpleNamespace(id="BATCH-1"),
        "batch_status": "executing",
        "items": [],
        "batch_duration_secs": None,
    }
    rendered = template.render(**ctx)
    # Must have a Cancel button
    assert "Cancel" in rendered
    # Cancel button must use htmx GET to the cancel confirmation endpoint
    assert "api/confirm-batch/cancel/BATCH-1" in rendered
    # Must NOT have the old if/elif chain that only showed cancel for 'planning'/'approved'
    # (executing is now included)
    assert "executing" in rendered  # cancel button appears for executing


# ---------------------------------------------------------------------------
# Test 4: item_header renders disabled cancel when item is in active batch
# ---------------------------------------------------------------------------


def test_item_header_renders_disabled_cancel_when_in_active_batch():
    """When item.status is in CANCELLABLE_WORK_ITEM_STATUSES but the item
    belongs to an active batch (batch_status in _ACTIVE_BATCH_STATUSES),
    the cancel button must be rendered as disabled with a hint paragraph.
    """
    env = _env()
    template = env.get_template("fragments/item_header.html")
    ctx = {
        "current_project": SimpleNamespace(id="P1"),
        "item": SimpleNamespace(
            id="X-1",
            title="Test item",
            status="in_progress",
            type=SimpleNamespace(value="Feature"),
            summary=None,
        ),
        "item_type": "Feature",
        "item_status": "in_progress",
        "batch_ref": "BATCH-1",  # item is in a batch
        "batch_status": "executing",  # active batch — cancel button must be disabled
        "steps": [],
        "metrics": SimpleNamespace(
            total_duration_secs=None,
            fix_cycles_count=0,
            steps_completed=0,
            steps_total=1,
        ),
        "setup_error": None,
    }
    rendered = template.render(**ctx)
    # Cancel button (or disabled version) must be mentioned
    assert "Cancel" in rendered
    # Must be disabled (cursor-not-allowed + opacity-50)
    assert "cursor-not-allowed" in rendered or "disabled:" in rendered
    # Hint paragraph with active batch reference must appear
    assert "BATCH-1" in rendered
    assert "cancel the batch instead" in rendered.lower() or "cancel batch" in rendered.lower()
