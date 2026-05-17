# CR-00057_S09_CodeReview_FIX_Final_prompt

**Work Item**: CR-00057 — AI Assistant chat model allowlist (per-project, with Ollama provider)
**Step**: S09
**Agent**: code-review-fix-final-impl

---

## Standard Policy Headers

Standard `⛔ Docker is off-limits` and `⛔ Migrations: agents generate, daemon applies` policies apply.

## Input Files

- `ai-dev/active/CR-00057/reports/CR-00057_S08_CodeReview_Final_report.md` — findings to address
- `ai-dev/active/CR-00057/CR-00057_CR_Design.md`
- All implementation files under `scope.allowed_paths`

## Output Files

- `ai-dev/active/CR-00057/reports/CR-00057_S09_CodeReview_FIX_Final_report.md` — finding-by-finding resolution

## Requirements

1. Address every CRITICAL and HIGH finding from S08. MEDIUM/LOW best-effort.
2. After fixes, run the full per-layer targeted tests (not the QV-gate full suites):

   ```bash
   uv run pytest tests/unit/daemon/test_project_registry_ai_assistant.py \
                 tests/dashboard/test_chat_router.py \
                 tests/integration/test_project_registry_ai_assistant.py \
                 tests/integration/test_chat_config_allowlist_intersection.py -v
   ```

3. Re-run pre-flight gates: `make format` → `make typecheck` → `make lint`.

## Subagent Result Contract

Use the standard code-review-fix-final-impl JSON contract.
