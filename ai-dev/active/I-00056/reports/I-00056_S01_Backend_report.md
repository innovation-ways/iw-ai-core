# I-00056 S01 Backend Report

## What was done

1. **`wrap_h2_sections_collapsible` helper** (`dashboard/utils/markdown.py`):
   - Added a new function that wraps each H2 and its following content in a `<details>` / `<summary>` block.
   - The first H2 in document order gets the `open` attribute; all others are collapsed by default.
   - Idempotent: detects already-wrapped H2s and returns the input unchanged.
   - Uses BeautifulSoup (promoted to a module-level import to satisfy type checking).

2. **Applied helper in `_render_architecture_html`** (`dashboard/routers/code_ui.py`):
   - After `render_markdown(processed)`, the result is now passed through `wrap_h2_sections_collapsible` before being returned.

3. **Chip-strip endpoint** (`dashboard/routers/code.py`):
   - Added `GET /api/projects/{project_id}/code/modules/chips` returning a `code_module_chips.html` fragment.
   - Reuses `parse_modules_from_level1` (same parser as `list_modules`) so chip set and card set always match.
   - The template itself is S03's job; this endpoint is functional once S03 lands.

4. **Tightened mapgen grounding prompt** (`orch/rag/mapgen.py`):
   - Changed `"Write 2–5 concise sentences"` to `"Write 1-3 concise sentences"` on line 63.

## Files changed

| File | Change |
|------|--------|
| `dashboard/utils/markdown.py` | Added `wrap_h2_sections_collapsible`; moved `BeautifulSoup` import to module level |
| `dashboard/routers/code_ui.py` | Added import of `wrap_h2_sections_collapsible`; applied it in `_render_architecture_html` |
| `dashboard/routers/code.py` | Added `list_modules_chips` endpoint at `/modules/chips` |
| `orch/rag/mapgen.py` | One-line edit: "2-5" → "1-3" in `_GROUNDING_TEMPLATE` |

## Test results

- **Typecheck**: `make typecheck` — ✅ Success (no issues in 211 source files)
- **Lint** (changed files only): `uv run ruff check <4 files>` — ✅ All checks passed
- **Unit tests** (full suite): 2247 passed, 2 failed (pre-existing `test_safe_migrate.py` failures unrelated to this step)
  - The 2 failures (`test_apply_refuses_in_agent_context`, `test_rollback_refuses_in_agent_context`) existed before S01 and are unrelated to any code changed here — confirmed by running tests against the pre-S01 commit.

## Preflight gates

| Gate | Result |
|------|--------|
| `make format` | Fixed (`dashboard/utils/markdown.py` reformatted); other files were pre-existing |
| `make typecheck` | ✅ OK |
| `make lint` | ✅ OK (changed files only) |
| `make test-unit` | 2247 passed / 2 failed (pre-existing, unrelated) |

## Blockers

None.

## Notes

- The `mapgen.py` prompt edit uses a plain ASCII hyphen (`1-3`) rather than the en-dash (`1–3`) used in the specification text — the actual string in the file uses standard ASCII, which is the existing pattern in that file.
- The `wrap_h2_sections_collapsible` helper uses a TYPE_CHECKING import guard for `BeautifulSoup` to satisfy mypy, but a runtime import at the module level (for type-checked code, `bs4` is imported via the `else` branch). This is a standard pattern in this codebase.
