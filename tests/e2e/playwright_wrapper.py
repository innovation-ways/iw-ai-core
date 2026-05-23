"""Thin subprocess wrapper around the playwright-cli binary.

ALL browser interactions go through ``playwright-cli`` — never call
``chromium.launch()``, ``agent-browser``, or run ``npx playwright install``.

Binary: ``~/.local/bin/playwright-cli``
Config: ``.playwright/cli.config.json``

Usage::

    wrapper = PlaywrightWrapper(base_url="http://localhost:9900")
    wrapper.open_url("/")
    wrapper.snapshot()          # accessibility tree
    wrapper.click("button#next")
    wrapper.goto("/project/iw-ai-core/queue")

The wrapper manages one browser session (kill-all before open; goto after
first open).  Stale ``.playwright-cli/page-*.png`` and ``.playwright-cli/console-*.log``
files are wiped by the ``conftest.py`` ``pw`` fixture before every test so
each test starts with a clean slate.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

PLAYWRIGHT_CLI = Path.home() / ".local" / "bin" / "playwright-cli"

# Ensure the binary is present at import time so the error is loud and early.
if not PLAYWRIGHT_CLI.exists():
    raise RuntimeError(
        f"playwright-cli binary not found at {PLAYWRIGHT_CLI!s}. "
        "Install it or ensure ~/.local/bin/ is in your PATH."
    )


class PlaywrightWrapper:
    """Browser-automation wrapper via playwright-cli subprocess calls."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    # ------------------------------------------------------------------
    # Internal subprocess helpers
    # ------------------------------------------------------------------

    def _run(
        self,
        args: list[str],
        timeout: int = 30,
    ) -> subprocess.CompletedProcess[str]:
        """Run ``playwright-cli <args>`` and return the completed process."""
        return subprocess.run(
            [str(PLAYWRIGHT_CLI), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,  # callers assert on returncode
        )

    def _run_checked(
        self,
        args: list[str],
        timeout: int = 30,
    ) -> subprocess.CompletedProcess[str]:
        """Run ``playwright-cli <args>`` and raise on non-zero exit."""
        result = self._run(args, timeout=timeout)
        if result.returncode != 0:
            raise RuntimeError(
                f"playwright-cli {' '.join(args)!r} failed (exit {result.returncode}):\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )
        return result

    # ------------------------------------------------------------------
    # Browser session lifecycle
    # ------------------------------------------------------------------

    def kill_all(self) -> None:
        """Kill all browser sessions."""
        self._run(["kill-all"], timeout=10)

    def open_url(self, url: str) -> None:
        """Launch a fresh browser and open ``url``.

        ``open_url`` wipes browser state (localStorage / cookies).  After
        the first ``open_url`` use ``goto`` for all subsequent navigations
        to preserve session state.
        """
        target = self._resolve(url)
        self._run_checked(["open", target], timeout=30)

    def goto(self, url: str) -> None:
        """Navigate to ``url`` in the existing browser session."""
        target = self._resolve(url)
        self._run_checked(["goto", target], timeout=30)

    def _resolve(self, path_or_url: str) -> str:
        """Normalise a path-or-URL to an absolute URL string."""
        if path_or_url.startswith(("http://", "https://")):
            return path_or_url
        return f"{self.base_url}{path_or_url}"

    def _resolve_snap_file(self, relative_path: str) -> Path:
        """Resolve a playwright-cli snapshot .yml path to an absolute Path.

        playwright-cli writes ``[Snapshot](.playwright-cli/page-<ts>.yml)`` —
        a path relative to the CWD where the browser CLI was invoked.
        ``relative_path`` starts with ``.playwright-cli/``; we strip that
        prefix so the returned Path points to the actual file under
        ``.playwright-cli/<name>.yml`` in the worktree root.
        """
        relative_path = relative_path.lstrip("./")
        if relative_path.startswith(".playwright-cli/"):
            relative_path = relative_path[len(".playwright-cli/") :]
        return Path(".playwright-cli") / relative_path

    def _read_latest_snap_yml(self) -> str:
        """Read the most recently-written playwright-cli snapshot .yml file.

        playwright-cli writes the accessibility tree to ``.playwright-cli/page-<ts>.yml``.
        Returns the file content as a string, or an empty string if no file exists.
        """
        log_dir = Path(".playwright-cli")
        if not log_dir.exists():
            return ""
        yml_files = sorted(
            log_dir.glob("page-*.yml"), key=lambda p: p.stat().st_mtime, reverse=True
        )
        if not yml_files:
            return ""
        return yml_files[0].read_text(errors="replace")

    # ------------------------------------------------------------------
    # DOM interaction
    # ------------------------------------------------------------------

    def snapshot(self) -> str:
        """Return the accessible element tree of the current page.

        playwright-cli writes the tree to ``.playwright-cli/page-<ts>.yml``;
        the stdout is a reference header for short pages but a full reference
        for long pages.  We always read the written file so callers get the
        complete, consistent tree regardless of output size.
        """
        result = self._run_checked(["snapshot"], timeout=15)
        # Always read the latest .yml file — it's the authoritative tree.
        return self._read_latest_snap_yml() or result.stdout

    def click(self, ref: str) -> None:
        """Click the element identified by ``ref`` (accessible ref)."""
        self._run_checked(["click", ref], timeout=15)

    def fill(self, ref: str, value: str) -> None:
        """Fill the form field identified by ``ref`` with ``value``."""
        self._run_checked(["fill", ref, value], timeout=15)

    def eval_js(self, ref: str, script: str) -> str:
        """Evaluate ``script`` in the browser context.

        playwright-cli's ``eval`` command signature is::

            eval <func> [ref]

        where ``func`` is a JS expression or ``(el) => ...`` arrow function, and
        ``ref`` (optional) is the accessible ref of the element to pass as ``el``.
        When ``ref`` is empty the script runs in the page top-level frame.

        Args:
            ref: accessible element ref (from the snapshot) to pass as ``el``;
                 use ``""`` to run in the top-level frame with no element.
            script: JS expression or ``(el) => ...`` arrow function.
        """
        result = self._run_checked(["eval", script, ref], timeout=15)
        return result.stdout

    # ------------------------------------------------------------------
    # Screenshots
    # ------------------------------------------------------------------

    def screenshot(self, dest_path: str | Path) -> None:
        """Take a screenshot and write it to ``dest_path``.

        ``playwright-cli screenshot`` saves to
        ``.playwright-cli/page-<ts>.png`` with no path argument.
        We find the newest file in that directory and copy it to
        ``dest_path``.
        """
        dest_path = Path(dest_path)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        before = set(Path(".playwright-cli").glob("page-*.png"))
        result = self._run_checked(["screenshot"], timeout=15)
        if result.returncode != 0:
            raise RuntimeError(f"screenshot failed: {result.stderr}")
        # Give the filesystem a moment to flush.
        after: set[Path] = set()
        for _ in range(10):
            after = set(Path(".playwright-cli").glob("page-*.png")) - before
            if after:
                break
            import time as _time

            _time.sleep(0.2)

        if not after:
            # Fallback: find the single newest page-*.png globally.
            pages = sorted(
                Path(".playwright-cli").glob("page-*.png"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if pages:
                after = {pages[0]}
            else:
                raise RuntimeError(
                    "playwright-cli screenshot produced no .playwright-cli/page-*.png file"
                )

        shutil.copy(after.pop(), dest_path)

    # ------------------------------------------------------------------
    # Console error detection
    # ------------------------------------------------------------------

    def read_console_errors(self) -> list[str]:
        """Return error-level lines from all console log files.

        Looks for ``.playwright-cli/console-*.log``.  Returns an empty list
        if no log file exists or no error lines are found.  Unlike the
        previous single-file approach, this method scans **all** console
        logs, newest to oldest, and aggregates any error lines found.

        This eliminates cross-test contamination: later test runs (which
        may produce no errors) no longer mask errors produced by the
        test currently under analysis.
        """
        log_dir = Path(".playwright-cli")
        if not log_dir.exists():
            return []

        logs = sorted(
            log_dir.glob("console-*.log"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not logs:
            return []

        errors: list[str] = []
        # Scan ALL log files — not just the most recent one — so that
        # errors from an earlier run are not masked by a later run that
        # produces no errors (which would cause logs[0] to point to the
        # cleaner log, masking the real error).
        for _log in logs:
            for line in _log.read_text(errors="replace").splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                # Strip common log-prefix characters before checking the token.
                clean_tokens = [
                    tok.lstrip("([{ :").lower()
                    for tok in stripped.replace("(", " ").replace(")", " ").split()
                ]
                if any(token.startswith("error") for token in clean_tokens):
                    errors.append(stripped)
        return errors

    def assert_no_console_errors(self) -> None:
        """Assert that zero console errors were recorded since the last page load."""
        errors = self.read_console_errors()
        if errors:
            msg = "Browser console errors detected:\n" + "\n".join(f"  {e}" for e in errors)
            raise AssertionError(msg)

    # ------------------------------------------------------------------
    # Accessibility
    # ------------------------------------------------------------------

    def accessibility_check(self, url: str | None = None) -> list[str]:
        """Run an accessibility snapshot and return a list of violations.

        If ``url`` is given, navigate to it first (via ``goto``).

        A violation is raised when the page has no landmark region
        (e.g. ``<main>``, ``<nav>``, ``<aside>``, ``<header>``, ``<footer>``).

        Returns a list of human-readable violation messages (empty == pass).
        """
        if url is not None:
            self.goto(url)

        snapshot_text = self.snapshot()

        # playwright-cli "snapshot" writes the real accessibility tree to
        # .playwright-cli/page-<ts>.yml.  The stdout contains a reference header
        # "### Snapshot - [Snapshot](.playwright-cli/page-<ts>.yml)" plus the
        # tree for short pages.  To get the full tree we always read the
        # latest .yml file directly, which is the most reliable approach
        # (avoids issues when the stdout is a reference to a new snapshot
        # that does not yet exist on disk).
        snapshot_text = self._read_latest_snap_yml()

        # ------------------------------------------------------------------
        # Landmarks
        # ------------------------------------------------------------------
        violations: list[str] = []

        # A page must contain at least one landmark region for a11y.
        # The playwright-cli snapshot renders accessibility-tree roles, not HTML tags:
        #   <main>  → "main"               <header> → "banner"
        #   <nav>   → "navigation"         <aside>  → "complementary"
        #   <footer> → "contentinfo"
        # We check for both HTML-tag forms (plain GET) and
        # accessibility-tree forms (playwright-cli snapshot format).
        html_landmark_forms = ("<main", "<nav", "<aside", "<header", "<footer")
        a11y_landmark_forms = ("navigation", "main", "complementary", "banner", "contentinfo")
        has_landmark = any(form in snapshot_text for form in html_landmark_forms) or any(
            form in snapshot_text for form in a11y_landmark_forms
        )
        if not has_landmark:
            violations.append(
                "Accessibility check failed: page has no landmark region "
                "(expected one of <main>, <nav>, <aside>, <header>, <footer>)"
            )

        return violations

    def assert_accessibility(self, url: str | None = None) -> None:
        """Assert the accessibility check passes for the current (or given) page."""
        violations = self.accessibility_check(url)
        if violations:
            raise AssertionError("\n".join(violations))

    # ------------------------------------------------------------------
    # HTMX dangling-target detector (used by test_journey_htmx_fragments)
    # ------------------------------------------------------------------

    def check_htmx_dangling_targets(self, html_fragment: str | None = None) -> list[str]:
        """Detect dangling htmx references in a synthetic HTML fragment or the current page.

        When called with no argument, fetches the current browser page's HTML
        via ``document.body.innerHTML`` and scans it for htmx dangling targets.

        When called with an explicit ``html_fragment`` string, scans that fragment
        directly (for use in page-fragment-level tests).

        Returns a list of violation messages (empty == pass).
        """
        if html_fragment is None:
            # Fetch the live page HTML to scan for dangling htmx refs.
            # Use empty-string ref so the script runs in the top-level frame.
            html_fragment = self.eval_js("", "document.body.innerHTML")

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
                    f'Dangling htmx reference: hx-target="#{target_id}" '
                    f'has no matching id="{target_id}" in the current HTML fragment '
                    f"(defined IDs: {sorted(defined_ids)})"
                )

        # Check hx-include="#X" references
        hx_include_pattern = re.compile(r'hx-include=["\']#([^"\']+)["\']', re.IGNORECASE)
        for match in hx_include_pattern.finditer(html_fragment):
            target_id = match.group(1)
            if target_id not in defined_ids:
                violations.append(
                    f'Dangling htmx reference: hx-include="#{target_id}" '
                    f'has no matching id="{target_id}" in the current HTML fragment'
                )

        return violations

    def assert_htmx_dangling_targets(self, html_fragment: str | None = None) -> None:
        """Assert no dangling htmx target references exist in the given HTML fragment.

        When called with no argument, fetches the live page HTML via
        ``document.body.innerHTML`` and scans it for dangling htmx refs.
        """
        violations = self.check_htmx_dangling_targets(html_fragment)
        if violations:
            raise AssertionError(
                "Dangling htmx references detected:\n" + "\n".join(f"  {v}" for v in violations)
            )

    # ------------------------------------------------------------------
    # SSE stream helpers (used by test_journey_code_qa_sse)
    # ------------------------------------------------------------------

    def wait_for_sse_chunk(
        self,
        stream_output: str | None = None,
        timeout: float = 30.0,
    ) -> bool:
        """Assert an SSE stream has delivered at least one non-empty chunk.

        When called with an explicit ``stream_output`` string (e.g. raw HTTP body
        captured via curl), scans it for ``data:`` lines and returns ``True`` if at
        least one non-empty chunk arrived.  Raises ``AssertionError`` with an
        ``SSE_TIMEOUT`` message if the stream is empty or no chunk arrives.

        When called with no ``stream_output`` (browser-mode), polls the live page
        HTML every second for up to ``timeout`` seconds, checking for content in
        the answer panel (``#chat-messages`` or ``[role=log]``).  Returns ``True``
        as soon as non-empty text appears; raises ``AssertionError`` on timeout.

        For use in journeys that assert the Code Q&A page renders an
        incrementally streaming answer.
        """
        if stream_output is not None:
            # String-mode: scan a pre-captured HTTP body.
            if not stream_output.strip():
                raise AssertionError(f"SSE_TIMEOUT: no content received within {timeout:.0f}s")
            data_lines = [
                line[5:].strip()  # strip "data:" prefix
                for line in stream_output.splitlines()
                if line.startswith("data:")
            ]
            non_empty = [line for line in data_lines if line and line not in ("<eof>", "[DONE]")]
            if not non_empty:
                raise AssertionError(f"SSE_TIMEOUT: no content received within {timeout:.0f}s")
            return True

        # Browser-mode: poll the live page for streaming answer content.
        import time as _time

        deadline = _time.monotonic() + timeout
        while _time.monotonic() < deadline:
            # Use empty-string ref so the script runs in the top-level frame.
            html = self.eval_js("", "document.body.innerHTML")
            # The Code Q&A page renders answer chunks inside #chat-messages or
            # a [role=log] region.  Any non-empty text in those regions means
            # at least one chunk arrived.
            answer_markers = ("chat-messages", 'role="log"', "data-stream")
            stripped = html.strip()
            if stripped and any(m in stripped for m in answer_markers):
                return True
            _time.sleep(1)

        raise AssertionError(
            f"SSE_TIMEOUT: no streaming answer content detected within {timeout:.0f}s"
        )
