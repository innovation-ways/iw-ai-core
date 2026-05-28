# I-00116_S01_Backend_prompt

**Work Item**: I-00116 — Daemon marks code-review step as PID-dead when reviewer exits without `iw step-done`; downstream review chain loops unboundedly
**Step**: S01
**Agent**: Backend

---

## ⛔ Docker is off-limits

Standard policy. You are not modifying any docker config in this step.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This step does NOT add a migration.

## Scope (`allowed_paths`)

You MAY only modify `orch/daemon/step_monitor.py`. The workflow manifest's `scope.allowed_paths` declares the full item-level allowlist; for THIS step you stay within just the single file. Edits outside that single file will be flagged by S02.

## Input Files

- **Runtime step state**: `uv run iw item-status I-00116 --json`
- **Design** (read first): `ai-dev/active/I-00116/I-00116_Issue_Design.md` — especially "Root Cause Analysis" §1 and "Fix Plan" S01 row
- **Reference**: I-00113's `_probe_for_child` work in `orch/daemon/step_monitor.py:251-314` (your helper sits alongside it)
- **Reference report**: `ai-dev/active/I-00113/I-00113_Issue_Design.md` (the design that added the existing PID-dead protections this step extends)

## Output Files

- Source change: `orch/daemon/step_monitor.py`
- Step report: `ai-dev/active/I-00116/reports/I-00116_S01_Backend_report.md`

## Context

The daemon's `_check_step_health` declares a step crashed when the wrapper PID is dead AND `_probe_for_child` returns False. For `code_review` step types, the agent's verdict report file on disk is the authoritative signal that the agent did its work — even when the agent forgot to call `iw step-done`. Your job: introduce a recovery path so the daemon consults that artifact before declaring crash.

## Requirements

### 1. Add `_try_recover_completed_review_step(db, run, project_id, now)` to `orch/daemon/step_monitor.py`

Place it next to `_probe_for_child`. Signature:

```python
def _try_recover_completed_review_step(
    db: Session,
    run: StepRun,
    project_id: str,
    now: datetime,
) -> bool:
    """Return True if the run was successfully recovered from an on-disk report.

    Only applies to ``run.step_type in ('code_review', 'code_review_final')``.
    Looks for ``ai-dev/active/<work_item_id>/reports/<work_item_id>_<step_id>_*_report.md``
    with mtime > ``run.started_at``. Parses the JSON contract block. If verdict
    is recognised, persists the recovery via the same path ``iw step-done`` uses
    (i.e. mark the step ``completed`` with a per-agent verdict, OR ``needs_fix``
    when verdict='fail' and ``mandatory_fix_count > 0``). Records a DaemonEvent
    of type ``step_run_recovered_from_report``. Returns True on success, False
    if no report is found / the report is malformed / the step type is not a
    review type (caller falls through to ``_handle_crashed``).
    """
```

Implementation notes:
- Use `glob.glob(f"ai-dev/active/{run.work_item_id}/reports/{run.work_item_id}_{run.step_id}_*_report.md")` (relative to project root — use the project's worktree root from `project_config`, NOT the daemon's cwd).
- Require `os.path.getmtime(report_path) > run.started_at.timestamp()` so a stale report from a prior run doesn't accidentally satisfy the guard.
- Parse the JSON contract block by finding the first ```` ```json ```` fenced block in the markdown and `json.loads`-ing it. If parse fails or required keys (`verdict`, `mandatory_fix_count`) are missing, return False.
- Recognised verdicts: `pass` → mark `completed`. `fail` with `mandatory_fix_count > 0` → mark `needs_fix`. Anything else → return False.
- Log `INFO orch.daemon.step_monitor: I-00116 recovered run %s step=%s/%s from report=%s verdict=%s` with `%`-style placeholders.

### 2. Wire `_try_recover_completed_review_step` into `_check_step_health`

After `_probe_for_child(run.pid)` returns False, AND BEFORE `_handle_crashed(...)`:

```python
if not _probe_for_child(run.pid):
    if _try_recover_completed_review_step(db, run, project_id, now):
        return
    _handle_crashed(db, run, project_id, now, project_config)
    return
```

Do NOT touch the existing `_probe_for_child` body (that's I-00113's territory).

### 3. Emit a DaemonEvent on successful recovery

Type: `step_run_recovered_from_report`. Payload (in `event_metadata`, NOT `metadata` — SQLAlchemy reserves it; see CLAUDE.md "Critical Rules"):

```python
{
    "work_item_id": run.work_item_id,
    "step_id": run.step_id,
    "step_run_id": run.id,
    "report_path": str(report_path),
    "report_mtime_iso": datetime.fromtimestamp(os.path.getmtime(report_path), UTC).isoformat(),
    "verdict": parsed["verdict"],
    "mandatory_fix_count": parsed.get("mandatory_fix_count", 0),
}
```

### 4. RED → GREEN

Before editing, run the reproduction test from the design (it does not exist yet — S07 owns the file). You cannot run it now; instead capture the RED reasoning in your report's `tdd_red_evidence`:

> "Pre-fix `_check_step_health` calls `_handle_crashed` unconditionally when `_probe_for_child` returns False, regardless of step_type or on-disk report presence. The S07 reproduction test will fail with `_handle_crashed.assert_not_called()` raising AssertionError because crashed.called is True."

### 5. Post-edit gate (MANDATORY)

After your final edit:

```bash
make format-check
make lint
```

Fix any violation YOUR edits introduced before exit (`uv run ruff format <file>` for format, targeted edit for lint). Closing these now prevents the next review cycle from burning a fix cycle on a trivial gate failure.

## Project Conventions

- SQLAlchemy 2.0 `Mapped[]` style, sync session (see `orch/CLAUDE.md`).
- `psycopg` v3, not psycopg2.
- `DaemonEvent.metadata` is named `event_metadata` in Python (CLAUDE.md Critical Rule).
- `%`-style format-filter calls in logger (NEVER `.format()` or f-strings inside logger calls).
- Use `datetime.now(UTC)`, not `datetime.utcnow()`.

## Constraints

- Touch ONLY `orch/daemon/step_monitor.py`.
- Do NOT modify `_probe_for_child` or `_has_agent_cmdline` (those are I-00113's contract).
- Do NOT modify `_handle_crashed` itself; only add a sibling helper and a callsite.
- Do NOT touch any test file — S07 owns tests.
- Do NOT touch `orch/daemon/fix_cycle.py` or `batch_manager.py` — S03 owns those.

## Step Done Contract

When complete, your report MUST contain a JSON block with:
```json
{"step": "S01", "agent": "Backend", "work_item": "I-00116",
 "files_changed": ["orch/daemon/step_monitor.py"],
 "tests_run": "see RED evidence — S07 owns test files",
 "tdd_red_evidence": "...the explanation from §4...",
 "post_edit_gates": {"make format-check": "pass", "make lint": "pass"},
 "notes": "..."}
```

After writing the report, call `iw step-done S01 --report ai-dev/active/I-00116/reports/I-00116_S01_Backend_report.md`. **DO NOT exit without calling `iw step-done`** — the entire reason this incident exists is that reviewer agents forgot to do this. If you encounter a blocker, call `iw step-fail` with the reason; do not exit silently.
