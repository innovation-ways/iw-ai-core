# CR-00088_S02_Backend_prompt

**Work Item**: CR-00088 -- Auto-merge — partial-allowlist semantics in Phase 1 dry-run
**Step**: S02
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network state. Allowed: testcontainers in pytest fixtures, read-only `docker ps/inspect/logs`, `./ai-core.sh` and `make` targets. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step adds NO migration.

## Input Files

- **Runtime step state**: `uv run iw item-status CR-00088 --json`.
- `ai-dev/active/CR-00088/CR-00088_CR_Design.md` — design (AC4 is this step's bar).
- `ai-dev/work/CR-00088/reports/CR-00088_S01_Backend_report.md` — S01's report (partition is now in place; you build on it).
- `orch/daemon/auto_merge.py` — `attempt_resolution()` ~line 836 and the `EVENT_AUTO_*` event-emission helpers.
- `orch/daemon/merge_queue.py` — `emit_skipped_event` call site ~line 512.

## Output Files

- `ai-dev/work/CR-00088/reports/CR-00088_S02_Backend_report.md` — Step report.

## Context

S01 made `classify_conflicts` return a `ClassificationResult` with a populated `deferred_files` tuple. This step threads that tuple through to the three places it affects daemon-event metadata so operators can see the partition in the dashboard auto-merge views and in raw `daemon_events` rows.

## Requirements

### 1. `EVENT_AUTO_RESOLUTION_ATTEMPTED` metadata (orch/daemon/auto_merge.py ~line 915)

The current emission in `attempt_resolution()` is:

```python
_emit_event(
    db,
    project_id,
    EVENT_AUTO_RESOLUTION_ATTEMPTED,
    item_id,
    "work_item",
    f"Auto-merge resolution attempted: {len(eligible_files)} file(s)",
    {
        "phase": PHASE_DRY_RUN,
        "conflict_files": eligible_files,
        "policy_decision": "allowlist",
        "runtime_option_id": runtime_option.id,
    },
)
```

`attempt_resolution` accepts `eligible_files: list[str]` today. Add a new keyword parameter `deferred_files: list[str] | None = None` (default `None` for backward compat with any existing callers / tests) and pass it through. The metadata dict becomes:

```python
{
    "phase": PHASE_DRY_RUN,
    "conflict_files": eligible_files,
    "policy_decision": "allowlist",
    "runtime_option_id": runtime_option.id,
    "allowlisted_files": eligible_files,
    "deferred_files": list(deferred_files or []),
}
```

`allowlisted_files` is a deliberate alias for `eligible_files` in the metadata — the dashboard reads `allowlisted_files` / `deferred_files` to render the partition; `conflict_files` is preserved for back-compat with existing views.

### 2. `EVENT_AUTO_RESOLVED` metadata (search for the next `_emit_event(... EVENT_AUTO_RESOLVED ...)` call below the attempt block in attempt_resolution)

Add `deferred_files` to the resolved-event metadata using the same `list(deferred_files or [])` pattern. Update the human-readable message string to include the deferred count when non-zero, e.g.:

```python
msg = f"Auto-merge dry-run: proposed resolutions for {len(proposed_files)} file(s)"
if deferred_files:
    msg += f"; {len(deferred_files)} file(s) deferred (non-allowlisted) for operator"
```

### 3. `EVENT_AUTO_RESOLUTION_SKIPPED` metadata (orch/daemon/merge_queue.py ~line 512)

In `merge_queue.py`, the `emit_skipped_event` call passes a dict built from `_classification`. Add `"deferred_files": list(_classification.deferred_files)` to the dict so the dashboard sees the deferred list even when no LLM was invoked. Keep the existing keys unchanged.

### 4. Thread `deferred_files` through the caller (orch/daemon/merge_queue.py ~line 540)

The `attempt_resolution(...)` call site in `merge_queue.py` currently passes `eligible_files=list(_classification.eligible_files)`. Add `deferred_files=list(_classification.deferred_files)` immediately after that argument.

### 5. Update auto_merge.py docstrings

- `attempt_resolution()` docstring: mention the new `deferred_files` parameter and that its only effect is on event metadata; the LLM is still invoked only for `eligible_files`.
- `EVENT_AUTO_RESOLUTION_ATTEMPTED` constant's adjacent comment (if any): add a line about the new metadata key.

### 6. Add `deferred_files` to `EVENT_AUTO_RESOLUTION_FAILED` metadata

The `EVENT_AUTO_RESOLUTION_FAILED` emission inside `attempt_resolution()` (~line 977, the `if abstained_files or error_files:` branch at orch/daemon/auto_merge.py:976) fires when the LLM abstains or errors for at least one eligible file. In the partial-allowlist case, the operator deserves the full picture — eligible files that failed AND files that were never attempted (deferred). Add `"deferred_files": list(deferred_files or [])` to that metadata dict alongside `abstained_files`, `error_files`, `proposed_files`. Do NOT change the human-readable message string for this event in this CR — it already conveys abstain/error counts.

### 7. Test plumbing — integration only

These tests need a real DB session (they read `DaemonEvent` rows after `attempt_resolution(...)` runs and writes events via `_emit_event` → `db.commit()`). They do NOT belong in `tests/unit/` — CLAUDE.md forbids mocking the DB in any test that exercises commit semantics. Add them to `tests/integration/test_auto_merge_phase1.py` alongside the existing event-read tests (the file already does this exact pattern at ~line 164 with `attempted[0].event_metadata`).

**NOTE** — `DaemonEvent`'s Python attribute is `event_metadata`, not `metadata` (SQLAlchemy reserves `metadata` on `DeclarativeBase`). The SQL column is still `metadata`. Mirror the existing tests' attribute usage exactly — `assert event.event_metadata["..."] == ...`, never `event.metadata[...]`.

RED-first additions (run them against the pre-S02 codebase and capture the failure mode verbatim in the report's `tdd_red_evidence`):

- **`test_attempt_resolution_attempted_event_includes_deferred_files`** — Call `attempt_resolution(..., eligible_files=["docs/foo.md"], deferred_files=["Makefile"])` with `monkeypatch.setattr(auto_merge, "invoke_llm_for_file", ...)` returning an `LLMCallResult` with `abstained=False, proposed_content="<stub>"`. Read the latest `EVENT_AUTO_RESOLUTION_ATTEMPTED` row from the DB and assert `event.event_metadata["allowlisted_files"] == ["docs/foo.md"]` AND `event.event_metadata["deferred_files"] == ["Makefile"]`.
- **`test_attempt_resolution_resolved_event_includes_deferred_files`** — Same stub; assert the `EVENT_AUTO_RESOLVED` row's `event_metadata["deferred_files"] == ["Makefile"]` AND `"docs/foo.md" in event_metadata.get("resolved_files", [])`.
- **`test_attempt_resolution_failed_event_includes_deferred_files`** — Stub `invoke_llm_for_file` to return `abstained=True` for the eligible file, then call `attempt_resolution(..., eligible_files=["docs/foo.md"], deferred_files=["Makefile", "pyproject.toml"])`. Assert the `EVENT_AUTO_RESOLUTION_FAILED` row's `event_metadata["deferred_files"] == ["Makefile", "pyproject.toml"]` AND `event_metadata["abstained_files"] == ["docs/foo.md"]`. Specific-value assertions only — no shape checks.
- **`test_attempt_resolution_default_deferred_files_empty`** — Call WITHOUT `deferred_files=` (positional, or `deferred_files=None`); assert `event_metadata["deferred_files"] == []` in BOTH the `EVENT_AUTO_RESOLUTION_ATTEMPTED` and the success-path `EVENT_AUTO_RESOLVED` events. Guards backward compat for any existing caller.

Mirror the fixture pattern in `tests/integration/test_auto_merge_phase1.py` (look at how it constructs `AutoMergeConfig`, stubs the runtime option resolution, and reads events via the existing helpers).

### 8. Integration-side test plumbing (merge_queue caller / skipped path)

Also in `tests/integration/test_auto_merge_phase1.py`, find the existing test that asserts the `EVENT_AUTO_RESOLUTION_SKIPPED` event after a `not_allowlisted` classification. Tighten the assertion to also check `event_metadata["deferred_files"]` matches the input list (specific values, exact order). Do NOT add a new file in this step — S03 owns the new partial-allowlist integration test.

## Do NOT touch in this step

- `classify_conflicts()` (S01 is done).
- The new partial-allowlist integration test (S03's job).
- `executor/auto_merge.toml`, `executor/worktree_commit.sh`.
- Any dashboard router or template.
- `docs/research/R-00076-*.md` / `ai-dev/active/AUTO_MERGE_RESOLUTION.md` (S03 covers doc updates).

## TDD Approach

RED-GREEN. The three new unit tests in `test_auto_merge_invoke.py` must fail against the current `attempt_resolution()` signature/metadata (RED: `TypeError` for the unknown keyword OR `KeyError` for missing metadata keys). Record RED output verbatim in the step report.

## Acceptance Criteria for this step

1. `attempt_resolution()` accepts `deferred_files` as a keyword arg, default `None`.
2. Both `EVENT_AUTO_RESOLUTION_ATTEMPTED` and `EVENT_AUTO_RESOLVED` metadata include `allowlisted_files` and `deferred_files` lists.
3. `EVENT_AUTO_RESOLUTION_FAILED` metadata includes `deferred_files` (new in this CR — fills the partial-allowlist visibility gap when LLM abstains/errors).
4. `EVENT_AUTO_RESOLUTION_SKIPPED` metadata (emitted from `merge_queue.py`) includes `deferred_files`.
5. `merge_queue.py` passes `_classification.deferred_files` through to `attempt_resolution`.
6. Four new integration tests pass; tightened skipped-event integration assertion passes.
7. `make lint && make test-assertions && make typecheck` all green. Run targeted tests only: `uv run pytest tests/integration/test_auto_merge_phase1.py -v`. Do NOT run `make test-unit` or `make test-integration` (full-suite execution is owned by the QV gates).

## Hard rules

- Allowed paths: `orch/daemon/auto_merge.py`, `orch/daemon/merge_queue.py`, `tests/integration/test_auto_merge_phase1.py`, `ai-dev/work/CR-00088/reports/**`.
- Phase stays at 1. No worktree mutation. No new event types.
- Keep `conflict_files` metadata key intact for backward compatibility.
- Do NOT add new tests to `tests/unit/test_auto_merge_invoke.py` — these tests need a real DB session (they read `DaemonEvent` rows after commits). Unit/integration boundary stays clean.

## Result Contract

Emit the standard `iw step-done` result contract JSON with:
- `tdd_red_evidence`: short string describing the RED state of the four new integration tests.
- `files_changed`: exact list.
- `tests_added`: the four new test names + tightened existing skipped-event test name.
