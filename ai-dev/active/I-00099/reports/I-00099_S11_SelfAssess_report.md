# Item Analysis: I-00099

**Item**: Scope-overlap sibling-dir rule generates false-positive cross-batch holds
**Self-assessment step**: S11
**Analyzer**: iw-item-analyze skill

---

## Bottom Line

The item executed correctly end-to-end; the fix is sound and all gates passed. Three process-level findings merit attention: (1) S01 introduced an out-of-scope modification to `globs_intersect` that S02's fix cycle caught and reverted — the per-step review template should explicitly require agents to confirm what they did NOT change; (2) test flakiness from random seed ordering masked two real test issues across S04 and S05's initial runs; (3) a minor-subtractive workflow template would better fit a 40-line deletion that touches one file.

---

## Steps Analyzed: 11   Runs: 13   Fix Cycles: 2   Total Retries: 3   DB Signal: no (worktree logs used)

### Signal Source Notes
S09/S10 logs are large (378 KB / 366 KB); read tails and grep for failures. S01–S05 logs read in full. Coverage data is sparse due to targeted test runs. No DB telemetry was queried (soft-step semantics; DB confirmed unreachable).

---

## Findings

[1] **S01 introduced an out-of-scope modification to `globs_intersect` — caught by S02 fix cycle**
Severity: HIGH   Class: platform   Frequency: systemic

Evidence:
  - .worktrees/I-00099/ai-dev/logs/I-00099_S02_fix1.log:163 — "Design doc spec for S01: 'Remove `_same_parent` and the sibling fallback... **No change to `globs_intersect`**'"
  - .worktrees/I-00099/ai-dev/logs/I-00099_S02_fix1.log:164 — "S01 actual: Added a 'Reverse anchor containment' block to `globs_intersect` (out of scope per design doc)"
  - .worktrees/I-00099/ai-dev/logs/I-00099_S02_fix1.log:105-127 — diff showing S01 added 11 lines to `globs_intersect` (reverse anchor check) beyond the sibling-rule removal

Recommendation: Update the S01 Backend prompt template (`ai-dev/templates/Feature_Backend_prompt.md` or `ai-dev/templates/Issue_Backend_prompt.md`) to add an explicit checklist section: "Confirm you did NOT modify: [globs_intersect body, _strip_test_globs body, any function not listed above]". This makes scope boundary violations self-evident before the agent submits its report.

Target: ai-dev/templates/Feature_Backend_prompt.md, ai-dev/templates/Issue_Backend_prompt.md

Pros: Reduces fix-cycle risk on multi-agent items; agents must actively confirm boundary.

Cons: Slightly longer prompt; adds a checklist burden to every Backend step.

If we don't: Agents continue to silently add related improvements to the target function, requiring S02 fix cycles to correct. S02 already self-corrected well, but this costs time.

Effort: S (~5 lines added to prompt template)

[2] **S02 typo in working directory caused first run to fail — self-corrected in run 2**
Severity: LOW   Class: agent   Frequency: one-off

Evidence:
  - .worktrees/I-00099/ai-dev/logs/I-00099_S02_run1.log:23 — "cd /home/sgeriog/dev/... No such file or directory"
  - .worktrees/I-00099/ai-dev/logs/I-00099_S02_run2.log — run 2 used correct path, all checks passed

Recommendation: No platform change needed. The agent self-corrected in run 2. This is within normal retry behavior for a busy agent. However, consider whether the prompt should include a `pwd` sanity check at step start to catch path mismatches earlier.

Target: None (self-corrected; no action required)

[3] **Test flakiness from random seed ordering masked real failures in S04 and S05**
Severity: MED   Class: platform   Frequency: recurring

Evidence:
  - .worktrees/I-00099/ai-dev/logs/I-00099_S04_run1.log:41 — `test_glob_anchor_still_blocks_file_under_anchor FAILED` (randomly-seed=2726543514)
  - .worktrees/I-00099/ai-dev/logs/I-00099_S04_run1.log:85 — `test_blocks_multiple_in_flight FAILED`
  - .worktrees/I-00099/ai-dev/logs/I-00099_S04_run2.log:41 — same tests PASSED (randomly-seed=996209880)
  - .worktrees/I-00099/ai-dev/logs/I-00099_S05_fix1.log:28 — `test_glob_anchor_still_blocks_file_under_anchor FAILED` initially
  - .worktrees/I-00099/ai-dev/logs/I-00099_S05_fix1.log (tail) — same test PASSED after fix applied

The `test_blocks_multiple_in_flight` failure was eventually diagnosed by S05_fix1 as a real issue: the test used sibling files (`src/app/config.py` + `src/app/main.py`) that do NOT block under the corrected rule, so the test itself was incorrectly written. The fix1 applied a proper glob anchor (`src/app/**/*.py`). The `test_glob_anchor_still_blocks_file_under_anchor` failure was a pre-existing bug in the test file's assertion (`len(result) == 1` vs `len(result) == 1` with the new code's behavior).

Recommendation: Add `--randomly-seed=0` to targeted pytest invocations in test-step prompts so test order is deterministic during development. Alternatively, document that agents should re-run on failure with a different seed before concluding a test is flaky. Also consider adding a test-stability check to the CodeReview_Final prompt ("verify tests pass with a second seed before signing off").

Target: skills/iw-ai-core-testing/SKILL.md, ai-dev/templates/Feature_CodeReview_Final_prompt.md

Pros: Reduces false-positive failures that trigger unnecessary fix cycles or mask real bugs.

Cons: Deterministic order can mask cross-test dependencies; tradeoff is acceptable for unit tests.

If we don't: Agents waste time on spurious fix cycles; real test failures get dismissed as "flaky".

Effort: S (~3 lines in prompt template; `--randomly-seed=0` flag in test invocation)

[4] **S03 deleted obsolete test cleanly — pre-emptive guard in S04 was warranted**
Severity: MED   Class: prompt   Frequency: systemic

Evidence:
  - .worktrees/I-00099/ai-dev/logs/I-00099_S03_run1.log:48-49 — "Now delete `test_non_test_sibling_still_blocks`"
  - .worktrees/I-00099/ai-dev/logs/I-00099_S04_run1.log:23 — "Grep 'test_non_test_sibling_still_blocks' — 0 matches" (confirmed deleted)
  - .worktrees/I-00099/ai-dev/logs/I-00099_S04_run1.log:24 — S04 explicitly checked for deletion (as instructed) and confirmed 0 matches

Recommendation: The S04 prompt's explicit instruction to flag non-deletion as CRITICAL was correct and should be retained in the `CodeReview_Tests_prompt.md` template. This pattern — explicitly instructing the reviewer to check for a specific deletion — is valuable for any step that removes code. Formalize it: "If the step is supposed to delete X and X still exists, that is a CRITICAL finding."

Target: ai-dev/templates/Feature_CodeReview_Tests_prompt.md

Pros: Prevents "rescue" anti-patterns where an agent converts a deletion into a modification to preserve the test.

Cons: None identified.

If we don't: Agents may "helpfully" adapt rather than delete tests that pin removed behavior, silently breaking regression.

Effort: S (~2 lines in template)

[5] **Reproduction tests used exact path strings — cross-reference accuracy verified**
Severity: LOW   Class: convention   Frequency: systemic

Evidence:
  - .worktrees/I-00099/ai-dev/logs/I-00099_S03_run1.log:74-76 — `"docs/IW_AI_Core_Testing_Strategy.md"` and `"docs/IW_AI_Core_AI_Assistant_Models.md"` (exact strings from design doc)
  - .worktrees/I-00099/ai-dev/logs/I-00099_S03_run1.log:86-88 — `"orch/daemon/batch_manager.py"` and `"orch/daemon/project_registry.py"` (exact strings from design doc)
  - .worktrees/I-00099/ai-dev/active/I-00099/I-00099_Issue_Design.md:131-133 — same exact path strings

Recommendation: No change needed. The agents used exact path strings as specified. This finding confirms the design doc's cross-reference convention is being followed and the regression net is properly anchored.

Target: None (convention is working as designed)

[6] **S01 read-only cross-check of `batch_manager.py` was done but not formally recorded**
Severity: LOW   Class: prompt   Frequency: recurring

Evidence:
  - .worktrees/I-00099/ai-dev/logs/I-00099_S01_run1.log:10 — "Read orch/daemon/batch_manager.py [offset=390, limit=30]"

Recommendation: For steps that include a read-only verification task, add a field to the report template: "Verification completed: [what was checked]". This makes cross-check findings visible without requiring the agent to guess what format to use. Alternatively, add a prompt clause: "Record in your report the specific read-only finding you confirmed."

Target: ai-dev/templates/Feature_Backend_prompt.md, ai-dev/templates/Issue_Backend_prompt.md

Pros: Makes read-only verification traceable in the audit trail.

Cons: Slight increase in report length for steps that do read-only checks.

Effort: S (~2 lines in prompt template)

[7] **Subtractive-change workflow template would better fit this item's shape**
Severity: MED   Class: design   Frequency: systemic

Evidence:
  - .worktrees/I-00099/ai-dev/logs/I-00099_S01_run1.log:11-15 — S01 described changes as "1. Update module docstring 2. Delete `_same_parent()` 3. Remove sibling-case fallback" (~40 lines deleted, no new code)
  - Workflow manifest: 11 steps total (Backend → CodeReview → Tests → CodeReview → CodeReview_Final → 5 QV gates) for a pure deletion in one file
  - QV gates S06–S10 all ran cleanly in <10s each (lint, format, typecheck each ~3s; unit tests 76s; integration tests ~9s)

Recommendation: Define a `minor-subtractive` workflow template (or step variant) that collapses or shortens the review chain for small deletions: e.g., Backend + one CodeReview + targeted test + 3 QV gates (skip the CodeReview_Final if no new logic was introduced). This is lower priority than the findings above — the current workflow produced a correct result — but it represents process overhead for no marginal safety benefit.

Target: docs/IW_AI_Core_Workflow_Templates.md (or equivalent workflow definition)

Pros: Faster cycle time for low-risk subtractive changes; less agent time wasted on ceremonial review.

Cons: Requires defining what qualifies as "minor-subtractive" (line count threshold? new code ratio?) to avoid misuse.

If we don't: Every small deletion still costs the full 11-step template, creating unnecessary latency.

Effort: M (requires defining template criteria and updating workflow manifest generator)

---

## I-00099-Specific Signals

### 1. Subtractive-fix pattern
This was a ~40-line deletion in one file. The full 11-step workflow (Backend → CodeReview → Tests → CodeReview → CodeReview_Final → 5 QV gates) felt like ceremony for a pure subtraction. Finding [7] above addresses this.

### 2. Obsolete test deletion
S03 deleted `test_non_test_sibling_still_blocks` cleanly. No "rescue" attempt was made. S04's pre-emptive guard (flagging non-deletion as CRITICAL) was warranted — the design explicitly called for deletion, and S04's explicit grep confirmed it. Finding [4] above addresses this.

### 3. Cross-reference accuracy
S03 used exact path strings from the design (`docs/IW_AI_Core_Testing_Strategy.md` not `docs/A.md`; `orch/daemon/batch_manager.py` not `orch/daemon/A.py`). This is confirmed correct. Finding [5] above is a positive signal, not a finding.

### 4. Caller-contract verification
S01 read `batch_manager.py` at line 10 to confirm the event message becomes accurate (the caller site logs `conflicting_globs[:3]` — with the sibling fallback removed, `conflicting_globs` will always be a real glob from `globs_intersect`). However, this finding was not formally recorded in S01's report. Finding [6] above addresses this.

---

## Coverage Notes

S09 log (378 KB): read tail (last 500 lines) + grep for FAILED/PASSED. S10 log (366 KB): same. S01–S05 logs read in full. Fix-cycle logs (S02_fix1, S05_fix1) read in full to trace the globs_intersect modification and its fix.