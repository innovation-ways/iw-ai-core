# CR-00044_S05_CodeReview_Final_prompt

**Work Item**: CR-00044 — Markdown viewer for subdirectory docs, sharper per-page help-doc mappings, and favicon route
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S04

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state (`docker kill|stop|rm|restart`, `docker compose up|down|restart`, `docker volume rm|prune`, `docker system prune`, …). Allowed: testcontainers via pytest fixtures, read-only `docker ps|inspect|logs`, `./ai-core.sh` / `make` targets. If your task seems to require a prohibited command, STOP and raise a blocker. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This item touches no migrations. Do not run `alembic upgrade|downgrade|stamp`. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- Runtime step state: `uv run iw item-status CR-00044 --json`.
- `ai-dev/active/CR-00044/CR-00044_CR_Design.md` — design document.
- All implementation step reports: `ai-dev/active/CR-00044/reports/CR-00044_S*_report.md`.
- All per-agent review reports: `ai-dev/active/CR-00044/reports/CR-00044_S*_CodeReview_report.md`.
- All files in the implementation reports' `files_changed` (expected: `dashboard/app.py`, `dashboard/routers/system.py`, `dashboard/routers/help.py`, `dashboard/CLAUDE.md`, possibly `dashboard/templates/pages/system/docs_view.html`, `tests/dashboard/test_system_docs_route.py`, `tests/dashboard/test_help_router.py`, `tests/dashboard/test_favicon.py`).

## Output Files

- `ai-dev/active/CR-00044/reports/CR-00044_S05_CodeReview_Final_report.md` — final review report.

## Context

Final cross-agent review of CR-00044. Per-agent reviews (S02, S04) are done; your job is the holistic picture: does the favicon route + the widened docs viewer + the `_SLUG_TO_DOC` retargeting + the tests fit together and fully satisfy AC1–AC6 with no scope creep?

## Read the Design Document FIRST

Read `## Acceptance Criteria` (AC1–AC6) and `## TDD Approach` in full. Build a matrix: each AC → the code that implements it → the test(s) that cover it. Any AC with no implementation OR no covering test is a CRITICAL finding. Cross-check every TDD-named test file against the union of all `files_changed` arrays — a missing one is CRITICAL.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run `make lint` and `make format` (check-only) on all changed files. Any NEW violation not on `main` → CRITICAL finding, `category: conventions`. If `make` is unavailable, STOP and raise a blocker.

## Review Checklist (CR-specific)

1. **Completeness vs design** — favicon route present and wired on the app; `{doc_path:path}` route with recursive allow-list + curated CLAUDE.md set (incl. `orch/rag/CLAUDE.md`) + 4-part traversal guard; `_SLUG_TO_DOC` retargeted exactly as the design says (`code`→RAG CLAUDE.md, `item_detail`/`research`/`search`→Dashboard_Design, `projects` unchanged, fallback unchanged); H1-derived title; `dashboard/CLAUDE.md` note updated.
2. **Security (cross-cutting)** — re-trace the traversal guard end-to-end as if attacking it. `..`, leading `/`, resolved-path escape, non-`.md`, allow-list miss must each 404. The `:path` converter is the risk surface; confirm no combination reaches `read_text` on a file outside `docs/` or the curated set. No file content leaks in 404 bodies.
3. **Anchors** — every `#fragment` in `_SLUG_TO_DOC` must resolve to a real `toc` heading id in its target doc. Verify by rendering each target through the markdown call (or via a locally running dashboard) — don't take it on faith. A dangling anchor is MEDIUM (fixable).
4. **Consistency** — naming/style consistent across `app.py`/`system.py`/`help.py`; no duplicated allow-list logic that should be shared; the docs-view template still receives its title under the expected key.
5. **No scope creep** — no new dependency; `_SLUG_TO_DOC` not externalised to a config file; the unmapped-slug fallback unchanged; no help-fragment prose edits; no new documentation content; no unrelated file churn. Anything beyond the File Manifest is a finding.
6. **Test coverage holistic** — AC1 (subdir + RAG CLAUDE.md), AC2 (flat-form regression), AC3 (all five rejection classes), AC4 (the four retargeted slugs + `projects`, plus the "no `/docs/IW_AI_Core` / bare `/orch/` href" regression that must not false-positive on `/system/docs/orch/rag/CLAUDE.md`), AC5 (favicon 200 + content-type + bytes), AC6 (H1 title) — all covered.

## Test Verification (NON-NEGOTIABLE)

Run the **full** test suite (`make test-unit` and `make test-integration`). Integration includes `tests/dashboard/`. Any failure → CRITICAL finding. Report results accurately.

## Severity Levels & Result Contract

Standard severities. `verdict: pass` only if zero CRITICAL/HIGH/MEDIUM_FIXABLE findings and zero missing requirements.

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "CR-00044",
  "steps_reviewed": ["S01", "S02", "S03", "S04"],
  "verdict": "pass|fail",
  "findings": [{"severity": "...", "category": "completeness|consistency|integration|testing|architecture|security", "file": "...", "line": 0, "description": "...", "suggestion": "...", "cross_cutting": false}],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
