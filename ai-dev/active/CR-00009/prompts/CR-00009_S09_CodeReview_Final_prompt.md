# CR-00009_S09_CodeReview_Final_prompt

**Work Item**: CR-00009 — Chat panel context awareness
**Review Step**: S09 (Final Review)
**Implementation Steps Reviewed**: S01..S08

---

## Input Files

- `ai-dev/active/CR-00009/CR-00009_CR_Design.md`
- All S01..S08 reports under `ai-dev/active/CR-00009/reports/`
- All files changed across S01, S03, S05, S07:
  - `orch/rag/qa.py`
  - `dashboard/routers/code_qa.py`
  - `dashboard/templates/chat/panel.html`
  - `dashboard/templates/project_code.html`
  - `dashboard/templates/fragments/code_module_detail.html`
  - `dashboard/static/chat/panel.js`
  - `dashboard/static/chat/composer.js`
  - `tests/unit/test_qa_engine.py`
  - `tests/integration/test_code_qa_routes.py`

## Output Files

- `ai-dev/active/CR-00009/reports/CR-00009_S09_CodeReview_Final_report.md`

## Context

Final cross-agent review of the complete CR-00009 change set. Per-agent reviews have been done; your job is to catch what they could not: integration seams, end-to-end correctness, and completeness vs. the design document.

## Review Checklist

### 1. Completeness vs Design Document

Go through every AC in the design doc and confirm it is delivered:

- **AC1** (`Chat — Architecture` on no-module view) — verify template + JS produce this on first paint.
- **AC2** (`Chat — <path> (<name>)` on module view) — verify the Option-A data-attr propagation chain: server renders `code_module_detail.html` with `data-module-path` + `data-module-name` on `#code-module-detail` → inline `<script>` at end of fragment mirrors BOTH attrs onto `#code-content-root` and dispatches `iw:code-context-changed` → `syncChatHeader` listens to that event → label text updates. Also verify the architecture-reset listener (`code-components-section` swap or `code-detail-panel` swap with no `#code-module-detail` in the new content) clears both attrs and re-dispatches the event.
- **AC3** (system prompt names module) — verify `_build_system_prompt` emits the module block.
- **AC4** (fallback on empty filtered search) — verify `answer_stream` fires the unfiltered search AND the prompt emits the retrieval note.
- **AC5** (no fallback when filtered yields chunks) — verify the guard condition.
- **AC6** (end-to-end reply references the module) — covered by S16 (qv-browser); not testable here but note it.
- **AC7** (QARequest accepts module_name optional) — verify the Pydantic model + router forwarding.

Any AC without a clear implementation path is a CRITICAL finding + a `missing_requirements` entry.

### 2. Cross-Agent Consistency

- `module_name` naming matches end-to-end: JS `moduleName` → request field `module_name` → `QARequest.module_name` → `answer_stream(..., module_name=...)` → `_build_system_prompt(..., module_name=...)`. Any rename along the chain is CRITICAL.
- The data-attr spelling is consistent: `data-module-name` (kebab-case in HTML, `moduleName` in JS `dataset`). Python never touches this attr directly.

### 3. Integration Points

- Does `syncChatHeader` run before or after `composer.js::syncContextChip`? Order doesn't matter for correctness (they target different elements), but both must listen to `iw:code-context-changed` (the Option-A coordination event). Confirm both fire on module navigation AND on architecture reset.
- **Composer chip side-effect fix**: `composer.js`'s IIFE must gain a `document.body.addEventListener('iw:code-context-changed', syncContextChip);` line. Without it, the composer chip continues to never appear (pre-existing dead read path). Missing this line is CRITICAL — the design doc's Desired Behavior item 6 explicitly requires this side-effect fix.
- Do BOTH `data-module-path` AND `data-module-name` get *cleared* when the user navigates back to the architecture view? A stale `data-module-path` keeps the composer sending the wrong `module_path` to the API — HIGH. A stale `data-module-name` makes the header lie — HIGH.
- Server → fragment → DOM: both `{{ module.path }}` and `{{ module.name }}` must be autoescaped. Any `| safe` on either is CRITICAL.

### 4. Test Coverage (Holistic)

- Are AC3, AC4, AC5, AC7 all covered by at least one passing test?
- Are there any obvious edge cases the per-agent reviews missed? For example: what if `module_path` is set but `module_name` contains a backtick or quote? The template autoescape handles it, but a smoke test with a weird name is cheap insurance.
- Does the integration test confirm streaming still works end-to-end (not just that the spy was called)?

### 5. Architecture Compliance

- No business logic leaked into the router (still thin).
- No DB or LanceDB calls from templates or JS.
- `orch/rag/qa.py` remains the single owner of prompt construction.
- The `dashboard/CLAUDE.md` rule "business logic belongs in `orch/` layer" is respected.

### 6. Security (Cross-Cutting)

- User-controlled `module_name` (originating from server-side Jinja) flows to:
  1. HTML attribute — autoescaped → safe.
  2. JS `dataset.moduleName` → `label.textContent` → safe (no `innerHTML`).
  3. POST body → system prompt string → safe (not used as SQL, path, or shell).
- Confirm none of these paths regress.

### 7. Regression Surface

- Chat send flow (existing CR-00008 behavior) must be untouched: slash menu, image paste chip, SSE streaming, markdown render, Mermaid, citations.
- The composer module chip (`module:<path>`) must still render as before.
- The collapse/expand panel keyboard shortcut (Cmd+\\) must still work.
- Mobile drawer behavior unchanged.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — all green, including new tests.
2. `make test-integration` — all green, including new tests.
3. `uv run ruff check .`
4. `uv run ruff format --check .`
5. `uv run mypy orch/ dashboard/`

Any failure is CRITICAL.

## Severity Levels

Standard. Emphasis on cross-cutting: a rename along the `module_name` chain, a missing autoescape, or a stale `data-module-name` on architecture view are each CRITICAL.

## Review Result Contract

```json
{
  "step": "S09",
  "agent": "code-review-final-impl",
  "work_item": "CR-00009",
  "steps_reviewed": ["S01", "S03", "S05", "S07"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
