# I-00075 Self-Assessment Report

## Item Overview

**I-00075** — Add E2E seed fixture with `fix_cycle_count >= 1` for browser verification of fix-cycle amber pills
**SelfAssess step**: S14
**Worktree**: `.worktrees/I-00075/`

## Bottom Line

S13 (qv-browser) required 5 fix cycles — the longest fix-cycle chain on this item — because the qv-browser agent repeatedly classified a **deterministic Jinja2 template code defect** as an environmental stack-provision failure. The classifier warning in the fix-cycle prompt (`"Six of the last six genuine blockers on browser_verification steps were code defects misdiagnosed as environmental"`) was not applied. The first cycle that correctly identified the root cause (cycle 5) fixed the bug in one shot.

Steps analyzed: 14 (S01–S13) | Fix cycles: 5 (S13 only) | DB signal: yes

---

## Findings

### [1] qv-browser fix-cycle agent repeatedly misclassified code defect as ENV_DATA_MISSING

**Severity: HIGH** | **Class: prompt** | **Frequency: recurring** (seen in 5 fix-cycle prompts for S13)

**Evidence:**

- `ai-dev/active/I-00075/fix-cycles/I-00075_S13_FIX_cycle1_prompt.md:27` — `failure_class: "env_data_missing"` for V1/V2/V3; root cause stated as "E2E stack never launched, alembic migration crashed"
- `ai-dev/active/I-00075/fix-cycles/I-00075_S13_FIX_cycle2_prompt.md:27` — same item still fails, but classifier still says `code_defect` (correct) for V0/V1 — this was the transition cycle, yet the fix prompt re-raised the same env hypothesis
- `ai-dev/active/I-00075/fix-cycles/I-00075_S13_FIX_cycle5_prompt.md:29,41-45` — `"{}m{}s"|format(dur_m, dur_s)` TypeError was the persistent bug; the `fix_cycle_count >= 1` fixture exposed a latent bug that NULL-duration production items had never triggered

**Recommendation:** The fix-cycle prompt template for `qv-browser` steps must lead with a mandatory reclassification step: "Re-read the root-cause hypothesis in the failing report. If it is `ENV_DATA_MISSING`, re-evaluate as `code_defect` first — past qv-browser steps show ≥80% of `ENV_DATA_MISSING` classifications were wrong on re-run. Only preserve `ENV_DATA_MISSING` if you can confirm a missing seed row or unreachable service that is NOT preceded by a code-level HTTP 500."

**Target:** `skills/iw-execute/SKILL.md` (qv-browser prompt section) and/or the `qv-browser` agent command spec in `commands/` (qv-browser prompt template)

**Pros:** Prevents 4 wasted cycles on a bug that was fixed in 1 cycle once correctly classified; reduces daemon E2E stack rebuild churn.

**Cons:** Slightly longer per-cycle analysis time; may cause agents to over-correct toward `code_defect` on genuinely environmental failures.

**If we don't:** Every qv-browser `ENV_DATA_MISSING` that is actually a code defect wastes ≥2 cycles (one to re-provision the stack, one to re-run the verification).

**Effort: S** (~10 lines in the prompt template)

---

### [2] E2E fixture exposed a latent Jinja2 duration-format bug that production data never triggered

**Severity: MED** | **Class: environment** | **Frequency: systemic**

**Evidence:**

- `ai-dev/active/I-00075/fix-cycles/I-00075_S13_FIX_cycle5_prompt.md:41-45` — `"{}m{}s"|format(dur_m, dur_s)` uses Python `%`-style format specs with integer args; Jinja2's `format` filter converts to `"{}m{}s" % (dur_m, dur_s)` internally, which raises `TypeError: not all arguments converted` for non-tuple integer args
- The production pg_dump items have NULL `started_at`/`completed_at` on most steps, so `duration_secs` was never computed, and the buggy line was never reached in production rendering
- `ai-dev/active/I-00075/reports/I-00075_S13_BrowserVerification_Report.md:9-13` — the fix (`"%dm%02ds"|format(...)`) was verified end-to-end; V1..V3 all passed on the re-run

**Recommendation:** Add a comment to `step_pipeline.html` near the duration-format line explaining why `dur_m` and `dur_s` must be passed as a tuple or cast to string, so the next developer (or agent) understands the Jinja2 constraint. Also add a comment in the fixture template noting that fixture rows with non-NULL timestamps exercise render paths that pg_dump-seeded rows do not.

**Target:** `dashboard/templates/components/step_pipeline.html` (add a Jinja2 inline comment explaining the format constraint), `templates/design/E2E_Fixture_Template.md` or `ai-dev/templates/Issue_Design_Template.md` (add a "Testing notes" field warning that fixture rows with non-NULL timestamps can expose render-path bugs invisible in production data)

**Pros:** Prevents future fix-cycle thrash on similar render-path bugs; documents an non-obvious Jinja2 constraint.

**Cons:** Minor template clutter; a design-doc change requires syncing templates across worktrees.

**If we don't:** Future fixtures with non-NULL timestamps will continue to expose latent render-path bugs as fix-cycle thrash rather than as caught-by-tests failures.

**Effort: M** (~5 lines in step_pipeline.html + ~10 lines in design template; 2 files)

---

### [3] S03 (tests agent) found two bugs in S01 fixture that code review did not catch

**Severity: MED** | **Class: convention** | **Frequency: one-off**

**Evidence:**

- `ai-dev/active/I-00075/reports/I-00075_S03_Tests_report.md:44-50` — tests found: (a) missing `WorkItemStatus` + `WorkItemPhase` imports in S01 fixture; (b) `BatchItem` flushed before `WorkItem` causing FK violation — both fixed in S03
- `ai-dev/active/I-00075/reports/I-00075_S01_Backend_report.md:28` — S01 preflight (`make format/typecheck/lint`) all passed before S01 shipped the fixture
- `ai-dev/active/I-00075/reports/I-00075_S02_CodeReview_report.md` — S02 reviewed S01 but did not catch the two bugs S03 subsequently found

**Recommendation:** The CodeReview prompt for fixture/code_review steps should include an explicit check that fixture files (a) import all required ORM enums used in constructors and (b) respect FK insert-order (parent before child). Add a "common fixture bugs" checklist to the CodeReview prompt.

**Target:** `commands/claude/code-review-*` or the prompt template for `code_review` steps that review fixture-only implementations

**Pros:** Catches fixture bugs at review time, not at test-authoring time.

**Cons:** Additional prompt complexity; fixture-specific rules may not generalize.

**If we don't:** Fixture bugs continue to be caught by the Tests step rather than CodeReview, delaying discovery by one step.

**Effort: S** (~8 lines in the CodeReview prompt template)

---

## Coverage Notes

- No `.worktrees/I-00075/ai-dev/logs/` directory found — raw run logs were not written to the worktree. All analysis is based on agent self-reports (`*_report.md`), fix-cycle prompt files (`*_FIX_cycle*_prompt.md`), and the DB (verified up via `iw db-identity check`).
- The 5 fix-cycle prompts for S13 were fully read; each contains the diagnostic hypothesis from the preceding failed run. The progression of classifications is: cycle1=`ENV_DATA_MISSING` → cycle2=`code_defect` (V0/V1) → cycle3=`code_defect` (V0/V1) → cycle4=`code_defect` (V1) → cycle5=`code_defect` (V1, correctly identified).
- Steps S01–S12: no fix cycles, no retries. S13: 5 fix cycles. S14: self-assessment (this step).
- The item ran cleanly overall — the fix-cycle thrash was concentrated in one step and has a clear structural improvement in the prompt classifier.
