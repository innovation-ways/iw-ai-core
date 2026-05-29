# I-00120_S06_CodeReview_prompt

**Work Item**: I-00120 — Codex usage chips silently show 0% when the opencode OAuth token is expired or invalid
**Step Being Reviewed**: S05 (tests-impl)
**Review Step**: S06

---

## ⛔ Docker is off-limits

Do not run any command that changes Docker state. Testcontainer fixtures, read-only introspection, and
`./ai-core.sh` / `make` targets are allowed. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

No migrations in this item.

## Input Files

- Runtime step state: `uv run iw item-status I-00120 --json`.
- `ai-dev/active/I-00120/I-00120_Issue_Design.md` — design doc (read **TDD Approach** — note every named test).
- `ai-dev/work/I-00120/reports/I-00120_S05_Tests_report.md`.
- Files in S05's `files_changed` (`tests/unit/test_llm_usage.py`, `tests/dashboard/test_usage_fragment.py`).

## Output Files

- `ai-dev/work/I-00120/reports/I-00120_S06_CodeReview_report.md` — review report.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```
New violations in changed files → CRITICAL (`category: conventions`).

## Review Checklist (item-specific)

1. **Reproduction test present and correct** — `test_codex_usage_expired_token_reports_expired_status`
   exists, would FAIL against pre-fix code (missing `status` key) and PASS now. If the design's named
   test files are missing from `files_changed`, that is CRITICAL.
2. **Semantic correctness, not shape** — every status test asserts a SPECIFIC value
   (`== "expired"`, `== "unauthenticated"`, `== "error"`, `== "ok"`), NOT merely `"status" in result`.
   Rendering tests assert the SPECIFIC warning phrase per state and assert the **absence** of the
   normal bars in a warning state and the **absence** of the warning in the `ok` state. Flag any
   shape-only assertion as a HIGH finding.
3. **All four statuses covered** plus both `error` triggers (non-401 HTTP + generic exception) and the
   401→`expired` path. `_oauth_is_expired` boundary table (past/future/missing/non-numeric, epoch-ms)
   is tested.
4. **No network** — tests monkeypatch `_load_openai_oauth` / the remote call / `httpx`; nothing hits a
   live endpoint. Dashboard tests use a file-local `TestClient` fixture under `tests/dashboard/`.
5. **Isolation & determinism** — no reliance on the real `~/.local/share/opencode/auth.json`; no
   dependence on wall-clock beyond what `_oauth_is_expired` needs (and that is controlled via the
   `expires` input).
6. **CSS assertion scoping** — warning-class assertions are attribute/phrase-scoped, not bare ambiguous
   substrings (design doc note + I-00067).
7. **No live-DB / no `importlib.reload(orch.config)`** — per CLAUDE.md hard rules.

## Severity Levels

CRITICAL / HIGH / MEDIUM_FIXABLE / MEDIUM_SUGGESTION / LOW. `verdict: pass` only when zero
CRITICAL + HIGH + MEDIUM_FIXABLE.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/unit/test_llm_usage.py -k codex -v
uv run pytest tests/dashboard/test_usage_fragment.py -v
```
Report results accurately.

## Review Result Contract

```json
{
  "step": "S06",
  "agent": "CodeReview",
  "work_item": "I-00120",
  "step_reviewed": "S05",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
