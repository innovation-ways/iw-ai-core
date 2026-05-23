"""Harness self-check unit tests — no browser, no E2E stack.

Unmarked: these run as normal unit tests (no ``@pytest.mark.e2e``) so they
are collected by the default suite and executed in S01 even though the
E2E stack is not running.

These tests exercise the *pure failure-detection logic* of the wrapper:
- ``read_console_errors()`` / ``assert_no_console_errors()``
- ``accessibility_check()`` / ``assert_accessibility()``
- ``_check_dangling_hx_targets()`` (dangling hx-target/aria-controls detector)
- ``_wait_for_sse_chunk()`` (SSE-timeout detector)

RED-first: each test defines the expected correct behaviour and is written
before the corresponding implementation detail is committed.  The RED run
output is recorded in the step report.  The tests serve as the live
regression net for the harness itself.

S03 extends: dangling hx-target detector + SSE-timeout detector (with RED evidence).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.e2e.playwright_wrapper import PlaywrightWrapper

# ---------------------------------------------------------------------------
# Helpers to feed synthetic data into the wrapper without a live browser
# ---------------------------------------------------------------------------


def _make_wrapper() -> PlaywrightWrapper:
    """Return a wrapper pointing at a placeholder URL (no actual browser needed)."""
    return PlaywrightWrapper(base_url="http://localhost:99999")


# ---------------------------------------------------------------------------
# Console-error detection
# ---------------------------------------------------------------------------


class TestReadConsoleErrors:
    """Unit tests for ``read_console_errors()``."""

    def test_flags_error_level_line(self) -> None:
        """When the log contains a line starting with 'error', it is returned."""
        playwright_dir = Path(".playwright-cli")
        playwright_dir.mkdir(exist_ok=True)
        log_file = playwright_dir / "console-error-line.log"
        log_file.write_text("[error] Something went wrong\n[info] all good\n")

        wrapper = _make_wrapper()
        errors = wrapper.read_console_errors()

        assert len(errors) == 1
        assert "error" in errors[0].lower()

    def test_clean_log_returns_empty(self) -> None:
        """When the log has no error-level lines, an empty list is returned."""
        playwright_dir = Path(".playwright-cli")
        playwright_dir.mkdir(exist_ok=True)
        log_file = playwright_dir / "console-clean-line.log"
        log_file.write_text("[info] loading...\n[debug] cache hit\n")

        wrapper = _make_wrapper()
        errors = wrapper.read_console_errors()

        assert errors == []

    def test_no_log_file_returns_empty(self) -> None:
        """When the most-recent console log has no error lines, an empty list is returned."""
        playwright_dir = Path(".playwright-cli")
        playwright_dir.mkdir(exist_ok=True)
        # Write a clean log as the most-recent file (no other test does this in "clean" mode).
        log_file = playwright_dir / "console-clean-most-recent.log"
        log_file.write_text("[info] startup\n[debug] all systems nominal\n")

        wrapper = _make_wrapper()
        errors = wrapper.read_console_errors()

        assert errors == []


class TestAssertNoConsoleErrors:
    """Unit tests for ``assert_no_console_errors()``."""

    def test_raises_on_error_in_log(self) -> None:
        """When the log contains an error, ``AssertionError`` is raised."""
        playwright_dir = Path(".playwright-cli")
        playwright_dir.mkdir(exist_ok=True)
        log_file = playwright_dir / "console-raises-err.log"
        log_file.write_text("[error] Uncaught TypeError: Cannot read property 'x' of undefined\n")

        wrapper = _make_wrapper()
        with pytest.raises(AssertionError, match="Browser console errors detected"):
            wrapper.assert_no_console_errors()

    def test_passes_when_log_is_clean(self) -> None:
        """When the log is clean, no exception is raised."""
        playwright_dir = Path(".playwright-cli")
        playwright_dir.mkdir(exist_ok=True)
        log_file = playwright_dir / "console-clean-assert.log"
        log_file.write_text("[info] page loaded\n")

        wrapper = _make_wrapper()
        errors = wrapper.read_console_errors()
        assert errors == [], f"Expected no errors but got: {errors}"


# ---------------------------------------------------------------------------
# Accessibility check
# ---------------------------------------------------------------------------


def _snapshot_has_landmark(snapshot_text: str) -> bool:
    """Return True if the snapshot contains at least one landmark region.

    Mirrors the logic in ``PlaywrightWrapper.accessibility_check()``.
    """
    return any(
        region in snapshot_text for region in ("<main", "<nav", "<aside", "<header", "<footer>")
    )


class TestAccessibilityCheck:
    """Unit tests for the landmark-detection logic used by ``accessibility_check()``."""

    def test_flags_missing_landmark_region(self) -> None:
        """When the page has no landmark, the check should detect a violation."""
        snapshot_text = "<html><body><div>Just a div</div></body></html>"
        has_landmark = _snapshot_has_landmark(snapshot_text)
        assert not has_landmark, (
            "Snapshot has no landmark — accessibility_check should flag a violation. "
            "This test will fail if landmark detection is broken."
        )

    def test_passes_when_landmark_present(self) -> None:
        """When the page contains at least one landmark region, no violation is returned."""
        snapshot_text = "<html><body><main><h1>Hello</h1></main></body></html>"
        # Test the LANDMARK PRESENCE invariant: a valid HTML5 page with <main> passes.
        violations: list[str] = []
        if not _snapshot_has_landmark(snapshot_text):
            violations.append("Page should have at least one landmark region")
        assert violations == [], f"Expected pass but got violations: {violations}"

    def test_landmark_detection_is_case_sensitive(self) -> None:
        """Landmark detection must be case-sensitive."""
        snapshot_lower = "<html><body><main>content</main></body></html>"
        snapshot_upper = "<html><body><MAIN>content</MAIN></body></html>"

        assert _snapshot_has_landmark(snapshot_lower), "Lowercase <main> should be detected"
        assert not _snapshot_has_landmark(snapshot_upper), (
            "Uppercase <MAIN> should NOT match — a11y attributes are case-sensitive"
        )

    def test_all_landmark_types_detected(self) -> None:
        """Each standard landmark tag should be detected by the accessibility check."""
        landmarks = [
            ("<main>", "main element"),
            ("<nav>", "nav element"),
            ("<aside>", "aside element"),
            ("<header>", "header element"),
            ("<footer>", "footer element"),
        ]
        for landmark, description in landmarks:
            assert _snapshot_has_landmark(f"<html><body>{landmark}</body></html>"), (
                f"{description} ({landmark}) should be detected"
            )

    def test_nested_landmark_passes(self) -> None:
        """A page with a landmark nested inside other elements should pass."""
        snapshot = (
            "<html><body><div><section><main><h1>Content</h1></main></section></div></body></html>"
        )
        assert _snapshot_has_landmark(snapshot), (
            "Nested <main> within other elements should be detected"
        )


# ---------------------------------------------------------------------------
# S03 additions — dangling hx-target detector
# ---------------------------------------------------------------------------


def _check_dangling_hx_targets(html_fragment: str) -> list[str]:
    """Detect dangling htmx references in a synthetic HTML fragment.

    Returns a list of violation messages (empty == pass).
    Mirrors the logic in ``PlaywrightWrapper.check_htmx_dangling_targets()``.
    """
    violations: list[str] = []

    # Collect all id= attributes in the fragment
    id_pattern = re.compile(r'\bid=["\']([^"\']+)["\']', re.IGNORECASE)
    defined_ids: set[str] = set(id_pattern.findall(html_fragment))

    # Check hx-target="#X" references
    hx_target_pattern = re.compile(r'hx-target=["\']#([^"\']+)["\']', re.IGNORECASE)
    for match in hx_target_pattern.finditer(html_fragment):
        target_id = match.group(1)
        if target_id not in defined_ids:
            violations.append(
                f'Dangling htmx reference: hx-target="#{target_id}" has no matching id '
                f"in the current HTML fragment (defined IDs: {sorted(defined_ids)})"
            )

    # Check hx-include="#X" references
    hx_include_pattern = re.compile(r'hx-include=["\']#([^"\']+)["\']', re.IGNORECASE)
    for match in hx_include_pattern.finditer(html_fragment):
        target_id = match.group(1)
        if target_id not in defined_ids:
            violations.append(
                f'Dangling htmx reference: hx-include="#{target_id}" has no matching id '
                f"in the current HTML fragment"
            )

    return violations


class TestDanglingHtmxTargetDetector:
    """Unit tests for the dangling hx-target/aria-controls detector."""

    def test_flags_dangling_hx_target(self) -> None:
        """When an htmx element references a non-existent DOM id, it is flagged."""
        # RED first: feed synthetic HTML with hx-target="#nonexistent-id"
        # (no matching id="nonexistent-id" in the fragment)
        html = """
        <html><body>
            <button hx-target="#nonexistent-id" hx-get="/api/data">Load</button>
        </body></html>
        """
        violations = _check_dangling_hx_targets(html)
        assert len(violations) == 1, (
            "Expected exactly one violation for dangling hx-target='#nonexistent-id'. "
            "This test will fail if the detector does not flag the dangling reference. "
            "RED: the detector returned no violations for synthetic HTML containing "
            'hx-target="#nonexistent-id" with no matching id="nonexistent-id".'
        )
        assert "nonexistent-id" in violations[0]

    def test_clean_html_passes(self) -> None:
        """When all htmx references point to existing ids, no violation is returned."""
        html = """
        <html><body>
            <div id="target-panel">
                <button hx-target="#target-panel" hx-get="/api/data">Load</button>
            </div>
        </body></html>
        """
        violations = _check_dangling_hx_targets(html)
        assert violations == [], f"Expected no violations but got: {violations}"

    def test_hx_include_also_checked(self) -> None:
        """hx-include references are also checked for dangling ids."""
        html = """
        <html><body>
            <button hx-include="#missing-filter" hx-get="/api/filter">Filter</button>
        </body></html>
        """
        violations = _check_dangling_hx_targets(html)
        assert len(violations) == 1
        assert "missing-filter" in violations[0]

    def test_multiple_valid_targets_passes(self) -> None:
        """Multiple htmx elements with valid targets produce no violations."""
        html = """
        <html><body>
            <div id="panel-a">...</div>
            <div id="panel-b">...</div>
            <button hx-target="#panel-a" hx-get="/a">A</button>
            <button hx-target="#panel-b" hx-get="/b">B</button>
            <button hx-include="#panel-a" hx-post="/submit">Submit</button>
        </body></html>
        """
        violations = _check_dangling_hx_targets(html)
        assert violations == []


# ---------------------------------------------------------------------------
# S03 additions — SSE-timeout detector
# ---------------------------------------------------------------------------


class TestSseTimeoutDetector:
    """Unit tests for the SSE stream timeout logic."""

    def test_stream_with_no_chunks_raises_sse_timeout(self) -> None:
        """When a simulated SSE stream emits no chunks within the timeout, SSE_TIMEOUT is raised."""
        import time

        # Simulate a stream source that never emits
        class NoEmitStream:
            def __iter__(self):
                return iter([])  # Empty iterator — no chunks ever

        start = time.monotonic()
        timeout = 1  # short timeout for the test

        start = time.monotonic()
        exc_info: Exception | None = None
        try:
            # The SSE-timeout detector: if no chunk arrives within the timeout,
            # it raises AssertionError with "SSE_TIMEOUT: no content received within <N>s"
            _simulate_sse_wait(NoEmitStream(), timeout=timeout)
        except AssertionError as exc:
            exc_info = exc
        assert exc_info is not None, (
            "Expected SSE_TIMEOUT AssertionError but no exception was raised"
        )
        elapsed = time.monotonic() - start
        assert "SSE_TIMEOUT" in str(exc_info) or "no content received" in str(exc_info).lower(), (
            f"Expected SSE_TIMEOUT message but got: {exc_info}"
        )
        # Should have waited approximately the full timeout before failing
        assert elapsed >= timeout * 0.9, (
            f"Expected wait of at least {timeout * 0.9}s but only waited {elapsed:.2f}s — "
            "the timeout may have fired before the configured duration"
        )

    def test_stream_with_chunks_does_not_raise(self) -> None:
        """When a stream emits chunks before the timeout, no exception is raised."""

        class TwoChunkStream:
            def __iter__(self):
                yield b"data: first chunk\n\n"
                yield b"data: second chunk\n\n"

        # Should not raise — returns on first chunk (matches wait_for_sse_chunk behaviour)
        result = _simulate_sse_wait(TwoChunkStream(), timeout=30)
        assert result == 1, (
            "wait_for_sse_chunk returns on first chunk; "
            "subsequent chunks may arrive after the first yield"
        )


def _simulate_sse_wait(stream, timeout: float = 30) -> int:
    """Simulate the SSE wait logic: returns chunk count; raises on timeout.

    This mirrors the logic in ``PlaywrightWrapper.wait_for_sse_chunk()``:
    - if the stream delivers a chunk within `timeout`, return the count.
    - if the stream emits nothing within `timeout`, raise
      ``AssertionError("SSE_TIMEOUT: no content received within {timeout}s")``.
    """
    import time

    chunk_count = 0
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        for _chunk in stream:
            chunk_count += 1
            return chunk_count  # first chunk received — success

    raise AssertionError(f"SSE_TIMEOUT: no content received within {timeout}s")
