# CR-00025 S02 — Code Review of S01 (Backend Ingestion + CLI Hooks)

**Reviewer**: code-review-impl
**Step reviewed**: S01 (backend-impl)
**Work item**: CR-00025
**Verdict**: **pass**

---

## Summary

S01 correctly implements the evidence-ingestion pipeline. All checklist items verified. The implementation closes the gap left by CR-00020's S03 des coping.

---

## Checklist Findings

### 1. Transaction Scope — CRITICAL ✅

`get_session()` rolls back on `BaseException` (session.py:109-110). Both ingestion calls are inside the same `with get_session() as session:` block as the status flip:

- **`approve`** (item_commands.py:496-508): status flip at line 496, `ingest_phase_from_disk` at 501-508, `session.flush()` at 512. If `EvidenceTooLargeError` is raised, the session rolls back and the work item stays in `draft` — AC4 satisfied.

- **`step_done`** (step_commands.py:340-351): browser_verification branch fires `ingest_phase_from_disk` at 342-349 inside the same session block opened at line 288. If it raises, the session rolls back and the step/completed_at state is not committed.

### 2. `ingest_phase_from_disk` Correctness ✅

| Requirement | Status |
|---|---|
| Signature: `(session, project_id, work_item_id, phase, root, step_id=None, max_bytes=None)` | ✅ |
| Returns `int` (count of upserted rows) | ✅ line 118 |
| No `session.commit()` call | ✅ caller owns boundary |
| Skips non-regular-file entries (subdirs, symlinks) | ✅ `if not entry.is_file(): continue` |
| Tolerates missing dir + empty dir without raising | ✅ lines 75-76: returns 0 |
| Hard-fails on oversize via `EvidenceTooLargeError` | ✅ line 86, not silently skipped |
| PostgreSQL `INSERT ... ON CONFLICT DO UPDATE` | ✅ lines 90-115 using correct constraint columns |
| MIME type for `.yaml` / `.yml` registered | ✅ lines 23-24 |

### 3. CLI Hook Correctness ✅

- **`approve`** (item_commands.py:490-510): fires before `session.flush()` (line 512). Uses `repo_root` from CLI ctx (line 490, 499). Error exits via `output_error` without leaving status in `approved`. ✅
- **`step_done`** (step_commands.py:340-351): guards with `if step.step_type == StepType.browser_verification:` (line 340) — equality check, not string match. Passes `step_id` (string, e.g. "S11") not `step.id` (UUID). Uses `Path.cwd()` (worktree root) for `root` arg. ✅

### 4. Config Knob ✅

- `IW_CORE_EVIDENCE_MAX_BYTES` default: 5 MiB (evidences.py:44, config.py:172)
- Read via `os.getenv` + `int()` conversion with clear `ValueError` on bad values (evidences.py:42-50)
- Wired into `_default_max_bytes()` called from `ingest_phase_from_disk` when `max_bytes is None` (line 72)

### 5. No Agent-Facing Surface Change ✅

- `validate_browser_evidence_present` still exists (step_commands.py:54-86) and guards `iw step-done`
- `approve` and `step-done` argument signatures unchanged — no new flags

### 6. Documentation Sync ✅

- `CLAUDE.md` Quick Navigation row 22: `Evidences ingestion (CR-00025) | orch/evidences.py · hooks in orch/cli/item_commands.py (approve) and orch/cli/step_commands.py (step-done)`
- `docs/IW_AI_Core_Database_Schema.md` line 761: mentions CR-00025 wires up the ingestion

### 7. No New External Dependencies ✅

Imports: `mimetypes`, `os`, `pathlib`, `dataclasses` (stdlib), SQLAlchemy, `orch.config`, `orch.db.models`. No new deps introduced.

### 8. Project Conventions ✅

- SQLAlchemy 2.0 `Mapped[]`-aware queries throughout
- psycopg v3: `postgresql+psycopg://` in config.py:54, 74
- `output_error` / `click.exceptions.Exit` flow consistent with existing commands

---

## Test Results

| Check | Result |
|---|---|
| `make test-unit` | 1915 passed, 2 skipped |
| `make lint` | All checks passed |
| `make typecheck` | Success: no issues found in 192 source files |
| `make format-check` | 447 files already formatted |

---

## Findings

No critical or high-severity issues found.

---

## verdict

**pass** — S01 backend implementation is correct and complete.
