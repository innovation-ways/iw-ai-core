# CR-00064_S07_Lint_prompt

**Work Item**: CR-00064 — Clear Chat History Button in AI Assistant
**Step**: S07
**Agent**: qv-gate
**Gate**: lint
**Command**: make lint

---

Run `make lint` and report pass/fail based on exit code.

This gate covers:
- `ruff check` on Python files (including `dashboard/routers/chat.py`)
- `node --check` on dashboard JS files (including `dashboard/static/chat_assistant/chat.js`)
- `scripts/check_templates.py` for Jinja2 format-filter correctness

Do NOT fix failures — only report. Exit 0 = pass, non-zero = fail.
