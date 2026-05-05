"""I-00070 clipboard fallback — Playwright browser test.

AC1 (non-secure context): The Copy paste prompt button must work and show
"Copied" feedback when navigator.clipboard.writeText is unavailable
(plain HTTP on a non-localhost hostname like iw-dev-01).

AC2 (no regression): No TypeError in console when button is clicked in any
access mode.

Marked @pytest.mark.browser — run with:
    uv run pytest tests/dashboard/browser/test_i00070_clipboard_fallback.py -m browser -v
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.browser

_EVAL_RESULT_RE = re.compile(r"###\s*Result\s*\n(?P<value>.*?)(?:\n###\s+|\Z)", re.DOTALL)
_SNAPSHOT_LINK_RE = re.compile(r"\[Snapshot\]\((?P<path>[^)]+\.yml)\)")


def _snap(session: str) -> str:
    """Capture a snapshot and inline its YAML body so callers can grep it."""
    out = subprocess.check_output(["playwright-cli", f"-s={session}", "snapshot"], text=True)
    match = _SNAPSHOT_LINK_RE.search(out)
    if not match:
        return out
    yml_path = Path(match.group("path"))
    if not yml_path.is_absolute():
        yml_path = Path.cwd() / yml_path
    body = yml_path.read_text(encoding="utf-8") if yml_path.is_file() else ""
    return out + "\n" + body


def _eval(session: str, code: str) -> str:
    """Evaluate JS in the page and return the result value as a string."""
    stripped = code.lstrip()
    if stripped.startswith(("() =>", "function")):
        pass
    elif ";" in code:
        code = f"() => {{ {code} }}"
    else:
        code = f"() => ({code})"
    try:
        out = subprocess.check_output(
            ["playwright-cli", f"-s={session}", "eval", code],
            text=True,
            timeout=20,
        )
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    match = _EVAL_RESULT_RE.search(out)
    if not match:
        return out.strip()
    return match.group("value").strip()


def _click(session: str, selector: str) -> None:
    """Click an element by CSS selector via JS."""
    _eval(
        session, f"() => {{ const el = document.querySelector({selector!r}); if (el) el.click(); }}"
    )


# ---------------------------------------------------------------------------
# Helpers shared across tests
# ---------------------------------------------------------------------------


def _start_browser_session(dashboard_url: str, project_id: str, item_id: str) -> str:
    """Open the item detail page and switch to the Execution Report tab.

    Returns the playwright-cli session name.
    """
    session = f"i00070-clipboard-{os.getpid()}"
    # Navigate to the Execution Report tab directly via htmx URL
    url = f"{dashboard_url}/project/{project_id}/item/{item_id}/tab/execution-report"
    subprocess.run(
        ["playwright-cli", f"-s={session}", "open", url],
        check=True,
        capture_output=True,
        timeout=30,
    )
    return session


def _close_browser_session(session: str) -> None:
    subprocess.run(
        ["playwright-cli", f"-s={session}", "close"],
        capture_output=True,
        timeout=10,
    )


def _wait_for_selector(session: str, selector: str, timeout_secs: float = 5.0) -> bool:
    """Poll the DOM until an element matching selector is found or timeout."""
    deadline = time.monotonic() + timeout_secs
    while time.monotonic() < deadline:
        result = _eval(session, f"document.querySelector({selector!r}) !== null")
        if result == "true":
            return True
        time.sleep(0.2)
    return False


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def dashboard_url(dashboard_server) -> str:
    """The base URL of the test dashboard server."""
    return dashboard_server


@pytest.fixture
def test_item_session(
    dashboard_url: str,
    db_session,
    test_project,
    tmp_path,
) -> tuple[str, str, str]:
    """Create a work item with a self_assess step and open its Execution Report tab.

    Returns a tuple of (session, project_id, item_id).
    """
    # Import here to avoid early collection errors (dashboard dependencies
    # require testcontainer db_session in scope).
    import json
    from datetime import UTC, datetime

    from orch.db.models import (
        RunStatus,
        StepRun,
        StepStatus,
        StepType,
        WorkflowStep,
        WorkItem,
        WorkItemPhase,
        WorkItemStatus,
        WorkItemType,
    )

    item = WorkItem(
        project_id=test_project.id,
        id="F-00070",
        title="I-00070 Clipboard Fallback Test",
        type=WorkItemType.Feature,
        status=WorkItemStatus.completed,
        phase=WorkItemPhase.active,
        design_doc_search="",
    )
    db_session.add(item)

    step = WorkflowStep(
        project_id=test_project.id,
        work_item_id=item.id,
        step_id="S03",
        step_number=3,
        step_type=StepType.self_assess,
        agent_label="SelfAssess",
        opencode_agent="self-assess-impl",
        status=StepStatus.completed,
    )
    db_session.add(step)
    db_session.flush()

    work_dir = tmp_path / "ai-dev" / "work" / item.id
    reports_dir = work_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    report_file = reports_dir / f"{item.id}_self_assess_report.md"
    report_file.write_text("# Narrative", encoding="utf-8")

    findings_file = reports_dir / f"{item.id}_self_assess_findings.json"
    findings_file.write_text(
        json.dumps(
            {
                "narrative_md": "# Test",
                "findings": [
                    {
                        "severity": "HIGH",
                        "class": "Process",
                        "target": "iw-ai-core",
                        "title": "Agent re-read files repeatedly",
                        "recommendation": "Add a summarisation step",
                        "paste_prompt": "/iw-new-incident title='Agent re-reads same files'",
                        "evidence": [],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    step_run = StepRun(
        step_id=step.id,
        run_number=1,
        status=RunStatus.completed,
        started_at=datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
        completed_at=datetime(2025, 1, 1, 10, 1, 0, tzinfo=UTC),
        duration_secs=60.0,
        report_file=str(report_file),
    )
    db_session.add(step_run)
    db_session.commit()

    session = _start_browser_session(dashboard_url, test_project.id, item.id)
    try:
        yield session, test_project.id, item.id
    finally:
        _close_browser_session(session)


# ---------------------------------------------------------------------------
# AC1 — RED->GREEN: fallback branch must copy and show "Copied" feedback
# ---------------------------------------------------------------------------


class TestAC1NonSecureClipboardFallback:
    """AC1: button must work via fallback when clipboard API is unavailable."""

    def test_i00070_button_works_when_clipboard_api_unavailable(
        self,
        test_item_session: tuple[str, str, str],
    ) -> None:
        """RED->GREEN: Without the S01 fix the button silently fails.

        After S01 the button uses window.iwClipboard.copy which falls back to
        textarea+execCommand when navigator.clipboard is unavailable. The fallback
        path writes to the clipboard AND sets the button label to "Copied".
        """
        session, project_id, item_id = test_item_session

        def _capture_console() -> None:
            # Use page.on console capture via a JS snippet that stores messages
            _eval(
                session,
                "() => { "
                "  if (!window._capturedConsole) window._capturedConsole = []; "
                "  var orig = console.error.bind(console); "
                "  console.error = function() { "
                "    var args = Array.prototype.slice.call(arguments); "
                "    window._capturedConsole.push(args.map(String).join(' ')); "
                "    orig.apply(console, arguments); "
                "  }; "
                "}",
            )

        _capture_console()

        # Wait for the "Copy paste prompt" button to appear in the DOM
        found = _wait_for_selector(
            session, 'button:has-text("Copy paste prompt")', timeout_secs=8.0
        )
        assert found, (
            "I-00070 AC1: 'Copy paste prompt' button not found in the execution report. "
            "Check that the self_assess step with findings is rendering correctly."
        )

        # Strip the secure-context clipboard API to simulate iw-dev-01 plain-HTTP access.
        # This exactly mirrors the bug scenario: isSecureContext=false and
        # navigator.clipboard is undefined.
        _eval(
            session,
            "Object.defineProperty(window, 'isSecureContext', "
            "{ value: false, configurable: true });",
        )
        _eval(session, "delete navigator.clipboard;")

        # Sanity: verify the browser environment now matches iw-dev-01 access mode
        has_clipboard = _eval(session, "typeof navigator.clipboard !== 'undefined'")
        is_secure = _eval(session, "window.isSecureContext === true")
        assert has_clipboard == "false", (
            f"I-00070 AC1 sanity: navigator.clipboard should be undefined, got {has_clipboard!r}"
        )
        assert is_secure == "false", (
            f"I-00070 AC1 sanity: isSecureContext should be false, got {is_secure!r}"
        )

        # Act: click the Copy paste prompt button
        _click(session, 'button:has-text("Copy paste prompt")')

        # Assert (semantic correctness): the helper must surface "Copied" feedback.
        # The iwClipboard.copy() sets button.textContent = 'Copied' on success.
        copied_found = _wait_for_selector(session, 'button:has-text("Copied")', timeout_secs=3.0)
        assert copied_found, (
            "I-00070 AC1: After clicking 'Copy paste prompt' with clipboard API unavailable, "
            "the button did not show 'Copied' feedback. "
            "The fallback branch (textarea+execCommand) is likely not working, "
            "or the feedback label is not being set."
        )

        # Assert: no TypeError ended up in the console.
        type_errors = _eval(
            session,
            "() => { "
            "  if (!window._capturedConsole) return []; "
            "  return window._capturedConsole.filter(function(m) { "
            "    return m.indexOf('TypeError') !== -1 || m.indexOf('Uncaught') !== -1; "
            "  }); "
            "}",
        )
        # _eval returns a JSON array string
        import json as _json

        try:
            errors_list = _json.loads(type_errors) if type_errors else []
        except Exception:
            errors_list = [type_errors] if type_errors else []
        assert errors_list == [], (
            f"I-00070 AC1: Unexpected console errors detected: {errors_list}. "
            "A TypeError from the onclick handler means the fallback is not wired correctly."
        )


# ---------------------------------------------------------------------------
# AC2 — Regression: no console errors when clipboard API IS available
# ---------------------------------------------------------------------------


class TestAC2SecureContextNoRegression:
    """AC2: when navigator.clipboard.writeText IS available (localhost), button works as before."""

    def test_i00070_no_console_errors_in_secure_context(
        self,
        test_item_session: tuple[str, str, str],
    ) -> None:
        """Secure-context path (localhost) must not throw errors either.

        The S01 fix should be a no-op for secure-context users — the modern
        navigator.clipboard.writeText branch is taken and works as before.
        """
        session, project_id, item_id = test_item_session

        # Set up console error capture
        _eval(
            session,
            "() => { "
            "  if (!window._capturedConsole) window._capturedConsole = []; "
            "  window._origConsoleError = window._origConsoleError || console.error.bind(console); "
            "  console.error = function() { "
            "    var args = Array.prototype.slice.call(arguments); "
            "    window._capturedConsole.push(args.map(String).join(' ')); "
            "    window._origConsoleError.apply(console, arguments); "
            "  }; "
            "}",
        )

        # Wait for the button
        found = _wait_for_selector(
            session, 'button:has-text("Copy paste prompt")', timeout_secs=8.0
        )
        assert found, "I-00070 AC2: 'Copy paste prompt' button not found"

        # Ensure we are in secure context (the default on localhost — no patching needed)

        # Act: click the button
        _click(session, 'button:has-text("Copy paste prompt")')

        # Assert: the button label changes to "Copied"
        copied_found = _wait_for_selector(session, 'button:has-text("Copied")', timeout_secs=3.0)
        assert copied_found, (
            "I-00070 AC2: 'Copied' feedback not shown after clicking 'Copy paste prompt' "
            "in secure context (localhost). The modern clipboard branch may be broken."
        )

        # Assert: no TypeErrors in console
        type_errors = _eval(
            session,
            "() => { "
            "  if (!window._capturedConsole) return []; "
            "  return window._capturedConsole.filter(function(m) { "
            "    return m.indexOf('TypeError') !== -1 || m.indexOf('Uncaught') !== -1; "
            "  }); "
            "}",
        )
        import json as _json

        try:
            errors_list = _json.loads(type_errors) if type_errors else []
        except Exception:
            errors_list = [type_errors] if type_errors else []
        assert errors_list == [], f"I-00070 AC2: Unexpected console errors: {errors_list}"
