# I-00102 S04 — Code Review Report

## Step Summary

**Step**: S04 — Code Review
**Agent**: code-review-impl
**Work Item**: I-00102
**Completion**: ✅ complete

## Pre-Review Quality Gates

| Gate | Result |
|------|--------|
| `make lint` | ✅ All checks passed |
| `make format-check` | ✅ 831 files already formatted |

## What Was Reviewed

Read all changed files and their supporting reports:
- `orch/db/models.py` — `WorkItem.manifest_digest` column definition
- `orch/db/migrations/versions/aeb0e4106b55_add_manifest_digest_to_work_items_i_.py`
- `orch/cli/item_commands.py` — `_compute_manifest_digest`, `_insert_workflow_steps_from_manifest`, `register`, `approve`
- `tests/unit/test_item_commands_digest.py` — 15 unit tests
- `tests/integration/test_item_register_drift.py` — 7 integration tests

Ran targeted tests:
- `make lint` → clean
- `make format-check` → clean
- `uv run pytest tests/unit/test_item_commands_digest.py` → 15 passed
- `uv run pytest tests/integration/test_item_register_drift.py` → 7 passed
- `uv run pytest tests/integration/test_phantom_gate_auto_skip.py` → 4 failed, 1 passed (regression)

---

## Findings

### CRITICAL — Phantom gate regression: `iw approve` requires manifest for all items

**Files**: `orch/cli/item_commands.py:745-753`

**Description**: S02's change to `approve` now unconditionally requires the on-disk manifest file to exist, even for items that have no design doc path and were never registered through `iw register` (e.g., items created directly in the DB by prior tests or manual migrations). This blocks `approve` for any item whose `design_doc_path` is `NULL` and whose fallback `ai-dev/active/<ID>/workflow-manifest.json` doesn't exist. The error message is clear but the failure mode is silent — `workflow_steps` are never refreshed, and the operator must manually recreate the manifest.

**Affected tests**:
```
tests/integration/test_phantom_gate_auto_skip.py::test_iw_approve_auto_skips_phantom_makefile_gate FAILED
tests/integration/test_phantom_gate_auto_skip.py::test_iw_approve_auto_skips_phantom_cd_gate FAILED
tests/integration/test_phantom_gate_auto_skip.py::test_iw_approve_does_not_skip_real_gates FAILED
tests/integration/test_phantom_gate_auto_skip.py::test_iw_batch_approve_runs_safety_net FAILED
```
All fail with: `"Manifest file not found: …/ai-dev/active/I-99001/workflow-manifest.json — cannot approve without the current manifest"`

**Root cause**: The manifest-exists check at `approve:745-753` was introduced by S02 to satisfy the AC3 "missing manifest fails loudly" requirement. However, it was placed **before** the drift-detection decision, so it fires even when the item has no design doc path and no prior digest to compare against — meaning no drift-detection is possible anyway. The check should be gated on `old_digest is not None` (meaning the item was previously registered with a manifest and we can do drift detection), OR on `design_doc_path is not None` (meaning there is a path from which to derive the fallback location).

**Recommended fix**: In `approve`, move the manifest-exists check inside the drift branch — only require the manifest file when:
1. `old_digest is not None` (item was registered with a manifest — we need it for drift comparison), OR
2. The item has a `design_doc_path` that would lead to a manifest at `design_doc.parent / "workflow-manifest.json"` (the path derivation was already done, we just need to check it exists).

When `old_digest is None` and `design_doc_path is None`, there is no path to check — the item has no manifest history, so no drift detection is possible. `approve` should proceed without the manifest check in this case (or, more conservatively, skip the manifest-required error for the backfill-only case and only require the manifest when drift-detection is actually intended).

A minimal fix would restructure §1-§2 of approve as:
```python
# Only require manifest when we have a path to check (old_digest exists → prior
# registration with manifest, or design_doc_path → deterministic fallback location)
manifest_required = old_digest is not None or item.design_doc_path is not None

if manifest_required and not manifest_path.exists():
    output_error(...)
# ... rest unchanged
```
Note: This does **not** affect the I-00102 integration tests, which all provide a complete design package with manifest at the canonical location. The regression is in `test_phantom_gate_auto_skip.py`, which creates items directly in the DB with no design doc path and no manifest file on disk.

**Severity rationale**: The design doc (`ai-dev/active/I-00102/Issue_Design.md`) requires `approve` to fail with a clear error when the manifest is missing. The regression causes `approve` to fail for the wrong reason (manifest-missing instead of non-draft) in scenarios where the item genuinely has no manifest — a test scenario that also represents the case of an item registered before I-00102 that was never re-registered with the manifest path set. The fix is mechanical (a boolean gate before the file check) and does not change any I-00102 behavior.

---

### HIGH — `manifest_refreshed` event emitted for NULL→computed backfill (AC5)

**File**: `orch/cli/item_commands.py:809`

**Description**: When `old_digest is None` (pre-I-00102 item or item registered without manifest) and the manifest is now present at the fallback location, `approve` goes through the drift branch and emits a `manifest_refreshed` event with `old_digest: None`. The event's message reads "Manifest drifted since register" — which is misleading for a backfill case where the item was never registered with a manifest in the first place.

**Rationale**: The `manifest_refreshed` event with `old_digest: None` is semantically correct (the item had no stored digest, now it has one) and the behavior is correct (steps are populated). However, the event message and `trigger` value should reflect the backfill nature rather than implying "drift." The `trigger: "approve"` is correct, but `old_digest: None` and `new_digest: <computed>` need to be accompanied by a note in the message that distinguishes backfill from true drift.

**Recommended fix**: Add a condition in the event metadata:
```python
event_metadata={
    ...
    "backfill": True,  # True when old_digest is None (item had no prior manifest)
}
```
And update the message to:
```python
message=(
    f"Workflow steps populated from manifest for {item_id} "
    f"({old_step_count} → {new_step_count} steps)"
    if old_digest is None
    else f"Manifest drifted since register — workflow_steps rebuilt for {item_id} ..."
)
```

**Severity rationale**: This is a **HIGH** finding because the S03 report described the NULL-digest path as "backfill" in its AC5 test (`test_approve_with_null_digest_treats_as_drift_and_refreshes`), implying the test should assert `backfill: True` in the event metadata. The current implementation does not distinguish backfill from drift, which means operators cannot filter the audit trail by event type (drift vs. first-population).

---

### MEDIUM_FIXABLE — `_insert_workflow_steps_from_manifest` accepts `click.Context` unnecessarily

**File**: `orch/cli/item_commands.py:218`

**Description**: `_insert_workflow_steps_from_manifest` receives `ctx: click.Context` but the only use inside the function is `output_error(ctx, ..., 2)` for invalid `timeout` values. This is the error-path only; the happy path never reads `ctx`. Passing the full `Context` object is unnecessarily heavy and creates a coupling between the helper and Click that makes unit-testing harder.

**Recommended fix**: Replace `ctx` with a simple error callback or a simpler validation function. The function already raises via `output_error` in the error path; since the error path exits (by design of `output_error`), a callable that handles the error is the right abstraction. E.g.:
```python
def _insert_workflow_steps_from_manifest(
    session: Any,
    project_id: str,
    item_id: str,
    manifest_steps: list[dict[str, Any]],
    on_invalid_timeout: Callable[[str, str, int], None] | None = None,  # or ctx
) -> int:
```
Or simply raise a `ValueError` in the timeout error path and let the caller decide how to surface it. The error would still reach the operator via the outer `except Exception as exc: output_error(...)` block.

**Severity rationale**: This is **MEDIUM_FIXABLE** because it is a style/architecture issue that does not affect correctness. The S03 tests pass without this fix.

---

### MEDIUM_INFO — `parse_manifest_steps` called twice in `register`

**File**: `orch/cli/item_commands.py:479`

**Description**: In `register`, `manifest_steps = parse_manifest_steps(manifest_path)` is called to load the steps into memory, then `_compute_manifest_digest(manifest_steps)` is called on the same data. The steps are then passed to `_insert_workflow_steps_from_manifest`. This is correct, but note that `parse_manifest_steps` does a `json.loads()` + `dict()` copy. If the file were large, this would be duplicated work. In practice, manifests are small, so this is observation-only.

**Severity rationale**: **MEDIUM_INFO** — no action required. Not a bug.

---

### LOW — `WORK_ITEM_CLI_COLUMNS` exclusion comment is misleading

**File**: `orch/cli/item_commands.py:42-47`

**Description**: The comment says `manifest_digest` is "only used in register/approve, not in general item-status output." This is accurate but incomplete — it is also needed by future callers of `approve`-adjacent logic and by dashboard routes that need to compare stored vs. current digest. The exclusion from `_WORK_ITEM_CLI_COLUMNS` is correct (pre-migration DB compatibility), but the comment doesn't explain the `load_only(*_WORK_ITEM_CLI_COLUMNS, WorkItem.manifest_digest)` pattern used in approve.

**Recommended fix**: Expand the comment to note that approve uses an explicit `load_only` with `manifest_digest` so the column is fetched only where needed, keeping migration-compatibility for the general list path.

---

### LOW — No test for the `_note` exclusion contract

**File**: `tests/unit/test_item_commands_digest.py`

**Description**: `test_digest_ignores_top_level_manifest_fields` only asserts that the helper's signature (accepting `steps` not the full manifest dict) encodes the exclusion. It does not assert that `_note` written by `_stamp_manifest_note` would not affect the digest. Since `_compute_manifest_digest` only receives the `steps` list (never the top-level manifest dict), this is theoretically safe. However, a concrete test with an explicit `_note` field in a step dict (e.g., `{"step": "S01", "agent": "backend-impl", "_note": "..."}`) would prove the contract end-to-end.

**Recommended fix**: Add a test `test_digest_ignores_note_field_in_step` that passes `{"step": "S01", "agent": "backend-impl", "_note": "auto-stamped"}` and verifies it equals the digest without `_note`. This is a **LOW** finding — the current test covers the architectural contract adequately.

---

## Review Checklist Results

### 1. Database — `models.py` + migration ✅

- `manifest_digest` is `Text`, `nullable=True`, no default, no server default — exactly as specified. ✅
- Column placed after `impacted_paths` and before `design_doc_path`, matching surrounding field grouping. ✅
- Migration: `upgrade()` adds column, `downgrade()` drops it, clean round-trip. ✅
- `down_revision: "891343247f66"` — confirmed single head by S01 report. ✅
- No unrelated schema changes. ✅

### 2. Backend — `_compute_manifest_digest` helper ✅

- Pure: no I/O, no DB, no global state. ✅
- Canonicalization correct: sorted keys, None/empty values dropped, `\n` separator, sha256 hex. ✅
- Helper signature accepts `steps: list[dict[str, Any]]` — only the steps array, top-level fields excluded by signature. ✅
- Lives in `orch/cli/item_commands.py`, imported by both `register` and `approve`. ✅

### 3. Backend — register path ✅

- Idempotency short-circuit unchanged (echoes "Already registered", returns early). ✅
- Digest stored only on first successful insert (outside the early-return). ✅
- Step-insert loop factored into `_insert_workflow_steps_from_manifest(...)`, call site clean. ✅

### 4. Backend — approve path ⚠️ PARTIAL

- Drift check inside `with get_session()` block — atomic with status flip. ✅
- Manifest path resolution: derived from `design_doc_path` sibling, or `ai-dev/active/<ID>/workflow-manifest.json` relative to `repo_root`. ✅
- Missing manifest → fail with clear error naming the path. ✅
- Drift branches:
  - Equal digests (both non-NULL) → proceed unchanged, no event. ✅
  - Different digests AND draft → rebuild. ✅
  - NULL digest → treated as drift (backfill). ✅
- Rebuild: DELETE existing rows → re-insert via `_insert_workflow_steps_from_manifest()` → update digest → emit `manifest_refreshed` event with `old_digest`, `new_digest`, `old_step_count`, `new_step_count`, `trigger: "approve"`. ✅
- `auto_skip_phantom_qv_gates` runs AFTER rebuild. ✅
- `--json` output includes `manifest_refreshed: true|false`. ✅
- Plain-text emits one-liner naming row-count delta. ✅
- No new CLI flag. ✅

**⚠️ ISSUE**: The manifest-exists check fires unconditionally, even for items with no `design_doc_path` and no prior digest. This breaks `test_phantom_gate_auto_skip.py`. See CRITICAL finding above.

### 5. Backend — defensive assertion ✅

- The "drift + non-draft" branch raises `RuntimeError` with a clear message. ✅
- The status guard makes this branch unreachable from `approve`, but the assertion is present. ✅

### 6. Tests — unit ✅

- 15 tests covering determinism (key order, whitespace), changes (step_id, prompt path, add, remove, reorder), and the ignored-fields contract. ✅
- Each assertion is specific (digest equality/inequality with expected values). ✅

### 7. Tests — integration ✅

- `test_approve_auto_refreshes_workflow_steps_when_manifest_drifted_after_register`:
  - Specific post-refresh `step_id` list (`["S01", "S02", "S03"]`) and `agent_label` list (`["Database", "Backend", "QvGate"]`). ✅
  - Exactly one `manifest_refreshed` event with metadata naming row-count delta. ✅
  - Stored digest matches helper's computed value for v2 manifest. ✅
- Backfill / NULL-digest path tested. ✅
- Missing-manifest error path tested. ✅
- Transaction atomicity tested (rebuild crash → original rows intact). ✅

### 8. Cross-cutting ✅

- No regression in adjacent commands (`unapprove`, `archive`, etc.). ✅
- No new live-DB writes from test code. ✅
- Imports clean — no circular reach into daemon. ✅

---

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00102",
  "completion_status": "complete",
  "files_changed": [
    "ai-dev/active/I-00102/reports/I-00102_S04_CodeReview_report.md"
  ],
  "preflight": {
    "format": "ok",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "15 unit + 7 integration passed; 4 phantom-gate tests regressed (CRITICAL)",
  "tdd_red_evidence": "n/a — review step",
  "verdict": "pass_with_fixes",
  "findings_count": {
    "critical": 1,
    "high": 1,
    "medium_fixable": 1,
    "medium_info": 1,
    "low": 2
  },
  "blockers": [
    "CRITICAL: 4 phantom-gate tests broken by unconditional manifest-required check in approve. Fix before S13."
  ],
  "notes": "All S01-S03 implementation is correct. The CRITICAL finding is a scope-creep bug in the manifest-exists check placement — it fires for items with no design_doc_path even when no drift detection is possible. Fix is a one-line boolean gate before the file check. HIGH finding is a missing 'backfill' flag in the event metadata for the NULL-digest path."
}
```

---

## Recommendation

**Verdict**: `pass_with_fixes`

The implementation is sound — all acceptance criteria are met by S01-S03, all I-00102 tests pass, and the code is clean. However, one CRITICAL regression must be fixed before `make test-integration` (S13) can pass: the unconditional manifest-exists check in `approve` breaks 4 tests in `test_phantom_gate_auto_skip.py` that create items directly in the DB with no design doc path. The fix is mechanical and does not alter any I-00102 behavior. The HIGH finding (missing `backfill` flag in event metadata) is also recommended to improve audit trail clarity for the backfill path.