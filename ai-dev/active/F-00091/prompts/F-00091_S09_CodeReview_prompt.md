# F-00091_S09_CodeReview_prompt

**Work Item**: F-00091 -- AI Assistant — Decouple from page URL, persist per-project tab, and surface an always-visible context-usage progress bar
**Steps Being Reviewed**: S01 (api-impl), S02 (frontend-impl), S03 (frontend-impl), S04 (database-impl), S06 (backend-impl), S07 (frontend-impl), S08 (tests-impl)
**Review Step**: S09

---

## ⛔ Docker is off-limits

Standard policy. This step touches no Docker.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. S04's migration was already validated by S05 (`make migration-check`). Re-verify the file passes the gate but do not re-apply it manually.

## Input Files

- **Runtime step state** — `uv run iw item-status F-00091 --json`
- `ai-dev/active/F-00091/F-00091_Feature_Design.md` — Design doc (read AC1–AC4 and Invariants 1–7 in full)
- `ai-dev/active/F-00091/F-00091_Functional.md` — Functional summary (sanity-check it matches what shipped)
- All seven impl reports under `ai-dev/work/F-00091/reports/`:
  - `F-00091_S01_API_report.md`
  - `F-00091_S02_Frontend_report.md`
  - `F-00091_S03_Frontend_report.md`
  - `F-00091_S04_Database_report.md`
  - `F-00091_S06_Backend_report.md`
  - `F-00091_S07_Frontend_report.md`
  - `F-00091_S08_Tests_report.md`
- All files listed in each report's `files_changed`

## Output Files

- `ai-dev/work/F-00091/reports/F-00091_S09_CodeReview_report.md`

## Context

You are reviewing SEVEN implementation steps in a single pass. They share one cohesive code locality (`dashboard/static/chat_assistant/**`, `dashboard/routers/chat.py`, `orch/chat/context_usage.py`, one small migration). Per-step reviews would duplicate work.

Read the design doc BEFORE running any gate. Read all seven impl reports. Then review every file in their combined `files_changed`.

## Read the Design Document FIRST

The four Acceptance Criteria and seven Invariants are the anchor. Carry them into the checklist below.

Key TDD/scope requirements to verify by path:

- `dashboard/routers/chat.py` MUST appear in S01 and S06 `files_changed`. (S01 adds endpoint; S06 modifies `get_tab`.)
- `tests/dashboard/test_api_chat_projects.py` MUST appear in S01.
- `dashboard/templates/chat_assistant/panel.html` MUST appear in S02.
- `dashboard/static/chat_assistant/chat.js` MUST appear in S02, S03, AND S07.
- `dashboard/static/chat_assistant/chat.css` MUST appear in S02 AND S07.
- `tests/dashboard/test_assistant_project_decoupling.py` MUST appear in S02.
- A test file matching `*active_tab_restoration*` or `*active_tab_storage*` MUST appear in S03.
- `orch/db/migrations/versions/` MUST contain ONE new file from S04.
- `tests/integration/test_alembic_chat_context_backfill.py` MUST appear in S04.
- `orch/chat/context_usage.py` MUST appear in S06.
- `tests/unit/test_context_usage_status.py` AND `tests/dashboard/test_chat_tabs_status_payload.py` MUST appear in S06.
- `dashboard/templates/chat_assistant/composer.html` MUST appear in S07.
- `tests/dashboard/test_context_pct_progress_bar.py` MUST appear in S07.
- Three new test files MUST appear in S08 (cross-step coverage).

Any missing or forbidden path → CRITICAL.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading any code, run on all changed files:

```bash
make lint
make format-check
```

NEW violations (not pre-existing on `main`) in the changed files → each is a CRITICAL finding (`category: conventions`, exact code + message). Do not fix; report only.

## Review Checklist

### 1. S01 — `/api/chat/projects` endpoint

- Endpoint returns `{"projects": [...]}` exactly per Scope → S01.
- ONLY `enabled = true` rows appear (Invariant 4).
- Sorted alphabetically by `display_name` (case-insensitive).
- Empty list → HTTP 200 with `{"projects": []}`, not 404.
- Same router prefix and auth posture as the rest of `dashboard/routers/chat.py`.
- TDD RED evidence present and plausible.

### 2. S02 — Project selector & URL decoupling

- `<select id="chat-assistant-project-select">` is in `panel.html` and hides correctly when the panel is collapsed.
- A visually-hidden span retains `id="chat-assistant-title"` (back-compat).
- `chat.js` contains `_assistantProjectId()` / `_setAssistantProjectId()` / `_seedAssistantProjectId()` / `_loadAssistantProjects()` exactly as the prompt specified.
- Per Invariant 1: the symbol `_currentProjectId` does NOT appear in `chat.js` anywhere. Grep to confirm.
- The ONLY `window.location.pathname` reference inside `chat.js` is in `_seedAssistantProjectId` (one-time seed). Any other reference is a CRITICAL finding.
- Per Invariant 2: a single page load reads the project id consistently (no race where `_assistantProjectId()` returns different values on different reads).
- localStorage writes are wrapped in try/catch (Boundary row 6).
- The dropdown change handler re-bootstraps tabs WITHOUT a full page reload.
- Empty-projects state: dropdown disabled with placeholder "No projects available", composer disabled.

### 3. S03 — Per-project active-tab restoration

- `_activeTabKey(projectId)` returns `'iw-chat-active-tab:' + projectId` exactly (colon, not dash — Invariant 6). Grep to confirm.
- Every old sessionStorage call to `iw-chat-active-tab-...` is replaced or removed.
- Stale-pointer cleanup: a pointer that does not match any returned tab is removed from localStorage.
- localStorage access is try/catch wrapped.
- The change to `_browserTabId` is documented (either deleted with a one-line comment, or left untouched with a TODO comment).

### 4. S04 — Alembic data migration

- File lives in `orch/db/migrations/versions/` with a slug containing `f_00091`.
- `upgrade()` uses `WHERE context_window_tokens IS NULL` (idempotent, Invariant 5).
- `downgrade()` only reverts rows the upgrade set; does NOT delete rows.
- Each (cli_tool, model, window_tokens) tuple has a citation in the file's docstring or an adjacent comment.
- `make migration-check` passed in S04's report.
- The integration test `tests/integration/test_alembic_chat_context_backfill.py` covers BOTH the NULL-only update path AND the no-overwrite-of-existing-value path AND the downgrade round-trip.

### 5. S06 — Context-usage payload extension

- `resolve_context_usage(...)` (or the two split functions) returns `ContextUsage` with the documented dataclass shape.
- Three statuses are exhaustive: `known`, `unknown_window`, `unknown_runtime`. No fourth string. No `Optional[Literal[...]]` returning `None`.
- The `get_tab` route now ALWAYS emits `context_pct_status`, `used_tokens`, `window_tokens`, `context_pct_reason`. The pre-existing `context_pct` field is still emitted (for back-compat).
- Per Invariant 7: `status == "known"` IFF all three numeric fields are populated.
- The outer `with contextlib.suppress(Exception):` defensive wrapper still exists at the call-site so the route never 500s due to a resolver bug.
- Six TDD tests (three statuses × two runtimes) are present and pass.

### 6. S07 — Progress-bar UI

- `composer.html` markup matches the spec (bar + fill + label children, role, aria-label).
- The element NEVER carries the Tailwind `hidden` class; per Invariant 3, the only place `display: none` is applied is when `_activeTabId === null` (no active tab).
- New CSS classes are appended to `chat_assistant/chat.css`, NOT to `styles.css`.
- `_applyContextPct` now takes the FULL payload (`{ pct, used_tokens, window_tokens, status, reason }`), not just a number.
- Color thresholds: green <70%, amber 70–89%, red ≥90%. Confirm the class-toggle logic matches.
- Unknown state renders `—%` label + striped/greyed fill + tooltip with the server-provided reason.
- Token-formatting helper `_formatTokenCount` exists and produces `120k` / `1.2M` style output.

### 7. S08 — Cross-step tests

- The three new test files are present and pass.
- Every Boundary Behavior table row from the design has at least one automated test, OR is documented as "covered by S19 browser verification" in the S08 report.
- Tests follow the IW AI Core assertion-strength rules from `skills/iw-ai-core-testing/SKILL.md`.

### 8. Functional doc sanity

- `F-00091_Functional.md` matches what shipped. The "What Changed" bullets describe behaviour the implementation actually exhibits, not a parallel universe.
- The functional doc remains <500 words and has no file paths / class names / fenced code blocks.

### 9. Invariant cross-check

Confirm by grep / read:

- I1: `_currentProjectId` is absent from `chat.js`.
- I2: only one localStorage read for `iw-chat-assistant-project` per request lifecycle.
- I3: no `display:none` for `#chat-assistant-context-pct` while an active tab exists.
- I4: `/api/chat/projects` filters by `enabled=true`.
- I5: migration `upgrade()` includes `WHERE … IS NULL`.
- I6: `'iw-chat-active-tab:' + projectId` exact key shape.
- I7: status `"known"` ↔ all three numeric fields populated.

## Categorisation

Use the standard severity scale:

- **CRITICAL** — violates an Invariant or AC, breaks a security/scope rule, or is a regression of an existing feature.
- **HIGH** — clear correctness or maintenance bug, missing TDD evidence on a Backend step, broken contract.
- **MEDIUM** — convention violation, weak test, minor accessibility miss.
- **LOW** — polish / nit / opportunistic improvement.

## Subagent Result Contract

```json
{
  "step": "S09",
  "agent": "code-review-impl",
  "work_item": "F-00091",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/work/F-00091/reports/F-00091_S09_CodeReview_report.md"
  ],
  "preflight": {
    "format": "ok|skipped:review-only",
    "typecheck": "ok|skipped:review-only",
    "lint": "ok|skipped:review-only"
  },
  "tests_passed": true,
  "test_summary": "review-only step; no tests run",
  "tdd_red_evidence": "n/a — review step",
  "findings": [
    {"severity": "CRITICAL|HIGH|MEDIUM|LOW", "category": "...", "path": "...", "summary": "..."}
  ],
  "blockers": [],
  "notes": ""
}
```
