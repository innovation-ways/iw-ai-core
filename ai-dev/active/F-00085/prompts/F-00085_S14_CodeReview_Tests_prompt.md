# F-00085_S14_CodeReview_Tests_prompt

**Work Item**: F-00085
**Step**: S14 (Per-agent review of S13 tests)
**Agent**: code-review-impl

---

## Inputs

- F-00085 Feature Design (ACs, Invariants, Boundary table)
- S13 report + diff of test files
- `skills/iw-ai-core-testing/SKILL.md`

## Output

- `ai-dev/active/F-00085/reports/F-00085_S14_CodeReview_report.md`

## Review Checklist

### AC + Invariant + Boundary coverage matrix

- [ ] Every AC1..AC14 has ≥ 1 mapped test. List the mapping in the review report.
- [ ] Every Invariant 1..9 has ≥ 1 mapped test.
- [ ] Every Boundary table row has ≥ 1 mapped test.

### Assertion strength

- [ ] No test relies solely on `assert X is not None` as final assertion.
- [ ] Event-firing assertions name the exact `event_type` AND check specific `event_metadata` keys.
- [ ] Subprocess-mocking assertions check call count AND argument structure.
- [ ] Diff-rendering assertions check that both panes have content (or the documented placeholder).
- [ ] No `pytest.approx` on integers or strings.

### Isolation rules

- [ ] No connection to port 5433 (live DB). All integration tests use testcontainers.
- [ ] `monkeypatch.delenv()` used instead of `importlib.reload(orch.config)`.
- [ ] `DaemonEvent.metadata` accessed via Python attr `event_metadata`.
- [ ] FTS SQL applied after `Base.metadata.create_all()` if FTS-using tests exist.

### LLM-mock hygiene

- [ ] `fake_executor_subprocess` intercepts the subprocess boundary, not via `subprocess.run` patching at module level.
- [ ] No real LLM call leaks into CI. Search the diff for `claude`, `opencode`, `anthropic`, `openai` invocations outside the fake.
- [ ] Health probe tests use `fake_executor_subprocess` exclusively.

### Fixture quality

- [ ] `seeded_events_factory` produces realistic `event_metadata` shapes (matching what F-00084 actually emits + what the new probe + config events emit).
- [ ] `mock_git_show` correctly simulates both success (returncode 0) and failure (non-zero / timeout).
- [ ] All fixtures use `tmp_path` / testcontainer scopes; no global state mutation.

### Coverage

- [ ] S13 report shows aggregator ≥ 90 %, health ≥ 85 %, routes ≥ 85 %.
- [ ] Every new branch in `resolve_project_config` has at least one test path.
- [ ] Every new endpoint has at least one happy-path + at least one error-path test.

### TDD evidence

- [ ] `tdd_red_evidence` in S13 report shows a deliberate-break-and-fix loop.
- [ ] No test passes vacuously.

### Test naming

- [ ] Names follow AC numbers where applicable.
- [ ] Names describe behaviour, not implementation.
- [ ] Files split by concern (observability vs control_surface; unit by module).

### Red-flag checklist (iw-ai-core-testing)

- [ ] No `pytest.skip()` muting a real failure.
- [ ] No `xfail` without a tracking ticket.
- [ ] No assertion looser than the design's contract.
- [ ] No commented-out assertions.
- [ ] No TODO/FIXME without a ticket.

## Severity Mapping

- **CRITICAL** — real LLM call possible in CI; live DB connection; coverage < 70 % on new code; an AC or Invariant uncovered.
- **HIGH** — assertion-strength violations; mocking misplaced; missing fixtures.
- **MEDIUM** — naming inconsistency; Boundary row uncovered.
- **LOW** — style.

## Result Contract

Standard code-review JSON. Include the AC↔test, Inv↔test, Boundary↔test mapping tables in the report body.
