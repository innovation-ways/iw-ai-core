# I00109_S02_CodeReview_prompt

**Work Item**: I-00109 -- `GET /project/{project_id}/docs/{doc_id}/pdf` raises unhandled `PermissionError` → HTTP 500 when on-disk PDF cache dir is not writable
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

You MUST NOT change Docker container/volume/network state. Testcontainer fixtures in pytest are exempt. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This item adds no migration. You MUST NOT run any `alembic upgrade/downgrade/stamp` command. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00109 --json`.
- `ai-dev/active/I-00109/I-00109_Issue_Design.md` -- Design document (read §Acceptance Criteria, §Root Cause Analysis, §Affected Components).
- `ai-dev/active/I-00109/reports/I-00109_S01_Backend_report.md` -- S01 implementation report.
- All files listed in S01's `files_changed` (expected: `dashboard/routers/docs.py`).
- `dashboard/routers/docs.py` -- The reviewed file. Compare `docs_pdf` (lines ~271-340 post-fix) against the sibling `docs_pdf_view` (lines 188-268) — the fix MUST mirror the latter's guard pattern.

## Output Files

- `ai-dev/active/I-00109/reports/I-00109_S02_CodeReview_report.md` -- Review report.

## Context

S01 wrapped the unguarded `cache_dir.mkdir(...)` + `cache_file.write_bytes(...)` + `svc.update_doc(...)` block in `docs_pdf` (was lines 320-324) in `try / except Exception`, mirroring the existing guard pattern at lines 256-266 in `docs_pdf_view`. The fix is intentionally a structural mirror of an existing pattern in the same file — your review must verify exact mirroring, scope discipline, and that the response path stays unchanged on the happy path.

Read the design doc first, then the implementation report, then diff the changed file against the sibling handler.

## Read the Design Document FIRST

Read `ai-dev/active/I-00109/I-00109_Issue_Design.md` in full **before** running the lint/format gate and **before** opening any changed file. Specifically:

- §Acceptance Criteria — both AC1 (route returns 200 on read-only `repo_root`) and AC2 (regression test exists + `EXPECTED_5XX` entry removed). Note: AC2 is implemented in S03, NOT in S01 — so a missing test file or unaltered `EXPECTED_5XX` in S01's diff is **expected and correct**. Flag it only if S01 inappropriately edited a test file.
- §TDD Approach — note the test file the design names (`tests/dashboard/test_docs_pdf_cache_failure.py`). It is created in S03; if it appears in S01's `files_changed`, that is a scope violation — flag as CRITICAL.
- §Fix Plan — S01's scope is `dashboard/routers/docs.py` only. Anything else in `files_changed` is a scope violation (the `scope.allowed_paths` enforcer will block the merge regardless, but flag it now).

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading any code, run on the files in S01's `files_changed`:

```bash
make lint
make format-check
```

If either reports NEW violations in the changed file (i.e., violations that did not exist on `main` before S01), classify each as a **CRITICAL** finding with `"category": "conventions"`, `file`/`line` from the tool output, and a `description` quoting the violation code + message verbatim.

If a tool is unavailable, STOP and raise a blocker. Do NOT skip.

## Review Checklist

### 1. Exact Mirror of `docs_pdf_view`'s Guard (CRITICAL)

The fix's value is structural symmetry with the sibling handler. Diff the post-fix `docs_pdf` cache-write block against `docs_pdf_view` lines 254-266 and verify:

- Same `try:` / `except Exception:` shape.
- Same `# noqa: BLE001 — read-only fs, permission error, etc.` comment **verbatim** (the noqa code is necessary; the comment carries the rationale for the broad catch — both are part of the project's style for this pattern).
- Same `import logging` inside the `except` block (do NOT hoist to module-top in this incident — `docs_pdf_view` does not hoist either; consistency is the point).
- Same logger: `logging.getLogger(__name__)`.
- Same `.warning(...)` call with the format string `"Failed to write pdf_path cache for doc %s/%s"` and positional args `project_id, doc_id`. The format string MUST match `docs_pdf_view`'s call verbatim — the message is operator-visible and operators grep for it.

Any deviation from the sibling pattern (different log level, different message, different exception scope, refactor to a helper) is a **HIGH** finding. The fix should be a copy-paste mirror, not a "clean-up".

### 2. Response Path Unchanged on Happy Path (HIGH)

Verify that on the happy path (cache write succeeds) the response is **identical** to pre-fix:

- Same `Response(content=pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": ...})` call after the `try/except` block — NOT inside the `try` block, NOT duplicated inside `except`.
- The `Content-Disposition: attachment; filename="{doc.slug}-v{doc.version}.pdf"` header is preserved verbatim.
- The function still returns the same `Response` object on the cached-PDF fast path (lines 289-298 pre-fix) — unchanged.
- The function still returns the same 503 `JSONResponse` when Chromium is missing (lines 311-318 pre-fix) — unchanged.

If the return moved into the `try` block, the bug would re-emerge differently (the `except` would fall through and return `None`, surfacing as a different HTTP error). Flag as **CRITICAL** if so.

### 3. Scope Discipline (CRITICAL)

S01 must touch **only** `dashboard/routers/docs.py`. Verify:

- `files_changed` contains exactly one path: `dashboard/routers/docs.py`. Anything else is a scope violation — **CRITICAL**.
- `docs_pdf_view` was NOT edited. Diff its lines 188-268 against `main` — they must be byte-identical. The fix is in `docs_pdf` only; touching the sibling is out of scope.
- No template, service, or other router was edited.
- No `EXPECTED_5XX` removal in `tests/dashboard/test_route_contract_sweep.py` (that is S03's job). If S01 made the removal, flag as **HIGH** (it works, but it violates step ownership and obscures S03's RED→GREEN signal).

### 4. No Refactor

A common failure mode is "while I'm here, let me extract a shared helper for the cache-write." Verify S01 did NOT:

- Extract a new function (`_safe_write_pdf_cache`, `_cache_pdf_to_disk`, etc.).
- Move the logger import to the module top.
- Rewrite `docs_pdf_view`'s guard to delegate to the new shape.
- Reorder unrelated code in the file.

Any of these is a **HIGH** finding (scope creep), even if functionally equivalent. The follow-up CR for consolidation, if desired, is filed separately.

### 5. TDD RED Evidence (Required for Backend Steps)

Verify S01's report includes a `tdd_red_evidence` field that captures the strict-xfail flip on the route-sweep case. Acceptable forms:

- `XPASS(strict)` output line from `pytest tests/dashboard/test_route_contract_sweep.py -v` showing the `GET /project/{project_id}/docs/{doc_id}/pdf` case flipped, e.g. `tests/dashboard/test_route_contract_sweep.py::test_route_returns_no_5xx[GET /project/{project_id}/docs/{doc_id}/pdf] XPASS(strict) — ...`.

**Reason about whether the strict-xfail case would actually fail against pre-change code.** Pre-fix the route returns 500 → the `xfail(strict=True)` marker holds → the case is reported as `XFAIL` (pass). Post-fix the route returns 200 → the strict marker treats this as `XPASS(strict)` → reported as FAIL. That is the RED→GREEN demonstration. If S01's `tdd_red_evidence` does not capture this flip (e.g. reports a passing test against no marker), flag as **HIGH** — the evidence does not prove the bug was fixed.

The stash-recheck (manually reverting the guard and re-running the targeted file to confirm the case goes back to `XFAIL`) is **optional** and not mandatory; mark it as noted-not-required in the review.

### 6. Project Conventions

- Routers stay thin (see `dashboard/CLAUDE.md`).
- No docker / no alembic commands invoked from the route.
- Naming + formatting matches the file's existing style.
- No `print(...)` — the project uses `logging`.

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. Run the targeted dashboard test file (cheap):
   ```bash
   uv run pytest tests/dashboard/test_route_contract_sweep.py -v --no-cov
   ```
   Expected: 1 XPASS(strict) on the `docs_pdf` case (failure), all other sweep cases pass. This is the post-fix expected state until S03 lands. Report it accurately — a strict-xfail flip is a `tests_passed: true` semantic GREEN for this step's purpose, even though pytest's exit code is non-zero. Use `tests_passed: true` with a `test_summary` that explains the XPASS(strict) is the GREEN signal.

2. Run `make test-unit` to confirm no regressions in unit-test coverage of the dashboard router layer. (Cheap, ~seconds.)

Do NOT run `make test-integration` — that is the S11 QV gate's job.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Breaks functionality, scope violation that the merge gate will block, missing required step output, or response-path regression | Must fix before merge |
| **HIGH** | Mirror deviation from `docs_pdf_view`, scope creep (refactor / helper extraction), missing/weak `tdd_red_evidence` | Must fix before merge |
| **MEDIUM (fixable)** | Convention drift, missing log context, formatting nits the gate will catch | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Design improvement that is explicitly out of scope (e.g. "consolidate the two handlers") | Optional, file follow-up |
| **LOW** | Nitpick / style preference | Informational only |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00109",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "test_route_contract_sweep.py: 1 XPASS(strict) on docs_pdf case (expected GREEN per S03 plan), all other sweep cases pass; make test-unit: <X> passed, 0 failed",
  "notes": "S03 removes the EXPECTED_5XX entry; the XPASS(strict) is the RED→GREEN signal for S01, not a regression."
}
```

- `verdict`: `pass` only if zero CRITICAL + zero HIGH + zero MEDIUM_FIXABLE findings.
- `mandatory_fix_count`: sum of CRITICAL + HIGH + MEDIUM_FIXABLE findings.
