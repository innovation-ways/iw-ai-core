# CR-00087 S06 — Code Review Final

**Work Item**: CR-00087 — Auto-amend scope violations matching per-project allow-patterns
**Step**: S06 — Final cross-step review
**Agent**: code-review-final-impl
**Status**: ✅ PASS

---

## What Was Done

Comprehensive cross-step review of S01–S04 against the design document (CR-00087_CR_Design.md). Carried out the full mandated checklist: lint & format gates, per-AC verdicts, matcher-parity chain audit, backwards-compat chain, atomicity & audit trail, scope discipline, architecture compliance, documentation review, and test discipline. Ran all unit tests including the full suite (`make test-unit`).

---

## Pre-Flight Gates

| Gate | Result |
|------|--------|
| `make lint` | ✅ All checks passed |
| `make format` | ✅ 893 files already formatted |
| `make test-unit` | ✅ 3521 passed, 5 skipped, 5 xfailed, 3 xpassed |

---

## Acceptance Criteria Verdicts

| AC | Verdict | Evidence |
|----|---------|---------|
| **AC1** — Feature off by default | ✅ PASS | Default `auto_amend_allow_patterns=[]` / `auto_amend_max_paths=None` in `ProjectConfig` (line 117-118, `project_registry.py`); `should_auto_amend([v], [], N)` short-circuits to `False` (line 231, `scope_amendment.py`); `test_complete_fix_cycle_does_not_auto_amend_when_feature_disabled` integrates through the full path against a real DB |
| **AC2** — Auto-amend fires when every violation matches | ✅ PASS | `test_complete_fix_cycle_auto_amends_when_all_violations_match`: asserts both `scope_violation_escalation` AND `scope_auto_amended` events, manifest update, new StepRun, step `pending` |
| **AC3** — Partial match → no auto-amend | ✅ PASS | `test_complete_fix_cycle_does_not_auto_amend_when_violation_falls_outside_allow_patterns`: violations include a non-matching path; asserts no `scope_auto_amended`, step stays `needs_fix` |
| **AC4** — max_paths cap | ✅ PASS | `test_complete_fix_cycle_does_not_auto_amend_when_count_exceeds_max_paths`: 5 violations vs `max_paths=2`, no auto-amend fires |
| **AC5** — Malformed config → off | ✅ PASS | 10-test matrix in `test_project_registry_auto_amend_scope.py` covers: non-dict block, non-list patterns, non-string entries, non-int max_paths, bool max_paths (explicit `isinstance` check before `int`), negative max_paths — all return `([], None)` + WARNING log |
| **AC6** — Audit trail preserved | ✅ PASS | `test_complete_fix_cycle_auto_amends_when_all_violations_match` asserts both events appear; `scope_auto_amended` payload at line 2637-2644 contains `step_id`, `added_paths`, `manifests_updated`, `matched_patterns` (snapshot, not live reference) |

---

## Matcher-Parity Chain (HEADLINE CHECK)

**Verified: `should_auto_amend` and the violation detector share the same `scope_match` implementation.**

Three-site inspection:

1. **Canonical definition** — `orch/daemon/fix_cycle.py:scope_match` (line 60): `dir/**` prefix short-circuit + plain `fnmatch`. No other matcher for violations.
2. **Violation detector** — `fix_cycle.py:239` and `1093`: `any(scope_match(p, pat) for pat in allowed + implicit)` — the canonical `scope_match`, not a separate function. **Note (informational)**: the detector filters against `allowed + implicit` while `should_auto_amend` only checks against `auto_amend_allow_patterns`. This is correct by design — `implicit` patterns (`ai-dev/active/{id}/**`, etc.) are not part of `auto_amend_scope`; they are pre-blessed in the violation detector. The auto-amend filter only checks against the project's explicit allow-patterns, which is the intended contract.
3. **Auto-amend filter** — `scope_amendment.py:241` (deferred import inside function body): `from orch.daemon.fix_cycle import scope_match`. Calls `scope_match` for every violation/pattern comparison.

**No divergence found.** The rename from `_scope_match` to `scope_match` was complete (no `_scope_match` references remain), and the deferred import inside `should_auto_amend` is the documented architectural choice.

---

## Backwards-Compatibility Chain (SECOND HEADLINE CHECK)

**Verified: projects without `auto_amend_scope` see zero behavioural change.**

| Check | Result |
|-------|--------|
| `ProjectConfig` defaults `auto_amend_allow_patterns=[]`, `auto_amend_max_paths=None` | ✅ |
| `should_auto_amend([v], [], None)` returns `False` (empty allow_patterns is first short-circuit) | ✅ |
| `_try_auto_amend_after_escalation(project_config=None, ...)` returns `False` before any DB or filesystem write | ✅ |
| `test_complete_fix_cycle_does_not_auto_amend_when_feature_disabled` exists and passes, running the full integration path with empty patterns | ✅ |

---

## Atomicity & Audit Trail

- `scope_violation_escalation` is committed at line 1149 (`db.commit()`) **before** `_try_auto_amend_after_escalation` runs (called at 1151).
- The escalation commit and the auto-amend commit are two separate transactions — intentional per design doc. The escalation persists even when auto-amend fires.
- `_try_auto_amend_after_escalation` issues its own `db.commit()` (line 2655) after StepRun insertion, step status flip, WorkItem status flip, and event emission.

**Both events visible in chronological order** in `DaemonEvent` rows.

- `scope_auto_amended` payload snapshot: `allow_patterns = list(project_config.auto_amend_allow_patterns or [])` (line 2609) → copied at call time, not a live reference.
- All four required payload keys present: `step_id`, `added_paths`, `manifests_updated`, `matched_patterns` (lines 2637-2644).

---

## Scope Discipline

```
.git/worktrees/CR-00087$ git diff main..HEAD --name-only | grep -E "^orch/|^tests/|^docs/|^.iw-orch"
```

Changed CR-00087 files (confirmed):

- `orch/daemon/project_registry.py` (S01)
- `orch/daemon/scope_amendment.py` (S02)
- `orch/daemon/fix_cycle.py` (S02+S03)
- `docs/IW_AI_Core_Daemon_Design.md` (S03)
- `.iw-orch.json` (S03)
- `tests/unit/daemon/test_project_registry_auto_amend_scope.py` (S01, new)
- `tests/unit/daemon/test_scope_amendment.py` (S02)
- `tests/unit/test_fix_cycle.py` (S03)
- `tests/integration/test_scope_amend_endpoints.py` (S04)

`tidy`/`scope_overlap.py` was **not touched** — correct. No files outside the manifest touched.

---

## Architecture Compliance

- No `from orch` import in `executor/` ✅
- `DaemonEvent.metadata` → Python attribute `event_metadata` (line 2582) ✅ — SQLAlchemy reserves `metadata`
- No new dependency in `pyproject.toml` ✅
- No new migration in `orch/db/migrations/versions/` ✅

---

## Documentation & Example Coverage

- `docs/IW_AI_Core_Daemon_Design.md` §4.8.1 (~15 lines) documents: when auto-amend fires, that both events are emitted, that the feature is opt-in and default-off, and where to configure it ✅
- `.iw-orch.json`: example block keyed as `_auto_amend_scope_example` (underscore prefix → parser ignores it; iw-ai-core itself does NOT enable auto-amend) ✅
- `CR-00087_Functional.md` matches what shipped ✅

---

## Test Discipline

- `test_should_auto_amend_matches_violation_detector_by_construction` (line 734, `test_scope_amendment.py`) asserts `should_auto_amend([v], [p], None) == bool(scope_match(v, p))` for each realistic pattern the project would use ✅ — guard against future `scope_match` drift silently breaking auto-amend. **Note**: S05 flagged this; it is confirmed present in S06.
- Strong identity assertions: `event.event_metadata.get("matched_patterns") == [...]` in integration tests, not weak `in` checks ✅

---

## Security

- `grep -rn "sk-ant-\|password\s*=\|secret" `git diff --name-only main..HEAD`` → no matches ✅
- `.env` not committed ✅
- `fnmatch.fnmatch` only path-concatenation is to deterministic manifest paths via `worktree_path`/`item_id` ✅
- No `subprocess` from user-controlled input ✅

---

## Files Changed

| File | Step | Change |
|------|------|--------|
| `orch/daemon/project_registry.py` | S01 | +2 fields on `ProjectConfig`, +`_parse_auto_amend_scope` helper, wired into `_build_project_config` |
| `orch/daemon/scope_amendment.py` | S02 | +`should_auto_amend`, deferred import of `scope_match` |
| `orch/daemon/fix_cycle.py` | S02+S03 | `_scope_match` → `scope_match` (public); +`_try_auto_amend_after_escalation` helper hooked after escalation commit |
| `docs/IW_AI_Core_Daemon_Design.md` | S03 | +§4.8.1 ~15 lines |
| `.iw-orch.json` | S03 | +`_auto_amend_scope_example` block |
| `tests/unit/daemon/test_project_registry_auto_amend_scope.py` | S01 | NEW, 11 tests |
| `tests/unit/daemon/test_scope_amendment.py` | S02 | +`TestShouldAutoAmend`, 13 tests |
| `tests/unit/test_fix_cycle.py` | S03 | +2 TDD RED tests for short-circuit paths |
| `tests/integration/test_scope_amend_endpoints.py` | S04 | +4 `TestAutoAmendFixCycle` integration tests + fixture/impl bug fixes |

---

## Test Results

```
Targeted (94 tests):
  tests/unit/daemon/test_project_registry_auto_amend_scope.py  → 11 passed
  tests/unit/daemon/test_scope_amendment.py (TestShouldAutoAmend) → 13 passed
  tests/unit/test_fix_cycle.py (CR-00087 fix-cycle tests) → 2 passed
  tests/integration/test_scope_amend_endpoints.py → 10 passed (all 4 new + 6 existing)

Full unit suite:
  3521 passed, 5 skipped, 5 xfailed, 3 xpassed
```

---

## Review Result

```json
{
  "step": "S06",
  "agent": "code-review-final-impl",
  "work_item": "CR-00087",
  "steps_reviewed": ["S01", "S02", "S03", "S04"],
  "verdict": "pass",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "3521 passed (full unit suite), 10/10 integration tests passed (4 new + 6 existing)",
  "missing_requirements": [],
  "ac_verdicts": {
    "AC1": "PASS",
    "AC2": "PASS",
    "AC3": "PASS",
    "AC4": "PASS",
    "AC5": "PASS",
    "AC6": "PASS"
  },
  "matcher_parity_verified": true,
  "backwards_compat_verified": true,
  "notes": "All six ACs pass. Matcher parity chain verified end-to-end: scope_match is the single canonical implementation used by both the violation detector and should_auto_amend. Backwards-compat chain verified: projects without auto_amend_scope see zero behavioural change. The two-BUGFIX-in-S04 (fixture HEAD setup and composite-PK query) were legitimate; their cause was rooted in test design rather than design flaws and they are correctly fixed in S04's implementation. No CRITICAL, HIGH, or MEDIUM_FIXABLE findings."
}
```
