### Item Analysis: I-00071

Bottom line: S01's implementation prompt should explicitly require `_strip_test_globs` filtering before the sibling-directory check, not just in `is_test_path` — the bug was self-corrected in the S05 fix cycle but the miss indicates a prompt gap.

Steps analyzed: 13   Steps with retries: 0   Fix-cycles: 1   DB signal: yes

---

[1] S01 sibling-check logic bug caught by S03 regression tests and fixed in S05 fix cycle
    Severity: LOW   Class: prompt   Frequency: systemic
    Evidence:
      - ai-dev/active/I-00071/reports/I-00071_S03_Tests_report.md:75-76 — "S01 production code has a logic bug in find_blocking_items... sibling check applies _same_parent to raw (unfiltered) paths, bypassing _strip_test_globs"
      - ai-dev/active/I-00071/reports/I-00071_S04_CodeReview_report.md:169-175 — "Sibling-directory check in find_blocking_items applies _same_parent to raw (unfiltered) paths... This is a production bug in S01, NOT a test bug in S03."
      - ai-dev/active/I-00071/fix-cycles/I-00071_S05_FIX_cycle1_prompt.md:16 — Diagnostic hypothesis explicitly identifies the raw-paths bug and its fix
      - ai-dev/active/I-00071/reports/I-00071_S05_CodeReview_Final_report.md:62-64 — All 3 BATCH-00078 tests PASS after S05 fix cycle
    Recommendation: Add a guidance bullet in the implementation prompt template (and design-doc generator) for bug-fix items: "When a function filters a list with `_strip_test_globs` or equivalent, ensure ALL downstream consumers of that list (including sibling-directory checks) use the filtered version, not the raw list."
    Target: templates/design/Issue_Design_Template.md (or the prompt generator that creates S01 prompts)
    Pros: Prevents a specific, reproducible class of bug where filtering is applied in one place but missed in another.
    Cons: Slightly longer prompts; more guidance may feel repetitive for simple fixes.
    If we don't: Future bug-fix items with test-path filtering will repeat this miss; S03 tests catch it, S05 fixes it, but it wastes a full review cycle.
    Effort: S (~5 lines in prompt template)
    paste_prompt: /iw-new-incident Add sibling-check path-filtering guidance to the Issue_Design_Template.md; analyzed in I-00071 self-assess (ai-dev/active/I-00071/reports/I-00071_self_assess_report.md). Target: templates/design/Issue_Design_Template.md. Effort: S.