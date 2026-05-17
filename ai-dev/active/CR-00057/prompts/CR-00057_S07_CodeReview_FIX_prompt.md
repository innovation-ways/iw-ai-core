# CR-00057_S07_CodeReview_FIX_prompt

**Work Item**: CR-00057 — AI Assistant chat model allowlist (per-project, with Ollama provider)
**Step**: S07
**Agent**: code-review-fix-impl

---

## Standard Policy Headers

Standard `⛔ Docker is off-limits` and `⛔ Migrations: agents generate, daemon applies` policies apply.

## Input Files

- `ai-dev/active/CR-00057/reports/CR-00057_S06_CodeReview_report.md` — findings to address
- `ai-dev/active/CR-00057/CR-00057_CR_Design.md`
- Implementation files under `scope.allowed_paths` in `workflow-manifest.json`

## Output Files

- `ai-dev/active/CR-00057/reports/CR-00057_S07_CodeReview_FIX_report.md` — finding-by-finding resolution
- Modified files: those that the S06 findings touch

## Requirements

1. Address every CRITICAL and HIGH finding from S06. MEDIUM/LOW are best-effort — fix when fast, defer with justification otherwise.
2. After fixes, re-run the targeted tests for any file you touched:

   ```bash
   uv run pytest <path/to/touched/test_file.py> -v
   ```

   Do NOT run `make test-unit` or `make test-integration` — the QV gates handle that.

3. Re-run pre-flight gates after fixes: `make format` → `make typecheck` → `make lint`.

## Subagent Result Contract

Use the standard code-review-fix-impl JSON contract. For each S06 finding, report `status: resolved | deferred | wont_fix` with reason and `file:line` of the fix.
