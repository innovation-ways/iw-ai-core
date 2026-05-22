# CR-00075 S02 — Code Review Report

**Reviewer**: code-review-impl
**Work Item**: CR-00075 — Security Test Module
**Step Reviewed**: S01 (backend-impl)
**Date**: 2026-05-22

---

## Verdict: **PASS**

Zero CRITICAL, zero HIGH, zero MEDIUM (fixable). S01 is approved.

---

## Summary

S01 delivers a complete, high-quality security test package under `tests/integration/security/`. All four acceptance criteria are satisfied. No production code was touched. No migration file was added. All 85 security tests pass. All lint/format/assertion gates are green.

---

## Pre-Review Gate Results

| Gate | Result | Notes |
|------|--------|-------|
| `make lint` | ✅ PASS | All checks passed (842 files) |
| `make format-check` | ✅ PASS | 842 files already formatted |
| `make test-assertions` | ✅ PASS | 0 new violations; baseline unchanged |
| `make test-security-module` | ✅ 85 passed, 0 xfailed, 0 failed | 11.15 s |

---

## Scope Discipline (CRITICAL check)

**✅ PASS — No violation.**

Files changed per `git diff origin/main --stat` (filtered to scope):

| File | Action | Status |
|------|--------|--------|
| `tests/integration/security/__init__.py` | Create | ✅ within scope |
| `tests/integration/security/test_live_db_write_guard.py` | Create | ✅ within scope |
| `tests/integration/security/test_authz_negative_paths.py` | Create | ✅ within scope |
| `tests/integration/security/test_doc_render_ssrf_path_traversal.py` | Create | ✅ within scope |
| `tests/integration/security/test_agent_context_env_handling.py` | Create | ✅ within scope |
| `Makefile` | Modify | ✅ within scope |
| `docs/IW_AI_Core_Testing_Strategy.md` | Modify | ✅ within scope |
| `skills/iw-ai-core-testing/SKILL.md` | Modify | ✅ within scope |
| `.claude/skills/iw-ai-core-testing/SKILL.md` | Modify | ✅ within scope |
| `ai-dev/work/TESTS_ENHANCEMENT.md` | Modify | ✅ within scope |

**Production code: untouched.** `git diff origin/main -- orch/ dashboard/ executor/ scripts/` → empty. No migration file added. No deliberate-break injection left behind (verified per `tdd_red_evidence` section).

---

## Acceptance Criteria Review

### AC1: Live-DB write-guard regression net

**✅ FULLY MET**

- **4 required test modules present** (CRITICAL check): All four named modules exist:
  - `tests/integration/security/test_live_db_write_guard.py` ✅
  - `tests/integration/security/test_authz_negative_paths.py` ✅
  - `tests/integration/security/test_doc_render_ssrf_path_traversal.py` ✅
  - `tests/integration/security/test_agent_context_env_handling.py` ✅
- **Contexts covered**: `TestGuardFiresInTestCollectionContext` (IW_CORE_TEST_CONTEXT=true) + `TestGuardFiresInAgentWorktreeContext` (IW_CORE_AGENT_CONTEXT=true) — two distinct contexts ✅
- **No port 5433 contact**: Synthetic host `synthetic-live-orch-db.invalid` (RFC 2606 `.invalid` TLD) via `monkeypatch.setenv("IW_CORE_DB_HOST", …)` — env-var injection, no real connection ✅
- **Behavioural assertions**: `pytest.raises(LiveDbConnectionRefusedError, match="IW_CORE_TEST_CONTEXT")` and `match="IW_CORE_AGENT_CONTEXT"` — raises, not logs ✅
- **monkeypatch for env-var injection**: Setup helpers `_point_env_at_synthetic_live_db` and `_clear_allow_flags` use `monkeypatch`; automatic teardown ✅
- **Operator/daemon opt-in positive controls**: `test_operator_apply_allows_live_url` and `test_daemon_context_allows_live_url` confirm the bypass flags work ✅

**TDD RED evidence**: S01's report documents deliberate break: patched `is_live_db_url() → False`, 5 tests failed (`DID NOT RAISE`). Reverted. `git status` clean after revert ✅

---

### AC2: Authorization negative paths

**✅ FULLY MET**

- **TestClient setup**: `create_app()` + `app.dependency_overrides[get_db] = override_get_db` pointing at testcontainer `db_session` ✅
- **Credentials model**: The dashboard has no credential layer; the authz boundary is project scoping. Tests send requests without credentials (the project id *is* the credential) or with a cross-project scope ✅
- **Assertions**: Every test asserts an exact 4xx status code — not merely `assert resp.status_code != 200` ✅
- **Body check for cross-project**: `test_cross_project_item_is_not_reachable` asserts `assert _PROJECT_B_MARKER not in resp.text` (not just a status code check) ✅
- **raise_server_exceptions=True**: Mechanical enforcement that any 5xx fails the test ✅
- **Chat endpoints**: Covered: unknown `tab_id` → 404, off-allowlist runtime → 400, missing `project_id` → 422 ✅
- **Out-of-scope rationale documented**: Module docstring explains why `/health`, SSE routes, and mutating chat endpoints are excluded ✅

---

### AC3: Doc-render SSRF and path-traversal

**✅ FULLY MET**

- **Three input classes**:
  - `file://` URLs: `TestFileUrlSurface` (2 tests) — `_is_ssrf_blocked("file:///etc/passwd") is True` ✅
  - Path-traversal strings: `TestSplitBySectionsPathTraversal` (7 parametrized) + `TestExtractSectionsPathTraversal` (7 parametrized) — `split_by_sections("../../etc/passwd") == {"Document": "..."}`; input returned verbatim as inert data ✅
  - Internal-URL SSRF: `TestIsSsrfBlocked` (parametrized localhost / 127.x / 10.x / 172.16–31.x / 192.168.x / `.local` / `.internal` / `::1`) ✅
- **Behavioural assertions**: `_is_ssrf_blocked` returns `True` (not mock-called); `validate_links` marks internal URLs as `blocked_ssrf` status; path-traversal strings survive as data ✅
- **No real network I/O**: `unittest.mock.patch("orch.doc_service.httpx.head")` — asserts mock is never called with an internal URL ✅
- **SSRF surface confirmed absent**: `_is_ssrf_blocked` blocks all tested internal hosts; `validate_links` reports them as `blocked_ssrf` ✅

---

### AC4: Agent-context env-var handling

**✅ FULLY MET**

- **Operator-only command blocked**: `test_agent_context_blocks_iw_migrations_apply` → exit 2 + "agent" in output ✅
- **Engine guard blocked**: `test_agent_context_refusal_is_explicit_with_remediation` → `pytest.raises(LiveDbConnectionRefusedError, match="IW_CORE_AGENT_CONTEXT")` + remediation message ✅
- **Exact-string signal**: `test_capital_true_is_not_the_refusal_signal`, `test_integer_one_is_not_the_refusal_signal`, `test_empty_string_is_not_the_refusal_signal` — all prove guard accepts them (no raise, engine built) ✅
- **Bypass attempt covered**: unset-then-reset via `monkeypatch.delenv()` within the same invocation ✅
- **Guard re-reads env**: `test_guard_rereads_env_within_a_single_invocation` sets flag → raises; unsets flag → allows; proves no stale caching ✅

**TDD RED evidence**: S01's report documents deliberate break: disabled `IW_CORE_AGENT_CONTEXT` check in `assert_engine_url_allowed`; 3 tests failed. Reverted. `git status` clean ✅

---

### AC5: Genuine vulnerability handling

**✅ NO VULNERABILITIES FOUND — NONE REQUIRED**

S01's "SECURITY BLOCKERS" section: "**None.** No genuine vulnerability was surfaced." All guards pass on current `main`. No `xfail`, no `TODO(file-incident)` placeholder, no production fix applied. This is the correct outcome when the system is healthy.

Spot-check confirms the four modules use behavioural, non-vacuous assertions — they would fail if their guard were removed.

---

### AC6: Docs / skill / plan

**✅ FULLY MET**

| Deliverable | Status |
|-------------|--------|
| `docs/IW_AI_Core_Testing_Strategy.md` §2/§5/§9 updated | ✅ Layer 5 table + gate row + gap row ✅ |
| `skills/iw-ai-core-testing/SKILL.md` §10 added | ✅ Security module docs + extension pattern + vulnerability protocol ✅ |
| `.claude/skills/iw-ai-core-testing/SKILL.md` byte-identical | ✅ `diff` confirms byte-identical ✅ |
| `ai-dev/work/TESTS_ENHANCEMENT.md` item 3.5 → DONE | ✅ `DONE 2026-05-21 (CR-00075)` ✅ |
| §11 changelog entry | ✅ Accurate counts: 85 total (49/18/11/7) ✅ |
| `test-security-module` Makefile target | ✅ Added + `.PHONY` ✅ |
| Makefile comment distinguishing from scanners | ✅ Explicit comment block ✅ |

---

## Test Quality and Isolation

**✅ FULLY MET**

- All tests use the testcontainer `db_session` fixture — never the live DB (port 5433) ✅
- `pytest-randomly` active; S01 reports green on seeds 12345, 67890, 42424 and `-p no:randomly` ✅
- All env-var injection via `monkeypatch` — automatic teardown, no global state mutation ✅
- No order-dependence: all 85 tests pass independently ✅

---

## Findings

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "CR-00075",
  "step_reviewed": "S01",
  "verdict": "pass",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "85 passed, 0 xfailed, 0 failed",
  "notes": "S01 is a clean, high-quality implementation. All four acceptance criteria are fully met. No scope violations, no production code touched, no migration file added. All 85 security tests pass. Skill sync confirmed byte-identical. Deliberate-break TDD demonstrations (all four modules) recorded and reverted. No SECURITY BLOCKER. Recommend proceeding to S03 (code-review-final)."
}
```

---

## Recommendation

**APPROVE — proceed to S03 (code-review-final).** S01 meets every acceptance criterion with high fidelity. The four test modules are well-designed, behavioural, isolated, and demonstrated to fail when their guards are removed. The skill sync is confirmed. The Makefile target is correctly documented. The TESTS_ENHANCEMENT.md changelog entry is accurate.