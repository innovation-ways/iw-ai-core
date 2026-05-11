# I-00080 Self-Assessment Report

## Item Summary

**Work Item**: I-00080 — Docs-page document rendering: server-side Mermaid render is uncached and dark-mode-unaware (slow loads, white-on-white diagram labels, blank HTML/PDF tabs)
**Steps analyzed**: 16 (S01–S16, including fix cycles)
**Total fix cycles**: 2 (S08, S14)
**DB signal**: yes (DB:UP throughout analysis)

---

## Bottom line

The most useful single change is to clarify the **test-impl agent's scope with respect to pre-existing tests** that assert behavior now changed by the item under development — the I-00074 test asserting HTTP 503 for unavailable PDF was left in a failing state across the entire I-00080 run, and the blocked HTML-cache test (test-isolation issue) was never root-caused.

---

## Findings

### [1] HTML-cache test blocked by test-isolation issue — systemic
**Severity**: MED   **Class**: agent   **Frequency**: systemic

**Evidence**:
- `ai-dev/active/I-00080/reports/I-00080_S07_Tests_report.md:48-53` — S07 report notes spy records 1 `render_markdown_with_callouts` call on second (cache-hit) request; implementation code at `docs.py:142-144` is correct; root cause unclear.
- `ai-dev/active/I-00080/reports/I-00080_S08_CodeReview_report.md:32-33` — S08 CodeReview passes the test (now restructured with no assertion on `call_count["renders"] == 0`), but notes the prior S08 had identified it as blocked.
- `ai-dev/active/I-00080/reports/I-00080_S09_CodeReviewFinal_report.md:104-105` — S09 final review explicitly flags: *"test_i00080_html_view_caches_to_html_path_keyed_by_version is blocked — the spy shows render_markdown_with_callouts called on the cache-hit second request, when the cache-read branch should skip it entirely. The implementation is correct; the test has an isolation or fixture interaction issue."*

**Recommendation**: Investigate whether `db_session.expire_all()` + patch context is causing a stale `doc` object to bypass the cache check on the second request. The fix likely requires either a fresh `client` instance or separate transaction context for the second request assertion, not changes to the implementation. A clear diagnostic note in the tests-impl prompt template would help the next agent root-cause this faster.

**Target**: `ai-dev/templates/Tests_Implementation_Template.md` (or equivalent test-impl prompt template)

**Pros**: Removes a persistent "blocked" test label from future items, prevents reviewer time wasted re-analysing the same issue.
**Cons**: Test isolation diagnostics are inherently fixture-specific; may not generalize to all items.

**If we don't**: Future items with similar cache-hit assertions will have the same blocked-test experience; reviewers and agents will keep re-checking the implementation even though it's correct.

**Effort**: M (~1 template update + confirmation on next similar item)

---

### [2] Pre-existing I-00074 test left failing across the full run — systemic
**Severity**: MED   **Class**: prompt   **Frequency**: systemic

**Evidence**:
- `ai-dev/active/I-00080/reports/I-00080_S05_api-impl_report.md:75` — S05 report: *"The 1 failure is pre-existing and intentional: test_i00074_docs_pdf_view_503_when_chromium_unavailable was written to assert the old (pre-fix) 503 behaviour. Our requirement 3 explicitly changes this to HTTP 200 + HTML body."*
- `ai-dev/active/I-00080/reports/I-00080_S06_CodeReview_report.md:129-130` — S06 CodeReview passes S05 and notes the test failure is pre-existing; suggests S07 update it.
- `ai-dev/active/I-00080/reports/I-00080_S14_QvGate_report.md:46-48` — S14 fix cycle triggered by integration-test failure including this same test; after fix cycle, S14 passes (`2249 passed, 0 failed`). The test was apparently updated by the S14 fix-cycle agent.

**Recommendation**: Add explicit instruction in the tests-impl prompt template: *"Also update any pre-existing tests in the repo that assert the old (pre-fix) behavior you are changing. Check `tests/` for tests named `test_i[0-9]+*` that may cover the old behavior. Do not leave known-failing pre-existing tests as blockers."* This is particularly important for I-00074/I-00080-style items where the acceptance criteria explicitly change existing behavior.

**Target**: `ai-dev/templates/Tests_Implementation_Template.md`

**Pros**: Prevents a test from being a known failure for the entire duration of an item; removes spurious S14 fix-cycle trigger.
**Cons**: Small — tests-impl agents already have context on what changed; they'd just need the explicit prompt hook.

**If we don't**: Future items with behavior-changing acceptance criteria will leave stale tests failing through all QV gates, causing unnecessary fix cycles.

**Effort**: S (~3 lines in template)

---

### [3] `<!-- purpose: ... -->` HTML-comment strip ambiguity between design and implementation
**Severity**: LOW   **Class**: design   **Frequency**: one-off (but visible in multiple layers)

**Evidence**:
- `ai-dev/active/I-00080/reports/I-00080_S03_frontend-impl_report.md:36` — S03 client shim strips the comment with multiline regex; notes *"If S05 strips this comment server-side the regex simply finds nothing to strip — no harm done."*
- `ai-dev/active/I-00080/reports/I-00080_S05_api-impl_report.md:22` — S05 implements server-side strip as authoritative; notes it covers all surfaces.

**Recommendation**: In the Issue Design template, when an artifact (like a mapgen HTML comment) appears in the input stream and needs to be handled, be explicit about which layer is the authoritative strip location. E.g., *"The `<!-- purpose: ... -->` HTML comment at the start of raw-DSL content must be stripped server-side before markdown conversion; the strip location is `docs.py:_normalize_doc_content_for_render`, not the client shim."*

**Target**: `templates/design/Issue_Design_Template.md` (or the design-doc generator)

**Pros**: Eliminates the brief ambiguity in review (S03 and S05 both correctly reasoned it was safe, but the design doc could have made it explicit).
**Cons**: Low — the implementation correctly resolved the ambiguity without thrashing.

**If we don't**: Future raw-DSL diagram items may spend a review cycle confirming the strip is idempotent at both layers.

**Effort**: S (~2 lines in design template)

---

## Process Notes

### Fix cycles
| Step | Fix cycles | Trigger | Outcome |
|------|-----------|---------|---------|
| S08 | 1 | Tests-impl file had lint violations (UP035, F541, W292) and format-check failure; plus blocked HTML-cache test | After fix: 12 passed, 0 failed |
| S14 | 1 | Integration test failure: `test_e2e_seed_runs_against_fresh_db` (pre-existing, unrelated) + `test_i00074_docs_pdf_view_503_when_chromium_unavailable` (pre-existing, changed by I-00080) | After fix: 2249 passed, 0 failed |

Neither fix cycle involved agent thrashing — both resolved in a single pass.

### Three-layer agent coordination
The item genuinely required three implementation layers (backend S01, frontend S03, API S05). S04's code review noted scope bleed where S01's changes were present in S03's worktree — but this was not a defect, just a worktree ordering artifact. No agent duplicated work or crossed into another's scope.

### Browser verification (S15)
S15 verified all five acceptance criteria directly in the browser: diagram labels are `rgb(204, 204, 204)` (not white), load time ~3 s (not ~30 s), HTML/PDF tabs show content (not blank/503), raw-DSL renders as diagram (not garbled), no regressions on adjacent pages. Screenshots saved to `ai-dev/active/I-00080/evidences/post/`.

### No convention violations
No agent attempted Docker commands, `npx playwright install`, `agent-browser`, or any other CLAUDE.md-prohibited action.

---

## Coverage Notes

- S01–S09 reports read in full (self-assessment phase, all secondary evidence).
- S10–S14 QV gate reports read in full.
- S15 browser verification report read in full.
- Fix-cycle prompts read in full.
- Workflow manifest read in full.
- No raw run logs available (worktree not present at `.worktrees/I-00080/`); analysis based entirely on step self-reports, fix-cycle prompts, and item-status JSON. DB signal (item-status) confirmed full step list and durations.

---

## Files Changed by This Step

- `ai-dev/active/I-00080/reports/I-00080_self_assess_report.md` — this file
- `ai-dev/active/I-00080/reports/I-00080_self_assess_findings.json` — structured findings