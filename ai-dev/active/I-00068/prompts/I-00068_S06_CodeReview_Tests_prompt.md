# I-00068_S06_CodeReview_Tests_prompt

**Work Item**: I-00068 -- Recent Activity batch link from "archived" event routes to /item/ instead of /batch/
**Step Being Reviewed**: S05 (tests-impl)
**Review Step**: S06

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

Standard policy.

## Input Files

- `uv run iw item-status I-00068 --json` — runtime step state
- `ai-dev/active/I-00068/I-00068_Issue_Design.md` — Design document
- `ai-dev/active/I-00068/reports/I-00068_S05_Tests_report.md` — S05 report
- `tests/integration/test_i00068_batch_link_routing.py` — Tests added in S05
- `tests/integration/test_dashboard_pages.py` — Existing dashboard tests
- `tests/conftest.py` and `tests/CLAUDE.md` — Conventions

## Output Files

- `ai-dev/active/I-00068/reports/I-00068_S06_CodeReview_report.md`

## Pre-Review Lint & Format Gate

```bash
make lint
make format
```

Report new violations as CRITICAL findings.

## Review Checklist

### 1. Falsifiability

For each test, verify the test would FAIL on the pre-fix code:

- `test_batch_archiver_emit_writes_entity_type_batch` — pre-fix `_emit` does NOT set `entity_type`. The asserted equality `row.entity_type == "batch"` would fail with `None == "batch"`. ✓
- `test_dashboard_routes_batch_id_to_batch_url_when_entity_type_is_none` — pre-fix template falls through to `/item/`. The assertion `'href="/project/test-proj/batch/BATCH-99099"' in resp.text` would fail. ✓
- `test_dashboard_routes_batch_id_to_batch_url_when_entity_type_is_batch` — would PASS pre-fix too (the `entity_type=='batch'` branch already works). This is a regression-prevention test, NOT a reproduction test. Flag it as such in your review notes.
- `test_dashboard_falls_back_to_item_for_non_batch_id_with_no_entity_type` — would PASS pre-fix (the bug only affects BATCH IDs). Regression-prevention. Note this.
- `test_dashboard_falls_back_to_item_for_lowercase_batch_prefix` — would PASS pre-fix. Regression-prevention.
- `test_dashboard_does_not_match_batchfoo_prefix_without_dash` — would PASS pre-fix. Regression-prevention.
- `test_dashboard_existing_entity_type_branches_unchanged` — would PASS pre-fix. Regression-prevention.

If any test labelled "reproduction" in S05's report would actually PASS on `main`, flag it as CRITICAL.

### 2. Semantic correctness, not shape

- Tests assert SPECIFIC values. Examples:
  - `assert row.entity_type == "batch"` ✓ — exact equality
  - `assert 'href="/project/test-proj/batch/BATCH-99099"' in resp.text` ✓ — full URL substring
  - `assert 'href="/project/test-proj/item/BATCH-99099"' not in resp.text` ✓ — explicit absence

- Flag any:
  - `assert "batch" in row.entity_type` — substring instead of equality (false positive risk)
  - `assert "BATCH-99099" in resp.text` (without the surrounding `href=`) — could match in any text, not just href

### 3. Coverage

The suite must include:
- ≥1 backend test asserting `_emit(...)` writes `entity_type="batch"`.
- ≥1 dashboard test asserting `BATCH-` ID + `entity_type=None` → `/batch/`.
- ≥1 dashboard test asserting `BATCH-` ID + `entity_type="batch"` → `/batch/` (no regression on explicit branch).
- ≥1 dashboard test asserting non-`BATCH-` ID + `entity_type=None` → `/item/` (no over-matching).
- ≥1 dashboard test asserting case-sensitivity (`batch-...` lowercase routes to `/item/`).
- ≥1 dashboard test asserting prefix requires the trailing dash (`BATCHFOO` routes to `/item/`).

If any of these is missing, flag as MEDIUM (fixable).

### 4. Test isolation

- Tests use the testcontainer-backed `db_session` fixture.
- Tests do NOT modify pre-existing rows (`daemon_events` is append-only).
- No mocks for the database.
- No order-dependence between tests.

### 5. Existing tests not regressed

- `tests/integration/test_dashboard_pages.py` is NOT modified by S05.
- `test_recent_activity_unknown_entity_type_falls_back_to_item_route` (using `I-99999`) still passes — verify by running `make test-integration` and reading the output.

### 6. Project conventions

Read `tests/CLAUDE.md` for any other rules. Confirm `event_metadata` is used (not `metadata`) wherever the test code accesses the column.

## Test Verification (NON-NEGOTIABLE)

Run `make test-integration`. All tests must pass.

## Severity Levels

CRITICAL / HIGH / MEDIUM_FIXABLE / MEDIUM_SUGGESTION / LOW.

## Review Result Contract

Same JSON shape as I-00067_S02. `verdict: "pass"` requires zero CRITICAL/HIGH/MEDIUM_FIXABLE findings.
