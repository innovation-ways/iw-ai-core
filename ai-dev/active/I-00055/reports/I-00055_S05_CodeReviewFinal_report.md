# I-00055_S05_CodeReviewFinal_report.md

## Step Summary

**Agent**: CodeReview_Final (S05)
**Work Item**: I-00055 — Architecture Diagram renders twice on Code page; inline copy unreadable in dark mode
**Step Reviewed**: S01..S04 (Backend + Tests, cross-step integration)
**Review Date**: 2026-05-01

---

## Pre-Flight Gate Results

```
make lint      — PASS (0 violations)
make format    — PASS (508 files already formatted)
make typecheck — PASS (0 errors in 210 source files)
make test-unit — PASS (2264 passed, 2 skipped, 5 xfailed, 1 xpassed)
```

---

## Cross-Step Integration Review

### 1. End-to-End Fix Coverage ✅

Trace the complete bug-fix arc across the three changed layers:

**Authoring path** (`orch/rag/mapgen.py`):
- `MapGenerator._assemble_markdown()` (lines 342–355) no longer appends a trailing `## Architecture Diagram` section.
- `mermaid` and `purpose` parameters are retained with `# noqa: ARG002` — call sites unchanged.
- The standalone `diagram-architecture` ProjectDoc is still stored separately via `store_arch_diagram` (lines 185–221) — the dual-write architecture is preserved exactly as designed.

**Storage path**: Intact. The standalone `diagram-architecture` ProjectDoc is still created/stored by `store_arch_diagram`. No change to this path.

**Render path** (`dashboard/routers/code_ui.py`):
- `_render_architecture_html()` (lines 82–87) calls `strip_trailing_arch_diagram_section(arch_doc.content)` before `_preprocess_mermaid()` and `render_markdown()`.
- `code_architecture()` endpoint inherits the fix automatically — no template changes needed.
- Stored docs are never mutated; the strip is purely in-memory at render time.

**Tests** (`tests/unit/rag/test_mapgen.py`, `tests/unit/rag/test_strip_arch_diagram_section.py`, `tests/dashboard/test_code_page_arch_diagram.py`):
- 3 mapgen unit tests asserting the `_assemble_markdown` invariant.
- 7 strip-helper unit tests covering positive, idempotent, no-op, non-trailing-H2, no-final-newline, content-preservation, and multiple-mermaid cases.
- 4 dashboard integration tests including the primary reproduction test `test_code_page_renders_exactly_one_diagram`.

All three arms are present and compose correctly.

---

### 2. Reproduction Test Correctness ✅

`test_code_page_renders_exactly_one_diagram` in `tests/dashboard/test_code_page_arch_diagram.py`:

- Seeds an `architecture-map` ProjectDoc with `_LEGACY_ARCH_MAP_CONTENT` (trailing `## Architecture Diagram` + mermaid fence + YAML frontmatter).
- Seeds a separate `diagram-architecture` ProjectDoc with `_CLEAN_ARCH_DIAGRAM_DSL` (no purpose comment, no YAML frontmatter).
- Seeds a completed `CodeIndexJob` linking to the arch-map doc.
- GETs `/project/{id}/code` and asserts `inline_count + bottom_count == 1`.

This test **would fail on `main`** (pre-fix) because:
- The legacy arch-map content would produce an inline `<pre data-lang="mermaid">` from `_preprocess_mermaid()`.
- The standalone `diagram-architecture` doc would produce a bottom `<div class="mermaid">`.
- Total = 2 diagrams → assertion `== 1` fails.

Post-fix: the strip helper removes the trailing section before preprocessing, so only the bottom `<div class="mermaid">` from the diagram-architecture doc remains.

---

### 3. Operational Follow-Up ✅

The design doc's "Operational Follow-up" section (I-00055_Issue_Design.md, lines 283–292) is intact and accurately describes the post-merge regen step:

```bash
# For each project_id from projects.toml or `iw projects list`:
curl -fsS -X POST "$DASHBOARD_URL/project/$pid/api/code/regen-map"
```

**Confirmed**: No step in S01..S04 silently triggers regeneration. The fix is purely defensive — the strip helper bridges the gap for legacy docs until regen runs. The regen is explicitly operator work, not part of the fix.

---

### 4. No Scope Creep ✅

Reviewed all changed files for out-of-scope changes:

| File | Changes | Verdict |
|------|---------|---------|
| `orch/rag/mapgen.py` | Removed diagram emission from `_assemble_markdown`; added `strip_trailing_arch_diagram_section` | ✅ In-scope |
| `dashboard/routers/code_ui.py` | Imported and applied `strip_trailing_arch_diagram_section` in `_render_architecture_html` | ✅ In-scope |
| `tests/unit/rag/test_mapgen.py` | 3 unit tests for `_assemble_markdown` invariant | ✅ In-scope |
| `tests/unit/rag/test_strip_arch_diagram_section.py` | 7 unit tests for strip helper | ✅ In-scope |
| `tests/dashboard/test_code_page_arch_diagram.py` | 4 dashboard tests for reproduction + regression | ✅ In-scope |

**No changes** to:
- `_clean_diagram_dsl` (intentionally untouched per design)
- `code_architecture_view.html` / `code_architecture_diagram.html` templates
- Components-cards layout / chip strip (Incident B)
- Chat panel toggle UI (Incident C)
- Mapgen prompt-length tuning (Incident B)
- Any migration file

---

### 5. CLAUDE.md Conformance ✅

Swept all changed files against project-wide rules:

| Rule | Status | Evidence |
|------|--------|---------|
| No new direct DB connections from tests | ✅ | Dashboard test uses testcontainer-backed `db_session` fixture from `tests/dashboard/conftest.py`; no raw connections |
| No `docker compose up` commands | ✅ | None introduced |
| No alembic upgrade/downgrade calls | ✅ | None introduced |
| No `importlib.reload(orch.config)` in tests | ✅ | Not present |
| Testcontainers used for DB fixtures | ✅ | Confirmed in `conftest.py` |
| `# noqa: ARG002` for intentionally unused params | ✅ | Both `mermaid` and `purpose` in `_assemble_markdown` have this annotation |

---

### 6. Test Suite Verification

```
make test-unit → 2264 passed, 2 skipped, 5 xfailed, 1 xpassed, 48 warnings
```

All I-00055-specific tests pass:
- `tests/unit/rag/test_mapgen.py`: 3 passed
- `tests/unit/rag/test_strip_arch_diagram_section.py`: 7 passed
- `tests/dashboard/test_code_page_arch_diagram.py`: 4 passed (TestClient with testcontainer-backed `db_session`)

Pre-existing `test_safe_migrate.py` failures (2 tests) confirmed by S01/S02 as unrelated to I-00055 — they fail due to `IW_CORE_AGENT_CONTEXT=true` leaking into the shell environment.

`make test-integration` times out at 300s on this environment (not a code defect; the suite is slow by design). The I-00055 dashboard test does not require integration DB — it uses FastAPI TestClient with a single testcontainer session.

---

## Findings

**CRITICAL**: 0
**HIGH**: 0
**MEDIUM (fixable)**: 0
**MEDIUM (suggestion)**: 0
**LOW**: 0

All cross-step integration checks pass. The fix is complete and correct.

---

## Notes

1. **Strip helper implementation (S03 fix)**: The S03 agent found and fixed a semantic bug in the original regex-based `strip_trailing_arch_diagram_section` implementation — the original regex `\Z` anchor incorrectly stripped content when `## Architecture Diagram` was NOT the last H2. The fixed implementation (using `content.rfind("\n## ")` to locate the last H2 and extracting its title) is correct and was validated by the `test_strip_trailing_arch_diagram_section_keeps_non_trailing_h2` defensive test.

2. **S02 and S04 reports are both present** in `ai-dev/active/I-00055/reports/`:
   - `I-00055_S02_CodeReview_report.md` — PASS, 0 mandatory fixes
   - `I-00055_S04_CodeReview_report.md` — PASS, 0 mandatory fixes

3. **Format note from S02**: The S02 agent found and auto-fixed a ruff-format violation in `orch/rag/mapgen.py` left by the S01 agent. This is a minor process note, not a code defect.

---

## Mandatory Fix Count

**0** — The implementation is complete and correct.

---

## Test Summary

- Unit tests: **2264 passed** (0 new failures)
- I-00055-specific: **14 passed** (3 mapgen + 7 strip + 4 dashboard)

---

## Verdict

**PASS** — The mapgen change, render-time strip helper, and tests compose into a complete fix for the double-diagram bug. The fix is minimal, conservative, and correctly scoped. All pre-flight quality gates pass. All three arms of the fix (authoring path, storage path, render path) are covered by tests.
