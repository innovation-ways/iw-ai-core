# CR-00056 S12 — CodeReview Report (Tests)

**Agent**: code-review-impl
**Work Item**: CR-00056 — Surface step prompts in dashboard (Prompt column + modal viewer)
**Step Reviewed**: S11 (tests-impl)
**Date**: 2026-05-17

---

## Summary

S11 implemented the full test suite for CR-00056. All 33 tests pass. The AC × test coverage matrix is complete. No mandatory fixes, but two pre-existing lint violations in unrelated files prevent a fully clean gate.

---

## 1. AC × Test Coverage Matrix

| AC | Required Behaviour | Test(s) | Status |
|----|--------------------|---------|--------|
| AC1 | Schema columns exist | `test_step_run_prompt_columns.py` (implicit via S03 migration-check) | ✅ Covered |
| AC2 | Initial run snapshots prompt | `test_daemon_prompt_snapshot.py::test_initial_run_snapshots_prompt_text` | ✅ Covered |
| AC3 | Fix-cycle snapshots fix + base prompt | `test_daemon_prompt_snapshot.py::test_fix_cycle_snapshots_fix_prompt_text_and_base_prompt_text` | ✅ Covered |
| AC4 | Prompt column renders with View/— | `test_item_steps_table_render.py::test_prompt_column_header_present_between_model_and_status` + `test_step_with_prompt_renders_view_button_with_correct_hx_get` + `test_synthetic_step_renders_dash_in_prompt_column` + `test_step_without_prompt_renders_dash` | ✅ Covered |
| AC5 | Modal returns 200 with `<pre>` + aria | `test_prompt_modal_route.py::test_returns_200_with_initial_prompt_section` + `test_fragment_has_aria_modal_dialog` | ✅ Covered |
| AC6 | Dismissal a11y | qv-browser S22 (frontend behaviour) | Delegated |
| AC7 | Stacked Initial + Fix sections | `test_prompt_modal_route.py::test_returns_200_with_initial_and_fix_sections` | ✅ Covered |
| AC8 | Copy works | qv-browser S22 (requires real browser) | Delegated |
| AC9 | 404 on project mismatch | `test_prompt_modal_route.py::test_returns_404_when_step_belongs_to_other_project` + `test_returns_404_when_item_id_mismatch` | ✅ Covered |

**Result**: All self-testable ACs (1–5, 7, 9) have explicit test coverage. AC6 and AC8 are correctly delegated to qv-browser S22.

---

## 2. Pre-Review Lint & Format Gate

```bash
make lint   # E501 + F401 in pre-existing files (not S11 changes)
make format # 1 violation in pre-existing safe_migrate.py
```

Two pre-existing violations block the gate — neither is in S11's test files:

| File | Line | Issue | In S11? |
|------|------|-------|---------|
| `dashboard/routers/items.py` | 19 | `Integer` imported but unused | ❌ (S06/S07) |
| `orch/db/safe_migrate.py` | 64 | Line too long (101 > 100 chars) | ❌ (pre-existing) |

S11's test files (`test_step_run_prompt_columns.py`, `test_daemon_prompt_snapshot.py`, `test_prompt_modal_route.py`, `test_item_steps_table_render.py`) have **zero** lint or format violations.

---

## 3. Test Execution Results

All S11 test files verified against the actual implementation:

```
tests/unit/test_step_run_prompt_columns.py          — 8 passed
tests/integration/test_daemon_prompt_snapshot.py   — 5 passed
tests/dashboard/test_prompt_modal_route.py         — 14 passed
tests/dashboard/test_item_steps_table_render.py    — 6 passed
Total: 33 passed, 0 failed
```

---

## 4. Assertion Strength Review

### Unit (`test_step_run_prompt_columns.py`)
- `test_step_run_accepts_prompt_text`: asserts attribute round-trips correctly ✅
- `test_step_run_defaults_prompt_columns_to_none`: asserts both are `None` when omitted ✅
- `test_step_run_accepts_both_prompt_columns_together`: both columns coexist ✅
- `test_step_run_prompt_text_with_long_content`: 10 KB stored correctly ✅
- `test_step_run_prompt_text_special_characters`: `<script>alert('xss')</script>` stored as-is at ORM level ✅
- `test_step_run_accepts_prompt_text_with_unicode`: unicode handled ✅
- `test_step_run_accepts_empty_string_prompt`: `""` is distinct from `None` ✅

All assertions are specific and meaningful. No tautological assertions.

### Integration (`test_daemon_prompt_snapshot.py`)
- `test_initial_run_snapshots_prompt_text`: checks `raw_prompt in run.prompt_text` — specific substring check, not just non-NULL ✅
- `test_fix_cycle_snapshots_fix_prompt_text_and_base_prompt_text`: verifies `fix_prompt_text == fix_prompt_content` AND `prompt_text == base_prompt_content` ✅
- `test_initial_run_with_missing_prompt_file_creates_step_run_with_fallback_prompt`: asserts `run.prompt_text is not None` and `item_id in run.prompt_text` — strong fallback assertion ✅
- `test_fix_cycle_missing_base_prompt_file_sets_null_not_error`: verifies fix_prompt_text is set AND prompt_text is NULL when base file missing ✅

### Dashboard modal (`test_prompt_modal_route.py`)
- `test_returns_200_with_initial_prompt_section`: asserts on specific content (`"The initial prompt for S02"` in response), not just 200 ✅
- `test_returns_200_with_initial_and_fix_sections`: checks both content AND ordering (Initial before Fix) ✅
- `test_fragment_has_aria_modal_dialog`: BeautifulSoup assertions on `role`, `aria-modal`, `aria-labelledby` ✅
- `test_fragment_does_not_extend_base_html`: checks no `<html>` or `<!doctype` ✅
- **`test_prompt_text_is_html_escaped`**: feeds `<script>alert(1)</script>` and asserts `&lt;script&gt;` in raw pre HTML — strong XSS test ✅**

### Dashboard table (`test_item_steps_table_render.py`)
- `test_prompt_column_header_present_between_model_and_status`: BeautifulSoup finds `<th>Prompt</th>`, verifies `Model < Prompt < Status` ordering ✅
- `test_step_with_prompt_renders_view_button_with_correct_hx_get`: verifies exact `hx-get` URL, not just presence of button ✅
- `test_synthetic_step_renders_dash_in_prompt_column`: asserts `—` (not a button) ✅
- `test_step_without_prompt_renders_dash`: `has_prompt=False` → `—` ✅

---

## 5. Test Isolation

| Check | Result |
|-------|--------|
| No live DB port 5433 in S11 test files | ✅ Zero hits |
| No `importlib.reload(orch.config)` | ✅ Zero hits |
| No `psycopg2` imports | ✅ Zero hits |
| Uses `db_session` fixture (testcontainer-backed) | ✅ All tests use `testcontainer_db` |
| Deterministic (no `time.sleep`, no real network) | ✅ All use mocks or real temp files |

**Note on `daemon_config` fixture using `db_port=5433`**: The `daemon_config` is a dataclass literal (not a live DB connection). The `BatchManager` is constructed with `session_factory` pointing to the test's `db_session` fixture, which is testcontainer-backed. The `5433` in the fixture is a default value for the dataclass field — it does not cause a connection to the live DB. Confirmed by test passing and `db_session` being testcontainer-backed throughout.

---

## 6. XSS Test (CRITICAL check)

`test_prompt_text_is_html_escaped` in `test_prompt_modal_route.py`:
- Feeds XSS payload `<script>alert(1)</script>` into DB
- Uses regex to find the `<pre>` element's raw HTML
- Asserts `&lt;script&gt;` is in the raw pre HTML (escaped)
- Asserts unescaped `<script>` is NOT in the pre HTML content

This is a strong XSS test using raw HTML inspection, not just `BeautifulSoup.get_text()` (which would decode entities).

---

## 7. TDD RED Evidence

The report documents `test_returns_200_with_initial_and_fix_sections` as the key RED-first test with this assertion failure:

```
AssertionError: 'Fix Prompt (cycle 1)' not in response.text
```

The test was written in RED, confirmed it failed, then the route was wired to render fix-cycle sections. This is proper TDD.

---

## 8. Fixture Usage

- Dashboard tests: `TestClient` via `client(db_session)` fixture ✅
- Integration tests: `db_session` from `conftest.py` (testcontainer-backed) ✅
- Transactional rollback: `db_session.commit()` at end of each test, `db_session.expire_all()` before assertions ✅
- FTS DDL: handled by the `db_session` fixture's `Base.metadata.create_all()` + `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` (standard fixture) ✅

---

## Findings

### Pre-existing lint violations (NOT in S11 — cannot fix in S12)

| Severity | File | Issue |
|----------|------|-------|
| MEDIUM | `dashboard/routers/items.py:19` | `Integer` imported but unused (S06/S07) |
| MEDIUM | `orch/db/safe_migrate.py:64` | Line too long 101 > 100 chars (pre-existing) |

These are outside S11's scope and cannot be addressed by this review step.

---

## Verdict

```json
{
  "step": "S12",
  "agent": "CodeReview",
  "work_item": "CR-00056",
  "step_reviewed": "S11",
  "verdict": "pass",
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "33 tests passed (8 unit + 5 integration + 14 dashboard modal + 6 dashboard table)",
  "ac_coverage": "All self-testable ACs covered (AC1–AC5, AC7, AC9). AC6 and AC8 correctly delegated to qv-browser S22.",
  "xss_test_present": true,
  "tdd_red_evidence": true,
  "live_db_violations": 0,
  "importlib_reload_violations": 0,
  "psycopg2_violations": 0,
  "lint_violations_in_s11_files": 0,
  "pre_existing_lint_blocking_gate": 2,
  "notes": "Two pre-existing lint violations in dashboard/routers/items.py (F401 Integer unused) and orch/db/safe_migrate.py (E501 line too long) block the gate but are not from S11. All S11 test files are lint-clean. The daemon_config fixture uses db_port=5433 as a dataclass default but is backed by the testcontainer db_session, not a live connection."
}
```

---

## Recommendation

**S12 PASS** — proceed to S13 (CodeReview Final). The pre-existing lint violations should be cleaned up in a separate pass (not in S11's scope).
