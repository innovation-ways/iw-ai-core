### Item Analysis: I-00065

Bottom line: The workflow for this trivial frontend-only fix (2 files, 4 new lines total) was largely clean, but every code-review step had to waste cycles distinguishing real lint errors from ruff/Jinja2 false positives — a prompt can fix this.

Steps analyzed: 5   Steps with retries: 1 (S03, self-corrected)   Total fix-cycles: 0   DB signal: yes

[1] Ruff false-positives on Jinja2 templates pollute `make lint` output in every code-review step
    Severity: MED   Class: prompt   Frequency: systemic
    Evidence:
      - I-00065_S02_run1.log:69 — "invalid-syntax: Simple statements must be separated by newlines or semicolons → panel.html:61"
      - I-00065_S04_run1.log:50 — "invalid-syntax: Expected an expression → panel.html:61"
      - I-00065_S05_run1.log:69-200 — ~100 lines of ruff "invalid-syntax" errors on panel.html, ~2000 total lines in log
      - I-00065_S05_run1.log:74 — "Full output saved to: .../tool_df80494120012g20RNZfPgrUe4" (log truncated)
    Recommendation: In every code-review prompt template (S02, S04, S05), add an explicit instruction to scope `make lint` and `make format` to only the files that the item's scope allows, using `uv run ruff check <file1> <file2> ...` rather than `make lint`. The broad `make lint` is correct for S01/S03 but wastes code-reviewer cycles on unrelated worktrees' Jinja2 templates.
    Target: templates/design/CodeReview_prompt_template.md (or the generated per-step prompts at ai-dev/active/<ID>/prompts/I-00065_S0X_CodeReview_prompt.md)
    Pros: Code reviewers never spend cycles on false-positive Jinja2 parser output; cleaner, shorter logs.
    Cons: Requires updating prompt template(s); regenerated prompts will carry the fix.
    If we don't: Every code-review step continues spending ~30s reading and mentally filtering false-positive lint output; S05's log ballooned to 2088 lines from this alone.
    Effort: S (~2 lines added to 1 prompt template)

[2] S03 first test had a regex bug causing false failure; agent self-corrected but wasted one run
    Severity: MED   Class: agent   Frequency: one-off
    Evidence:
      - I-00065_S03_run1.log:214 — "FAILED ... test_i00065_all_expanded_header_elements_hidden_when_collapsed"
      - I-00065_S03_run1.log:238-253 — assertion error showing all 6 expected IDs "missing" from regex matches
      - I-00065_S03_run1.log:438 — "The secondary regression test has a regex issue — the selectors span multiple lines"
      - I-00065_S03_run1.log:456-483 — agent rewrites test to use `id_ not in style_block` string containment instead of multiline regex
    Recommendation: No structural fix needed — the agent self-corrected. However, the prompt for S03 tests-impl could benefit from an example of a CSS multiline selector string check, to reduce the likelihood of the agent reaching for a regex that doesn't handle multiline selectors. Alternatively, add `pytest --no-cov` to the test run command in the prompt so coverage thresholds don't cause noise in small test-file additions.
    Target: templates/design/Tests_prompt_template.md
    Pros: Faster test iteration for future test-writing steps; fewer false starts on simple test assertions.
    Cons: Minor; the self-correction worked.
    If we don't: Future test-impl steps may similarly write a multiline CSS regex that fails on the first run.
    Effort: S (~3 lines added to prompt)
