# CR-00078: Per-batch ignore overlap & force-start

**Type**: Change Request
**Priority**: Medium
**Reason**: Once the operator can see the full overlap detail in the popup (CR-00077), they need a way to release the hold for legitimate cases without cancelling and rebuilding the entire batch.
**Created**: 2026-05-22
**Status**: Draft

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

This CR **adds one new Alembic migration** — a new `batch_overlap_ignore` table for the per-batch audit of operator-ignored overlaps. The agent writes the revision file; the daemon applies it during the merge pipeline.

## Description

Add per-file "Ignore" buttons and a master "Ignore all & start" button inside the modal partial introduced by CR-00077. Ignoring an overlap is recorded in a new `batch_overlap_ignore` table (per-batch, with audit fields). The runtime overlap check in `orch/daemon/batch_manager.py` consults this set and excludes ignored `(blocking_item_id, conflicting_globs)` pairs. When the held set becomes empty for an item (manually one-by-one, or via the master button), the item transitions out of "Held" and the daemon picks it up on the next poll. Each ignore action is surfaced on the batch Timeline tab as a new event type.

## Project Context

Read the project's `CLAUDE.md` (root, `dashboard/CLAUDE.md`, `orch/CLAUDE.md`). Read `docs/IW_AI_Core_Daemon_Design.md` for the daemon poll-cycle structure and `docs/IW_AI_Core_Database_Schema.md` for the schema conventions (composite PKs `(project_id, id)`, append-only event tables).

This CR **depends on CR-00077**. The modal partial introduced by CR-00077 (`dashboard/templates/fragments/batch_overlap_modal.html`) is the surface this CR extends with action buttons. CR-00078 MUST NOT ship until CR-00077 is merged — the planner / daemon will hold this item via the cross-batch overlap gate when both are queued together.

## Current Behavior

After CR-00077:
- Operators can open a modal showing every conflicting file grouped by blocking item.
- The modal is read-only — no actions.
- The daemon's runtime overlap gate (`orch/daemon/batch_manager.py:457`) calls `scope_overlap.find_blocking_items(...)` every poll cycle. If the returned list is non-empty, the item stays at status `pending` and an `item_held_for_scope` `DaemonEvent` row is emitted. There is no way for an operator to unblock the item except cancelling the batch and rebuilding it without the conflicting work item.

There is no concept of a per-batch, per-file ignore. The overlap gate is binary: either there is no overlap (launch) or there is overlap (hold forever, until the blocking item finishes or the batch is cancelled).

## Desired Behavior

### 1. New ignore data model (one new table)

```
batch_overlap_ignore
  project_id      VARCHAR    NOT NULL
  batch_id        VARCHAR    NOT NULL
  held_item_id    VARCHAR    NOT NULL
  blocking_item_id VARCHAR   NOT NULL
  file_pattern    VARCHAR    NOT NULL
  ignored_by      VARCHAR    NOT NULL  -- operator identifier (placeholder "operator" until auth lands)
  ignored_at      TIMESTAMP  NOT NULL DEFAULT now()
  reason          TEXT       NULL
  PRIMARY KEY (project_id, batch_id, held_item_id, blocking_item_id, file_pattern)
  FOREIGN KEYS:
    (project_id, batch_id)               → batches(project_id, id)
    (project_id, batch_id, held_item_id) → batch_items(project_id, batch_id, work_item_id)
```

`held_item_id` and `blocking_item_id` are the `WorkItem.id` values (e.g. `"CR-00072"`, `"CR-00076"`). They are not full foreign keys to `work_items` because the ignore record outlives the batch's lifecycle and we want to preserve audit history when archive cleans up.

### 2. Modified modal partial — per-file Ignore button

Inside `dashboard/templates/fragments/batch_overlap_modal.html` (added by CR-00077), each `<li>` for a file glob gains an `Ignore` button beside the glob text:

```jinja
<li class="iw-modal-file-row">
  <code>{{ glob }}</code>
  <button type="button"
          class="iw-modal-ignore-btn"
          hx-post="/project/{{ project_id }}/batch/{{ batch_id }}/overlap/{{ held_item_id }}/ignore"
          hx-vals='{"blocking_item_id": "{{ section.blocking_item_id }}", "file_pattern": "{{ glob }}"}'
          hx-target="closest .iw-modal-file-row"
          hx-swap="outerHTML">Ignore</button>
</li>
```

When the operator clicks Ignore: htmx POSTs to the new endpoint. The server:
1. Inserts a `batch_overlap_ignore` row.
2. Emits a `batch_overlap_ignored_by_operator` `DaemonEvent`.
3. Returns an empty fragment (the `<li>` disappears via `outerHTML` swap).

The endpoint does **not** clear the hold itself. The daemon's next poll cycle re-evaluates the overlap, filters out the ignored pairs, and releases the item once nothing remains (see §4). This keeps the daemon the single owner of the launch decision and avoids a write race with `_launch_item`.

### 3. Modified modal partial — master "Ignore all & start" button

At the bottom of the modal (inside `.iw-modal-body`, after the sections loop):

```jinja
<footer class="iw-modal-footer">
  <button type="button"
          class="iw-modal-ignore-all-btn"
          hx-post="/project/{{ project_id }}/batch/{{ batch_id }}/overlap/{{ held_item_id }}/ignore-all"
          hx-target="#overlap-modal-root"
          hx-swap="innerHTML"
          hx-confirm="Ignore every remaining overlap for {{ held_item_id }} in this batch and let it start?">
    Ignore all &amp; start
  </button>
</footer>
```

On click: the server inserts one `batch_overlap_ignore` row per remaining `(blocking_item_id, file_pattern)` pair AND emits a single `batch_overlap_ignore_all_by_operator` `DaemonEvent` (with the count in `event_metadata`). It then clears the hold and the modal returns the empty fragment (modal closes via the same swap mechanic CR-00077 set up).

### 4. Daemon hook

In `orch/daemon/batch_manager.py:457` (the call to `scope_overlap.find_blocking_items`), after the call returns, the `blocked_by` list is filtered against the `batch_overlap_ignore` table for the current `(project_id, batch_id, held_item_id)`:

- For each `(blocking_item_id, conflicting_globs)` tuple in `blocked_by`, drop every `file_pattern` from `conflicting_globs` that has a matching `batch_overlap_ignore` row.
- If the filtered `conflicting_globs` list is empty, drop the entire `(blocking_item_id, ...)` tuple.
- If the filtered `blocked_by` list is empty, the item is no longer held — proceed to launch (`_launch_item`) honouring `max_parallel`.
- Emit `batch_overlap_allowed_by_ignore` event (analogous to existing `item_overlap_allowed_by_policy`) when the launch was unblocked because of ignore rows. The event's `event_metadata` lists the matched ignore rows.

The filtering logic is a pure helper `filter_blocked_by_ignores` — placed in a new module `orch/daemon/overlap_ignore.py` (or, equivalently, as a pure addition to `orch/daemon/scope_overlap.py`), so it is unit-testable without DB or FastAPI machinery. The DB query that builds the ignore set lives in `batch_manager.py`. The `scope_overlap` overlap calculation itself stays pure — it knows nothing about ignores.

### 5. Timeline surfacing

`dashboard/routers/batches.py` Timeline tab logic already iterates `DaemonEvent` rows. Extend it to recognise the three new event types and render human-readable lines:

| Event type | Line |
|---|---|
| `batch_overlap_ignored_by_operator` | `Operator ignored overlap on <file> with <blocking_item_id> (held: <held_item_id>)` |
| `batch_overlap_ignore_all_by_operator` | `Operator ignored all <N> remaining overlaps for <held_item_id>` |
| `batch_overlap_allowed_by_ignore` | `<held_item_id> launched — ignored overlaps with <blocking_id_list>` |

### 6. Authorization / actor

For this CR there is no auth subsystem to plug into. The `ignored_by` column gets the string `"operator"` as a placeholder. When auth lands later (separate work), a follow-up CR can populate this from the request session. **NEVER hardcode an operator email or assume one** — keep it a single string literal in `dashboard/routers/actions.py` (or wherever the POST handlers live) so the future swap is a one-line edit.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| Schema | No `batch_overlap_ignore` table | New table + migration |
| `orch/db/models.py` | Existing models | `BatchOverlapIgnore` model added |
| `orch/daemon/batch_manager.py` | `find_blocking_items` result used as-is | Filtered against the ignore table before holding |
| `orch/daemon/overlap_ignore.py` *(new)* | Did not exist | New pure helper `filter_blocked_by_ignores` (no DB knowledge); may instead be a pure addition to `orch/daemon/scope_overlap.py` |
| `dashboard/routers/batches.py` / `actions.py` | No overlap-action endpoints | Two POST endpoints: `/ignore`, `/ignore-all`. Timeline rendering recognises new event types |
| `dashboard/templates/fragments/batch_overlap_modal.html` | Read-only file list (CR-00077) | Per-row Ignore button + footer master button |
| `dashboard/static/styles.css` | Modal styling from CR-00077 | Append `.iw-modal-ignore-btn`, `.iw-modal-ignore-all-btn`, `.iw-modal-footer` rules |

### Breaking Changes

- None. New endpoints + new event types are additive. Existing `item_held_for_scope` semantics unchanged.

### Data Migration

- One new table; reversible. The Alembic migration's `downgrade()` drops the table. No backfill needed — fresh installations and existing DBs both start with zero rows.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | database-impl | New `BatchOverlapIgnore` model + Alembic migration | — |
| S02 | code-review-impl | Review S01 model + migration | — |
| S03 | qv-gate | `make migration-check` (round-trip + drift) | — |
| S04 | backend-impl | Daemon hook in `batch_manager.py` — filter `blocked_by` against the ignore table; emit `batch_overlap_allowed_by_ignore` event when the item is unblocked | — |
| S05 | code-review-impl | Review S04 daemon changes | — |
| S06 | api-impl | Two POST endpoints: `/ignore` and `/ignore-all`; Timeline event rendering for the new event types | — |
| S07 | code-review-impl | Review S06 endpoints + Timeline rendering | — |
| S08 | frontend-impl | Add per-row Ignore button + master footer button to `batch_overlap_modal.html`; append CSS for the new controls | — |
| S09 | code-review-impl | Review S08 template + CSS | — |
| S10 | tests-impl | Unit + integration + dashboard tests | — |
| S11 | code-review-impl | Review S10 tests | — |
| S12 | code-review-final-impl | Global cross-agent review | — |
| S13 | qv-gate | `make lint` | — |
| S14 | qv-gate | `make format-check` | — |
| S15 | qv-gate | `make type-check` | — |
| S16 | qv-gate | `make test-unit` | — |
| S17 | qv-gate | `make test-integration` | — |
| S18 | qv-gate | `make test-assertions` | — |
| S19 | qv-browser | Playwright: open held item, click Ignore on a file → row disappears; click Ignore all & start → modal closes, item moves out of Held | — |
| S20 | self-assess-impl | Post-execution analysis | — |

### Database Changes

- **New tables**: `batch_overlap_ignore` (see §1 in Desired Behavior).
- **Modified tables**: None.
- **Migration notes**: Single Alembic revision. `upgrade()` creates the table with the composite PK and the two FKs. `downgrade()` drops it. No data migration. Run `make migration-check` as S03 to validate.

### API Changes

- **New endpoints**:
  - `POST /project/{project_id}/batch/{batch_id}/overlap/{held_item_id}/ignore`
    - Body (form-encoded via htmx `hx-vals`): `blocking_item_id`, `file_pattern`, optional `reason`.
    - Inserts one `batch_overlap_ignore` row. Emits `batch_overlap_ignored_by_operator` event. If this clears the hold (no remaining non-ignored pairs), also clears the hold via the daemon-side filter (the daemon picks up on next poll; the response does not need to wait).
    - Response: HTTP 200 with an empty fragment (the `<li>` is removed by the `outerHTML` swap).
    - Idempotency: if the `(project_id, batch_id, held_item_id, blocking_item_id, file_pattern)` row already exists, the insert is a no-op (use `INSERT ... ON CONFLICT DO NOTHING`). Still emit the event for audit.
  - `POST /project/{project_id}/batch/{batch_id}/overlap/{held_item_id}/ignore-all`
    - No body required.
    - Server queries the most recent `item_held_for_scope` events for this held item (300s window), expands the `(blocking_item_id, conflicting_globs)` pairs, and inserts one `batch_overlap_ignore` row per pair (with `INSERT ... ON CONFLICT DO NOTHING`). Emits a single `batch_overlap_ignore_all_by_operator` event with the total count.
    - Response: HTTP 200 with an empty fragment (the modal closes).

- **Modified endpoints**:
  - `GET /project/{project_id}/batch/{batch_id}/overlap/{held_item_id}` (from CR-00077): filter out file globs that already have a matching ignore row, so reopening the modal does not re-show already-ignored files.
  - Timeline tab handler (whichever route renders it in `dashboard/routers/batches.py`): extended to recognise the three new event types.

- **Removed endpoints**: None.

### Frontend Changes

- **New components**: None (the modal partial is CR-00077's; this CR extends it).
- **Modified components**:
  - `dashboard/templates/fragments/batch_overlap_modal.html` — add per-row Ignore button, add footer master button.
  - `dashboard/static/styles.css` — append `.iw-modal-ignore-btn`, `.iw-modal-ignore-all-btn`, `.iw-modal-footer`, `.iw-modal-file-row` rules.
- **Removed components**: None.

## File Manifest

All files for this work item live under `ai-dev/active/CR-00078/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00078_CR_Design.md` | Design | This document |
| `CR-00078_Functional.md` | Design | Human-facing summary |
| `workflow-manifest.json` | Manifest | Step definitions |
| `prompts/CR-00078_S01_Database_prompt.md` | Prompt | Model + migration |
| `prompts/CR-00078_S02_CodeReview_prompt.md` | Prompt | Review DB |
| `prompts/CR-00078_S04_Backend_prompt.md` | Prompt | Daemon hook |
| `prompts/CR-00078_S05_CodeReview_prompt.md` | Prompt | Review daemon |
| `prompts/CR-00078_S06_API_prompt.md` | Prompt | POST endpoints + Timeline |
| `prompts/CR-00078_S07_CodeReview_prompt.md` | Prompt | Review API |
| `prompts/CR-00078_S08_Frontend_prompt.md` | Prompt | Modal buttons + CSS |
| `prompts/CR-00078_S09_CodeReview_prompt.md` | Prompt | Review FE |
| `prompts/CR-00078_S10_Tests_prompt.md` | Prompt | Tests |
| `prompts/CR-00078_S11_CodeReview_prompt.md` | Prompt | Review tests |
| `prompts/CR-00078_S12_CodeReview_Final_prompt.md` | Prompt | Final review |
| `prompts/CR-00078_S19_BrowserVerification_prompt.md` | Prompt | Playwright |
| `prompts/CR-00078_S20_SelfAssess_prompt.md` | Prompt | Analysis |
| `evidences/pre/CR-00078-before-truncated-cell.png` | Evidence | Same baseline as CR-00077 |

Reports are created in `ai-dev/active/CR-00078/reports/`.

## Acceptance Criteria

### AC1: Per-file Ignore — row disappears, audit row written

```
Given a held item with overlap details visible in the modal
When the operator clicks Ignore on a file row
Then a batch_overlap_ignore row is inserted with (project_id, batch_id, held_item_id, blocking_item_id, file_pattern, ignored_by="operator", ignored_at=now())
And a batch_overlap_ignored_by_operator DaemonEvent is emitted
And the file row disappears from the modal
And reopening the modal does not show that file again
```

### AC2: Per-file Ignore idempotent

```
Given a (project_id, batch_id, held_item_id, blocking_item_id, file_pattern) row already exists
When the same Ignore is fired again (via UI race or replay)
Then no duplicate row is inserted
And a batch_overlap_ignored_by_operator event is still emitted for audit
And the response is still HTTP 200
```

### AC3: Master Ignore all & start — item unblocks

```
Given a held item with 5 conflicting files across 2 blocking items
When the operator clicks "Ignore all & start"
Then 5 batch_overlap_ignore rows are inserted
And a single batch_overlap_ignore_all_by_operator event is emitted with metadata count=5
And on the next daemon poll, the item is no longer held
And a batch_overlap_allowed_by_ignore event is emitted
And the item transitions to setting_up / executing (subject to max_parallel)
```

### AC4: Daemon filter — partial ignore keeps hold

```
Given a held item with 3 conflicting files
When the operator ignores only 1 file
Then on the next daemon poll, the item is still held (2 files remain)
And no batch_overlap_allowed_by_ignore event is emitted yet
And the modal — when reopened — shows the remaining 2 files only
```

### AC5: Per-batch isolation

```
Given the operator ignored a (held_item, blocking_item, file_pattern) tuple in BATCH-A
And the same conflict exists in BATCH-B between the same two items
When the daemon evaluates BATCH-B
Then the ignore row from BATCH-A has no effect — BATCH-B's held item is still held
```

### AC6: Timeline surfacing

```
Given any of the new event types is emitted
When the operator opens the batch Timeline tab
Then the corresponding event is rendered with the human-readable line from §5
And the events are ordered by created_at like every other Timeline entry
```

### AC7: Migration round-trip

```
Given a fresh testcontainer DB at the parent revision
When alembic upgrade head runs
Then the batch_overlap_ignore table exists with the documented columns, PK, and FKs
And make migration-check passes (schema parity vs Base.metadata.create_all)
And alembic downgrade <parent> drops the table cleanly
And alembic upgrade head re-creates it
```

### AC8: Scope discipline

```
When git diff origin/main is inspected
Then no orch/ file is modified outside orch/db/models.py, orch/db/migrations/versions/<new>.py, orch/daemon/batch_manager.py, and the new pure helper module (orch/daemon/overlap_ignore.py, or a pure addition to orch/daemon/scope_overlap.py)
And no executor/ file is modified
And no test under tests/ touches the live DB (port 5433)
```

## Rollback Plan

- **Database**: `alembic downgrade <parent>` drops the `batch_overlap_ignore` table. Reversible. Any ignore audit history is lost on rollback — acceptable for this feature class.
- **Code**: Revert the merge commit. The daemon falls back to its pre-CR behaviour (no ignore awareness). The modal reverts to read-only (CR-00077).
- **Data**: No production data is modified or deleted. Only the new ignore rows (operator-created) disappear on `downgrade`.

## Dependencies

- **Depends on**: **CR-00077** — the modal partial extended by this CR is introduced there.
- **Blocks**: None.

## Impacted Paths

- `orch/db/models.py`
- `orch/db/migrations/versions/**`
- `orch/daemon/batch_manager.py`
- `orch/daemon/overlap_ignore.py`
- `orch/daemon/scope_overlap.py`
- `dashboard/routers/batches.py`
- `dashboard/routers/actions.py`
- `dashboard/templates/fragments/batch_overlap_modal.html`
- `dashboard/static/styles.css`
- `tests/unit/test_batch_overlap_ignore.py`
- `tests/unit/test_daemon_overlap_filter.py`
- `tests/integration/test_batch_overlap_ignore_flow.py`
- `tests/dashboard/test_batch_overlap_ignore_endpoints.py`
- `tests/dashboard/test_batch_overlap_modal.py`

## TDD Approach

- **Unit tests**:
  - `tests/unit/test_daemon_overlap_filter.py` — pure helper that filters a `blocked_by` list against a set of ignore tuples. Edge cases: empty ignores, partial ignore, full ignore, glob normalization (string-equal matching only — no fnmatch on the ignore side).
  - `tests/unit/test_batch_overlap_ignore.py` — model instantiation + `__repr__` / PK uniqueness handling.
- **Integration tests**:
  - `tests/integration/test_batch_overlap_ignore_flow.py` — seed Project/Batch/BatchItem/DaemonEvents, call the daemon's overlap-check path with the ignore table pre-populated, assert items are launched vs held correctly. Uses the `db_session` testcontainer fixture.
  - Migration round-trip: covered by `make migration-check` (S03) and reused by S17.
- **Dashboard tests**:
  - `tests/dashboard/test_batch_overlap_ignore_endpoints.py` — POST `/ignore` inserts a row + emits event; POST again returns 200 with no duplicate row (idempotency); POST `/ignore-all` inserts N rows + emits ignore-all event; GET modal after ignore filters out ignored files.
  - Timeline rendering (AC6): a dashboard test that seeds one `DaemonEvent` of each of the three new event types and renders the batch Timeline tab, asserting the exact human-readable line from §5 for each. This is the only automated coverage of the Timeline render branches (S19 browser verification is the complementary manual check). Lives in `test_batch_overlap_ignore_endpoints.py`.
- **Updated tests**:
  - Tests in `tests/dashboard/test_batch_overlap_modal.py` (from CR-00077) may need additional assertions that pre-ignored files are NOT in the response. Confirm in S10 whether CR-00077's tests need extending here.

## Notes

- **Per-batch isolation is enforced by the composite PK**. The daemon filter MUST scope its query by `(project_id, batch_id, held_item_id)` — never by `(held_item_id)` alone. The integration test covers this (AC5).
- **`file_pattern` match is exact string equality** with what the daemon emitted in `event_metadata["conflicting_globs"]`. This is correct: the daemon emits the same glob strings repeatedly per poll cycle, and `find_blocking_items` returns them deterministically. If a future planner change normalises globs (e.g., `dir//` → `dir/`), this CR's match logic must be updated — note this in the migration's comment.
- **The hold-clearing path lives in the daemon**, not the endpoint. The endpoint inserts the row and emits the event; the next poll cycle reads the ignore table, filters `blocked_by`, and decides to launch. This keeps the state machine single-owner (the daemon) and avoids a write race between the endpoint and the daemon's `_launch_item` path.
- **`hx-confirm`** on the master button: htmx's built-in `confirm()` dialog is a JS-level prompt. Accessible and keyboard-friendly out of the box. No custom modal-in-modal needed.
- **Reason field is optional and left UI-less in this CR.** The DB column exists for forward compat. A future CR can add an optional textarea before the Ignore click.
- **The `ignored_by` placeholder** (`"operator"`) is a single string literal in the endpoint handler. When auth lands, replace with the session subject. Document this in `dashboard/routers/actions.py` as `# TODO(auth): replace placeholder when sessions land`.
