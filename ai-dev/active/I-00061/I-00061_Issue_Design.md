# I-00061: Auto-skip phantom QV gates at item approval

**Type**: Issue
**Severity**: Medium
**Created**: 2026-05-03
**Reported By**: sergio (during F-00076 stall investigation)
**Status**: Draft

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This incident does NOT touch migrations. No alembic work is required.
The standard migration policy still applies — see the canonical block
in `ai-dev/templates/Issue_Design_Template.md` for the full text.

---

## Description

When a design author lists a `qv-gate` step whose command is structurally
unrunnable in the project (a missing Makefile target, or a `cd <dir> && ...`
where `<dir>` does not exist), the daemon launches the gate, it fails
immediately, the fix-cycle budget (5) is exhausted on no-op patches, and the
work item parks in `failed` until an operator manually skips. F-00076 hit this
on five separate gates (S15 `frontend-tsc`, S16 `arch-check`, S17
`security-sast`, S19 `frontend-tests`, S20 `integration-tests`) — `iw-ai-core`
has no `frontend/` directory and no `arch-check`/`security-sast`/`test-frontend`/
`allure-integration` Makefile targets, so each gate stalled the item for ~20
minutes of compute on dead-end fix attempts before the operator stepped in.

## Project Context

Read `CLAUDE.md` (root) and `orch/CLAUDE.md` for architecture, ORM patterns,
CLI structure, and database conventions. The relevant subsystems are the CLI
(`orch/cli/`) and the daemon's fix-cycle logic (`orch/daemon/fix_cycle.py`).

## Steps to Reproduce

1. Author a Feature/Incident/CR design that includes a `qv-gate` whose command
   cannot succeed in the project's `repo_root` — e.g., `make arch-check` when
   no such target exists, or `cd frontend && npx tsc --noEmit` when no
   `frontend/` directory exists.
2. Register the item: `iw register <ID> "<title>" --steps-from <manifest>`.
3. Approve the item: `iw approve <ID>`.
4. Add it to a batch and run: `iw batch-create <ID>` → `iw batch-approve …`.
5. Wait for the daemon to reach the phantom QV step.

**Expected**: The phantom gate is recognised before any compute is spent on it
and is silently marked `skipped`. The item completes successfully if all real
gates pass.

**Actual**: The gate fails (`exit 1` from `cd: frontend: No such file or
directory` or `make: *** No rule to make target …`). The daemon launches a fix
cycle. The fix agent cannot create a Makefile target or invent a directory it
was not asked to add, so the gate fails again. After 5 fix cycles the budget
is exhausted; the step parks in `failed` and the item stalls. Real example:
F-00076's S15 burned 6 step runs and 5 fix cycles before parking (see
`daemon_events` for `F-00076/S15` between 2026-05-03 03:18 and 03:38 UTC).

## Root Cause Analysis

`orch/cli/item_commands.py:497-546` — the `approve` Click command transitions
the item from `draft` to `approved` (`item.status = WorkItemStatus.approved`,
line 535) without inspecting the `quality_validation` workflow_step rows that
were registered alongside it. Once approved, the daemon's poll loop picks the
item up and launches every QV gate command verbatim — including any
structurally unrunnable ones.

The skill `skills/iw-new-feature/SKILL.md:288-293` already warns design
authors:

> **NEVER include a gate whose command will exit non-zero unconditionally**
> (missing dir, missing Makefile target). A phantom gate will exhaust all fix
> cycles and stall the item permanently.

…but this is advisory text. F-00076 is direct evidence that the warning gets
ignored or missed. The system needs to enforce the invariant, not rely on
authors reading the skill.

A secondary entry point — `iw batch-approve` (`orch/cli/batch_commands.py`) —
has the same gap. Even if an item was clean at approval time, the project's
`main` branch may have rebased a Makefile target out from under it before the
batch was assembled. The same validator should run there as a safety net.

## Affected Components

| Component | Impact |
|-----------|--------|
| `orch/cli/item_commands.py` `approve` | Approves items with structurally unrunnable QV gates; downstream daemon work is wasted |
| `orch/cli/batch_commands.py` `batch_approve` | No safety-net re-check for items that drifted after approval |
| `orch/daemon/fix_cycle.py` | Burns 5 cycles per phantom gate before giving up — wasted compute and operator time |
| `daemon_events` | No `step_auto_skipped_phantom_gate` audit trail today (because no auto-skip exists) |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Create `orch/qv_gate_validator.py` (pure validators + `auto_skip_phantom_qv_gates()`); wire into `item_commands.py` `approve` (post-flush) and `batch_commands.py` `batch_approve` (post-flush, all items in the batch). | — |
| S02 | code-review-impl | Review S01 (validator + 2 hooks) | — |
| S03 | tests-impl | Unit tests per pattern; integration tests for `iw approve` (phantom Makefile + phantom `cd dir`); integration test for `iw batch-approve` safety net; assert real gates are NOT skipped. | — |
| S04 | code-review-impl | Review S03 (semantic correctness, fixture quality) | — |
| S05 | code-review-final-impl | Global review of S01 + S03 — full fix is coherent | — |
| S06 | qv-gate (lint) | `make lint` | — |
| S07 | qv-gate (format) | `make format-check` | — |
| S08 | qv-gate (typecheck) | `make type-check` | — |
| S09 | qv-gate (unit-tests) | `make test-unit` | — |
| S10 | qv-gate (integration-tests) | `make test-integration` | — |

QV gates above include only Makefile targets that actually exist in
`iw-ai-core` (verified by `grep -E '^(target):' Makefile` for each). This is
the same precheck the validator built in S01 will enforce.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None — no schema change. The fix only writes
  `workflow_steps.status='skipped'` rows and inserts `daemon_events` rows,
  both of which are existing schema.

### Code Changes

- **Files to modify**: `orch/cli/item_commands.py` (call hook in `approve`),
  `orch/cli/batch_commands.py` (call hook in `batch_approve`).
- **Files to create**: `orch/qv_gate_validator.py`,
  `tests/unit/test_qv_gate_validator.py`,
  `tests/integration/test_phantom_gate_auto_skip.py`.
- **Nature of change**: Add a pure-function validator with a small pattern
  registry and a thin DB-mutating orchestrator. Hook it from two existing CLI
  commands.

### Validator Design

`orch/qv_gate_validator.py` exposes two callables:

```python
def validate_qv_gate(repo_root: Path, gate: str, command: str) -> bool:
    """Return True if the command is structurally runnable in repo_root.
    False means a phantom gate (missing target/dir/binary).
    Conservative: when a pattern is unrecognised, return True (do not skip)."""

def auto_skip_phantom_qv_gates(
    session: Session, project_id: str, work_item_id: str
) -> list[tuple[str, str, str]]:
    """For each quality_validation step on the item, check the gate.
    Phantom ones are set to status='skipped' (completed_at=now()) and a
    daemon_event 'step_auto_skipped_phantom_gate' is inserted.
    Returns list of (step_id, gate, reason) for skipped steps."""
```

Pattern registry (matched in order; first hit wins):

| Pattern | Detector | Phantom when |
|---------|----------|--------------|
| `make <target>` (whole command) | parse first non-option token after `make` | `<repo_root>/Makefile` does not exist OR has no `^<target>:` line |
| `cd <dir> && <rest>` (command starts with `cd`) | parse `<dir>` | `<repo_root>/<dir>` is not a directory |
| Bare exec (`npx tsc …`, `pytest …`, `ruff …`) | first whitespace-separated token | `shutil.which(token, path=os.environ['PATH'])` is None |
| Anything else | — | conservative — return True (assume runnable) |

The validator is **pure** — no DB, no mutation, no logging, no I/O beyond
filesystem reads and `which` lookups. The orchestrator function does the DB
work.

### Hook Points

1. `orch/cli/item_commands.py` `approve` (line 535-538) — after
   `item.status = WorkItemStatus.approved` and `session.flush()`, call
   `auto_skip_phantom_qv_gates(session, project_id, item_id)`. Within the
   same transaction. The approval still succeeds even if no gates are
   skipped (it's a no-op on a clean item).

2. `orch/cli/batch_commands.py` `batch_approve` — after the batch transitions
   to approved and is flushed, iterate all items in the batch and call
   `auto_skip_phantom_qv_gates` for each. Safety net for drift between item
   approval and batch approval.

### Daemon Event Schema

The `daemon_events` table is free-form on `event_type`; no enum constraint
exists. Insert with:

```python
{
  "project_id": project_id,           # populated — UI/dashboard filters events by project
  "event_type": "step_auto_skipped_phantom_gate",
  "entity_type": "workflow_step",
  "entity_id": f"{work_item_id}/{step_id}",
  "message": f"Auto-skipped phantom QV gate {gate}: {reason}",
  "event_metadata": {                 # Python attribute (DB column is "metadata")
    "work_item_id": work_item_id,
    "step_id": step_id,
    "gate": gate,
    "command": command,
    "reason": reason,  # e.g., "missing_makefile_target", "missing_directory"
    "trigger": "approve" | "batch_approve",
  },
}
```

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `I-00061_Issue_Design.md` | Design | This document |
| `I-00061_Functional.md` | Design | Human-facing summary |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00061_S01_Backend_prompt.md` | Prompt | Validator + 2 CLI hooks |
| `prompts/I-00061_S02_CodeReview_Backend_prompt.md` | Prompt | Review S01 |
| `prompts/I-00061_S03_Tests_prompt.md` | Prompt | Unit + integration tests |
| `prompts/I-00061_S04_CodeReview_Tests_prompt.md` | Prompt | Review S03 |
| `prompts/I-00061_S05_CodeReview_Final_prompt.md` | Prompt | Global review |

## Test to Reproduce

Integration test that fails before the fix:

```python
def test_iw_approve_auto_skips_phantom_makefile_gate(
    cli_runner, project_with_no_arch_check_target, registered_item_with_arch_check_gate
):
    """Before fix: approve succeeds and the phantom gate stays 'pending'.
    After fix: approve succeeds AND the phantom gate is 'skipped'."""
    result = cli_runner.invoke(cli, ["approve", "I-99999"])
    assert result.exit_code == 0

    with get_session() as s:
        step = s.query(WorkflowStep).filter_by(
            project_id="test-proj", work_item_id="I-99999", step_id="S05"
        ).one()
        assert step.status == StepStatus.skipped, (
            f"Phantom gate should be auto-skipped; got {step.status.value}"
        )

        # And a daemon event was emitted
        ev = s.query(DaemonEvent).filter(
            DaemonEvent.event_type == "step_auto_skipped_phantom_gate",
            DaemonEvent.entity_id == "I-99999/S05",
        ).first()
        assert ev is not None
        assert ev.event_metadata["reason"] == "missing_makefile_target"
```

## Acceptance Criteria

### AC1: Phantom Makefile gate auto-skipped at approval

```
Given a work item with a quality_validation step whose command is `make foo`
  and the project's Makefile has no `^foo:` target
When the operator runs `iw approve <ID>`
Then the step's status transitions to 'skipped'
  And a 'step_auto_skipped_phantom_gate' event is recorded in daemon_events
  And the approve command itself exits 0
```

### AC2: Phantom `cd <dir>` gate auto-skipped at approval

```
Given a work item with a quality_validation step whose command is
  `cd frontend && npx tsc --noEmit` and no `frontend/` directory exists
  in the project's repo_root
When the operator runs `iw approve <ID>`
Then the step's status transitions to 'skipped' with reason 'missing_directory'
```

### AC3: Real gates are NOT skipped

```
Given a work item with quality_validation steps whose commands all map to
  existing Makefile targets (`make lint`, `make test-unit`, etc.)
When the operator runs `iw approve <ID>`
Then no steps are marked 'skipped'
  And no 'step_auto_skipped_phantom_gate' events are emitted
```

### AC4: Batch-approve safety net

```
Given an item was approved when `make security-sast` existed
  And `main` was subsequently rebased and the target was removed
  And the item is added to a batch
When the operator runs `iw batch-approve <BATCH-ID>`
Then the previously-clean step is now auto-skipped with reason
  'missing_makefile_target'
```

### AC5: Regression test exists

```
Given the fix is applied
When `make test-integration` runs
Then `tests/integration/test_phantom_gate_auto_skip.py` passes
  And `tests/unit/test_qv_gate_validator.py` passes
```

## Regression Prevention

- **Validator pattern registry is unit-tested** — adding new gate-command
  shapes in the future requires extending the registry AND adding a unit
  test. The structure forces the test alongside the code.
- **Conservative default** — unrecognised command shapes return True (do not
  skip). This means a future buggy registry entry cannot accidentally skip a
  real gate; the worst case is failing to catch a new phantom shape, which
  degrades to today's behaviour.
- **Two enforcement points** — `iw approve` catches design-time mistakes;
  `iw batch-approve` catches drift-time mistakes. Single source of truth
  (the validator function) means both hooks behave identically.
- **Audit via daemon_events** — every auto-skip leaves a trail with the
  exact gate, command, and reason. If this triggers unexpectedly, the
  operator can grep events and diagnose.

## Dependencies

- **Depends on**: None
- **Blocks**: None (separately, the skill text in `iw-new-feature` /
  `iw-new-incident` / `iw-new-cr` could keep its precheck guidance — that
  is out of scope for this incident.)

## Impacted Paths

- `orch/qv_gate_validator.py`
- `orch/cli/item_commands.py`
- `orch/cli/batch_commands.py`
- `tests/unit/test_qv_gate_validator.py`
- `tests/integration/test_phantom_gate_auto_skip.py`

## TDD Approach

- **Reproducing test**: `tests/integration/test_phantom_gate_auto_skip.py::test_iw_approve_auto_skips_phantom_makefile_gate`
  — fails on `main` (the step stays `pending`), passes after the fix.
- **Unit tests**: `tests/unit/test_qv_gate_validator.py` covers each pattern
  in the registry: Makefile target present/missing/missing-Makefile;
  `cd <dir>` present/missing/relative-vs-absolute; bare exec on/off PATH;
  unrecognised command shape (default-True).
- **Integration tests**: `tests/integration/test_phantom_gate_auto_skip.py`
  covers `iw approve` and `iw batch-approve` end-to-end, including the
  daemon_event row, the conservative no-op case, and the multi-item batch
  case.

## Notes

- The `iw next-id --type incident` CLI was unavailable when this incident was
  drafted (unresolved merge conflicts in `orch/cli/step_commands.py`); the ID
  `I-00061` was allocated directly from the `id_sequences` table to mirror
  the CLI's semantics.
- The validator should NOT execute the gate command — only inspect its
  structure. Executing arbitrary commands at approval time would broaden
  blast radius and slow the CLI.
- Edge case (acknowledged, not handled): if a Feature *adds* a Makefile
  target in S01 that a later QV gate depends on, the validator would mark
  the gate phantom at approval (target doesn't exist on `main` yet). This is
  rare; an operator can `iw step-restart` the skipped step manually if it
  occurs. A future change could add a per-step `skip_precheck=true` opt-out
  on the design row, but that is deliberately out of scope for I-00061.
