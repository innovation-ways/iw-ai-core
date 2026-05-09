### Item Analysis: CR-00038

Bottom line: Test-writing agents should prefix unused test-fixture variables with `_` to avoid F841 lint errors before gates run, saving one fix cycle per affected item.

Steps analyzed: 12   Steps with retries: 0   Total fix-cycles: 2   DB signal: yes

[1] Lint gate S06 failed due to mechanical F841 errors in test file
    Severity: MED   Class: agent   Frequency: one-off
    Evidence:
      - ai-dev/active/CR-00038/fix-cycles/CR-00038_S06_FIX_cycle1_prompt.md:16 — "lint failed: exit=2"
      - ai-dev/active/CR-00038/reports/CR-00038_S05_CodeReview_Final_Report.md:108 — "13 unused variables (F841) in tests/dashboard/test_docs_running_jobs.py"
    Recommendation: Test-writing agents should prefix test-fixture variables that are created only to satisfy DB FK constraints and not read after creation with `_` (e.g., `_doc = _make_project_doc(...)`). This suppresses F841 and avoids a lint fix cycle.
    Target: skills/iw-execute/SKILL.md or templates/design/Feature_Design_Template.md (test-writing guidance section)
    Pros: Eliminates a lint fix cycle on every item that writes tests with fixture-only variables.
    Cons: Minor naming convention change; agents must learn the pattern.
    If we don't: Every test that creates a DB object purely for FK satisfaction triggers F841, causing a lint fix cycle before merge.
    Effort: S (~1 line in guidance, propagated to agent behavior through prompt updates)

[2] Format gate S07 also failed alongside lint
    Severity: MED   Class: agent   Frequency: one-off
    Evidence:
      - ai-dev/active/CR-00038/fix-cycles/CR-00038_S07_FIX_cycle1_prompt.md:16 — "format failed: exit=2"
    Recommendation: Same as [1] — test-writing agents should also run `uv run ruff format` before marking step-done to catch format-check failures before QV gates run.
    Target: skills/iw-execute/SKILL.md or templates/design/Feature_Design_Template.md (test-writing guidance section)
    Pros: Prevents a second fix cycle that usually accompanies lint failures.
    Cons: Slightly longer step run time.
    If we don't: Format failures accompany lint failures as a paired fix cycle on most items that fail lint.
    Effort: S (~1 line addition to test-writing guidance)

[3] S05 code review correctly identified the issues but they were not pre-empted
    Severity: LOW   Class: prompt   Frequency: systemic
    Evidence:
      - ai-dev/active/CR-00038/reports/CR-00038_S05_CodeReview_Final_Report.md:102-122 — "make lint — 15 errors", "make format-check — 2 files"
      - ai-dev/active/CR-00038/reports/CR-00038_S05_CodeReview_Final_Report.md:129-132 — "Run uv run ruff check --fix ... Run uv run ruff format"
    Recommendation: Add "run lint and format-check before step-done" to the test-step agent instructions so the agent catches mechanical issues before the code review step surfaces them.
    Target: templates/design/Feature_Design_Template.md (test implementation section)
    Pros: Closes the gap between code review (which catches everything) and the agent's own pre-step-done verification.
    Cons: Slightly longer agent runtime in test steps.
    If we don't: Code review catches issues that the agent could have caught — the handoff between test-agent and code-review-agent carries avoidable back-and-forth.
    Effort: S (~1 line addition)

[4] Browser verification S11 required manual DB seeding via docker exec
    Severity: MED   Class: environment   Frequency: recurring
    Evidence:
      - ai-dev/active/CR-00038/reports/CR-00038_S11_BrowserVerification_Report.md:61 — "A fixture file was also created at ai-dev/active/CR-00038/e2e_fixtures/001_running_job.py"
      - ai-dev/active/CR-00038/reports/CR-00038_S11_BrowserVerification_Report.md:61 — "inserted one directly via docker exec"
    Recommendation: Provide a seed-data mechanism (SQL fixture file or SQLAlchemy fixture) for browser-verification steps that depend on live DB rows (e.g., running `DocGenerationJob`). The current approach requires the agent to run raw SQL against the E2E DB container.
    Target: skills/iw-execute/SKILL.md (browser verification section)
    Pros: Removes the need for agents to use docker exec for seeding; fixture is reproducible.
    Cons: Requires the E2E test infrastructure to support SQL seed fixtures; adds complexity.
    If we don't: Browser verification agents continue needing docker exec for DB seeding on steps that depend on live job state.
    Effort: M (~2 files, e2e fixture infrastructure)