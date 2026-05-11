# I-00079 S02 — Code Review Report

## What Was Reviewed

S01 (frontend-impl) fixed 7 broken `primary_href` values in 6 page templates that were
pointing empty-state CTAs at the non-existent `/docs/<name>.md` route instead of the
dashboard's doc viewer at `/system/docs/<key>`.

## Files Changed

| File | Change |
|------|--------|
| `dashboard/templates/pages/project/queue.html` | Lines 97 & 197: `/docs/IW_AI_Core_CLI_Spec.md` → `/system/docs/IW_AI_Core_CLI_Spec#iw-approve` |
| `dashboard/templates/pages/project/history.html` | Line 139: `/docs/IW_AI_Core_Architecture.md` → `/system/docs/IW_AI_Core_Architecture` |
| `dashboard/templates/pages/project/batches.html` | Line 137: `/docs/IW_AI_Core_Daemon_Design.md#batches` → `/system/docs/IW_AI_Core_Daemon_Design#batches` |
| `dashboard/templates/pages/system/all_active.html` | Line 72: `/docs/IW_AI_Core_Daemon_Design.md` → `/system/docs/IW_AI_Core_Daemon_Design` |
| `dashboard/templates/docs_library.html` | Line 129: `/docs/implementation/00_INDEX.md` → `/system/docs/implementation/00_INDEX` |
| `dashboard/templates/research_library.html` | Line 149: `/docs/implementation/00_INDEX.md` → `/system/docs/implementation/00_INDEX` |
| `tests/dashboard/test_empty_states.py` | Added `TestEmptyStateHrefResolves::test_queue_cta_resolves` (I-00079 seed test) |

## Pre-Review Lint & Format Gate

- `make lint` — **PASSED** (scripts/check_templates.py + ruff check)
- `make format` — **PASSED** (669 files already formatted)
- No new violations introduced.

## Grep Sweeps

- `grep -rn 'primary_href="/docs/' dashboard/` → **0 results** ✓
- `grep -rn '"/docs/[A-Za-z0-9_./-]*\.md' dashboard/templates/` → **0 results** ✓

## Correctness Check

**All six CTAs fixed, and only those.** Git diff vs `main` shows only `primary_href=`
changes in those 6 files — no other attributes (`slug`, `heading`, `body`, `primary_label`,
`secondary_*`) were touched, no styling changes, no unrelated edits.

**New targets resolve** (reasoned from `system.py:417-420` `_DOC_URL_MAP` construction):
- `/system/docs/IW_AI_Core_CLI_Spec#iw-approve` → key `IW_AI_Core_CLI_Spec` (from `docs/IW_AI_Core_CLI_Spec.md`) ✓
- `/system/docs/IW_AI_Core_Architecture` → key `IW_AI_Core_Architecture` (from `docs/IW_AI_Core_Architecture.md`) ✓
- `/system/docs/IW_AI_Core_Daemon_Design#batches` → key `IW_AI_Core_Daemon_Design` (from `docs/IW_AI_Core_Daemon_Design.md`) ✓
- `/system/docs/IW_AI_Core_Daemon_Design` → key `IW_AI_Core_Daemon_Design` ✓
- `/system/docs/implementation/00_INDEX` → key `implementation/00_INDEX` (CR-00044 subdirectory serving) ✓

## Consistency with `help.py` (AC3)

| Page slug | Empty-state CTA (S01) | help.py `_SLUG_TO_DOC` | Notes |
|----------|----------------------|------------------------|-------|
| `queue` | `/system/docs/IW_AI_Core_CLI_Spec#iw-approve` | `/system/docs/IW_AI_Core_CLI_Spec#iw-approve` | **Exact match** ✓ |
| `history` | `/system/docs/IW_AI_Core_Architecture` | `/system/docs/IW_AI_Core_CLI_Spec` | **Intentional divergence** — CTA label is "How execution works →", not a bug (design doc §Code Changes) |
| `batches` | `/system/docs/IW_AI_Core_Daemon_Design#batches` | `/system/docs/IW_AI_Core_Daemon_Design` | **CTA adds #batches anchor** — accepted as per design doc ✓ |
| `all_active` | `/system/docs/IW_AI_Core_Daemon_Design` | `/system/docs/IW_AI_Core_Daemon_Design` | **Exact match** ✓ |
| `docs` library | `/system/docs/implementation/00_INDEX` | `/system/docs/IW_AI_Core_Dashboard_Design` | **Intentional** — CTA label is "Doc catalogue →", index is the correct target (design doc §Code Changes) |
| `research` library | `/system/docs/implementation/00_INDEX` | `/system/docs/IW_AI_Core_Dashboard_Design` | **Intentional** — same reasoning as docs library ✓ |

No unintended drift. All label-driven target choices match the design documentation.

## Testing

- `make test-unit` → **2744 passed**, 0 failed ✓
- `uv run pytest tests/dashboard/test_empty_states.py -v` → **7 passed** (existing 6 + new `test_queue_cta_resolves`) ✓
- Coverage failure (19% < fail-under 46%) is pre-existing, unrelated to this change.

**Test quality note** (MEDIUM, not a blocker): The new `test_queue_cta_resolves` checks:
1. No stale `/docs/` prefix — `assert not href.startswith("/docs/")`
2. No `.md` suffix — `assert ".md" not in href.split("#")[0]`
3. The resolved path returns HTTP 200 — `followed.status_code == 200`

These are semantics-level assertions scoped to `class="empty-state__cta-primary"`, not bare-substring word searches. The design doc (§TDD Approach) notes the full regression test (all 6 pages + `all_active`) is S03's responsibility; S01's seed test is minimal but correct for what it covers.

## Project Conventions

- Tailwind classes untouched — pure href-string change only.
- Jinja2 `format` filter not touched — no risk of `%`-style violation.
- No migrations, no DB schema changes, no Docker state.

## Security

- No hardcoded secrets, URLs, ports, or credentials introduced. Only relative doc-viewer paths.

---

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00079",
  "step_reviewed": "S01",
  "verdict": "pass",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "7 passed (test_empty_states.py), 2744 passed (make test-unit)",
  "notes": "All 7 CTAs correctly updated. No stale /docs/*.md links remain. Targets resolve per system.py doc map. lint/format clean. S01 added a minimal but semantically correct seed test; S03 will extend coverage to all 6 pages. History CTA intentionally diverges from help.py (per design doc). No migrations, no unrelated changes."
}
```
