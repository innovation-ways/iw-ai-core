# CR-00048 S02 CodeReview — Test hygiene (P1-CR-C)

**Work Item**: CR-00048
**Step**: S02
**Agent**: code-review-impl
**Reviewed**: S01 (backend-impl)
**Status**: PASS

---

## Summary

The implementation is correct and complete. All acceptance criteria are met, all files changed are in-scope, lint/format/typecheck/quality all pass, unit tests pass (2,799 passed), and the `test_safe_migrate` env-leak fix is verified against an ambient `IW_CORE_PER_WORKTREE_DB=true` environment.

---

## Pre-Review Gate Results

| Command | Result |
|---------|--------|
| `make lint` | ✅ All checks passed |
| `make format` | ✅ 676 files already formatted |

No new violations introduced by this step.

---

## Files Changed — Scope Verification

| File | Change | In-scope? |
|------|--------|-----------|
| `pyproject.toml` | pytest-randomly/vulture/deptry deps; `--strict-markers`; `[tool.vulture]`/`[tool.deptry]`; `order_dependent` marker | ✅ |
| `uv.lock` | Regenerated with 3 new deps | ✅ |
| `Makefile` | `dead-code` + `dep-check` targets (warn-only); appended to `quality:`; added to `.PHONY` | ✅ |
| `.github/workflows/test-quality.yml` | `make dead-code \|\| true` + `make dep-check \|\| true` in `lint-typecheck` job | ✅ |
| `tests/unit/test_safe_migrate.py` | `IW_CORE_PER_WORKTREE_DB=false` added to env dicts in agent-context tests | ✅ |
| `tests/unit/test_browser_env.py` | `import pytest` added; `test_pick_free_offset_returns_hash_offset_when_free` quarantined with `@pytest.mark.order_dependent` + `@pytest.mark.xfail` | ✅ |
| `tests/CLAUDE.md` | §7 pytest-randomly reproduce recipe | ✅ |
| `docs/IW_AI_Core_Testing_Strategy.md` | §3/§5/§6/§9 updated | ✅ |
| `skills/iw-ai-core-testing/SKILL.md` | §2/§8 updated; §7 new bullet; red-flag checklist renumbered | ✅ |
| `ai-dev/work/TESTS_ENHANCEMENT.md` | Items 1.4/1.5/1.7 DONE; §5 grouping P1-CR-C SHIPPED→P1-CR-D; changelog entry | ✅ |

No out-of-scope changes found. No integration-gate fix, no hard-gate flip, no dead-code deletion pass.

---

## Acceptance Criteria Review

### AC1: pytest-randomly is in, and the suite is robust to it

- `pytest-randomly>=3.15` in `[dependency-groups] dev` ✅
- 3 × unit seeds (12345, 67890, 11111) + 1 × integration seed (42424) swept ✅
- All 3 unit seeds green: **2799 passed, 4 skipped, 6 xfailed, 1 xpassed** ✅
- 1 order-dependent failure quarantined: `test_pick_free_offset_returns_hash_offset_when_free` in `test_browser_env.py` with `@pytest.mark.order_dependent` + `@pytest.mark.xfail(strict=False, reason="...")` + tracking comment ✅
- `order_dependent` registered in `pyproject.toml` markers ✅
- No fallback used (off-by-default path not triggered) ✅

### AC2: --strict-markers is default and markers are clean

- `--strict-markers` added to `addopts` in `pyproject.toml` ✅
- No unregistered/typo'd markers found (no fixes needed) ✅
- `order_dependent` properly registered ✅

### AC3: dead-code and dep-check exist, warn-only

- `[tool.vulture]` config in `pyproject.toml` with `min_confidence = 70`, paths, ignore decorators/names ✅
- `[tool.deptry]` config in `pyproject.toml` with `per_rule_ignores` and `extend_exclude` ✅
- `make dead-code` target: `uv run vulture || true` ✅
- `make dep-check` target: `uv run deptry . ... || true` ✅
- Both appended to `make quality` (warn-only via `|| true`) ✅
- Both added to `.PHONY` ✅
- Non-failing steps in `.github/workflows/test-quality.yml` `lint-typecheck` job ✅

### AC4: test_safe_migrate env-leak is fixed

- Root cause correctly identified: ambient `IW_CORE_PER_WORKTREE_DB=true` leaks through `clear=False` into `patch.dict`, flipping the refuse path out of its branch ✅
- Fix: explicit `IW_CORE_PER_WORKTREE_DB=false` in the test env dict ✅
- Verified: tests pass with `IW_CORE_PER_WORKTREE_DB=true` ambient AND without it ✅
- No production code change in `orch/db/safe_migrate.py` ✅
- RED evidence: `Failed: DID NOT RAISE AgentContextForbiddenError` captured (actual: `sqlalchemy.exc.OperationalError` from the bypassed guard attempting a connection to `postgresql+psycopg://unused/db`) ✅

### AC5: recipe is documented

- `tests/CLAUDE.md` §7: disable with `-p no:randomly`; reproduce with `--randomly-seed=<N>`; multi-seed surface recipe ✅
- `skills/iw-ai-core-testing/SKILL.md` §2: same recipe; §8 quality gates paragraph updated ✅
- `.claude/skills/iw-ai-core-testing/SKILL.md` matches master (no diff) ✅

### AC6: plan and strategy doc updated

- `ai-dev/work/TESTS_ENHANCEMENT.md`: items 1.4/1.5/1.7 → DONE (CR-00048); §5 grouping: P1-CR-C SHIPPED, "*(start here)*" moved to P1-CR-D; changelog entry with counts ✅
- `docs/IW_AI_Core_Testing_Strategy.md`: §3 pytest-randomly default-on + recipe; §5 gate table dead-code/dep-check (warn-only) rows; §6 `--strict-markers` default; §9 "Test-order randomisation" and "vulture/deptry" rows flipped to ✅ ✅

### AC7: QV gates pass under randomization

- `make test-unit` with pytest-randomly enabled: **2799 passed, 4 skipped, 6 xfailed, 2 xpassed** (xpassed = pre-existing xpass markers, not failures) ✅
- `make quality`: all checks passed (lint + format-check + typecheck + test-assertions; dead-code/dep-check printed findings but didn't fail) ✅

---

## TDD RED Evidence Review

The behavioural test fix is `tests/unit/test_safe_migrate.py`'s 2 agent-context tests. The report records the RED run:

> `IW_CORE_PER_WORKTREE_DB=true` ambient → `sqlalchemy.exc.OperationalError` — the guard was bypassed, `apply()` tried to connect to `postgresql+psycopg://unused/db`.

The test **would** fail against pre-change code because the `clear=False` in `patch.dict` allows the ambient `IW_CORE_PER_WORKTREE_DB=true` to flow through, and the guard function (`_assert_not_agent_context`) checks that variable to determine whether to allow the per-worktree DB path. With it set to `"true"`, the refuse branch is never entered. ✅

---

## Quality Checks

| Check | Result |
|-------|--------|
| `make lint` | ✅ All checks passed |
| `make format` | ✅ 676 files already formatted |
| `make typecheck` | ✅ Passed |
| `make quality` | ✅ Passed |
| `make test-unit` | ✅ 2799 passed, 4 skipped, 6 xfailed, 2 xpassed |

---

## Test Results

| Run | Result |
|-----|--------|
| `make test-unit` (unit suite, random seed active) | 2799 passed, 4 skipped, 6 xfailed, 2 xpassed ✅ |
| `test_safe_migrate` agent-context with `IW_CORE_PER_WORKTREE_DB=true` ambient | 17/17 passed ✅ |

---

## Findings

None. The implementation is correct, in-scope, and complete.

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "CR-00048",
  "step_reviewed": "S01",
  "verdict": "pass",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "2799 passed, 4 skipped, 6 xfailed, 2 xpassed",
  "notes": "All acceptance criteria met. No out-of-scope edits. No lint/format/typecheck violations. test_safe_migrate fix verified against ambient IW_CORE_PER_WORKTREE_DB=true. Suite green under randomisation across all seeds. Docs/plan/skills all updated. iw sync-skills confirmed no diff in .claude/skills/iw-ai-core-testing/SKILL.md vs master."
}
```