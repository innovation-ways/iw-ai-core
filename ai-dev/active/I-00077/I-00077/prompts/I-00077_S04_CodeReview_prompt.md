# I-00077_S04_CodeReview_prompt

**Work Item**: I-00077 — Doc-generation jobs abort on missing editorial guide and the failure is invisible on the Docs page
**Step Being Reviewed**: S03 (frontend-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits

No Docker state-changing commands. Allowed: testcontainers via pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` / `make`. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

No migrations / no schema change in this item.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00077 --json`.
- `ai-dev/active/I-00077/I-00077_Issue_Design.md` — design document
- `ai-dev/active/I-00077/reports/I-00077_S03_frontend-impl_report.md` — S03 report
- All files in S03's `files_changed` (expect: `dashboard/routers/docs.py`, `dashboard/templates/docs_library.html`, `dashboard/templates/fragments/docs_running_jobs.html`, `tests/dashboard/test_docs_running_jobs.py`)

## Context

Review S03's implementation of Fix #3 (Docs catalogue page surfaces job failures). Read the design doc first — note **AC3** and the **TDD Approach** dashboard tests; carry those into your checklist.

## Read the Design Document FIRST

- Read `## Acceptance Criteria` (AC3) and `## TDD Approach` in full.
- The design names `tests/dashboard/test_docs_running_jobs.py` as carrying the failed-job-in-strip regression test. Confirm it appears in S03's `files_changed` (S05 extends it further; a minimal RED→GREEN assertion here is expected).
- This item adds a new data shape on a render path: `docs_running_jobs` now emits rows with `status == "failed"` that the fragment has never rendered before. Independently re-trace the fragment for that new shape — confirm a failed row does NOT open an `EventSource`, does NOT start an elapsed-timer interval, does NOT render a Cancel button, and that `_docJobSources` dedup logic isn't tripped by a failed row.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Any NEW violation in the changed files vs `main` → a **CRITICAL** finding (`category: conventions`, file/line + exact code/message). `make lint` includes `scripts/check_templates.py` (Jinja2 `format`-filter rule) and `node --check` on dashboard JS — a failure in either is a CRITICAL finding. If `make` is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. Router (`docs_running_jobs`)

- Query returns `running` jobs **and** `failed` jobs whose `completed_at` is within ~10 min; `research` docs still excluded; `doc_id` still scoped to the project. The 10-min cutoff uses an aware datetime (`datetime.now(UTC) - timedelta(...)`), not a naive one.
- Ordering is deterministic and sensible (running first).
- The per-job dict gained `status` and `error`; existing keys (`job_id`, `doc_id`, `doc_title`) intact.
- No N+1 explosion beyond what already existed (the handler already does `svc.get_doc` per job — acceptable, not new).

### 2. Fragment (`docs_running_jobs.html`)

- Running rows are byte-for-byte behaviourally unchanged (spinner, timer, Cancel, EventSource).
- Failed rows: distinct red styling using an existing token/class; error text rendered through Jinja2 autoescaping (NOT `|safe`); a Dismiss control that removes the row client-side via the `docs-rjob-` id; **no** EventSource, **no** timer, **no** Cancel button.
- No `str.format`-style `format` filter anywhere (only `%`-style permitted).
- The outer `id="docs-rjob-{{ item.job_id }}"` convention is preserved.

### 3. Catalogue page (`docs_library.html`)

- `{% include "components/toast.html" %}` added (and not double-included).
- `docJobFailed` listener calls `showToast({type:'error', ...})` with the doc id and (truncated) error.
- The optional `docJobCreated` → `runningJobsReload` re-poll, if present, is small (a couple of `setTimeout`s) and does not introduce an unbounded polling loop.
- No regression to the existing `docJobCompleted` flow or the `#docs-running-jobs` `hx-trigger`.

### 4. Conventions / quality / security

- `dashboard/CLAUDE.md` + `CLAUDE.md` respected; no hardcoded URLs/ports; no XSS (error strings escaped); no scope creep into `orch/` or the skills.

### 5. Testing

- `tests/dashboard/test_docs_running_jobs.py` asserts (semantically) that a recently-failed job appears in `GET .../api/docs/running-jobs`, that the failed row carries a dismiss control and no Cancel control, and that `docs_library.html` includes a `docJobFailed` handler. CSS-class assertions are attribute-scoped (not bare substrings — I-00067).

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/dashboard/test_docs_running_jobs.py -v
```

Report results accurately.

## Severity Levels

CRITICAL / HIGH / MEDIUM (fixable) / MEDIUM (suggestion) / LOW — only the first three trigger a fix cycle.

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00077",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [{"severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW", "category": "architecture|code_quality|conventions|security|testing", "file": "", "line": 0, "description": "", "suggestion": ""}],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

`verdict`: `pass` only if zero CRITICAL/HIGH/MEDIUM(fixable) findings.
