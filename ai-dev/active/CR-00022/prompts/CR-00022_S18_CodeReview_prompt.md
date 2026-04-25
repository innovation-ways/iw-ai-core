# CR-00022_S18_CodeReview_prompt

**Work Item**: CR-00022
**Step Being Reviewed**: S17 (tests-impl)
**Review Step**: S18
**Agent**: code-review-impl

---

## ⛔ Docker / Migrations off-limits

Standard rules.

## Input Files

- Design + S17 report
- All test files added/modified by S17

## Output Files

- `ai-dev/active/CR-00022/reports/CR-00022_S18_CodeReview_report.md`

## Review Checklist

### 1. AC coverage

Walk every AC in the design (AC1–AC12). For each, identify which test(s) cover it. Any AC without a test is a HIGH finding.

### 2. Test isolation

- Tests use `tmp_path` fixture for working-tree writes — never the actual repo?
- Testcontainer fixtures used for DB-touching tests (no live port 5433)?
- `monkeypatch` used for env var overrides (no `os.environ[...] = ...`)?
- No cross-test state leak (each test isolated)?
- No tests connect to localhost:5433?

### 3. Idempotency test correctness

`test_oss_fix_recipes_idempotent.py`:
- Parametrised over `list_recipes()` so every recipe is exercised?
- `_snapshot` captures all files under `tmp_path` so the comparison is total?
- Test fails meaningfully (recipe.check_id in error message)?

### 4. Catalog completeness test

- AST walk handles all check files?
- Both directions tested (missing + orphan)?
- Required-fields test covers all four fields?
- Brand-voice not asserted (out of scope)?

### 5. Hash consistency test

`test_oss_honor_accepted.py` includes a golden test asserting the dashboard hash and the CI hash agree on a known fixture? Without this, hash divergence ships silently.

### 6. Migration test

- Pre-migration row insertion test exists?
- Post-migration: enum values asserted as exact sets (not just "contains")?
- Downgrade asserted to raise `NotImplementedError`?

### 7. Removed-route tests

- `POST /oss/prepare` → 404?
- `POST /oss/publish` → 404?

### 8. Project conventions

- `tests/CLAUDE.md` rules followed (FTS_FUNCTION_SQL after create_all, psycopg URL prefix replace, no `importlib.reload(orch.config)`)?
- Slow tests marked `@pytest.mark.integration`?

### 9. Run the suite

```bash
make test-unit
make test-integration -- tests/integration/test_oss_*
```

Anything failing is a finding.

## Output Report

Findings + verdict + step-done/fail.
