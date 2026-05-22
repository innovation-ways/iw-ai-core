# I-00102 S02 — Backend Implementation Report

## Step Summary

**Step**: S02 — Backend (register populate, approve auto-refresh)
**Agent**: backend-impl
**Work Item**: I-00102
**Completion**: ✅ complete

## What Was Done

Added the full drift-detection + auto-refresh pipeline to `iw register` and `iw approve`:

1. **`_compute_manifest_digest(steps)`** — pure stdlib helper (hashlib sha256) that canonicalizes the manifest steps array (drop None/empty-string keys, sort_keys, join with `\n`). Placed in `orch/cli/item_commands.py` before `parse_manifest_steps`.

2. **`register`** — after `parse_manifest_steps()`, computes digest and passes `manifest_digest=initial_digest` to `WorkItem(...)`. The digest is only stored on first insert (outside the idempotency early-return). Refactored the workflow-step insertion loop into `_insert_workflow_steps_from_manifest()` helper so register and approve rebuild share identical logic.

3. **`approve`** — before flipping status:
   - Resolves on-disk manifest path (from `design_doc_path` sibling, or `ai-dev/active/<ID>/workflow-manifest.json` relative to `repo_root`).
   - Fails with clear error if manifest file does not exist (AC3 missing-manifest branch).
   - Re-parses via `parse_manifest_steps()` and recomputes digest.
   - Three branches: **no drift** (proceed unchanged), **drift + non-draft** (hard RuntimeError — defensive, ties to AC3), **drift + draft** (rebuild path).
   - Rebuild: count existing rows, delete all, re-insert via `_insert_workflow_steps_from_manifest()`, update `manifest_digest`, emit `manifest_refreshed` daemon event.
   - Pre-I-00102 items with NULL stored digest trigger drift detection on first approve (AC5 backfill safety).

4. **`_insert_workflow_steps_from_manifest(session, project_id, item_id, manifest_steps, ctx)`** — shared helper extracted from `register`'s loop body; returns the row count. Used by both register (first insert) and approve (drift rebuild).

5. **No new CLI flags** — auto-refresh on approve is the only path, per user choice.

6. **Unit test** — `tests/unit/test_item_commands_digest.py` with 10 tests covering AC4 determinism (key order, whitespace, None/empty-string stripping), hex format, order-sensitivity, and step count changes.

## Files Changed

| File | Change |
|------|--------|
| `orch/cli/item_commands.py` | Added `_compute_manifest_digest`, `_insert_workflow_steps_from_manifest`, populate `manifest_digest` in `register`, full drift detection + rebuild in `approve` |
| `tests/unit/test_item_commands_digest.py` | New — 10 unit tests for digest determinism |

## TDD RED Evidence

```
tests/unit/test_item_commands_digest.py::TestComputeManifestDigest::test_digest_is_deterministic_across_key_order PASSED
tests/unit/test_item_commands_digest.py::TestComputeManifestDigest::test_digest_is_deterministic_across_whitespace PASSED
tests/unit/test_item_commands_digest.py::TestComputeManifestDigest::test_digest_changes_when_step_id_changes PASSED
tests/unit/test_item_commands_digest.py::TestComputeManifestDigest::test_digest_changes_when_prompt_path_changes PASSED
tests/unit/test_item_commands_digest.py::TestComputeManifestDigest::test_digest_ignores_none_values PASSED
tests/unit/test_item_commands_digest.py::TestComputeManifestDigest::test_digest_ignores_empty_string_values PASSED
tests/unit/test_item_commands_digest.py::TestComputeManifestDigest::test_digest_is_hex_string PASSED
tests/unit/test_item_commands_digest.py::TestComputeManifestDigest::test_digest_different_for_different_steps_count PASSED
tests/unit/test_item_commands_digest.py::TestComputeManifestDigest::test_empty_steps_array_produces_valid_digest PASSED
tests/unit/test_item_commands_digest.py::TestComputeManifestDigest::test_digest_order_sensitive PASSED

10 passed in 0.24s
```

## Preflight Quality Gates

| Gate | Result |
|------|--------|
| `make format` | ✅ 830 files already formatted |
| `make typecheck` | ✅ no issues found in 274 source files |
| `make lint` | ✅ All checks passed |

## Test Results

```
uv run pytest tests/unit/test_item_commands_digest.py -v --no-cov
10 passed in 0.24s
```

## Acceptance Criteria Coverage

| AC | Status | Notes |
|----|--------|-------|
| AC1 | ✅ | Drift detection + auto-refresh in approve (draft-only); `manifest_refreshed` event; digest update; success message |
| AC4 | ✅ | `_compute_manifest_digest` determinism tests pass (key order, whitespace, None/empty-string) |
| AC5 | ✅ | NULL stored digest → treated as drift → refresh on first approve → stores digest |

## Observations

- The `manifest_digest` column is intentionally excluded from `_WORK_ITEM_CLI_COLUMNS` to avoid crashing against pre-migration DBs. `approve` loads it explicitly via `load_only(*_WORK_ITEM_CLI_COLUMNS, WorkItem.manifest_digest)` — this is the only code path that needs the column at this stage.
- The `manifest_refreshed` daemon event metadata includes `old_digest`, `new_digest`, `old_step_count`, `new_step_count`, and `trigger: "approve"`, matching the shape used by `auto_skip_phantom_qv_gates`.
- The design's §4 "no drift" branch intentionally emits no event; operators only see events when something actually changed.

## Blockers

None.

## Next Step

S03 (Tests) will add the integration reproduction test (`tests/integration/test_item_register_drift.py`) and additional unit tests covering the full approve-auto-refresh and missing-manifest flows.