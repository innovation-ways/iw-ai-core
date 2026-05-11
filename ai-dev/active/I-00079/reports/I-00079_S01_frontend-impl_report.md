# I-00079 S01 — Frontend-impl Report

## What Was Done

Fixed 7 broken empty-state CTA `primary_href` values across 6 page templates. Every
`empty_state(...)` call was passing `/docs/<Name>.md` which matches no route — the
docs viewer lives at `/system/docs/<key>` (no `.md` suffix, with anchor support). Updated
all values to the correct `/system/docs/<key>` form, matching `help.py`'s `_SLUG_TO_DOC` map.

### Template edits

| File | Line | Old `primary_href` | New `primary_href` |
|------|------|--------------------|--------------------|
| `dashboard/templates/pages/project/queue.html` | 97 | `/docs/IW_AI_Core_CLI_Spec.md` | `/system/docs/IW_AI_Core_CLI_Spec#iw-approve` |
| `dashboard/templates/pages/project/queue.html` | 197 | `/docs/IW_AI_Core_CLI_Spec.md` | `/system/docs/IW_AI_Core_CLI_Spec#iw-approve` |
| `dashboard/templates/pages/project/history.html` | 139 | `/docs/IW_AI_Core_Architecture.md` | `/system/docs/IW_AI_Core_Architecture` |
| `dashboard/templates/pages/project/batches.html` | 137 | `/docs/IW_AI_Core_Daemon_Design.md#batches` | `/system/docs/IW_AI_Core_Daemon_Design#batches` |
| `dashboard/templates/pages/system/all_active.html` | 72 | `/docs/IW_AI_Core_Daemon_Design.md` | `/system/docs/IW_AI_Core_Daemon_Design` |
| `dashboard/templates/docs_library.html` | 129 | `/docs/implementation/00_INDEX.md` | `/system/docs/implementation/00_INDEX` |
| `dashboard/templates/research_library.html` | 149 | `/docs/implementation/00_INDEX.md` | `/system/docs/implementation/00_INDEX` |

### Test seed

Added `TestEmptyStateHrefResolves` class to `tests/dashboard/test_empty_states.py` with
`test_queue_cta_resolves` — renders the queue page, extracts `empty-state__cta-primary` hrefs
via regex, asserts no stale `/docs/` prefix or `.md` suffix, and follows the link to verify
HTTP 200. S03 will extend this to all 6 pages and add the `all_active` system page.

## Grep Sweeps

```bash
grep -rn 'primary_href="/docs/' dashboard/         # 0 results — clean
grep -rn '"/docs/[A-Za-z0-9_./-]*\.md' dashboard/templates/  # 0 results — clean
```

## Preflight

| Gate | Result |
|------|--------|
| `make format` | ok — 669 files already formatted (test file auto-reformatted by ruff before final check) |
| `make typecheck` | ok — no issues in 240 source files |
| `make lint` | ok — `scripts/check_templates.py` + `ruff check` both passed |

## Test Results

```
tests/dashboard/test_empty_states.py
  TestEmptyStateRendering (6 tests) — all PASSED
  TestEmptyStateHrefResolves::test_queue_cta_resolves — PASSED
  Total: 7 passed, 0 failed
```

Coverage failure is pre-existing (total 19% < fail-under 46%) — unrelated to this change.

## Notes for S02/S03

- The `TestEmptyStateHrefResolves` test currently covers only the queue page (2 hrefs —
  one for approved-items, one for drafts). S03 should extend to history, batches,
  docs_library, research_library, and all_active pages with assertions matching the
  specific expected destination per page (e.g. history CTA → `/system/docs/IW_AI_Core_Architecture`).
- No Python routes or DB were touched — this is a pure template + test change.
- `make css` was not run — Tailwind is prebuilt and unaffected by an href-string edit.
