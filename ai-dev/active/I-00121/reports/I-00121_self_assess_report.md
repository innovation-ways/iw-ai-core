### Item Analysis: I-00121

**Bottom line**: The implementation was correct and complete; the real cost was in QV gate instability driven by Docker/testcontainer infrastructure failures on this host, not by code defects. Add per-file suppression granularity to the `test-assertions` QV gate so that new test files with legitimate structural patterns (e.g., `assert ("foo" in cmd)` with noqa comments) don't fail the gate on first run.

**Steps analyzed**: 13 implementation/QV steps | **Total retries**: 27 | **Total fix-cycles**: 8 | **DB signal**: yes

---

[1] **`test-assertions` QV gate fires on suppressed-pattern tests at first run**
Severity: MED | Class: platform | Frequency: systemic
Evidence:
  - `ai-dev/logs/I-00121_S09_run1.log:1` — `tests/unit/test_test_runner_allure_env.py:24: tautology: test_make_command_injects_pytest_addopts_alluredir: every assert matches a tautological form`
  - `ai-dev/logs/I-00121_S09_run1.log:1` — (4 more tests in the same file flagged, all with `noqa: PT018` in source)
  - `scripts/check_test_assertions.py:45` — tool flags PT018 tautology category before reading noqa suppression comments
Recommendation: Change `scripts/check_test_assertions.py` to read noqa suppression comments from the source file before emitting failures, so that test authors who guard assertions with `# noqa: PT018` are not forced through a fix cycle. Alternatively, add a project-level config (`pyproject.toml` or `.ruff.toml`) that marks `tests/unit/test_test_runner_allure_env.py` as a known-ok file for the PT018 rule.
Target: `scripts/check_test_assertions.py`, `Makefile`
Pros: Fix cycle 1 on S09 was entirely avoidable; the noqa comments were in the source from the first test write.
Cons: Changes the QV gate tool — needs validation against the full test suite.
If we don't: Every future item that writes tests with `# noqa: PT018` will burn one fix cycle on S09 before the gate stabilises.
Effort: M (~30 lines, 1-2 files)

---

[2] **S10 `make test-unit` is non-deterministically flaky due to Docker port exhaustion**
Severity: HIGH | Class: environment | Frequency: recurring
Evidence:
  - `ai-dev/logs/I-00121_S10_run4.log:1` — `docker.errors.APIError: 500 Server Error ... failed to bind host port 0.0.0.0:44273/tcp: address already in use`
  - `ai-dev/logs/I-00121_S10_run6.log:1` — `failed to bind host port 0.0.0.0:44433/tcp: address already in use`
  - `ai-dev/logs/I-00121_S10_run8.log:1` — `failed to bind host port 0.0.0.0:44521/tcp: address already in use`
  - `ai-dev/logs/I-00121_S10_run10.log:1` — (63 errors, worst case)
  - `ai-dev/logs/I-00121_S10_run13.log:1` — `testcontainers-ryuk: failed to bind host port 0.0.0.0:46402/tcp`
Recommendation: Add `TESTCONTAINERS_RYUK_DISABLED=true` to the `Makefile`'s `test-unit` target environment, and document in `docs/IW_AI_Core_Testing_Strategy.md` that this variable should be set host-wide or in `.env`. The Ryuk cleanup container is consuming ports that concurrent testcontainers need.
Target: `Makefile`, `docs/IW_AI_Core_Testing_Strategy.md`
Pros: S10 on this host was 14 runs; disabling Ryuk would likely reduce to 1-2 runs. All I-00121 in-scope tests (42 unit + 3 integration) passed on every run where Docker didn't exhaust ports.
Cons: Ryuk cleanup container won't run — potential for orphaned containers if tests crash. Mitigation: periodic `docker container prune` cron.
If we don't: Every item with Docker-using integration tests in its test-unit target will be flaky on this host, burning multiple fix cycles and QV retries per step.
Effort: S (~5 lines, 1 file + 1 doc)

---

[3] **S11 `make test-integration` — same Docker port exhaustion, different manifestation**
Severity: MED | Class: environment | Frequency: one-off (but recurring pattern with S10)
Evidence:
  - `ai-dev/logs/I-00121_S11_run1.log:1` — `psycopg.OperationalError: connection failed: FATAL: database "iwcore_template_tdzhjoecyeibvnnm" does not exist`
  - `ai-dev/logs/I-00121_S11_run1.log:48` — 48 ERRORs from testcontainers fixtures failing to start (same port-exhaustion root cause as S10)
Recommendation: Same as [2] — disable Ryuk in test-integration environment. Additionally, consider adding `--force-color` or `-p no:randomly` to reduce parallelism-related port contention.
Target: `Makefile`
Pros: Fixes both S10 and S11 simultaneously.
Cons: Same as [2].
If we don't: S11 will be flaky on every integration-test-heavy item.
Effort: S (~2 lines)

---

[4] **S06–S08 QV gates each ran 6 times despite passing on run 1**
Severity: MED | Class: platform | Frequency: systemic
Evidence:
  - `ai-dev/logs/I-00121_S06_run1.log` — `All checks passed!` (run 1 passed)
  - `ai-dev/logs/I-00121_S06_run2.log` through `ai-dev/logs/I-00121_S06_run6.log` — all 5 subsequent runs also passed but were still recorded
  - Same pattern for S07 and S08
Recommendation: Investigate why QV gates that pass on run 1 are being re-triggered 5 more times. Likely root cause: the item's step-done handler is recording the step complete but the orchestrator's loop is picking up the step as still pending. Check `orch/daemon/` step-tracking logic for a race condition where `step_completed` is set but the polling loop re-reads the step before the commit is visible.
Target: `orch/daemon/worktree_executor.py` (or whichever daemon module handles step completion)
Pros: Eliminates wasted re-runs that count against agent budgets and fill logs.
Cons: Requires careful concurrency testing.
If we don't: Every item wastes 5 QV re-runs per gate; over 100 items/month this is significant noise.
Effort: M (~20 lines, 1 module)

---

[5] **S03 wrote two test files that required S02 review cycles to stabilise**
Severity: LOW | Class: prompt | Frequency: one-off
Evidence:
  - `ai-dev/logs/I-00121_S02_run1.log:1` — S02 run 1 raised concern about git stash left in worktree
  - `ai-dev/logs/I-00121_S02_run2.log:1` — S02 run 2 was a re-run of the same review with no code change
  - `ai-dev/logs/I-00121_S02_run5.log` — 5 total runs to reach a stable PASS
Recommendation: Add a checklist item to the Tests step prompt (`I-00121_S03_Tests_prompt.md`) requiring the agent to confirm no git stash is left in the worktree before declaring the step complete. This was a recurring finding in earlier items too.
Target: `ai-dev/templates/Issue_Test_Template.md` (or the generator that creates test step prompts)
Pros: Removes one source of re-runs on the Tests→CodeReview handoff.
Cons: Very low frequency.
If we don't: Minor friction at handoff; not a systemic problem.
Effort: S (~3 lines in template)

---

### Coverage Notes

All step logs read in full (all < 1 MB). The large S10 run logs (S10_run6.log at 690 KB, S10_run10.log at 808 KB) were read completely — they contained repeated docker port-exhaustion errors which were consistent across runs and fully characterised by the first two runs.

DB telemetry confirmed step durations and completion order, but raw log analysis was the primary evidence source.

TDD RED evidence for S01 was confirmed from `ai-dev/active/I-00121/reports/I-00121_S01_Backend_report.md` — the `ImportError: cannot import name '_build_run_command'` was a valid RED indicating the helper didn't exist before implementation. This is the correct TDD pattern for a newly-extracted pure function.