# F-00061 S02 Fix Cycle 1/5

The code review for step S02 of work item F-00061 found issues that must be fixed.

## Findings to Fix

### `step_id` is `Integer` instead of `BIGINT`

**File**: `orch/db/models.py:688–691`
```python
step_id: Mapped[int] = mapped_column(
    Integer,          # ← should be BigInteger per design spec
    nullable=False,
    comment="FK to workflow_steps.id",
)
```

**File**: `orch/db/migrations/versions/3035dfc20db5_add_qv_baselines_table_f_00061.py:33–39`
```python
sa.Column(
    "step_id",
    sa.Integer(),     # ← should be sa.BigInteger() per design spec
    nullable=False,
    comment="FK to workflow_steps.id",
),
```

**Design doc requirement** (`F-00061_Feature_Design.md`, Database Changes table):
```
- `step_id BIGINT NOT NULL` — FK `workflow_steps(id)` ON DELETE CASCADE
```

The design explicitly calls for `BIGINT` (64-bit signed integer) but S01 used `Integer` (32-bit signed integer). While this will not cause a runtime FK failure (since `workflow_steps.id` is also `Integer`), it is a deviation from the stated specification. The specification is the source of truth for the feature contract.

**Fix required**: Change `Integer` → `BigInteger` for `step_id` in both `models.py` and the migration file.

---

## Mandatory Fix Count

| Severity | Count |
|----------|-------|
| CRITICAL | 1 |
| HIGH | 0 |
| Total | **1** |

S01 must fix the `step_id` type deviation before S02 can be marked pass.

---

## Constraints

1. **Only fix the flagged issues.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run tests after every fix.** Ensure no regressions.


## Instructions

1. Read the findings above carefully
2. Apply the minimum changes needed to resolve each finding
3. Run tests to verify no regressions
4. Exit when done — the daemon will detect completion and re-run the review

**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
