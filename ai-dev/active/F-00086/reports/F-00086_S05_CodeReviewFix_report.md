# F-00086 S05 — Code Review Fix Report (Fix Cycle 1)

**Step**: S05 (code-review-fix-impl)
**Original Step**: S03 (backend-impl)
**Review That Triggered Fix**: S04
**Fix Cycle**: 1 of 5
**Work item**: F-00086 — Multi-tab AI Assistant on OpenCode
**Date**: 2026-05-19

---

## What Was Done

S04 produced exactly **one** mandatory finding (MEDIUM_FIXABLE) and one LOW (non-mandatory) finding.

### Finding #1 (MEDIUM_FIXABLE) — Fixed

**File**: `orch/chat/tab_service.py`, line 68
**Category**: conventions

**Problem**: The `ValueError` message used `sorted(ALLOWED_RUNTIMES)!r` which produces list notation `['opencode']`. The design spec (§Boundary Behavior table and AC6) requires set notation `{'opencode'}`. When S06 wires this exception into the HTTP 400 response body, AC6's assertion checking the exact bracket notation would fail.

**Fix**: Changed `sorted(ALLOWED_RUNTIMES)!r` → `set(ALLOWED_RUNTIMES)!r`. The resulting message is now `"runtime 'pi' not in allowlist {'opencode'}"` — exactly matching the design spec.

**Spec re-anchor**: Confirmed against design doc:
- §Boundary Behavior line 286: `HTTP 400 with {"error":"runtime 'pi' not in allowlist {'opencode'}"}`
- §Acceptance Criteria AC6 line 235: `error "runtime 'pi' not in allowlist {'opencode'}"`

Both unambiguously use curly-brace set notation.

### Finding #2 (LOW) — Not Addressed

`OpencodeRuntime.subscribe` silently ignores `session_id` (already documented via `# noqa: ARG002`). The review tagged this as LOW / suggestion only — outside the CRITICAL/HIGH/MEDIUM(fixable) fix scope per the prompt's "Apply **only** those findings" constraint. The existing `noqa` already documents the intentional discard.

## Files Changed

- `orch/chat/tab_service.py` (1 line: error message format)

## Test Results

All targeted test suites pass with zero failures:

| Suite | Result |
|-------|--------|
| `uv run pytest tests/unit/chat/ -v --no-cov` | **9/9 passed** in 5.47s |
| `uv run pytest tests/dashboard/test_chat_router.py tests/integration/test_chat_endpoint_session_lifecycle.py -v --no-cov` | **49/49 passed** in 23.20s |
| `make lint` | All checks passed (ruff + check_templates.py) |
| `make typecheck` | Success: no issues found in 262 source files |

The existing `test_create_tab_rejects_unknown_runtime` test uses a partial regex (`r"runtime 'pi' not in allowlist"`), so it covers both the old and new message formats and continues to pass.

## Observations

- The fix is one character/word change (`sorted` → `set`), minimum-patch as the prompt requires.
- No semantic drift: the only observable change is the bracket notation in the error message — exactly the deviation the reviewer flagged.
- `set(frozenset({"opencode"}))!r` produces `{'opencode'}` deterministically (single-element sets always render this way; multi-element sets are not yet possible because `ALLOWED_RUNTIMES` only has one entry — F-B will widen it, but at that point the spec's exact-string format will need re-evaluation anyway).

## Contract JSON

```json
{
  "step": "S05",
  "agent": "code-review-fix-impl",
  "work_item": "F-00086",
  "fix_cycle": 1,
  "review_step": "S04",
  "findings_addressed": [
    {
      "finding_number": 1,
      "severity": "MEDIUM_FIXABLE",
      "status": "fixed",
      "files_changed": ["orch/chat/tab_service.py"],
      "description": "Changed error message format from sorted(ALLOWED_RUNTIMES)!r (list notation ['opencode']) to set(ALLOWED_RUNTIMES)!r (set notation {'opencode'}) to match design spec §Boundary Behavior and AC6. Existing tests continue to pass; downstream S06 HTTP 400 body will now match the spec exactly."
    }
  ],
  "findings_skipped": [
    {
      "finding_number": 2,
      "severity": "LOW",
      "reason": "Outside CRITICAL/HIGH/MEDIUM(fixable) fix scope per prompt constraints. The noqa: ARG002 already documents the intentional discard; the suggestion is a nice-to-have docstring polish, not a correctness issue."
    }
  ],
  "tests_passed": true,
  "test_summary": "tests/unit/chat/: 9/9 passed. tests/dashboard/test_chat_router.py + tests/integration/test_chat_endpoint_session_lifecycle.py: 49/49 passed. make lint: clean. make typecheck: clean (262 files).",
  "notes": "Single-line fix; no refactoring beyond flagged scope; spec re-anchor verified before edit."
}
```
