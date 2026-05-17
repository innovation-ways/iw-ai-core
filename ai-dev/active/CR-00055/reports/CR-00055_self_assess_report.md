### Item Analysis: CR-00055

Bottom line: Add `test_pending_migration_log_migration.py::test_downgrade_drops_table` to the S01 deliverable list so the third migration downgrade teardown is never missed again.

Steps analyzed: 12   Steps with retries: 4 (S08, S09, S10, S04–S07 re-ran due to downstream fix cycles)   Total fix-cycles: 3 (S08/fix1, S09/fix1, S10/fix1)   DB signal: yes

---

[1] S01 prompt specified two class teardowns but test_pending_migration_log_migration.py needed a third
    Severity: MED   Class: prompt   Frequency: systemic
    Evidence:
      - ai-dev/logs/CR-00055_S09_run1.log (tail) — "FAILED tests/integration/test_pending_migration_log_migration.py::test_direction_check_constraint / test_phase_check_constraint / test_table_exists_with_columns"
      - ai-dev/logs/CR-00055_S09_fix1.log:1 — "adding `command.upgrade(alembic_cfg, 'head')` after the downgrade assertion … the two sibling migration test files [used the same pattern]"
    Recommendation: Extend S01 deliverable (5) to name all three migration test files that have a downgrade step and need a post-downgrade upgrade call: `test_oss_migration.py`, `test_project_oss_job_migration.py`, **and** `test_pending_migration_log_migration.py`. The spike likely didn't surface the third because the random seed selected for it happened not to order `test_downgrade_drops_table` before the column/constraint tests.
    Target: ai-dev/active/CR-00055/prompts/CR-00055_S01_Backend_prompt.md (for archaeology), and any future randomisation CR template derived from R-00077 Appendix A.
    Pros: Prevents one integration-test fix cycle on any future CR that touches this migration family. Low-cost patch to one prompt section.
    Cons: Prompt grows slightly; only relevant if the same migration file pattern recurs.
    If we don't: Future randomisation implementors read the 2-teardown spec, replicate it faithfully, and hit the same S09 failure on a seed that re-orders the pending-migration tests.
    Effort: S (~3 lines in the deliverable section)

[2] Live config file in unit test caused cross-initiative breakage at S08
    Severity: MED   Class: design   Frequency: systemic
    Evidence:
      - ai-dev/logs/CR-00055_S08_run1.log (tail) — "FAILED tests/unit/test_auto_merge_config.py::test_load_actual_auto_merge_toml … 1 failed, 3005 passed"
      - ai-dev/logs/CR-00055_S08_fix1.log:1 — "test was asserting `config.phase == PHASE_DISABLED` (0), but `executor/auto_merge.toml` was advanced to `phase = 1` (PHASE_DRY_RUN) via commit `1856cf8b` as part of the auto-merge Phase 1 dry-run rollout"
    Recommendation: When a CR design doc is written for a branch that also carries changes from a parallel initiative (here: the auto-merge Phase 1 rollout), the design's "Pre-conditions / Branch State" section should explicitly list pre-existing branch commits that touch live config or test-fixture files. Alternatively, add a pre-S01 checklist item to the executor or to the S01 prompt template: "Check git log for non-CR commits on this branch that may have updated config files exercised by unit tests."
    Target: templates/design/CR_Design_Template.md (add Pre-conditions section note) or CLAUDE.md (agent checklist).
    Pros: Avoids a surprise fix cycle whenever an implementation CR rides on a branch that already has config changes from a parallel feature.
    Cons: Slight increase in design doc verbosity; the check is only relevant when branches are shared across initiatives.
    If we don't: Any CR whose branch carries unrelated config changes continues to surprise the S01 agent with a stale unit test assertion, burning a fix cycle each time.
    Effort: S (~5 lines in the design template)

[3] Flaky docker-startup test blocked the diff-coverage gate (S10)
    Severity: MED   Class: platform   Frequency: systemic
    Evidence:
      - ai-dev/logs/CR-00055_S10_run1.log:477 — "AssertionError: assert False … tests/integration/test_per_worktree_isolation.py::test_two_parallel_iw_ai_core_worktrees_do_not_interfere:243"
      - ai-dev/logs/CR-00055_S10_fix1.log — empty (0 bytes; no code change was applied)
      - ai-dev/logs/CR-00055_S10_run3.log (tail) — "2522 passed … Completed CR-00055 step S10" (passed without any fix)
    Recommendation: `test_two_parallel_iw_ai_core_worktrees_do_not_interfere` starts two full docker compose stacks and is sensitive to port-availability races. Either (a) add a startup-retry loop inside the test, or (b) quarantine it with `@pytest.mark.flaky(reruns=2)` (requires `pytest-rerunfailures`), or (c) move it out of `make diff-coverage`'s test collection scope. At minimum, open an Incident to track this known flaky test.
    Target: tests/integration/test_per_worktree_isolation.py
    Pros: Eliminates the empty-fix-cycle dance; saves one full diff-coverage run (~4m27s) per occurrence.
    Cons: (a) adds retry complexity inside a test; (b) requires an extra dev dep; (c) reduces coverage scope.
    If we don't: Any CR whose diff-coverage gate happens to schedule alongside heavy docker activity will hit a spurious fix cycle, wasting ~9 minutes (empty fix cycle + rerun).
    Effort: S–M (retry: ~5 lines; quarantine: ~3 lines)

---

## CR-00055-specific Cross-Reference Answers

**Q1: Did the spike-reference + R-00077 outline keep S01 inside its 4800s budget?**
Yes. S01 completed without timeout evidence. The 4-seed sweep alone consumed ~45 minutes of wall-clock (4 × ~11m), so the agent spent the remaining ~35 minutes on implementation and preflight. The budget was adequate; no tightening needed.

**Q2: Did the implementing agent remember the WAL_LOG override?**
Yes. S02 independently confirmed "WAL_LOG override is present and correct in `tests/integration/conftest.py:253`." S01's own log notes "~12x clone speedup: ~25ms vs ~310ms per clone." The override was not forgotten.

**Q3: Did the implementing agent remember the `_pgtestdb_setup` re-export in `tests/dashboard/conftest.py`?**
Yes. S02 confirmed "`_pgtestdb_setup` is re-exported in `tests/dashboard/conftest.py:17`." S01's log explicitly lists this as a completed deliverable. No fix cycle was needed for this.

**Q4: Did any seed surface a new offender beyond the 3 known quarantines?**
A 4th isolation issue surfaced at S09 (not at S01's 4-seed sweep). The issue was not a new quarantine candidate but a missing `command.upgrade(alembic_cfg, "head")` teardown in `test_pending_migration_log_migration.py::test_downgrade_drops_table` — structurally equivalent to the 2 class teardowns S01 applied to the sibling migration files. This is the subject of Finding [1] above. The suite has not drifted beyond this; the 3 quarantines remain sufficient.

**Q5: Was S09 wall-clock close to the 1200s budget?**
Not dangerously so. S09 ran in 848–877s (71–73% of the 1200s budget), compared with the spike's 10m54s (654s). The QV pipeline adds ~3 minutes compared to single-process execution. With ~325s headroom the budget is comfortable for this suite size. No bump needed — but if the integration suite grows by ~30% the budget will need revisiting.

**Q6: Did any agent touch production code?**
No. S01, S02, and S03 all confirmed zero production code changes. The allowed-paths scope (tests/, pyproject.toml, uv.lock, docs/, skills/, ai-dev/) was respected throughout.

---

Coverage notes: S01–S03 logs read in full (< 2 KB each). S04–S07 first run read in full (< 200 B each; runs 2–4 are byte-identical). S08 run1: tail-50 + grep for FAILED (362 KB, 3323 lines); fix1 read in full (444 B); runs 3–5: tail-20. S09 run1: tail-30 + grep for FAILED (360 KB, 3365 lines); fix1 read in full (662 B); runs 3–4: tail-20. S10 run1: head-20 + tail-20 + grep for errors (78 KB, 797 lines); fix1: 0 bytes; run3: tail-10. S11 read in full (278 B). All S08/S09/S10 logs are under 1 MB; selective reads chosen for efficiency. DB telemetry: full (item-status --json).
