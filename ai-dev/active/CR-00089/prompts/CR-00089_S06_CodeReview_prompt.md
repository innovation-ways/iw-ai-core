# CR-00089_S06_CodeReview_prompt

**Work Item**: CR-00089 -- Fix-Cycle Pipeline Systemic Hardening (I-00113 RCA Follow-up)
**Steps Being Reviewed**: S01 (backend-impl), S02 (backend-impl), S03 (backend-impl), S04 (backend-impl), S05 (tests-impl)
**Review Step**: S06

---

## ⛔ Docker is off-limits

(Standard policy. This step touches no Docker.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This CR adds no migrations.)

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00089 --json`
- `ai-dev/active/CR-00089/CR-00089_CR_Design.md` — design (read AC1–AC6 in full)
- `ai-dev/active/CR-00089/CR-00089_Functional.md` — functional summary
- `ai-dev/work/CR-00089/reports/CR-00089_S01_Backend_report.md`
- `ai-dev/work/CR-00089/reports/CR-00089_S02_Backend_report.md`
- `ai-dev/work/CR-00089/reports/CR-00089_S03_Backend_report.md`
- `ai-dev/work/CR-00089/reports/CR-00089_S04_Backend_report.md`
- `ai-dev/work/CR-00089/reports/CR-00089_S05_Tests_report.md`
- All files listed in S01–S05 reports' `files_changed`

## Output Files

- `ai-dev/work/CR-00089/reports/CR-00089_S06_CodeReview_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading any code, run on all changed files:

```bash
make lint
make format-check
make typecheck
```

NEW violations (not pre-existing on `main`) in the changed files → each is a CRITICAL finding.

## Review Checklist

### 1. S01 — always_in_scope_paths in ProjectConfig + projects.toml

- `ProjectConfig.always_in_scope_paths: list[str]` field exists with `field(default_factory=list)` default.
- `projects.toml` for `iw-ai-core` has `[projects.iw-ai-core.always_in_scope]` with `paths = ["tests/assertion_free_baseline.txt"]`.
- `_build_project_config` defensively handles missing `always_in_scope` key (defaults to `[]`) and invalid `paths` type (warns + defaults to `[]`).
- `ProjectConfig(...)` constructor call includes `always_in_scope_paths=always_in_scope_paths`.
- No other project in `projects.toml` was modified.

### 2. S02 — Scope reconciliation in fix_cycle.py

- At BOTH reconciliation sites (in `run_fix_cycle` and `_complete_fix_cycle`), `project_config.always_in_scope_paths` is appended to `allowed` when `project_config is not None`.
- The append uses `allowed = allowed + project_config.always_in_scope_paths` (list concat, not in-place mutation — `allowed` is a local copy from `_load_allowed_paths`).
- `_load_allowed_paths` itself is unchanged.
- If `run_fix_cycle` required `project_config` threading through from `batch_manager.py`, verify the call site was updated and no other code path was disturbed.
- The scope_block prompt shown to agents also reflects the expanded allowed list (it is built from `allowed` after the append).

### 3. S03 — completed_at guard in step_monitor.py

- In `_check_step_health`, the guard `if run.completed_at is not None: return` appears AFTER `_probe_for_child` and BEFORE `_handle_crashed`.
- The guard is a plain early return with no side effects (no logging, no DB writes, no state mutation).
- `_handle_crashed`, `_probe_for_child`, and all other functions in `step_monitor.py` are unchanged.
- A test with `completed_at=datetime.now(UTC)` confirms `_handle_crashed` is NOT called (AC3).
- A test with `completed_at=None` confirms `_handle_crashed` IS called (regression guard).

### 4. S04 — Smarter cascade reset in fix_cycle.py

- `_GATE_RELEVANT_EXTENSIONS` exists as a module-level `dict[str, frozenset[str]]` constant with all 9 gate names from the design.
- `_DEFAULT_GATE_EXTENSIONS: frozenset[str] = frozenset({".py"})` exists as a companion constant.
- `_gate_is_relevant(gate_name, changed_files)` returns `True` conservatively when `changed_files` is empty.
- `_gate_is_relevant` uses `Path(f).suffix` for extension extraction (not manual string splitting).
- `_gate_is_relevant` returns `True` directly for unknown gate names (not `_DEFAULT_GATE_EXTENSIONS` fallback) — unknown gate = conservative reset.
- `_cascade_reset_upstream_qv_gates` signature has `changed_files: list[str] | None = None`.
- `_peek_cascade_reset_ids` has the same signature change and applies the same filter.
- Both call sites in `_complete_fix_cycle` pass `changed_files=changed_files or []`.
- `_files_changed_by_fix_cycle` is called BEFORE the thrashing preview (not after) so `changed_files` is available for both calls.
- The mutable-default-argument gotcha: `changed_files` parameter defaults to `None`, not `[]`.

### 5. S05 — Tests

- `test_always_in_scope.py` has ≥4 tests covering: append to allowed, no violation for global file, empty default, invalid type default.
- `test_step_monitor_completed_at_guard.py` has ≥3 tests covering: guard fires when `completed_at` set, guard does not fire when `None`, child-check takes priority.
- `test_cascade_smarter_scope.py` has ≥6 tests covering: Python file resets all gates, `.txt`-only change skips lint/format, empty changed_files is conservative, unknown gate is conservative, reset filtering (only assertion-check reset for txt), empty changed_files resets all.
- All assertions are strong (exact equality, not membership or isinstance-only).
- Tests do not hit a real database (no testcontainer fixtures in unit tests).

### 6. Cross-step: scope discipline

`git diff --name-only main..HEAD` must match only:

- `orch/daemon/project_registry.py`
- `projects.toml`
- `orch/daemon/fix_cycle.py`
- `orch/daemon/step_monitor.py`
- `tests/unit/daemon/test_always_in_scope.py`
- `tests/unit/daemon/test_step_monitor_completed_at_guard.py`
- `tests/unit/daemon/test_cascade_smarter_scope.py`
- `ai-dev/active/CR-00089/**` (implicit)
- `ai-dev/work/CR-00089/**` (implicit)

Any other file → CRITICAL scope violation.

Optionally also allowed if S02 required threading: `orch/daemon/batch_manager.py` (call-site update only).

### 7. Architecture compliance

- No new DB models, no schema changes, no migrations.
- No new daemon event types introduced.
- `always_in_scope_paths` is a pure in-memory list — it is not persisted to the DB.
- `_gate_is_relevant` has no DB access.
- `DaemonEvent.metadata` accessed as `event_metadata` in Python (no regression here).

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Guard missing, scope violation, conservative fallback broken, `_peek` not updated to match `_cascade_reset` |
| **HIGH** | Bug in `_gate_is_relevant`, missing reconciliation site in S02, mutable default arg |
| **MEDIUM (fixable)** | Convention drift, weak assertion |
| **LOW** | Nitpick |

## Test Verification

Run targeted tests only:

```bash
uv run pytest tests/unit/daemon/test_always_in_scope.py \
              tests/unit/daemon/test_step_monitor_completed_at_guard.py \
              tests/unit/daemon/test_cascade_smarter_scope.py -v
```

Do NOT run `make test-unit` — that is S11's job.

## Review Result Contract

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "CR-00089",
  "steps_reviewed": ["S01", "S02", "S03", "S04", "S05"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "scope_violations": [],
  "notes": ""
}
```

`verdict`: `pass` iff zero CRITICAL + zero HIGH + zero MEDIUM_FIXABLE findings.
