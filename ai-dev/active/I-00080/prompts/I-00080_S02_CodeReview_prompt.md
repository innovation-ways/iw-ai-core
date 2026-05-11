# I-00080_S02_CodeReview_prompt

**Work Item**: I-00080 — Docs-page document rendering: server-side Mermaid render is uncached and dark-mode-unaware
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state.
Allowed: testcontainers via pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` / `make` targets.
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This item adds no migrations. If S01 added an alembic file, that is a CRITICAL finding (out of scope).

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00080 --json`.
- `ai-dev/active/I-00080/I-00080_Issue_Design.md` — design (read **Root Cause Analysis**, **AC1**, **TDD Approach** in full first).
- `ai-dev/active/I-00080/reports/I-00080_S01_backend-impl_report.md` — S01 report.
- All files in S01's `files_changed` (expected: `dashboard/utils/markdown.py` and `tests/unit/test_markdown_mermaid_legibility.py`).

## Output Files

- `ai-dev/active/I-00080/reports/I-00080_S02_CodeReview_report.md` — review report.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run on the files in S01's `files_changed`, report only (fix nothing):
```bash
make lint
make format-check
```
Any NEW violation in the changed files (not present on `main` before S01) → a CRITICAL finding with `"category":"conventions"`, file, line, exact code+message.

## Review Checklist

1. **Does S01 actually fix the dark-mode legibility?** The `mmdc` render must now produce a self-contained, theme-neutral SVG: light/neutral diagram background, **dark legible label/edge colours** that cannot inherit a near-white page `color`. Verify the approach (explicit `-t`/`-c` theme/config and/or a coloured wrapper `<div>` and/or a scoped `<style>` — design Requirement 1). If the wrapper `<div>` alone is relied on but the SVG's embedded `.nodeLabel` style would out-specify it, that's a HIGH finding (the fix wouldn't hold).
2. **Fallbacks intact?** `_render_mermaid_kroki` still called when `mmdc` fails; the raw-`<pre>` fallback still returned when both fail (`_replace` returning `match.group(0)`); the kroki SVG gets the same legibility wrapper.
3. **No regressions to the markdown pipeline** — `render_markdown` unchanged; `render_markdown_with_callouts` signature unchanged (`render_mermaid: bool = True` preserved); callout-blockquote conversion unaffected; `_MERMAID_CODE_RE` matching unchanged.
4. **No module-level dict cache added in `markdown.py`** (caching is S05's job, version-keyed). If S01 added one, MEDIUM_FIXABLE (it would leak across docs / not be version-aware).
5. **Test quality** — the `tests/unit/` legibility test asserts a **specific** enforced colour token (not "a `style=` exists"), skips cleanly when `mmdc` is unavailable, and is deterministic.
6. **Conventions / security** — matches `CLAUDE.md` + `dashboard/CLAUDE.md`; no new long subprocess timeouts; no hardcoded paths beyond what's already in `markdown.py`; no secrets.

## Test Verification (NON-NEGOTIABLE)

Run the targeted unit tests for `markdown.py` (e.g. `uv run pytest tests/unit/ -k markdown -v`). Report results accurately. Do not run the full integration suite.

## Severity Levels & Result Contract

Use the standard severities (CRITICAL / HIGH / MEDIUM_FIXABLE / MEDIUM_SUGGESTION / LOW). `verdict: pass` only if zero CRITICAL/HIGH/MEDIUM_FIXABLE.

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00080",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [{"severity": "...", "category": "...", "file": "...", "line": 0, "description": "...", "suggestion": "..."}],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
