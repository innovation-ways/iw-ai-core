# I-00072: iw merge-queue retry-merge rejects items in merge_failed status

**Type**: Issue
**Severity**: Medium
**Created**: 2026-05-06
**Reported By**: Operator (CLI/dashboard parity audit after CR-00028)
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt. This fix touches CLI / dashboard code only — no docker interaction.

## ⛔ Migrations: agents generate, daemon applies

This item leaves migrations unchanged. The `BatchItemStatus` enum already contains every label this fix references (added by I-00042 and F-00062).

## Description

Operators cannot retry a failed squash-merge from the CLI when the batch item is in `merge_failed`, `migration_invalid`, or `migration_rolled_back` status — `iw merge-queue retry-merge <ID>` returns "No failed batch item found". The dashboard's `restart-merge` action accepts those statuses (per CR-00028), so the two surfaces silently disagree: the same item is "retryable" from the browser and "not retryable" from the terminal.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Daemon merge-queue logic lives under `orch/daemon/merge_queue.py`, the operator-facing CLI lives under `orch/cli/merge_queue_commands.py`, and the equivalent dashboard endpoint lives under `dashboard/routers/actions.py`. CR-00028 is the most recent change touching this code path and is the proximate cause: it introduced the `merge_failed` status without updating the CLI filter to match.

## Steps to Reproduce

1. Approve a work item, let the daemon execute it through to merge.
2. Cause the squash-merge to fail (the most direct repro is a transient git conflict that bumps `BatchItem.status` to `BatchItemStatus.merge_failed` via `orch/daemon/merge_queue.py:343`).
3. From the dashboard, click "Restart merge" — the action succeeds; status flips back to `completed` and the daemon re-attempts on the next poll.
4. From a fresh shell, run: `uv run iw merge-queue retry-merge <ITEM_ID>`.

**Expected**: Same behaviour as the dashboard — the CLI accepts the item, flips it to `completed`, emits a `merge_retry_requested` audit event, and exits 0.

**Actual**: The CLI exits non-zero with `Error: No failed batch item found for <ITEM_ID>`. The DB row is untouched. No audit event is emitted.

## Root Cause Analysis

The CLI filter in `orch/cli/merge_queue_commands.py:223-226` only matches two of the operator-recoverable terminal statuses:

```python
_retryable = (
    BatchItemStatus.failed,
    BatchItemStatus.migration_rebase_failed,
)
```

Compare with the dashboard's authoritative set in `dashboard/routers/actions.py:925-929`:

```python
_ALLOWED_RETRY_STATUSES = {
    BatchItemStatus.merge_failed,
    BatchItemStatus.migration_invalid,
    BatchItemStatus.migration_rebase_failed,
}
```

Three concrete divergences fall out of this:

1. **`merge_failed` is missing from the CLI.** CR-00028 (`orch/daemon/merge_queue.py:340-343`) intentionally produces `merge_failed` (instead of the legacy `failed`) so the cascade is **not** triggered for clean merge failures. The CLI was not updated to recognise this new status, so every post-CR-00028 merge failure is unretryable from the terminal.
2. **`migration_invalid` is missing from the CLI.** This is a recoverable terminal status that the daemon transitions to from `orch/daemon/merge_queue.py:211` when migration validation fails before the squash. The dashboard accepts it; the CLI silently drops it.
3. **The CLI accepts blanket `failed` rows.** The dashboard treats a `failed` row as merge-retryable **only if** `notes.startswith("Merge failed")` (`dashboard/routers/actions.py:947-957, 964-972`), which is the back-compat path for rows created before CR-00028 added the new enum labels. The CLI accepts every `failed` row regardless of phase, so it can mistakenly retry a setup-phase or execution-phase failure as if it were a merge failure.

A fourth recoverable status — `migration_rolled_back` (added by I-00042 and listed in `BatchItemStatus`) — is currently absent from **both** surfaces. Adding it everywhere now closes the gap proactively rather than waiting for the producer to land.

The two filter declarations are therefore drifting copies of the same concept. Without a shared constant, the next status added to the recoverable set will drift again.

## Affected Components

| Component | File | Impact |
|-----------|------|--------|
| Daemon merge queue | `orch/daemon/merge_queue.py` | Hosts the new shared `OPERATOR_RECOVERABLE_MERGE_STATUSES` constant. No behavioural change. |
| CLI `retry-merge` | `orch/cli/merge_queue_commands.py` | Replaces the local `_retryable` tuple with the shared constant; adds back-compat for legacy `failed` + `notes.startswith("Merge failed")` rows. |
| Dashboard `restart-merge` | `dashboard/routers/actions.py` | Replaces local `_ALLOWED_RETRY_STATUSES` with the shared constant. Behaviour preserved. |
| CLI tests | `tests/unit/test_merge_queue_cli.py` | New reproduction + regression tests covering all four statuses + the legacy `failed`-with-notes path. |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Extract `OPERATOR_RECOVERABLE_MERGE_STATUSES` shared constant in `orch/daemon/merge_queue.py`; align CLI retry filter with dashboard via that constant; add legacy `failed`-with-`notes.startswith("Merge failed")` back-compat path to the CLI; rewire dashboard to import the shared constant. | — |
| S02 | code-review-impl | Review S01: CLI/dashboard parity, no orphan local copies of the status set, legacy back-compat path correct (only `failed` rows whose notes start with `"Merge failed"` are accepted). | — |
| S03 | tests-impl | Reproduction test: CLI `retry-merge` succeeds on a `merge_failed` row. Regression tests: `migration_invalid`, `migration_rebase_failed`, `migration_rolled_back`, legacy `failed`-with-merge-notes path; rejection of plain `failed` rows without merge notes; parity assertion that the CLI's accepted set equals the dashboard's. | S04 (review) |
| S04 | code-review-impl | Review S03: tests verify semantic outcomes (status flipped, `merge_retry_requested` daemon event written, CLI exit code 0/non-zero), not just response shape. | — |
| S05 | code-review-final-impl | Final cross-step review: shared constant in place; CLI/dashboard parity; all four recoverable statuses + legacy notes path covered by tests; regression tests would have failed against pre-fix code. | — |
| S06–S12 | qv-gate | `make lint`, `make format-check`, `make typecheck`, `make arch-check`, `make security-sast`, `make test-unit`, `make test-integration`. | — |
| S13 | self-assess-impl | Self-assessment via the `iw-item-analyze` skill (soft step). | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None — every status referenced (`merge_failed`, `migration_invalid`, `migration_rebase_failed`, `migration_rolled_back`) is already present in the `batch_item_status` PG enum (per I-00042 and CR-00028 / F-00062).

### Code Changes

- **Files to modify**:
  - `orch/daemon/merge_queue.py` — add module-level `OPERATOR_RECOVERABLE_MERGE_STATUSES: frozenset[BatchItemStatus]` exported as a public constant.
  - `orch/cli/merge_queue_commands.py` — import the constant, replace local `_retryable` tuple, add legacy-failed-with-notes path.
  - `dashboard/routers/actions.py` — import the constant, replace local `_ALLOWED_RETRY_STATUSES`. Existing legacy back-compat path stays.
  - `tests/unit/test_merge_queue_cli.py` — add reproduction + regression test class for `retry-merge`.
- **Nature of change**: Refactor (extract shared constant) + bug fix (CLI filter alignment) + back-compat addition (CLI legacy path).

## File Manifest

All files for this work item live under `ai-dev/active/I-00072/`:

| File | Type | Purpose |
|------|------|---------|
| `I-00072_Issue_Design.md` | Design | This document |
| `I-00072_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00072_S01_Backend_prompt.md` | Prompt | S01 backend fix |
| `prompts/I-00072_S02_CodeReview_Backend_prompt.md` | Prompt | S02 review of S01 |
| `prompts/I-00072_S03_Tests_prompt.md` | Prompt | S03 tests |
| `prompts/I-00072_S04_CodeReview_Tests_prompt.md` | Prompt | S04 review of S03 |
| `prompts/I-00072_S05_CodeReview_Final_prompt.md` | Prompt | S05 final review |
| `prompts/I-00072_S13_SelfAssess_prompt.md` | Prompt | S13 self-assessment |

Reports are created during execution in `ai-dev/active/I-00072/reports/`.

## Test to Reproduce

Write a failing test that demonstrates the bug before fixing it. Located at `tests/unit/test_merge_queue_cli.py` (CLI tests do not need the dashboard `client` fixture — they use the existing `cli_runner` fixture in that file, see I-00067).

```python
def test_i00072_retry_merge_accepts_merge_failed_status(
    cli_runner: CliRunner, monkeypatch, sample_worktree_path: Path
) -> None:
    """RED before fix, GREEN after.

    A batch item in BatchItemStatus.merge_failed (CR-00028's new status)
    must be accepted by `iw merge-queue retry-merge`, flipped to
    `completed`, and produce a `merge_retry_requested` daemon event.
    """
    project_id = "iw-ai-core"
    item_id = "F-99999"

    # Seed: a batch item in merge_failed with a valid worktree path
    with seeded_session(
        project_id=project_id,
        item_id=item_id,
        status=BatchItemStatus.merge_failed,
        worktree_path=sample_worktree_path,
    ) as session:
        result = cli_runner.invoke(cli, ["merge-queue", "retry-merge", item_id])
        assert result.exit_code == 0, result.output

        item = session.scalar(
            select(BatchItem).where(BatchItem.work_item_id == item_id)
        )
        assert item.status == BatchItemStatus.completed
        assert (
            session.scalar(
                select(DaemonEvent).where(
                    DaemonEvent.event_type == "merge_retry_requested",
                    DaemonEvent.entity_id == item_id,
                )
            )
            is not None
        )
```

## Acceptance Criteria

### AC1: Bug is fixed

```
Given a BatchItem is in BatchItemStatus.merge_failed (or migration_invalid, or
      migration_rolled_back) with an existing worktree_info.path on disk
When the operator runs `iw merge-queue retry-merge <ITEM_ID>`
Then the CLI exits 0, the BatchItem.status flips to BatchItemStatus.completed,
     a `merge_retry_requested` DaemonEvent is written, and the daemon picks
     the item up on its next poll.
```

### AC2: Regression test exists

```
Given the fix is applied
When the test suite runs
Then the I-00072 reproduction test passes; before the fix it fails with
     "No failed batch item found".
```

### AC3: CLI / dashboard parity

```
Given the dashboard's restart-merge endpoint and the CLI's retry-merge
      command
When the test suite runs
Then a parity assertion confirms both surfaces accept the same set of
     statuses (the imported OPERATOR_RECOVERABLE_MERGE_STATUSES constant)
     and the same legacy `failed`-with-merge-notes back-compat path.
```

### AC4: Legacy back-compat preserved

```
Given a pre-CR-00028 BatchItem in BatchItemStatus.failed whose notes start
      with "Merge failed"
When the operator runs `iw merge-queue retry-merge <ITEM_ID>`
Then the CLI accepts the row and behaves as if it were `merge_failed`.

Given a BatchItem in BatchItemStatus.failed whose notes do NOT start with
      "Merge failed" (e.g., setup or execution failure)
When the operator runs `iw merge-queue retry-merge <ITEM_ID>`
Then the CLI rejects with a 422-equivalent message guiding the operator to
     use item-restart instead.
```

## Regression Prevention

- **Single source of truth.** `OPERATOR_RECOVERABLE_MERGE_STATUSES` lives once, in `orch/daemon/merge_queue.py`. Both CLI and dashboard import it. Linting (`make arch-check`) plus the parity test below prevent re-divergence.
- **Parity test.** A unit test in `tests/unit/test_merge_queue_cli.py` imports both the CLI's accepted statuses and the dashboard's accepted statuses and asserts they are the same `frozenset` — guarantees future drift trips the test before merging.
- **Enum coverage test.** A dedicated test asserts that every status in `OPERATOR_RECOVERABLE_MERGE_STATUSES` is covered by an explicit `retry-merge` test case, so adding a new label to the constant forces a new test row.
- **Legacy path is asserted, not assumed.** A test exercises a row in `BatchItemStatus.failed` with `notes="Merge failed: …"` and asserts retry succeeds; a sibling test exercises a `failed` row with non-merge notes and asserts retry is refused.

## Dependencies

- **Depends on**: None (CR-00028 and I-00042 are already merged; this fix only consumes their effects).
- **Blocks**: None.

## Impacted Paths

- `orch/daemon/merge_queue.py`
- `orch/cli/merge_queue_commands.py`
- `dashboard/routers/actions.py`
- `tests/unit/test_merge_queue_cli.py`

## TDD Approach

- **Reproducing test**: `test_i00072_retry_merge_accepts_merge_failed_status` (above) — fails on `main`, passes after S01.
- **Unit tests** (in `tests/unit/test_merge_queue_cli.py`):
  - `merge_failed` → accepted, status flips to `completed`, audit event written.
  - `migration_invalid` → accepted; same outcome.
  - `migration_rebase_failed` → accepted; same outcome (regression — already worked).
  - `migration_rolled_back` → accepted; same outcome (forward-coverage).
  - Legacy `failed` + `notes.startswith("Merge failed")` → accepted.
  - Legacy `failed` + non-merge notes (e.g. `"Setup failed: …"`) → refused with a clear, actionable error and non-zero exit.
  - Missing worktree path → refused (existing behaviour preserved).
  - Parity test: `OPERATOR_RECOVERABLE_MERGE_STATUSES` set imported by both CLI and dashboard match exactly.
- **Integration tests**: not required — the bug is in CLI filter logic, fully observable from unit tests with a seeded session. A `merge_queue.process_merge_queue` integration test that re-picks a previously-failed item is **out of scope** and would re-test logic already covered by the existing daemon test suite.

**Test-file location** — `tests/unit/test_merge_queue_cli.py` (CLI test, no dashboard `client` fixture required, see I-00067).

**Assertion scoping** — Tests assert specific enum values and event types; no CSS / HTML rendering involved, so the I-00067 attribute-scoping rule does not apply here.

## Notes

- This is the inverse drift of I-00042: that ticket added enum labels to PG; this ticket aligns CLI consumers with the labels' rollout. Both tickets are part of the same operator-recovery story.
- Forward-coverage: `migration_rolled_back` has no producer wired today, but adding it to the constant now means whenever a producer lands the operator surfaces will already accept it. Cost: zero (one frozenset element + one test row). Benefit: avoids reopening this ticket the day a producer is wired.
- The fix deliberately does **not** rewrite the legacy back-compat path away — historical rows from before CR-00028 still sit in production databases with `BatchItemStatus.failed` + merge-failure notes. Removing the path would orphan those rows. A future cleanup ticket can drop the path once `iw migrations` confirms zero such rows remain.
