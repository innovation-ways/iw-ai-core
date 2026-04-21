# F-00058_S09_CodeReview_prompt

**Work Item**: F-00058
**Step Being Reviewed**: S08 (tests-impl)
**Review Step**: S09

---

## Input Files

- `ai-dev/active/F-00058/F-00058_Feature_Design.md` — Boundary Behavior + Invariants
- `ai-dev/active/F-00058/reports/F-00058_S08_Tests_report.md`
- Files listed in S08 report

## Output Files

- `ai-dev/active/F-00058/reports/F-00058_S09_CodeReview_report.md`

## Review Checklist

### 1. Coverage
- Every Boundary Behavior row has a dedicated test.
- Every Invariant (1–7) has at least one dedicated assertion.
- AC5 freshness scenarios exercised.
- SSE reconnect + heartbeat scenarios exercised.

### 2. Isolation (CLAUDE.md)
- Testcontainer Postgres, never the live DB on 5433.
- No `importlib.reload(orch.config)`.
- URL dialect replacement applied.
- FTS trigger installed post create_all().
- Tests order-independent.

### 3. TDD evidence
- S08 report's notes field should confirm red-before-green for new invariant / boundary tests.

### 4. Quality
- Test names describe behavior, not shape.
- Semantic assertions.
- Fixtures reused where sensible.
- No sleeps; SSE heartbeat tests use time mocks, not real time.

### 5. Performance
- Integration test file total runtime under 90s (SSE tests add overhead).

## Test Verification (NON-NEGOTIABLE)

`make test-integration` + `make test-unit` + `make lint` pass.

## Review Result Contract

Standard JSON. `verdict: pass` only when zero CRITICAL + HIGH + MEDIUM_FIXABLE findings.
