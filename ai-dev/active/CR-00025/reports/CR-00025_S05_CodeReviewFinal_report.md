# CR-00025 S05 — Final Cross-Layer Code Review

**Reviewer**: code-review-final-impl
**Step**: S05
**Work Item**: CR-00025
**Verdict**: **pass**

---

## What Was Done

Cross-layer review of all CR-00025 implementation from S01 (backend) and S03 (tests).
Verified: AC1–AC5 coverage end-to-end, transaction integrity, archive-survival behaviour,
no agent-facing surface change, docs synced, no regressions, style conventions.
Ran full quality gate: `make quality`, `make test-unit`, and targeted integration tests.

---

## Files Changed (from S01 + S03)

| File | Change |
|------|--------|
| `orch/evidences.py` | Created — `ingest_phase_from_disk` helper |
| `orch/config.py` | Added `evidence_max_bytes` field + `IW_CORE_EVIDENCE_MAX_BYTES` env-var |
| `orch/cli/item_commands.py` | Hooked `ingest_phase_from_disk` in `approve` |
| `orch/cli/step_commands.py` | Hooked `ingest_phase_from_disk` in `step_done` for `browser_verification` |
| `tests/integration/test_evidences_ingest.py` | Created — 10 helper-level tests |
| `tests/integration/test_evidences_lifecycle.py` | Created — 5 CLI-level integration tests |
| `docs/IW_AI_Core_Database_Schema.md` | Added CR-00025 ingestion note (line 763–764) |
| `CLAUDE.md` | Added Quick Navigation row for Evidences ingestion |

---

## Quality Gate Results

| Gate | Result |
|------|--------|
| `make lint` (ruff) | PASS — All checks passed |
| `make quality` (format-check) | PASS — 449 files already formatted |
| `make typecheck` (mypy) | PASS — Success: no issues found in 192 source files |
| `make test-unit` | 1903 passed, 2 skipped, 12 errors (pre-existing errors in `test_db_identity.py` unrelated to CR-00025 — verified by S02 and by checking `git stash` baseline) |
| `tests/integration/test_evidences_ingest.py` | 10/10 PASSED |
| `tests/integration/test_evidences_lifecycle.py` | 5/5 PASSED (including AC5 post-archive regression) |

---

## AC Traceability (AC1–AC5)

### AC1: `iw approve` ingests pre evidences
- **Implementation**: `orch/cli/item_commands.py:498-507` — `ingest_phase_from_disk(phase=EvidencePhase.pre, step_id=None)` inside `with get_session()` block before status flip commit
- **Test**: `tests/integration/test_evidences_lifecycle.py::TestApproveIngestsPreEvidences::test_approve_ingests_pre_2_files_png_and_yaml` — asserts 2 rows, SHA256, content_type, size_bytes

### AC2: `iw step-done` ingests post evidences only for browser_verification
- **Implementation**: `orch/cli/step_commands.py:340-351` — guarded by `if step.step_type == StepType.browser_verification:`, calls `ingest_phase_from_disk(phase=EvidencePhase.post, step_id=step_id)`
- **Test positive**: `TestStepDoneIngestsPostEvidences::test_step_done_browser_verification_ingests_post` — asserts 1 post row with step_id
- **Test negative**: `TestStepDoneIngestsPostEvidences::test_step_done_implementation_does_not_ingest` — asserts 0 post rows for implementation step

### AC3: Idempotent ingestion (upsert)
- **Implementation**: `orch/evidences.py:110-123` — `ON CONFLICT DO UPDATE` on `(project_id, work_item_id, phase, filename)`
- **Test**: `TestIngestPhaseFromDiskIdempotentUpsert::test_ingest_twice_overwrites_content_and_size_bytes` + `test_upsert_updates_step_id_when_step_id_changes`

### AC4: Hard-fail on oversize, transaction rolled back
- **Implementation**: `orch/evidences.py:94-95` — raises `EvidenceTooLargeError` before any rows written; `orch/cli/item_commands.py:506-507` and `orch/cli/step_commands.py:350-351` catch it and call `output_error()` which exits without committing
- **Test helper-level**: `TestIngestPhaseFromDiskOversize::test_oversize_raises_evidence_too_large_error_no_rows_inserted` — asserts 0 rows after rollback
- **Test CLI-level**: `TestApproveOversizeRollback::test_approve_oversize_keeps_status_draft_no_rows` — asserts exit_code != 0, status stays draft, 0 rows

### AC5: Post-archive visibility (regression guard for CR-00020 gap)
- **Implementation**: `work_item_evidences` stores bytes in DB; `archive_work_item(cleanup=True)` deletes FS but DB survives; `_list_evidences` (`dashboard/routers/items.py:700`) reads DB-first
- **Test**: `TestPostArchiveVisibilityRegression::test_evidences_visible_after_archive_cleanup` — full approve → step-done → `archive_work_item(cleanup=True)` → `_list_evidences` returns 2 rows from DB after `ai-dev/active/<id>/` is gone; SHA256 assertions confirm byte-identical content

### AC6–AC8: Deferred to S12 (backfill script)
- Status noted as "deferred to S12"; not failing this review on their absence

---

## Transaction Integrity (CRITICAL) — VERIFIED ✅

### `approve` path
- `with get_session() as session:` opens transaction (item_commands.py:481)
- `ingest_phase_from_disk(...)` runs at line 498 inside the `with` block
- If it raises `EvidenceTooLargeError`, caught at line 506 → `output_error()` → raises `click.exceptions.Exit`
- `get_session()` context manager rolls back on `BaseException` (session.py:109-110)
- If no exception: implicit `session.commit()` at exit of `with` block (session.py:108) persists both status flip and ingested rows atomically

### `step_done` path
- `with get_session() as session:` opens transaction (step_commands.py:288)
- `ingest_phase_from_disk(...)` runs at line 342 inside the `with` block
- `session.flush()` at line 363 precedes the implicit commit
- Same rollback semantics apply

---

## Archive Survival (AC5) — VERIFIED ✅

The regression test (`test_evidences_lifecycle.py:381-544`) exercises the **real** `archive_work_item` from `orch/archive/archiver.py`:

1. Creates real git repo with `ai-dev/active/<item_id>/` structure
2. Runs `iw approve` (pre ingested via real CLI)
3. Runs `iw step-done` (post ingested via real CLI)
4. Calls `archive_work_item(cleanup=True)` — real archiver, not a stub
5. Confirms `ai-dev/active/<id>/` is deleted (`assert not pre_dir.exists()`)
6. Calls `_list_evidences` (the real dashboard helper) with `worktree_path=None`
7. Asserts DB rows returned for both phases
8. Uses SHA256 to confirm byte-identical content preserved in DB

---

## No Agent-Facing Surface Change — VERIFIED ✅

- `iw approve` and `iw step-done` argument signatures unchanged — no new flags
- Exit codes for success path unchanged
- `validate_browser_evidence_present` still exists and guards `iw step-done`
- qv-browser skill prompts and `validate_browser_evidence_present` work as before for existing purpose

---

## Documentation Consistency — VERIFIED ✅

- `CLAUDE.md` Quick Navigation row 22: `Evidences ingestion (CR-00025) | orch/evidences.py · hooks in orch/cli/item_commands.py (approve) and orch/cli/step_commands.py (step-done)` — matches actual file paths
- `docs/IW_AI_Core_Database_Schema.md` lines 763–764: "Ingestion pipeline implemented in CR-00025 — see orch/evidences.py. The `iw approve` command ingests pre-evidences..."
- Design doc File Manifest lists all actual changed files

---

## No Regressions — VERIFIED ✅

- Existing `tests/integration/test_work_item_evidence.py` (18 tests) still passes — model-level CRUD/UNIQUE/FK tests unaffected
- `_list_evidences` and `item_evidence_file` at `dashboard/routers/items.py:700,1238,1255` unchanged at source level
- No changes to dashboard templates or htmx fragments

---

## Style and Conventions — VERIFIED ✅

- SQLAlchemy 2.0 style maintained (`Mapped[]`, `select()`, `session.execute(Insert(...))`)
- psycopg v3 driver: `postgresql+psycopg://` in config.py and session.py
- No new external dependencies — all imports are stdlib or already-in-tree
- Imports placed at top of files (no scattered local imports)
- `EvidenceTooLargeError` at `orch/evidences.py:34-44` follows project exception conventions
- S04 found a formatting violation (single quotes `'rb'` on line 91) — **FIXED** before this review; `make quality` now passes

---

## Findings

| Severity | Issue | Status |
|----------|-------|--------|
| CRITICAL | AC1–AC5 not satisfied end-to-end | **Resolved** — all ACs covered with impl + test |
| HIGH | Formatting violation in `orch/evidences.py` (S04) | **Resolved** — `uv run ruff format orch/evidences.py` applied |
| MEDIUM (suggestion) | `test_non_file_entries_ignored` skipped on non-Linux (symlink platform variation) | **Known** — acceptable, documented in test |
| LOW | S04 noted test file naming discrepancy (report mentioned `tests/unit/test_evidences_ingest.py` but file is `tests/integration/test_evidences_ingest.py`) | **Informational** — file correctly placed in integration suite |

---

## Review Result

```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
  "work_item": "CR-00025",
  "verdict": "pass",
  "findings": [],
  "mandatory_fix_count": 0,
  "ac_traceability": {
    "AC1": {"impl": "orch/cli/item_commands.py:498-507", "test": "test_evidences_lifecycle.py::TestApproveIngestsPreEvidences::test_approve_ingests_pre_2_files_png_and_yaml"},
    "AC2": {"impl": "orch/cli/step_commands.py:340-351", "test": "test_evidences_lifecycle.py::TestStepDoneIngestsPostEvidences (positive + negative)"},
    "AC3": {"impl": "orch/evidences.py:110-123 (ON CONFLICT DO UPDATE)", "test": "test_evidences_ingest.py::TestIngestPhaseFromDiskIdempotentUpsert"},
    "AC4": {"impl": "orch/evidences.py:94-95 + item_commands.py:506-507 + step_commands.py:350-351", "test": "test_evidences_ingest.py::TestIngestPhaseFromDiskOversize + test_evidences_lifecycle.py::TestApproveOversizeRollback"},
    "AC5": {"impl": "work_item_evidences table + archive_work_item + _list_evidences DB-first read", "test": "test_evidences_lifecycle.py::TestPostArchiveVisibilityRegression::test_evidences_visible_after_archive_cleanup"},
    "AC6": {"status": "deferred to S12"},
    "AC7": {"status": "deferred to S12"},
    "AC8": {"status": "deferred to S12"}
  },
  "tests_passed": true,
  "test_summary": "15 integration tests (10 helper + 5 CLI) passed; 1903 unit passed (pre-existing errors in test_db_identity.py, unrelated to CR-00025)",
  "notes": "S04 CRITICAL finding (orch/evidences.py formatting violation) was fixed before this review. make quality now passes. Transaction integrity confirmed: ingest_phase_from_disk runs inside caller's get_session() transaction; BaseException rollback in session.py:109-110 ensures atomicity of status flip + ingestion."
}
```