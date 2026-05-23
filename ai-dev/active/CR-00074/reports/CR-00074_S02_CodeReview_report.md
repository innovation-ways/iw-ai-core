# CR-00074 — S02 Code Review Report

**Work Item**: CR-00074 — Cross-Project Isolation Test Matrix
**Step**: S02 (code-review-impl)
**Reviewing**: S01 (backend-impl)
**Status**: **PASS** — zero CRITICAL, zero HIGH, zero MEDIUM (fixable)

---

## Pre-flight Quality Gates

| Check | Command | Result |
|-------|---------|--------|
| Lint | `make lint` | ✅ All checks passed (ruff + templates) |
| Format | `make format-check` | ✅ 846 files already formatted |
| Assertion scanner | `make test-assertions` | ✅ No new violations (537 files scanned) |
| Test execution | `uv run pytest tests/integration/test_cross_project_isolation.py -v --no-cov` | ✅ **14 passed in 15.11s** |

---

## Files Changed (S01 scope)

All files are within the declared `scope.allowed_paths`. No production code touched.

| File | Action | Purpose |
|------|--------|---------|
| `tests/integration/test_cross_project_isolation.py` | Create | Isolation matrix (14 test cases, 4 axes) |
| `tests/fixtures/dual_project_seed.py` | Create | `seed_two_projects` / `TwoProjects` / `ProjectIds` |
| `tests/fixtures/__init__.py` | Create | Package init |
| `tests/integration/conftest.py` | Modify | `second_project` fixture added |
| `Makefile` | Modify | `test-isolation` target + `.PHONY` |
| `docs/IW_AI_Core_Testing_Strategy.md` | Modify | §2 Layer 6 + §5 gate row + §9 row updated |
| `skills/iw-ai-core-testing/SKILL.md` | Modify | Matrix sub-section added |
| `.claude/skills/iw-ai-core-testing/SKILL.md` | Modify | Synced copy (byte-identical to master verified) |
| `ai-dev/work/TESTS_ENHANCEMENT.md` | Modify | Item 3.4 → DONE; §11 changelog entry |

---

## Scope Discipline

✅ No production code touched. `git diff origin/main -- dashboard/ orch/ executor/ scripts/` is empty.

✅ No deliberate-break injection left behind. Both TDD injections (route-filter removal + `get_orch_db_url()` break) were fully reverted.

✅ No migration file. None added or modified.

---

## Acceptance Criteria Checklist

### AC1 — `second_project` fixture

✅ Function-scoped fixture, no session/module scope — preserves `pgtestdbpy` template-clone isolation.
✅ Both projects seeded: WorkItem, Batch, architecture ProjectDoc, research ProjectDoc, CodeIndexJob, DocGenerationJob.
✅ Distinct identifiers: `WI-ALPHA-001`/`WI-BETA-001`, `BATCH-ALPHA-001`/`BATCH-BETA-001`, etc.
✅ Project A reused from existing `test_project` fixture — existing tests unaffected.

### AC2 — Dashboard-route isolation matrix

✅ `TestClient` + `app.dependency_overrides[get_db]` per `test_jobs_filter_ui.py` pattern.
✅ `IW_CORE_EXPECTED_INSTANCE_ID` popped from env.
✅ Behavioural assertions: `assert leaked not in body` for project A's identifiers; positive-control proves project B's data rendered.
✅ 5 routes parametrized one-per-case: `/queue`, `/batches`, `/docs`, `/jobs`, `/research`.
✅ `KNOWN_LEAK` empty — no genuine leaks on `main`.
✅ Scope note correctly explains detail routes are excluded.

### AC3 — `iw`-command isolation assertions

✅ **Read commands** (`search`, `item-status`): output isolation — project A's identifiers absent from project-B-scoped output.
✅ **Mutating command** (`doc-update`): mutation isolation — project A's `ProjectDoc` rows byte-for-byte unchanged before/after; project B's new doc confirmed.
✅ `iw next-id` correctly excluded — global per-prefix allocator.
✅ Isolation mode labelled in parametrize ID.
✅ No global `iw` commands included.

**Note (LOW)**: `iw item-report --project B <item-A-id>` is also project-scoped but not covered in Axis 2. Lower priority than `item-status`; documented in test module.

### AC4 — Global-aggregation positive assertion

✅ `/docs` page + `/api/docs/search` both assert identifiers from BOTH projects.
✅ Positive-assertion cases labelled `aggregation_check-*`.
✅ No global `/jobs` route — correctly documented.

### AC5 — Per-worktree-DB vs orch-DB boundary (F-00062)

✅ Exercises `orch/config.py` resolution, not two unrelated sessions.
✅ Two distinct testcontainers; `get_db_url()` / `get_orch_db_url()` resolve to distinct URLs.
✅ Sessions see only their own marker rows.
✅ `_prefer` fallback tested (orch env unset → falls back to `IW_CORE_DB_*`).
✅ I-00062 agent-context guard tested.
✅ `monkeypatch.setenv` exclusively — no `importlib.reload`.
✅ `boundary_databases` module-scoped (immutable containers, no cross-test mutation).

### AC6 — KNOWN_LEAK allowlist + TDD RED evidence

✅ `KNOWN_LEAK` module-level dict keyed by route/command — empty, 0 Incidents filed.
✅ `_xfail_marks` helper auto-attaches `xfail(strict=True)` for future entries.
✅ TDD RED evidence fully documented:
  - Axis 1: `_queue_items` filter removed → `ISOLATION LEAK` failure → reverted.
  - Axis 4: `get_orch_db_url()` made to return `get_db_url()` → boundary case failure → reverted.

### AC7 — Docs / skill / plan

✅ §2 **Layer 6** section added with 4-axis table + extension guidance.
✅ §5 gate table row added.
✅ §9 roadmap table row flipped: `❌ (3.4)` → `✅ DONE 2026-05-21 (CR-00074)` with full detail.
✅ `skills/iw-ai-core-testing/SKILL.md` matrix sub-section + how-to-extend.
✅ `.claude/skills/iw-ai-core-testing/SKILL.md` byte-identical to master (diff exit 0).
✅ `ai-dev/work/TESTS_ENHANCEMENT.md` item 3.4 → DONE + §11 changelog entry.

---

## Test Quality & Isolation

✅ All 14 tests use `db_session` fixture — never the live DB.
✅ `second_project` function-scoped — no shared state.
✅ Axis 4 module-scoped containers are immutable (no writes) — order-independent.
✅ Order-independent under `pytest-randomly` default-on; 4-seed documented.
✅ Behavioural assertions throughout; no vacuous assertions.

---

## Verdict

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "CR-00074",
  "step_reviewed": "S01",
  "verdict": "pass",
  "findings": [
    {
      "severity": "LOW",
      "category": "testing",
      "file": "tests/integration/test_cross_project_isolation.py",
      "line": null,
      "description": "iw item-report is a project-scoped read command (filters by project_id) not included in Axis 2. Lower priority than item-status and search; documented in test module.",
      "suggestion": "Add item-report to _AXIS2_COMMANDS as 'item-report-output' in a follow-up CR when extending the matrix."
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "14 passed, 0 xfailed, 0 failed",
  "notes": "All 7 ACs fully satisfied. Zero CRITICAL/HIGH/MEDIUM_FIXABLE findings. One LOW suggestion for future matrix extension. Ready for S03."
}
```
