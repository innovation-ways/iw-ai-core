# I-00100_S01_Backend_prompt

**Work Item**: I-00100 — Cascade thrashing detector is dead code in the production daemon path
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state. Allowed: testcontainers spun up by pytest fixtures, read-only introspection (`docker ps`, `docker inspect`), and `./ai-core.sh` / `make` targets. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step does NOT add or modify any alembic migration. Do not run `alembic upgrade` / `downgrade` / `stamp` against any live DB.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00100 --json`
- `ai-dev/active/I-00100/I-00100_Issue_Design.md` — authoritative spec for this fix
- `orch/daemon/fix_cycle.py` — the file you will modify
- `orch/daemon/batch_manager.py` (read-only) — production caller at line 109 that already passes `project_config`
- `orch/daemon/project_registry.py` (read-only) — `ProjectConfig` dataclass with `cascade_thrashing_threshold` / `cascade_thrashing_jaccard_min`

## Output Files

- `ai-dev/active/I-00100/reports/I-00100_S01_Backend_report.md` — your step report
- Modified: `orch/daemon/fix_cycle.py`

## Context

The thrashing detector `_detect_thrashing` (line 956) is supposed to halt the cascade reset of upstream QV gates when the same trigger step has fired ≥ N cascades with overlapping reset-sets. It works — its unit tests pass — but it never runs in production because the production call chain drops `project_config` before reaching the guard at line 1139.

**Production call chain (read this carefully — the bug is plumbing, not logic):**

1. `batch_manager.py:109` — `fix_cycle.check_active_fix_cycles(db, self.project_id, self.project_config, self.config)` — *passes* `project_config`.
2. `fix_cycle.py:805` — `def check_active_fix_cycles(db, project_id, project_config: ProjectConfig, config: DaemonConfig) -> None:` — annotated `# noqa: ARG001` and **never references** `project_config`.
3. `fix_cycle.py:823` — loop body: `_check_fix_cycle_health(db, cycle, project_id)` — config is not threaded.
4. `fix_cycle.py:866` — `_check_fix_cycle_health` calls `_complete_fix_cycle(db, cycle, project_id, now)` when the fix agent's PID has exited — config is not threaded.
5. `fix_cycle.py:1014` — `_complete_fix_cycle(db, cycle, project_id, now, project_config: ProjectConfig | None = None)` — default `None`.
6. `fix_cycle.py:1139` — `if potential_reset_ids and project_config is not None:` — short-circuits because `project_config` is always `None` here.

The fix is to thread `project_config` through the three intermediate functions so the guard at line 1139 can run.

## Requirements

### 1. Thread `project_config` through `check_active_fix_cycles`

- Remove the `# noqa: ARG001` marker from the `project_config` parameter of `check_active_fix_cycles`. The argument is now used.
- Pass `project_config` into `_check_fix_cycle_health` (see #2).

### 2. Add `project_config` to `_check_fix_cycle_health`

- Update the signature: `def _check_fix_cycle_health(db: Session, cycle: FixCycle, project_id: str, project_config: ProjectConfig) -> None:`.
- Forward `project_config` into the existing `_complete_fix_cycle(...)` call at the end of the function (currently `fix_cycle.py:866`).
- Leave the rest of the function untouched (the timeout / PID-alive paths do not need the config).

### 3. Pass `project_config` to `_complete_fix_cycle`

- The function already has the `project_config: ProjectConfig | None = None` keyword parameter. Pass the now-threaded value into it explicitly.
- Do NOT change `_complete_fix_cycle`'s signature, default, or body — only change the call site so the value actually arrives.

### 4. Do NOT change anything else on this path

- Do NOT alter `_detect_thrashing` (line 956).
- Do NOT alter `_cascade_reset_upstream_qv_gates` (line 869).
- Do NOT alter `_emit_event(..., "cascade_thrashing_detected", ...)` (line 1160).
- Do NOT alter `ProjectConfig` or any unrelated callers of `_complete_fix_cycle`. Other test callers may continue to omit `project_config` (the keyword default stays `None`) — that's intentional, so existing unit tests for `_complete_fix_cycle` keep working.

### 5. Search for sibling drops on the same path

Grep `orch/daemon/fix_cycle.py` for `# noqa: ARG001`. If you find any OTHER unused-parameter marker on a function that is on the production fix-cycle path (caller chain from `batch_manager` → `fix_cycle`), document it in your report's `notes` field but DO NOT fix it in this step — file it as a follow-up for the operator. Scope discipline matters here; widening the scope routinely costs more than the original bug.

## Project Conventions

Read `CLAUDE.md` (root) and `orch/CLAUDE.md`. Key invariants for this step:

- `orch/daemon/` modules use SQLAlchemy 2.0 sync `Session`. The functions you're touching already follow that pattern.
- The daemon's polling cycle calls `check_active_fix_cycles` once per project per tick (see `batch_manager.py:_drive_runtime`). Behaviour-wise, after your change, `project_config` reaches `_complete_fix_cycle` on every tick where a `FixCycle` row exists with `status=in_progress` and its PID has died.
- Never log secrets or env contents from `project_config` (it shouldn't carry any — but defense in depth).

## TDD Requirement

This step is a plumbing fix. The behavioural test that proves the seam works lives in **S03** (`tests-impl`). For S01 you do NOT need to write a new test — the regression net comes in S03 — but you MUST:

1. Before changing anything, run `uv run pytest tests/unit/daemon -v -k thrashing` (or the closest existing thrashing-detector test) and capture the green baseline.
2. After your edit, run the same targeted subset and confirm it stays green. If a unit test broke, your plumbing change is wrong — fix it or roll back and raise a blocker.

For the `tdd_red_evidence` field in your result contract, use `"n/a — pure plumbing fix; behavioural regression test added in S03 by tests-impl"`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`, run in order:

1. `make format` — auto-fix formatting drift. Re-stage if it changes anything.
2. `make typecheck` — must report zero errors on `orch/daemon/fix_cycle.py`. Pre-existing errors elsewhere: note in report, don't ignore your own.
3. `make lint` — must report zero errors. The `# noqa: ARG001` you remove is a known suppression; ruff should now agree the parameter is used.

## Test Verification

Run only the targeted unit tests that exercise the code path:

```bash
uv run pytest tests/unit/daemon/ -v -k "thrashing or fix_cycle"
```

Do NOT run `make test-unit` or `make test-integration` — those are S11 / S12 QV gates and have their own budgets. If you cannot find a narrow target, run `tests/unit/daemon/` only.

## Migration Verification

N/A. This step does not generate or modify any alembic migration.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "I-00100",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["orch/daemon/fix_cycle.py"],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "n/a — pure plumbing fix; behavioural regression test added in S03 by tests-impl",
  "blockers": [],
  "notes": "Any sibling `# noqa: ARG001` drops you noticed on the production path but did NOT fix (document for operator follow-up). Any baseline unit tests that broke and how you resolved them."
}
```
