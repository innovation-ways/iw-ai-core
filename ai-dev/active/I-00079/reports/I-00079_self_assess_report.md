### Item Analysis: I-00079

Bottom line: The fix was clean and well-scoped — the item's primary finding worth acting on is that the pre-existing regression test suite asserted empty-state marker *presence* but never validated that the CTA `href` actually resolves, letting this class of bug ship undetected.

Steps analyzed: S01, S02, S03, S04, S05, S06, S07, S08, S09, S10, S11   Total retries: 0   Total fix-cycles: 1 (S10 integration-test gate — unrelated pre-existing e2e_seed failure)   DB signal: yes

---

[1] Regression suite tested shape, not semantics — the gap that let this bug ship
    Severity: MED   Class: prompt   Frequency: one-off
    Evidence:
      - ai-dev/active/I-00079/I-00079_Issue_Design.md:78 — "The existing regression test `tests/dashboard/test_empty_states.py` asserts the empty-state *markup markers* (`data-empty-state`, `<h3>`, `<p>`, `class="empty-state__cta-primary"`) are present but never follows or validates `primary_href`, so a broken target passes the suite (a classic 'shape, not semantics' gap — the I003 lesson)"
      - ai-dev/active/I-00079/reports/I-00079_S03_tests-impl_report.md:20 — "All tests use the existing `_primary_hrefs()` helper… and follow the href to verify HTTP 200 — not merely 'shape' checks"
      - tests/dashboard/test_empty_states.py (pre-S03) — contained only marker assertions; no `client.get()` on `primary_href` values
    Recommendation: Update the `tests/dashboard/test_empty_states.py` design-pattern documentation (or any I003Lesson reference in the codebase) to explicitly call out that empty-state CTA hrefs require resolve-to-200 checks, not just marker checks. Add a note to the test file's module docstring that CTA href semantic correctness is mandatory, with a link to the I003 lesson if it exists as a documented anti-pattern.
    Target: tests/dashboard/test_empty_states.py (module docstring / pattern note), and/or the I003 lesson reference in project docs
    Pros: Future empty-state tests won't silently omit the semantic check; the I003 lesson becomes actionable guidance rather than an abstract principle.
    Cons: Requires someone to write the I003 lesson down if it doesn't already exist as a shareable artifact.
    If we don't: The next empty-state CTA that uses a wrong URL form will pass the test suite until someone notices by hand in the browser.
    Effort: S (~5 lines in module docstring)

[2] Empty-state CTA hrefs were out-of-scope for CR-00042 — same bug class, two surfaces, one fixed
    Severity: MED   Class: design   Frequency: one-off
    Evidence:
      - ai-dev/active/I-00079/I-00079_Issue_Design.md:78 — "CR-00042 ('Fix Broken 'Open full docs' Links in Help Popups') corrected the same class of broken link, but only in `dashboard/routers/help.py`'s `_SLUG_TO_DOC` map — it never touched the `empty_state` macro `primary_href` values in the page templates"
      - ai-dev/active/I-00079/I-00079_Issue_Design.md:39-47 — the 7 affected `primary_href` values listed explicitly
    Recommendation: When a CR or Feature fixes links in one surface (`help.py` `_SLUG_TO_DOC`), the design doc template or review checklist should include a mandatory "check all link surfaces" step that sweeps the other known surfaces (empty-state CTAs, breadcrumb links, sidebar links, any other `href` injection points). A one-line checklist item in the `/iw-review-design` skill's review criteria would be enough.
    Target: skills/iw-review-design/SKILL.md (or the design doc template in templates/design/)
    Pros: Prevents half-fixes where the same bug class is corrected in one place but remains in another.
    Cons: Slightly broader scope review, but the review is faster than the fix cycle.
    If we don't: CR-00042-style half-fixes continue; the next CR that fixes help-popover links might again leave empty-state CTAs alone.
    Effort: S (~3 lines in review criteria)

[3] S11 e2e fixture should be a standing seed fixture — empty-project is a recurring verification need
    Severity: LOW   Class: environment   Frequency: systemic
    Evidence:
      - ai-dev/active/I-00079/e2e_fixtures/001_empty_project.py:1-37 — the fixture `001_empty_project.py` was created specifically so S11 could verify empty-state CTAs; it creates `Project(id="empty-test-project")` with no child rows
      - ai-dev/active/I-00079/reports/I-00079_S11_BrowserVerification_Report.md:24 — "The `empty-test-project` project (created by the fixture) has no work items, batches, or docs, causing all empty-state panels to render"
      - The S10 fix-cycle prompt (ai-dev/active/I-00079/fix-cycles/I-00079_S10_FIX_cycle1_prompt.md) shows the e2e_seed was already running other items' fixtures before S11 needed this one
    Recommendation: Add `001_empty_project.py` (or its logic) as a standing fixture in `scripts/e2e_seed.py` so every E2E stack starts with a guaranteed-empty project. This eliminates the per-item fixture creation step for any future browser-verification work item that needs to check empty-state CTAs.
    Target: scripts/e2e_seed.py
    Pros: Future S11 (and any qv-browser step checking empty states) skips the fixture-creation step; the empty project is available immediately after seed.
    Cons: One more Project row in every E2E stack; negligible cost.
    If we don't: Every future empty-state browser verification repeats the fixture-creation step, burning time that could be spent on the actual verification.
    Effort: S (~20 lines in e2e_seed.py)
