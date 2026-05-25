# I-00112_S09_CodeReview_Final_prompt

**Work Item**: I-00112 -- Keep-Alive Scheduler logs `status=success` for silent no-op CLI fires
**Review Step**: S09 (Final Review)
**Implementation Steps Reviewed**: S01..S07

---

## ⛔ Docker is off-limits

Standard policy. Read-only `docker ps/inspect/logs` is fine.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. You may inspect the S01 revision file. You MUST NOT apply migrations.

## Input Files

- `uv run iw item-status I-00112 --json`.
- `ai-dev/active/I-00112/I-00112_Issue_Design.md`.
- `ai-dev/active/I-00112/I-00112_Functional.md`.
- All implementation reports: `ai-dev/active/I-00112/reports/I-00112_S0[1357]_*_report.md`.
- All per-agent review reports: `ai-dev/active/I-00112/reports/I-00112_S0[2468]_CodeReview_report.md`.
- All files listed in implementation reports' `files_changed`:
  - `orch/db/migrations/versions/<rev>_i00112_*.py`
  - `orch/db/models.py`
  - `orch/keep_alive_service.py`
  - `orch/daemon/keep_alive_poller.py`
  - `dashboard/templates/fragments/keep_alive_runs.html`
  - `tests/unit/test_keep_alive_poller_success_contract.py`
  - `tests/unit/test_keep_alive_service.py`
  - `tests/unit/test_keep_alive_poller.py`
  - `tests/dashboard/test_keep_alive_runs_table.py`
  - Any others reported.

## Output Files

- `ai-dev/active/I-00112/reports/I-00112_S09_CodeReview_Final_report.md`.

## Context

You are performing the **final cross-agent review** of all implementation work for I-00112. Per-agent reviews (S02, S04, S06, S08) caught issues within each step. Your job is to catch cross-cutting issues they could not.

The fix has four cross-cutting concerns:
1. **Schema ↔ ORM ↔ runtime persistence** — does the migration produce columns that the model declares that the poller actually writes?
2. **Backend ↔ Frontend** — does the template render the same field names the model exposes?
3. **Production code ↔ Tests** — do the tests actually exercise the success-contract boundary, not just the wrapper?
4. **Behavioural intent ↔ ACs** — does the assembled work satisfy AC1–AC5?

## Read the Design Document FIRST

- **Acceptance Criteria** AC1–AC5 — each one is a mandatory check.
- **TDD Approach** — every test file named there MUST appear in some `files_changed` array.
- **Notes** — the 500 ms floor rationale; verify the constant is named, not magic.

Test files the design names:
- `tests/unit/test_keep_alive_poller_success_contract.py` ← must be in S07's `files_changed`. Missing anywhere = CRITICAL.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

NEW violations in any of the impl steps' `files_changed` are CRITICAL.

## Review Checklist

### 1. Cross-layer schema consistency

- Migration column names (`stdout`, `stderr`, `elapsed_ms`, `returncode`) match the ORM attribute names exactly. Mismatch → CRITICAL.
- ORM attribute types (`Text` ↔ `str | None`, `Integer` ↔ `int | None`) agree with the migration columns. Mismatch → CRITICAL — `make migration-check` would catch but worth a manual sweep.
- Production code writes ALL four fields on every `_log_run` call. Re-trace the poller code paths to confirm no branch produces a row with NULL diagnostic fields when the fields were actually captured. (NULL on legacy rows is intentional; NULL on fresh rows is a HIGH regression.)

### 2. Backend ↔ Frontend field consistency

- The template references `run.stdout`, `run.elapsed_ms` (and possibly `run.stderr`, `run.returncode` — if rendered). Each of those names MUST appear as a `Mapped[…]` attribute on `KeepAliveRun` in `orch/db/models.py`. A template reference to a non-existent attribute renders empty (silent UX defect) — HIGH.
- The router still passes ORM objects to the template (no dict transformation that drops the new fields). Verify by reading `dashboard/routers/keep_alive.py:GET /api/keep-alive/runs`.

### 3. Success contract is implemented exactly once

- `_MIN_SUCCESS_ELAPSED_MS = 500` exists exactly once. `grep -rn "500" orch/` MUST NOT show another magic 500 in `keep_alive_service.py` or `keep_alive_poller.py` that should reference the constant. Duplicate magic numbers are HIGH.
- The contract `rc == 0 AND stdout.strip() != "" AND elapsed_ms >= _MIN_SUCCESS_ELAPSED_MS` lives in exactly one place (`FireResult.is_success`). The poller MUST consult `result.is_success`, not re-derive the contract inline. Re-derivation is HIGH (drift risk).

### 4. Test boundary

- Re-confirm tests mock at `subprocess.run`, not at `fire_claude`. A mock at the wrapper boundary would PASS today but fail to catch the next silent no-op variant — HIGH.

### 5. AC mapping

For each AC1–AC5, point to the specific code OR test that demonstrates it satisfied. Missing demonstration → CRITICAL.

- **AC1** (silent no-op classified failed): `tests/unit/test_keep_alive_poller_success_contract.py::test_i00112_poller_logs_failed_when_contract_violated` + `_fire_slot` consults `is_success`.
- **AC2** (real round-trip classified success): `tests/unit/test_keep_alive_poller_success_contract.py::test_i00112_real_round_trip_is_success` + `_fire_slot` consults `is_success`.
- **AC3** (regression tests exist): All six tests in the new file pass.
- **AC4** (dashboard shows new columns): `tests/dashboard/test_keep_alive_runs_table.py` + the extended fragment.
- **AC5** (migration round-trips): `make migration-check` passes in S01's report and S02's review.

### 6. Functional doc ↔ technical doc consistency

- `I-00112_Functional.md` describes user-observable outcomes (two new columns, stricter Success label, "—" for legacy rows). Cross-check against the actual template change: does a non-engineer reading the functional doc accurately predict what the dashboard now shows? Drift between functional and technical docs → MEDIUM (suggestion).

### 7. Architecture compliance

- `orch/keep_alive_service.py` retains its layer role (subprocess + business logic). The success contract lives there via `FireResult.is_success` — appropriate. If you find the contract being re-checked in the dashboard layer, that is a layer violation → HIGH.
- Routers stay thin. Any business logic that crept into `dashboard/routers/keep_alive.py` → HIGH (per `dashboard/CLAUDE.md`).

### 8. Security (cross-cutting)

- The template HTML-escapes `stdout` in the `title` attribute. A model reply containing `"` or `</span>` MUST NOT break the page. Missing `|e` (or any equivalent escaping) → CRITICAL (XSS class).
- No hardcoded credentials, model name aliases that bypass config, or env-var defaults snuck in.

### 9. Scope cleanliness

- The union of all `files_changed` MUST match the **Impacted Paths** declared in the design doc. A file outside that list shipped → CRITICAL (cross-batch overlap detector will flag it at merge anyway, but better caught here).

## Test Verification (NON-NEGOTIABLE)

Run the **full unit AND integration suite**:

```bash
make test-unit
make migration-check
```

Integration suite (`make allure-integration`) is the S17 gate's job; you may run it for completeness but it is not blocking for this review.

If `make test-unit` or `make migration-check` fail, that is a CRITICAL finding.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Cross-layer mismatch, missing AC demonstration, scope leak, XSS, contract duplicated incorrectly |
| **HIGH** | Wrong mock boundary, magic number duplication, contract re-derived, template references missing attribute |
| **MEDIUM (fixable)** | Functional ↔ technical drift, weak assertion patterns |
| **MEDIUM (suggestion)** | Helpers, naming |
| **LOW** | Nitpicks |

## Review Result Contract

```json
{
  "step": "S09",
  "agent": "CodeReview_Final",
  "work_item": "I-00112",
  "steps_reviewed": ["S01", "S03", "S05", "S07"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "<n> unit passed, migration-check PASS, 0 failed",
  "missing_requirements": [],
  "notes": "AC1..AC5 demonstrations cross-referenced above."
}
```

- `missing_requirements`: each missing AC demonstration is automatically a CRITICAL finding.
- `cross_cutting: true` on findings that span steps.

## Lifecycle Commands

```bash
uv run iw step-start I-00112 --step S09
uv run iw step-done I-00112 --step S09 --report ai-dev/active/I-00112/reports/I-00112_S09_CodeReview_Final_report.md
```
