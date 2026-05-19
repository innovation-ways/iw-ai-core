### Item Analysis: F-00086

Bottom line: tighten the S16 qv-browser execution guardrails (selector strategy + command hygiene + session lifecycle checks) to cut the highest-cost retry loop in this item.

Steps analyzed: 17   Steps with retries: 8   Total fix-cycles: 9   DB signal: yes

[1] Browser verification thrash from brittle Playwright interaction patterns
    Severity: HIGH   Class: prompt   Frequency: systemic
    Evidence:
      - ai-dev/logs/F-00086_S16_run1.log:189 - "Error: locator.fill: Error: Element is not an <input>, <textarea> or [contenteditable] element"
      - ai-dev/logs/F-00086_S16_run11.log:643 - "TimeoutError: locator.click: Timeout 5000ms exceeded."
      - ai-dev/logs/F-00086_S16_run11.log:813 - "TypeError: Cannot read properties of undefined (reading 'url')"
    Recommendation: update qv-browser prompts/skill to require resilient role/text selectors, explicit wait-for-enabled checks before click/fill, and a fallback refresh-snapshot branch when element refs drift.
    Target: skills/iw-workflow/SKILL.md
    Pros: reduces high-cost reruns in the most expensive manual-verification step; improves deterministic browser evidence capture.
    Cons: longer prompt and slightly slower first-pass scripting.
    If we don't: S16 will continue to consume multiple reruns/fix cycles when UI state changes or Playwright snapshot refs drift.
    Effort: M (~40-80 lines across 1-2 prompt/skill files)

[2] Fix-cycle execution context drift triggered import-path failures
    Severity: HIGH   Class: convention   Frequency: systemic
    Evidence:
      - ai-dev/logs/F-00086_S16_fix3.log:59 - "ImportError: cannot import name 'tab_service' from 'orch.chat' (/home/sergiog/dev/iw-ai-core/orch/chat/__init__.py)."
      - ai-dev/logs/F-00086_S16_fix4.log:56 - "ModuleNotFoundError: No module named 'orch.chat.opencode'"
    Recommendation: add mandatory fix-cycle preflight (`pwd`, `git rev-parse --show-toplevel`, and one import sanity check) before running pytest in repair steps.
    Target: CLAUDE.md
    Pros: catches wrong-root execution early; avoids misleading failures unrelated to the current fix.
    Cons: tiny overhead at each fix-cycle start.
    If we don't: agents can keep burning retries on environment/path mistakes before touching real defects.
    Effort: S (~10-20 lines in one guidance file)

### TDD RED evidence check

- S03 report contains plausible RED evidence (`ModuleNotFoundError` for missing `orch.chat.migration_helpers`) tied to `test_create_tab_returns_soft_cap_flag_when_count_exceeds_ten` context.
- S06 report contains plausible RED evidence (`assert 404 == 400`) for `test_post_tabs_rejects_unknown_runtime`.
- No TDD evidence anomaly findings promoted.
