# CR-00087_S03_BackendImpl_prompt

**Work Item**: CR-00087 -- Auto-amend scope violations matching per-project allow-patterns
**Step**: S03
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Allowed exceptions: testcontainers, read-only introspection, `./ai-core.sh`/`make` targets.

If your task seems to require a prohibited command, STOP and raise a blocker.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This step adds NO migration. Do not run alembic commands against the live DB.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00087 --json`.
- `ai-dev/active/CR-00087/CR-00087_CR_Design.md` — Design document.
- `ai-dev/work/CR-00087/reports/CR-00087_S01_BackendImpl_report.md` — S01 report (registry parsing).
- `ai-dev/work/CR-00087/reports/CR-00087_S02_BackendImpl_report.md` — S02 report (`should_auto_amend` helper).
- `orch/daemon/fix_cycle.py` — primary file to modify (target: `_complete_fix_cycle`, ~line 1043).
- `orch/daemon/scope_amendment.py` — read for `amend_allowed_paths` signature.
- `dashboard/routers/actions.py:444` — reference for `scope_amend_and_restart` flow (read-only — what the manual operator endpoint does is what S03 must mirror).
- `docs/IW_AI_Core_Daemon_Design.md` — file to update with new auto-amend pass.
- `.iw-orch.json` (root) — file to add a commented-out example block to.

## Output Files

- `ai-dev/work/CR-00087/reports/CR-00087_S03_BackendImpl_report.md` — Step report

## Context

You are implementing **Step 3** of CR-00087 — the integration step that wires everything from S01 and S02 into the daemon's fix-cycle path.

The target is `orch/daemon/fix_cycle.py:_complete_fix_cycle` (~line 1043). The function currently has an escalation branch (~line 1117) that sets `cycle.status = FixStatus.escalated`, emits `scope_violation_escalation`, and returns — leaving the step in `needs_fix`. Your job is to layer auto-amend on top of that branch, INLINE in the same transaction, without disturbing the existing behaviour for projects that haven't opted in.

The new behaviour (mirroring the manual operator flow in `dashboard/routers/actions.py:scope_amend_and_restart`):

1. Existing escalation logic runs first (unchanged) — sets `cycle.status = escalated`, populates `fix_metadata.scope_violations`, emits `scope_violation_escalation`, calls `db.commit()`.
2. NEW: after that commit, evaluate `should_auto_amend(violations, project_config.auto_amend_allow_patterns, project_config.auto_amend_max_paths)`.
3. On `True`:
   a. Call `amend_allowed_paths(worktree_path, item_id, violations)` (returns an `AmendResult` with `paths_added` and `manifests_updated`).
   b. Emit a new `scope_auto_amended` DaemonEvent with payload:
      ```json
      {
        "step_id": "<step.step_id>",
        "added_paths": [<violations>],
        "manifests_updated": ["<str(p) for p in result.manifests_updated>"],
        "matched_patterns": [<the project's auto_amend_allow_patterns at the time of decision>]
      }
      ```
   c. Create a new `StepRun` mirroring the latest one (run_number incremented; command, worktree_path, cli_tool, timeout_secs copied — match the pattern in `dashboard/routers/actions.py:scope_amend_and_restart` lines 484-493).
   d. Set `step.status = StepStatus.pending`, `step.started_at = None`, `step.completed_at = None`.
   e. If the parent work item is `WorkItemStatus.failed`, transition it to `WorkItemStatus.in_progress` (mirror lines 498-499 of actions.py).
   f. `db.commit()`.
   g. Log a daemon INFO line summarising the auto-amend: `"[<project_id>] Auto-amended scope for <item_id>/<step_id> cycle <n>: added <N> path(s) matching patterns <patterns>"`.
4. On `False`: do NOTHING extra — the step stays in `needs_fix` and today's manual flow remains.

## Requirements

### 1. Locate the auto-amend hook point in `_complete_fix_cycle`

Find `orch/daemon/fix_cycle.py:_complete_fix_cycle` (~line 1043). The existing escalation branch ends with `return  # Do NOT advance the step — operator must intervene` (~line 1151). Insert the auto-amend block IMMEDIATELY BEFORE that return statement, so the auto-amend runs after `cycle.status = escalated` has been committed but before the function returns.

The cleanest factoring is to extract the auto-amend logic into a private helper:

```python
def _try_auto_amend_after_escalation(
    db: Session,
    project_id: str,
    project_config: "ProjectConfig",
    cycle: FixCycle,
    step: WorkflowStep,
    violations: list[str],
    worktree_path: Path,
    now: datetime,
) -> bool:
    """If the project's auto_amend policy allows, apply amend + restart inline.

    Returns True when auto-amend fired (caller can log it), False otherwise.
    All DB mutations are committed inside this helper.
    """
```

This keeps `_complete_fix_cycle`'s body readable; the new branch becomes a single `if` + helper call.

### 2. New DaemonEvent type: `scope_auto_amended`

Use the existing `_emit_event` helper (already used by `_complete_fix_cycle` for `scope_violation_escalation`). The event:
- `event_type`: `"scope_auto_amended"`
- `entity_id`: `step.work_item_id`
- `entity_type`: `"work_item"`
- `message`: `f"Auto-amended scope for {step.step_id} (cycle {cycle.cycle_number}): added {len(violations)} path(s) matching project patterns"`
- `metadata` (passed as `event_metadata=` if the helper uses that name — match what `scope_violation_escalation` uses in the same file):
  ```python
  {
      "step_id": step.step_id,
      "cycle_number": cycle.cycle_number,
      "added_paths": violations,
      "manifests_updated": [str(p) for p in amend_result.manifests_updated],
      "matched_patterns": list(project_config.auto_amend_allow_patterns),
  }
  ```

### 3. Mirror `scope_amend_and_restart` for StepRun creation + step transition

The manual operator endpoint at `dashboard/routers/actions.py:444` does the canonical sequence. Mirror it line-for-line:

```python
last_run = _get_last_run(db, step.id)
new_run = StepRun(
    step_id=step.id,
    run_number=(last_run.run_number + 1) if last_run else 1,
    status=RunStatus.pending,
    command=last_run.command if last_run else None,
    worktree_path=last_run.worktree_path if last_run else None,
    cli_tool=last_run.cli_tool if last_run else None,
    timeout_secs=last_run.timeout_secs if last_run else None,
)
db.add(new_run)
step.status = StepStatus.pending
step.started_at = None
step.completed_at = None
if item.status == WorkItemStatus.failed:
    item.status = WorkItemStatus.in_progress
db.commit()
```

Adapt to your helper's available locals. You will likely need to `db.get(WorkItem, ...)` to load the parent item if it isn't already in scope.

The `_get_last_run` helper lives in `dashboard/routers/actions.py` — for daemon code, query directly:

```python
last_run = (
    db.query(StepRun)
    .filter(StepRun.step_id == step.id)
    .order_by(StepRun.run_number.desc())
    .first()
)
```

### 4. Plumb `project_config` into the auto-amend helper

`_complete_fix_cycle` already accepts `project_config: ProjectConfig | None = None` (line 1048). When it is `None`, skip auto-amend (this preserves backwards-compat with any test that calls `_complete_fix_cycle` without the config). When non-None, pass it through to `_try_auto_amend_after_escalation`.

### 5. Update `docs/IW_AI_Core_Daemon_Design.md`

Find the section that describes the scope-amend / fix-cycle flow (likely under "Fix cycles" or a similar heading; grep for "scope_violation_escalation" or "amend"). Add a short subsection describing the new auto-amend pass:
- When it fires (`auto_amend_scope.auto_allow_patterns` non-empty, every violation matches a pattern, count within `max_paths`).
- That it emits both `scope_violation_escalation` and `scope_auto_amended` so audit history is preserved.
- That it is opt-in (default off) and configured per-project in `.iw-orch.json`.

Keep the update to ~10-20 lines. Do not rewrite the surrounding sections.

### 6. Add a commented-out example to `.iw-orch.json` (root)

`.iw-orch.json` at the repo root is iw-ai-core's own config. Add a commented-out example block so future operators can copy-paste it. JSON does NOT support comments — use a `"_auto_amend_scope_example"` sibling key whose value is the example block:

```jsonc
{
  ...,
  "_auto_amend_scope_example": {
    "_note": "Uncomment by renaming to 'auto_amend_scope'. When present, the daemon auto-amends scope violations that all match auto_allow_patterns and stay within max_paths. Default (key absent) keeps today's manual amend flow.",
    "auto_allow_patterns": ["tests/**", "**/*.md", "docs/**", "ai-dev/**"],
    "max_paths": 10
  }
}
```

(Do not enable the feature on `iw-ai-core` itself in this CR — that's a follow-up after the CR is verified. The example block exists for documentation and is ignored by the parser because the key isn't `auto_amend_scope`.)

### 7. No new unit tests in this step

This is an integration-heavy change. The behavioural test is the integration test in S04. For S03 itself, write only a small unit test for `_try_auto_amend_after_escalation`'s decision logic (e.g. a test that mocks `amend_allowed_paths` and asserts the helper short-circuits when `project_config` is None or `should_auto_amend` returns False). Put it next to the existing `_complete_fix_cycle` tests under `tests/unit/daemon/`.

**RED capture**: write the short-circuit test first; it should fail because `_try_auto_amend_after_escalation` doesn't exist yet (after writing a stub returning `False` to satisfy ImportError-vs-AssertionError TDD rules, the test should fail with `AssertionError` or `NotImplementedError`).

## Project Conventions

- The daemon must NEVER mutate state outside its session — `_try_auto_amend_after_escalation` owns its writes and `db.commit()`s them.
- Logging level for auto-amend success is INFO (not DEBUG — operators want to see when this fires).
- DaemonEvent uses `event_metadata` (NOT `metadata`) on the Python side — see CLAUDE.md.
- The `_emit_event` helper signature in `orch/daemon/fix_cycle.py` is the one to use; do not import a different one.

## TDD Requirement

Follow TDD (Red-Green-Refactor). Write the small unit test for short-circuit behaviour first, confirm RED, then implement.

The full positive/negative integration tests are S04's job, not yours.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`:

1. **`make format`**
2. **`make typecheck`**
3. **`make lint`**

## Test Verification (NON-NEGOTIABLE)

Run only the targeted tests:

```bash
uv run pytest tests/unit/daemon/test_scope_amendment.py tests/unit/daemon/test_fix_cycle.py -v -k "auto_amend or _try_auto"
```

(Adjust the `-k` selector to your actual test names.)

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "backend-impl",
  "work_item": "CR-00087",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/daemon/fix_cycle.py",
    "docs/IW_AI_Core_Daemon_Design.md",
    ".iw-orch.json",
    "tests/unit/daemon/test_fix_cycle.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/unit/daemon/test_fix_cycle.py::test_auto_amend_short_circuits_when_project_config_none — AssertionError or NotImplementedError",
  "blockers": [],
  "notes": "If you mirrored scope_amend_and_restart in dashboard/routers/actions.py, note any divergence (e.g. _get_last_run is only in dashboard, so you queried StepRun directly)."
}
```
