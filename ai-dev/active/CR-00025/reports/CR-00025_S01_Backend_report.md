# CR-00025 S01 Backend Report

## What Was Done

Implemented the missing evidence-ingestion pipeline specified in CR-00020 but never delivered:

1. **Created `orch/evidences.py`** — pure helper `ingest_phase_from_disk(session, project_id, work_item_id, phase, root, step_id, max_bytes)` with:
   - Upsert via PostgreSQL `ON CONFLICT DO UPDATE` on `(project_id, work_item_id, phase, filename)`
   - MIME sniffing via `mimetypes.guess_type` with YAML registered for `.yaml`/`.yml`
   - Hard-fail `EvidenceTooLargeError` on oversize files (no silent skip)
   - Returns count of rows upserted; does not commit (caller owns transaction)
   - Tolerates missing/empty phase dirs (returns 0)

2. **Added `IW_CORE_EVIDENCE_MAX_BYTES` to `orch/config.py`** — `DaemonConfig.evidence_max_bytes` (default 5 MiB) with env-var override

3. **Hooked `approve`** (`orch/cli/item_commands.py`) — after status flip to `approved`, calls `ingest_phase_from_disk(phase=EvidencePhase.pre, step_id=None)` inside the same transaction; rolls back on `EvidenceTooLargeError`

4. **Hooked `step_done`** (`orch/cli/step_commands.py`) — only for `StepType.browser_verification`, calls `ingest_phase_from_disk(phase=EvidencePhase.post, step_id=step_id)` before `session.flush()`

5. **Updated `docs/IW_AI_Core_Database_Schema.md`** — added CR-00025 note to `work_item_evidences` section

6. **Updated `CLAUDE.md` Quick Navigation** — added Evidences ingestion row

## Files Changed

| File | Change |
|------|--------|
| `orch/evidences.py` | Created (new module) |
| `orch/config.py` | Added `evidence_max_bytes` field + env-var parsing |
| `orch/cli/item_commands.py` | Hooked `ingest_phase_from_disk` in `approve` |
| `orch/cli/step_commands.py` | Hooked `ingest_phase_from_disk` in `step_done` for browser_verification |
| `docs/IW_AI_Core_Database_Schema.md` | Added CR-00025 ingestion note |
| `CLAUDE.md` | Added Quick Navigation row |

## Test Results

- **Existing tests**: 1913 passed (2 pre-existing failures in `test_safe_migrate.py` unrelated to this CR — verified by running with `git stash`)
- **`test_work_item_evidence.py` (integration)**: 18 passed — model/constraint tests unaffected by new hooks
- **Pre-flight**: `make format` ok, `make typecheck` ok, `make lint` ok

## Notes

- `get_session()` context manager rolls back on any exception propagated via `output_error` (which raises `click.exceptions.Exit`), so AC4 (oversize → status stays `draft`) is satisfied
- `step_id` for pre-phase is `None` (as specified); for post-phase it is the concrete step ID string (e.g., `"S11"`)
- No migration written — `work_item_evidences` table already exists from CR-00020
