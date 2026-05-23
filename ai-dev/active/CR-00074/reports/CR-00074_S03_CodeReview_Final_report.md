# CR-00074 — S03 Final Review Report

**Work Item**: CR-00074 — Cross-Project Isolation Test Matrix
**Step**: S03 (code-review-final-impl)
**Reviewing**: S01 (backend-impl) + S02 (code-review-impl)
**Status**: **PASS** — zero CRITICAL, zero HIGH, zero MEDIUM (fixable)

---

## Pre-Flight Quality Gates

| Check | Command | Result |
|-------|---------|--------|
| Lint | `make lint` | ✅ All checks passed (ruff + Jinja2 templates) |
| Format | `make format-check` | ✅ 849 files already formatted |
| Unit tests | `make test-unit` | ✅ 3384 passed, 5 skipped, 5 xfailed, 2 xpassed in 83.89s |
| Isolation matrix | `make test-isolation` | ✅ **14 passed in 13.88s** (5 Axis 1 · 3 Axis 2 · 2 Axis 3 · 4 Axis 4; 0 xfailed, 0 failed) |

---

## Scope Discipline

| Check | Result |
|-------|--------|
| No production code edited | ✅ `git diff origin/main -- dashboard/ orch/ executor/ scripts/` → empty |
| No residual deliberate-break injection | ✅ Both TDD injections (route-filter removal + `get_orch_db_url()` break) fully reverted |
| No migration file added | ✅ No migration files in the changeset |
| Skills master copy synced | ✅ `.claude/skills/iw-ai-core-testing/SKILL.md` byte-identical to `skills/iw-ai-core-testing/SKILL.md` |
| No new canonical QV gate added | ✅ `skills/iw-workflow/SKILL.md` not modified — `test-isolation` is a convenience target, not a daemon gate |

---

## Files Changed

All files are within `scope.allowed_paths`. No production code touched.

| File | Action | Purpose |
|------|--------|---------|
| `tests/integration/test_cross_project_isolation.py` | Create | Isolation matrix — 14 test cases across 4 axes |
| `tests/fixtures/dual_project_seed.py` | Create | `seed_two_projects` / `TwoProjects` / `ProjectIds` / `SHARED_SEARCH_KEYWORD` |
| `tests/fixtures/__init__.py` | Create | Package init for `tests/fixtures/` |
| `tests/integration/conftest.py` | Modify | `second_project` fixture (function-scoped, additive to `test_project`) |
| `Makefile` | Modify | `test-isolation` target + added to `.PHONY` |
| `docs/IW_AI_Core_Testing_Strategy.md` | Modify | §2 Layer 6 + §5 gate row + §9 known-gap row flipped |
| `skills/iw-ai-core-testing/SKILL.md` | Modify | §3 "Cross-project isolation" extended |
| `.claude/skills/iw-ai-core-testing/SKILL.md` | Modify | Re-synced (byte-identical to master confirmed) |
| `ai-dev/work/TESTS_ENHANCEMENT.md` | Modify | Item 3.4 → DONE 2026-05-21 (CR-00074); §11 changelog |

---

## Acceptance Criteria Verification

### AC1 — `second_project` fixture and dual-project seeding

✅ Function-scoped fixture; preserves `pgtestdbpy` template-clone isolation.
✅ Both projects seeded: `WorkItem`, `Batch`, architecture `ProjectDoc`, research `ProjectDoc`, `CodeIndexJob`, `DocGenerationJob`.
✅ Distinct identifiers: `WI-ALPHA-001`/`WI-BETA-001`, `BATCH-ALPHA-001`/`BATCH-BETA-001`, etc.
✅ `SHARED_SEARCH_KEYWORD` in both projects' work items and docs — FTS-backed surfaces have real data.
✅ Project A reused from existing `test_project` fixture — existing tests unaffected.
✅ `tests/fixtures/__init__.py` created (package init).

### AC2 — Dashboard-route isolation matrix

✅ `TestClient` + `app.dependency_overrides[get_db]` per `test_jobs_filter_ui.py` pattern.
✅ `IW_CORE_EXPECTED_INSTANCE_ID` popped from env.
✅ Positive assertion: project B's own identifier renders (proves route returned real data).
✅ Negative assertion: none of project A's distinguishing identifiers in response body.
✅ 5 routes parametrized one-per-case: `/queue`, `/batches`, `/docs`, `/jobs`, `/research`.
✅ `KNOWN_LEAK` empty — no genuine leaks on `main`; 0 Incidents filed.
✅ Scope note correctly excludes detail routes.

### AC3 — `iw`-command isolation assertions

✅ **Read commands** (`search`, `item-status`): output isolation — no project A identifiers in project-B-scoped output.
✅ **Mutating command** (`doc-update`): mutation isolation — project A's `ProjectDoc` rows byte-for-byte unchanged (id/title/slug/content/version/updated_at snapshot); project B's doc created.
✅ `iw next-id` correctly excluded — `id_sequences` is a global per-prefix allocator.
✅ Isolation mode labelled in parametrize ID.
✅ No global `iw` commands included.

### AC4 — Global-aggregation positive assertion

✅ `/docs` page + `/api/docs/search` both surface project A and project B identifiers.
✅ Positive-assertion cases labelled `aggregation_check-*`.
✅ No global `/jobs` route — correctly documented.

### AC5 — Per-worktree-DB vs orch-DB boundary (F-00062)

✅ Exercises `orch/config.py` resolution, not two unrelated sessions.
✅ Two distinct testcontainer Postgres DBs; `get_db_url()` / `get_orch_db_url()` resolve to distinct URLs.
✅ Sessions see only their own marker rows.
✅ `_prefer` fallback tested (orch env unset → falls back to `IW_CORE_DB_*`).
✅ I-00062 agent-context guard tested.
✅ `monkeypatch.setenv` exclusively — no `importlib.reload`.
✅ `boundary_databases` module-scoped (immutable containers, no cross-test mutation).

### AC6 — KNOWN_LEAK allowlist + TDD RED evidence

✅ `KNOWN_LEAK` module-level dict keyed by route/command — empty; 0 Incidents filed.
✅ `_xfail_marks` helper auto-attaches `xfail(strict=True)` for any future entry.
✅ TDD RED evidence fully documented in S01 report:
  - Axis 1: `_queue_items` filter removed → `ISOLATION LEAK: /project/second-proj/queue leaked WI-ALPHA-001` → reverted.
  - Axis 4: `get_orch_db_url()` made to return `get_db_url()` → boundary case failures → reverted.

### AC7 — Docs / skill / plan

✅ Strategy doc §2 Layer 6 + §5 gate table row + §9 row flipped.
✅ `skills/iw-ai-core-testing/SKILL.md` matrix sub-section added + synced.
✅ `.claude/skills/iw-ai-core-testing/SKILL.md` byte-identical to master (diff exit 0).
✅ `ai-dev/work/TESTS_ENHANCEMENT.md` item 3.4 → DONE + §11 changelog.

---

## Test Effectiveness (Holistic)

✅ All 14 tests use `db_session` fixture — never the live DB.
✅ `second_project` function-scoped — no shared state across tests.
✅ Axis 4 module-scoped containers are immutable — order-independent under `pytest-randomly`.
✅ All assertions are behavioural: check specific identifier presence/absence, not just HTTP status codes.
✅ No vacuous assertions (e.g., "status == 200" alone is never used as an isolation check).
✅ TDD RED evidence confirms the matrix can fail — proven by S01.

---

## Architecture & Security

✅ Tests follow established `tests/integration/` patterns (testcontainer + SQLAlchemy session).
✅ No hardcoded secrets, URLs, credentials, or port numbers in test files or fixtures.
✅ `KNOWN_LEAK` empty — 0 genuine leaks found on `main`, 0 Incidents filed.
✅ No new daemon QV gate — matrix runs inside the existing `integration-tests` gate.

---

## Verdict

```json
{
  "step": "S03",
  "agent": "code-review-final-impl",
  "work_item": "CR-00074",
  "steps_reviewed": ["S01", "S02"],
  "verdict": "pass",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "3384 unit passed, 14 isolation matrix passed, 0 failed",
  "missing_requirements": [],
  "notes": "All 7 ACs fully satisfied. All 4 axes implemented as specified. Zero CRITICAL/HIGH/MEDIUM_FIXABLE findings. Test-only CR — no production code edited. No migration files. No residual TDD injection. Skills synced. Strategy doc and TESTS_ENHANCEMENT updated. CR-00074 is safe to merge."
}
```
