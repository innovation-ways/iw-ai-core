# CR-00076 — S02 CodeReview report

**Work Item**: CR-00076 — Data-Layer Test Module — Migrations, FTS, DB Identity
**Step**: S02 (code-review-impl)
**Date**: 2026-05-22
**Reviewer**: code-review-impl

---

## Review scope

S01 is a test-infrastructure step. I reviewed: the design document (§Acceptance Criteria §TDD Approach), the S01 report, and all four new test modules plus the Makefile, docs, skill, and plan changes.

---

## Pre-flight gates (NON-NEGOTIABLE)

| Gate | Result |
|------|--------|
| `make lint` | ✅ All checks passed |
| `make format-check` | ✅ 839 files already formatted |
| `make test-assertions` | ✅ No new assertion-scanner violations (531 files scanned) |
| `git diff origin/main -- orch/db/migrations/` | ✅ Empty — no migration file created |
| `git diff origin/main -- orch/ dashboard/ executor/` | ✅ Empty — no production code touched |
| `git diff origin/main -- tests/integration/test_work_items_functional_doc_fts.py tests/integration/test_db_identity_integration.py tests/integration/test_migrations_round_trip.py` | ✅ Empty — existing files untouched |
| `.claude/skills/iw-ai-core-testing/SKILL.md` vs `skills/iw-ai-core-testing/SKILL.md` | ✅ Byte-identical (diff returned no output) |

---

## Acceptance Criteria review

### AC1 — FTS-trigger invariant (all tsvector columns)

**Verdict: PASS**

- `TSVECTOR_COLUMNS` in `test_fts_trigger_invariant.py` enumerates exactly 3 tuples: `work_items.design_doc_search`, `work_items.functional_doc_search`, `project_docs.content_search`. Confirmed exhaustive by spot-checking `orch/db/models.py` — `work_items` carries two tsvector columns, `project_docs` one.
- `db_session` fixture's template DB installs all FTS triggers via `alembic upgrade head` (per `_migrate_template` in `tests/integration/conftest.py`), so the test inherits them. No raw `create_all()` engine — correct path.
- Each parametrized case: INSERT → assert tsvector non-null and non-empty; UPDATE → assert tsvector non-null and contains the updated lexeme via `@@ to_tsquery` with exact row count `assert matched == 1`.
- `test_work_items_functional_doc_fts.py` confirmed NOT in S01's `files_changed`.
- **6 test cases** (3 columns × INSERT + UPDATE) all passed.

### AC2 — Revision-skew regression test

**Verdict: PASS**

- `test_upgrade_head_fails_on_bogus_revision`: stamps `alembic_version` at a random UUID-prefixed bogus revision ID absent from the graph, runs `alembic upgrade head`, asserts `alembic.util.exc.CommandError` with message starting `Can't locate revision identified by` and containing the bogus revision. Asserts on the **specific** exception type + message substring — not a bare `pytest.raises(Exception)`.
- `test_upgrade_head_succeeds_with_valid_head`: sanity-check — upgrades to a specific valid old revision (`824e6e6f34ee`), then `upgrade head` succeeds, proving the failure is specifically about *absent* revisions, not "behind head". Assertion is `assert new_head == script_head` — not tautological. The design flaw (re-upgrade over head schema) was fixed during S01 recovery.
- No skew guard added to `orch/daemon/migration_rebase.py` or anywhere in `orch/` — confirmed by `git diff origin/main -- orch/`.
- No `downgrade` calls in the module.
- **2 tests** both passed.

### AC3 — DB-identity invariants

**Verdict: PASS**

- Match path: `test_identity_check_match_path` and `test_verify_instance_identity_match_path_no_exception` — `monkeypatch.setenv` to actual fingerprint, assert `status.mode == "match"`, no exception.
- Mismatch path: `test_identity_check_mismatch_path` and `test_verify_instance_identity_mismatch_raises` — `monkeypatch.setenv` to a different UUID, assert `status.mode == "mismatch"`, assert `InstanceMismatchError` raised with message containing "mismatch" (specific exception, not bare `Exception`).
- Bootstrap path: `test_identity_check_bootstrap_path` and `test_verify_instance_identity_bootstrap_no_exception` — `monkeypatch.delenv`, assert `status.mode == "bootstrap"`.
- Missing row: `test_verify_instance_identity_missing_row_with_env_raises` — deletes the row, sets env, asserts `InstanceRowMissingError`.
- `monkeypatch.setenv/delenv` used exclusively — no `importlib.reload(orch.config)`.
- `test_db_identity_integration.py` confirmed NOT in S01's `files_changed`.
- **7 tests** all passed.

### AC4 — `make data-layer-check`

**Verdict: PASS**

- Makefile has `data-layer-check` target with `migration-check` as prerequisite.
- Target runs `uv run pytest tests/integration/data_layer/ -v --no-cov`.
- `data-layer-check` is listed in `.PHONY`.
- Existing `migration-check` target unchanged.
- `make data-layer-check` exits 0 with 3 migration-check + 15 data-layer = **18 passed, 0 failed**.

### AC5 — No migration / scope / existing gates

**Verdict: PASS**

- `git diff origin/main -- orch/db/migrations/` empty → **CRITICAL** if not, and it is clean.
- `git diff origin/main -- orch/ dashboard/ executor/` empty → no production code touched.
- `git diff origin/main` shows changes only in: `.claude/skills/iw-ai-core-testing/SKILL.md`, `Makefile`, `ai-dev/work/TESTS_ENHANCEMENT.md`, `docs/IW_AI_Core_Testing_Strategy.md`, `skills/iw-ai-core-testing/SKILL.md` — all within `scope.allowed_paths`.
- `migration-check` (run as part of `data-layer-check`) still passes.

### AC6 — Docs / skill / plan and tdd_red_evidence

**Verdict: PASS (with note)**

- `docs/IW_AI_Core_Testing_Strategy.md`: §2 (Layer 2 sub-package note), §5 (data-layer-check row in gate table), §9 (item 3.6 → ✅ DONE) — all updated.
- `skills/iw-ai-core-testing/SKILL.md`: new §2 sub-section "Data-layer test package" with table + extending instructions.
- `.claude/skills/iw-ai-core-testing/SKILL.md`: byte-identical to master (confirmed by `diff`).
- `ai-dev/work/TESTS_ENHANCEMENT.md`: item 3.6 status flipped to **DONE 2026-05-21 (CR-00076)** with full changelog entry in §11; counts match S01 report (15 tests, 0 xfail, 0 failed).
- **tdd_red_evidence note**: S01's report describes two genuine RED captures (the `DuplicateTable` re-upgrade failure and the `NameError` + assertion exercise path), plus the FTS assertion strength verified via the assertion scanner. A full deliberate-break-then-revert cycle (dropping a trigger and confirming FTS test fails) was *not* re-run during manual recovery, with the scanner gate used as proxy verification. **Finding: MEDIUM (suggestion)** — the S01 report is transparent about this, and the scanner is a valid proxy. However, future reviews should prefer an actual captured failing output for clarity. No mandatory fix here — the tests are structurally sound and would fail against a missing trigger.

---

## Test quality & isolation

- All 15 tests use the testcontainer `db_session` fixture — never the live DB.
- Tests are order-independent (random seed `3625524652` produced a clean run; second `data-layer-check` run used seed `2141784402` — both clean).
- Assertions are behavioural and strong:
  - FTS: exact-count `@@ to_tsquery` assertion (`assert matched == 1`) is mutation-killing — fails if trigger leaves stale tsvector.
  - Skew: asserts on `CommandError` type + message prefix + bogus revision in message.
  - Identity: asserts on specific `IdentityStatus.mode` strings and specific exception types (`InstanceMismatchError`, `InstanceRowMissingError`), not bare `Exception`.
- No `xfail` entries — no genuine data-layer bug surfaced on `main`.

---

## Test verification (NON-NEGOTIABLE)

```
$ uv run pytest tests/integration/data_layer/ -v --no-cov
15 passed in ~19s (randomly-seed=3625524652)

$ make data-layer-check
3 (migration-check) + 15 (data_layer) = 18 passed in ~28s
exit 0
```

---

## Findings

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "CR-00076",
  "step_reviewed": "S01",
  "verdict": "pass",
  "findings": [
    {
      "severity": "MEDIUM_SUGGESTION",
      "category": "testing",
      "file": "ai-dev/work/CR-00076/reports/CR-00076_S01_Backend_report.md",
      "line": null,
      "description": "AC6 tdd_red_evidence: S01 report is transparent that a full deliberate-break-then-revert cycle was not re-run for the FTS module (proxy-verified via assertion scanner instead). This is acceptable given the report's transparency, but future CRs should capture an actual failing output for maximum clarity.",
      "suggestion": "No fix required for this CR — the tests are structurally sound and would fail against a missing trigger. For future test-infrastructure CRs, include an actual captured failing output in tdd_red_evidence."
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "18 passed, 0 xfailed, 0 failed (3 migration-check + 15 data_layer/); make data-layer-check exit 0",
  "notes": "S01 had a difficult delivery (pi/MiniMax-M2.7 context-window exhaustion, manual operator recovery, two defects corrected during recovery). All three defects described in the S01 report were legitimate: tautology assertion, broken re-upgrade design, orphaned assertion-free baseline entries. All corrected. The delivered code is clean and complete."
}
```

---

## Summary

S01 is **PASS**. Zero CRITICAL or HIGH findings. Zero MEDIUM (fixable) findings. One MEDIUM (suggestion) — the tdd_red_evidence for the FTS module was proxy-verified via the assertion scanner rather than a full deliberate-break capture; the report is transparent about this, and no mandatory fix is required. All six acceptance criteria are satisfied. All pre-flight gates green. `make data-layer-check` exits 0 with 18 tests passing.