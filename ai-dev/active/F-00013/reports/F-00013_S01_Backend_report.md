# F-00013 S01 Backend Report

## What was done

Implemented the automation backend for F-00013: Project-Level Documentation System — Automation (Phase 3).

### Files changed

| File | Change |
|------|--------|
| `orch/db/models.py` | Added `lint_warnings JSONB` and `trigger_reason Text` columns to `DocGenerationJob` |
| `orch/db/migrations/versions/20260413144509_add_doc_lint_warnings.py` | Migration adding `lint_warnings` column |
| `orch/db/migrations/versions/20260413144705_add_doc_job_trigger_reason.py` | Migration adding `trigger_reason` column |
| `orch/doc_service.py` | Added `find_docs_by_source_path()`, upgraded `get_stale_docs()` with git mtime, added `lint_doc_content()`, integrated lint gate into `complete_doc_job()` |
| `orch/daemon/batch_merge_hooks.py` | New file — `trigger_doc_regeneration_on_merge()` post-merge hook |
| `orch/daemon/merge_queue.py` | Wired `trigger_doc_regeneration_on_merge()` after `item_merged` event |
| `orch/cli/doc_commands.py` | Added `docs-check-stale` CLI command |
| `tests/unit/test_doc_automation.py` | New test file with 15 tests covering all new methods |
| `tests/unit/test_doc_job_poller.py` | Fixed `test_complete_doc_job_success` mock (added `doc_id=None`) |

### Implementation details

**1. Migration**: Two Alembic migrations add `lint_warnings JSONB` and `trigger_reason Text` columns to `doc_generation_jobs`.

**2. DocService.find_docs_by_source_path()**: Returns `ProjectDoc` records where any `source_paths` entry matches any changed path. Supports both exact and segment-wise glob matching (e.g., `docs/auth/*` matches `docs/auth/middleware/token.py`).

**3. DocService.get_stale_docs()** (upgraded): Checks git mtime of source files via `git log -1 --format=%ct -- {path}`. Returns `list[tuple[ProjectDoc, str, datetime]]` of stale docs with the changed path and mtime.

**4. DocService.lint_doc_content()**: Editorial lint gate enforcing:
- All categories: frontmatter required + parseable, forbidden phrase check
- `technical`: `## Purpose`, `## Architecture`, code block required
- `functional`: `## Overview`, `## Key Capabilities` required
- `guide`: `## Prerequisites`, `## Steps` required

**5. Lint integration**: `complete_doc_job()` now fetches the associated `ProjectDoc` after job completion and calls `lint_doc_content()`. Warnings are stored in `job.lint_warnings` but `DocStatus` is unchanged.

**6. Post-merge hook**: `trigger_doc_regeneration_on_merge()` in `batch_merge_hooks.py` — called after `item_merged` event, computes changed files via `git diff HEAD^..HEAD --name-only`, matches against `ProjectDoc.source_paths`, creates `DocGenerationJob` records for each matched doc.

**7. CLI**: `iw docs-check-stale PROJECT_ID [--threshold-hours INTEGER]` — exits 0 if all docs current, exits 1 with formatted stale doc table otherwise.

### Test results

```
617 passed, 1 warning in 1.31s
```

All 15 new F-00013 tests pass. One pre-existing test (`test_complete_doc_job_success`) was updated to mock `doc_id=None` to avoid the lint gate path.

### Quality issues (intentional)

- `S607 subprocess.run("git" ...)`: Intentional — git is always in PATH
- `S603 subprocess.run()`: Intentional — `path` comes from trusted DB `source_paths` field, not user input
- `yaml` stub missing: Pre-existing; types-PyYAML installed but mypy needs config update

### Notes

- `trigger_reason` column was added to `DocGenerationJob` model to support automation traceability
- The `S607/S603` warnings in `batch_merge_hooks.py` and `doc_service.py` are intentional (git commands with DB-sourced paths)
- `threshold_hours` parameter kept in `get_stale_docs()` signature for CLI/API compatibility but git mtime supersedes it
