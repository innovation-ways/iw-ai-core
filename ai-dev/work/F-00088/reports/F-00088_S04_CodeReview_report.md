# F-00088 S04 Code Review Report

## Step: S04 — Code Review (S03 backend implementation)
**Agent**: code-review-impl
**Work Item**: F-00088 — Structured Dashboard E2E Test Layer
**Step Reviewed**: S03
**Status**: ✅ PASS

---

## Pre-Review Gates (Non-Negotiable)

| Gate | Command | Result |
|------|---------|--------|
| Format | `make format-check` | ❌ FAIL — `tests/e2e/test_journey_code_qa_sse.py` would be reformatted |
| Lint | `make lint` | ❌ FAIL — E501 (line too long) in `test_journey_code_qa_sse.py:73` |
| Assertions | `make test-assertions` | ✅ PASS — no new violations (555 files scanned) |

Both format and lint failures are in the **same file**: `tests/e2e/test_journey_code_qa_sse.py:73`, line 109 characters — exceeds the 100-char limit. This is a new violation introduced by S03 (confirmed by `git diff origin/main -- tests/e2e/test_journey_code_qa_sse.py`).

---

## Review Findings

| Severity | Category | File | Line | Description | Fix |
|----------|----------|------|------|-------------|-----|
| **HIGH** | code_quality | `tests/e2e/test_journey_code_qa_sse.py` | 73 | E501: line 109 chars (limit 100). `pw.eval_js("", "document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true}))")` — the JS string is too long and `ruff format` wants to reformat it. | Break the JS string into a variable before the call, e.g. `script = "document.dispatchEvent(...)"; pw.eval_js("", script)` — single-line variable declaration fits in 100 chars. Or pass `script` on next line. |
| **MEDIUM_FIXABLE** | conventions | `tests/e2e/test_journey_htmx_fragments.py` | top of file | Missing docstring note on the CR-00072 relationship. The design specifies: *"`test_journey_htmx_fragments` must have a module docstring (or a prominent comment) explaining that this journey is the **browser-level complement** to CR-00072's TestClient route sweep — CR-00072 has no JS/HTMX runtime; this journey does."* The skill's §13 (`skills/iw-ai-core-testing/SKILL.md:422`) mentions this relationship but the journey file itself is silent. Absence will confuse the next engineer reading both files. | Add a prominent note at the top of the module docstring, e.g. `"CR-00072 relationship: this journey is the browser-level complement to test_route_contract_sweep.py (CR-00072) — CR-00072 has no JS/HTMX runtime; this journey does."` |
| **MEDIUM_FIXABLE** | code_quality | `tests/e2e/test_journey_code_qa_sse.py` | 54-56 | `pw.check_htmx_dangling_targets()` is called with no argument. The method `check_htmx_dangling_targets(self, html_fragment: str)` requires a mandatory `html_fragment: str` parameter — it has no default. At runtime this will raise `TypeError: check_htmx_dangling_targets() missing 1 required positional argument: 'html_fragment'`. The call should be `pw.check_htmx_dangling_targets(pw.snapshot())`. | Pass the current page snapshot as the argument. |
| **MEDIUM_FIXABLE** | code_quality | `tests/e2e/test_journey_htmx_fragments.py` | 96 | `pw.assert_htmx_dangling_targets()` is called with no argument. The method `assert_htmx_dangling_targets(self, html_fragment: str)` requires a mandatory `html_fragment: str` parameter — it has no default. At runtime this will raise `TypeError`. The call should be `pw.assert_htmx_dangling_targets(pw.snapshot())`. | Pass the post-HTMX-swap snapshot as the argument. |
| **LOW** | code_quality | `tests/e2e/test_journey_code_qa_sse.py` | 79, 100 | `pw.wait_for_sse_chunk(timeout=30)` is called with only a `timeout` kwarg but the method signature is `wait_for_sse_chunk(self, stream_output: str, timeout: float = 30.0)`. The `stream_output` positional argument is missing. At runtime this will raise `TypeError`. | The SSE chunk detection in the wrapper is based on HTTP response body text. Since the wrapper uses `playwright-cli` (which doesn't directly expose HTTP response bodies), the correct SSE detection approach should be clarified — either the wrapper needs an SSE capture method or the test needs a different assertion approach. See note below. |

---

## Detailed Analysis

### ✅ Scope Discipline

`git diff origin/main -- dashboard/ orch/ executor/` → **empty** (no production code touched). No migration files added. ✅

### ✅ AC1 — playwright-cli wrapper uses binary exclusively

All browser interactions go through `playwright-cli` subprocess calls. No `chromium.launch`, `agent-browser`, or `npx playwright install` anywhere in `tests/e2e/`. The only reference to `chromium.launch` is in a docstring — the comment warning *against* using it. ✅

### ✅ AC2 — All six journeys exist and assert a11y + no console errors

All five S03 journeys present, each with `assert_accessibility()` and `assert_no_console_errors()` calls. ✅

| Journey | File | a11y call | console-error call |
|---------|------|-----------|-------------------|
| Journey 1 (home_navigation) | S01 | L57, L110 | L58, L105, L140 |
| Journey 2 (queue_to_merge) | S03 | L84, L176 | L89, L112, L168 |
| Journey 3 (code_qa_sse) | S03 | L105 | L120 |
| Journey 4 (docs_export) | S03 | L119 | L105, L113, L124 |
| Journey 5 (jobs_filters) | S03 | L124 | L129 |
| Journey 6 (htmx_fragments) | S03 | L101 | L106 |

### ✅ AC4 — e2e_smoke subset is exactly two journeys

```
uv run pytest tests/e2e/ -m e2e_smoke --collect-only -q --no-cov
→ 2/22 collected:
   test_journey_home_navigation
   test_journey_queue_to_merge
```

Exactly `home_navigation` + `queue_to_merge`. ✅

### ✅ AC5 — e2e.yml workflow correctness

- `e2e-smoke` job: `if: github.event_name == 'pull_request' || github.event_name == 'push'` — **blocking**, no `continue-on-error`. ✅
- `e2e-full` job: `if: github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'` — `continue-on-error: true`. ✅
- `e2e-smoke` does NOT appear in `schedule` — no risk of nightly slow suite on every push. ✅
- `e2e-full` does NOT appear in `push` — no risk of slow full suite on every commit. ✅
- Teardown step: `if: always()` on both jobs. ✅
- No hardcoded ports — env vars `COMPOSE_PROJECT_NAME`, `E2E_FRONTEND_PORT`, `E2E_DB_PORT`, `IW_BROWSER_BASE_URL` used throughout. ✅

### ⚠️ Journey 6 — htmx-fragments CR-00072 relationship note missing

`skills/iw-ai-core-testing/SKILL.md:422` mentions the relationship, but `test_journey_htmx_fragments.py` itself has no module-level note. Per the design (Review Checklist item 5), this is **MEDIUM_FIXABLE**. ✅ (flagged)

### ✅ AC7 — docs / skill / plan updated and synced

- `docs/IW_AI_Core_Testing_Strategy.md` — §2 Layer 4, §5 gate table, §9 updated. ✅
- `skills/iw-ai-core-testing/SKILL.md` — §13 E2E browser journey layer documented. ✅
- `.claude/skills/iw-ai-core-testing/SKILL.md` — byte-identical to master (`diff` returns empty). ✅
- `ai-dev/work/TESTS_ENHANCEMENT.md` — item 3.1 marked DONE 2026-05-21 (F-00088), §11 changelog entry present. ✅

### ✅ Invariant checks

- **Invariant 6**: `grep -rn 'chromium.launch\|agent-browser\|npx playwright' tests/e2e/` → only the docstring warning. No actual usage. ✅
- **Invariant 8**: Exactly two journeys marked `@pytest.mark.e2e_smoke`. ✅ (verified in collection output)

### ✅ TDD RED Evidence

`test_harness_selfcheck.py` extended with:
- `TestDanglingHtmxTargetDetector::test_flags_dangling_hx_target` — RED→GREEN evidence recorded
- `TestSseTimeoutDetector::test_stream_with_no_chunks_raises_sse_timeout` — RED→GREEN evidence recorded

All 16 self-check tests pass. ✅

### ✅ Harness self-check unit tests collect under default addopts

Default collection: 16/22 (6 journey tests deselected by `e2e` marker exclusion). ✅

---

## Critical Issues Requiring Mandatory Fix

The following must be addressed before S05 (final cross-agent review) can proceed:

1. **`test_journey_code_qa_sse.py:73` — line too long (E501)**. Run `uv run ruff format tests/e2e/test_journey_code_qa_sse.py` (or break the long line manually).
2. **`test_journey_code_qa_sse.py:56` — `check_htmx_dangling_targets()` missing required argument**. Fix: `pw.check_htmx_dangling_targets(pw.snapshot())` or equivalent.
3. **`test_journey_htmx_fragments.py:96` — `assert_htmx_dangling_targets()` missing required argument**. Fix: `pw.assert_htmx_dangling_targets(pw.snapshot())`.
4. **`test_journey_code_qa_sse.py:79,100` — `wait_for_sse_chunk()` missing `stream_output` positional argument**. The wrapper's `wait_for_sse_chunk(self, stream_output: str, ...)` expects raw SSE response text. Since `playwright-cli` does not expose raw HTTP response bodies directly, the SSE journey may need to be implemented differently (e.g., polling the DOM for answer-panel text changes rather than raw stream capture). This requires clarification — the current code will `TypeError` at runtime.

---

## Verdict

**FAIL** — 4 mandatory fixes (1 HIGH, 3 MEDIUM_FIXABLE):

1. **HIGH**: Line 73 lint/format violation (new)
2. **MEDIUM_FIXABLE**: `check_htmx_dangling_targets()` missing argument (runtime TypeError)
3. **MEDIUM_FIXABLE**: `assert_htmx_dangling_targets()` missing argument (runtime TypeError)
4. **MEDIUM_FIXABLE**: `wait_for_sse_chunk()` missing `stream_output` argument (runtime TypeError)
5. **MEDIUM_FIXABLE**: CR-00072 relationship note missing from `test_journey_htmx_fragments.py` docstring

All issues are in `tests/e2e/` (test infrastructure — no production code) and are correctable without scope expansion.

**Required action**: S03 agent must fix issues 1–4 (issue 5 can be handled at S05 or as a self-fix). The S04 reviewer should re-run `make lint` + `make format-check` after the fixes and confirm clean before S05 proceeds.