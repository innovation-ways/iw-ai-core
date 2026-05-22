# CR-00078_S12_CodeReview_Final_prompt

**Work Item**: CR-00078 -- Per-batch ignore overlap & force-start
**Step**: S12
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits
(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies
S01 wrote the migration; S03 validated it via `make migration-check`. The daemon applies it during merge.

## Scope

Global cross-agent review across S01..S11.

## Checks

### 1. AC coverage matrix

| AC | Owner step(s) | Verification artifact |
|----|---|---|
| AC1 — per-file ignore writes audit row + event | S06 + S10 dashboard test | `test_post_ignore_inserts_row_and_emits_event` |
| AC2 — idempotency | S06 + S10 dashboard test | `test_post_ignore_idempotent` |
| AC3 — ignore-all unblocks | S04 + S06 + S10 integration test | `test_all_ignored_releases_item` |
| AC4 — partial ignore keeps hold | S04 + S10 integration test | `test_partial_ignore_keeps_hold` |
| AC5 — per-batch isolation | S04 + S10 integration test | `test_per_batch_isolation` (two distinct batches) |
| AC6 — Timeline rendering | S06 + S10 dashboard test + S19 browser | `test_timeline_renders_new_event_types` + Timeline branch in `batches.py` + browser screenshot |
| AC7 — migration round-trip | S01 + S03 | `make migration-check` passing summary |
| AC8 — scope discipline | (this step) | `git diff origin/main` audit |

Any AC missing a concrete artifact → CRITICAL.

### 2. Scope discipline (AC8)

```bash
git diff origin/main -- executor/
```

Must be empty.

```bash
git diff origin/main -- orch/
```

Should be confined to:
- `orch/db/models.py`
- `orch/db/migrations/versions/<rev>_cr_00078_add_batch_overlap_ignore.py`
- `orch/daemon/batch_manager.py`
- `orch/daemon/overlap_ignore.py` (if S04 created it; else `orch/daemon/scope_overlap.py` had a small addition)

Anything else in `orch/` is a CRITICAL scope violation.

### 3. CR-00077 modal partial reuse

`dashboard/templates/fragments/batch_overlap_modal.html` was modified, not replaced. The Esc handler, backdrop, header, and empty-state branch from CR-00077 are still intact.

### 4. Migration round-trip — re-verify

Run `make migration-check` once more on the full branch state. Must pass.

### 5. Full test suite — re-verify

Run `make test-unit` and `make test-integration`. New tests pass + existing tests not broken.

### 6. Read-only contract of the GET endpoint

`git diff origin/main -- dashboard/routers/batches.py` — search the diff for `db.add(`, `db.commit(`, `db.flush(`, `insert(` in the GET overlap endpoint area. There should be NONE — only in the new POST endpoints (which live in `actions.py` per S06's design).

### 7. Carry-forward to ops

Note in your report:
- Whether the `ignored_by="operator"` placeholder is appropriate for the auth landing roadmap.
- Whether the 300s window for `ignore-all` is configurable or hardcoded (and whether ops would want to tune it).

## Severity Guide

- CRITICAL: missing AC artifact, scope violation, broken migration, GET endpoint writes to DB.
- HIGH: failing test suite, missing per-batch isolation test, AC5 test that doesn't cover two batches.
- MEDIUM: hardcoded constants that should be configurable, placeholder ignored_by without TODO.
- LOW: comment polish.

## Subagent Result Contract

```json
{
  "step": "S12",
  "agent": "code-review-final-impl",
  "work_item": "CR-00078",
  "completion_status": "complete",
  "files_changed": [],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "<X> passed across unit + integration",
  "tdd_red_evidence": "n/a — final review",
  "blockers": [],
  "notes": "<one-line summary>"
}
```
