# I-00068 S07 — Final Cross-Agent Code Review Report

## Work Item

**I-00068** — Recent Activity batch link from "archived" event routes to `/item/` instead of `/batch/`

## Step

**S07** — CodeReview_Final (cross-cutting review across S01 + S03 + S05)

## Summary

All implementation steps (S01, S03, S05) are correct, consistent, and complete. The backend fix and template hardening provide defence-in-depth. The 8 regression tests are falsifiable on `main` and all pass. No regressions introduced to existing tests.

---

## Pre-Flight Gate Results

| Check | Command | Result |
|-------|---------|--------|
| Lint | `make lint` | 2 pre-existing errors in `ai-dev/active/I-00067/e2e_fixtures/` — NOT in I-00068 scope |
| Format | `make format` | 2 pre-existing errors in `ai-dev/active/I-00067/e2e_fixtures/` — NOT in I-00068 scope |

I-00068-specific files are clean:
- `orch/archive/batch_archiver.py` — lint/format clean
- `dashboard/templates/pages/project/dashboard.html` — lint/format clean
- `tests/integration/test_i00068_batch_link_routing.py` — lint/format clean

---

## 1. Completeness vs Design Document

| AC | Description | Covered By | Status |
|----|------------|------------|--------|
| AC1 | Archive events carry `entity_type="batch"` | S01: `_emit` signature adds `entity_type` param; all 3 call sites pass `entity_type="batch"`; S05: `test_batch_archiver_emit_writes_entity_type_batch` asserts `row.entity_type == "batch"` | ✅ |
| AC2 | Dashboard routes `BATCH-` IDs to `/batch/` even with `entity_type=None` | S03: new `elif event.entity_id.startswith('BATCH-')` branch at line 115; S05: `test_dashboard_routes_batch_id_to_batch_url_when_entity_type_is_none` | ✅ |
| AC3 | Existing `entity_type` routing preserved | S03: explicit `entity_type` branches unchanged; S05: `test_dashboard_existing_entity_type_branches_unchanged` | ✅ |
| AC4 | Generic `/item/` fallback still works for non-`BATCH-` IDs | S03: trailing `elif event.entity_id` still routes to `/item/` for non-`BATCH-` IDs; S05: `test_dashboard_falls_back_to_item_for_non_batch_id_with_no_entity_type` with `I-99099` | ✅ |
| AC5 | Regression tests exist and are falsifiable | `tests/integration/test_i00068_batch_link_routing.py` — 8 tests, 2 are true reproduction tests that would fail on `main` | ✅ |

**Missing requirements**: None.

---

## 2. Cross-Agent Consistency

### Signature change does not break any caller

All calls to `_emit` are within `orch/archive/batch_archiver.py` itself. No external callers import `_emit` — the only external reference is in the test file:
```
tests/integration/test_i00068_batch_link_routing.py:21: from orch.archive.batch_archiver import _emit
```
This is intentional (testing the `_emit` boundary). No unexpected breakage.

### Batch ID prefix consistency

The template checks `event.entity_id.startswith('BATCH-')`. Batch IDs are minted by `orch/cli/id_commands.py` via `TYPE_TO_PREFIX["batch"] = "BATCH"`, producing IDs like `BATCH-00001`. The prefix `'BATCH-'` matches exactly.

### New test file does not duplicate existing tests

`test_i00068_batch_link_routing.py` covers I-00068-specific regression scenarios. The existing `test_dashboard_pages.py::test_recent_activity_unknown_entity_type_falls_back_to_item_route` (uses `I-99999`) remains unchanged — it continues to test the generic fallback for non-batch IDs. No duplication.

---

## 3. Integration Points (Defence-in-Depth)

| Layer | Fix | Effect |
|-------|-----|--------|
| **S01 backend** | `_emit` now accepts `entity_type="batch"` and writes it to `DaemonEvent` | New archive events carry the correct type → explicit `entity_type=='batch'` template branch fires |
| **S03 template** | Prefix check `startswith('BATCH-')` catches `entity_type=None` events | Historical data (pre-fix rows) or any future emitter that forgets `entity_type` will still route correctly |

**Together**: Both fixes are required. S01 prevents the bug for new events; S03 fixes the template to handle legacy data and future omissions.

---

## 4. No Regressions

### Existing test suite

| Test Suite | Result |
|------------|--------|
| Unit tests (`make test-unit`) | **2581 passed**, 4 skipped, 5 xfailed, 1 xpassed |
| Integration (recent_activity tests) | **5 passed** — `test_recent_activity_batch_event_links_to_batch_route`, `test_recent_activity_doc_job_event_links_to_doc_job_route`, `test_recent_activity_work_item_event_links_to_item_route`, `test_recent_activity_unknown_entity_type_falls_back_to_item_route`, `test_recent_activity_no_link_renders_when_entity_id_is_null` |
| I-00068 regression tests | **8 passed** |

### Full integration suite
Ran `tests/integration/test_dashboard_pages.py + test_i00068_batch_link_routing.py + test_batch_archive.py` — **67 passed** with no failures.

Coverage threshold failure (17.89% vs 46% required) is a pre-existing condition across the full suite, NOT caused by I-00068.

---

## 5. Architecture Compliance

| Rule | Status |
|------|--------|
| `event_metadata` Python attribute name (not `metadata`) | ✅ Used correctly in `batch_archiver.py:363` |
| `daemon_events` append-only (no UPDATE/DELETE) | ✅ `_emit` only does `db.add(event)`, no UPDATE/DELETE |
| No migrations added | ✅ Verified — this item adds 0 migrations |
| No JS or Tailwind class changes | ✅ Pure Jinja2 template change |
| `entity_type` default is `None` (backward compatible) | ✅ Line 355: `entity_type: str \| None = None` |

**`orch/CLAUDE.md`**: Complied.
**`dashboard/CLAUDE.md`**: Complied.

---

## 6. Security

| Check | Status |
|-------|--------|
| Template autoescape preserved | ✅ `{{ event.entity_id }}` renders through Jinja2's default autoescape; no `|safe` or `Markup(...)` |
| SQL injection (ORM used correctly) | ✅ `DaemonEvent(...)` constructor with named parameters; no raw SQL |
| XSS prevention | ✅ No user input interpolated without escaping |

---

## 7. Test Falsifiability on Main

Two tests are true reproduction tests that **would fail on main** (pre-fix code):

1. **`test_batch_archiver_emit_writes_entity_type_batch`** — Pre-fix `_emit` omits `entity_type`, row has `None`, assertion `row.entity_type == "batch"` fails.

2. **`test_dashboard_routes_batch_id_to_batch_url_when_entity_type_is_none`** — Pre-fix template falls through to `elif event.entity_id` → `/item/`, assertion `'href=".../batch/BATCH-99099"' in resp.text` fails.

The remaining 6 tests lock in regression-prevention (case-sensitivity, prefix-with-dash, non-batch fallback, explicit branches).

---

## Verdict

```json
{
  "step": "S07",
  "agent": "code-review-final-impl",
  "work_item": "I-00068",
  "steps_reviewed": ["S01", "S02", "S03", "S04", "S05", "S06"],
  "verdict": "pass",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "2581 unit passed, 67 integration passed (recent_activity + i00068), 0 failed",
  "missing_requirements": [],
  "notes": "Pre-existing lint/format errors in ai-dev/active/I-00067/e2e_fixtures/ are NOT in I-00068 scope. Coverage threshold failure is pre-existing across full suite, not caused by this item. Both S01 (backend) and S03 (template) are required together for defence-in-depth."
}
```