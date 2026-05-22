### Item Analysis: CR-00076

**Bottom line:** The CR's test infrastructure is sound and all gates passed cleanly, but execution was materially complicated by an S01 runtime failure (context-window crash requiring operator recovery), an S01 tdd_red_evidence gap in the FTS module (proxy-verified vs. actual deliberate-break capture), and an S10 diff-coverage failure whose root cause was an `origin/main` sync staleness problem — not a CR-00076 defect — that masked whether the new data-layer modules actually triggered any coverage diff.

**Steps analyzed:** 11 (S01–S11; S12 is this step) | **Steps with retries:** 3 (S01, S09, S10) | **Total fix-cycles:** 2 (S09 retry, S10 fix+retry) | **DB signal:** yes (DB:UP)

---

[1] S10 diff-coverage failure root cause was `origin/main` staleness, not CR code
> **Severity:** HIGH | **Class:** environment | **Frequency:** systemic | **Target:** iw-ai-core

The S10 quality gate failed with `diff-coverage failed: exit=2`, caused by `test_bootstrap_concurrent_calls_create_exactly_one_tab` failing under `pytest --cov-append`. The agent attempted a fix cycle. S10_run3 fixed it by syncing `origin/main` to match local `main` (log line 1: `# I-00084: sync stale origin/main so diff-cover compares against actual local main`). After the sync, diff-cover reported `No lines with coverage information in this diff` — meaning CR-00076 touches no production code (as expected for a test-infrastructure CR) and the failing test was unrelated pre-existing flakiness.

The concurrent bootstrap test (`test_bootstrap_concurrent_calls_create_exactly_one_tab`) passes in S09_run2 and in isolation but fails only under coverage-append + diff-coverage gate. The underlying flakiness was not introduced by CR-00076. The S10 fix cycle correctly identified and fixed the `origin/main` staleness as the actionable trigger, not the test itself.

**Recommendation:** The diff-coverage gate's `--compare-branch=origin/main` assumption is fragile when `origin/main` lags local `main`. Add a pre-flight `git fetch origin` step to the diff-coverage Makefile target, or document that operators should ensure `origin/main` is current before launching CR worktrees. The concurrent-tab test remains pre-existing flaky but is out of scope for this CR.

**Target:** `Makefile` (diff-coverage target), `docs/IW_AI_Core_Testing_Strategy.md` (gate documentation)

**Pros:** Robust diff-coverage comparisons; no future CR blocked by stale remote branch.
**Cons:** Minor pre-flight latency (~5s git fetch).
**If we don't:** Future CRs with test-infrastructure scope (no production code delta) will still fail diff-coverage for non-code reasons.
**Effort:** S (~3 lines in Makefile)

---

[2] S01 context-window crash forced operator recovery; S01 agent self-reported completion without step-done
> **Severity:** HIGH | **Class:** agent | **Frequency:** one-off | **Target:** iw-ai-core

The S01 backend-impl agent ran on `pi` runtime with `minimax/MiniMax-M2.7` and hit `context window exceeds limit (2013)`. The step never reached a clean finish: no `step-done`, no clean agent report, a junk nested directory was created, and the agent had whitelisted two of its own (later-renamed) tests in `tests/assertion_free_baseline.txt`. The step was killed and the deliverable produced manually by the operator.

The S01 report (`CR-00076_S01_Backend_report.md`) documents the operator-recovery state, but the agent did not itself call `step-done` — the step was marked `skipped` by the operator. This creates a process gap: the agent self-reported completion without executing the lifecycle command.

**Recommendation:** For context-window risks, the prompt for S01 (and similar long-inference steps) should instruct the agent to call `step-done` incrementally or checkpoint mid-deliverable. Alternatively, the executor should treat `context window exceeded` as an automatic retry trigger rather than a silent compactor-resume.

**Target:** `skills/iw-execute/SKILL.md` or executor logic (`executor/` scripts)

**Pros:** Future long steps won't silently fail; operator recovery becomes unnecessary.
**Cons:** Requires executor/instrumentation change.
**If we don't:** Future long-inference steps may silently produce incomplete work without calling step-done.
**Effort:** M (~executor + skill update)

---

[3] S01 tdd_red_evidence for FTS module was proxy-verified, not a full deliberate-break capture
> **Severity:** MED | **Class:** prompt | **Frequency:** one-off | **Target:** iw-ai-core

The S01 report transparently notes that the FTS module's failability evidence was "proxy-verified via assertion scanner rather than a full deliberate-break-then-revert cycle." This was accepted by S02/S03 as acceptable given transparency. However, it is a process gap: S01 should never report completion without actual failing-output evidence for each test module.

**Recommendation:** Update the S01 prompt template to require a specific `tdd_red_evidence` section with three entries (one per module for this CR). S01 agent must capture actual failing output before reverting. Enforce this in the pre-flight checklist.

**Target:** `templates/design/Feature_Template.md` (or the CR design prompt for test-infrastructure items), `docs/IW_AI_Core_Testing_Strategy.md`

**Pros:** Complete failability evidence for every test-infrastructure CR; audit trail.
**Cons:** Slightly longer S01 execution (must run deliberate-break cycles).
**If we don't:** Future test-infrastructure CRs may proxy-verify instead of actual-verify.
**Effort:** S (~prompt template update)

---

[4] S01 tsvector column enumeration required manual inspection of `orch/db/models.py`
> **Severity:** LOW | **Class:** design | **Frequency:** one-off | **Target:** iw-ai-core

The three `tsvector` columns (`work_items.design_doc_search`, `work_items.functional_doc_search`, `project_docs.content_search`) were found by inspecting `orch/db/models.py`. They were all correctly enumerated on first pass (no missed columns caught in review), but the enumeration process was not documented in any design doc — an agent discovering data-layer invariants would have no guidance on where to find them. The S02/S03 reviews confirmed all three columns were covered; no column was missed.

**Recommendation:** Document the tsvector column discovery path in `docs/IW_AI_Core_Testing_Strategy.md` (already updated with sub-package note) and consider adding a `data_layer_discovery_notes` section to future CR design docs for test-infrastructure items.

**Target:** `docs/IW_AI_Core_Testing_Strategy.md`

**Pros:** Reduces agent discovery effort for future data-layer test CRs.
**Cons:** Documentation maintenance overhead.
**If we don't:** Agents discovering data-layer invariants have no canonical "where to look" guidance.
**Effort:** S (~doc update)

---

[5] S01 agent orphaned baseline-whitelist entries and a junk nested directory
> **Severity:** LOW | **Class:** convention | **Frequency:** one-off | **Target:** iw-ai-core

During the context-window crash recovery, two now-renamed test names had been added to `tests/assertion_free_baseline.txt` and a junk `ai-dev/active/CR-00076/CR-00076/` directory existed. Both were cleaned up manually during operator recovery. These are symptoms of an agent that crashed mid-execution without a clean rollback path.

**Recommendation:** The executor should ensure that any file modifications are tracked and rolled back if a step is killed mid-execution. Alternatively, the assertion-scanner baseline file should be in a scope that the executor validates before step completion.

**Target:** `executor/` scripts, `tests/assertion_free_baseline.txt` conventions

**Pros:** Prevents orphaned baseline entries; cleaner worktree state on crash.
**Cons:** Executor complexity increase.
**If we don't:** Mid-crash file modifications persist and may pollute future step scopes.
**Effort:** M (~executor enhancement)

---

### Additional Observations

- S01's `test_migration_revision_skew.py` did produce genuine RED evidence: both `test_upgrade_head_fails_on_bogus_revision` (NameError → real assertion path) and `test_upgrade_head_succeeds_with_valid_head` (DuplicateTable on broken re-upgrade design) actually failed during recovery. This is the gold-standard evidence the FTS module lacked.
- `make data-layer-check` succeeded end-to-end on first attempt in S03: `migration-check` prerequisite passed cleanly (3 passed) before running `data_layer/` tests (15 passed). No latent issue surfaced.
- All 11 prior steps (S01–S11) produced complete step-done calls; no orphaned in-progress state.
- S09 ran for 18+ minutes (1118s) for the full integration suite; this is pre-existing suite perf, not a CR-00076 defect.

### Summary

| Aspect | Status |
|--------|--------|
| Test modules (`data_layer/`) | ✅ All 15 tests pass; clean |
| `make data-layer-check` | ✅ Exits 0 |
| AC1 FTS invariant | ✅ 6 cases (3 columns × INSERT/UPDATE) |
| AC2 revision-skew | ✅ Specific `CommandError` assertion |
| AC3 DB-identity | ✅ 7 tests all pass |
| No migration / no prod code | ✅ `git diff origin/main` clean |
| S01 operator recovery | ⚠️ Context-window crash; manual fix required |
| tdd_red_evidence completeness | ⚠️ FTS module proxy-verified; revision-skew actual |
| S10 diff-coverage | ✅ Fixed via origin/main sync; no real failure |
| S09 flaky test (pre-existing) | ℹ️ `test_bootstrap_concurrent_calls_create_exactly_one_tab` |