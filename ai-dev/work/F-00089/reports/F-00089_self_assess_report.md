### Item Analysis: F-00089

Bottom line: tighten workflow prompts/skills for targeted pytest runs to default to `PYTEST_ADDOPTS=--no-cov` during step-level RED/GREEN, because coverage fail-under noise caused repeated avoidable retries.

Steps analyzed: 19   Steps with retries: 8   Total fix-cycles: 8   DB signal: yes

[1] Step-level pytest command contract conflicts with repository coverage gate
    Severity: MED   Class: prompt   Frequency: recurring
    Evidence:
      - ai-dev/logs/F-00089_S01_run1.log:23 — "Required verification command `uv run pytest tests/integration/daemon_chaos/ -v` fails at repository-wide coverage fail-under=50% for narrow subset runs, even when assertions pass."
      - ai-dev/logs/F-00089_S03_run2.log:21 — "required command runs all 5 tests green, but exits non-zero... coverage fail-under=50"
      - ai-dev/logs/F-00089_S04_run2.log:19 — "required verification command ... fails after tests pass because repository-wide coverage fail_under=50"
    Recommendation: update backend implementation prompt template + testing skill to explicitly allow `PYTEST_ADDOPTS=--no-cov` for per-file behavioural RED/GREEN evidence in workflow steps.
    Target: ai-dev/templates/Feature_Implementation_Template.md; skills/iw-ai-core-testing/SKILL.md
    Pros: Fewer false step failures; less retry churn in S01..S06-style work.
    Cons: Slightly longer prompt guidance.
    If we don't: agents will keep failing valid single-file runs and burning retries on coverage-policy noise.
    Effort: S   (~15-25 lines, 2 files)

[2] CodeReview step scope/routing produced repeated fail/fix churn
    Severity: HIGH   Class: platform   Frequency: recurring
    Evidence:
      - ai-dev/logs/F-00089_S09_run5.log:4 — "step-fail ... reason \"scope diff vs main not empty ...\""
      - ai-dev/logs/F-00089_S09_fix2.log:39 — "Please amend allowed paths ... if you want this critical finding resolved in this fix cycle."
      - ai-dev/logs/F-00089_S10_run9.log:8 — "step-fail ... reason \"... production-scope diff not empty\""
    Recommendation: harden review workflow routing so review agents ignore/pre-filter pre-existing out-of-scope branch diffs, and only fail on diffs attributable to this item's allowed paths.
    Target: skills/iw-workflow/SKILL.md; orch/daemon/fix_cycle.py
    Pros: Reduces multi-cycle review thrash; clearer actionable review output.
    Cons: Requires careful scoping logic adjustment.
    If we don't: review/fix loops will continue to consume many runs without moving in-scope work forward.
    Effort: M   (~40-120 lines, 2 files)

Checks requested by step prompt:
- S01 gating pattern: expensive (blocked+rerun) while S02..S06 were mostly cheap; one clarification stop in S03 but no broad API-drift cascade.
- S05 F-00084 dual-path: exercised F-00084-present branch (auto-merge hook path).
- xfail incident pins S02..S06: none filed as Incident IDs; one strict xfail present in S05.
- Skill-sync mirror discipline: S07 and S08 both report `iw sync-skills --force` + mirror parity checks.
- 9-vs-8 split: `daemon-chaos-smoke` present in canonical `skills/iw-workflow/SKILL.md`, not added as a qv-gate in `ai-dev/active/F-00089/workflow-manifest.json`.
- TDD RED evidence quality S01..S06: plausible assertion/attribute failures; not vacuous import/collection noise.
