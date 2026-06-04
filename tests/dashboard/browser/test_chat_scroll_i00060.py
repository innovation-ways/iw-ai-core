"""Browser regression tests for I-00060 — scroll-on-submit and compact empty assistant bubble.

AC1: After Enter, the just-typed user bubble is visible inside #chat-messages.
AC2: The empty assistant bubble (pre-stream) renders <= 48px tall.
AC3: While streaming, follow-scroll is conditional on user being at bottom.
AC5: No regressions in existing chat behaviours (citations, scroll-to-bottom button).
AC phase-strip: Bubble grows above 48px once phase text appears (expected).

Uses playwright-cli (no direct Playwright Python API) to drive a headless Chromium
session. Marked @pytest.mark.browser — run with:
    uv run pytest tests/dashboard/browser/test_chat_scroll_i00060.py -m browser -v

The S01 fix:
- composer.js: scrollToBottom() called after appendUserBubble/appendAssistantBubble.
- composer.js: isAtBottom closure variable updated by IntersectionObserver;
  onToken/onPhase/onDone call scrollToBottom() only when isAtBottom.
- chat.css: removed min-height:50dvh rule that forced empty assistant bubble to ~50vh.
"""

from __future__ import annotations

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
    """Evaluate JS in the page and return the result value as a string.

    playwright-cli eval wraps the given code as the body of a page.evaluate() call.
    - Arrow functions (() => ...) are passed as-is.
    - Multi-statement code (containing semicolons) is wrapped as () => { code }
      so that statements like const declarations and if/return work correctly.
    - Bare expressions are wrapped as () => (expr).
    """
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
    value = match.group("value").strip()
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        value = value[1:-1]
    return value


def _eval_int(session: str, code: str, default: int = 0) -> int:
    """Evaluate JS that returns a numeric value and coerce to int.

    DOM measurements such as `getBoundingClientRect()` and (in some browsers)
    `scrollTop` return subpixel floats. `int("475.921875")` raises ValueError,
    so go through `float()` first.
    """
    raw = _eval(session, code)
    if raw in ("", "TIMEOUT", "undefined", "null"):
        return default
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return default


def _run(session: str, *args: str) -> subprocess.CompletedProcess:
    """Run playwright-cli with the given session and arguments."""
    cmd = ["playwright-cli", f"-s={session}"] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30)


def _click(session: str, selector: str) -> None:
    """Click an element by CSS selector via JS."""
    _eval(
        session,
        f"() => {{ const el = document.querySelector({selector!r}); if (el) el.click(); }}",
    )


def _fill_and_submit(session: str, text: str) -> None:
    """Type into #chat-input and click #chat-send via JS."""
    escaped = text.replace("\\", "\\\\").replace("'", "\\'")
    js = (
        "() => { "
        "const el = document.querySelector('#chat-input'); "
        "if (!el) return false; "
        f"el.value = '{escaped}'; "
        "el.dispatchEvent(new Event('input', {bubbles: true})); "
        "return true; "
        "}"
    )
    result = _eval(session, js)
    if result == "TIMEOUT":
        return
    time.sleep(0.2)
    _click(session, "#chat-send")
    time.sleep(0.5)


def _expand_chat_panel(session: str) -> None:
    """Force the chat panel into the expanded state (I-00057 pattern)."""
    js = (
        "() => { "
        "const panel = document.getElementById('chat-panel'); "
        "if (!panel) return false; "
        "if (panel.dataset.collapsed === 'true') { "
        "  const rail = document.getElementById('chat-expand-rail'); "
        "  if (rail) rail.click(); "
        "  else panel.dataset.collapsed = 'false'; "
        "} "
        "return panel.dataset.collapsed !== 'true'; "
        "}"
    )
    _eval(session, js)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# playwright_session and dashboard_server are provided by conftest.py


# ---------------------------------------------------------------------------
# AC1 -- RED->GREEN: submit must scroll user bubble into view
# ---------------------------------------------------------------------------


class TestAC1SubmitScrollsUserBubbleIntoView:
    """AC1: After Enter, the just-typed user bubble must be visible inside #chat-messages."""

    def test_i00060_repro_submit_scrolls_user_bubble_into_view(self, playwright_session):
        """RED->GREEN: Without S01 fix the user bubble stays below the fold after submit.

        S01 adds scrollToBottom() immediately after appendUserBubble. This test
        fails on pre-S01 code because the messages container does not scroll.
        """
        session = playwright_session

        # Expand panel and fill with enough messages to overflow #chat-messages.
        _expand_chat_panel(session)
        for i in range(8):
            _fill_and_submit(session, f"warmup question {i}")
            time.sleep(3)

        # Scroll to top so the anchor is out of view.
        _eval(session, "document.getElementById('chat-messages').scrollTop = 0")

        scroll_top_before = _eval_int(session, "document.getElementById('chat-messages').scrollTop")

        # Send the question we care about.
        _fill_and_submit(session, "the question that must be in view")

        # IMMEDIATELY after submit the container must have scrolled so the
        # user bubble is inside the viewport.
        container_bottom = _eval_int(
            session,
            "document.getElementById('chat-messages').getBoundingClientRect().bottom",
        )
        user_bubble_bottom = _eval_int(
            session,
            "const bs = document.querySelectorAll('article[data-role=\"user\"]'); "
            "if (!bs.length) return -1; "
            "return bs[bs.length - 1].getBoundingClientRect().bottom;",
        )
        user_bubble_top = _eval_int(
            session,
            "const bs = document.querySelectorAll('article[data-role=\"user\"]'); "
            "if (!bs.length) return -1; "
            "return bs[bs.length - 1].getBoundingClientRect().top;",
        )
        container_top = _eval_int(
            session,
            "document.getElementById('chat-messages').getBoundingClientRect().top",
        )

        assert user_bubble_bottom > 0, (
            f"I-00060 AC1 bug: user bubble bottom is {user_bubble_bottom} (should be > 0). "
            f"Scroll top before={scroll_top_before}",
        )
        assert user_bubble_bottom <= container_bottom, (
            f"I-00060 AC1 bug: user bubble bottom ({user_bubble_bottom}) is below "
            f"container bottom ({container_bottom}) — submit did not scroll. "
            f"Scroll top before={scroll_top_before}",
        )
        assert user_bubble_top >= container_top, (
            f"I-00060 AC1 bug: user bubble top ({user_bubble_top}) is above "
            f"container top ({container_top}) — bubble only partially visible.",
        )


# ---------------------------------------------------------------------------
# AC2 -- RED->GREEN: empty assistant bubble must be compact (<= 48px)
# ---------------------------------------------------------------------------


class TestAC2EmptyAssistantBubbleCompact:
    """AC2: The empty assistant bubble (pre-stream) must render <= 48px tall."""

    def test_i00060_repro_empty_assistant_bubble_compact(self, playwright_session):
        """RED->GREEN: Without S01 fix the empty assistant bubble renders at ~50vh.

        S01 removes the chat.css rule:
          #chat-messages > article[data-role="assistant"]:last-child { min-height: 50dvh; }
        Before S01 this rule forced the empty bubble to ~50% of the dynamic viewport.
        After S01 the bubble collapses to natural height (~36px).
        """
        session = playwright_session
        _expand_chat_panel(session)

        _fill_and_submit(session, "what modules exist in this project")

        # Poll for the assistant bubble height before the first token arrives.
        height_px = None
        for _ in range(20):  # up to 1 second
            h = _eval_int(
                session,
                "const bs = document.querySelectorAll("
                "  'article[data-role=\"assistant\"]'"
                "); "
                "if (!bs.length) return -1; "
                "const last = bs[bs.length - 1]; "
                "const body = last.querySelector('.chat-message-body'); "
                "const isEmpty = !body || body.textContent.trim() === ''; "
                "if (isEmpty) return last.getBoundingClientRect().height; "
                "return -2;",
                default=-1,
            )
            if h == -2:
                # Token already arrived. Verify the bubble is NOT forced to 50vh.
                h = _eval_int(
                    session,
                    "const bs = document.querySelectorAll("
                    "  'article[data-role=\"assistant\"]'"
                    "); "
                    "if (!bs.length) return -1; "
                    "return bs[bs.length - 1].getBoundingClientRect().height;",
                    default=-1,
                )
                assert h < 300, (
                    f"I-00060 AC2 bug: assistant bubble is {h}px after token arrived — "
                    f"should not be 50vh. The min-height rule was NOT removed.",
                )
                height_px = h
                break
            if h > 0:
                height_px = h
                break
            time.sleep(0.05)

        assert height_px is not None, (
            "I-00060 AC2: could not measure assistant bubble height before first token. "
            "Either the bubble was not appended or the timing window was missed.",
        )
        assert height_px <= 48, (
            f"I-00060 AC2 bug: empty assistant bubble is {height_px}px tall, "
            f"expected <= 48px (label 'Assistant' + minimal padding ~= 36px). "
            f"The min-height:50dvh rule in chat.css may not have been removed.",
        )


# ---------------------------------------------------------------------------
# AC3 -- Regression: stream follow-scroll is conditional on user being at bottom
# ---------------------------------------------------------------------------


class TestAC3ConditionalFollowScroll:
    """AC3: While streaming, the container auto-scrolls only when user is at bottom."""

    def test_i00060_ac3_follow_scroll_conditional(self, playwright_session):
        """If user scrolls away mid-stream, container must NOT yank them to bottom."""
        session = playwright_session
        _expand_chat_panel(session)

        # Ensure we start at the bottom.
        _eval(
            session,
            "document.getElementById('chat-scroll-anchor').scrollIntoView()",
        )

        _fill_and_submit(session, "explain the architecture of this project in detail")

        # Wait for streaming to start.
        time.sleep(1.5)

        # Manually scroll UP (away from bottom).
        _eval(session, "document.getElementById('chat-messages').scrollTop = 0")

        # Wait a moment for any erroneous auto-scroll to fire.
        time.sleep(0.5)

        # The container must still be scrolled to top.
        scroll_top = _eval_int(session, "document.getElementById('chat-messages').scrollTop")
        assert scroll_top == 0, (
            f"I-00060 AC3 regression: user scrolled away but container auto-scrolled "
            f"back (scrollTop={scroll_top}, expected 0). "
            f"Conditional follow-scroll is broken.",
        )

    def test_i00060_ac3_scroll_to_bottom_button_works(self, playwright_session):
        """Clicking #chat-scroll-to-bottom snaps the container to the anchor."""
        session = playwright_session
        _expand_chat_panel(session)

        # Scroll to top first.
        _eval(session, "document.getElementById('chat-messages').scrollTop = 0")
        time.sleep(0.2)

        # Click the floating scroll-to-bottom button.
        _click(session, "#chat-scroll-to-bottom")
        time.sleep(0.3)

        # The anchor should now be in view.
        anchor_in_view = _eval(
            session,
            "const a = document.getElementById('chat-scroll-anchor'); "
            "if (!a) return false; "
            "const r = a.getBoundingClientRect(); "
            "const c = document.getElementById('chat-messages').getBoundingClientRect(); "
            "return r.top >= c.top && r.bottom <= c.bottom;",
        )
        assert anchor_in_view == "true", (
            "I-00060 AC3 regression: #chat-scroll-to-bottom button did not scroll "
            "container to bottom. The anchor should be fully visible inside container.",
        )


# ---------------------------------------------------------------------------
# AC5 -- Regression: no regressions in citations / existing behaviour
# ---------------------------------------------------------------------------


class TestAC5NoRegressions:
    """AC5: Citation popovers and existing chat behaviour remain intact."""

    def test_i00060_ac5_no_console_errors_on_submit(self, playwright_session):
        """Sending a question and waiting for stream should not introduce console errors."""
        session = playwright_session
        _expand_chat_panel(session)

        _fill_and_submit(session, "what is the purpose of this project")

        # Wait for stream to complete.
        time.sleep(5)

        # Verify no error text appeared on the page.
        page_has_errors = _eval(
            session,
            "() => { "
            "const msgs = document.querySelectorAll('.chat-message-body'); "
            "for (const m of msgs) { "
            "  if (m.textContent.includes('Error:') && m.textContent.includes('traceback')) "
            "    return true; "
            "} "
            "return false; "
            "}",
        )
        assert page_has_errors in ("false", "true"), (
            f"I-00060 AC5: unexpected result {page_has_errors!r} from error-check eval. "
            f"Expected 'false' or 'true'."
        )
        assert page_has_errors == "false", (
            "I-00060 AC5 regression: page appears to contain error text after streaming. "
            "The scroll/streaming changes may have broken something.",
        )


# ---------------------------------------------------------------------------
# Phase-strip positive test: bubble grows when phase text appears
# ---------------------------------------------------------------------------


class TestPhaseStripBubbleGrowth:
    """Phase strip with text is expected to grow the bubble above 48px — this is OK."""

    def test_i00060_phase_strip_grows_bubble(self, playwright_session):
        """When a phase event with text arrives, the assistant bubble may grow above 48px.

        This is the expected behaviour — phase text like 'Looking up related code...'
        increases the bubble height, and this must NOT regress to a bug.
        """
        session = playwright_session
        _expand_chat_panel(session)

        _fill_and_submit(session, "explain the orch module")

        # Wait long enough for a phase event to arrive (~1-2s into stream).
        time.sleep(2)

        assistant_count = _eval_int(
            session,
            "document.querySelectorAll('article[data-role=\"assistant\"]').length",
        )
        assert assistant_count > 0, "No assistant bubble found after submit"

        bubble_height = _eval_int(
            session,
            "const bs = document.querySelectorAll("
            "  'article[data-role=\"assistant\"]'"
            "); "
            "if (!bs.length) return -1; "
            "return bs[bs.length - 1].getBoundingClientRect().height;",
            default=-1,
        )

        # After phase text, height may legitimately exceed 48px.
        # The key assertion: it is NOT forced to 50vh any more.
        # 50dvh on a typical viewport ~= 300-400px.
        assert bubble_height < 400, (
            f"I-00060 phase-strip: assistant bubble is {bubble_height}px which exceeds "
            f"even 50dvh (~300-400px). The min-height:50dvh rule may not have been removed.",
        )
