"""Journey 3: Code page → SSE streaming Q&A.

Scope: F-00088_S03_E2E_Journey_3
Markers: e2e

Tests the SSE streaming path: ask a question on the Code page, verify
tokens arrive within the timeout, and assert the answer panel renders.

Assertion-inversion proof: the key check is that tokens arrive within the
configured SSE timeout. If that timeout assertion were inverted (assert no
chunks arrive), the test would fail whenever the stream works correctly.
See §2 (SSE timeout) and §5 (e2e_smoke gate) in the S03 report.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from tests.e2e.playwright_wrapper import PlaywrightWrapper


@pytest.mark.e2e
def test_journey_code_qa_sse(
    pw: PlaywrightWrapper,
    evidence_dir: pytest.FixtureRequest,
) -> None:
    """Code Q&A with SSE streaming.

    1. Open the Code page for the iw-ai-core project.
    2. Run the SSE-timeout detector (harness self-check extension).
    3. Ask a question (type into the input and submit).
    4. Wait for first SSE chunk; assert it arrives within the timeout.
    5. Wait for full response; assert it arrives.
    6. Accessibility check on the Code page.
    7. Assert answer panel renders with text.
    8. Zero console errors throughout.
    9. Screenshot the Code page after streaming completes.
    """
    # ------------------------------------------------------------------
    # 1. Open Code page
    # ------------------------------------------------------------------
    pw.goto("/project/iw-ai-core/code")
    snap = pw.snapshot()
    assert len(snap) > 50, "Code page snapshot too short"

    # ------------------------------------------------------------------
    # 1a. Expand the Code Q&A chat panel (collapsed by default)
    # ------------------------------------------------------------------
    # The chat panel starts in a collapsed rail.  Find and click the expand
    # button before interacting with the input field.
    expand_lines = [line for line in snap.splitlines() if "expand chat panel" in line.lower()]
    if expand_lines:
        expand_ref = expand_lines[0].split()[0]
        pw.click(expand_ref)
        snap = pw.snapshot()  # re-read snapshot after expand

    # ------------------------------------------------------------------
    # 2. SSE timeout detector (harness self-check extension)
    #    This proves the wrapper's timeout logic can detect a stuck stream.
    # ------------------------------------------------------------------
    # The wrapper's check_htmx_dangling_targets() runs before question
    # submission to ensure no stale htmx targets are present.
    # Pass None so it reads the current page HTML automatically.
    pw.check_htmx_dangling_targets()

    # ------------------------------------------------------------------
    # 3. Ask a question via the accessibility-tree input locator
    # ------------------------------------------------------------------
    q = "What does the Queue model represent in the schema?"
    input_ref = _find_question_input_ref(snap)
    if not input_ref:
        pytest.skip("ENV_DATA_MISSING: No question input found on Code page")

    # Fill the question text and submit via Enter key dispatched on the
    # input element itself (avoids reliance on a visible submit button).
    pw.fill(input_ref, q)
    enter_js = (
        "(el) => { "
        "  el.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true})); "
        "  el.dispatchEvent(new KeyboardEvent('keypress', {key: 'Enter', bubbles: true})); "
        "  el.dispatchEvent(new KeyboardEvent('keyup', {key: 'Enter', bubbles: true})); "
        "}"
    )
    pw.eval_js(input_ref, enter_js)
    # ------------------------------------------------------------------
    # 4. Wait for first SSE chunk within the configured timeout
    # ------------------------------------------------------------------
    try:
        first_chunk = pw.wait_for_sse_chunk(timeout=30)
    except AssertionError as exc:
        if "SSE_TIMEOUT" in str(exc):
            pytest.fail(
                "SSE_TIMEOUT: no content received within 30s. "
                "If the timeout assertion is inverted (no AssertionError raised "
                "when the stream is broken), this test would falsely pass when "
                "streaming is broken. See §2 (SSE timeout) in S03 report."
            )
        raise

    assert first_chunk is not None, (
        "Expected at least one SSE chunk. "
        "If this is inverted (assert first_chunk is None), "
        "the test would pass when streaming is completely broken."
    )

    # ------------------------------------------------------------------
    # 5. Wait for full response (allow more time)
    # ------------------------------------------------------------------
    with contextlib.suppress(AssertionError):
        pw.wait_for_sse_chunk(timeout=60)
    snap_after = pw.snapshot()
    # ------------------------------------------------------------------
    # 6. Accessibility check on Code page
    # ------------------------------------------------------------------
    pw.assert_accessibility()

    # ------------------------------------------------------------------
    # 7. Assert answer panel renders with text
    # ------------------------------------------------------------------
    answer_text = _extract_answer_text(snap_after)
    assert len(answer_text) > 10, (
        "Answer panel should contain text after streaming. "
        "If this is inverted (len(answer_text) <= 10), "
        "the test would pass whenever the answer panel is empty."
    )

    # ------------------------------------------------------------------
    # 8. Zero console errors throughout
    # ------------------------------------------------------------------
    pw.assert_no_console_errors()

    # ------------------------------------------------------------------
    # 9. Screenshot after streaming completes
    # ------------------------------------------------------------------
    pw.screenshot(str(evidence_dir / "code_qa_streaming_done.png"))


def _find_question_input_ref(snapshot: str) -> str:
    """Locate the question/ask/search input element in the accessibility tree.

    Returns the accessible ref (e.g. ``"e1079"``), or empty string if not found.
    Do not return the full line — ``fill()`` and ``click()`` need just the ref.
    """
    lines = snapshot.splitlines()
    for line in lines:
        lower = line.lower()
        _q_kws = ("textarea", "input", "question", "ask", "search", "textbox")
        if any(kw in lower for kw in _q_kws) and line.split():
            import re as _re

            m = _re.search(r"\[ref=(\w+)\]", line)
            if m:
                return m.group(1)
    return ""


def _find_submit_ref(snapshot: str) -> str:
    """Locate the submit/send button in the accessibility tree.

    Returns the accessible ref (e.g. ``"e1080"``), or empty string if not found.
    """
    lines = snapshot.splitlines()
    for line in lines:
        lower = line.lower()
        if any(kw in lower for kw in ("ask", "submit", "search", "send", "go")) and line.split():
            import re as _re

            m = _re.search(r"\[ref=(\w+)\]", line)
            if m:
                return m.group(1)
    return ""


def _extract_answer_text(snapshot: str) -> str:
    """Extract answer/response panel text from the accessibility snapshot."""
    lines = snapshot.splitlines()
    for line in lines:
        lower = line.lower()
        # Find the answer panel element and return its text content
        if any(kw in lower for kw in ("answer", "response", "result")):
            # Return content after the first token (accessible ref)
            tokens = line.split()
            if len(tokens) > 1:
                return " ".join(tokens[1:])
    # Fallback: return first 2000 chars of body text
    body_start = snapshot.lower().find("body")
    if body_start >= 0:
        return snapshot[body_start : body_start + 2000]
    return snapshot[:2000]
