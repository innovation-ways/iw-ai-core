# CR-00063_S06_Lint_prompt

**Work Item**: CR-00063 — Restore Chat Message History on Browser Reload
**Step**: S06
**Agent**: qv-gate
**Gate**: lint
**Command**: make lint

---

Run `make lint` and report pass/fail based on exit code.

This gate covers:
- `ruff check` on Python files
- `node --check` on dashboard JS files (including `dashboard/static/chat_assistant/chat.js`)
- `scripts/check_templates.py` for Jinja2 format-filter correctness

Do NOT fix failures — only report. Exit 0 = pass, non-zero = fail.
