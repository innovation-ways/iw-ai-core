# CR-00044_S04_CodeReview_prompt

**Work Item**: CR-00044 — Markdown viewer for subdirectory docs, sharper per-page help-doc mappings, and favicon route
**Step Being Reviewed**: S03 (tests-impl)
**Review Step**: S04
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state. Allowed: testcontainers via pytest fixtures, read-only `docker ps|inspect|logs`, `./ai-core.sh` / `make` targets. If your task seems to require a prohibited command, STOP and raise a blocker. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This item touches no migrations. Do not run `alembic upgrade|downgrade|stamp`. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- Runtime step state: `uv run iw item-status CR-00044 --json`.
- `ai-dev/active/CR-00044/CR-00044_CR_Design.md` — design document.
- `ai-dev/active/CR-00044/reports/CR-00044_S03_tests-impl_report.md` — S03 report.
- All files in S03's `files_changed`.

## Output Files

- `ai-dev/active/CR-00044/reports/CR-00044_S04_CodeReview_report.md` — review report.

## Read the Design Document FIRST

Read `## Acceptance Criteria` (AC1–AC6) and `## TDD Approach` in full. Build a checklist mapping each AC and each TDD-named test to an actual test function in S03's changes. Any AC with no covering test is a CRITICAL finding; any TDD-named test file absent from `files_changed` is a CRITICAL finding.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run `make lint` and `make format` (check-only) on S03's changed files. Any NEW violation → CRITICAL finding, `category: conventions`. If `make` is unavailable, STOP and raise a blocker.

## Review Checklist (CR-specific emphasis)

1. **Traversal coverage.** Are there negative tests for: `..` segments, leading `/`, resolved-path escape (`docs/../../etc/passwd`-style), non-`.md` file, allow-list miss? Each must assert 404 **and** that no file content leaked into the body. Missing any class → MEDIUM (fixable) or higher depending on which.
2. **Subdir positive tests.** `orch/rag/CLAUDE.md` and a `docs/<subdir>/*.md` (e.g. `implementation/00_INDEX`) both asserted to 200 with real content. The flat-form regression test (`IW_AI_Core_Daemon_Design` → 200) present.
3. **Help-mapping asserts are precise.** The "no `/orch/` href" regression assert must not false-positive on the legitimate `/system/docs/orch/rag/CLAUDE.md` value — it should anchor on the `/system/docs/` prefix. The `code`/`item_detail`/`research`/`search`/`projects` targets asserted. If present, the anchor-pinning test (`#fragment` → `id="fragment"` in target doc) is a plus.
4. **Favicon test.** 200, `image/svg+xml`, body equals the SVG bytes.
5. **Title-from-H1 test.** Asserts the `00_INDEX` page title is the file's H1, not the path string.
6. **Test isolation/determinism.** Tests use `TestClient`, no live DB, no docker, no network; they read repo files via stable relative paths, not absolute machine paths.
7. **No scope creep** in the tests (no new fixtures touching live infra, no unrelated test churn).

## Test Verification (NON-NEGOTIABLE)

Run `uv run pytest tests/dashboard/test_system_docs_route.py tests/dashboard/test_help_router.py tests/dashboard/test_favicon.py -v` and report results accurately. Do not run the full integration suite.

## Severity Levels & Result Contract

Standard severities. `verdict: pass` only if zero CRITICAL/HIGH/MEDIUM_FIXABLE findings.

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "CR-00044",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [{"severity": "...", "category": "...", "file": "...", "line": 0, "description": "...", "suggestion": "..."}],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
