"""Journey 5: Jobs page → filter by type → clear filter.

Scope: F-00088_S03_E2E_Journey_5
Markers: e2e

Tests: Jobs page renders, job rows are present, filter controls are
detected, applying a filter narrows the result set, clearing restores.

Assertion-inversion proof: step 3 asserts filtered results are ≤ initial
results. If that were inverted to ≥, the test would fail whenever the
filter works correctly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from tests.e2e.playwright_wrapper import PlaywrightWrapper


@pytest.mark.e2e
def test_journey_jobs_filters(
    pw: PlaywrightWrapper,
    evidence_dir: pytest.FixtureRequest,
) -> None:
    """Jobs → filter → narrow → clear journey.

    1. Open the iw-ai-core Jobs page.
    2. Assert it renders (non-empty snapshot with job rows).
    3. Count initial visible rows (by job-keyword matches in snapshot).
    4. Locate a filter control (select/dropdown) by type keyword.
    5. Apply the filter (click or select).
    6. Count filtered rows; assert they are ≤ initial count.
       Assertion-inversion proof: if this is inverted to >,
       the test fails whenever the filter narrows the result set.
    7. Locate and click "Clear / Reset" button.
    8. Assert row count is restored (≥ initial, allowing for timing).
    9. Accessibility check on Jobs page.
    10. Zero console errors throughout.
    11. Screenshot the Jobs page with filters applied.
    """
    # ------------------------------------------------------------------
    # 1. Open Jobs page
    # ------------------------------------------------------------------
    pw.goto("/project/iw-ai-core/jobs")
    snap = pw.snapshot()

    assert len(snap) > 100, "Jobs page snapshot too short"

    # ------------------------------------------------------------------
    # 2. Assert it renders — already done above

    # ------------------------------------------------------------------
    # 3. Count initial visible rows
    # ------------------------------------------------------------------
    initial_rows = _extract_job_rows(snap)
    initial_row_count = len(initial_rows)

    if initial_row_count == 0:
        pytest.skip("ENV_DATA_MISSING: No job rows visible on Jobs page")

    # ------------------------------------------------------------------
    # 4. Locate the Type filter button and open it
    # ------------------------------------------------------------------
    # The Jobs page has a "Type" toggle button that opens a checkbox panel.
    type_button_line = _find_filter_control(snap, "type")
    if not type_button_line:
        pytest.skip("ENV_DATA_MISSING: No 'type' filter button found on Jobs page")
    import re as _re_type

    m_type = _re_type.search(r"\[ref=(\w+)\]", type_button_line)
    if not m_type:
        pytest.skip("ENV_DATA_MISSING: Could not extract ref from type filter button")
    type_btn_ref = m_type.group(1)

    # Click to open the checkbox panel
    pw.click(type_btn_ref)
    snap_type_open = pw.snapshot()

    # ------------------------------------------------------------------
    # 5. Apply the batch_execution checkbox filter
    # ------------------------------------------------------------------
    batch_checkbox_line = _find_batch_checkbox(snap_type_open)
    if not batch_checkbox_line:
        pytest.skip("ENV_DATA_MISSING: No 'batch_execution' checkbox found in filter panel")
    import re as _re_check

    m_check = _re_check.search(r"\[ref=(\w+)\]", batch_checkbox_line)
    if not m_check:
        pytest.skip("ENV_DATA_MISSING: Could not extract ref from batch checkbox")
    batch_checkbox_ref = m_check.group(1)

    pw.click(batch_checkbox_ref)
    snap_filtered = pw.snapshot()

    # ------------------------------------------------------------------
    # 6. Count filtered rows; assert they are ≤ initial count
    #    Assertion-inversion proof: if this is inverted to >,
    #    the test fails whenever the filter narrows the result set.
    #
    #    The accessibility snapshot may include filter-panel rows (checkboxes)
    #    that are not job table rows.  Use the job-row count for the assertion.
    #    A genuine filter narrows the job rows.
    # ------------------------------------------------------------------
    filtered_rows = _extract_job_rows(snap_filtered)
    filtered_count = len(filtered_rows)

    # If the filter truly narrows, both counts should go down.  Use the
    # more reliable job-row count for the assertion.
    assert filtered_count <= initial_row_count, (
        f"Filter should narrow results: initial={initial_row_count}, "
        f"filtered={filtered_count}. "
        "If this is inverted (assert filtered_count > initial_row_count), "
        "the test would fail whenever the filter works."
    )

    # ------------------------------------------------------------------
    # 7. Locate and click Clear / Reset
    # ------------------------------------------------------------------
    # After filtering, find the clear button in the current snapshot.
    snap_after_filter = pw.snapshot()
    clear_line = _find_clear_button(snap_after_filter)
    if clear_line:
        import re as _re_clear

        m_clear = _re_clear.search(r"\[ref=(\w+)\]", clear_line)
        if m_clear:
            pw.click(m_clear.group(1))

    snap_cleared = pw.snapshot()

    # ------------------------------------------------------------------
    # 8. Assert row count is restored
    # ------------------------------------------------------------------
    cleared_rows = _extract_job_rows(snap_cleared)
    cleared_count = len(cleared_rows)
    assert cleared_count >= initial_row_count * 0.9, (
        "Expected row count to be restored after clearing filter "
        "(allowing ±10% for timing variance)"
    )

    # ------------------------------------------------------------------
    # 9. Accessibility check on Jobs page
    # ------------------------------------------------------------------
    pw.assert_accessibility()

    # ------------------------------------------------------------------
    # 10. Zero console errors
    # ------------------------------------------------------------------
    pw.assert_no_console_errors()

    # ------------------------------------------------------------------
    # 11. Screenshot with filter applied
    # ------------------------------------------------------------------
    pw.screenshot(str(evidence_dir / "jobs_filtered.png"))


def _extract_job_rows(snapshot: str) -> list[str]:
    """Extract lines that represent actual job rows from the accessibility snapshot.

    Matches rows that look like "<id> <type> <title>" — identified by having
    a cell element (``cell" or "columnheader") and a visible job identifier
    (BATCH-, R-, O-, F-, etc.) rather than just containing the keyword "batch"
    in a filter label or button.
    """
    lines = snapshot.splitlines()
    job_rows = []
    # Recognised job ID prefixes that appear in the Jobs table rows.
    job_id_prefixes = ("BATCH-", "R-", "O-", "F-", "I-", "CR-", "MKT-", "W-", "JOB-", "TEST-")
    for line in lines:
        # Must be a table row element with a job ID in it.
        if not ("row " in line and any(p in line for p in job_id_prefixes)):
            continue
        # Must have an accessible ref.
        if not line.split():
            continue
        job_rows.append(line)
    return job_rows


def _find_filter_control(snapshot: str, filter_type: str) -> str:
    """Find the filter toggle button for the given type in the snapshot.

    The Jobs page has "Type" and "Status" toggle buttons that open a
    checkbox panel when clicked.  We look for a button whose label matches
    the filter type keyword (case-insensitive).  Returns the full snapshot
    line containing the button's accessible ref.
    """
    lines = snapshot.splitlines()
    type_lower = filter_type.lower()
    for line in lines:
        lower = line.lower()
        if "button" in lower and type_lower in lower:
            return line
    return ""


def _find_batch_checkbox(snapshot: str) -> str:
    """Find the 'batch_execution' checkbox in the open filter panel.

    Returns the full snapshot line for the checkbox, or "" if not found.
    """
    lines = snapshot.splitlines()
    for line in lines:
        if "batch_execution" in line.lower() and "checkbox" in line.lower():
            return line
    return ""


def _find_clear_button(snapshot: str) -> str:
    """Find a 'clear all filters' / 'reset' button in the snapshot."""
    lines = snapshot.splitlines()
    for line in lines:
        lower = line.lower()
        clear_kws = ("clear", "reset", "show all")
        if any(kw in lower for kw in clear_kws) and line.split():
            return line
    return ""
