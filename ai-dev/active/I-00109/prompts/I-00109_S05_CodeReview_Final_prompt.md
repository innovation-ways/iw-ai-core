# I00109_S05_CodeReview_Final_prompt

**Work Item**: I-00109 -- `GET /project/{project_id}/docs/{doc_id}/pdf` raises unhandled `PermissionError` → HTTP 500 when on-disk PDF cache dir is not writable
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S04

---

## ⛔ Docker is off-limits

You MUST NOT change Docker container/volume/network state. Testcontainer fixtures in pytest are exempt. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This item adds no migration. You MUST NOT run any `alembic upgrade/downgrade/stamp` command. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00109 --json`.
- `ai-dev/active/I-00109/I-00109_Issue_Design.md` -- Design document (read §Acceptance Criteria, §Fix Plan, §File Manifest, §Regression Prevention in full).
- `ai-dev/active/I-00109/I-00109_Functional.md` -- Functional design.
- All step reports: `ai-dev/active/I-00109/reports/I-00109_S01_Backend_report.md`, `I-00109_S02_CodeReview_report.md`, `I-00109_S03_Tests_report.md`, `I-00109_S04_CodeReview_report.md`.
- All files listed in S01's and S03's `files_changed` arrays (expected union: `dashboard/routers/docs.py`, `tests/dashboard/test_docs_pdf_cache_failure.py`, `tests/dashboard/test_route_contract_sweep.py`).
- `dashboard/routers/docs.py` -- Diff against `origin/main` (compare `docs_pdf` and `docs_pdf_view` post-fix — they must be structurally symmetric).
- `tests/dashboard/test_route_contract_sweep.py` -- Confirm the `EXPECTED_5XX` entry for `/project/{project_id}/docs/{doc_id}/pdf` is gone.

## Output Files

- `ai-dev/active/I-00109/reports/I-00109_S05_CodeReview_Final_report.md` -- Final review report.

## Context

You are performing the **final cross-agent review** of ALL implementation work for **I-00109**. Per-agent reviews (S02, S04) already addressed step-level issues. Your job is to catch cross-cutting issues they could not see:

- Coherence between the production fix (S01) and the regression test (S03): the test must actually exercise the guarded code path.
- Coherence between the `EXPECTED_5XX` removal (S03) and the route fix (S01): both must be in the same merge — otherwise the sweep regresses to `XPASS(strict)`→FAIL on merge.
- Scope discipline across the full item: `git diff origin/main` must touch only the three allow-listed paths.
- AC1 + AC2 both end-to-end verified.

## Read the Design Document FIRST

Read `ai-dev/active/I-00109/I-00109_Issue_Design.md` in full **before** running the lint/format gate and **before** opening any changed files. Specifically:

- §Acceptance Criteria — AC1 (route returns 200 + PDF + warning + `pdf_path` unchanged on read-only `repo_root`) and AC2 (`test_docs_pdf_returns_200_when_cache_dir_not_writable` passes GREEN + `EXPECTED_5XX` entry removed). Verify every clause of every AC has corresponding code or test that pins it.
- §TDD Approach — the design names `tests/dashboard/test_docs_pdf_cache_failure.py::test_docs_pdf_returns_200_when_cache_dir_not_writable` by path. Verify it appears in S03's `files_changed`. If a TDD-named test file is missing from any report's `files_changed`, that is a **CRITICAL** finding.
- §File Manifest — three production/test paths are allowed (`dashboard/routers/docs.py`, `tests/dashboard/test_route_contract_sweep.py`, `tests/dashboard/test_docs_pdf_cache_failure.py`). Anything in any report's `files_changed` outside this set is a **CRITICAL** scope violation (the merge gate will block it).

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

NEW violations on any changed file → **CRITICAL** `"category": "conventions"`. Quote exact violation code + message.

If a tool is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. Completeness vs Design Document (CRITICAL on miss)

- AC1 every clause has a corresponding test assertion in `test_docs_pdf_returns_200_when_cache_dir_not_writable`:
  - status 200 → `assert resp.status_code == 200` ✓
  - Content-Type `application/pdf` → `assert resp.headers["content-type"] == "application/pdf"` ✓
  - body starts with `%PDF` → `assert resp.content.startswith(b"%PDF")` ✓
  - Content-Disposition `attachment` → `assert "attachment" in resp.headers["content-disposition"]` ✓
  - warning logged → `caplog` assertion on `"Failed to write pdf_path cache for doc"` ✓
  - `pdf_path` NOT updated → `db_session.refresh(doc); assert doc.pdf_path is None` ✓
- AC2 the `EXPECTED_5XX` entry for the docs-pdf route is removed from `tests/dashboard/test_route_contract_sweep.py`.

Any missing clause → **CRITICAL** finding.

### 2. Cross-Agent Consistency (CRITICAL)

- S01's guard in `docs_pdf` is a **structural mirror** of `docs_pdf_view`'s guard (lines 256-266). Diff the two `except Exception: ...` blocks side-by-side and confirm:
  - Same comment `# noqa: BLE001 — read-only fs, permission error, etc.`
  - Same `import logging` placement inside `except`.
  - Same logger getter `logging.getLogger(__name__)`.
  - Same `.warning(...)` call with format string `"Failed to write pdf_path cache for doc %s/%s"` and args `project_id, doc_id`.
  Any drift between the two → **HIGH** finding (the symmetry is the design's regression-prevention story).
- S03's test patches `dashboard.routers.docs.render_pdf_chromium` — confirm this dotted path matches the actual import in `dashboard/routers/docs.py` (the symbol may be re-exported from a helper module). A mismatched patch path means the test patches nothing and accidentally exercises real Chromium — which may pass by coincidence on dev machines and fail in CI. **HIGH**.
- S03's test seeds a `ProjectDoc` with all NOT NULL columns the live model requires. Cross-check the `ProjectDoc(...)` constructor in the test against `orch/db/models.py`. Missing-required-column errors at fixture-build time are a **CRITICAL** finding (the test would never collect cleanly).

### 3. Integration Points (HIGH)

- `EXPECTED_5XX` removal + S01's route fix are in the same item (same merge). If split (e.g. S01 in a different commit window than S03), the route sweep would briefly report `XPASS(strict)`→FAIL during S01..S03. They share the merge — verify both are in S05's worktree at review time.
- The `EXPECTED_5XX: dict[str, str] = {}` declaration and explanatory comment block are preserved (even if the dict is now empty). Removing the declaration would break the sweep at import. **HIGH**.
- The post-fix `docs_pdf` and `docs_pdf_view` handlers both serve a 503 JSON / styled HTML when Chromium is unavailable — unchanged. Verify the Chromium-missing path is unaffected by S01's edit. **HIGH** if regressed.

### 4. Test Coverage (Holistic)

- The reproduction test pins the `mkdir`-fails path. Optional but ideal: a second test pinning the `write_bytes`-fails path (same outcome). If absent, flag as **MEDIUM_SUGGESTION** only (the design did not require it).
- The new test runs in-process via `TestClient` (no real Chromium needed, fast). Confirm no skip markers, no `pytest.mark.slow`, no Playwright dependency.
- No new property tests or smoke tests are added — that is correct; this incident does not warrant new property coverage and the smoke layer SLA caps at 15 tests.

### 5. Architecture Compliance

- Router stays thin (no business logic moved out of `docs_pdf`). Per `dashboard/CLAUDE.md`.
- No docker invocation in test or route. Per `docs/IW_AI_Core_Agent_Constraints.md`.
- No alembic invocation. Per `docs/IW_AI_Core_Agent_Constraints.md`.

### 6. Security (Cross-Cutting)

- No hardcoded secrets in test or route (test seeds a fake-content doc only).
- The warning log records `project_id` + `doc_id` — both are caller-supplied URL path params already validated by FastAPI. No sensitive data leakage. ✓.

### 7. Scope Discipline (CRITICAL on violation)

Run `git diff --name-only origin/main..HEAD` (or the equivalent in your worktree) and verify the changed-files set is EXACTLY:

```
ai-dev/active/I-00109/...                                    (design package — implicit allow)
dashboard/routers/docs.py
tests/dashboard/test_docs_pdf_cache_failure.py
tests/dashboard/test_route_contract_sweep.py
```

Any file outside this set is a **CRITICAL** scope violation — the `worktree_commit.sh` Step 2.25 merge gate will block the merge regardless. Flag it so the operator can amend the allow-list (or remove the rogue change) before the gate blows up.

## Test Verification (NON-NEGOTIABLE)

Before submitting your review, run **targeted** tests only — the full
integration suite is the S11 QV gate's job, and duplicating it inside an
`-impl` step burns the timeout budget (see I-00073/S03 post-mortem):

1. Run the **full unit suite** (cheap, < 1 min):
   ```bash
   make test-unit
   ```
2. Run the targeted dashboard files (exercises both the new regression test
   and the route-sweep change end-to-end):
   ```bash
   uv run pytest tests/dashboard/test_docs_pdf_cache_failure.py tests/dashboard/test_route_contract_sweep.py -v --no-cov
   ```

Do NOT run `make test-integration` here — that is the S11 QV gate, which
runs the full suite (including the dashboard route-sweep and the new
regression test) immediately after this step.

Report results in the result contract under `test_summary`.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Missing AC clause, scope violation, missing required test column | Must fix before merge |
| **HIGH** | Mirror drift between `docs_pdf` and `docs_pdf_view`, mis-patched import path, `EXPECTED_5XX` declaration removed, split commits | Must fix before merge |
| **MEDIUM (fixable)** | Convention drift, missing log scope, format-check failure | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Add a `write_bytes`-fails edge-case test; extract a shared `_safe_write_pdf_cache` helper (out of scope for this incident) | Optional, file follow-up |
| **LOW** | Nitpick / style | Informational only |

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "I-00109",
  "steps_reviewed": ["S01", "S02", "S03", "S04"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|integration|testing|architecture|security",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it",
      "cross_cutting": true
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "make test-unit: <X> passed, 0 failed; targeted dashboard (test_docs_pdf_cache_failure.py + test_route_contract_sweep.py): <Y> passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```

- `verdict`: `pass` only if zero CRITICAL + zero HIGH + zero MEDIUM_FIXABLE findings.
- `mandatory_fix_count`: CRITICAL + HIGH + MEDIUM_FIXABLE.
- `missing_requirements`: List any AC clause without a corresponding test assertion or production change.
- `cross_cutting`: `true` for findings spanning S01↔S03 coherence or scope-discipline.
