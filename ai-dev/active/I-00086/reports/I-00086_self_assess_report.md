### Item Analysis: I-00086

Bottom line: standardize review-step prompt test commands to use `--no-cov` (or equivalent coverage-safe guidance) for targeted pytest runs to stop repeated false-fail retries.

Steps analyzed: 15   Steps with retries: 11   Total fix-cycles: 13   DB signal: yes

[1] Coverage-gated targeted pytest commands repeatedly triggered false failures in review steps
    Severity: HIGH   Class: prompt   Frequency: recurring
    Evidence:
      - `ai-dev/active/I-00086/prompts/I-00086_S04_CodeReview_Frontend_prompt.md:97` — "uv run pytest tests/dashboard/ -v"
      - `ai-dev/logs/I-00086_S04_run15.log:606` — "ERROR: Coverage failure: total of 29 is less than fail-under=50"
      - `ai-dev/active/I-00086/prompts/I-00086_S06_CodeReview_Tests_prompt.md:110` — "uv run pytest tests/dashboard/test_runtime_override_response.py -v"
      - `ai-dev/logs/I-00086_S06_run15.log:41` — "ERROR: Coverage failure: total of 18 is less than fail-under=50"
      - `ai-dev/logs/I-00086_S07_run7.log:55` — "ERROR: Coverage failure: total of 18 is less than fail-under=50" (also seen in prior S07 retries)
    Recommendation: update code-review prompt templates to require `--no-cov` for targeted verification commands, matching the final-review pattern already present in S07.
    Target: `templates/design/CodeReview_Prompt_Template.md`
    Pros: cuts avoidable reruns/fix-cycles; preserves signal from targeted tests; reduces wasted agent time.
    Cons: targeted review checks no longer enforce global coverage in that step.
    If we don't: code-review steps will keep thrashing on non-behavioral coverage gates and inflate execution time.
    Effort: S (~10-20 lines, 1-2 files)

TDD RED evidence check:
- S01 report contains plausible pre-change RED evidence of the `204` contract (`ai-dev/active/I-00086/reports/I-00086_S01_Api_report.md:31-33`) and is acceptable.
- S03 template-only RED narrative is present and acceptable.
- S05 coverage-step exemption is present and acceptable.
