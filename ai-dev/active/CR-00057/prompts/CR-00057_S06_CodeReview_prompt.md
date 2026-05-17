# CR-00057_S06_CodeReview_prompt

**Work Item**: CR-00057 — AI Assistant chat model allowlist (per-project, with Ollama provider)
**Step Being Reviewed**: S01 (backend-impl), S02 (api-impl), S03 (frontend-impl), S04 (tests-impl), S05 (template-impl)
**Review Step**: S06
**Agent**: code-review-impl

---

## Standard Policy Headers

Standard `⛔ Docker is off-limits` and `⛔ Migrations: agents generate, daemon applies` policies apply. Read `docs/IW_AI_Core_Agent_Constraints.md` if unsure.

## Input Files

- `ai-dev/active/CR-00057/CR-00057_CR_Design.md` — the contract you are reviewing against
- `ai-dev/active/CR-00057/reports/CR-00057_S01_Backend_report.md` through `..._S05_Template_report.md`
- Implementation files declared in `workflow-manifest.json` under `scope.allowed_paths`
- `CLAUDE.md` and per-package `CLAUDE.md` files for the project conventions
- `skills/iw-ai-core-testing/SKILL.md` for the testing red-flag checklist

## Output Files

- `ai-dev/active/CR-00057/reports/CR-00057_S06_CodeReview_report.md` — findings with severities (CRITICAL / HIGH / MEDIUM / LOW), each with `file:line` reference and a concrete suggested fix

## Review Focus (CR-00057 specific)

Beyond the standard per-agent review checklist, give weight to:

1. **Allowlist validation regex.** Confirm S01's regex `^[a-z0-9._-]+/[A-Za-z0-9._:/-]+$` rejects bad inputs (`MiniMax-M2.7` without provider; `/foo`; `foo/`; whitespace) and accepts every entry in the seed allowlist (`ollama/gemma4:26b` includes the `:` — confirm it's allowed).
2. **Fail-open semantics.** The router must return today's full list (not an empty list, not a 503) when (a) `project_id` is absent, (b) the project doesn't exist, (c) the project has no `ai_assistant` key, (d) the allowlist intersection is empty. All four branches must be tested.
3. **Cache key isolation.** `_config_cache` keyed by `project_id` must not poison across keys. Look for tests that prove two consecutive calls with different ids both populate their slots and don't share state.
4. **Project_id source on the frontend.** `chat.js` must read from `window.location.pathname` with a regex matching `/project/{id}/...` and only that — not from arbitrary referer or document URL fields that could be spoofed. The id is opaque (no decoding).
5. **No template/HTML changes in S03.** The `<select id="chat-assistant-model">` selector must be untouched; the qv-browser step's snapshot assertions depend on it. Flag any rename or attribute change.
6. **Label honesty doc paragraph.** S05's new doc must contain an explicit "Claude Opus 4.7 routes via opencode's Anthropic provider, not the claude-code CLI" paragraph. Missing → HIGH finding.
7. **TDD RED evidence.** S01's `tdd_red_evidence` must show a real RED failure (AttributeError/AssertionError on the parser helper), not an ImportError or fixture error.
8. **CLAUDE.md table row.** S05 must add exactly one row, in a logical position. Multiple-row additions or table reflow → MEDIUM finding.

## Standard Review Checklist

Run through the full per-agent review checklist in `skills/iw-ai-core-testing/SKILL.md` and `docs/IW_AI_Core_Testing_Strategy.md`. Pay particular attention to:

- Test assertion strength (`assert result` is a red flag — needs `assert result == expected`)
- Live-DB write guard compliance
- Cross-project isolation in fixtures
- ORM round-trip correctness (JSONB columns)
- Logging at the right levels (INFO for fallback, WARNING for filtered-out entries, no spam in the happy path)
- Type hints on new helpers
- No silent broad excepts

## Subagent Result Contract

Use the standard code-review-impl JSON contract (severity-grouped findings, each with `file:line`, description, suggested fix, and the layer/agent that wrote it).
