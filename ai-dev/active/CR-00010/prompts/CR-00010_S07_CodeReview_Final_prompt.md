# CR-00010_S07_CodeReview_Final_prompt

**Work Item**: CR-00010 — Research items auto-complete without manual approval
**Review Step**: S07 (Final Review)
**Implementation Steps Reviewed**: S01..S06

---

## Input Files

- `ai-dev/active/CR-00010/CR-00010_CR_Design.md`
- All S01..S06 reports under `ai-dev/active/CR-00010/reports/`
- All files changed across S01, S03, S05:
  - `orch/daemon/state_machine.py`
  - `orch/cli/item_commands.py`
  - `orch/cli/doc_commands.py`
  - `orch/cli/batch_commands.py`
  - `dashboard/routers/actions.py`
  - `dashboard/routers/project_pages.py` (and any sibling router modified by S03)
  - `dashboard/templates/**` (all modified templates)
  - `skills/iw-research/SKILL.md`
  - `tests/unit/test_state_machine.py`
  - `tests/unit/test_cli_core.py`
  - `tests/integration/test_cli_core.py`
  - `tests/integration/test_cli_batches.py`
  - Any other test files modified or added

## Output Files

- `ai-dev/active/CR-00010/reports/CR-00010_S07_CodeReview_Final_report.md`

## Context

Final cross-agent review of the complete CR-00010 change set. Per-agent reviews (S02, S04, S06) have already run. Your job: catch what they could not — integration seams, end-to-end correctness, completeness vs. the design document.

## Review Checklist

### 1. Completeness vs Design Document

Walk through every AC and confirm it is delivered end-to-end, not just in isolation:

- **AC1** (approve rejects research): CLI validator + command + exit code `1` (matches existing invalid-transition at `orch/cli/item_commands.py:325`) + error substring. Trace the path from user input to error output.
- **AC2** (unapprove rejects research): same as AC1, different command.
- **AC3** (doc-update auto-completes): CLI path from `iw doc-update R-00001 --doc-type research ...` through `DocService.upsert_doc` to the work-item transition. All four trigger conditions (doc_type=research, work_item found, item_type=Research, status=draft) enforced. `work_item_auto_completed: true` in the JSON output.
- **AC4** (idempotent): second call on a completed research item returns `work_item_auto_completed: false` and does not raise `InvalidTransition`.
- **AC5** (non-research doc-update untouched): verified by tests; also trace code to confirm the `doc.doc_type == DocType.research` gate.
- **AC6** (batch-create rejects research): CLI validation order has research check BEFORE status check.
- **AC7** (state machine): both `can_transition_work_item_status` and `validate_work_item_status` accept the optional `item_type` parameter; the research table is `{draft: {completed}, completed: {}}`; backward compat preserved.
- **AC8** (dashboard hides approve/unapprove): template guard present; inline notice rendered. (Full verification in S14.)
- **AC9** (batch-queue excludes research): backend query has `WorkItem.type != WorkItemType.Research` predicate (note: ORM attribute is `type`, not `item_type` — see `orch/db/models.py:291`).
- **AC10** (skill docs): Step 6 updated; no `iw approve` instruction; callout added.

Any AC without a clear implementation path is a CRITICAL finding + a `missing_requirements` entry.

### 2. Cross-Agent Consistency

- **Enum value agreement**: `WorkItemType.Research.value == "Research"` (capital R). Jinja templates use `item.type.value != 'Research'` (ORM attribute is `.type`, not `.item_type`). Python routers use `item.type == WorkItemType.Research`. Python validators take a function **parameter** named `item_type` (distinct from the ORM attribute — don't conflate): `item_type == WorkItemType.Research`. Any case mismatch on the `'Research'` string, or any use of `.item_type` as an ORM attribute access, is CRITICAL.
- **Error-message consistency**: CLI `approve`/`unapprove` message (from S01) and dashboard route rejection message (from S03) don't have to be byte-identical but they should convey the same information. Divergent wording that implies different semantics is MEDIUM.
- **`work_item_auto_completed` JSON field**: backend (S01) emits it; tests (S05) assert on it. Name must match exactly in both.
- **Filter predicate placement**: S01 rejects research in `batch-create` (CLI) with error; S03 excludes research from the batch-queue list (dashboard). These are two different contracts — confirm both exist. Removing one on the assumption the other covers it is HIGH.

### 3. Integration Points

- **`doc-update` → work-item transition happens in the same session**: the `with get_session() as session:` block contains BOTH the doc upsert and the work-item mutation. A split session is CRITICAL (partial-commit risk).
- **Flush before output**: the session flushes/commits before the JSON is printed, so a failure in the work-item update path does not silently emit a "success" JSON. Verify by reading the commit-context-manager semantics in `orch/db/session.py` — if it commits on exit without error, the code is correct.
- **Phase state machine vs research**: `work_item.phase = WorkItemPhase.done` bypasses the phase transition table (per S01 prompt §3). Confirm the code does NOT call `validate_work_item_phase(active, done, ...)` — that would raise.

### 4. Test Coverage (Holistic)

- Every AC in the design has at least one passing test (except AC8 & AC10 which may defer to S14/manual). Missing test coverage is CRITICAL.
- Edge cases covered: (a) doc-update on a research doc_id with no matching work item; (b) approve/unapprove on a research item in a status other than draft (e.g., manually set to 'completed' — research check must still fire first); (c) batch-create with a mix of research and non-research IDs.
- Pre-existing research-flow tests are updated (not silently skipped). Grep for `@pytest.mark.skip` and `@pytest.mark.xfail` in the CR's touched test files — any is CRITICAL.

### 5. Architecture Compliance

- **`orch/` owns the business logic**: the research-auto-complete rule lives in `orch/cli/doc_commands.py` (CLI) and the state machine lives in `orch/daemon/state_machine.py`. No business logic leaked into dashboard routers or templates.
- **Templates stay presentational**: the only template change is a boolean guard on the work-item type. No data transformation, no enum conversion in Jinja beyond `.value`.
- **`tests/CLAUDE.md` hard rules**: testcontainer only, psycopg v3 URL rewrite, FTS trigger, no `importlib.reload`, no DB mocking in integration tests.

### 6. Security (Cross-Cutting)

- User-controlled `doc_id` flows to `session.get(WorkItem, (project_id, doc_id))` — composite PK lookup, parameterized, safe.
- No hardcoded secrets, ports, or URLs.
- Jinja autoescape on — `{{ item.type.value }}` is safe in text context. No `| safe` filter on user data.

### 7. Regression Surface

- **Non-research workflows untouched**:
  - Feature / Issue / ChangeRequest `approve` → `draft → approved`.
  - Feature / Issue / ChangeRequest `batch-create` → works if all approved.
  - Feature / Issue / ChangeRequest `doc-update` on a matching work item → does NOT transition the work item.
- **State machine 2-arg calls** still behave as before. Any existing test that calls `can_transition_work_item_status(a, b)` without `item_type` still passes.
- **Dashboard non-research items** still show approve / unapprove.

### 8. Documentation

- `skills/iw-research/SKILL.md` Step 6 updated (AC10).
- `CLAUDE.md` / `orch/CLAUDE.md` / `dashboard/CLAUDE.md` / `tests/CLAUDE.md` — do any of them describe the old research flow? If so, update. If not, no change needed.
- `docs/IW_AI_Core_CLI_Spec.md` — check if it documents `approve` / `unapprove` / `doc-update` / `batch-create` behavior. If it does, update to reflect the research-specific path.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — all green, including new tests.
2. `make test-integration` — all green, including new tests.
3. `uv run ruff check .`
4. `uv run ruff format --check .`
5. `uv run mypy orch/ dashboard/`

Any failure is CRITICAL.

## Severity Levels

Standard. CRITICAL threshold — any of:

- Jinja/Python enum-value mismatch.
- `doc-update` mutating a non-research work item.
- `iw approve` succeeding on a research item.
- Missing backend filter on the batch-queue query.
- Any pre-existing non-research test regressing.
- Any `@pytest.mark.skip` / `xfail` marker added in this CR.

## Review Result Contract

```json
{
  "step": "S07",
  "agent": "code-review-final-impl",
  "work_item": "CR-00010",
  "steps_reviewed": ["S01", "S03", "S05"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
