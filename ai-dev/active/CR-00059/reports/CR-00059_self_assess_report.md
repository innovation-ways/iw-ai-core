### Item Analysis: CR-00059

Bottom line: keep the spike-then-setup pattern for Phase-2, but fix the pytest coverage preemption path first, because it blocked actual mutant execution and reduced the spike to infrastructure timing instead of mutation-signal collection.

Steps analyzed: 11 (S01-S11)   Steps with retries: 3 (S01, S04, S05)   Total fix-cycles: 1 (S05)   DB signal: no (file/log analysis only)

#### Phase-2 specific assessment

1) **Spike timeout calibration (S01, 3600s budget)**
- Observed wall clock was `0:17:17` (`ai-dev/active/CR-00059/evidences/pre/cr-00059-spike-measurements.txt:13`), which is well below the 3600s budget in the design (`ai-dev/active/CR-00059/CR-00059_CR_Design.md:138`).
- Assessment: **used with large margin**. For P2-CR-B spike-like work, a shorter budget (for example 1800s) is likely safe while preserving slack for testcontainer variance.

2) **mutmut infrastructure blockers encountered vs predicted**
- Predicted blockers in design included testcontainer cost, FTS replay, and live-DB guard interactions (`ai-dev/active/CR-00059/CR-00059_CR_Design.md:104`).
- Actual blocker was different and dominant: coverage fail-under preempted mutant execution (`ai-dev/logs/CR-00059_S03_run1.log:99`, `ai-dev/logs/CR-00059_S03_run1.log:503`, `ai-dev/active/CR-00059/evidences/pre/cr-00059-spike-measurements.txt:53`).
- live-DB guard and FTS issues were explicitly *not* observed (`ai-dev/active/CR-00059/evidences/pre/cr-00059-spike-measurements.txt:54`).

3) **Spike runtime distribution**
- The run produced `0` generated mutants and still consumed ~17m (`ai-dev/active/CR-00059/evidences/pre/cr-00059-spike-measurements.txt:7`, `ai-dev/active/CR-00059/evidences/pre/cr-00059-spike-measurements.txt:13`).
- Evidence indicates time was dominated by repeated pytest startup/collection and coverage checks, not mutant execution (`ai-dev/active/CR-00059/evidences/pre/cr-00059-spike-measurements.txt:60`).
- Assessment: dominant cost is **runner/gate overhead**, not mutmut mutation execution.

4) **Surviving-mutant queue actionability**
- Queue is currently non-actionable: top-5 section is placeholder `n/a` rows (`ai-dev/active/CR-00059/evidences/pre/cr-00059-spike-measurements.txt:46`).
- S01 report also marks none captured due to blocker (`ai-dev/active/CR-00059/reports/CR-00059_S01_Backend_report.md:77`).
- Assessment: no module concentration or systemic mutant-pattern inference is possible yet; this must be first output of follow-up re-run.

5) **Audit-table-as-deliverable pattern quality**
- Pattern worked: S02/S03 quickly surfaced drift and formula issues in the measurement table (`ai-dev/active/CR-00059/reports/CR-00059_S02_CodeReview_report.md:25`, `ai-dev/active/CR-00059/reports/CR-00059_S02_CodeReview_report.md:30`, `ai-dev/active/CR-00059/reports/CR-00059_S03_CodeReviewFinal_report.md:28`).
- The cross-doc triangle itself stayed consistent (S03 marked consistency pass) even though values were blocked (`ai-dev/active/CR-00059/reports/CR-00059_S03_CodeReviewFinal_report.md:36`).
- Recommendation: formalize this pattern in Phase-2 template for any measurement-bearing CR.

6) **Shape recommendation for next Phase-2 CRs**
- **P2-CR-B (Hypothesis property tests)**: keep **spike-then-setup** shape; use a constrained first-run benchmark on the work-item state machine before broad rollout, because subprocess pytest gating issues already surfaced in this CR (`ai-dev/active/CR-00059/reports/CR-00059_S03_CodeReviewFinal_report.md:86`).
- **P2-CR-C (flaky/quarantine workflow)**: use an audit-table deliverable (classification table of intermittent failures, suspected cause, and quarantine decision) by default.

7) **deptry / new dependency check**
- S03 explicitly validated that deptry did not flag mutmut as unused (`ai-dev/active/CR-00059/reports/CR-00059_S03_CodeReviewFinal_report.md:53`).
- Assessment: no follow-up needed here.

8) **TDD RED evidence contract check (CR-00045 alignment)**
- S01 includes concrete RED evidence with real test IDs and failure lines (`ai-dev/active/CR-00059/reports/CR-00059_S01_Backend_report.md:24`, `ai-dev/active/CR-00059/reports/CR-00059_S01_Backend_report.md:25`).
- `tdd_red_evidence` is not `n/a` and no CRITICAL contract breach is detected.

#### Promoted findings

[1] Coverage fail-under preempts mutation runs and erases mutation signal
Severity: HIGH   Class: platform   Frequency: systemic
Evidence:
- `ai-dev/logs/CR-00059_S03_run1.log:99` - `RuntimeError: Tests don't run cleanly without mutations`
- `ai-dev/logs/CR-00059_S03_run1.log:503` - `FAIL Required test coverage of 50.0% not reached. Total coverage: 12.28%`
- `ai-dev/active/CR-00059/evidences/pre/cr-00059-spike-measurements.txt:53` - coverage gate exits before mutant execution
Recommendation: define and document a mutation-runner path that avoids fail-under preemption for audit runs (without weakening normal quality gates).
Target: `Makefile`, `docs/IW_AI_Core_Testing_Strategy.md`
Pros: unlocks real killed/survived data; makes mutation outputs actionable.
Cons: requires careful gate-scoping to avoid quality-policy regression.
If we don't: future mutation/property-test spikes will continue to report blocked metrics after long runtime.
Effort: M (~20-40 lines across 2 files)

[2] Measurement artifacts permit placeholder/undefined values that reduce decision quality
Severity: MED   Class: design   Frequency: systemic
Evidence:
- `ai-dev/active/CR-00059/evidences/pre/cr-00059-spike-measurements.txt:46` - top-5 queue is all `n/a`
- `ai-dev/active/CR-00059/reports/CR-00059_S02_CodeReview_report.md:30` - score displayed when denominator is zero
Recommendation: add template rules for blocked metrics (`N/A:blocked` with reason) and mandatory rerun criteria for queue-producing spikes.
Target: `ai-dev/templates/CR_Design_Template.md`, `ai-dev/work/TESTS_ENHANCEMENT.md`
Pros: prevents ambiguous data; improves comparability across Phase-2 CRs.
Cons: adds stricter reporting expectations.
If we don't: downstream CR planning will rely on inconsistent or non-actionable measurements.
Effort: S (~10-20 lines, 2 files)

[3] Review/retry overhead indicates avoidable workflow churn before QV chain
Severity: MED   Class: prompt   Frequency: recurring
Evidence:
- `ai-dev/logs/CR-00059_S01_run1.log` + `CR-00059_S01_run2.log` + `CR-00059_S01_run3.log` (3 implementation runs)
- `ai-dev/active/CR-00059/reports/CR-00059_S02_CodeReview_report.md:5` and `ai-dev/active/CR-00059/reports/CR-00059_S03_CodeReviewFinal_report.md:5` (both NEEDS_FIX)
Recommendation: in backend/code-review prompts for measurement CRs, explicitly require blocked-score semantics and top-5 queue criteria before marking step done.
Target: `ai-dev/active/CR-00059/prompts/CR-00059_S01_Backend_prompt.md`, `ai-dev/active/CR-00059/prompts/CR-00059_S02_CodeReview_prompt.md`
Pros: fewer re-runs and less review thrash.
Cons: prompts become slightly longer.
If we don't: similar first-CR-of-phase items likely repeat 2-3 run correction cycles.
Effort: S (~15 lines, 2 files)

Coverage notes: read S01/S02/S03 and key QV reports in full; sampled QV-heavy logs via targeted grep for errors/failures and coverage-preemption signatures; all CR-00059 logs are <1 MB so no large-log tail sampling was required.
