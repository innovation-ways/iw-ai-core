# I-00103: `merge_auto_resolution_failed` event drops per-file error string

**Type**: Issue
**Severity**: Low
**Created**: 2026-05-22
**Reported By**: sergio (via 2026-05-21 auto-merge failure-mode investigation)
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. **This item adds no migration** — the `daemon_events.metadata` column is JSONB and new keys are additive; readers tolerate missing keys.

## Description

When an auto-merge LLM call fails (timeout, non-zero exit, or subprocess exception), the resulting `merge_auto_resolution_failed` DaemonEvent stores only the *list of file paths* that errored, not the *reason* each one errored. The error string from `LLMCallResult.error` exists in memory at the point of emission but is dropped before the event metadata is written. The dashboard event-detail modal therefore shows 7 metadata keys with no actionable error reason, forcing the operator to `grep invoke_llm_for_file logs/daemon.log` correlated by timestamp to learn whether the failure was a timeout or something else.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Note in particular: `DaemonEvent.metadata` is named `event_metadata` in Python (SQLAlchemy reserves `metadata` on declarative bases) but the DB column is `metadata`. Auto-merge subsystem and per-event payloads are documented in `ai-dev/active/AUTO_MERGE_RESOLUTION.md` (v1.7.2) and `docs/research/R-00076-llm-automated-merge-resolution.md` §5.7.

## Browser Evidence

Pre-fix evidence captured against the live dashboard at `http://localhost:9900/project/iw-ai-core/auto-merge/events/80689` (event corresponding to I-00091's auto-merge failure on 2026-05-18, a 121 s timeout against `opencode/MiniMax-M2.7`):

- `evidences/pre/I-00103-bug-event-80689-missing-error.png` — screenshot of the event-detail modal. The "Metadata" section shows: `abstained_files: []`, `error_files: ["tests/dashboard/test_auto_merge_routes.py"]`, `phase: 1`, `proposed_files: []`, `runtime_option_id: 1`, `total_input_tokens: 0`, `total_output_tokens: 0` — seven keys, no `error` field, no `per_file_errors` field, no way for the operator to learn the cause.
- `evidences/pre/I-00103-bug-event-80689-snapshot.yml` — accessible-DOM snapshot for the same page, confirming the missing field structurally.

## Steps to Reproduce

1. Trigger a `merge_auto_resolution_failed` event with at least one errored file (e.g. set `llm_call_timeout_seconds = 1` in `executor/auto_merge.toml`, queue a merge with a conflict in `tests/**`, observe the timeout).
2. Open the auto-merge dashboard at `http://localhost:9900/project/<id>/auto-merge`.
3. Click into the resulting event row to open the event-detail modal.

**Expected**: The event detail shows the per-file failure reason — for the file that errored, render the actual error text (`"LLM call timed out after 120s: ..."`, `"exit code 1: <stderr>"`, or the subprocess exception message).

**Actual**: The modal renders `event_metadata` as a JSON blob containing `error_files: ["<path>"]`, aggregate token counts of 0, and `phase=1`, but no error text. The operator has to open `logs/daemon.log` and grep by timestamp to discover the failure reason.

## Root Cause Analysis

At `orch/daemon/auto_merge.py:961-981`, the `EVENT_AUTO_RESOLUTION_FAILED` event is emitted with this metadata payload:

```python
{
    "phase": PHASE_DRY_RUN,
    "abstained_files": abstained_files,
    "error_files": error_files,
    "proposed_files": proposed_files,
    "runtime_option_id": runtime_option.id,
    "total_input_tokens": total_input_tokens,
    "total_output_tokens": total_output_tokens,
}
```

The per-file error string already exists in memory inside the `llm_calls: list[LLMCallResult]` accumulator (built at `auto_merge.py:931-956`). Each `LLMCallResult` has an `error: str | None` field, populated at:

- `auto_merge.py:745` — `f"LLM call timed out after {config.llm_call_timeout_seconds}s: {exc}"` (timeout)
- `auto_merge.py:764` — `str(exc)` (generic subprocess exception)
- `auto_merge.py:784` — `f"exit code {result.returncode}: {result.stderr[:500]}"` (non-zero exit)

The event-emission code at `auto_merge.py:961-981` reads the `error_files` *list of paths* derived from `LLMCallResult.error is not None`, but it never includes the `error` string itself in the metadata payload. The string is only written to `logs/daemon.log` by `logger.warning(...)` at the failure site (`auto_merge.py:738`, `:754`, `:774`).

Concrete current example: events with `daemon_events.id` 80689 (I-00091, opencode/MiniMax-M2.7, timed out at 121 s on 2026-05-18 15:07 UTC) and 88770 (CR-00066, pi/MiniMax-M2.7, timed out at 120 s on 2026-05-21 11:59 UTC) both store the file path and 0 tokens but no error string. The dashboard shows them as "1 errored" with no actionable detail.

## Affected Components

| Component | Impact |
|-----------|--------|
| `orch/daemon/auto_merge.py` | Event payload missing per-file error string; needs `per_file_errors` field |
| `dashboard/templates/fragments/auto_merge_event_detail.html` | Modal renders raw JSON but has no dedicated section for the new field |
| Tests (integration + dashboard) | No test guards the contract that error strings are propagated; needs regression test in both layers |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Add `per_file_errors` field to `EVENT_AUTO_RESOLUTION_FAILED` event metadata, populated from `LLMCallResult.error`. Truncate each `error` string at 500 chars (matches existing stderr slice). Include `file_path`, `error`, `cli_tool`, `model` per entry. | — |
| S02 | code-review-impl | Review S01 (backend) | — |
| S03 | frontend-impl | Render `metadata.per_file_errors` in `auto_merge_event_detail.html` as a labelled section above the raw JSON dump. One card per file: file_path, error text (preserve whitespace), runtime label. Section hidden when the field is missing or empty (backward compatibility for historical events). | — |
| S04 | code-review-impl | Review S03 (frontend) | — |
| S05 | tests-impl | Reproduction + regression tests. Integration test: emit a failed event with a mocked `llm_calls` list containing one `error`-bearing `LLMCallResult`; assert `event_metadata["per_file_errors"]` contains a dict with the expected `file_path`, `error`, `cli_tool`, `model`. Dashboard test: render `auto_merge_event_detail.html` for an event whose metadata contains a `per_file_errors` entry; assert the error text appears in the rendered HTML inside the new labelled section. Second dashboard test: render an event WITHOUT `per_file_errors` (historical shape) and assert no template exception, no empty section visible. | — |
| S06 | code-review-impl | Review S05 (tests) | — |
| S07 | code-review-final-impl | Cross-cutting review | — |
| S08..S15 | qv-gate | lint, format-check, type-check, arch-check, security-sast, unit-tests, frontend-tests, integration-tests | — |
| S16 | qv-browser | End-to-end browser verification — emit a synthetic failed event, open its modal, confirm the error text renders | — |
| S17 | self-assess-impl | Post-execution self-assessment (project has `self_assess = true`) | — |

Agent slugs: `backend-impl`, `frontend-impl`, `tests-impl`, `code-review-impl`, `code-review-final-impl`, `qv-gate`, `qv-browser`, `self-assess-impl`.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: No migration. `daemon_events.metadata` is JSONB; new keys are additive; reader tolerates missing keys.

### Code Changes

- **Files to modify**:
  - `orch/daemon/auto_merge.py` (lines 961-981; add `per_file_errors` derivation + key)
  - `dashboard/templates/fragments/auto_merge_event_detail.html` (add the labelled section above the existing JSON-blob block)
- **New test files**:
  - `tests/integration/test_auto_merge_failed_event_metadata.py` (event-payload schema integration test — needs the testcontainer DB to round-trip the JSONB event metadata)
  - `tests/dashboard/test_auto_merge_event_detail_per_file_errors.py` (template rendering tests, both shapes)
- **Nature of change**: Additive — new JSON field in event metadata; new optional render section in the modal. No existing behaviour modified.

## File Manifest

All files for this work item live under `ai-dev/active/I-00103/`:

| File | Type | Purpose |
|------|------|---------|
| `I-00103_Issue_Design.md` | Design | This document |
| `I-00103_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00103_S01_Backend_prompt.md` | Prompt | S01 backend fix |
| `prompts/I-00103_S02_CodeReview_prompt.md` | Prompt | S02 review of S01 |
| `prompts/I-00103_S03_Frontend_prompt.md` | Prompt | S03 frontend (Jinja2) change |
| `prompts/I-00103_S04_CodeReview_prompt.md` | Prompt | S04 review of S03 |
| `prompts/I-00103_S05_Tests_prompt.md` | Prompt | S05 reproduction + regression tests |
| `prompts/I-00103_S06_CodeReview_prompt.md` | Prompt | S06 review of S05 |
| `prompts/I-00103_S07_CodeReview_Final_prompt.md` | Prompt | S07 cross-agent final review |
| `prompts/I-00103_S16_BrowserVerification_prompt.md` | Prompt | S16 browser verification |
| `prompts/I-00103_S17_SelfAssess_prompt.md` | Prompt | S17 self-assessment |
| `evidences/pre/I-00103-bug-event-80689-missing-error.png` | Evidence | Pre-fix screenshot of buggy modal |
| `evidences/pre/I-00103-bug-event-80689-snapshot.yml` | Evidence | Pre-fix accessibility snapshot |

Reports are created during execution in `ai-dev/active/I-00103/reports/`.

## Test to Reproduce

Test-file location: `tests/integration/test_auto_merge_failed_event_metadata.py`. This is an **integration** test: it uses the testcontainer-backed `db_session` from `tests/integration/conftest.py` plus the `fake_llm` fixture, mirroring `tests/integration/test_auto_merge_phase1.py` (where the `attempt_resolution` failed-event path is already exercised by `test_ac4_operator_ux_unchanged_on_llm_error`). It cannot live under `tests/unit/` — the `tests/unit/conftest.py` `db_session` is a `MagicMock` and cannot round-trip a `DaemonEvent` JSONB payload. The reproduction test fails before the fix because the event payload lacks the `per_file_errors` key entirely.

```python
def test_i00103_failed_event_carries_per_file_error_strings(db_session, project_factory):
    """Reproduction: when an LLM call fails with a non-None error string, the
    emitted merge_auto_resolution_failed event metadata must contain a
    per_file_errors list with the file_path, error, cli_tool, and model.

    Fails before fix: KeyError or empty list on metadata['per_file_errors']
    because auto_merge.py:961-981 does not include the field.
    """
    project = project_factory()
    # Build a synthetic eligible-conflict scenario; monkeypatch invoke_llm_for_file
    # to return a single LLMCallResult with error="LLM call timed out after 120s: ...".
    # Call attempt_resolution(...) in phase=1 dry-run mode.
    # Read the emitted DaemonEvent of type 'merge_auto_resolution_failed'.
    event = read_latest_event(db_session, project.id, "merge_auto_resolution_failed")
    assert "per_file_errors" in event.event_metadata, (
        "I-00103 bug: failed event payload must carry per-file error strings"
    )
    per_file = event.event_metadata["per_file_errors"]
    assert len(per_file) == 1
    entry = per_file[0]
    # Semantic checks — specific expected values, NOT shape-only
    assert entry["file_path"] == "tests/dashboard/test_auto_merge_routes.py"
    assert "LLM call timed out after 120s" in entry["error"], (
        "Error string must be the actual timeout message, not just a placeholder"
    )
    assert entry["cli_tool"] == "opencode"
    assert entry["model"] == "minimax/MiniMax-M2.7"
```

## Acceptance Criteria

### AC1: Failed-event metadata carries the per-file error string

```
Given an auto-merge LLM call fails with LLMCallResult.error = "LLM call timed out after 120s: ..."
When the daemon emits the resulting merge_auto_resolution_failed DaemonEvent
Then event_metadata["per_file_errors"] is a list with one dict per errored file,
     each containing keys {file_path, error, cli_tool, model},
     and event_metadata["per_file_errors"][0]["error"] contains the literal
     timeout reason string from LLMCallResult.error
```

### AC2: Regression test exists

```
Given the fix is applied
When the test suite runs
Then tests/integration/test_auto_merge_failed_event_metadata.py::test_i00103_failed_event_carries_per_file_error_strings passes,
     and tests/dashboard/test_auto_merge_event_detail_per_file_errors.py renders both shapes correctly
```

### AC3: Dashboard event-detail modal renders the error string

```
Given a merge_auto_resolution_failed event whose metadata contains a non-empty per_file_errors list
When the dashboard renders the event-detail modal at /project/<id>/auto-merge/events/<event_id>
Then the HTML contains a labelled section showing the file path, the literal error string from
     per_file_errors[i].error, and the runtime label (cli_tool/model)
```

### AC4: Backward compatibility — historical events render without error

```
Given a merge_auto_resolution_failed event whose metadata does NOT contain per_file_errors (e.g. events 80689 / 88770)
When the dashboard renders the event-detail modal
Then the response is HTTP 200, the labelled section is hidden (not rendered as an empty card),
     no template exception is raised, and the existing JSON-blob view continues to work
```

### AC5: Truncation cap

```
Given an LLM call fails with an error string longer than 500 characters
When the failed event is emitted
Then each per_file_errors[i].error in the persisted metadata is at most 500 characters,
     matching the cap already applied to stderr at auto_merge.py:784
```

## Regression Prevention

- Integration test pins the event-payload contract: the `per_file_errors` field must exist whenever the failed event is emitted with any non-None `LLMCallResult.error`, and the dict shape must match `{file_path, error, cli_tool, model}`. Future refactors that touch `auto_merge.py:961-981` will break this test.
- Dashboard render test pins the template's two-shape behaviour: with the field, render visibly; without it, hide silently. Prevents accidental removal or accidental "always show empty section" regressions.
- Inline truncation cap (500 chars) matches the upstream cap already applied to `result.stderr[:500]` — keeps the per-event payload bounded so a runaway stderr cannot inflate the JSONB row.

## Dependencies

- **Depends on**: F-00084 (introduced the event-emission code path), F-00085 (introduced the event-detail modal where the new field renders)
- **Blocks**: None — the auto-merge Phase 1 audit can continue without this fix, but the operator's failure-introspection workflow improves once it lands

## Impacted Paths

- `orch/daemon/auto_merge.py`
- `dashboard/templates/fragments/auto_merge_event_detail.html`
- `tests/integration/test_auto_merge_failed_event_metadata.py`
- `tests/dashboard/test_auto_merge_event_detail_per_file_errors.py`

## TDD Approach

- **Reproducing test**: `tests/integration/test_auto_merge_failed_event_metadata.py::test_i00103_failed_event_carries_per_file_error_strings` — fails before fix (missing key), passes after.
- **Integration tests** (file: `tests/integration/test_auto_merge_failed_event_metadata.py`):
  - `test_i00103_failed_event_carries_per_file_error_strings` — reproduction (above).
  - `test_per_file_errors_truncated_at_500_chars` — emit with a 2000-char error string; assert each entry's `error` field is ≤ 500 chars.
  - `test_per_file_errors_only_includes_errored_calls` — emit with mixed `llm_calls` (one error, one ABSTAIN, one success); assert `per_file_errors` contains exactly the errored entry. ABSTAIN/success entries must NOT appear in `per_file_errors`.
  - `test_per_file_errors_absent_when_no_calls_errored` — when the failed event fires for pure ABSTAIN reasons (no `error` strings, only abstentions), `per_file_errors` is either absent or empty; the existing `abstained_files` field continues to carry the data.
- **Dashboard tests** (file: `tests/dashboard/test_auto_merge_event_detail_per_file_errors.py`):
  - `test_event_detail_renders_per_file_errors_section_when_present` — seed a failed event with `per_file_errors=[{file_path, error="LLM call timed out after 120s: <exc>", cli_tool, model}]`; GET the detail route; assert the response HTML contains the file path, the literal error substring (`"LLM call timed out"`), and the runtime label, scoped to the new section (use attribute-scoped assertions per the I-00067 lesson — e.g. `'class="auto-merge-modal__per-file-error"'`, not bare-substring `'per-file-error'`).
  - `test_event_detail_hides_per_file_errors_section_when_absent` — seed a failed event without the field (historical shape mimicking event 80689); GET the detail route; assert HTTP 200 and assert the new section's class name is NOT present in the response.
  - `test_event_detail_hides_per_file_errors_section_when_empty_list` — seed a failed event with `per_file_errors=[]`; assert same hidden behaviour as the missing-key case.

## Notes

- Severity is **Low** because there is no functional regression and no data loss — purely an observability ergonomics fix. Decision recorded 2026-05-22.
- No backfill of historical events 80689 / 88770 (per operator decision 2026-05-22). The daemon-log evidence for those is already captured in `AUTO_MERGE_RESOLUTION.md` v1.7.2.
- The `cli_tool` and `model` fields per entry are mild duplication today (the event already records `runtime_option_id` at the aggregate level), but they are useful if Phase 2 ever introduces per-file runtime fallback. Including them now is cheap and forward-compatible.
- `MODEL_PRICING` in `orch/auto_merge_aggregator.py` already covers the runtimes likely to appear in `per_file_errors[i].cli_tool/model`; no aggregator change is required for this fix.
