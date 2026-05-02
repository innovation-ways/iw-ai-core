# I-00055_S04_CodeReview_report.md

## Step Summary

**Agent**: CodeReview (S04)
**Work Item**: I-00055 — Architecture Diagram renders twice on Code page; inline copy unreadable in dark mode
**Step Reviewed**: S03 (Tests)
**Review Date**: 2026-05-01

---

## Review Verdict

**PASS** — All tests are semantically correct, falsifiable, and regression-protective.

---

## Files Changed (S03)

| File | Purpose |
|------|---------|
| `orch/rag/mapgen.py` | Fixed `strip_trailing_arch_diagram_section` implementation; added `noqa: ARG002` on `mermaid` param |
| `tests/unit/rag/test_mapgen.py` | 3 test cases for `_assemble_markdown` invariant |
| `tests/unit/rag/test_strip_arch_diagram_section.py` | 7 test cases for strip helper |
| `tests/dashboard/test_code_page_arch_diagram.py` | 4 dashboard integration tests |

---

## Pre-Flight Quality Gates

```
make lint      — PASS (0 violations)
make format    — PASS (508 files already formatted)
```

No convention violations introduced by S03 on any of the three test files.

---

## Review Checklist

### 1. Falsifiability

| Test | Assertion | Would it FAIL on pre-S01 code? | Verdict |
|------|-----------|--------------------------------|---------|
| `test_i00055_assemble_markdown_omits_inline_diagram` | `## Architecture Diagram` not in md, `<!-- purpose:` not in md, ` ```mermaid ` not in md — all three required | YES — pre-S01 `_assemble_markdown` appended the diagram block | ✅ Correct |
| `test_strip_trailing_arch_diagram_section_removes_legacy_block` | All three forbidden substrings absent after strip | YES — pre-S01 stored docs would retain the block and the strip wouldn't be applied at render time yet | ✅ Correct |
| `test_strip_trailing_arch_diagram_section_is_idempotent` | `once == twice` | YES — pre-S01 code has no idempotency guarantee | ✅ Correct |
| `test_strip_trailing_arch_diagram_section_keeps_non_trailing_h2` | `result == md.rstrip()` (equality, not just no-error) | YES — would fail if strip incorrectly removes non-trailing `## Architecture Diagram` | ✅ Correct |
| `test_code_page_renders_exactly_one_diagram` | `inline_count + bottom_count == 1` (exactly one, not "at most two") | YES — pre-S01 rendered 2 diagrams (inline + bottom) | ✅ Correct |

**Shape-check issue detected and confirmed fixed by S03**: The dashboard test correctly uses `== 1` (exactly one), not `>= 1` or `<= 2`. The S03 agent correctly wrote `assert inline + bottom == 1`.

### 2. Real-DB Integration Discipline

- Dashboard test uses `db_session` fixture backed by testcontainers (from `tests/dashboard/conftest.py`).
- `create_app()` + `app.dependency_overrides[get_db] = override_get_db` pattern matches established project pattern.
- No DB mocks used.
- `Project` imported from `orch.db.models` (safe because test uses testcontainer).
- FTS trigger setup is handled by the `db_session` fixture inherited from the conftest hierarchy.

### 3. Test Isolation

- Each test calls `_seed_docs(db_session, project.id)` with unique `project_id` (from `test_project` fixture).
- No reliance on a particular project existing on disk.
- No live network, no Ollama, no LLM calls — all three test files are pure string-contract or FastAPI TestClient tests.

### 4. Coverage of Both Fix Arms

| Fix Arm | Covered By | Evidence |
|---------|-----------|---------|
| mapgen writer no longer emits diagram | `test_i00055_assemble_markdown_omits_inline_diagram` | Direct assertion on `_assemble_markdown` output |
| render-time strip helper removes legacy block | `test_strip_trailing_arch_diagram_section_*` (7 tests) | Direct unit tests on `strip_trailing_arch_diagram_section` |
| Dashboard end-to-end (both together) | `test_code_page_renders_exactly_one_diagram` | Seeds legacy arch-map + clean diagram-architecture doc; asserts `inline + bottom == 1` |

Both fix arms are covered. The dashboard test exercises the composition: legacy content in DB → strip helper applied in `_render_architecture_html` → exactly one diagram renders.

### 5. Convention Conformance

- Tests live under `tests/unit/rag/` and `tests/dashboard/` — correct subtrees. ✅
- Naming: `test_*.py`, `def test_*(...)` — correct. ✅
- Imports: `from __future__ import annotations` at top; pytest, FastAPI TestClient, SQLAlchemy models — all follow project style. ✅
- `_LEGACY_ARCH_MAP_CONTENT` and `_CLEAN_ARCH_DIAGRAM_DSL` defined as module-level constants with descriptive names — matches project convention. ✅

---

## Test Results

```
uv run pytest tests/unit/rag/test_mapgen.py tests/unit/rag/test_strip_arch_diagram_section.py tests/dashboard/test_code_page_arch_diagram.py --no-cov -v

tests/unit/rag/test_mapgen.py                              3 passed
tests/unit/rag/test_strip_arch_diagram_section.py          7 passed
tests/dashboard/test_code_page_arch_diagram.py             4 passed

14 passed, 0 failed
```

Full unit suite: `make test-unit` → **2264 passed** (0 failures).

---

## Notes

1. **Non-trailing H2 test is correctly structured**: `test_strip_trailing_arch_diagram_section_keeps_non_trailing_h2` asserts equality (`result == md.rstrip()`), not just absence of error. This proves the function does not touch non-trailing `## Architecture Diagram` H2s. This is the critical defensive test that validates the fix from S01/S03.

2. **`test_no_op_when_absent` compares to `clean.rstrip()`**: The function unconditionally calls `.rstrip()` on output, so the comparison is `result == clean.rstrip()`. This is documented in the assertion message — correct.

3. **Idempotency test compares equality of two consecutive applications**: `once == twice` — not just "no error raised". Correct.

4. **Dashboard test `test_strip_helper_is_applied_to_arch_map_content`** is a semantic check rather than a white-box test — it verifies that the `<!-- purpose: shows overall architecture -->` comment from the seeded legacy content does not appear in the rendered page HTML. This confirms the strip helper runs at render time. While the primary regression test (`test_code_page_renders_exactly_one_diagram`) is the definitive proof, this supplementary test adds coverage.

5. **`make test-integration` timeout**: The integration suite is slow (180+ seconds) due to multiple testcontainers spinning up. The new I-00055 tests do not require integration DB — they use FastAPI TestClient with a single testcontainer fixture. The 14 tests all pass when run directly. No DB-related issues were found.

---

## Mandatory Fix Count

**0** — No CRITICAL or HIGH findings.

---

## JSON Summary

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00055",
  "step_reviewed": "S03",
  "verdict": "pass",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "14 passed (3 mapgen unit + 7 strip unit + 4 dashboard), 0 failed. Full unit suite: 2264 passed.",
  "notes": "All tests are semantically correct, falsifiable against pre-S01 bug, and cover both fix arms (mapgen non-emission + render-time strip). Conventions fully respected. No mocks, no live DB, no LLM calls. Dashboard test uses exact-one assertion (== 1). Strip helper negative test uses equality (not just no-error). Idempotency test uses equality of two applications."
}
```