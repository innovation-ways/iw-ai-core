# F-00068_S05_Tests_prompt

**Work Item**: F-00068 — AI Chat Visual Improvements
**Step**: S05
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

---

## Input Files

- `ai-dev/active/F-00068/F-00068_Feature_Design.md` — §Boundary Behavior, §Invariants, §TDD Approach
- `orch/rag/qa.py`
- `dashboard/templates/chat/message.html`
- `tests/conftest.py`, `tests/CLAUDE.md`

## Output Files

- `tests/unit/test_qa_system_prompt.py` — New or extended
- `tests/dashboard/test_chat_message.py` — New
- `ai-dev/active/F-00068/reports/F-00068_S05_Tests_report.md`

---

## Requirements

### 1. System prompt unit tests (`tests/unit/test_qa_system_prompt.py`)

```python
from orch.rag.qa import QAEngine

def test_rendering_capabilities_includes_callout_note():
    assert "[!NOTE]" in QAEngine.RENDERING_CAPABILITIES_BLOCK

def test_rendering_capabilities_includes_callout_warning():
    assert "[!WARNING]" in QAEngine.RENDERING_CAPABILITIES_BLOCK

def test_rendering_capabilities_includes_callout_danger():
    assert "[!DANGER]" in QAEngine.RENDERING_CAPABILITIES_BLOCK

def test_rendering_capabilities_includes_structure_guidance():
    block = QAEngine.RENDERING_CAPABILITIES_BLOCK
    # Must mention headings or H2 for multi-section structure
    assert "H2" in block or "heading" in block.lower()

def test_rendering_capabilities_includes_list_guidance():
    block = QAEngine.RENDERING_CAPABILITIES_BLOCK
    assert "bullet" in block.lower() or "list" in block.lower()

def test_build_system_prompt_includes_capabilities_block():
    """Capabilities block appears in actual system prompt output."""
    engine = QAEngine.__new__(QAEngine)
    prompt = engine._build_system_prompt(
        context_doc_content="ctx",
        chunks=[],
        module_path=None,
        module_name=None,
        fallback_triggered=False,
        context_chips=None,
    )
    assert "[!WARNING]" in prompt

def test_rendering_capabilities_preserves_mermaid_mention():
    """Existing Mermaid instruction not removed by S01 changes."""
    assert "mermaid" in QAEngine.RENDERING_CAPABILITIES_BLOCK.lower()

def test_rendering_capabilities_preserves_d2_mention():
    """Existing D2 instruction not removed by S01 changes."""
    assert "d2" in QAEngine.RENDERING_CAPABILITIES_BLOCK.lower()
```

### 2. Dashboard template test (`tests/dashboard/test_chat_message.py`)

```python
def test_chat_message_template_has_body_class(test_client):
    """chat-message-body class present in message template."""
    # Render the message.html template with role=assistant and content
    # Assert response HTML contains class="chat-message-body"
    # Use existing dashboard test client pattern from tests/dashboard/
```

Read `tests/dashboard/` for existing test patterns and how the dashboard test client is set up.

### 3. Boundary behavior tests

Cover each row from §Boundary Behavior in the design doc:

```python
def test_unknown_callout_type_in_block():
    """RENDERING_CAPABILITIES_BLOCK does not claim to support [!CUSTOM]."""
    # This is a negative test — verify only note/tip/warning/danger/important are listed

def test_capabilities_block_does_not_suggest_every_answer_needs_heading():
    """Instruction says NOT to start every answer with a heading."""
    block = QAEngine.RENDERING_CAPABILITIES_BLOCK
    # Verify the block contains guidance against overusing headings
    assert "not" in block.lower() or "only" in block.lower()
```

---

## CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

Tests that only check output *shape* (non-empty, has a key, is a string) can pass even when the behavior is wrong. Every assertion in this step must check **specific values**:

- BAD: `assert result is not None`
- BAD: `assert "callout" in block` (only checks that the word appears anywhere)
- GOOD: `assert "[!NOTE]" in QAEngine.RENDERING_CAPABILITIES_BLOCK` (verifies the exact token)
- GOOD: `assert "[!WARNING]" in prompt` (verifies the specific string in the built prompt)
- GOOD: `assert "mermaid" in QAEngine.RENDERING_CAPABILITIES_BLOCK.lower()` (verifies the specific preserved term)

If a test passes whether the bug is present or not, it is not a useful test.

## Project Conventions

Read `tests/CLAUDE.md`. Key rules:
- NEVER connect to live DB
- Use testcontainers for integration tests
- Unit tests in `tests/unit/`, dashboard tests in `tests/dashboard/`

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`
4. `make test-unit`

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "tests-impl",
  "work_item": "F-00068",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_qa_system_prompt.py",
    "tests/dashboard/test_chat_message.py"
  ],
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
