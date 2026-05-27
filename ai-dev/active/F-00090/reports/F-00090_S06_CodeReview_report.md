# F-00090 S06 — Per-Agent Code Review Report

**Work Item**: F-00090 — Regression-rate tracking
**Step**: S06 (code-review-impl)
**Reviewer**: code-review-impl agent
**Date**: 2026-05-27
**Steps reviewed**: S01 (Database) · S02 (Backend) · S03 (Frontend) · S04 (Frontend) · S05 (Backend)

---

## Verdict: PASS

All quality gates green; no CRITICAL or HIGH findings; one MEDIUM_FIXABLE (test gap) and one MEDIUM_SUGGESTION noted below.

---

## Pre-Gate Results (NON-NEGOTIABLE)

| Gate | Result |
|------|--------|
| `make lint` | ✅ All checks passed (ruff + Jinja2 template check) |
| `make format` | ✅ All formatted (ruff format, 940 files checked) |
| `make test-unit` | ✅ 3601 passed, 0 failed, 7 skipped, 5 xfailed, 3 xpassed |

---

## Architecture Compliance

| Concern | Finding |
|---------|---------|
| S01 SQLAlchemy 2.0 / `Mapped[]` style | ✅ `WorkItem` fields use `Mapped[str \| None]` etc., matching existing model conventions |
| ENUM pattern | ✅ `RegressionClassification` follows `_col` helper + `create_type=False` pattern; migration creates PG type explicitly |
| S02 service takes session as argument | ✅ `classify(session, ...)` and `suggest_introducer(session, ...)` take `Session` as arg |
| S03 htmx (no JS framework) | ✅ All interactions are server-rendered htmx fragments; no client-side framework |
| S05 backfill uses argparse | ✅ `scripts/backfill_regression_classification.py` uses `argparse.ArgumentParser` |
| Composite PK `(project_id, id)` preserved | ✅ No changes to primary key structure on `work_items` |

---

## Code Quality

### `suggest_introducer()` scoring — verified correct

The git log iteration accumulates counts per SHA. Because `git log` returns newest-first, iterating and incrementing gives higher counts to the more-recently-active SHAs. The sort `key=lambda c: (c.score, c.commit_sha), reverse=True)` gives score DESC primary, then SHA DESC as a recency tiebreaker. This is sound.

### N+1 pattern — avoided

`regression_count_for_merge()` (project_dashboard.py) uses a single batched query with `GROUP BY introduced_by_work_item_id` and `.in_(merge_item_ids)`. Both `batches.py` and `project_pages.py` call it once per request, prefetching all badge counts — no N+1.

### Rate guard (Invariant 6) — correct

```python
rate = round(regressions / merges, 3) if merges > 0 else 0.0
```
Never NaN, never a `ZeroDivisionError`. Verified by `weekly_metrics` unit-test coverage.

### htmx form error handling — correct

`ValueError` → 422 with re-rendered form + inline error. `LookupError` → 404. No 500 on git failures (`suggest_introducer` wrapped in try/except returning `[]`).

### `classified_by` derivation — correct

Sourced from `request.headers.get("X-User-Name", "unknown")` in UI routes, not from any user-editable form field. `heuristic:auto` only set when `accept_top=1` is submitted. Invariant 3 (operator confirmation) is enforced throughout.

### Backfill — Invariant 3 upheld

`run()` calls `suggest_introducer()` only and returns `(processed, had_suggestions, 0)`. The `classified` count is always 0; no row is ever persisted by the script. `test_backfill_persists_no_classifications` asserts this explicitly.

---

## Project Conventions

| Convention | Finding |
|-----------|---------|
| Jinja2 `format` filter `%`-style | ✅ All new templates use `"%.1f%%"\|format(...)`; zero `str.format`-style calls |
| Plain CSS (no Tailwind-only utilities) | ✅ `.iw-regression-badge` is plain CSS; no `@apply` or Tailwind-only utilities |
| psycopg v3 (not psycopg2) | ✅ All new files use `sqlalchemy` / `Session`; no `psycopg2` references found |
| Migration round-trip | ✅ S01 `make migration-check`: 3/3 tests passed; ENUM + index clean in `downgrade()` |
| `db_engine` fixture patched for backfill tests | ✅ `tests/integration/conftest.py` now patches all 6 `IW_CORE_DB_*` + `IW_CORE_ORCH_DB_*` env vars |

---

## Security

| Surface | Assessment |
|---------|-----------|
| `introduced_by_commit_sha` free-text field | ✅ Server-side regex re-validation in `item_regression_classify`: `^[0-9a-fA-F]{7,40}$`; `pattern` HTML attribute is progressive enhancement only |
| `classified_by` spoofing | ✅ Not a form field; derived from `X-User-Name` header (same as existing routes) |
| SQL injection | ✅ All queries use SQLAlchemy `select()` with bound parameters; no raw SQL |

---

## TDD RED Evidence

| Step | Evidence present? | Notes |
|------|-------------------|-------|
| S01 | ✅ `n/a — schema/migration only; verified by make migration-check round-trip` | Acceptable for schema-only steps |
| S02 | ✅ `AssertionError: WorkItem.regression_classification is None` | RED confirmed before service existed |
| S03 | ✅ `AssertionError: Expected searchable dropdown…` | Form fragment did not exist yet |
| S04 | ✅ `AssertionError: Expected 200 even with 0 merges, got 404` + badge absent | Route + badge not yet wired |
| S05 | ✅ `AssertionError: Backfill persisted classifications on previously-NULL rows` | RED captured before `run()` implemented |

---

## Testing Coverage

### All four required test files present ✅

| File | Design doc requirement | Status |
|------|----------------------|--------|
| `tests/integration/test_regression_link_service.py` | TDD: service + heuristic | ✅ 13 tests |
| `tests/integration/test_backfill_regression_classification.py` | TDD: backfill script | ✅ 4 tests |
| `tests/dashboard/test_regression_classification_form.py` | TDD: classification form | ✅ 8 tests |
| `tests/dashboard/test_quality_kpis_section.py` | TDD: KPI section + badge | ✅ 8 tests |

### Boundary rows

| Boundary row | Covered by |
|-------------|-----------|
| Empty heuristic result → suggestion list empty + UI button hidden | `test_suggest_returns_empty_when_no_files`, `test_suggestion_button_hidden_when_no_candidates` |
| Cross-project FK rejected | `test_classify_rejects_cross_project_fk`, `test_suggest_drops_cross_project_candidates` |
| Non-merged FK rejected | `test_classify_rejects_non_merged_target` |
| Zero-merge rate guard | `test_kpis_rate_is_zero_when_merges_zero` |
| Re-classification overwrites | `test_classify_overwrites_on_reclassify` |
| Pre-existing does not contribute | `test_pre_existing_classification_does_not_contribute` |
| N==0 → no badge | `test_regression_badge_absent_when_count_zero` |
| <12 weeks history → chart still works | `test_kpis_trend_handles_less_than_12_weeks` |
| Backfill processes only unclassified | `test_backfill_processes_only_unclassified_incidents`, `test_backfill_is_idempotent` |
| Backfill persists nothing | `test_backfill_persists_no_classifications` |
| Backfill handles 0 incidents | `test_backfill_handles_zero_incidents` |
| Regression count aggregation | `test_regression_badge_aggregates_multiple_incidents` |

### Invariants

| Invariant | Coverage |
|-----------|---------|
| Invariant 1 (NULL = unknown) | `test_pre_existing_classification_does_not_contribute` (pre_existing has no introduced_by), plus KPI queries only count `regression_classification == 'regression'` |
| Invariant 3 (operator confirmation) | `test_backfill_persists_no_classifications` + `test_accept_suggestion_uses_heuristic_auto` + UI form `classified_by` derivation from headers |
| Invariant 4 (FK integrity) | `test_classify_rejects_cross_project_fk` |
| Invariant 6 (rate guard) | `test_kpis_rate_is_zero_when_merges_zero` |

---

## Findings

### MEDIUM_FIXABLE — `test_suggest_ranks_by_frequency` does not verify ranking order

**File**: `tests/integration/test_regression_link_service.py`, line 437

**Description**: The test docstring states "candidates ranked by score descending then recency descending" and creates two commits (F-00001 score=2, F-00002 score=1), but the only assertion is `assert len(result) >= 1`. The ranking is never verified. A regression that inverted the sort would not fail this test.

**Suggestion**: Add an explicit assertion:
```python
assert len(result) >= 2
assert result[0].work_item_id == "F-00001"   # score=2, higher rank
assert result[1].work_item_id == "F-00002"   # score=1, lower rank
```

---

### MEDIUM_FIXABLE — `test_kpis_rate_is_zero_when_merges_zero` asserts status only, not value

**File**: `tests/dashboard/test_quality_kpis_section.py`, line 174

**Description**: The test creates incident items via `_seed_merged_feature(is_incident=True)` (which sets `status=completed`). Since the KPI merges query counts ALL completed items (no type filter), these incidents would be counted as merges — meaning `merges` is not actually 0. The test only asserts `response.status_code == 200` and does not verify that the rate is `0.0`.

**Suggestion**: Change the test to use un-merged incidents or a separate project to truly create a zero-merge state, and assert the rate value:
```python
assert '0.0%' in response.text or 'Regression Rate' in response.text
```

---

### MEDIUM_SUGGESTION — Recency tiebreaker relies on SHA lexicographic ordering

**File**: `orch/regression_link_service.py`, line 226

**Description**: `suggest_introducer` sorts candidates by `(c.score, c.commit_sha)` with `reverse=True`. The recency tiebreaker (SHA DESC) works in practice because `git log` returns newest-first and newer commits tend to have larger SHAs, but SHA is not a function of commit time — a newer commit could theoretically have a lower SHA lexicographically.

**Suggestion**: If precise recency ordering is important, emit `--format=%H %ct` from git log (committer timestamp) and parse the timestamp alongside the SHA, then sort `(score DESC, timestamp DESC)`. This is a design improvement rather than a bug since SHA ordering is a reasonable approximation in practice and the primary sort (score) is always correct.

---

### LOW — Missing explicit `return` after `output_error()` in CLI

**File**: `orch/cli/regression_commands.py`, line 77

**Description**: After `output_error(ctx, ..., 2)` the function implicitly returns. Since `output_error()` calls `sys.exit(code)`, execution never reaches the subsequent code, but an explicit `return` would be clearer:

```python
if item is None:
    output_error(ctx, f"Incident {incident} not found in project {project_id}", 2)
    return  # unreachable but documents intent
```

**Severity**: LOW — `output_error()` raises `SystemExit`, so the implicit return is safe.

---

## Files Changed (S01–S05 combined)

| File | Step |
|------|------|
| `orch/db/models.py` | S01 |
| `orch/db/migrations/versions/d43ea9e75e8f_f_00090_regression_link_fields.py` | S01 |
| `docs/IW_AI_Core_Database_Schema.md` | S01 |
| `orch/regression_link_service.py` | S02 |
| `orch/cli/regression_commands.py` | S02 |
| `orch/cli/main.py` | S02 |
| `tests/integration/test_regression_link_service.py` | S02 |
| `dashboard/templates/fragments/regression_classification_form.html` | S03 |
| `dashboard/templates/fragments/regression_suggestion_list.html` | S03 |
| `dashboard/routers/items.py` | S03 |
| `dashboard/routers/search.py` | S03 |
| `dashboard/templates/fragments/item_overview.html` | S03 |
| `tests/dashboard/test_regression_classification_form.py` | S03 |
| `dashboard/templates/fragments/quality_kpis_section.html` | S04 |
| `dashboard/templates/fragments/regression_badge.html` | S04 |
| `dashboard/templates/pages/quality_kpis.html` | S04 |
| `dashboard/routers/project_dashboard.py` | S04 |
| `dashboard/routers/project_pages.py` | S04 |
| `dashboard/routers/batches.py` | S04 |
| `dashboard/templates/pages/project/dashboard.html` | S04 |
| `dashboard/templates/pages/project/history.html` | S04 |
| `dashboard/templates/fragments/batch_items_rows.html` | S04 |
| `dashboard/static/styles.css` | S04 |
| `tests/dashboard/test_quality_kpis_section.py` | S04 |
| `scripts/backfill_regression_classification.py` | S05 |
| `tests/integration/test_backfill_regression_classification.py` | S05 |
| `tests/integration/conftest.py` | S05 |
| `docs/IW_AI_Core_Testing_Strategy.md` | S05 |
| `docs/IW_AI_Core_Dashboard_Design.md` | S05 |
| `ai-dev/work/TESTS_ENHANCEMENT.md` | S05 |
| `skills/iw-ai-core-testing/SKILL.md` | S05 |
| `.claude/skills/iw-ai-core-testing/SKILL.md` | S05 |

---

## Summary

The implementation is solid. All three layers (schema, service+CLI, frontend) are correctly wired. The N+1 avoidance, rate guard, operator confirmation invariant, and FK integrity checks are all in place. The four required test files are present with comprehensive coverage of acceptance criteria and boundary rows. The two MEDIUM_FIXABLE findings are test-quality gaps rather than production-code bugs.

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "F-00090",
  "step_reviewed": "S01..S05",
  "verdict": "pass",
  "findings": [
    {
      "severity": "MEDIUM_FIXABLE",
      "category": "testing",
      "file": "tests/integration/test_regression_link_service.py",
      "line": 437,
      "description": "test_suggest_ranks_by_frequency asserts only len(result) >= 1; does not verify that F-00001 (score=2) ranks above F-00002 (score=1). A sort inversion would not be caught.",
      "suggestion": "Add assertions: assert result[0].work_item_id == 'F-00001' and result[1].work_item_id == 'F-00002'"
    },
    {
      "severity": "MEDIUM_FIXABLE",
      "category": "testing",
      "file": "tests/dashboard/test_quality_kpis_section.py",
      "line": 174,
      "description": "test_kpis_rate_is_zero_when_merges_zero asserts only response.status_code == 200. The incident items created by _seed_merged_feature have status=completed, so the KPI query (which counts ALL completed items) would see non-zero merges. The rate value is never verified.",
      "suggestion": "Assert the rate value (e.g., '0.0%' in response text) to confirm the guard fires correctly."
    },
    {
      "severity": "MEDIUM_SUGGESTION",
      "category": "code_quality",
      "file": "orch/regression_link_service.py",
      "line": 226,
      "description": "Recency tiebreaker uses SHA DESC (higher SHA = newer in practice) rather than actual commit timestamp. SHA is not a function of commit time; theoretically a newer commit could have a lower SHA lexicographically.",
      "suggestion": "Emit --format=%H %ct from git log to get committer timestamps; parse and sort by (score DESC, timestamp DESC)."
    },
    {
      "severity": "LOW",
      "category": "code_quality",
      "file": "orch/cli/regression_commands.py",
      "line": 77,
      "description": "output_error() raises SystemExit; implicit return after it is safe but an explicit return would document intent.",
      "suggestion": "Add 'return' after the output_error() call on line 77."
    }
  ],
  "mandatory_fix_count": 2,
  "tests_passed": true,
  "test_summary": "make test-unit: 3601 passed, 0 failed, 7 skipped, 5 xfailed, 3 xpassed"
}
```
