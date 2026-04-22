# CR-00017_S06_CodeReview_report

**Work Item**: CR-00017 — Daemon-only migration application
**Step**: S06
**Agent**: code-review-impl
**Completion Status**: complete

---

## What Was Done

Reviewed S05 (backend-impl) implementation against CR-00017 design and S06 review checklist. Files reviewed:

- `orch/daemon/migration_pipeline.py`
- `orch/daemon/merge_queue.py`
- `orch/daemon/batch_manager.py`
- `orch/daemon/state_machine.py`
- `orch/db/models.py`

---

## Files Changed (S05 Backend Implementation)

| File | Change |
|------|--------|
| `orch/daemon/migration_pipeline.py` | New — 3-phase pipeline orchestration |
| `orch/daemon/merge_queue.py` | Modified — Phase 1/2/3 hook integration |
| `orch/daemon/batch_manager.py` | Modified — `IW_CORE_AGENT_CONTEXT=true` in agent env |
| `orch/daemon/state_machine.py` | Modified — new batch item state transitions |
| `orch/db/models.py` | Modified — `BatchItemStatus` enum additions |
| `tests/unit/test_migration_pipeline.py` | New — unit tests for pipeline module |
| `tests/unit/test_merge_queue.py` | Modified — added pipeline mocks |
| `tests/integration/test_batch_manager.py` | Modified — added pipeline mocks |

---

## Checklist Results

### 1. Pipeline Wiring Correctness — PARTIALLY CORRECT (1 MEDIUM finding)

- `is_merge_queue_frozen()` checked at top of `process_merge_queue()` — **PASS**
- `run_pre_merge_dry_run` called before `git squash-merge` (line 139) — **PASS**
- `run_rollback` called only if Phase 2 failed (line 196) — **PASS**
- `run_post_merge_apply` called after squash-merge (line 189) — **PASS**

**MEDIUM finding**: `batch_item.status = BatchItemStatus.merged` at line 172 is set **before** Phase 2 runs (line 189). If Phase 2 fails, the item is left in state `merged` while Phase 3 rollback runs. The status should only be set to `merged` after Phase 2 succeeds.

### 2. `IW_CORE_AGENT_CONTEXT=true` Propagation — **PASS**

Line 505: `agent_env = {**os.environ, "IW_CORE_AGENT_CONTEXT": "true"}` — flag is set only in subprocess env dict passed to `Popen`, never in daemon's own environment.

### 3. State Machine — **PASS**

`migration_invalid` and `migration_rolled_back` present in both `models.py` (line 144-145) and `state_machine.py` (lines 109-110). Transitions defined correctly.

### 4. `daemon_events` Usage — **PASS**

`event_metadata` field used correctly (not `metadata`). `event_type` values `"migration_pipeline"` and `"merge_queue_frozen"` match exactly. Writer pattern correct.

### 5. Frozen Queue Behavior — **PASS**

`set_merge_queue_frozen(active=...)` writes `active` to `event_metadata["active"]`. `is_merge_queue_frozen()` reads and defaults to `False` on empty table.

### 6. Phase 1 Testcontainer Hygiene — **PASS**

Spawned via `testcontainers.postgres.PostgresContainer`. Ryuk labels are a library default (v4.x). Container torn down in `finally` block.

### 7. No Agent-Context Guard Violations — **PASS**

`apply()` / `rollback()` in daemon process do not inherit `IW_CORE_AGENT_CONTEXT`; the flag is set only on child agent processes.

### 8. Error-Path Completeness — **PASS**

Phase 1 failure → `MIGRATION_INVALID`, no merge. Phase 2 failure → rollback runs → on failure freezes queue. Phase 3 failure → queue frozen.

---

## Findings

```json
{
  "verdict": "PASS with 1 MEDIUM",
  "mandatory_fix_count": 0,
  "findings": [
    {
      "severity": "MEDIUM",
      "file": "orch/daemon/merge_queue.py",
      "lines": "172, 189",
      "description": "batch_item.status = BatchItemStatus.merged is set at line 172 BEFORE run_post_merge_apply() at line 189. If Phase 2 fails, the item remains in 'merged' state while Phase 3 rollback runs — inconsistent state.",
      "suggested_fix": "Move 'batch_item.status = BatchItemStatus.merged' to after the apply_result.success check. Only set merged status after Phase 2 succeeds."
    },
    {
      "severity": "LOW",
      "file": "orch/daemon/batch_manager.py",
      "lines": "724-733",
      "description": "_build_agent_env() is defined but never called. Dead code.",
      "suggested_fix": "Remove or integrate into agent launch path."
    },
    {
      "severity": "LOW",
      "file": "orch/daemon/migration_pipeline.py",
      "lines": "61-107",
      "description": "No explicit Ryuk label comment — relies on testcontainers library default. Not self-documenting.",
      "suggested_fix": "Add comment documenting that Ryuk labels are applied automatically by testcontainers v4.x."
    }
  ]
}
```

---

## Test Results (from S05 report)

- `make test-unit`: 1198 passed, 18 warnings
- `make lint`: 2 SIM117 (style, not errors)
- `make test-integration`: 772 passed, 2 failed (pre-existing CR-00014 migration roundtrip failures)

---

## Notes

- The MEDIUM finding is an ordering issue — batch status is set to `merged` before Phase 2 apply completes. This should be fixed before S11 integration tests land to avoid confusion when a batch is "merged" but still has pending rollback.
- The 2 failing integration tests (`test_db_identity_integration.py::TestMigrationRoundtrip`, `test_iw_core_instance_migration.py::test_downgrade_and_upgrade_round_trip`) are pre-existing failures from CR-00014's migration roundtrip, unrelated to CR-00017.
