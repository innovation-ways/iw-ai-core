# CR-00057 — S06 Code Review Report

## Scope reviewed

- Design contract: `ai-dev/active/CR-00057/CR-00057_CR_Design.md`
- Step reports: S01..S05 reports under `ai-dev/active/CR-00057/reports/`
- Changed implementation files in scope:
  - `orch/daemon/project_registry.py`
  - `dashboard/routers/chat.py`
  - `dashboard/static/chat_assistant/chat.js`
  - `projects.toml`
  - `docs/IW_AI_Core_AI_Assistant_Models.md`
  - `CLAUDE.md`
  - `tests/unit/daemon/test_project_registry_ai_assistant.py`
  - `tests/dashboard/test_chat_router.py`
  - `tests/integration/test_project_registry_ai_assistant.py`
  - `tests/integration/test_chat_config_allowlist_intersection.py`

## Validation summary

- ✅ Allowlist regex implemented as specified in backend: `^[a-z0-9._-]+/[A-Za-z0-9._:/-]+$` (`orch/daemon/project_registry.py:36`), including support for `ollama/gemma4:26b`.
- ✅ Router fail-open response shape is correct across all required branches (missing `project_id`, unknown project, missing `ai_assistant`, empty intersection) and tested.
- ✅ Cache key isolation is implemented with per-`project_id` slots and test coverage (`tests/dashboard/test_chat_router.py:716`).
- ✅ Frontend derives project context from `window.location.pathname` using `/project/{id}/` regex (`dashboard/static/chat_assistant/chat.js:44-48`).
- ✅ No template/HTML selector changes were introduced; JS still targets `#chat-assistant-model`.
- ✅ Label-honesty paragraph exists and explicitly states Anthropic provider routing is not `claude-code` runtime (`docs/IW_AI_Core_AI_Assistant_Models.md:133-136`).
- ✅ S01 TDD RED evidence is valid (AttributeError on missing helper) per report.
- ✅ `CLAUDE.md` Quick Navigation updated with one logical row for AI Assistant allowlist docs.

## Findings

### 1) HIGH — Frontend sends `project_id` sentinel as `directory` instead of repo root path

- **Severity**: HIGH
- **File**: `dashboard/static/chat_assistant/chat.js`
- **Line(s)**: `154-158`
- **Layer/agent**: frontend-impl (S03)
- **Description**: The design contract requires `_createSession()` to send `directory` as the project `repo_root` (working directory path). Current implementation sends `directory = projectId` (opaque ID), which does not satisfy the API behavior requirement and can break runtime directory scoping semantics in `opencode` session creation.
- **Suggested fix**: Resolve project ID to repo root before POSTing `/api/chat/sessions` (e.g., expose/consume a trusted server-provided `repo_root` for the current project page, then send that absolute path as `directory`). Keep `project_id` only for `/api/chat/config` query scoping.

### 2) MEDIUM — Missing INFO log for fail-open path when `project_id` is absent

- **Severity**: MEDIUM
- **File**: `dashboard/routers/chat.py`
- **Line(s)**: `362-364`
- **Layer/agent**: api-impl (S02)
- **Description**: For the no-`project_id` branch, endpoint returns full list (correct fail-open), but it does not emit the INFO fallback log requested by the design (“no `project_id` supplied” should be visible operationally).
- **Suggested fix**: Add a single INFO log in the `if not project_key:` branch indicating fail-open/full-list behavior due to absent `project_id`, while keeping happy-path logging non-spammy.

## Quality checks run

- `make lint` → PASS
- `make typecheck` → PASS
- `uv run pytest tests/unit/daemon/test_project_registry_ai_assistant.py tests/dashboard/test_chat_router.py tests/integration/test_project_registry_ai_assistant.py tests/integration/test_chat_config_allowlist_intersection.py -q --no-cov` → PASS (59 passed)

## Verdict

- **NEEDS_FIX** (1 HIGH, 1 MEDIUM)

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "CR-00057",
  "reviewed_agent": "backend-impl, api-impl, frontend-impl, tests-impl, template-impl",
  "verdict": "NEEDS_FIX",
  "mandatory_fix_count": 1,
  "findings": [
    {
      "severity": "HIGH",
      "file": "dashboard/static/chat_assistant/chat.js",
      "lines": "154-158",
      "description": "`directory` is populated with project_id sentinel instead of project repo_root path required by design.",
      "suggested_fix": "Send actual project repo_root path as `directory` when creating session; keep project_id only for config scoping.",
      "layer": "frontend",
      "reviewed_agent": "frontend-impl"
    },
    {
      "severity": "MEDIUM",
      "file": "dashboard/routers/chat.py",
      "lines": "362-364",
      "description": "Fail-open branch for absent project_id does not log INFO fallback as specified.",
      "suggested_fix": "Emit one INFO log for absent project_id fallback branch.",
      "layer": "api",
      "reviewed_agent": "api-impl"
    }
  ],
  "notes": "Core behavior and tests are strong; fix directory wiring contract mismatch before final approval."
}
```
