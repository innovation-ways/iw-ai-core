# F-00072_S05_CodeReview_Final_prompt

**Work Item**: F-00072 -- Pragmatic Migration Safety + Schema Validation
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S03

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

(Standard policies.)

## Input Files

- `ai-dev/active/F-00072/F-00072_Feature_Design.md`
- All step reports under `ai-dev/active/F-00072/reports/`
- All files modified by S01 and S03

## Output Files

- `ai-dev/active/F-00072/reports/F-00072_S05_CodeReview_Final_report.md`

## Review Checklist

### 1. Completeness vs Design

- [ ] All 5 ACs implemented.
- [ ] All 8 invariants verifiable from the code.
- [ ] No "Out of Scope" items leaked in (no new migration, no alembic.ini edits, no live-DB connection logic changes).

### 2. Cross-step consistency

- [ ] Smoke test in S03 matches what S01 actually ships (test file path, marker name, workflow job structure).

### 3. Integration

- [ ] `make test-integration` passes including the new roundtrip test for the latest 3 revs.
- [ ] `make test-unit` passes including the smoke regression guard.
- [ ] Workflow YAML parses cleanly.

### 4. Architecture

- [ ] No live-DB connections introduced.
- [ ] Test follows established `test_iw_core_instance_migration.py` pattern (module-scoped container, `alembic.command` API, `MonkeyPatch.context()`).
- [ ] Downgrade uses explicit parent revision ID from `ScriptDirectory` — **not** `-1` (rule 4a from `tests/CLAUDE.md`).
- [ ] `downgrade base` reset before each parametrized case to ensure clean state.
- [ ] No new alembic migration was added.

### 5. Security

- [ ] Workflow permissions are `contents: read` only.
- [ ] Action versions all SHA-pinned.
- [ ] No credentials hardcoded (the workflow's POSTGRES_USER/PASSWORD are intentional service-container test credentials, OK).

### 6. Holistic test pass

1. `make lint`
2. `make format-check`
3. `make typecheck`
4. `make test-unit`
5. `make test-integration` — must include the roundtrip test passing
6. `uv run pytest tests/unit/test_migration_roundtrip_targets.py tests/integration/test_migration_roundtrip.py -v`

## Severity Levels

| Severity | Meaning |
|---|---|
| CRITICAL | Live-DB connection introduced; new alembic migration created; workflow permissions elevated beyond contents:read |
| HIGH | AC not fully implemented; invariant violated; integration test suite fails; `alembic check` not in workflow |
| MEDIUM (fixable) | Doc note missing or exceeds 80 words; smoke guard misses an assertion |
| MEDIUM (suggestion) | Structural improvement opportunity |
| LOW | Style |

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
  "work_item": "F-00072",
  "steps_reviewed": ["S01", "S02", "S03", "S04"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
