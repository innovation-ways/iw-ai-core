# I-00089_S03_Tests_prompt

**Work Item**: I-00089 -- AI Assistant panel — in-header collapse button is unusable in both states
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

You MUST NOT run docker compose / kill / stop / restart against running
infrastructure. Testcontainer fixtures spun up by pytest are exempt.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run alembic upgrade/downgrade/stamp. This step adds dashboard
tests, not migrations — alembic is not needed.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00089 --json` for current step + previous-step report paths.
- `ai-dev/active/I-00089/I-00089_Issue_Design.md` -- design doc (read the "Test to Reproduce" section — it contains the canonical reference tests)
- `ai-dev/active/I-00089/reports/I-00089_S01_Frontend_report.md` -- S01's report (especially the `notes` field that says which class-marker variant was chosen)
- `ai-dev/active/I-00089/reports/I-00089_S02_CodeReview_Frontend_report.md` -- S02's review (for any findings the implementation must already address)
- `dashboard/templates/chat_assistant/panel.html` -- as modified by S01
- `dashboard/static/chat_assistant/chat.css` -- as modified by S01
- `tests/dashboard/conftest.py` -- registers the `client` fixture
- `tests/dashboard/` existing tests -- reference for test style and imports
- `CLAUDE.md` and `dashboard/CLAUDE.md` -- project conventions

## Output Files

- `tests/dashboard/test_chat_assistant_header.py` -- NEW test file
- `ai-dev/active/I-00089/reports/I-00089_S03_Tests_report.md` -- Step report

## Context

You are writing the reproduction tests for I-00089. The Issue_Design document at `ai-dev/active/I-00089/I-00089_Issue_Design.md` contains the canonical reference implementation in its "Test to Reproduce" section — you should follow that closely. The Functional spec is in the same folder.

**Critical context**: the fix has already landed (S01) and been reviewed (S02). Your tests are written AFTER the implementation but must still demonstrate that they would have caught the bug pre-fix. Do this by reasoning carefully about each assertion: each assertion must target a specific change that S01 made. If you removed S01's change, the test must fail.

**Test-file location** — Regression tests for dashboard rendering MUST live under `tests/dashboard/`. This directory's `conftest.py` re-exports `db_session` / `test_project` from `tests/integration/conftest.py`; placing the file under `tests/unit/` or `tests/integration/` does not give the same fixture topology. Use exactly:

```
tests/dashboard/test_chat_assistant_header.py
```

**`client` fixture — define it inline.** There is NO project-wide `client` fixture in `tests/dashboard/conftest.py`. Every existing dashboard test file declares its own inline `client` fixture that overrides `get_db` to use the test `db_session`. Copy this canonical pattern verbatim from `tests/dashboard/test_chat_panel_default_collapsed.py:25-42`:

```python
import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from dashboard.app import create_app
from dashboard.dependencies import get_db


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:

        def override_get_db() -> Session:
            return db_session

        app = create_app()
        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original
        app.dependency_overrides.clear()
```

Skipping this fixture or assuming `client` is auto-injected will fail collection with `fixture 'client' not found`.

## Requirements

### 1. Create the test file with TWO reproduction tests

Create `tests/dashboard/test_chat_assistant_header.py`. Base it on the canonical version from the Issue_Design's "Test to Reproduce" section — copy the structure, refine the assertions to exactly match the class-marker variant that S01 chose (see S01's report `notes` field).

The two tests are:

1. **`test_i00089_bug_a_collapse_button_hidden_when_collapsed`** — asserts the inline `<style>` block in the rendered panel HTML names `#chat-assistant-collapse-btn` inside its `data-collapsed="true"` `display: none` selector group.
2. **`test_i00089_bug_b_collapse_button_has_discoverable_affordance`** — asserts the `<button id="chat-assistant-collapse-btn">` opening tag carries (a) a `title` attribute, and (b) a distinguishing class marker (`chat-assistant-collapse-btn-distinct` OR a Tailwind border utility).

### 2. CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed. But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "permissions" in data` (shape only)
- GOOD: `assert "brands:manage" in permissions` (semantic — verifies specific expected value)
- GOOD: `assert "*" not in permissions` (semantic — verifies unwanted value is absent)

For this incident specifically:

- BAD: `assert "chat-assistant-collapse-btn" in html` — the literal token "chat-assistant-collapse-btn" also appears inside the JS source served at `/static/chat_assistant/chat.js` and in HTML comments. This is a shape check that can false-pass.
- GOOD: `re.search(r'<button[^>]*id="chat-assistant-collapse-btn"[^>]*>', html)` — attribute-scoped match on the actual element tag.
- BAD: `assert "title" in button_tag` — matches "title" anywhere in the tag including inside the `aria-label` value or any other attribute name containing those letters.
- GOOD: `re.search(r'\btitle="[^"]+"', button_tag)` — matches the `title="..."` attribute as a word-boundary-anchored pattern.
- BAD: `assert "display: none" in html` — multiple CSS rules in the page use `display:none`.
- GOOD: `re.search(r'#chat-assistant-panel\[data-collapsed="true"\][^{]*#chat-assistant-collapse-btn', html, re.DOTALL)` — matches the specific selector chain that the fix introduces.

The CLAUDE.md "Assertion scoping for CSS class names" note (I-00067) applies here: use attribute-scoped substring matching rather than bare-substring tokens.

### 3. Adaptation to S01's chosen class-marker variant

S01 chose ONE of:

- **Variant A**: added a custom class `chat-assistant-collapse-btn-distinct` (plus a CSS rule in `chat.css`).
- **Variant B**: added Tailwind utility classes like `border-l border-border pl-1`.

Read S01's report `notes` field to learn which variant was used, then write the Bug B assertion to accept ONLY that variant — make the assertion semantic and tight, not a permissive "any of several markers" check.

For Variant A:

```python
assert "chat-assistant-collapse-btn-distinct" in button_tag, (
    "Expected the collapse button to carry the "
    "'chat-assistant-collapse-btn-distinct' class marker (variant A from S01)."
)
```

For Variant B (example with `border-l`):

```python
class_attr_match = re.search(r'\bclass="([^"]*)"', button_tag)
assert class_attr_match, "Collapse button missing class attribute."
classes = class_attr_match.group(1).split()
assert "border-l" in classes, (
    "Expected the collapse button to carry Tailwind 'border-l' utility class "
    "(variant B from S01)."
)
```

Pick exactly ONE of the two assertion bodies based on S01's choice.

### 4. Run the new tests targeted (not the full suite)

After writing the file:

```bash
uv run pytest tests/dashboard/test_chat_assistant_header.py -v --no-cov
```

Both tests MUST pass GREEN — because S01 has already landed the fix. Capture the pass output for your report. Do NOT run `make test-integration` or `make test-unit` — those are S09/S10's job (see I-00073/S03 post-mortem).

### 5. No manual revert-and-retest

You MUST NOT `git checkout HEAD~1 -- dashboard/templates/chat_assistant/panel.html`, `git stash`, or otherwise revert the fix to "prove RED". RED-evidence for this incident is established in the design document (the bug was visually reproduced via playwright-cli during incident intake — see `evidences/pre/`). Reverting source files at runtime is thrash-prone and explicitly forbidden by the skill template.

### 6. Pre-flight quality gates

Before reporting completion:

1. `make format` — auto-fix Python formatting on your new test file.
2. `make typecheck` — must report zero errors involving your new file.
3. `make lint` — must report zero errors.

Record the result of each in the `preflight` object.

## Project Conventions

Read `CLAUDE.md` and `dashboard/CLAUDE.md`. Key tests rules:

- Dashboard tests live under `tests/dashboard/` and use the `client` fixture from `tests/dashboard/conftest.py`.
- Attribute-scoped substring matching for CSS class assertions (CLAUDE.md "Assertion scoping for CSS class names", I-00067).
- Tests must not connect to the live DB on port 5433 — dashboard tests use FastAPI's TestClient against the in-process app and never need a real DB.

## TDD Requirement

This step IS the TDD test-writing step. The reproduction tests document the expected behaviour. For a `tests-impl` step (per the skill template), `tdd_red_evidence` is `n/a` — `tests-impl` adds coverage AFTER implementation exists and is not RED-first by nature.

## Test Verification (NON-NEGOTIABLE)

Run ONLY the new file:

```bash
uv run pytest tests/dashboard/test_chat_assistant_header.py -v --no-cov
```

Both tests MUST pass. Do NOT run `make test-integration` or `make test-unit`.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00089",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/dashboard/test_chat_assistant_header.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "2 passed, 0 failed",
  "tdd_red_evidence": "n/a — dedicated coverage step (tests-impl); RED reproduced at incident intake via playwright-cli (see ai-dev/active/I-00089/evidences/pre/)",
  "blockers": [],
  "notes": "S01 variant chosen: {A:custom-class | B:Tailwind-border}; Bug B assertion targets exactly that variant."
}
```
