### Item Analysis: CR-00042

Bottom line: The item completed successfully with all QV gates passing, but the Backend/S01 agent needed 3 internal test retries to converge on the correct implementation — evidence of insufficient early signal in the prompt about Jinja2 Markup safety and template rendering requirements.

Steps analyzed: 16   Steps with retries: 3   Total fix-cycles: 0   DB signal: yes

---

[1] S01 Backend agent required 3 internal test retries to converge on correct implementation
    Severity: MED   Class: agent   Frequency: one-off
    Evidence:
      - CR-00042_S01_run1.log:78 — "AssertionError: expected 200, got 404" (first run, route not registered yet)
      - CR-00042_S01_run1.log:416 — "AssertionError: response should contain rendered HTML headings" (second run, Markup double-escaped)
      - CR-00042_S01_run1.log:698 — same AssertionError (third run, still investigating)
      - CR-00042_S01_run1.log:456 — "The `Markup` is being double-escaped by Jinja2's `|tojson` filter. I need to use `|safe`" (root cause found, fix applied)
    Recommendation: Add a note to the Backend implementation prompt template clarifying that when passing pre-rendered HTML content to Jinja2 templates, use the `|safe` filter to prevent double-escaping. This is a common pitfall when using `markupsafe.Markup` with Jinja2's `|tojson`.
    Target: templates/design/CR_Template.md or ai-dev/templates/CR_Template.md
    Pros: Faster convergence on correct implementation; fewer test cycles.
    Cons: Slight prompt inflation.
    If we don't: Agents may continue to spend 2-3 extra test cycles debugging Markup/escaping issues for docs-rendering features.
    Effort: S (~3 lines in prompt)

[2] CodeReview agents (S02, S07) failed to read step reports due to incorrect filename pattern
    Severity: MED   Class: platform   Frequency: systemic
    Evidence:
      - CR-00042_S02_run1.log:8 — "File not found: .../reports/CR-00042_S01_backend-impl_report.md"
      - CR-00042_S07_run1.log:15 — "File not found: .../reports/CR-00042_S02_code_review_report.md"
      - CR-00042_S07_run1.log:17 — "File not found: .../reports/CR-00042_S04_code_review_report.md"
      - Actual filenames: CR-00042_S01_Backend_report.md, CR-00042_S02_CodeReview_report.md, etc. (capital B in "Backend"; capital C in "CodeReview")
    Recommendation: The agent prompts use a lowercase pattern (`backend-impl`, `code_review`) while the actual step report filenames use capitalized agent labels. Fix the prompt filename generator or standardize the convention. Also consider having `iw step-done` verify the report filename matches what the next step expects.
    Target: orch/cli/step_commands.py or the prompt template generator
    Pros: Eliminates noisy "read failed" errors in CodeReview steps; agents can read prior reports correctly.
    Cons: Requires coordinated change in prompt generation + filename convention.
    If we don't: Every CR with CodeReview steps will have noisy read failures; agents waste time on fallback searches.
    Effort: M (~2 files)

[3] S03 Frontend agent hit a path typo in an error message (docs.html)
    Severity: LOW   Class: agent   Frequency: one-off
    Evidence:
      - CR-00042_S03_run1.log:24 — "File not found: /home/sgeriog/dev/iw-doc-plan/..." (note "sgeriog" vs "sergiog")
    Recommendation: No platform change needed — single typo, agent self-corrected.
    If we don't: No recurring cost.
    Effort: N/A
