# CR-00075 S01 — Backend Implementation Report

**Work Item**: CR-00075 — Security Test Module
**Step**: S01 (backend-impl)
**Status**: complete
**Date**: 2026-05-21

## What was done

Implemented the full security test package `tests/integration/security/` — four
asserted regression modules covering distinct security risk classes — plus the
Makefile target, strategy-doc, skill, and plan updates. **Strictly test-only:
no production code (`orch/`, `dashboard/`, `executor/`, `scripts/`) was edited.**

This run inherited partial work from earlier S01 attempts and **corrected two
defects in it** before completing:

1. **`tests/assertion_free_baseline.txt` was reverted to `origin/main`.** A prior
   run had baseline-exempted 17 of the new security tests as `no-assert` /
   `tautology`. That defeats the assertion scanner. Instead, every weak test was
   rewritten to carry a real behavioural assertion; the baseline file is now
   unchanged from `main`.
2. **`test_authz_negative_paths.py` was rewritten.** The prior version used
   **stale chat endpoint paths** (`/api/chat/create-tab/{id}`, `/api/chat/tab/{id}`)
   that 404 as "route not found" — fake-passing tests. It also had a tautological
   `assert 200 <= status < 600` and accepted `5xx` (violating AC2). The rewrite
   uses the real tab-scoped endpoints and an exact-status-code + cross-project
   no-leak assertion model.

### Modules delivered (`tests/integration/security/`)

| Module | Tests | Covers |
|--------|------:|--------|
| `__init__.py` | — | Package marker (docstring only) |
| `test_live_db_write_guard.py` | 11 | I-00041 class: `is_live_db_url()` classification; `safe_create_engine()` / `assert_engine_url_allowed()` **raise** `LiveDbConnectionRefusedError` in test-collection context (`IW_CORE_TEST_CONTEXT`) and agent-worktree context (`IW_CORE_AGENT_CONTEXT`); operator/daemon opt-in positive controls. Live-DB URL simulated via env-var injection — port 5433 never contacted. |
| `test_authz_negative_paths.py` | 18 | Project-scoping authz boundary (the dashboard has no credential layer): unknown-project → 404 on items/batches/docs/jobs/code-QA; **cross-project isolation** (project B's work item is 404 + non-leaking via project A's URL, with a positive control); unknown-resource-in-valid-project → 404; chat guards (unknown `tab_id` → 404, off-allowlist runtime → 400, missing `project_id` → 422). `TestClient(raise_server_exceptions=True)` so any 5xx fails the test. |
| `test_doc_render_ssrf_path_traversal.py` | 49 | `DocService._is_ssrf_blocked()` against localhost / 127.x / 10.x / 172.16–31.x / 192.168.x / `.local` / `.internal` / `::1` / `file://`; `validate_links()` reports internal URLs as `blocked_ssrf` (mocked `httpx`, asserted never called with an internal URL); `split_by_sections` / `extract_sections` keep path-traversal strings verbatim as inert data. |
| `test_agent_context_env_handling.py` | 7 | `IW_CORE_AGENT_CONTEXT=true` blocks `iw migrations apply` (exit 2) and `safe_create_engine()` (explicit raise with remediation message); refusal signal is exact-string `"true"` (`True` / `1` / `""` documented as not-the-signal); guard re-reads the live env var within one invocation (no stale caching). |

**Total: 85 security tests — 85 passed, 0 xfailed, 0 failed.**

### Other deliverables

- **Makefile** — `test-security-module` target + `.PHONY` entry; comment block
  explicitly distinguishes it (asserted pytest tests) from `make security-secrets`
  (gitleaks) and `make security-sast` (Semgrep/bandit) advisory scanners.
- **`docs/IW_AI_Core_Testing_Strategy.md`** — §2 Layer 5 table + description, §5
  gate-table row, §9 gap row flipped to ✅; inventory counts refreshed (~85 / 4).
- **`skills/iw-ai-core-testing/SKILL.md`** — §10 security-module section (coverage,
  extension pattern, genuine-vulnerability protocol). `iw sync-skills --force
  iw-ai-core-testing` confirmed — `.claude/skills/iw-ai-core-testing/SKILL.md` is
  byte-identical to the master.
- **`ai-dev/work/TESTS_ENHANCEMENT.md`** — item 3.5 → `DONE 2026-05-21 (CR-00075)`;
  §11 changelog entry with accurate per-module counts.

## Files changed

- `tests/integration/security/__init__.py` (new)
- `tests/integration/security/test_live_db_write_guard.py` (new)
- `tests/integration/security/test_authz_negative_paths.py` (new)
- `tests/integration/security/test_doc_render_ssrf_path_traversal.py` (new)
- `tests/integration/security/test_agent_context_env_handling.py` (new)
- `Makefile` (modified)
- `docs/IW_AI_Core_Testing_Strategy.md` (modified)
- `skills/iw-ai-core-testing/SKILL.md` (modified)
- `.claude/skills/iw-ai-core-testing/SKILL.md` (modified — synced)
- `ai-dev/work/TESTS_ENHANCEMENT.md` (modified)
- `tests/assertion_free_baseline.txt` (reverted to `origin/main` — net no change)

## Test results

- `make test-security-module` → **85 passed** (~11 s).
- Order-independent under `pytest-randomly` — verified green on seeds 12345,
  67890, 42424 and `-p no:randomly`.
- Collection: all four modules collected by the default integration run
  (85 tests, no marker exclusion) — they run automatically under
  `make test-integration` (QV gate S09).

## "Every test must be able to fail" — deliberate-break demonstrations

Each module was proven able to fail by a deliberate break of the production
code it guards, then reverted. `git status` confirmed clean after every revert.

1. **Live-DB guard** — patched `is_live_db_url()` → always `False`;
   `test_live_db_write_guard.py` → **5 failed** (`DID NOT RAISE`). Reverted.
2. **Doc-render SSRF** — patched `DocService._is_ssrf_blocked()` → always `False`;
   `test_doc_render_ssrf_path_traversal.py` → **26 failed**. Reverted.
3. **Authz** — dropped the `project_id` filter in `items._get_item_or_404`;
   `test_cross_project_item_is_not_reachable` → **failed** (`assert 200 == 404` —
   project B's item leaked through project A's URL). Reverted.
4. **Agent-context** — disabled the `IW_CORE_AGENT_CONTEXT` check in
   `assert_engine_url_allowed`; `test_agent_context_env_handling.py` →
   **3 failed**. Reverted.

`grep -rn "DELIBERATE-BREAK"` over `orch/` `dashboard/` `tests/` → nothing;
`git status -- orch/ dashboard/ executor/ scripts/` → empty. No injection remains.

## Pre-flight quality gates

- `make format` / `ruff format --check` → 842 files already formatted.
- `make typecheck` (mypy `orch/` + `dashboard/`) → no issues (test files are not
  in mypy scope; no production code changed).
- `make lint` → all checks passed. (One fix during the run: ruff `S105` flagged
  a test constant named `_SECRET_TITLE` as a possible hardcoded password —
  renamed to `_PROJECT_B_MARKER`, false positive resolved.)
- `make test-assertions` → 0 new assertion-scanner violations (534 files);
  baseline file unchanged — no security test is baseline-exempt.

## SECURITY BLOCKERS

**None.** No genuine vulnerability was surfaced. Every guard assertion passes on
current `main`: the live-DB write guard fires in both test and agent contexts;
`_is_ssrf_blocked()` blocks every internal-URL / `file://` class tested;
`validate_links()` never fetches an internal URL; the doc-section functions
treat path-traversal strings as inert data; the agent-context guard blocks
`iw migrations apply` and live-DB engine creation. No `xfail`, no Incident, no
production fix required.

## Observations

- The dashboard has **no authentication / credential layer** — it is an internal
  operator tool. The authorization boundary is therefore *project scoping* (the
  `{project_id}` path segment). `test_authz_negative_paths.py` documents this in
  its module docstring and tests that boundary (unknown project, cross-project
  access, unknown resource). The coverage decision (which routes are in/out of
  scope, with rationale) is recorded in that docstring.
- An untracked nested directory `ai-dev/active/CR-00075/CR-00075/` (a duplicate of
  the CR's design files) exists from an earlier run's path mis-resolution. It is
  outside this CR's `scope.allowed_paths`, untracked, and harmless; left as-is
  since it was not created by this step.
