# F-00061_S02_CodeReview_Database_prompt

**Work Item**: F-00061 -- Baseline QV gates to prevent fix-cycle scope expansion
**Step**: S02
**Agent**: code-review-impl
**Reviews**: S01 (Database)

---

## ⛔ Docker is off-limits

(Same policy as S01. You MUST NOT touch `docker compose up/down/restart`, `docker kill`, `docker rm`, `docker volume rm`. Read-only introspection (`docker ps`, `docker inspect`, `docker logs`) is OK. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.)

## ⛔ Migrations: agents generate, daemon applies

(Same as S01 — do NOT run `alembic upgrade|downgrade|stamp` against the live DB. Read-only `alembic history / current / show` is fine. Testcontainer execution inside a pytest fixture is fine but S07 owns the real test suite; your job here is file review, not runtime validation beyond what S01 already did.)

## Input Files

- `ai-dev/active/F-00061/F-00061_Feature_Design.md` — particularly **Database Changes**, **Invariants 1/5/7**, **Acceptance Criteria AC3/AC4**
- `ai-dev/active/F-00061/reports/F-00061_S01_Database_report.md` — S01's own claims + migration revision id
- `orch/db/models.py` — S01's model additions (the `QvBaseline` class and the back-populating relationship on `WorkflowStep`)
- `orch/db/migrations/versions/<S01's revision>_add_qv_baselines.py` — the generated migration
- `orch/CLAUDE.md` — ORM rules and reserved-attr gotchas
- `tests/CLAUDE.md` — testcontainer rules (so you can flag any S01 behaviour that would break S07)

## Output Files

- `ai-dev/active/F-00061/reports/F-00061_S02_CodeReview_Database_report.md` — findings table + pass/fail verdict

## Context

You are the independent reviewer of S01's schema delivery. F-00061's correctness depends on three schema properties: (a) uniqueness per `(step_id, gate_name, base_sha)` so AC4's rebase-invalidation reliably deletes-and-replaces rather than duplicates, (b) CASCADE on workflow_step deletion so orphans can't accumulate, and (c) a revision file whose docstring advertises the `iw_core_baseline` marker for the migration pipeline. If any of those fail, the whole feature's contract fails.

## Review Checklist

Walk through each item and record **PASS / FAIL / N/A** with a short note. A FAIL on any CRITICAL item must block the step.

### CRITICAL — must pass

1. **Model fields match the design spec exactly.** `id`, `step_id`, `gate_name`, `base_sha`, `fingerprint`, `computed_at`; types and nullability per the design doc's Database Changes table.
2. **`UniqueConstraint("step_id", "gate_name", "base_sha")` exists** on the model and is reflected in the migration. Without this, AC4's deterministic invalidation breaks down.
3. **`ON DELETE CASCADE`** is set on the FK from `step_id` → `workflow_steps.id`. Without this, Invariant 7 is violated.
4. **Migration up/down symmetric** — downgrading the new revision produces a schema byte-identical to the base (modulo the baseline revision marker). Run `uv run alembic upgrade head` followed by `uv run alembic downgrade -1` inside a testcontainer fixture locally if you want to verify (do NOT hit port 5433). At minimum, read the migration file and confirm `op.drop_table("qv_baselines")` is the sole operation in `downgrade()`.
5. **`iw_core_baseline` marker** appears in the migration's module docstring on its own line (required so the merge pipeline attributes the migration to F-00061).
6. **No other schema changes.** Autogenerate sometimes emits spurious diffs on enum ordering or server_default normalisation; these must NOT appear in the final file. Diff the migration against the base-SHA schema to confirm.

### HIGH — should pass

7. **Relationship wiring on `WorkflowStep`**: `baselines: Mapped[list["QvBaseline"]] = relationship(back_populates="step", cascade="all, delete-orphan")` exists.
8. **No naming collision with SQLAlchemy reserved attrs** (e.g. `metadata`). The existing `DaemonEvent.event_metadata` pattern is a precedent — confirm `QvBaseline` has no such collision.
9. **`fingerprint` default is an object with a `failures` list** (e.g. `server_default=text("'{\"failures\": []}'::jsonb")`) — aligns with Invariant 5's semantic distinction between "missing row" and "empty row".
10. **`index=True` on `step_id`** so lookups in S05 (`baseline_for(step, gate, sha)`) don't full-scan.

### MEDIUM_SUGGESTION — nice to have

11. Docstring on the `QvBaseline` class briefly explains its role and references F-00061.
12. The model sits near `FixCycle` in the file (cohesion with other workflow-related tables).

## Verification Commands (read-only)

- `uv run mypy orch/db/models.py` — must pass
- `uv run ruff check orch/db/models.py orch/db/migrations/versions/` — zero NEW errors
- `uv run alembic history --verbose` — revision appears at head; only one revision was added by S01
- `git diff main..HEAD -- orch/db/models.py orch/db/migrations/versions/` — diff contains ONLY the F-00061 additions; no collateral changes

## Report

Write `ai-dev/active/F-00061/reports/F-00061_S02_CodeReview_Database_report.md` with:
- Per-checklist verdict table (PASS/FAIL/N/A + note)
- Overall verdict (**pass** only if no CRITICAL FAIL)
- Any fix recommendations (with file:line references) grouped by severity: CRITICAL, HIGH, MEDIUM_FIXABLE, MEDIUM_SUGGESTION

On **pass**, call `uv run iw step-done F-00061 --step S02 --report ai-dev/active/F-00061/reports/F-00061_S02_CodeReview_Database_report.md`.
On **fail**, call `uv run iw step-fail F-00061 --step S02 --reason "<short>" --report <path>`.

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "F-00061",
  "steps_reviewed": ["S01"],
  "verdict": "pass|fail",
  "findings": [
    {"severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION", "file": "path", "line": N, "description": "..."}
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "mypy clean; ruff clean on changed files; alembic history clean",
  "notes": ""
}
```

`verdict: "pass"` only if zero CRITICAL findings AND zero HIGH findings. `mandatory_fix_count` is the count of CRITICAL + HIGH. The fix-cycle will be triggered if `mandatory_fix_count > 0`.
