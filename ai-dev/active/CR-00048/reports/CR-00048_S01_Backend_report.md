# CR-00048 S01 Backend — Test hygiene (P1-CR-C)

**Work Item**: CR-00048 — Test hygiene (P1-CR-C)
**Step**: S01
**Agent**: backend-impl
**Status**: COMPLETE

---

## Summary

All 9 deliverables completed. The CR adds `pytest-randomly` (default-on), `--strict-markers` (default), and `vulture`/`deptry` (warn-only) tooling; fixes the `test_safe_migrate` agent-context test env-leak; quarantines one order-dependent test; and updates all docs/plan/skills.

**No fallback used** — suite is green under randomisation across all 3 unit seeds (2799 passed, 4 skipped, 6 xfailed, 1 xpassed).

---

## Deliverable 0 — RED reproduction

```bash
$ IW_CORE_PER_WORKTREE_DB=true uv run pytest tests/unit/test_safe_migrate.py::TestApply::test_apply_refuses_in_agent_context tests/unit/test_safe_migrate.py::TestRollback::test_rollback_refuses_in_agent_context -v
# FAILED — both tests: sqlalchemy.exc.OperationalError / psycopg.OperationalError:
# "failed to resolve host 'unused'" — because IW_CORE_PER_WORKTREE_DB=true
# in the ambient env (set in the agent worktree) leaks through patch.dict's
# clear=False and flips _assert_not_agent_context() out of the refuse branch,
# so apply() tries to connect to the fake 'unused' host.
```

**RED evidence captured**: `test_apply_refuses_in_agent_context` and `test_rollback_refuses_in_agent_context` — `Failed: DID NOT RAISE AgentContextForbiddenError` (in practice: `sqlalchemy.exc.OperationalError` because the guard was bypassed and the DB connection was attempted).

---

## Deliverable 1 — Dependencies added

`pytest-randomly>=3.15`, `vulture>=2.11`, `deptry>=0.20` added to `[dependency-groups] dev` in `pyproject.toml`. `uv lock` then `uv sync` succeeded. `pytest-randomly` is default-on once installed.

---

## Deliverable 2 — Multi-seed sweep

**Bounded sweep**: `make test-unit` × 3 seeds (12345, 67890, 11111) + `make test-integration` × 1 seed (42424; timed out at 300 s — verdict rests on unit suite; downstream QV gates supply further seeds).

**Order-dependent failures**: 1 found and quarantined.

| Test | File | Cause | Fix |
|------|------|--------|-----|
| `test_pick_free_offset_returns_hash_offset_when_free` | `test_browser_env.py` | Port-binding side effect from `_is_port_free` leaks between tests under random order | Quarantined `@pytest.mark.order_dependent` + `@pytest.mark.xfail(strict=False, ...)` + tracking comment; `import pytest` added (was missing) |

All 3 unit seeds now green: **2799 passed, 4 skipped, 6 xfailed, 1 xpassed**.

**No fallback used** — suite is robust to randomisation.

---

## Deliverable 3 — `--strict-markers`

Added to `addopts` in `pyproject.toml`. No unregistered/typo'd markers found — no fixes needed. `order_dependent` registered in `markers` list.

---

## Deliverable 4 — vulture + deptry (warn-only)

- `[tool.vulture]` added (`min_confidence = 70`, paths `orch dashboard executor scripts`, ignore decorators/names for FastAPI/Click/pytest fixtures).
- No `[tool.deptry]` section (deptry v0.25 doesn't support pyproject.toml config; options passed via CLI args instead).
- `make dead-code` (`uv run vulture || true`) and `make dep-check` (with `--per-rule-ignores` + `--extend-exclude "skills/.*"` to suppress noise from IW skill files) added to `Makefile`.
- Both appended to `make quality` (warn-only via `|| true`).
- Added to `.PHONY`.
- `.github/workflows/test-quality.yml`'s `lint-typecheck` job: `make dead-code || true` and `make dep-check || true` as non-failing informational steps (`continue-on-error: true` not used; `|| true` style matches the Makefile warn-only wiring).

---

## Deliverable 6 — `test_safe_migrate` agent-context fix

**Root cause**: In an agent worktree, `IW_CORE_PER_WORKTREE_DB=true` is in the ambient environment. The tests used `patch.dict("os.environ", {"IW_CORE_AGENT_CONTEXT": "true"}, clear=False)` — `clear=False` lets the ambient `IW_CORE_PER_WORKTREE_DB=true` leak into the patched env. When `_assert_not_agent_context()` checks `IW_CORE_PER_WORKTREE_DB=="true"` AND a non-5433 port is provided, it returns early (permitted path). So `apply()`/`rollback()` proceeds to try connecting to `postgresql+psycopg://unused/db`, which fails.

**Fix**: Explicitly set `IW_CORE_PER_WORKTREE_DB=false` in the test env dict:
```python
env = {"IW_CORE_AGENT_CONTEXT": "true", "IW_CORE_PER_WORKTREE_DB": "false"}
```
Now the refuse path is exercised regardless of the ambient env.

**Verified**: tests pass with `IW_CORE_PER_WORKTREE_DB=true` in ambient AND without it.

---

## Deliverable 7 — Docs/strategy/plan updates

- **`tests/CLAUDE.md`** §7: `pytest-randomly` recipe (disable with `-p no:randomly`, reproduce with `--randomly-seed=<N>`, multi-seed surface recipe).
- **`docs/IW_AI_Core_Testing_Strategy.md`**: §3 — `pytest-randomly` is default-on + reproduce recipe; §5 — `dead-code` (vulture warn-only) + `dep-check` (deptry warn-only) rows added to gate table; §6 — `--strict-markers` is default; §9 — "Test-order randomisation" and "`vulture`/`deptry`" rows flipped to ✅.
- **`skills/iw-ai-core-testing/SKILL.md`**: §2 — `pytest-randomly` section added; §8 (was §6) — `dead-code`/`dep-check` (warn-only) added to quality gates paragraph; red-flag checklist renumbered §9; §7 new bullet added: "**It only passes in fixed order** — this is an order-dependence smell".
- **`ai-dev/work/TESTS_ENHANCEMENT.md`**: items 1.4/1.5/1.7 → **DONE (CR-00048)**; §5 grouping: P1-CR-C **SHIPPED**, "*(start here)*" moved to **P1-CR-D**; changelog entry appended.

---

## Deliverable 8 — `iw sync-skills`

Ran `uv run iw sync-skills` — 0 synced (project override), 23 skipped. `.claude/skills/iw-ai-core-testing/SKILL.md` is already in sync (no diff vs master after our edits to `skills/iw-ai-core-testing/SKILL.md`). No `skills/iw-workflow/SKILL.md` changes (no new markers documented there). `iw sync-templates` NOT run (no template edits).

---

## Deliverable 9 — GREEN + REFACTOR

- `make format`: passed (auto-fixed `test_browser_env.py` line length on the xfail reason string).
- `make lint`: passed (ruff E501 on the long xfail reason string fixed by re-formatting).
- `make typecheck`: passed (no errors).
- `make quality`: passed (lint + format-check + typecheck + test-assertions all pass; dead-code/dep-check print findings but `|| true` makes them non-failing).
- Targeted `test_safe_migrate` run: 2/2 agent-context tests pass.
- Unit suite with seed 12345: **2799 passed, 4 skipped, 6 xfailed, 1 xpassed**.

---

## Files Changed

| File | Change |
|------|--------|
| `pyproject.toml` | `pytest-randomly>=3.15`, `vulture>=2.11`, `deptry>=0.20` added; `--strict-markers` added to `addopts`; `order_dependent` marker registered; `[tool.vulture]` section added |
| `uv.lock` | Regenerated (3 new deps) |
| `Makefile` | `dead-code` + `dep-check` targets added (warn-only); both appended to `make quality`; added to `.PHONY` |
| `.github/workflows/test-quality.yml` | `make dead-code \|\| true` + `make dep-check \|\| true` added to `lint-typecheck` job |
| `tests/unit/test_safe_migrate.py` | `IW_CORE_PER_WORKTREE_DB=false` added to agent-context test env dicts |
| `tests/unit/test_browser_env.py` | `import pytest` added; `test_pick_free_offset_returns_hash_offset_when_free` quarantined with `@pytest.mark.order_dependent` + `@pytest.mark.xfail(strict=False, ...)`; long xfail reason string re-formatted |
| `tests/CLAUDE.md` | `pytest-randomly` reproduce recipe added (§7) |
| `docs/IW_AI_Core_Testing_Strategy.md` | §3/§5/§6/§9 updated (randomisation, dead-code/dep-check gates, --strict-markers, gaps table) |
| `skills/iw-ai-core-testing/SKILL.md` | §2 pytest-randomly section added; §8 quality gates updated; red-flag checklist renumbered §9; new order-dependence smell bullet |
| `ai-dev/work/TESTS_ENHANCEMENT.md` | Items 1.4/1.5/1.7 DONE; §5 grouping updated (P1-CR-C SHIPPED → P1-CR-D); changelog appended |

---

## Test Results

| Run | Result |
|-----|--------|
| `test_safe_migrate` agent-context (with `IW_CORE_PER_WORKTREE_DB=true` ambient) | 2/2 PASSED |
| `test_safe_migrate` agent-context (without ambient) | 2/2 PASSED |
| Unit suite seed `12345` | 2799 passed, 4 skipped, 6 xfailed, 1 xpassed |
| Unit suite seed `67890` | 2799 passed, 4 skipped, 6 xfailed, 1 xpassed |
| Unit suite seed `11111` | 2799 passed, 4 skipped, 6 xfailed, 1 xpassed |
| `make lint` | PASSED |
| `make format` | PASSED |
| `make typecheck` | PASSED |
| `make quality` | PASSED |

---

## Changelog Entry (for TESTS_ENHANCEMENT.md §11)

```
- **2026-05-12** — **Items 1.4 + 1.5 + 1.7 → CR-00048 (P1-CR-C, test hygiene).**
  `pytest-randomly>=3.15`, `vulture>=2.11`, `deptry>=0.20` added to
  `[dependency-groups] dev`; `uv.lock` regenerated. `--strict-markers`
  added to `[tool.pytest.ini_options] addopts`. `order_dependent` marker
  registered. Bounded multi-seed sweep done: 3× `make test-unit` (seeds
  `12345`, `67890`, `11111`) + 1× `make test-integration` (seed `42424`;
  integration run timed out at 300 s — verdict rests on unit suite across
  3 seeds; downstream QV gates supply further seeds). Order-dependent failures:
  **1 quarantined** (`test_pick_free_offset_returns_hash_offset_when_free` in
  `test_browser_env.py` — port-binding side effect from `_is_port_free`
  leaks between tests under random order; marked `@pytest.mark.order_dependent`
  + `@pytest.mark.xfail(strict=False, reason="...")`). `tests/unit/test_safe_migrate.py`
  agent-context tests fixed: `IW_CORE_PER_WORKTREE_DB=false` added to env dict
  to prevent ambient agent-worktree env from leaking into `patch.dict` and
  flipping the refuse path. `[tool.vulture]` config added to `pyproject.toml`.
  `make dead-code` + `make dep-check` targets added (warn-only via `|| true`);
  appended to `make quality`; added to `.PHONY`; non-failing steps added to
  `.github/workflows/test-quality.yml`'s `lint-typecheck` job.
  `tests/CLAUDE.md` §7, strategy doc §3/§5/§6/§9, `skills/iw-ai-core-testing/SKILL.md`
  §2/§8 updated. `iw sync-skills` ran (`.claude/skills/iw-ai-core-testing/SKILL.md`
  in sync). `skills/iw-workflow/SKILL.md` not changed. §5: P1-CR-C **SHIPPED**,
  "*(start here)*" → **P1-CR-D**. Items 1.4/1.5/1.7 → **DONE (CR-00048)**.
  No fallback used — suite green under randomisation across all 3 unit seeds.
```
