# CR-00058 Self-Assessment Report

**Work Item**: CR-00058 — Configurable per-project scope-overlap gate with block/allow policy
**Step**: S15 (self-assess-impl)
**Analysis run**: 2026-05-18

---

## Item Analysis: CR-00058

**Bottom line**: S02 agent (tests-impl) crashed twice in succession, requiring operator-level manual recovery to write the integration test file. This is the highest-impact finding: agent stability failures force human intervention and mask whether the tests would have passed under agent execution.

**Steps analyzed**: 14 (S01–S14)
**Steps with retries**: S01 (2 runs), S02 (2 crashes → manual recovery), S03 (4 runs), S13 (3 runs), S14 (3 runs)
**Total fix-cycles**: S06, S08 (2 fix cycles)
**DB signal**: yes (DB:UP confirmed)

---

## Findings

### [1] S02 agent crashed twice, requiring operator-level manual test write

**Severity**: HIGH | **Class**: agent | **Frequency**: one-off (but impact was HIGH)

**Evidence**:
- `.worktrees/CR-00058/ai-dev/logs/CR-00058_S02_run1.log` — "Process exited without reporting completion (PID dead)" after ~180 s, agent still in directory-read phase
- `.worktrees/CR-00058/ai-dev/logs/CR-00058_S02_run2.log` — same crash pattern, PID dead before producing any test file
- `ai-dev/active/CR-00058/reports/CR-00058_S02_Tests_report.md:12` — "Both run logs show the agent still in the 'read context / list directory' phase when it crashed; no test file was created and `iw step-done` was never called. With the per-step retry budget exhausted, the operator wrote the integration test file directly"

**Recommendation**: Check whether `opencode + minimax/MiniMax-M2.7` has a memory or timeout issue for longer test-authoring tasks. If the model is being killed during tool-use sequences (not just idle), investigate the LLM API client's streaming handling. Also consider whether the `tests-impl` prompt could be shortened to reduce the task scope the agent must hold in context.

**Target**: `agents/opencode/tests-impl.py` or `skills/iw-execute/SKILL.md` (add "keep-alive" guidance for long test-authoring steps)

**Pros**: Reduces human intervention on agent crashes; preserves signal that tests were actually authored by the agent (audit completeness).

**Cons**: Model/timeout investigation may be inconclusive; shorter prompts may sacrifice guidance quality.

**If we don't**: Future long test-authoring steps risk the same crash-and-recovery pattern, forcing manual intervention and blurring the boundary between agent and operator work.

**Effort**: M (~5 lines, 1–2 files)

**Paste prompt**: `/iw-new-incident Investigate and mitigate opencode agent crash on long test-authoring steps (S02 of CR-00058 crashed twice, PID dead mid-task); analyzed in ai-dev/active/CR-00058/reports/CR-00058_self_assess_report.md. Target: agents/opencode/tests-impl.py or skills/iw-execute/SKILL.md. Effort: M.`

---

### [2] S01 path typo on first run caused wasted agent time

**Severity**: MED | **Class**: agent | **Frequency**: one-off

**Evidence**:
- `.worktrees/CR-00058/ai-dev/logs/CR-00058_S01_run1.log:11` — "Error: File not found: /home/sgeriog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00058/orch/daemon/batch_manager.py" (missing 's' in 'sergiog')

**Recommendation**: The worktree path in the prompt is correct (`/home/sergiog/...`). The agent appears to have typed the path manually with a typo. This is a single-occurrence issue, but worth flagging if it recurs in other steps — the prompt should be the ground truth for paths, not agent-constructed paths.

**Target**: `skills/iw-execute/SKILL.md` (guidance: use provided paths verbatim; do not re-type)

**Pros**: Eliminates a class of trivial retry caused by path typos.

**Cons**: Very low frequency; may not recur.

**If we don't**: Agents continue to type paths from memory and occasionally mistype, causing wasted retries.

**Effort**: S (~2 lines, 1 file)

**Paste prompt**: `/iw-new-incident Prevent agent path typos causing unnecessary retries (S01 of CR-00058 typed wrong path on first run); analyzed in ai-dev/active/CR-00058/reports/CR-00058_self_assess_report.md. Target: skills/iw-execute/SKILL.md. Effort: S.`

---

### [3] S03 Frontend step had 4 runs due to import/name errors that self-resolved

**Severity**: MED | **Class**: platform | **Frequency**: one-off

**Evidence**:
- `.worktrees/CR-00058/ai-dev/logs/CR-00058_S03_run1.log:45` — `ImportError: cannot import name 'ScopeStatus' from 'dashboard.routers.batches'`
- `.worktrees/CR-00058/ai-dev/logs/CR-00058_S03_run1.log:957` — `ImportError: cannot import name '_get_held_reasons'`
- Multiple `NameError: name '_get_held_reasons' is not defined` in test output (lines 1078–1333)
- `CR-00058_S03_run1.log:68` — "Error: Could not find oldString in the file"
- `CR-00058_S03_run1.log:319` — "Error: Found multiple matches for oldString"
- Tests ultimately passed — the agent self-corrected by run 4

**Recommendation**: This appears to be an agent reasoning issue (wrong function name chosen, then Edit tool mismatches). The function name `_get_held_reasons` vs `_held_reasons_for_items` suggests the agent was working from stale template or memory. The Edit failures ("Could not find oldString", "multiple matches") further suggest the agent was targeting wrong locations. Investigate whether the S03 prompt could be more explicit about which function name to use or provide a grep command to locate the correct definition before editing.

**Target**: `prompts/CR-00058_S03_Frontend_prompt.md` (or the generic frontend-impl skill prompt)

**Pros**: Reduces wasted runs on name-mismatch Edit failures.

**Cons**: Step eventually succeeded; the root cause may be agent-specific rather than prompt-specific.

**If we don't**: Future frontend steps may similarly thrash on import/name errors before self-correcting.

**Effort**: S (~3 lines, 1 prompt file)

**Paste prompt**: `/iw-new-incident Reduce S03-style import/name Edit thrash (CR-00058 S03 ran 4 times with NameError on '_get_held_reasons'); analyzed in ai-dev/active/CR-00058/reports/CR-00058_self_assess_report.md. Target: prompts/CR-00058_S03_Frontend_prompt.md. Effort: S.`

---

### [4] S13 integration tests required 3 runs; browser environment was down on first attempt

**Severity**: MED | **Class**: environment | **Frequency**: one-off

**Evidence**:
- `.worktrees/CR-00058/ai-dev/logs/CR-00058_S13_run1.log:368` — `psql: error: connection to server on socket "/var/run/postgresql/.s.PGSQL.5432" failed: FATAL: role "iw_ai_core" does not exist`
- `.worktrees/CR-00058/ai-dev/logs/CR-00058_S13_run1.log:376` — `psql: error: ... role "postgres" does not exist`
- `.worktrees/CR-00058/ai-dev/logs/CR-00058_S13_run1.log:384` — `psql: error: ... role "iw" does not exist`
- `.worktrees/CR-00058/ai-dev/logs/CR-00058_S13_fix1.log` — fix cycle log (10262 bytes)
- S13 final run passed: 369KB log, all tests green
- Browser env was confirmed down via separate logs (`CR-00058_S14_browser_env_down.log:1422 bytes`)

**Recommendation**: The S13 integration tests hit a PostgreSQL auth issue on run1 and required a fix cycle. The role-not-exist errors suggest either a DB auth config issue or the testcontainer wasn't fully up when the agent launched. This is borderline environment vs. platform. The fix cycle resolved it, so it doesn't block — but the pattern of DB-auth failures in integration test runs should be monitored. Consider whether `make allure-integration` should have a built-in health-check that waits for the testcontainer to be fully ready before running pytest.

**Target**: `Makefile` or `executor/` script that runs integration tests

**Pros**: Reduces spurious integration test failures due to premature testcontainer startup.

**Cons**: May add latency to test invocation.

**If we don't**: Integration test runs continue to occasionally hit DB auth failures requiring manual retry or fix cycles.

**Effort**: M (~10 lines, 1–2 files)

**Paste prompt**: `/iw-new-incident Add testcontainer health-check to integration test runner to prevent DB auth failures (CR-00058 S13 had psql role errors on first run); analyzed in ai-dev/active/CR-00058/reports/CR-00058_self_assess_report.md. Target: Makefile or executor/run_integration_tests.sh. Effort: M.`

---

### [5] S05 CodeReview caught CRITICAL metadata key mismatch (dropped_globs vs dropped_block_globs) that would have caused silent UI failure

**Severity**: HIGH | **Class**: platform | **Frequency**: systemic

**Evidence**:
- `ai-dev/active/CR-00058/reports/CR-00058_S05_CodeReview_findings.json:14` — "Event metadata key 'dropped_globs' does not match design doc (dropped_block_globs) or router reader (batches.py:220)"
- Fixed in S06 (`orch/daemon/batch_manager.py:325` renamed `dropped_globs` → `dropped_block_globs`)
- `ai-dev/active/CR-00058/reports/CR-00058_S06_CodeReviewFix_report.md:22` — "The `matched_globs` field on `ScopeStatus` for `policy_allowed` items was always empty (`[]`), causing the tooltip to never show the dropped globs"

**Recommendation**: The bug was a simple rename issue — the UI would have silently shown empty tooltips for allowed items. The CodeReview step correctly caught it (S05 finding F1, CRITICAL). However, the pattern of metadata key mismatches between daemon emit side and router reader side is a recurring risk (also F3 in S05: `blocking` vs `blocking_item_id` which was pre-existing). Consider adding a integration-level test that verifies event metadata keys between emit and read sides are consistent, so this class of bug is caught by the QV gate rather than only by manual code review.

**Target**: `tests/integration/daemon/test_overlap_gate_policy.py` or a new test file in `tests/integration/`

**Pros**: Catches metadata key mismatches automatically; reduces reliance on manual code review for this specific class.

**Cons**: Test maintenance burden; event schema changes would require updating the test.

**If we don't**: Future event metadata key mismatches will only be caught by manual code review steps, not by automated tests.

**Effort**: M (~20 lines, 1 file)

**Paste prompt**: `/iw-new-incident Add automated test for event metadata key consistency between emit and read sides (CR-00058 S05 caught dropped_globs mismatch via manual code review); analyzed in ai-dev/active/CR-00058/reports/CR-00058_self_assess_report.md. Target: tests/integration/daemon/test_event_metadata_contract.py (new). Effort: M.`

---

### [6] TDD RED evidence for S02 integration tests was behavioral description, not direct pytest output (audit note)

**Severity**: MED | **Class**: convention | **Frequency**: systemic

**Evidence**:
- `ai-dev/active/CR-00058/reports/CR-00058_S05_CodeReview_findings.json:23` — "TDD RED evidence is behavioral description rather than direct pytest output. The test file was written manually by the operator after two opencode agent crashes"
- `ai-dev/active/CR-00058/reports/CR-00058_S02_Tests_report.md:55–63` — RED evidence recorded as "pre-S01 behaviour" descriptions rather than actual `AssertionError` snippets

**Recommendation**: The integration tests for CR-00058 were manually written (due to S02 agent crash), so the RED evidence is necessarily a behavioral description. However, for future steps where the agent does write tests, the RED evidence field should contain actual pytest failure output, not just descriptions. This is a prompt/convention issue: agents should be instructed to capture the exact `AssertionError` output when a test fails before implementation. Add explicit guidance to the `tests-impl` prompt template to capture RED evidence properly.

**Target**: `skills/iw-execute/SKILL.md` or the tests-impl agent prompt template

**Pros**: Ensures RED evidence is verifiable and audit-ready.

**Cons**: Slight increase in prompt verbosity.

**If we don't**: Future TDD RED evidence continues to be described behaviorally rather than captured as direct pytest output, reducing auditability.

**Effort**: S (~3 lines, 1 file)

**Paste prompt**: `/iw-new-incident Enforce direct pytest RED evidence capture in tests-impl steps (CR-00058 S02 had behavioral-only RED description due to manual recovery); analyzed in ai-dev/active/CR-00058/reports/CR-00058_self_assess_report.md. Target: skills/iw-execute/SKILL.md. Effort: S.`

---

## Coverage Notes

- S01 run1 log (23KB): read in full — path typo on line 11, 8 FAILED tests captured correctly with AssertionError snippets (tdd_red evidence field in report shows actual error messages). Run2 (92KB): sampled tail via grep on Error/FAILED/PASSED lines.
- S02 run1 (2KB) + run2 (15KB): both showed "Process exited without reporting completion (PID dead)" — read both in full (small files).
- S03 run1 (104KB): read via grep for Error/FAILED lines, found ImportError and NameError patterns; multiple Edit failures (lines 68, 319). Run2–4: not read (agent self-corrected by run 4, confirmed by S06 report).
- S04 (19KB): no errors found in grep pass.
- S05 (16KB): read findings JSON directly (primary evidence).
- S06 (36KB): format error on line 407 only — rest was clean.
- S07 (10KB): no errors found.
- S08 (27KB): only error was missing findings JSON for S07 (line 5) — no actual code errors.
- S09–S12 (small logs, all <110KB): grep pass showed only make errors that were resolved in fix cycles.
- S13 run1 (372KB): large file — sampled via grep for Error/FAILED lines. psql auth errors found on lines 368–399. Run3 (369KB): all green (PASSED lines only). Fix1 (10KB): clean.
- S14 (multiple runs, 35KB/53KB/7KB): browser env failures confirmed via separate `browser_env_down.log`. No actionable platform finding — environment fluctuation resolved naturally.

**DB telemetry**: Full (`iw db-identity check` → DB:UP). No additional DB queries made beyond item-status and identity check.

---

## TDD RED Evidence Check (S01)

S01's report (`CR-00058_S01_Backend_report.md`) contains a `tdd_red_evidence` field with 8 tests and their RED output snippets. All 8 show plausible `AssertionError` messages (e.g., `'orch/foo.py' not in ['docs/X.md']`, `[] != [('F-00001', ['src/app/main.py'])]`). ✅ Present and valid.

S02's report states RED evidence as behavioral descriptions (no direct pytest output) because the operator wrote the tests manually after agent crashes. ⚠️ Audit note — no direct pytest output available.

---

## Notes

- The implementation is clean: all QV gates passed (S09–S13), browser verification completed (S14), 106 targeted tests pass.
- No CLAUDE.md convention violations detected (no docker commands, no playwright install, no agent-browser usage).
- Fix cycles were productive: S06 fixed the CRITICAL metadata key issue, S08 confirmed clean.
- The most actionable finding is the S02 agent crash pattern — it directly caused operator intervention and loss of agent-authored test signal.