# F-00086_S09_CodeReview_Final_prompt

**Work Item**: F-00086 -- Multi-tab AI Assistant on OpenCode
**Review Step**: S09 (Final Review)
**Implementation Steps Reviewed**: S01..S08

---

## ⛔ Docker is off-limits

(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy.)

## Input Files

- **Runtime step state** — `uv run iw item-status F-00086 --json`.
- `ai-dev/active/F-00086/F-00086_Feature_Design.md` — design document
- All implementation step reports: `ai-dev/active/F-00086/reports/F-00086_S0[1,3,6,7,8]_*_report.md`
- All per-agent code review reports: `ai-dev/active/F-00086/reports/F-00086_S04_CodeReview_report.md`
- All fix reports if present: `ai-dev/active/F-00086/reports/F-00086_S05_CodeReview_FIX_report.md`
- All files listed across every implementation report's `files_changed`

## Output Files

- `ai-dev/active/F-00086/reports/F-00086_S09_CodeReview_Final_report.md`

## Context

You are performing the **final cross-agent review** of F-00086. Per-agent reviews caught individual-step issues; your job is integration: does the schema in S01 line up with the ORM model used in S03, the API contract in S06, the JS payload shape in S07, and the test assertions in S08?

## Read the Design Document FIRST

- Read §Acceptance Criteria (AC1..AC8) in full.
- Read §Invariants (1..8) in full.
- Read §TDD Approach in full and note every test file the design names.

Cross-check every test file named in §TDD Approach against the `files_changed` arrays of S01/S03/S06/S08. Any named test file that does not appear anywhere is a **CRITICAL** finding.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

Any NEW violation in S01..S08 changed files is a CRITICAL finding with `"category":"conventions"`.

## Review Checklist

### 1. Completeness vs Design

- Every endpoint listed in §API Changes is implemented (11 new + 1 modified + 7 removed)? Use `grep -E "@router\.(get|post|patch|delete)" dashboard/routers/chat.py` to enumerate.
- Every column listed in §Database Changes exists on the `chat_tabs` table and on the `ChatTab` ORM model? Cross-check the migration file against `orch/db/models.py`.
- Every UI element listed in §Frontend Changes exists (tab strip, create-tab modal, recent-closed dropdown, soft-cap banner, per-tab model dropdown)?
- Every test file named in §TDD Approach exists?
- **No TODO/placeholder code.** Grep for `TODO`, `FIXME`, `XXX`, `pass  #`, `raise NotImplementedError` in S01..S08 changed files outside of strictly-defined abstract methods.

### 2. Schema ↔ ORM ↔ API ↔ JS payload alignment

Trace one field — `tab_id` — end-to-end:
- DB column type: UUID
- ORM: `Mapped[UUID]`
- API response: serialized as string
- JS: consumed as string

Repeat for `status`, `runtime`, `model`, `opencode_session_id`, `last_active_at`, `closed_at`. Any type mismatch (e.g., timestamp serialized differently between two endpoints) is a HIGH finding.

### 3. Invariants enforced by tests

For each invariant 1..8 in the design, locate the test that proves it. If you cannot point to one specific test for an invariant, that is a CRITICAL finding.

| Invariant | Expected test |
|-----------|---------------|
| 1. ABC method parity | `tests/unit/chat/test_opencode_runtime_abc_compliance.py` |
| 2. tab_id in every relayed event | `tests/integration/test_chat_tabs_multi_session_independence.py` |
| 3. Runtime allowlist enforcement | `tests/integration/test_chat_tabs_api.py::test_post_tabs_rejects_unknown_runtime` |
| 4. Soft-cap header iff count > 10 | `tests/integration/test_chat_tabs_api.py::test_post_tabs_soft_cap_header_on_eleventh` |
| 5. Soft-delete preserves session id | `tests/unit/chat/test_tab_service.py::test_close_tab_is_idempotent` (or sibling) |
| 6. Bootstrap idempotency | `tests/integration/test_chat_tabs_bootstrap_default.py` (concurrent case) |
| 7. No old endpoint paths | `tests/integration/test_chat_tabs_api.py::test_no_legacy_session_endpoints` |
| 8. Empty-body PATCH does not bump updated_at | `tests/integration/test_chat_tabs_api.py::test_patch_tabs_empty_body_does_not_bump_updated_at` |

### 4. Cross-agent consistency

- `RelayManager` is imported from `orch.chat.opencode` everywhere outside the subpackage itself — flag any remaining import of `orch.chat.relay_manager` (HIGH).
- The frontend's tab list dispatch uses `event.tab_id` from the SSE payload, not `event.session_id` or anything else.
- The API's PATCH handler delegates to `tab_service.update_tab` and does NOT itself bump `updated_at` (invariant #8 enforcement must live in one place).

### 5. Integration points

- `bootstrap_default_tab` is wired into the `GET /api/chat/tabs` handler (not at app startup). Confirm by tracing `dashboard/routers/chat.py` and `dashboard/app.py`.
- The `pgcrypto` extension (or Python-side `uuid.uuid4` default) is consistently chosen — the migration's choice must match the ORM model's default. A divergence here is a HIGH finding (would cause INSERTs from non-API paths to fail).
- The `uq_chat_tabs_default_per_project` partial unique index is created by S01 AND relied on by `bootstrap_default_tab` for race safety. Confirm both halves agree on the same WHERE clause.

### 6. Test coverage holism

- Every acceptance criterion AC1..AC8 has at least one test covering it. Map test → AC explicitly in your report.
- The "No Regressions" coverage: adapted tests in S08 cover the same behavioural surface the original tests covered. Compare the count of test functions before and after — they should be approximately equal (a drop > 10% needs explanation).

### 7. Security (cross-cutting)

- No hardcoded credentials, model API keys, or secrets in any new file.
- Input validation at the API boundary (Pydantic schemas catch type errors; tab_service catches allowlist violations).
- No SQL injection vectors — the new tab_service uses ORM, not raw `text()` queries (verify).

## Test Verification (NON-NEGOTIABLE)

Run **targeted** tests covering the F-00086 surface — the full-suite execution is owned by downstream QV gates S14 (`make test-unit`) and S15 (`make test-integration`). Duplicating them here wastes ~30 minutes and risks an I-00073-style timeout.

```bash
uv run pytest tests/unit/chat/ -v
uv run pytest tests/integration/test_chat_tabs_*.py -v
uv run pytest tests/dashboard/test_chat_*.py tests/integration/test_chat_endpoint_*.py -v
```

Report results. Any failure in these targeted runs is a CRITICAL finding (downstream QV gates will catch broader regressions).

## Review Result Contract

```json
{
  "step": "S09",
  "agent": "code-review-final-impl",
  "work_item": "F-00086",
  "steps_reviewed": ["S01", "S03", "S06", "S07", "S08"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|integration|testing|architecture|security",
      "file": "",
      "line": 0,
      "description": "",
      "suggestion": "",
      "cross_cutting": true
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "targeted: X unit/chat passed, Y integration/test_chat_tabs_* passed, Z adapted dashboard/test_chat_* passed",
  "missing_requirements": [],
  "notes": ""
}
```
