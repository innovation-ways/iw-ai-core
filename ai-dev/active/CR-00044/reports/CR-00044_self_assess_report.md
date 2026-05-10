### Item Analysis: CR-00044

Bottom line: Design-doc anchors must be verified against the rendered document's actual heading IDs before being specified; the S05 review step should catch unverified anchors before QV gates flag them.

Steps analyzed: 12   Steps with retries: 2 (S06: 3 runs; S07: 2 runs)   Total fix-cycles: 2   DB signal: yes

[1] Design-doc anchor for `item_detail` was unverified, causing 2 fix cycles
    Severity: HIGH   Class: design   Frequency: systemic
    Evidence:
      - ai-dev/active/CR-00044/fix-cycles/CR-00044_S06_FIX_cycle1_prompt.md — "The line is 103 characters. The design doc (line 45) says to verify anchors against rendered toc heading ids — if unconfirmed, ship without fragment. I'll remove the unverified anchor."
      - ai-dev/active/CR-00044/fix-cycles/CR-00044_S07_FIX_cycle1_prompt.md — "The item_detail entry in _SLUG_TO_DOC had a multi-line string that ruff wanted collapsed to a single line."
      - .worktrees/CR-00044/ai-dev/logs/CR-00044_S06_run2.log:7 — "E501 Line too long (103 > 100) --> dashboard/routers/help.py:42:101"
      - .worktrees/CR-00044/ai-dev/logs/CR-00044_S01_run1.log — S01 implementation included the anchor without verifying it against rendered doc heading IDs; S05 review did not catch the missing verification
    Recommendation: Add an explicit anchor-verification step to the CR/Feature design-doc template: "For each `#anchor` in `_SLUG_TO_DOC` or any URL fragment, confirm the heading ID exists in the rendered target doc (check `docs/*.md` at the heading line). If unconfirmed, omit the fragment." Also add to the S05 CodeReview_Final prompt an explicit check: "Verify every `#anchor` in `_SLUG_TO_DOC` is confirmed against the rendered doc's heading IDs."
    Target: templates/design/ChangeRequest_Design_Template.md, prompts/CR-00044_S05_CodeReview_Final_prompt.md (or the equivalent S05 prompt template)
    Pros: Eliminates fix-cycle waste caused by bad anchors; ensures QV gates don't block on easily preventable issues.
    Cons: Slight increase in design-doc writing time (verify 1 anchor takes ~2 min).
    If we don't: Every CR/Feature that specifies an anchor risks 2 fix cycles (lint + format) before merging; agents learn to strip anchors rather than verify them.
    Effort: S (~5 lines in design template, ~3 lines in code-review final prompt template)