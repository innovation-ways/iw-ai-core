# I-00100_S05_CodeReview_Final_prompt

**Work Item**: I-00100 — Cascade thrashing detector is dead code in the production daemon path
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01 (backend-impl), S03 (tests-impl)

---

## ⛔ Docker is off-limits

Standard policy. Testcontainers via pytest fixtures are exempt. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Review-only. No alembic commands.

## Input Files

- `uv run iw item-status I-00100 --json`
- `ai-dev/active/I-00100/I-00100_Issue_Design.md`
- `ai-dev/active/I-00100/I-00100_Functional.md`
- All reports under `ai-dev/active/I-00100/reports/I-00100_S01_*.md` through `I-00100_S04_*.md`
- All files in any `files_changed`: at minimum `orch/daemon/fix_cycle.py` and `tests/integration/daemon/test_cascade_thrashing_detector_wiring.py`

## Output Files

- `ai-dev/active/I-00100/reports/I-00100_S05_CodeReview_Final_report.md`

## Context

You are performing the cross-agent final review of I-00100. The fix is small (a 3-call plumbing thread plus a regression test), so cross-cutting issues are unlikely — but the spec is unusually specific. Verify that the production seam end-to-end actually delivers what the design promised.

## Read the Design Document FIRST

- Read the design's **Root Cause Analysis** — it names the exact lines that should change.
- Read **AC1**, **AC2**, **AC3** in full. AC3 specifically requires the negative-control test (no regression for non-thrashing cases).
- Read the **File Manifest** — verify every file it names actually exists and matches expectations.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
make typecheck
```

If any of these report new violations on the changed files, classify as CRITICAL conventions findings.

## Cross-Agent Review Checklist

### 1. End-to-end plumbing matches the spec

Open `orch/daemon/fix_cycle.py` and trace the call chain manually:

1. `check_active_fix_cycles(db, project_id, project_config, config)` — `project_config` no longer has `# noqa: ARG001`, is referenced in the loop body, and is forwarded to `_check_fix_cycle_health`.
2. `_check_fix_cycle_health(db, cycle, project_id, project_config)` — accepts the config and forwards it to `_complete_fix_cycle`.
3. `_complete_fix_cycle(db, cycle, project_id, now, project_config=project_config)` — receives the config; the line-1139 guard `if potential_reset_ids and project_config is not None:` can now succeed.
4. `_detect_thrashing(...)` — reachable; signature unchanged.
5. `_emit_event(..., "cascade_thrashing_detected", ...)` at line 1160 — reachable; metadata shape unchanged.

If any link is broken, file CRITICAL. The whole point of the incident is this chain.

### 2. Behaviour for non-thrashing cases is unchanged

Read the `_complete_fix_cycle` body around line 1124–1240. Confirm:
- When `project_config is not None` AND `_detect_thrashing` returns `False`, the function still calls `_cascade_reset_upstream_qv_gates(...)` and proceeds with the existing cascade reset.
- When `project_config is None` (test callers that omit the kwarg), behaviour is unchanged from before (the guard short-circuits as it always did).

This matches AC3. If S01 inadvertently moved code that runs on the non-thrashing path, flag CRITICAL.

### 3. The regression net covers both AC1 and AC3

Open `tests/integration/daemon/test_cascade_thrashing_detector_wiring.py`:
- Positive test asserts on `event_type == "cascade_thrashing_detected"`, specific `event_metadata` keys, and that the upstream gate's status is unchanged.
- Negative test asserts that no `cascade_thrashing_detected` event fired AND the upstream gate WAS reset.

If either is missing or weak, flag accordingly.

### 4. Functional doc accuracy

Open `I-00100_Functional.md`. It must describe observable behaviour ("a cascade-thrashing event now appears in the dashboard") in plain English with no code references. If it mentions file paths, class names, or SQL, flag MEDIUM_FIXABLE (the functional review skill blocks those).

### 5. Scope discipline

- `files_changed` across S01 + S03 should be exactly two files: `orch/daemon/fix_cycle.py` and the new test. Anything else needs justification in the report's notes. If unjustified, flag HIGH.
- Any sibling `# noqa: ARG001` drops S01 noticed but did NOT fix (documented in S01's notes per its prompt's requirement 5) should be acknowledged here as a follow-up — not fixed in I-00100. If S01 silently widened scope, flag CRITICAL.

### 6. No drive-bys

Read the diff of `orch/daemon/fix_cycle.py` end-to-end. Confirm there are no:
- Unrelated formatting changes
- Renamed variables in unrelated functions
- Added imports that aren't needed by the plumbing fix
- Touched lines outside the call chain documented in S01's prompt

### 7. Tests still pass

```bash
uv run pytest tests/integration/daemon/test_cascade_thrashing_detector_wiring.py -v
uv run pytest tests/unit/daemon/ -v -k "thrashing or fix_cycle"
```

Both must pass. Capture pass/fail counts.

### 8. CLAUDE.md hard rules

Re-read `CLAUDE.md` and `orch/CLAUDE.md`. Confirm:
- No live-DB writes in test code (the test uses the testcontainer-backed `db_session`).
- No `importlib.reload(orch.config)` anywhere.
- No mocking of the database in integration tests.
- `DaemonEvent.metadata` attribute access uses `event_metadata` in Python (gotcha note in `orch/CLAUDE.md`).

## Severity Levels

Standard scale. CRITICAL / HIGH / MEDIUM_FIXABLE trigger a fix cycle.

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "I-00100",
  "step_reviewed": "S01..S04",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file",
      "line": 0,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": "Acknowledge any follow-ups S01 flagged (sibling # noqa drops, etc.) that are intentionally deferred to a separate incident."
}
```
