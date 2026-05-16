# F-00084_S07_CodeReview_Tests_prompt

**Work Item**: F-00084 — LLM-Assisted Merge Conflict Resolution (Phase 0 + Phase 1 dry-run)
**Step**: S07 (Per-agent review of S06 tests)
**Agent**: code-review-impl

---

## Inputs

- `ai-dev/active/F-00084/F-00084_Feature_Design.md`
- `ai-dev/active/F-00084/reports/F-00084_S06_Tests_report.md`
- Diff of test files in S06's `files_changed`
- `skills/iw-ai-core-testing/SKILL.md` — assertion strength, isolation, red-flag checklist

## Output

- `ai-dev/active/F-00084/reports/F-00084_S07_CodeReview_report.md`

## Review Checklist (test-specific)

### AC coverage

- [ ] Every AC (AC1..AC6) has at least one mapped test. List the mapping in the review report.
- [ ] Every row in the Boundary Behavior table has at least one mapped test.
- [ ] Every Invariant (1..8) has at least one mapped test.

### Assertion strength (iw-ai-core-testing rules)

- [ ] No test relies solely on `assert X is not None` as its final assertion.
- [ ] Event-firing tests assert on **specific event_type AND specific metadata keys**, not just "an event row exists".
- [ ] LLM-call tests assert on **call count AND prompt structure**, not just "the mock was called".
- [ ] Git-state tests snapshot `HEAD` + `status --porcelain` and compare; do NOT just check exit codes.
- [ ] No `pytest.approx` on integers or strings.
- [ ] No tests use `time.sleep()` for synchronisation — use deterministic waits or direct DB polling.

### Isolation rules (CLAUDE.md hard rules)

- [ ] No test connects to the live DB (port 5433). All integration tests use testcontainers.
- [ ] No test calls `importlib.reload(orch.config)` — use `monkeypatch.delenv()` instead.
- [ ] FTS_FUNCTION_SQL / FTS_TRIGGER_SQL applied after `Base.metadata.create_all()` in tests that need FTS (auto_merge tests probably don't, but verify).
- [ ] `DaemonEvent.metadata` accessed via Python attribute `event_metadata`.

### LLM-mock hygiene

- [ ] `FakeLLM` (or equivalent) intercepts `invoke_llm_for_file` at the Python boundary — not at `subprocess.run` level (which would couple tests to subprocess semantics).
- [ ] No real LLM call leaks into CI. Search for `claude`, `opencode`, `anthropic` invocations outside the fake; flag any.
- [ ] Mock responses are deterministic; no `random` or `now()` in the fake's response generation.

### Fixture quality

- [ ] `i00085_shape_conflict` and `i00086_shape_conflict` fixtures reproduce the **conflict shape** described in the design — they do NOT depend on this repo's actual git history.
- [ ] Fixtures use `tmp_path` and `git init --bare` patterns from existing `tests/integration/` examples.
- [ ] Fixtures clean up after themselves (pytest's tmp_path is auto-cleaned; verify no global state mutation).

### Coverage

- [ ] S06 reports `orch.daemon.auto_merge` line coverage ≥ 90 %.
- [ ] `merge_queue.py`'s new lines (the F-00084 hook) have at least one test exercising each branch:
  - AUTO_RESOLVE_REQUESTED + phase 0 path
  - AUTO_RESOLVE_REQUESTED + phase 1 path (all good)
  - AUTO_RESOLVE_REQUESTED + phase 1 path (LLM abstain)
  - AUTO_RESOLVE_REQUESTED + phase 1 path (LLM error)
  - AUTO_RESOLVE_SKIPPED path (refuse-list)
  - AUTO_RESOLVE_SKIPPED path (mixed_refuse_list)
  - Neither marker present (today's plain conflict path)
  - Malformed marker (defensive fallback)

### TDD evidence

- [ ] `tdd_red_evidence` in S06's report shows a deliberate-break-and-fix loop that proves the test would actually fail if the contract were broken.
- [ ] No test passes vacuously (e.g., asserting `assert True` or `assert len(...) >= 0`).

### Test naming

- [ ] Test names describe behaviour AC numbers (e.g., `test_ac1_i00085_shape_phase_1_dry_run` not `test_resolution_works`).
- [ ] Files split by concern: `test_auto_merge_phase1.py` for AC1/2/4/5/6, `test_auto_merge_refuse_list.py` for AC3, unit tests by module surface.

### Project conventions

- [ ] Test file names follow `test_*.py` convention.
- [ ] Pytest markers used correctly: `@pytest.mark.integration` on integration tests, plain functions for unit tests.
- [ ] No fixture shadowing existing global fixtures from `conftest.py`.

### Red-flag checklist (from iw-ai-core-testing SKILL.md)

- [ ] No test mutes a real failure with `pytest.skip()` or `xfail`.
- [ ] No test relies on environment variables that aren't set in the fixture.
- [ ] No test assertion is "looser than the design's contract" (e.g., asserting `len >= 1` when the design says exactly 3).
- [ ] No test contains commented-out assertions.
- [ ] No test contains TODO/FIXME without a tracking ticket.

## Severity Mapping

- **CRITICAL** — a real LLM call possible in CI; a test connects to the live DB; coverage < 70 % on the new module.
- **HIGH** — assertion-strength violations; AC or Invariant uncovered; mocking misplaced.
- **MEDIUM** — naming inconsistency; fixture duplication; missing coverage on a Boundary row.
- **LOW** — style.

## Result Contract

Standard code-review JSON.
