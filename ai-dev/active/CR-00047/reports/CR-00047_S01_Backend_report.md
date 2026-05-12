# CR-00047 — S01 (Backend) report

**Work item**: CR-00047 — Coverage gates — raise the floor, ratchet it, and gate diff-coverage on PRs (P1-CR-B)
**Step**: S01 (`backend-impl`)
**Status**: complete

---

## What was done

### 0. Optional RED-first guard test — added
`tests/unit/test_coverage_gate_config.py` parses `pyproject.toml` / `Makefile` and pins:
- `[tool.coverage.report].fail_under == 50` and `> 46` and `< 100`,
- `[tool.coverage.run].relative_files is True`,
- `diff-cover` is in the `[dependency-groups] dev` group,
- `Makefile` has exactly one `diff-coverage:` target whose recipe runs `diff-cover --compare-branch=origin/main --fail-under=90`.

RED before the `fail_under` raise: `uv run pytest tests/unit/test_coverage_gate_config.py -v` → `AssertionError: assert 46 == 50` (1 failed, 3 passed). GREEN after the raise: 4 passed. The assertion scanner (`make test-assertions`) initially flagged `test_makefile_has_diff_coverage_target` as a tautology (all `... in ...` asserts) — fixed by switching the first assert to `makefile.count("\ndiff-coverage:") == 1`; scanner now clean (419 files, no new violations).

### 1. Measured coverage (both slices) + raised & ratcheted `fail_under`
- **Unit slice** — `make test-unit` (covers `tests/unit/`): **line ≈ 55 %**, **branch-inclusive coverage 51.84 %** (`coverage report` TOTAL: 21 908 stmts / 9 840 miss / 6 174 branch / 525 BrPart / 52 %).
- **Integration + dashboard slice** — `make test-integration` (covers `tests/integration/ tests/dashboard/`): **line ≈ 65 %**, **branch-inclusive coverage 61.23 %** (TOTAL: 21 937 stmts / 7 620 miss / 6 180 branch / 910 BrPart / 61 %; 2261 passed, 33 skipped, 3 xfailed — no failures).
- `[tool.coverage.report] fail_under` raised **46 → 50** — a few points below the *lower* (unit) slice's 51.84 %, rounded down to the nearest 5. This is a ratchet (raise as coverage improves, never lower). `relative_files`/`skip_covered`/`show_missing` kept; `--cov-report` config untouched otherwise.
- Re-ran `make test-unit` after the edit: `Required test coverage of 50.0% reached. Total coverage: 51.84%` — the new floor passes. `make quality` passes.

### 2. Coverage-plumbing audit (item 1.10)
- `relative_files = true` — was **missing**; **added** to `[tool.coverage.run]`.
- `addopts` uses `pytest --cov` (not the `coverage run -m pytest` xdist-bypass footgun) — **already correct**.
- No GH workflow uploads the raw `.coverage` file (only `coverage.xml` is uploaded, by the `unit` job) — so `include-hidden-files: true` on a `.coverage` artefact is **N/A**.
- Subprocess coverage (`COVERAGE_PROCESS_START`): the `iw` CLI / daemon subprocesses don't contribute coverage today — **documented as a known limitation** in `TESTS_ENHANCEMENT.md` item 1.10; **not wired up** (out of scope).
- Fork-PR two-workflow split — **not adopted** (out of scope).

### 3. `diff-cover` dev dependency
Added `diff-cover>=9` to `pyproject.toml`'s `[dependency-groups] dev` (the group that has `pytest`, `ruff`, `pip-audit`, …; the same one `uv sync --frozen` installs in CI). `uv lock` regenerated → `diff-cover==10.2.0`. `uv sync` ran; `uv run diff-cover --version` → `diff-cover 10.2.0`.

### 4. `make diff-coverage` — self-contained combined-coverage gate
New `diff-coverage:` target (added to `.PHONY`), with a header comment explaining the self-contained / combined-coverage rationale and the slow-gate trade-off:
```
uv run pytest tests/unit/ --cov-fail-under=0 -q
uv run pytest tests/integration/ tests/dashboard/ --ignore=tests/dashboard/browser --cov-append --cov-fail-under=0 -q
uv run coverage xml -o tests/output/coverage/coverage-combined.xml
uv run diff-cover tests/output/coverage/coverage-combined.xml --compare-branch=origin/main --fail-under=90
```
It builds its **own** combined coverage rather than reusing a leftover `coverage.xml` (each `pytest --cov` overwrites it → the leftover is the integration+dashboard slice only) or the no-op `integration-tests` gate. `--cov-fail-under=0` on the two intermediate runs suppresses the per-run `[tool.coverage.report] fail_under` re-check (the unit-only slice sits below the raised floor) — `diff-cover --fail-under=90` is the gate's verdict. `tests/output/` is gitignored, so `coverage-combined.xml` isn't committed.

### 5. `diff-coverage` daemon QV gate
`skills/iw-workflow/SKILL.md` "QV Gate Steps" block: added a 7th entry after `integration-tests` —
`{"step": "S16", "agent": "qv-gate", "gate": "diff-coverage", "command": "make diff-coverage", "description": "QV: Diff coverage (new/changed lines must be well-covered)", "timeout": 1800}`. Prose updated: "The 7 canonical QV gates are: `lint` → `assertions` → `format` → `typecheck` → `unit-tests` → `integration-tests` → `diff-coverage`", plus a sentence describing the gate (self-contained combined coverage, `--compare-branch=origin/main`, fails on changed-line coverage < ~90 %, generous 1800 s timeout because it re-runs the suites).

### 6. GH `Run diff coverage` step
`.github/workflows/test-quality.yml`'s `unit` job: added `fetch-depth: 0` to the `actions/checkout` step (so the PR base is fetchable) and a `Run diff coverage` step after the coverage-XML upload, `if: github.event_name == 'pull_request'`, which `git fetch`es `origin/${{ github.base_ref }}` then runs `diff-cover tests/output/coverage/coverage.xml --compare-branch=origin/${{ github.base_ref }} --fail-under=90` (uses the unit `coverage.xml` already produced — cheap; the daemon gate is the authoritative combined one). No new job. Skipped on `push` to main (no diff).

### 7. `docs/IW_AI_Core_Testing_Strategy.md`
- §1 principle table: the "Coverage is a floor on what's exercised" row now notes the `fail_under` floor is set just below measured branch coverage and **ratchets up over time, never down** (CR-00047), and that a `diff-coverage` gate additionally requires new/changed lines to be well-covered.
- §5 gate table: Coverage row updated (`fail_under = 50`, ratchet note, "enforced via `pytest --cov` at the end of every run"); new **Diff coverage** row (`diff-cover` / new-changed lines ≥ ~90 % vs `origin/main` / `make diff-coverage` daemon QV gate + PR step). New "**Coverage floor & diff-coverage (CR-00047, P1-CR-B)**" sub-section: the floor & ratchet rule + how to re-derive it; what the `diff-coverage` gate checks + `make diff-coverage` locally; the **coverage-source caveat** — daemon gate = combined unit+integration; GH PR check = unit `coverage.xml`; daemon gate is authoritative.
- §9 gaps table: "Coverage failure floor" and "Diff/patch coverage on PRs" rows flipped to ✅ (CR-00047, 2026-05-12).

### 8. `skills/iw-ai-core-testing/SKILL.md` §8
Added `diff-coverage` to the gate list, the 7-gate canon line, and a note that the `fail_under` floor is set just below measured branch coverage and ratchets up, never down (CR-00047).

### 9. `iw sync-skills`
Ran `iw sync-skills --force iw-workflow` and `iw sync-skills --force iw-ai-core-testing` (the no-arg run treats both as "project override (skipped)"). `git diff` confirms `.claude/skills/iw-workflow/SKILL.md` and `.claude/skills/iw-ai-core-testing/SKILL.md` are byte-identical to their masters under `skills/`. `iw sync-templates` was **not** run (no `templates/design/*.md` edits). Sibling repos (iw-doc-plan/podforger/cv) will pick up the new `diff-coverage` gate at their next `iw sync-skills` — not done from this worktree.

### 10. `ai-dev/work/TESTS_ENHANCEMENT.md`
Items **1.2**, **1.3** and the **1.10 audit** marked DONE (CR-00047). §5 grouping table: **P1-CR-B → SHIPPED (CR-00047, 2026-05-12)**, "*(start here)*" moved to **P1-CR-C**, sequencing-rationale line updated. Resolved the "Coverage floor starting value" open question. Top-of-doc "Current status" blurb refreshed (was stale at 2026-05-11 / "start with 1.1"). Added a changelog entry (the measured slices, the chosen `fail_under = 50`, `diff-cover` + `make diff-coverage` + the new 7th gate, the cov-plumbing audit findings, what was deferred, and the pre-existing-test-failure note).

### 11. GREEN + REFACTOR
- `uv run pytest tests/unit/test_coverage_gate_config.py -v` → **4 passed**.
- `make test-unit` → coverage check `Required test coverage of 50.0% reached. Total coverage: 51.84%` ✓ (2 pre-existing failures — see Observations).
- `make diff-coverage` → **halts at its first sub-step** (`pytest tests/unit/`) on the 2 pre-existing `test_safe_migrate.py` failures (exit 2). The `coverage xml` + `diff-cover ... --compare-branch=origin/main --fail-under=90` tail was verified separately against the unit `.coverage` → `"No lines with coverage information in this diff."` → **exit 0** (this CR changes ≈0 production Python; the only changed `.py` is `tests/unit/test_coverage_gate_config.py`, and `tests/` is in `[tool.coverage.run] omit`, so `diff-cover` has no changed lines to judge — matches AC5).
- `make quality` → **pass** (lint + format-check + typecheck + test-assertions; "676 files already formatted", mypy "no issues", "No new assertion-scanner violations (419 files scanned)").
- Targeted run of the new test file: `tests/unit/test_coverage_gate_config.py` 4/4 pass.
- Did **not** run `make check` / `make test-integration` at large beyond the one measurement run (per the prompt).

## Files changed
- `pyproject.toml` — `fail_under` 46 → 50 (+ comment); `relative_files = true` added to `[tool.coverage.run]`; `diff-cover>=9` added to `[dependency-groups] dev`
- `uv.lock` — regenerated (adds `diff-cover==10.2.0` + transitive deps)
- `Makefile` — new `diff-coverage:` target + header comment; `diff-coverage` added to `.PHONY`
- `skills/iw-workflow/SKILL.md` — 7th `diff-coverage` QV gate + prose
- `.claude/skills/iw-workflow/SKILL.md` — synced
- `skills/iw-ai-core-testing/SKILL.md` — §8 updated
- `.claude/skills/iw-ai-core-testing/SKILL.md` — synced
- `.github/workflows/test-quality.yml` — `unit` job: `fetch-depth: 0` + `Run diff coverage` PR step
- `docs/IW_AI_Core_Testing_Strategy.md` — §1, §5 (+ new sub-section), §9
- `ai-dev/work/TESTS_ENHANCEMENT.md` — items 1.2/1.3/1.10, §5 grouping, open-Qs, top blurb, changelog
- `tests/unit/test_coverage_gate_config.py` — new (optional guard test)
- `ai-dev/active/CR-00047/reports/CR-00047_S01_Backend_report.md` — this report

## Test results
- `tests/unit/test_coverage_gate_config.py`: **4 passed, 0 failed**.
- `make test-unit` (measurement / floor-verify run): 2798 passed, **2 failed** (`tests/unit/test_safe_migrate.py::TestApply::test_apply_refuses_in_agent_context`, `…TestRollback::test_rollback_refuses_in_agent_context`), 4 skipped, 5 xfailed, 1 xpassed. Coverage gate: `Required test coverage of 50.0% reached. Total coverage: 51.84%` ✓.
- `make test-integration` (measurement run): 2261 passed, 0 failed, 33 skipped, 3 xfailed. Coverage: 61.23 %.
- `make quality`: pass. `make diff-coverage`'s `diff-cover` tail (run manually): exit 0.

## Observations / issues
- **2 pre-existing unit failures, NOT caused by this CR.** `tests/unit/test_safe_migrate.py::TestApply::test_apply_refuses_in_agent_context` and `…TestRollback::test_rollback_refuses_in_agent_context` fail with `psycopg.OperationalError: failed to resolve host 'unused'` instead of `AgentContextForbiddenError`. Root cause: these tests use `patch.dict("os.environ", {"IW_CORE_AGENT_CONTEXT": "true"}, clear=False)`, and this agent worktree's environment has **`IW_CORE_PER_WORKTREE_DB=true`** set — which the updated agent-context guard (`orch/db/live_db_guard.assert_engine_url_allowed`, called by `safe_migrate.apply`/`rollback`) treats as "connecting to the worktree DB is OK", so it doesn't refuse. Verified pre-existing: `git stash` → clean tree → same 2 failures. Verified env-only: `env -u IW_CORE_AGENT_CONTEXT -u IW_CORE_PER_WORKTREE_DB uv run pytest …test_apply_refuses_in_agent_context` → **passes**. The fix belongs in `tests/unit/test_safe_migrate.py` (it should `monkeypatch.delenv("IW_CORE_PER_WORKTREE_DB", raising=False)` or use `clear=True`) — **out of scope for CR-00047** (`test_safe_migrate.py` is not in the Impacted Paths). The GitHub `unit` CI job is unaffected (no `IW_CORE_PER_WORKTREE_DB`). Coverage measurement & the new `fail_under = 50` floor are unaffected (coverage 51.84 % ≥ 50, computed even with the 2 failures). **Consequence**: the S08 (`make test-unit`) and S10 (`make diff-coverage`) QV gates will fail in any environment where `IW_CORE_PER_WORKTREE_DB=true` leaks; if the daemon's qv-gate env has it, the item will fail at S08 before reaching the new diff-coverage gate — but that's a pre-existing infra/test-isolation issue, independent of this CR. Worth a follow-up incident scoped to `test_safe_migrate.py`.
- **Headroom on the floor is ~1.84 points** (50 vs the unit slice's 51.84 %). That's the rule-of-thumb value (lower slice rounded down to the nearest 5) and is > the old 46. If a future CR ever trips it on the unit slice, the right response is to add coverage, not lower the floor (ratchet discipline). A more conservative pick (48 or 49) was possible but 50 is the round rule-of-thumb value and a meaningful raise.
- **Nested-dup directory**: `ai-dev/active/CR-00047/CR-00047/` exists as an untracked duplicate of `ai-dev/active/CR-00047/` (predates this step — visible in `git status` at session start). Not created or modified here; flagging for cleanup by the orchestrator / a later step (CR-00046's changelog tracked the same kind of artefact).
- The pytest "Unknown config option: env" warning is pre-existing (`[tool.pytest.ini_options] env = [...]` but `pytest-env` isn't installed) — unrelated to this CR.
