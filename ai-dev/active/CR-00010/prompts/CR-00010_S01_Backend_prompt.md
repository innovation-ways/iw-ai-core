# CR-00010_S01_Backend_prompt

**Work Item**: CR-00010 — Research items auto-complete without manual approval
**Step**: S01
**Agent**: backend-impl

---

## Input Files

- `ai-dev/active/CR-00010/CR-00010_CR_Design.md` — design document (read first)
- `orch/daemon/state_machine.py` — current state-machine transition tables
- `orch/cli/item_commands.py` — approve / unapprove commands + `validate_*` helpers
- `orch/cli/doc_commands.py` — `doc-update` command
- `orch/cli/batch_commands.py` — `batch-create` command
- `orch/db/models.py` — `WorkItem`, `WorkItemType`, `WorkItemStatus`, `WorkItemPhase`, `ProjectDoc`, `DocType`
- `skills/iw-research/SKILL.md` — Step 6 (lines 172–199)
- `CLAUDE.md`, `orch/CLAUDE.md`

## Output Files

- `ai-dev/active/CR-00010/reports/CR-00010_S01_Backend_report.md` — step report

## Context

Research work items (`WorkItemType.Research`) must bypass the `approved` state and auto-complete when `iw doc-update` runs for a `doc_type=research` document whose ID matches the work item. `iw approve` / `iw unapprove` must error for research items. `iw batch-create` must reject research items. The `iw-research` skill docs must reflect the new flow.

Read the full design doc before writing code. Pay particular attention to AC1–AC7 and AC10.

## Requirements

### 1. State machine — research-specific transition table

In `orch/daemon/state_machine.py`:

1. Import `WorkItemType` alongside the existing imports.
2. Add a new module-level table immediately after `_WORK_ITEM_STATUS`:
   ```python
   _RESEARCH_WORK_ITEM_STATUS: dict[WorkItemStatus, frozenset[WorkItemStatus]] = {
       WorkItemStatus.draft: frozenset({WorkItemStatus.completed}),
       WorkItemStatus.completed: frozenset(),
   }
   ```
3. Change the signature of `can_transition_work_item_status` and `validate_work_item_status` to accept an optional `item_type: WorkItemType | None = None` as the **third** positional parameter:
   ```python
   def can_transition_work_item_status(
       from_s: WorkItemStatus,
       to_s: WorkItemStatus,
       item_type: WorkItemType | None = None,
   ) -> bool: ...

   def validate_work_item_status(
       from_s: WorkItemStatus,
       to_s: WorkItemStatus,
       item_type: WorkItemType | None = None,
   ) -> None: ...
   ```
4. When `item_type == WorkItemType.Research`, route the lookup through `_RESEARCH_WORK_ITEM_STATUS`. For any other value (including `None`), route through the existing `_WORK_ITEM_STATUS`. The `_validate` / `_can` helpers already accept a table parameter — reuse them.
5. Keep every existing call site in the repo compiling — the new parameter MUST be optional and default to `None` with identical behavior to pre-change. Do NOT update non-research call sites unless they explicitly deal with research items.

### 2. CLI validators — type-aware approve/unapprove rejection

In `orch/cli/item_commands.py`:

1. Extend `validate_approve_transition`:
   ```python
   def validate_approve_transition(
       current_status: WorkItemStatus,
       item_type: WorkItemType | None = None,
   ) -> str | None:
       if item_type == WorkItemType.Research:
           return (
               "Cannot approve research items — they auto-complete when the "
               "research document is created via 'iw doc-update'"
           )
       if current_status != WorkItemStatus.draft:
           return f"Cannot approve: current status is '{current_status.value}'"
       return None
   ```
   **Order matters**: the research check MUST come first, so calling `iw approve` on a research item (regardless of its current status) always returns the research-specific message rather than a generic status error.
2. Extend `validate_unapprove_transition`:
   ```python
   def validate_unapprove_transition(
       current_status: WorkItemStatus,
       active_batch_id: str | None,
       item_type: WorkItemType | None = None,
   ) -> str | None:
       if item_type == WorkItemType.Research:
           return "Cannot unapprove research items — they do not use the approval workflow"
       # existing logic unchanged
   ```
3. Update the `approve` Click command to pass `item.item_type` into the validator. Rename any local vars only if strictly necessary to avoid shadowing. The exit code for validation failure stays the same as the existing invalid-status-transition path (code 2). Use `output_error(ctx, message, 2)`.
4. Update the `unapprove` Click command the same way.
5. Do NOT touch `_ITEM_TYPE_MAP`, `agent_to_step_type`, or unrelated helpers.

### 3. `iw doc-update` — auto-complete research work items

In `orch/cli/doc_commands.py`:

1. After the existing `doc, _created = svc.upsert_doc(...)` call, compute `work_item_auto_completed: bool`:
   - Initialize to `False`.
   - If `doc.doc_type == DocType.research`:
     - Look up the work item: `work_item = session.get(WorkItem, (project_id, doc_id))`.
     - If `work_item is not None AND work_item.item_type == WorkItemType.Research AND work_item.status == WorkItemStatus.draft`:
       - Use `validate_work_item_status(WorkItemStatus.draft, WorkItemStatus.completed, WorkItemType.Research)` — must not raise.
       - Set `work_item.status = WorkItemStatus.completed`.
       - Set `work_item.phase = WorkItemPhase.done` (research items skip the `work` phase — valid per the phase transition table? The existing `_WORK_ITEM_PHASE` requires `active → work → done`. Since research skips `work`, call `validate_work_item_phase(active, done, ...)` is NOT allowed. **Add a research-specific phase transition** in the same pass, OR skip the phase validator and set `phase` directly. **Prefer**: skip the phase validator for research only — set `work_item.phase = WorkItemPhase.done` directly with a comment `# research items transition phase directly to done — see CR-00010`.
       - Set `work_item.completed_at = datetime.now(UTC)`.
       - Set `work_item_auto_completed = True`.
     - Else (work item exists but is already `completed`, or not type `Research`, or not found): leave as `False`.
2. Extend the JSON output dict to include `"work_item_auto_completed": work_item_auto_completed`.
3. Imports: add `WorkItem`, `WorkItemType`, `WorkItemStatus`, `WorkItemPhase` to the existing `from orch.db.models import ...` block. `datetime` and `UTC` must also be imported at module top if not already (check first).
4. **Must be inside the existing `with get_session() as session:` block** so the work-item update commits in the same transaction as the doc upsert.
5. **Idempotency**: if the work item is already `completed`, the code must NOT attempt the transition. The `status == draft` guard handles this.
6. **Do not log or raise on "no matching work item"** — this is a valid case (ad-hoc research doc with no registered work item).

### 4. `iw batch-create` — reject research items

In `orch/cli/batch_commands.py::batch_create`:

1. Inside the validation loop (currently lines 247–258 where each item is fetched and status-checked):
   - **Before** the `if item.status != WorkItemStatus.approved` check, add:
     ```python
     if item.item_type == WorkItemType.Research:
         output_error(
             ctx,
             f"Work item {iid} is a research item and cannot be added to a batch — "
             "research items auto-complete via 'iw doc-update'",
             1,
         )
     ```
2. `WorkItemType` must already be imported in this module (check; if not, add it to the existing `from orch.db.models import ...`).
3. Do NOT change any other validation order or the batch-ID allocation step.

### 5. Skill documentation — `skills/iw-research/SKILL.md`

Update Step 6 (lines 172–199):

1. Keep the `iw register {ID} "{Title}" --type research` line unchanged.
2. In the `iw doc-update` example:
   - Remove the `--status draft` flag line (the doc can default; this flag is orthogonal to the work-item auto-complete).
   - Keep `--doc-type research` (critical — it's what triggers the auto-complete).
3. Immediately after the `iw doc-update` code block, add a callout:
   > **Work item auto-completion**: When `iw doc-update` runs for a `--doc-type research` document whose `doc_id` matches a registered research work item, the work item transitions from `draft` to `completed` automatically. Do **NOT** run `iw approve` on research items — the command will error.
4. Do NOT change any other step in the skill. Do NOT touch `skills/iw-research-quick/`.

### 6. Keep everything else untouched

- Do NOT modify `dashboard/` — that's S03's scope.
- Do NOT modify any test files — that's S05's scope. (Exception: if running the unit suite locally reveals pre-existing research-flow tests that fail against the new behavior, **leave them failing** and note them in the report so S05 can address them. Do NOT silently edit tests in this step.)
- Do NOT add a data migration — there are no research items in the DB.

## Project Conventions

Read `CLAUDE.md` and `orch/CLAUDE.md`. Hard rules that apply here:

- SQLAlchemy 2.0 `Mapped[]` style already in place — you are not adding new columns, only reading/writing existing ones.
- psycopg v3 (not psycopg2) — no change for this step.
- Append-only tables (`step_runs`, `fix_cycles`, `daemon_events`) — not touched.
- `DaemonEvent.metadata` → `event_metadata` in Python — not touched.
- No hardcoded ports, URLs, or credentials.
- All config in `.env` — not touched.

## TDD Requirement

Follow TDD (Red-Green-Refactor). You MAY write thin inline tests co-located with your implementation to verify the happy path while you work, but the authoritative test suite is owned by S05. Do NOT add duplicate tests that S05 will also write — focus your inline tests on the pure functions (state machine, validators) that are cheap to test without the DB.

RED phase is satisfied by the existing test suite: running `make test-unit` after you finish Step 2 (validators) should show failures on any test that currently expects `validate_approve_transition(draft)` to return `None` for a research item. That's the expected RED signal; S05 will update them to the new contract.

## Test Verification (NON-NEGOTIABLE)

Before reporting completion:

1. `uv run ruff check orch/`
2. `uv run ruff format --check orch/`
3. `uv run mypy orch/`
4. `make test-unit` — some pre-existing research-flow tests may fail at this point (expected — S05 will fix them). Record the exact failing test names in your report under `notes`. Do NOT edit test files to make them green.

If ruff or mypy fail, fix them before reporting. Test failures that are scoped to the research-flow change (and that S05 will address) are acceptable; any OTHER test regression is a blocker.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "CR-00010",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/daemon/state_machine.py",
    "orch/cli/item_commands.py",
    "orch/cli/doc_commands.py",
    "orch/cli/batch_commands.py",
    "skills/iw-research/SKILL.md"
  ],
  "tests_passed": true,
  "test_summary": "X passed, Y failed (list research-flow failures in notes for S05)",
  "blockers": [],
  "notes": "List pre-existing research-flow test failures that S05 must fix. Confirm ruff + mypy are green."
}
```
