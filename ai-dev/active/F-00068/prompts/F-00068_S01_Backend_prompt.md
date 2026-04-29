# F-00068_S01_Backend_prompt

**Work Item**: F-00068 — AI Chat Visual Improvements
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

---

## Input Files

- `ai-dev/active/F-00068/F-00068_Feature_Design.md` — Design doc (§Response Style Instructions, §Canonical Callout Spec)
- `orch/rag/qa.py` — `QAEngine.RENDERING_CAPABILITIES_BLOCK` at line ~188

## Output Files

- `orch/rag/qa.py` — Modified
- `ai-dev/active/F-00068/reports/F-00068_S01_Backend_report.md`

---

## Context

`QAEngine.RENDERING_CAPABILITIES_BLOCK` is the system prompt section that tells the LLM what the chat UI can render. It currently covers Mermaid, D2, tables, and code — but says nothing about callout blocks or structured responses. The LLM therefore produces unstructured prose walls. This step adds callout syntax guidance and structured response instructions to the block.

**The change is additive only** — do not remove or modify the existing Mermaid/D2/table/code lines.

---

## Requirements

### 1. Append callout instructions to `RENDERING_CAPABILITIES_BLOCK`

Locate `RENDERING_CAPABILITIES_BLOCK` in `orch/rag/qa.py` (class attribute on `QAEngine`, around line 188). Append the following text after the existing code block instruction and before `"Do not preface answers..."`:

```python
"- Callouts — use GitHub-style blockquote callouts for special content:\n"
"  > [!NOTE] supplementary context or background that doesn't interrupt main flow\n"
"  > [!TIP] best practice, shortcut, or recommended approach\n"
"  > [!WARNING] non-obvious behavior, footgun, or constraint the reader must not miss\n"
"  > [!DANGER] destructive or irreversible action — use very sparingly\n"
"  The UI renders these as colored admonition blocks. Use [!WARNING] when describing "
"  a non-obvious gotcha. Reserve [!DANGER] for operations that cannot be undone. "
"  Do NOT use [!DANGER] for normal informational notes.\n"
"- Structure — format multi-topic answers with H2 (##) headings. Use bullet lists "
"  for enumerations of 3 or more items. Avoid dense paragraphs when a list would be "
"  clearer. Do not start every answer with a heading — only use headings when the "
"  response covers 2 or more distinct sections.\n\n"
```

### 2. Preserve existing content exactly

The existing block ends with:
```python
"Do not preface answers with disclaimers about being a text-based AI; "
"emit diagrams and code directly in the response. If a diagram would make "
"an architectural relationship clearer than prose, include it proactively.\n\n"
```

This line must remain unchanged and must be the last sentence before the closing parenthesis/quote.

### 3. No other changes to `qa.py`

Do not modify `_build_system_prompt()`, `DIAGRAM_DIRECTIVE_BLOCK`, or any other method. The change is isolated to `RENDERING_CAPABILITIES_BLOCK`.

---

## Project Conventions

- `qa.py` uses Python string literal concatenation for multi-line string constants (no f-strings for static blocks). Match this style.
- Read `orch/CLAUDE.md` for any relevant layer conventions.

## TDD Requirement

1. **RED**: Add `tests/unit/test_qa_system_prompt.py`:
   ```python
   def test_rendering_capabilities_block_includes_callouts():
       """RENDERING_CAPABILITIES_BLOCK mentions callout syntax."""
       assert "[!NOTE]" in QAEngine.RENDERING_CAPABILITIES_BLOCK
       assert "[!WARNING]" in QAEngine.RENDERING_CAPABILITIES_BLOCK

   def test_rendering_capabilities_block_includes_structure_guidance():
       """RENDERING_CAPABILITIES_BLOCK includes heading/list structure advice."""
       block = QAEngine.RENDERING_CAPABILITIES_BLOCK
       assert "H2" in block or "headings" in block.lower()
       assert "bullet" in block.lower() or "list" in block.lower()

   def test_system_prompt_includes_capabilities():
       """_build_system_prompt() includes RENDERING_CAPABILITIES_BLOCK in output."""
       engine = QAEngine.__new__(QAEngine)
       prompt = engine._build_system_prompt("ctx", [], None, None, False, None)
       assert "[!WARNING]" in prompt
   ```

2. **GREEN**: Implement the changes.
3. **REFACTOR**: Confirm no duplicate newlines or spacing issues in the block.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`
4. `make test-unit`

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "F-00068",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["orch/rag/qa.py"],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
