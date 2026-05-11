### Item Analysis: CR-00046

Bottom line: The `integration-tests` QV gate is a silent no-op for every work item — `make allure-integration` has no recipe in the Makefile, so it exits 0 in <1s without running anything. Fix by either adding the recipe to `Makefile` or pointing the gate command in the canonical skill templates to `make test-integration`.

Steps analyzed: 10 (S01–S10)   Steps with retries: 0   Total fix-cycles: 0   DB signal: yes

CR-00046 ran exceptionally clean apart from one finding that the analyst from CR-00045 already saw and mis-classified as "no integration tests in scope" — it is in fact a systemic gate misconfiguration.

[1] `integration-tests` QV gate is a silent no-op — `make allure-integration` has no recipe
    Severity: HIGH   Class: platform   Frequency: systemic
    Evidence:
      - `ai-dev/logs/CR-00046_S09_run1.log:1` — "make: Nothing to be done for 'allure-integration'."
      - `ai-dev/active/CR-00046/reports/CR-00046_S09_QvGate_report.md:9` — "Exit code | 0 … Duration (s) | 0"
      - `ai-dev/active/CR-00045/reports/CR-00045_S08_QvGate_report.md:16` — same "Nothing to be done" output on the prior item (also see [[CR-00045_self_assess_report]] which interpreted this as expected behavior, confirming the issue is invisible to the self-assess pipeline as well)
      - `Makefile:10` — `allure-integration` appears only in the `.PHONY` list; no `allure-integration:` recipe exists (`grep -nE '^allure-' Makefile` returns nothing)
      - `skills/iw-workflow/SKILL.md:131`, `skills/iw-new-feature/SKILL.md:307`, `skills/iw-new-incident/SKILL.md:454` — all three canonical design templates hardcode `"command": "make allure-integration"` for the `integration-tests` gate
    Recommendation: Add an `allure-integration:` recipe to `Makefile` (analogous to the existing `test-integration:` recipe at `Makefile:76`, with `--alluredir=tests/output/allure/integration` since the `.PHONY` block references allure report dirs). Alternative quick fix: change the three skill templates to use `make test-integration` and re-run `iw sync-skills`. The Makefile-side fix is preferred because it preserves the allure-report integration the CR-00026 work intended.
    Target: `Makefile` (preferred) OR `skills/iw-workflow/SKILL.md` + `skills/iw-new-feature/SKILL.md` + `skills/iw-new-incident/SKILL.md` + `iw sync-skills` (fallback)
    Pros: Restores the integration-test safety net that the workflow believes it has; closes a gate that currently passes regardless of code correctness; aligns S09 behavior with what the agent's CodeReviewFinal report (S03) actually validated (it ran `make test-integration` directly and got 2256 passed, proving the suite works — only the gate plumbing is broken).
    Cons: If `allure-integration` is intentionally absent because `tests/integration/` is too slow for the gate budget (900s timeout exists, suggesting it was planned to run), this fix will start consuming that budget — verify by running locally first. Adding the recipe will surface any flaky integration tests that have been hiding behind the silent pass.
    If we don't: Every Feature / Incident / CR continues to claim `integration-tests` PASS in 0 seconds without running anything. A regression that breaks the integration suite ships unnoticed unless caught by the manual `make test-integration` that code-review agents happen to run inside the implementation step (S03 here, by coincidence).
    Effort: S (~3 lines, 1 file) for the Makefile fix; S (~3 line edits + sync command) for the templates fix.

(No other findings cleared the bar — see coverage_notes in the JSON. The rest of the run is the cleanest item I've seen analyzed: zero retries, zero fix cycles, zero install/setup commands inside steps, zero error traces in any log, RED-first TDD evidence cleanly captured by S01, S02 caught a real false-negative in the scanner and correctly tracked it as out-of-scope follow-up, S03 verified skill canon byte-match and end-to-end consistency.)
