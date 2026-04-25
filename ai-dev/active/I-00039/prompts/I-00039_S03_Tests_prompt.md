# I-00039_S03_Tests_prompt

**Work Item**: I-00039 -- Jobs page — drop color-coded Type chips and replace filter checkboxes with multi-select dropdowns
**Step**: S03
**Agent**: Tests (tests-impl)

---

## ⛔ Docker is off-limits

Standard rule. See `docs/IW_AI_Core_Agent_Constraints.md`. Testcontainer
fixtures (which spin up a labelled PostgreSQL via Ryuk) ARE allowed and are
how this project tests dashboard pages — NEVER connect to the live DB on
port 5433 from tests.

## ⛔ Migrations: agents generate, daemon applies

Not relevant for this step. Tests must run migrations INSIDE the
testcontainer fixture (already handled by `tests/conftest.py` / `tests/dashboard/conftest.py`),
never against the live DB.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `ai-dev/active/I-00039/I-00039_Issue_Design.md` — design document
- `ai-dev/active/I-00039/reports/I-00039_S01_Frontend_report.md` — what was built
- `ai-dev/active/I-00039/reports/I-00039_S02_CodeReview_report.md` — review of S01
- `tests/CLAUDE.md` — test conventions
- `tests/dashboard/conftest.py` — fixtures available for dashboard page tests
- `tests/integration/test_jobs_api.py` — existing pattern for jobs page tests
  (`_seed_all_sources` helper, `client`, `db_session`, `test_project` fixtures)
- The pre-fix evidence at `ai-dev/active/I-00039/evidences/pre/`

## Output Files

- `tests/dashboard/test_jobs_filter_ui.py` — NEW test file with reproduction
  and regression tests
- `ai-dev/active/I-00039/reports/I-00039_S03_Tests_report.md` — step report

## Context

You are writing the reproduction and regression tests for I-00039. The
implementation has already been done in S01. Your tests must:

1. Verify the fix is in place (FAIL against pre-fix code, PASS against the
   current fixed code).
2. Prevent the bug from recurring by asserting on **specific values**, not
   shape.
3. Confirm the existing query-string contract (repeated `?type=...&type=...`)
   still works end-to-end.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty)
and passed. But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "permissions" in data` (shape only)
- GOOD: `assert "brands:manage" in permissions` (semantic — verifies specific expected value)
- GOOD: `assert "*" not in permissions` (semantic — verifies unwanted value is absent)

For this incident specifically:

- BAD: `assert "type" in html` (shape only)
- BAD: `assert len(rows) > 0` (shape only)
- GOOD: `assert "bg-blue-100" not in html` (semantic — verifies specific class IS absent)
- GOOD: `assert 'data-multi-select="type"' in html` (semantic — verifies specific marker IS present)
- GOOD: `assert ids["cij_id"] in html and ids["batch_id"] not in html` (semantic — verifies specific row IS / IS NOT in result)

## Requirements

### 1. Create `tests/dashboard/test_jobs_filter_ui.py`

Use the existing `client`, `db_session`, and `test_project` fixtures from
`tests/dashboard/conftest.py` (or whichever conftest applies — check the
parent `tests/conftest.py` if dashboard tests inherit from there). Follow
the patterns established by `tests/integration/test_jobs_api.py` for any
seeding of multiple job types.

### 2. Test: Type cell is plain text — no per-type colour classes

```python
LEGACY_TYPE_COLOR_CLASSES = (
    "bg-blue-100",   # was code_mapping
    "bg-purple-100", # was doc_generation
    "bg-orange-100", # was batch_execution
    "bg-teal-100",   # was research
    "bg-emerald-100",# was oss_scan
)

def test_jobs_type_cell_is_plain_text_no_color_chip(
    client, db_session, test_project
):
    # Seed at least one job of each type so the rendered HTML actually
    # exercises every branch of the (now-removed) type_chip macro.
    _seed_all_sources(db_session, test_project.id)
    db_session.commit()

    resp = client.get(f"/project/{test_project.id}/jobs")
    assert resp.status_code == 200
    html = resp.text

    for cls in LEGACY_TYPE_COLOR_CLASSES:
        assert cls not in html, (
            f"Legacy color class {cls!r} still present in Jobs page HTML — "
            "Type chip color-coding was not removed."
        )
```

The seed helper `_seed_all_sources` already exists in
`tests/integration/test_jobs_api.py`. Either import it (preferred) or
duplicate the relevant seeding in your test file. If you import, keep the
import path explicit so a future reader can find it.

### 3. Test: Filter renders multi-select dropdown markup, not flat checkboxes

```python
def test_jobs_filter_uses_multiselect_dropdown_not_checkbox_groups(
    client, test_project
):
    resp = client.get(f"/project/{test_project.id}/jobs")
    assert resp.status_code == 200
    html = resp.text

    # The new component MUST be present for both filters.
    assert 'data-multi-select="type"' in html
    assert 'data-multi-select="status"' in html

    # The pre-fix flat-checkbox shape must NOT appear at the form's top level.
    # (Checkboxes still exist INSIDE the dropdown panel, but they should be
    # children of [data-multi-select-panel]. Use a normalized comparison so
    # whitespace differences don't make the test fragile.)
    normalized = "".join(html.split())
    assert '<inputtype="checkbox"name="type"' not in normalized
    assert '<inputtype="checkbox"name="status"' not in normalized
```

Note the normalised string trick is to make the assertion robust against
whitespace; refine if S01 produces a different shape but keep the assertion
**semantic** (specific marker must / must not appear).

### 4. Test: Multi-value filter still works (regression)

This is the regression guard for the query-string contract. Reuse the
pattern from `tests/integration/test_jobs_api.py::test_jobs_list_type_filter_excludes_other_types`:

```python
def test_jobs_filter_multiple_types_still_filters(
    client, db_session, test_project
):
    ids = _seed_all_sources(db_session, test_project.id)
    db_session.commit()

    # Submit two type values. The form action MUST still produce
    # ?type=code_mapping&type=research and the route MUST honour both.
    resp = client.get(
        f"/project/{test_project.id}/jobs?type=code_mapping&type=research"
    )
    assert resp.status_code == 200
    html = resp.text

    # Semantic assertions: only the seeded code_mapping and research rows
    # are present; batch and doc_generation rows are NOT.
    assert ids["cij_id"] in html      # code_mapping kept
    assert ids["res_doc_id"] in html  # research kept
    assert ids["batch_id"] not in html      # batch_execution excluded
    assert ids["dgj_id"] not in html        # doc_generation excluded
```

### 5. Test: multi_select.js syntax is valid

The dashboard's `make lint` already runs `node --check` on
`dashboard/static/**/*.js`. If S01 added `dashboard/static/multi_select.js`,
that file is automatically covered. Do NOT add a separate Python test for
JS syntax — `make lint` already handles it. (Just confirm S01 did not break
it; the QV-gate `make lint` step will catch failures.)

### 6. Verify your tests fail before the fix would be applied

Mentally walk through each assertion against the **pre-fix** HTML (you can
reconstruct it from the design document and the pre-fix screenshot) to
confirm each test would actually FAIL on the buggy code, not merely PASS
trivially. Document this reasoning in the step report.

## Project Conventions

- All dashboard tests use FastAPI's `TestClient` with a PostgreSQL
  testcontainer. Fixtures live in `tests/dashboard/conftest.py` and the
  parent `tests/conftest.py`.
- **NEVER** mock the database in integration tests (per project `CLAUDE.md`).
- **NEVER** connect tests to the live DB on port 5433.
- **MUST** replace psycopg2 URLs in testcontainers (already done by the
  fixture; just don't fight it).
- Test naming: `test_<scenario>_<expected_outcome>` — see existing tests
  for patterns.

## TDD Requirement

The implementation in S01 already exists. Your job is to lock it in:

1. **RED (mental)**: Verify each assertion would have FAILED against the
   pre-fix code — write down the reasoning in your step report.
2. **GREEN**: Run the tests and confirm they PASS against the current
   (fixed) code.
3. **REFACTOR**: Tidy assertions, factor any duplication into helpers if
   the file gets long.

## Test Verification (NON-NEGOTIABLE)

After writing the tests:

1. Run only your new tests:
   ```bash
   uv run pytest tests/dashboard/test_jobs_filter_ui.py -v
   ```
   All tests must pass.
2. Run the broader dashboard test suite to confirm no regressions:
   ```bash
   make test-unit
   ```
   Must pass with zero failures.
3. Do **NOT** report `tests_passed: true` unless both steps above pass.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00039",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/dashboard/test_jobs_filter_ui.py"
  ],
  "tests_passed": true,
  "test_summary": "3 new dashboard tests passed; full unit suite X passed, 0 failed",
  "blockers": [],
  "notes": "Each assertion verified to fail against pre-fix HTML (reasoning in this report). Used _seed_all_sources from tests/integration/test_jobs_api.py."
}
```
