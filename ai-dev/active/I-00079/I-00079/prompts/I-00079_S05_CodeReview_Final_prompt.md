# I-00079_S05_CodeReview_Final_prompt

**Work Item**: I-00079 — Empty-state CTA links point to non-existent `/docs/<name>.md` route (404)
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S04

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state.
Allowed: testcontainers via pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` / `make` targets.
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This item adds no migrations and touches no database schema. Flag any migration/schema change as out of scope (CRITICAL).

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00079 --json`.
- `ai-dev/active/I-00079/I-00079_Issue_Design.md` — design document
- All step reports: `ai-dev/active/I-00079/reports/I-00079_S01_*`, `..._S02_*`, `..._S03_*`, `..._S04_*`
- All files in every implementation report's `files_changed` (expected union: `dashboard/templates/pages/project/queue.html`, `dashboard/templates/pages/project/history.html`, `dashboard/templates/pages/project/batches.html`, `dashboard/templates/pages/system/all_active.html`, `dashboard/templates/docs_library.html`, `dashboard/templates/research_library.html`, `tests/dashboard/test_empty_states.py`)
- `dashboard/templates/macros/empty_state.html`, `dashboard/routers/help.py`, `dashboard/routers/system.py` — the macro and the routes the fix targets

## Output Files

- `ai-dev/active/I-00079/reports/I-00079_S05_CodeReview_Final_report.md` — final review report

## Context

Final cross-agent review of all I-00079 work — the whole picture, not individual steps. Per-agent reviews (S02, S04) are done; catch what they couldn't. The change is small (6 `primary_href` string edits + a regression test) — the review burden is correspondingly light, but the integration point (CTA href ↔ `system.py` doc-viewer route ↔ `help.py` map) is exactly where the bug lived, so verify it end to end.

## Read the Design Document FIRST

- `## Acceptance Criteria` (AC1–AC3) — every criterion must be satisfied by the combined work. An AC with no corresponding code or test → CRITICAL.
- `## Description` — the affected-templates table is the checklist of the six call sites.
- `## Regression Prevention` — the templates-wide scan test must exist.
- `## Notes` — pure template + test change; no `make css`; no DB.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint          # ruff + node --check + scripts/check_templates.py
make format        # ruff format --check
```

New violations → CRITICAL (`"category":"conventions"`). If `make` is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. Completeness vs the design

- All six `empty_state(...)` call sites fixed (queue ×2, history, batches, all_active, docs_library, research_library), each with the design's specified `/system/docs/<DocName>` target (anchors `#iw-approve` / `#batches` where the design says).
- `git diff main` shows **only** `primary_href` value changes in those six templates plus the test additions in `tests/dashboard/test_empty_states.py` — nothing else, no styling churn, no `help.py` edit, no Python route edit, no migration.
- No TODO / placeholder / commented-out fragment left behind.

### 2. Cross-cutting integration (the part the per-agent reviews can't fully see)

- **CTA href → `system.py` doc viewer**: for each of the four distinct targets (`IW_AI_Core_CLI_Spec`, `IW_AI_Core_Architecture`, `IW_AI_Core_Daemon_Design`, `implementation/00_INDEX`), confirm it's a valid key in `system.py`'s `_DOC_URL_MAP` (built via `_DOCS_DIR.rglob("*.md")`, key = path under `docs/` with `.md` stripped) — or just run the dashboard `client` fixture and `GET /system/docs/<key>` → 200 for each. The `implementation/00_INDEX` one depends on CR-00044's subdirectory support being present on `main` — verify it (the design assumes it; if it 404s, that's a CRITICAL — the fix would be re-pointing those two CTAs).
- **CTA href ↔ `help.py` `_SLUG_TO_DOC`**: for `queue`/`history`/`batches`/`all_active`, both surfaces point at a real `/system/docs/...` doc; `queue` matches `help.py` exactly (`/system/docs/IW_AI_Core_CLI_Spec#iw-approve`); `history`'s CTA is intentionally `/system/docs/IW_AI_Core_Architecture` per the design (label "How execution works →") — a documented divergence, not a finding. Confirm no `.md` suffix or bare `/docs/` slipped through anywhere.
- **Regression test ↔ macro shape**: the test's href-extraction regex must match what `empty_state.html` actually emits (`<a href="..." class="empty-state__cta-primary">`). If the macro is ever re-ordered, the regex must keep matching — flag if the test is brittle in a way that would silently pass on a future regression.
- **`tests/dashboard/test_empty_states.py`**: existing marker tests intact; new tests cover all six pages with the specific-destination + resolves-to-200 + no-legacy-pattern assertions; the templates-wide scan test is present and would fail if any `/docs/*.md` link target reappeared anywhere under `dashboard/templates/`.

### 3. Architecture / conventions

- Read `dashboard/CLAUDE.md` and `CLAUDE.md`. Routers stay thin (untouched here); Tailwind not affected; Jinja2 `format` filter rule not relevant (no `format` calls touched). No hardcoded ports/URLs/secrets introduced.

### 4. Test coverage (holistic)

- Does the test set pin the *real* invariant — "every empty-state CTA resolves to a 200 doc page and uses the `/system/docs/` form" — rather than the old shape-only "the CTA element exists"? Are assertions semantic and attribute-scoped? Is there a structural guard (templates-wide scan) so this class of bug can't recur unnoticed?

### 5. Security

- No hardcoded secrets/URLs/ports anywhere. (None expected — relative paths only.)

## Test Verification (NON-NEGOTIABLE)

Run the **full** suite:

```bash
make test-unit
make test-integration
uv run pytest tests/dashboard/test_empty_states.py -v
```

Report results accurately. Integration-test failure → CRITICAL.

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| CRITICAL | Missing AC; a CTA still 404s; `/system/docs/implementation/00_INDEX` doesn't resolve; unrelated/material changes outside the six templates + test file; migration sneaked in; integration tests fail; lint/format violation | Must fix |
| HIGH | A CTA points at the wrong doc; a page uncovered by tests; missing templates-wide scan | Must fix |
| MEDIUM (fixable) | Shape-only / weakened test assertion; missing AC3 consistency test; minor convention issue | Should fix |
| MEDIUM (suggestion) / LOW | Optional / informational | — |

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "I-00079",
  "steps_reviewed": ["S01", "S02", "S03", "S04"],
  "verdict": "pass|fail",
  "findings": [
    {"severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW", "category": "completeness|consistency|integration|testing|architecture|security", "file": "path", "line": 0, "description": "...", "suggestion": "...", "cross_cutting": true}
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, Z dashboard passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```

- `verdict`: `pass` only if zero CRITICAL/HIGH and zero MEDIUM (fixable).
- `mandatory_fix_count`: count of CRITICAL + HIGH + MEDIUM (fixable).
- `missing_requirements`: any design requirement with no implementation — each is automatically CRITICAL.
