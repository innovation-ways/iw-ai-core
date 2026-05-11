# I-00077_S07_CodeReview_Final_prompt

**Work Item**: I-00077 — Doc-generation jobs abort on missing editorial guide and the failure is invisible on the Docs page
**Review Step**: S07 (Final Review)
**Implementation Steps Reviewed**: S01..S06

---

## ⛔ Docker is off-limits

No Docker state-changing commands. Allowed: testcontainers via pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` / `make`. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

No migrations / no schema change in this item.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00077 --json`.
- `ai-dev/active/I-00077/I-00077_Issue_Design.md` — design document
- All step reports: `ai-dev/active/I-00077/reports/I-00077_S0{1..6}_*_report.md`
- All files changed across S01, S03, S05 (and any fix-cycle edits): `orch/doc_service.py`, `skills/iw-doc-generator/SKILL.md`, `skills/iw-doc-system/SKILL.md`, `dashboard/routers/docs.py`, `dashboard/templates/docs_library.html`, `dashboard/templates/fragments/docs_running_jobs.html`, `tests/unit/test_doc_type_guide_service.py`, `tests/integration/test_doc_type_guides.py` (and/or `tests/integration/test_i00077_doc_job_editorial_fallback.py`), `tests/dashboard/test_docs_running_jobs.py`

## Context

Final cross-agent review of all I-00077 work. Look at the whole picture — how the backend fix, the skill clarifications, the dashboard changes, and the tests fit together — not individual steps in isolation.

## Read the Design Document FIRST

- Read `## Acceptance Criteria` (AC1–AC4) and `## TDD Approach` in full. Cross-check every test file the design names against the union of all implementation reports' `files_changed`; any missing one is a **CRITICAL** finding.
- Re-trace the doc-job-context path end to end with the new data shapes: `DocService.create_doc_job` → `_effective_guide` (now `_default`-fallback) → `DocGenerationJob.guide_snapshot` → `iw doc-job-status --json` (`orch/cli/doc_commands.py`) → the agent's skill prompt (`skills/iw-doc-generator/SKILL.md` "Job lifecycle"). Confirm the chain now yields a non-`None` `guide_snapshot` for a `diagram` doc and that the skill text no longer tells the agent to bail on a null snapshot.
- Re-trace the strip render path with the new `status == "failed"` row shape: `docs_running_jobs` query → `running_jobs` dicts → `fragments/docs_running_jobs.html` → the per-row `<script>`. Confirm a failed row does not spawn an `EventSource`/timer/Cancel button and that `docs_library.html`'s new `docJobFailed` listener + `components/toast.html` produce a visible toast.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

NEW violations in any changed file vs `main` → CRITICAL (`category: conventions`). `make lint` includes `scripts/check_templates.py` (Jinja2) and `node --check` (dashboard JS) — failures there are CRITICAL. If `make` is unavailable, STOP and raise a blocker.

## Review Checklist

1. **Completeness vs design** — AC1 (`_default` fallback → non-`None` `guide_snapshot`), AC2 (both skill files clarified, consistent, old non-zero-exit guidance retained), AC3 (failed jobs in the strip, dismissible red row, `docJobFailed` toast on the catalogue page), AC4 (reproduction tests present & passing). Any unimplemented requirement is CRITICAL.
2. **Cross-agent consistency** — the `status` / `error` keys S03 added to `running_jobs` dicts match what the fragment consumes; the catalogue page consistent with `docs_detail.html`'s existing failure-banner behaviour; naming consistent.
3. **Integration points** — no circular imports; `timedelta`/`UTC` imports present in `dashboard/routers/docs.py`; the SSE `failed` branch still dispatches `docJobFailed` (S03 only added a listener) so the toast actually fires when a running job fails.
4. **Test coverage (holistic)** — reproduction tests genuinely target the bug; the failed-job-in-strip and bounded-window cases exist; semantic assertions; correct test-dir placement.
5. **Architecture / conventions** — `CLAUDE.md`, `dashboard/CLAUDE.md`, `orch/CLAUDE.md` respected; no scope creep beyond `workflow-manifest.json:scope.allowed_paths`; the skill-propagation-to-other-repos item is correctly left as a manual post-merge note (not done in this worktree).
6. **Security** — error strings are HTML-escaped in the fragment; no hardcoded secrets/URLs/ports.

## Test Verification (NON-NEGOTIABLE)

Run the **full test suite** (unit + integration, the latter includes `tests/dashboard/`):

```bash
make test-unit
make test-integration
```

Report results accurately. Integration test failures → CRITICAL.

## Severity Levels

CRITICAL / HIGH / MEDIUM (fixable) / MEDIUM (suggestion) / LOW — only the first three trigger a fix cycle.

## Review Result Contract

```json
{
  "step": "S07",
  "agent": "CodeReview_Final",
  "work_item": "I-00077",
  "steps_reviewed": ["S01", "S02", "S03", "S04", "S05", "S06"],
  "verdict": "pass|fail",
  "findings": [{"severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW", "category": "completeness|consistency|integration|testing|architecture|security", "file": "", "line": 0, "description": "", "suggestion": "", "cross_cutting": false}],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```

`verdict`: `pass` only if zero CRITICAL/HIGH/MEDIUM(fixable) findings.
