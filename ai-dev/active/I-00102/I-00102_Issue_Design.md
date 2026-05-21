# I-00102: `iw register` silently ignores design-package drift; approve must auto-refresh `workflow_steps`

**Type**: Issue
**Severity**: High
**Created**: 2026-05-21
**Reported By**: Postmortem of CR-00067/S08 (1826 s timeout — daemon ran a `qv-gate integration-tests` prompt for a `self_assess` step)
**Status**: Draft

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

This item **adds** one alembic migration (new nullable column on `work_items`). The agent writes the file; the daemon applies it via the merge pipeline. Do NOT run `alembic upgrade` against the live orch DB.

## Description

`iw register` is idempotent and silently no-ops on a re-run: once a work item exists, edits to the on-disk design package (manifest steps + prompt files) never make it into the database. The DB's `workflow_steps` rows stay frozen at the first-register layout while the on-disk files drift to a new layout. The daemon then launches the wrong prompts for renumbered steps (CR-00067/S08 burned 1826 s running `make test-integration` for a `self_assess` step). `iw approve` performs no manifest re-validation, so the operator has no warning until the daemon fails mid-batch.

## Project Context

Read the project's `CLAUDE.md` (architecture, conventions, hard rules). Register/approve live in `orch/cli/item_commands.py`. The `WorkflowStep` and `WorkItem` ORM models live in `orch/db/models.py`. Alembic migrations live in `orch/db/migrations/versions/`. The daemon's launch path reads `WorkflowStep.prompt_file` directly; the post-companion-fix `fix/daemon-prompt-file-missing-fail-fast` already short-circuits on a missing file, so the *new* failure mode under drift is "every renumbered step fails immediately" — better than 30-minute timeouts but still wastes a full batch attempt.

## Steps to Reproduce

1. Create a draft incident with a small workflow-manifest.json containing 3 steps S01/S02/S03 and the matching prompts; run `iw register <ID> "..." --type incident --design-doc … --steps-from ai-dev/active/<ID>/workflow-manifest.json`.
2. Edit the on-disk manifest: insert a new step at S01 and renumber the others to S02/S03/S04. Rename the prompt files to match.
3. Re-run the same `iw register` command. It silently prints `Already registered <ID>` and exits 0; no `workflow_steps` row is added, no row is renamed.
4. Run `iw approve <ID>` and create+approve a batch. The daemon launches S01: it now expects `prompts/<ID>_S01_<NewAgent>_prompt.md` but the DB row's `prompt_file` still points at the originally-registered name. With the companion fix in place every step fails with `prompt_file_missing`; without it the daemon silently substitutes a different on-disk manifest entry and runs the wrong prompt (the CR-00067/S08 case).

**Expected**: `iw approve` detects that the on-disk manifest no longer matches what was registered, atomically replaces the `workflow_steps` rows with the current manifest's content under one transaction (the item is still in `draft`, so there is no run history to invalidate), records an audit event, and proceeds with approve.

**Actual**: Approve never reads the manifest after register. DB and disk drift silently. The daemon then either runs the wrong prompt (pre-companion-fix) or fails every step (post-companion-fix).

## Root Cause Analysis

`orch/cli/item_commands.py:338-355` (the `existing` short-circuit inside the `register` command) returns "Already registered" without comparing the on-disk manifest against the registered rows:

```python
if existing is not None:
    # ... emits "Already registered" (plain-text or --json) ...
    click.echo(
        f"Already registered {item_id}: {existing.title} [{existing.status.value}]"
    )
    return
```

There is no representation of the registered manifest's *content* on the `WorkItem` row, so even if `approve` wanted to detect drift it has nothing to compare against. The on-disk `workflow-manifest.json` carries the design-time-snapshot `_note` (CR-00023) but that is intentionally non-authoritative; the DB is the source of truth, and nothing currently keeps DB and disk in sync after the first `register`.

The cascade chain that produced the CR-00067/S08 incident:
1. `iw register CR-00067 …` (16:30:11) inserts S01..S08 from an early 8-step manifest.
2. User iterates on the design — adds Backend at S01 and qv-gate unit-tests at S07, renumbers the rest, renames prompts to S01_Backend…S10_SelfAssess, commits at 19:02:52 (commit `5889b95a`), then runs `iw approve CR-00067`.
3. `approve` reads no manifest and does not detect drift; the DB still holds the 8-step layout with stale `prompt_file` strings.
4. Daemon launches the run; every renumbered step's `prompt_file` is missing on disk. Pre-companion-fix, the daemon silently fell back to `workflow-manifest.json[step_id=Sxx]` and pulled the wrong entry. S08 (now `self_assess` in DB, `qv-gate integration-tests` in manifest) ran `make test-integration` via the LLM for ~30 minutes until the 1800 s timeout fired.

## Affected Components

| Component | Impact |
|-----------|--------|
| `orch/cli/item_commands.py` (register) | Silently idempotent; never persists a manifest fingerprint |
| `orch/cli/item_commands.py` (approve) | Does not re-read manifest; cannot detect drift |
| `orch/db/models.py` (`WorkItem`) | No `manifest_digest` column — drift detection has nothing to compare against |
| Daemon launch path | Already partially mitigated by `fix/daemon-prompt-file-missing-fail-fast` (fail fast on missing prompt file), but the root cause sits one level upstream |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Database | Add `manifest_digest TEXT NULL` to `work_items`; alembic migration with round-trip safety | — |
| S02 | Backend | `_compute_manifest_digest()` helper; populate at register; re-compute at approve; auto-refresh `workflow_steps` rows in-transaction when the item is in `draft` and digests differ; emit a `manifest_refreshed` daemon event | S01 (sequential — depends on column) |
| S03 | Tests | Reproduction test (mirrors CR-00067 scenario); digest determinism tests; `--refresh`-equivalent behaviour tests (approve auto-refresh); refusal-on-non-draft test | S02 (sequential) |
| S04 | CodeReview | Review S01 + S02 + S03 | — |
| S05 | CodeReviewFix | Fix CRITICAL/HIGH/MEDIUM_FIXABLE findings | — |
| S06 | CodeReviewFinal | Cross-agent final review | — |
| S07 | CodeReviewFixFinal | Fix final review findings | — |
| S08 | QV | `make migration-check` | — |
| S09 | QV | `make lint` | — |
| S10 | QV | `make format-check` | — |
| S11 | QV | `make type-check` | — |
| S12 | QV | `make test-unit` | — |
| S13 | QV | `make test-integration` | — |
| S14 | SelfAssess | `iw-item-analyze` (project flag `self_assess = true`) | — |

Agent slugs: `database-impl`, `backend-impl`, `tests-impl`, `code-review-impl`, `code-review-fix-impl`, `code-review-final-impl`, `code-review-fix-final-impl`, `qv-gate`, `self-assess-impl`.

### Database Changes

- **New tables**: None
- **Modified tables**: `work_items` — add `manifest_digest TEXT NULL` (nullable so existing items don't require backfill; the `approve` path treats NULL as "never had a digest → always refresh on this approve, then store").
- **Migration notes**: Single forward migration; `downgrade()` drops the column. Round-trip clean.

### Code Changes

- **Files to modify**: `orch/cli/item_commands.py`, `orch/db/models.py`, `orch/db/migrations/versions/<new>.py`, `tests/integration/test_item_register_drift.py` (new), possibly `tests/unit/test_item_commands_digest.py` (new for the digest helper).
- **Nature of change**: Add the digest helper + column, persist on register, re-validate + auto-refresh on approve, with a daemon-event audit row.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `I-00102_Issue_Design.md` | Design | This document |
| `I-00102_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions |
| `prompts/I-00102_S01_Database_prompt.md` | Prompt | S01 column + migration |
| `prompts/I-00102_S02_Backend_prompt.md` | Prompt | S02 digest + register + approve auto-refresh |
| `prompts/I-00102_S03_Tests_prompt.md` | Prompt | S03 reproduction + regression tests |
| `prompts/I-00102_S04_CodeReview_prompt.md` | Prompt | S04 review of S01+S02+S03 |
| `prompts/I-00102_S05_CodeReviewFix_prompt.md` | Prompt | S05 fix review findings |
| `prompts/I-00102_S06_CodeReviewFinal_prompt.md` | Prompt | S06 cross-agent final review |
| `prompts/I-00102_S07_CodeReviewFixFinal_prompt.md` | Prompt | S07 fix final findings |
| `prompts/I-00102_S14_SelfAssess_prompt.md` | Prompt | S14 self-assessment |

(QV gates S08..S13 are script-driven; no prompt files.)

Reports are created during execution under `ai-dev/active/I-00102/reports/`.

## Test to Reproduce

Place under `tests/integration/test_item_register_drift.py` (testcontainer DB, runs the CLI via the `iw` entrypoint as a subprocess so the full register path is exercised). The reproducing test should FAIL before the fix is applied and PASS after.

```python
def test_approve_auto_refreshes_workflow_steps_when_manifest_drifted_after_register(
    tmp_path, db_session, test_project, iw_subprocess
):
    """I-00102 reproduction: editing the manifest after register, then approving,
    must atomically replace the DB workflow_steps to match the current on-disk
    manifest. Before the fix this is a silent no-op and the DB stays stale."""
    # Arrange — register with manifest A (2 steps).
    item_id = "I-99102"  # test-only id, never collides with production sequence
    _write_design_and_manifest_v1(tmp_path, item_id)  # S01 Backend, S02 QV unit-tests
    iw_subprocess("register", item_id, "Test drift", "--type", "incident",
                  "--design-doc", f"ai-dev/active/{item_id}/{item_id}_Issue_Design.md",
                  "--steps-from", f"ai-dev/active/{item_id}/workflow-manifest.json",
                  cwd=tmp_path, expect_exit=0)
    rows_v1 = _query_workflow_steps(db_session, test_project.id, item_id)
    assert [r.step_id for r in rows_v1] == ["S01", "S02"]
    assert rows_v1[0].agent_label == "Backend"

    # Act — edit manifest in place: prepend a Database step, renumber & rename prompts.
    _write_design_and_manifest_v2(tmp_path, item_id)  # S01 Database, S02 Backend, S03 QV
    iw_subprocess("approve", item_id, cwd=tmp_path, expect_exit=0)

    # Assert — DB now reflects manifest v2 atomically. No partial state.
    db_session.expire_all()
    rows_v2 = _query_workflow_steps(db_session, test_project.id, item_id)
    assert [r.step_id for r in rows_v2] == ["S01", "S02", "S03"]
    assert rows_v2[0].agent_label == "Database"
    assert rows_v2[1].agent_label == "Backend"
    # The audit event names the refresh action so operators can see it.
    events = _query_daemon_events(db_session, test_project.id, item_id)
    assert any(e.event_type == "manifest_refreshed" for e in events)
    # And the stored digest now matches the v2 manifest.
    item = _query_work_item(db_session, test_project.id, item_id)
    assert item.manifest_digest == _compute_expected_digest_v2()
```

## Acceptance Criteria

### AC1: Bug is fixed — approve auto-refreshes on drift

```
Given a work item was registered with manifest A and is still in `draft` status,
And the on-disk workflow-manifest.json has since been edited to manifest B (different step IDs / agents / order / prompt paths),
When `iw approve <ID>` is invoked,
Then approve detects digest drift, atomically deletes all existing `workflow_steps` rows for the item and re-inserts from manifest B,
And the new `manifest_digest` is stored on the WorkItem,
And a `manifest_refreshed` daemon event is recorded with old and new digest values,
And approve proceeds (status → `approved`) — exit code 0, success message includes "refreshed steps from manifest".
```

### AC2: Regression test exists

```
Given the I-00102 fix is applied,
When `tests/integration/test_item_register_drift.py` is run,
Then the reproduction test (Test to Reproduce above) passes.
```

### AC3: Refresh is rejected when not in `draft`

```
Given a work item is in any status other than `draft` (approved, in_progress, completed, …),
And the on-disk manifest has drifted from the stored digest,
When `iw approve <ID>` is invoked (or any other re-validation point),
Then no automatic refresh occurs,
And the operator receives a clear error naming the work item, the current status, and the digest mismatch,
And the existing `workflow_steps` rows are untouched.
(approve itself can only be called from `draft`, so this is enforced by the existing status guard; the test asserts the digest-mismatch path does NOT bypass it.)
```

### AC4: Digest is deterministic across cosmetic edits

```
Given two manifests that differ only in JSON key order and whitespace but encode the same steps array,
When `_compute_manifest_digest()` runs on each,
Then both produce the same digest string.
```

### AC5: Migration is backfill-safe

```
Given the migration adds `manifest_digest` as a NULL-able column,
When the daemon applies it against the orch DB,
Then no row backfill is required (existing items get NULL).
And on the first `approve` of any pre-existing draft item, approve sees NULL → treats as "drift" → refreshes from current manifest → stores the new digest. (No surprise data loss because drift handling is the same: replace from current manifest, the source of truth at approve time.)
```

## Regression Prevention

- The new `manifest_digest` column makes drift detectable mechanically; every approve checks it.
- Auto-refresh + audit event means drift is *observable* (operators see `manifest_refreshed` in the daemon-events feed and on the dashboard).
- A unit test pins the digest stability (key order / whitespace invariance) so future refactors of the helper don't accidentally produce different hashes for equivalent manifests.
- An integration test pins the end-to-end drift→approve→refresh flow with subprocess invocation of `iw register` / `iw approve`, so a regression that re-introduces the silent no-op fails CI.

## Dependencies

- **Depends on**: None
- **Blocks**: None

(Related but not a dependency: the companion daemon fix lives on branch `fix/daemon-prompt-file-missing-fail-fast`; CR-00067 is the original failure case — see **Notes** below.)

## Impacted Paths

- `orch/cli/item_commands.py`
- `orch/db/models.py`
- `orch/db/migrations/versions/**`
- `tests/integration/test_item_register_drift.py`
- `tests/unit/test_item_commands_digest.py`
- `ai-dev/active/I-00102/**`
- `ai-dev/work/I-00102/**`

## TDD Approach

- **Reproducing test**: `test_approve_auto_refreshes_workflow_steps_when_manifest_drifted_after_register` (see *Test to Reproduce*). Must fail before the fix lands and pass after.
- **Unit tests** (`tests/unit/test_item_commands_digest.py`):
  - `test_digest_is_deterministic_across_key_order` — same steps, shuffled keys → same digest.
  - `test_digest_is_deterministic_across_whitespace` — same steps, different JSON indentation → same digest.
  - `test_digest_changes_when_step_id_changes` — renumbering one step changes the digest.
  - `test_digest_changes_when_prompt_path_changes` — renaming a prompt changes the digest.
  - `test_digest_ignores_top_level_note_field` — adding/removing `_note` does not change the digest.
- **Integration tests** (`tests/integration/test_item_register_drift.py`):
  - The reproducing test above.
  - `test_approve_no_drift_does_not_emit_refresh_event` — happy path; if disk == DB, no `manifest_refreshed` event.
  - `test_register_stores_initial_digest` — after register, `WorkItem.manifest_digest` is non-NULL and equal to the digest of the manifest on disk.
  - `test_approve_refuses_when_manifest_missing_after_register` — disk file was deleted; approve fails with a clear error (this is a separate failure mode worth pinning; the digest comparison treats it as an error, not as "drift to nothing").
  - `test_approve_on_non_draft_item_does_not_refresh` — **AC3 coverage**: register, approve once (status → `approved`), then drift the on-disk manifest and invoke `approve` again. The existing status guard rejects the second approve (exit non-zero, error names the non-draft status); assert no `manifest_refreshed` event is emitted for the item and the `workflow_steps` rows are untouched — the drift/refresh path never runs ahead of the status guard.

## Notes

- The companion daemon-side fix (`fix/daemon-prompt-file-missing-fail-fast`, already merged to a feature branch on top of `main` as of 2026-05-21) ensures that even if drift slips through, the daemon never silently launches the wrong prompt — it fails the step fast with `prompt_file_missing`. This incident addresses the upstream cause so drift is fixed before the daemon ever sees it.
- The user explicitly chose **auto-refresh on approve** (over fail-loud) and **draft-only** scope for the refresh. Earlier drafts of this design considered an explicit `iw register --refresh <ID>` escape hatch; that was dropped because the auto-refresh on approve fully covers the pre-execution case (only valid state for editing the design package).
- The digest hashes the canonicalized `steps` array only (sorted keys, normalized whitespace). Top-level fields like `title`, `_note`, and `scope` are intentionally not part of the digest: `_note` is automatically added by `_stamp_manifest_note()` so it would flag every register as drift; `title` already lives on `WorkItem`; `scope` changes are caught downstream by the merge-time scope gate.
