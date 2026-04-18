# CR-00010_S02_CodeReview_prompt

**Work Item**: CR-00010 — Research items auto-complete without manual approval
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## Input Files

- `ai-dev/active/CR-00010/CR-00010_CR_Design.md` — design document
- `ai-dev/active/CR-00010/reports/CR-00010_S01_Backend_report.md` — S01 report
- All files listed in the S01 `files_changed`:
  - `orch/daemon/state_machine.py`
  - `orch/cli/item_commands.py`
  - `orch/cli/doc_commands.py`
  - `orch/cli/batch_commands.py`
  - `skills/iw-research/SKILL.md`

## Output Files

- `ai-dev/active/CR-00010/reports/CR-00010_S02_CodeReview_report.md`

## Context

Review S01's backend changes. Scope:
- New research-specific state-machine transition table + type-aware validators (`can_transition_work_item_status`, `validate_work_item_status`).
- `validate_approve_transition` / `validate_unapprove_transition` reject research items.
- `approve` / `unapprove` Click commands pass `item.type` (the ORM attribute, not `item.item_type`) into validators.
- `doc-update` auto-completes research work item on `doc_type=research` + matching work item in `draft`.
- `batch-create` rejects research items.
- `skills/iw-research/SKILL.md` Step 6 documents the new auto-complete flow.

Read the design doc first (especially AC1–AC7, AC10). Then diff and review.

## Review Checklist

### 1. State Machine Correctness (AC7)

- **Research table content**: `_RESEARCH_WORK_ITEM_STATUS` must be exactly `{draft: {completed}, completed: {}}`. Any additional transitions (e.g., `draft → in_progress`) is HIGH.
- **Signature preservation**: `can_transition_work_item_status` and `validate_work_item_status` accept `item_type: WorkItemType | None = None` as an optional third parameter. `item_type=None` MUST route to the existing `_WORK_ITEM_STATUS` table with byte-identical behavior — any test calling these with the 2-arg signature must still pass. Signature break is CRITICAL.
- **Routing logic**: when `item_type == WorkItemType.Research`, the lookup uses `_RESEARCH_WORK_ITEM_STATUS`. For any other enum value OR `None`, it uses `_WORK_ITEM_STATUS`. A bare `if item_type:` (truthy check) is a bug because it would route the enum `Research` correctly but route other enum values incorrectly — verify the check is explicitly `== WorkItemType.Research`.
- **Import hygiene**: `WorkItemType` is imported from `orch.db.models`. No duplicate imports.

### 2. Validator Rejection (AC1, AC2)

- **Order of checks**: in `validate_approve_transition`, the research check fires BEFORE the status check. An early `current_status != draft` check that runs first would return a misleading status error for a research item. HIGH if out of order.
- **Error message**: includes the substring `"Cannot approve research items"` (AC1) and `"Cannot unapprove research items"` (AC2). Missing either substring is HIGH — the AC tests will grep for them.
- **Backward compatibility**: calling `validate_approve_transition(status, item_type=None)` or without the second arg produces the exact same output as before for non-research types. CRITICAL if any existing non-research test regresses.
- **Command wiring**: `approve` / `unapprove` Click commands load the work item first, then pass `item.type` (ORM attribute — see `orch/db/models.py:291`) into the validator. Using `item.item_type` is CRITICAL — that attribute does not exist on `WorkItem` and will raise `AttributeError`. If the validator returns a non-None string, the command exits via `output_error(ctx, msg, 1)` (exit code `1`, matching the existing invalid-transition paths at `orch/cli/item_commands.py:325` and `377`). Any mismatch in exit code (e.g., `2`) or in-band error handling is MEDIUM.

### 3. `doc-update` Auto-Complete (AC3, AC4, AC5)

- **Trigger condition** — ALL of the following must hold for the transition to fire:
  - `doc.doc_type == DocType.research` (not `doc_type` input string — the resolved enum on the upserted doc, so default behavior is correct even when `--doc-type` flag was omitted and the upsert preserved the existing type)
  - `work_item is not None`
  - `work_item.type == WorkItemType.Research` (ORM attribute `.type`, not `.item_type`)
  - `work_item.status == WorkItemStatus.draft`
  Any trigger path that fires without ALL four conditions is HIGH.
- **Idempotency (AC4)**: calling `doc-update` on a research item already in `completed` must NOT re-trigger the transition. The `status == draft` guard handles this — verify it is present.
- **Non-research safety (AC5)**: if `doc.doc_type` is anything other than `research`, the work-item block must be skipped entirely. No lookup of the work item, no mutation.
- **Transaction scope**: the work-item update happens INSIDE the same `with get_session() as session:` block as the doc upsert. A separate session or a missing flush/commit would leave the DB inconsistent if one half fails. CRITICAL if split.
- **State-machine call**: either the validator is invoked (`validate_work_item_status(draft, completed, WorkItemType.Research)`) or the code directly sets `status = completed` without validation. Either is acceptable; if the validator is invoked, confirm the research transition table includes `draft → completed` (it does, per §1).
- **Phase transition**: `work_item.phase = WorkItemPhase.done`. The phase state machine (`_WORK_ITEM_PHASE`) requires `active → work → done` and does NOT permit `active → done` directly. The code may either (a) set `phase = done` directly without validation (acceptable per the S01 prompt — comment required: `# research items skip phase 'work' — see CR-00010`), or (b) extend the phase transition table to permit `active → done` for research. Either is acceptable; flag MEDIUM if neither is done (i.e., code calls `validate_work_item_phase` and it throws at runtime).
- **`completed_at` timestamp**: set to `datetime.now(UTC)`. No hardcoded dates.
- **JSON output**: `work_item_auto_completed` key present in the output dict, boolean value. Missing key is MEDIUM (AC3 and AC4 assert it).

### 4. `batch-create` Rejection (AC6)

- **Check location**: the research check is BEFORE the `status != approved` check. Reversed order would produce a confusing error ("not approved") instead of ("cannot be added to a batch"). HIGH if out of order.
- **Error message**: contains `"research item"` AND `"cannot be added to a batch"` substrings. AC6 asserts both.
- **Exit code**: `1` (same as the existing "not found" / "not approved" errors). Any other code is MEDIUM.
- **`WorkItemType` import**: present in the module (may already be imported). No duplicates.

### 5. Skill Documentation (AC10)

- **Step 6 no longer instructs `iw approve`**: grep Step 6 for `iw approve`. If found as an active instruction (not a "do NOT" warning), HIGH.
- **Callout added**: a note explains that `iw doc-update` auto-completes the work item and warns against `iw approve`. Missing is HIGH (AC10).
- **`--status draft` flag handling**: removed from the example (per design). If left in, flag as LOW — it doesn't break anything but contradicts the design's intent to simplify.
- **`iw-research-quick` untouched**: confirm no changes in `skills/iw-research-quick/`. Any change is CRITICAL (out of scope).

### 6. Code Quality

- **Duplication**: the research check in `validate_approve_transition` vs `validate_unapprove_transition` is near-duplicated. Acceptable (two messages, two call sites). Do NOT demand a shared helper.
- **Type hints**: all new parameters and locals have hints (PEP 484 style consistent with the module).
- **No dead code**: no leftover print statements, no commented-out lines.
- **Comments**: every new comment explains WHY, not WHAT. The only expected comment is the `# research items skip phase 'work' — see CR-00010` marker on the phase assignment (if that approach is taken).

### 7. Project Conventions

- Read `CLAUDE.md` + `orch/CLAUDE.md`.
- SQLAlchemy 2.0 `Mapped[]` style — no new columns, no violation.
- No psycopg2 references.
- `datetime.now(UTC)` used (not `datetime.utcnow()` — the latter is deprecated).
- `output_error(ctx, msg, exit_code)` used for errors (consistent with existing commands).

### 8. Security

- No hardcoded secrets.
- `doc_id` flows from user input to a `session.get()` by composite PK — parameterized, safe.
- No shell-out, no SQL string concatenation.

### 9. Regression Surface

- **Non-research work items unaffected**:
  - `iw approve F-00001` / `iw approve I-00001` / `iw approve CR-00011` still transition `draft → approved`.
  - `iw batch-create F-00001 I-00002` still works if both are approved.
  - `iw doc-update F-00001 --doc-type tech` does NOT mutate F-00001's status (AC5). Verify via code inspection — the `doc.doc_type == DocType.research` guard is the gate.
- **Existing state-machine tests** that call `can_transition_work_item_status(draft, approved)` (2-arg) still return `True` after the signature change. CRITICAL if the default path changed.

## Test Verification (NON-NEGOTIABLE)

1. `uv run ruff check orch/`
2. `uv run ruff format --check orch/`
3. `uv run mypy orch/`
4. `make test-unit` — record the failing tests. Any test failure OUTSIDE of pre-existing research-flow tests noted by S01 is a CRITICAL regression.

## Severity Levels

Standard. The CRITICAL threshold: any change that (a) breaks the 2-arg call signature of `can_transition_work_item_status` / `validate_work_item_status`, (b) lets `iw doc-update` mutate a non-research work item, or (c) lets `iw approve` succeed on a research item.

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "CR-00010",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, Y failed (pre-existing research-flow failures owned by S05)",
  "notes": ""
}
```
