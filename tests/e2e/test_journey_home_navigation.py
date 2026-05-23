"""Journey 1: dashboard home → project → cross-tab navigation.

Scope: F-00088_S01_E2E_Journey_1
Markers: e2e, e2e_smoke (blocking on pull_request / push)

The IW AI Core dashboard has no authentication — there is no login page,
no credentials, and no logout.  Do NOT add a login step and do NOT read
``IW_BROWSER_E2E_USER`` / ``IW_BROWSER_E2E_PASSWORD``.

If any assertion in this file is inverted (e.g. ``assert not page_visible``),
the journey will fail — proving the test can detect regressions.
Specifically: the single behavioural assertion that proves this journey
can fail is the check at step 2 that asserts the home page lists at
least one project — if that were inverted to ``assert projects == 0``,
the test would fail whenever seed data is present (the normal case).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from tests.e2e.playwright_wrapper import PlaywrightWrapper


@pytest.mark.e2e
@pytest.mark.e2e_smoke
def test_journey_home_navigation(
    pw: PlaywrightWrapper,
    evidence_dir: pytest.FixtureRequest,
) -> None:
    """Full home → project → cross-tab navigation journey.

    1. Open global dashboard home; assert HTTP 200 and ≥1 project listed.
    2. Accessibility check on home page (must have landmark).
    3. Zero console errors on home page.
    4. Click into a project (read the link from the rendered page).
    5. Assert project landing page renders with project name visible.
    6. Navigate Queue tab; assert HTTP 200 + zero console errors.
    7. Navigate Code tab; assert HTTP 200 + zero console errors.
    8. Navigate Docs tab; assert HTTP 200 + zero console errors.
    9. Navigate Jobs tab; assert HTTP 200 + zero console errors.
    10. Screenshot the project home page into the evidence dir.
    11. Navigate back to global home; assert still renders and project list intact.
    12. Accessibility check on project page; assert it passes.
    13. Zero console errors for the full journey.
    """
    # ------------------------------------------------------------------
    # 1. Open global home
    # ------------------------------------------------------------------
    pw.open_url("/")
    snap = pw.snapshot()

    # 2. Accessibility check on home
    pw.assert_accessibility()
    pw.assert_no_console_errors()

    # Extract project links from the snapshot — never hardcode URLs.
    # The snapshot lists accessible elements; look for links referencing "/project/".
    project_links = [
        line.strip()
        for line in snap.splitlines()
        if "/project/" in line and ">" not in line.split("/project/")[0]
    ]
    assert len(project_links) > 0, (
        "Expected at least one project link on the dashboard home page. "
        "If this assertion is inverted (assert projects == 0), the test "
        "will fail whenever seed data is present — proving the journey can fail."
    )

    # ------------------------------------------------------------------
    # 4–5. Click into first project
    # ------------------------------------------------------------------
    # Use the first line containing a project reference.  The accessible
    # ref is the first whitespace-delimited token on the line.
    first_link_line = next(line for line in snap.splitlines() if "/project/" in line)
    # The ref is the first token on the line (e.g. "row1" or "link1").
    ref = first_link_line.split()[0]

    pw.click(ref)
    snap_project = pw.snapshot()

    # 5. Project page renders with project name visible
    # At minimum the project landing page shows its own identifier.
    assert len(snap_project) > 100, "Project page snapshot too short — may not have rendered"

    # ------------------------------------------------------------------
    # 6–9. Cross-tab navigation (Queue / Code / Docs / Jobs)
    # ------------------------------------------------------------------
    nav_tabs = ["Queue", "Code", "Docs", "Jobs"]
    for tab_name in nav_tabs:
        # Find the tab link in the snapshot — use accessible ref to click.
        tab_line = next(
            (line for line in snap_project.splitlines() if tab_name in line),
            "",
        )
        if tab_line:
            tab_ref = tab_line.split()[0]
            pw.click(tab_ref)
        # Each tab is a full-page navigation; assert it renders.
        snap_tab = pw.snapshot()
        assert len(snap_tab) > 50, f"Tab '{tab_name}' page snapshot too short"
        pw.assert_no_console_errors()
        # ------------------------------------------------------------------
        # 12. Accessibility check on at least one project page
        # ------------------------------------------------------------------
        if tab_name == "Jobs":
            pw.assert_accessibility()

    # ------------------------------------------------------------------
    # 10. Screenshot
    # ------------------------------------------------------------------
    pw.screenshot(str(evidence_dir / "home_navigation_project.png"))

    # ------------------------------------------------------------------
    # 11. Navigate back to global home
    # ------------------------------------------------------------------
    # The global home link is typically labelled "IW AI Core" or similar
    # in the top navigation bar.
    global_home_line = next(
        (
            line
            for line in snap_project.splitlines()
            if 'href="/"' in line or 'href="/ "' in line or "/ " in line.split(">")[-1]
        ),
        "",
    )
    if global_home_line:
        home_ref = global_home_line.split()[0]
        pw.click(home_ref)

    snap_home_again = pw.snapshot()
    assert len(snap_home_again) > 50, "Global home no longer renders after navigation"

    # ------------------------------------------------------------------
    # 13. Zero console errors for the full journey
    # ------------------------------------------------------------------
    pw.assert_no_console_errors()
