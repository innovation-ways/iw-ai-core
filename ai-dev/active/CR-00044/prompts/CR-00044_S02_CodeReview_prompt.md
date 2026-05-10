# CR-00044_S02_CodeReview_prompt

**Work Item**: CR-00044 — Markdown viewer for subdirectory docs, sharper per-page help-doc mappings, and favicon route
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state. Allowed: testcontainers via pytest fixtures, read-only `docker ps|inspect|logs`, `./ai-core.sh` / `make` targets. If your task seems to require a prohibited command, STOP and raise a blocker. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This item touches no migrations. Do not run `alembic upgrade|downgrade|stamp`. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- Runtime step state: `uv run iw item-status CR-00044 --json`.
- `ai-dev/active/CR-00044/CR-00044_CR_Design.md` — design document.
- `ai-dev/active/CR-00044/reports/CR-00044_S01_backend-impl_report.md` — S01 report.
- All files in S01's `files_changed`.

## Output Files

- `ai-dev/active/CR-00044/reports/CR-00044_S02_CodeReview_report.md` — review report.

## Read the Design Document FIRST

Read `## Acceptance Criteria` (AC1–AC6), `## TDD Approach`, and `## Notes` in full before opening any code. Write down every test file named in the TDD section and cross-check it against S01's `files_changed` — a TDD-named test file missing from `files_changed` is a CRITICAL finding.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run `make lint` and `make format` (check-only) on S01's changed files. Any NEW violation not present on `main` → CRITICAL finding, `category: conventions`, quoting file/line/code. If `make` is unavailable, STOP and raise a blocker.

## Review Checklist (CR-specific emphasis)

1. **Path traversal — the highest-risk area.** The route now uses FastAPI's `:path` converter, so the matched value can contain `/` and `..`. Verify ALL of: (a) empty / leading-`/` / `..` / `.` components are rejected; (b) the resolved path is checked with `is_relative_to` against the allowed base dir(s); (c) `.md` suffix and `is_file()` are required; (d) the normalised relpath must be in the precomputed allow-list set. The allow-list alone is sufficient, but the resolved-path check must also be present as defence-in-depth. Try to construct a bypass (e.g. `docs/../docs/IW_AI_Core_Architecture` → should this be allowed or 404? It resolves inside `docs/` and is in the allow-list, so 200 is acceptable; but `docs/../orch/config.py` must 404 on the `.md` check; `docs/../../etc/passwd` must 404 on the `is_relative_to` check). If any class of traversal is reachable → CRITICAL.
2. **Allow-list correctness.** `docs/**/*.md` must be picked up recursively (e.g. `docs/implementation/00_INDEX.md`, `docs/research/*.md`). The curated `CLAUDE.md` list must include `orch/rag/CLAUDE.md` (otherwise AC4's `code` link 404s) and must not be a bulk sweep of every `CLAUDE.md`.
3. **`FileResponse` / favicon.** `GET /favicon.ico` must resolve the SVG path absolutely (not relative to CWD) and set `image/svg+xml`. No path-injection surface here (fixed filename), but confirm the path resolution is anchored to the package dir.
4. **`_SLUG_TO_DOC` retargeting.** `code` → `/system/docs/orch/rag/CLAUDE.md`; `item_detail`/`research`/`search` → `/system/docs/IW_AI_Core_Dashboard_Design`; `projects` unchanged. Every `#anchor` present in the dict must correspond to a real `toc` heading id in the target doc — spot-check at least the `queue` (`#iw-approve`) and any newly-added anchors by rendering the target doc. A dangling anchor is a MEDIUM (fixable) finding (the link still resolves to the right doc, just not the right section).
5. **Title from H1.** Confirm `doc_title` is the first `# H1` of the file, with a basename fallback, and that `docs_view.html` still receives it under the expected key.
6. **No scope creep.** No new dependency; `_SLUG_TO_DOC` not moved to a config file; help-fragment prose unchanged; no new documentation content authored; no unrelated edits.
7. Standard checks: architecture (routers thin), code quality, conventions (`CLAUDE.md`, `dashboard/CLAUDE.md`), security, test coverage of AC1–AC6.

## Test Verification (NON-NEGOTIABLE)

Run `uv run pytest tests/dashboard/test_system_docs_route.py tests/dashboard/test_help_router.py -v` (plus the favicon test) and report results accurately. Do not run the full integration suite.

## Severity Levels & Result Contract

Use the standard severities (CRITICAL / HIGH / MEDIUM_FIXABLE / MEDIUM_SUGGESTION / LOW). `verdict: pass` only if zero CRITICAL/HIGH/MEDIUM_FIXABLE findings.

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "CR-00044",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [{"severity": "...", "category": "...", "file": "...", "line": 0, "description": "...", "suggestion": "..."}],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
