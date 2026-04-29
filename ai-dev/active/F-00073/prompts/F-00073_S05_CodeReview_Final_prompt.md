# F-00073_S05_CodeReview_Final_prompt

**Work Item**: F-00073 -- Smoke Gate + Active Test CI + Logging Tests
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S03

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

(Standard policies.)

## Input Files

- `ai-dev/active/F-00073/F-00073_Feature_Design.md`
- All step reports under `ai-dev/active/F-00073/reports/`
- All files modified by S01 and S03

## Output Files

- `ai-dev/active/F-00073/reports/F-00073_S05_CodeReview_Final_report.md`

## Review Checklist

### 1. Completeness vs Design

- [ ] All 6 ACs implemented.
- [ ] All 8 invariants verifiable.
- [ ] No "Out of Scope" items leaked (no Codecov upload, no perf testing, no mutation testing).

### 2. Cross-step consistency

- [ ] Marker name `smoke` used consistently in pyproject + Makefile + test markers + test-quality.yml + smoke regression test.
- [ ] Job names in workflow match smoke regression guard's parametrize list.
- [ ] Smoke set actually contains the 10 paths from the design (cross-reference S01 report's `smoke_test_inventory`).

### 3. F-00069 dependency

- [ ] Design doc's `Depends on: F-00069` is still accurate.
- [ ] Nothing in this implementation overrides F-00069's coverage threshold.
- [ ] `make smoke` does not invoke `--cov-fail-under` (verified).
- [ ] CI workflow's `unit` job benefits from F-00069's threshold gate (verify by reading the make target chain).

### 4. CI safety

- [ ] All `uses:` SHA-pinned (40-char).
- [ ] Permissions `contents: read` only.
- [ ] No secrets used; no Codecov token.
- [ ] Postgres major matches `docker-compose.bootstrap.yml`.
- [ ] Coverage XML artefact uploaded with `if: always()`.

### 5. Logging tests honesty

- [ ] If a credential leak was found, it was raised as a blocker, not silenced.
- [ ] If no leak, the test asserts on real behavior (not a tautology).

### 6. Holistic test pass

1. `make lint`
2. `make format`
3. `make typecheck`
4. `make test-unit`
5. `make test-integration`
6. `make smoke` — under 60s wallclock
7. `make check`

## Severity Levels (standard)

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
  "work_item": "F-00073",
  "steps_reviewed": ["S01", "S02", "S03", "S04"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, Z smoke passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
