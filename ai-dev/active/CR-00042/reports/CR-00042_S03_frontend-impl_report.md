# CR-00042_S03_Frontend-Impl Report

## Step Summary

**Work Item**: CR-00042 — Fix Broken "Open full docs" Links in Help Popups
**Step**: S03
**Agent**: frontend-impl

## What Was Done

Updated all 22 help popup partial templates under `dashboard/templates/_partials/help/` to replace hardcoded `href` values with the Jinja2 variable `{{ docs_link }}`.

The `_SLUG_TO_DOC` dict in `dashboard/routers/help.py` (added in S01) maps each help slug to its corresponding `/system/docs/{doc_slug}` URL. The `_render_help_fragment` function passes `docs_link` as template context. All 22 partials now use this dynamic variable — when the help popup is rendered, the correct docs URL (including anchor fragments where applicable, e.g. `queue` → `/system/docs/IW_AI_Core_CLI_Spec#iw-approve`) is substituted.

### Files Changed (22)

| File | Old href | New href |
|------|----------|----------|
| `all_active.html` | `/docs/IW_AI_Core_Daemon_Design.md` | `{{ docs_link }}` |
| `batch_detail.html` | `/docs/IW_AI_Core_Daemon_Design.md#batches` | `{{ docs_link }}` |
| `batches.html` | `/docs/IW_AI_Core_Daemon_Design.md#batches` | `{{ docs_link }}` |
| `code.html` | `/orch/rag/CLAUDE.md` | `{{ docs_link }}` |
| `config.html` | `/docs/IW_AI_Core_Tech_Stack.md` | `{{ docs_link }}` |
| `containers.html` | `/docs/IW_AI_Core_Worktree_Isolation.md` | `{{ docs_link }}` |
| `coverage.html` | `/docs/IW_AI_Core_Tech_Stack.md` | `{{ docs_link }}` |
| `docs.html` | `/docs/implementation/00_INDEX.md` | `{{ docs_link }}` |
| `history.html` | `/docs/IW_AI_Core_CLI_Spec.md` | `{{ docs_link }}` |
| `item_detail.html` | `/docs/IW_AI_Core_Architecture.md` | `{{ docs_link }}` |
| `job_detail.html` | `/docs/IW_AI_Core_Daemon_Design.md` | `{{ docs_link }}` |
| `jobs.html` | `/docs/IW_AI_Core_Daemon_Design.md` | `{{ docs_link }}` |
| `keep_alive.html` | `/docs/IW_AI_Core_Daemon_Design.md` | `{{ docs_link }}` |
| `projects.html` | `/docs` | `{{ docs_link }}` |
| `quality.html` | `/docs/IW_AI_Core_Tech_Stack.md` | `{{ docs_link }}` |
| `queue.html` | `/docs/IW_AI_Core_CLI_Spec.md#approve` | `{{ docs_link }}` |
| `research.html` | `/docs/IW_AI_Core_Architecture.md` | `{{ docs_link }}` |
| `running.html` | `/docs/IW_AI_Core_Daemon_Design.md` | `{{ docs_link }}` |
| `search.html` | `/docs/IW_AI_Core_Architecture.md` | `{{ docs_link }}` |
| `status.html` | `/docs/IW_AI_Core_DB_Setup.md` | `{{ docs_link }}` |
| `tests.html` | `/docs/IW_AI_Core_Tech_Stack.md` | `{{ docs_link }}` |
| `worktrees.html` | `/docs/IW_AI_Core_Daemon_Design.md` | `{{ docs_link }}` |

## Verification

- `grep -r 'href="/docs/' dashboard/templates/_partials/help/` → **0 results** (no old `/docs/` hrefs remain)
- `grep -r 'href="/orch/' dashboard/templates/_partials/help/` → **0 results** (no old `/orch/` hrefs remain)
- `grep -r 'docs_link' dashboard/templates/_partials/help/` → **22 matches** (one per file)

## Quality Gates

- `make format` — ok (no files needed reformatting)
- `make lint` — ok (all checks passed)

## Test Results

```
tests/dashboard/test_help_fragments_present.py — 2 passed
tests/dashboard/test_help_router.py — 35 passed
Total: 37 passed, 0 failed
```

Coverage threshold failure is pre-existing (total 18% < fail-under=46%) — not related to these changes.

## Blockers

None.

## Notes

- `projects.html` previously pointed to `/docs` (the project docs catalogue URL, which was arguably correct). The mapping in `_SLUG_TO_DOC` maps it to `/system/docs/IW_AI_Core_Architecture`. This is the intended behavior per the S01 design — all links now go through the `/system/docs/` route.
- `queue.html` previously had `#approve` anchor; the mapping in `_SLUG_TO_DOC` now uses `#iw-approve` which is the toc-extension slugified ID of the `#### \`iw approve\`` heading in `IW_AI_Core_CLI_Spec.md`, as documented in the CR design.
