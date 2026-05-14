# CR-00053_S05_CodeReview_prompt

**Work Item**: CR-00053 -- Idempotent `iw next-id` via `--idempotency-key` flag
**Step Being Reviewed**: S01 (database-impl), S03 (backend-impl), S04 (tests-impl)
**Review Step**: S05

---

## ⛔ Docker is off-limits

(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy.)

## Input Files

- `ai-dev/active/CR-00053/CR-00053_CR_Design.md` -- Design
- `ai-dev/work/CR-00053/reports/CR-00053_S01_Database_report.md` -- S01 report
- `ai-dev/work/CR-00053/reports/CR-00053_S03_Backend_report.md` -- S03 report
- `ai-dev/work/CR-00053/reports/CR-00053_S04_Tests_report.md` -- S04 report
- All files listed in the implementation reports' `files_changed`

## Output Files

- `ai-dev/work/CR-00053/reports/CR-00053_S05_CodeReview_report.md` -- Review report (findings with severity)

## Review Checklist

### Schema (S01)
- `IdAllocation` model exists with composite PK `(prefix, number)`. **CRITICAL** if missing or PK shape wrong.
- Partial unique index named `idx_id_allocations_key` on `(prefix, idempotency_key) WHERE idempotency_key IS NOT NULL`. **CRITICAL** if `postgresql_where` is missing — autogenerate misses this routinely; the index would otherwise be a full unique on `(prefix, idempotency_key)` and break the no-key path immediately on second NULL insert.
- `created_at` has `server_default=text("now()")`. **HIGH** if absent.
- Migration `downgrade()` drops index first, then table. **HIGH** if reversed.
- Migration file is committed (not just present in the working tree) per the worktree-DB rule in `CLAUDE.md`. **CRITICAL** if uncommitted.
- `make migration-check` passed in S01's report. **CRITICAL** if not green.

### Allocator behavior (S03)
- `idempotency_key` is **keyword-only** (`*, idempotency_key: str | None = None`). **HIGH** if positional — breaks `batch_commands.py:326` and any other unchanged callers.
- No-key path is **bit-identical** to today: no `id_allocations` write, same FOR UPDATE pattern, same return shape. **CRITICAL** on regression.
- Keyed path is **transactional**: increment of `id_sequences` and INSERT into `id_allocations` are in the same SQLAlchemy transaction. **CRITICAL** if not — a crash between them yields a leaked `id_sequences` increment.
- Concurrent-INSERT race is handled by catching `IntegrityError` and retrying the SELECT, with a retry cap (≤3). **HIGH** if absent — concurrent same-key callers would crash.
- The new `--idempotency-key` Click option is `required=False` with `default=None`. **CRITICAL** if required.
- Output shape on idempotent replay is identical to fresh allocation (plain text and `--json` modes). **HIGH** if different.

### Tests (S03 unit + S04 integration)
- Five unit tests in `tests/unit/test_id_allocations.py` cover AC1–AC4 and the concurrent-INSERT path. **HIGH** if any AC missing.
- TDD RED evidence in S03's report names a real failure (`TypeError` / `AssertionError`), not an import or collection error. **HIGH** if the RED snippet looks like setup failure.
- Three CLI-level integration tests in `tests/integration/test_idempotency_key_cli.py` cover both keyed and unkeyed paths, plain and `--json` output. **HIGH** if the unkeyed regression-guard test is missing.
- Tests use testcontainer Postgres (not sqlite-in-memory). **CRITICAL** if sqlite — the partial unique index uses Postgres-specific `WHERE` syntax.
- Tests follow the FTS-trigger setup rule from `tests/CLAUDE.md`. **MEDIUM** if missing.

### Backwards compatibility
- Grep for all callers of `allocate_next_id` in the repo. S03's report names every one and confirms positional-args compatibility. **HIGH** if any caller would break.

### Out of scope / scope creep
- No changes to `iw register` or `iw doc-update` in this CR — both are explicitly out of scope. **CRITICAL** if changed.
- No changes to dashboard code or the dashboard chat feature. **CRITICAL** if changed.
- No new dependencies in `pyproject.toml`. **HIGH** if any.

## Output

Write the review report at `ai-dev/work/CR-00053/reports/CR-00053_S05_CodeReview_report.md`. Group findings by severity (`CRITICAL` / `HIGH` / `MEDIUM` / `LOW`). For each finding, name the file + line and quote 1–3 lines of evidence. If everything passes, write `findings: []` and explicitly state "no CRITICAL/HIGH findings; S06 may be a no-op."

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-impl",
  "work_item": "CR-00053",
  "completion_status": "complete",
  "files_changed": [
    "ai-dev/work/CR-00053/reports/CR-00053_S05_CodeReview_report.md"
  ],
  "preflight": {
    "format": "ok|skipped:no-code-changes",
    "typecheck": "ok|skipped:no-code-changes",
    "lint": "ok|skipped:no-code-changes"
  },
  "tests_passed": true,
  "test_summary": "review — no production code changed",
  "tdd_red_evidence": "n/a — review step",
  "blockers": [],
  "notes": "Findings count: CRITICAL=X HIGH=Y MEDIUM=Z LOW=W"
}
```
