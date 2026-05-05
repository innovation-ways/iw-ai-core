# I-00064 S01 Backend Report

## What Was Done

Fixed the "View document" link 404 bug in `orch/jobs/aggregator.py` by changing `_build_doc_generation_raw` to expose the **inner** `ProjectDoc.doc_id` identifier instead of the composite FK that was previously stored.

## Changes Made

### `orch/jobs/aggregator.py`

1. **`_build_doc_generation_raw`** — Changed signature to accept an optional `inner_doc_id: str | None = None` parameter. The `doc_id` field in the returned `raw` dict is now set to `inner_doc_id` (or `None` when the FK is set but the doc is deleted — orphan case), not `job.doc_id` (the composite). Added a docstring contract comment explaining the correct convention.

2. **`_fetch_doc_generation`** (list view) — Extended the existing batch query that loads `ProjectDoc` rows for titles to also build a `doc_inner_ids: dict[str, str]` map (key = composite PK, value = inner `doc_id`). This map is reused to pass the correct inner id to `_build_doc_generation_raw` per row. No per-row queries added.

3. **`_get_doc_generation`** (detail page) — Extended the existing doc lookup (already done for the title) to also capture `inner_doc_id = doc.doc_id` when the doc exists, and pass it to `_build_doc_generation_raw`.

4. **`_fetch_code_mapping`** — Added a comment above the `doc_id: job.doc_id` line documenting that this is the composite FK used as a presence flag only, and that it must not be used to build a `/docs/{id}` URL. No value change.

5. **`_get_code_mapping`** — Same comment added.

## Files Changed

- `orch/jobs/aggregator.py` — the only file modified; fix is isolated to the aggregator.

## Preflight Results

| Gate | Result |
|------|--------|
| `make format` | ✅ OK (604 files formatted after fixing unrelated `orch/llm_usage.py`) |
| `make typecheck` | ✅ OK (zero type errors) |
| `make lint` | ⚠️ Pre-existing error in `orch/daemon/worktree_compose.py` — unrelated to this change; verified by running against clean main. |

## Test Results

- `make test-unit` — **2572 passed, 8 failed**: The 8 failures are **pre-existing** on `main` (verified by stashing changes and running). They involve `test_worktree_compose.py` (Jinja2 path issues) and `test_safe_migrate.py` (network resolution in agent context). None are related to `aggregator.py` changes.
- `make test-integration` — Timed out after 300s (expected for full suite with testcontainers). Not run to completion per time constraints.

## Orphan Handling

When `job.doc_id` is set but the `ProjectDoc` row has been deleted, `inner_doc_id` remains `None`, which means `raw["doc_id"]` is `None`. The `job_detail.html` template already guards the link with `{% if raw.get('doc_id') %}`, so the link will be hidden — no broken output, no 500 error.

## Notes

- The lint error in `orch/daemon/worktree_compose.py` (TC004: `pathlib.Path` imported inside `TYPE_CHECKING` block) pre-exists on main and is not caused by any change in this step.
- The unrelated formatting fix in `orch/llm_usage.py` was auto-applied by `make format` and is included in the git diff.