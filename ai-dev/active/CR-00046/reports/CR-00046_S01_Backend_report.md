# CR-00046 — S01 Backend Report

**Step**: S01 (backend-impl) — RED-first AST assertion-scanner gate (P1-CR-A)
**Date**: 2026-05-11
**Status**: complete

## What was done

Eleven-deliverable single-step implementation of the new AST assertion-scanner gate.

1. **RED — `tests/unit/test_assertion_scanner.py`** (29 tests). Covers each detected category (positive + negative); the eight tautology sub-cases (`assert True`, `assert <bare Name>`, `assert x == x`, `assert isinstance(...)`, `assert x is not None`, `assert len(x) > 0`/`>= 1`/`!= 0`, `assert "k" in x`); the baseline mechanic (`--baseline`, `--write-baseline`, `--strict`); the JSON output shape; the human-readable line format; the `# noqa: assertion-scanner` opt-out; and the conftest-skip rule.
   - **RED capture (deliverable 1)**: `uv run pytest tests/unit/test_assertion_scanner.py -v` — **29 failed**. The first failure (`test_scanner_script_exists`) was `AssertionError: is_file() False` (the scanner did not exist); the rest cascaded through `JSONDecodeError: Expecting value` because `subprocess.run([sys.executable, scripts/check_test_assertions.py, ...])` produced no JSON output (script absent → CalledProcessError-ish). All 29 are now GREEN.
2. **`scripts/check_test_assertions.py`**. ~430 LOC. Ports InnoForge's `_has_assertion` walk and `--baseline-file` mechanic, then **extends** to the four-category detector per the design's Scanner-contract table. Skips `**/conftest.py`. Honours `# noqa: assertion-scanner` on the `def` line (case-insensitive on `noqa`, exact on the code). CLI: positional paths (default `tests`), `--baseline <path>`, `--write-baseline <path>`, `--strict`, `--json`. Exit 0/1 on no-new-violations / new-violations.
3. **`tests/assertion_free_baseline.txt`** generated via `uv run python scripts/check_test_assertions.py --write-baseline tests/assertion_free_baseline.txt tests/`. **621 entries** (header comment + sorted body), category breakdown:
   - `tautology`: 543 (predominantly `assert isinstance(...)` and `assert x is not None`)
   - `no-assert`: 71
   - `mock-only`: 7
   - `broad-raises`: 0 (no current `pytest.raises(Exception)` without `match=` after I-00041's tightening)
   Header explains purpose / format / cleanup-backlog framing / "fix the test, don't add to the baseline" rule.
4. **`Makefile`** — new `test-assertions:` target with header comment; folded into `quality:` (now `lint format typecheck test-assertions`); `test-assertions` added to `.PHONY`.
5. **`skills/iw-workflow/SKILL.md`** — new `assertions` QV gate inserted right after `lint` in the canonical example (now 6 gates: `lint` → `assertions` → `format` → `typecheck` → `unit-tests` → `integration-tests`); follow-on prose paragraph added.
6. **`.github/workflows/test-quality.yml`** — `- run: make test-assertions` added to `lint-typecheck` job immediately after `- run: make lint`. No `--strict` (matches local behaviour).
7. **`docs/IW_AI_Core_Testing_Strategy.md`** — §8 gains a new "Assertion scanner (CR-00046, P1-CR-A)" subsection; §9 row "AST assertion scanner" flipped to ✅ with date and gate command.
8. **`skills/iw-ai-core-testing/SKILL.md`** — block-quote cross-reference at the end of §1: bans now statically enforced, baseline file is for the cleanup backlog (not silencing).
9. **`uv run iw sync-skills --force iw-workflow`** + `uv run iw sync-skills --force iw-ai-core-testing`. Default `iw sync-skills` skipped both as "project override" (their lock entries had `overridden: true`); `--force` regenerated the `.claude/skills/` copies. `diff -q` confirms `.claude/skills/iw-workflow/SKILL.md` and `.claude/skills/iw-ai-core-testing/SKILL.md` now byte-match their masters. **Did NOT run `iw sync-templates`** — no template edits in this CR.
10. **`ai-dev/work/TESTS_ENHANCEMENT.md`** — Phase-1 row 1.1 status set to `**DONE 2026-05-11 (CR-00046)**`, Link `CR-00046`. Changelog entry added at the bottom.
11. **GREEN + REFACTOR** — `uv run pytest tests/unit/test_assertion_scanner.py -v` → 29 passed. `make test-assertions` → 0 (baseline admits all current offenders). `make quality` → all four steps pass (lint + format-check + typecheck + test-assertions).

## Files changed

- `scripts/check_test_assertions.py` *(new)*
- `tests/assertion_free_baseline.txt` *(new — 621 entries)*
- `tests/unit/test_assertion_scanner.py` *(new — 29 tests)*
- `Makefile`
- `skills/iw-workflow/SKILL.md`
- `.claude/skills/iw-workflow/SKILL.md` *(via `iw sync-skills --force`)*
- `skills/iw-ai-core-testing/SKILL.md`
- `.claude/skills/iw-ai-core-testing/SKILL.md` *(via `iw sync-skills --force`)*
- `.github/workflows/test-quality.yml`
- `docs/IW_AI_Core_Testing_Strategy.md`
- `ai-dev/work/TESTS_ENHANCEMENT.md`
- `pyproject.toml` *(per-file-ignore: `T201` for the scanner script's stdout prints; `ERA001` for the test file's commented-example labels — neither extends the scanner's behavioural surface, just keeps `make lint` clean)*
- `.iw-skills-lock.json` *(touched by `iw sync-skills --force` to record the new lock state — `iw-workflow` and `iw-ai-core-testing` flipped to `source: platform, overridden: false` since they now match master)*

## Test results

- `uv run pytest tests/unit/test_assertion_scanner.py -v` → **29 passed, 0 failed** in ~0.8s
- `make test-assertions` → **EXIT 0** (`No new assertion-scanner violations (417 files scanned).`)
- `make quality` → **all four steps green** (`lint`, `format`, `typecheck`, `test-assertions`)

## Notes

- **Baseline size: 621 entries.** Predominantly `tautology` (543) — the bulk of which are `assert isinstance(result, dict)` / `assert result is not None` / `assert "k" in result` and similar. This is in line with InnoForge's 77 entries scaled for a four-category scanner across iw-ai-core's 417 test files. Per the design's Scope-discipline rule we **did not** clean up any baseline entries — that's a follow-up item.
- **`broad-raises` count is 0.** Surprising in a good way: the strategy doc / iw-ai-core-testing skill have been preaching against `pytest.raises(Exception)` for a while and the codebase is already clean.
- **`mock-only` count is 7.** Lower than expected — most mock-heavy tests in this codebase do also have a real `assert`.
- **`pyproject.toml` per-file-ignores** were added for the scanner script (`T201` — the script intentionally prints to stdout) and the test file (`ERA001` — the test parametrize list carries `# assert ...` *labels* that ruff sees as commented-out code). Neither widens the rule beyond the strict need.
- **Sibling repos**. `skills/iw-workflow/` is a shared workflow skill; sibling repos (`iw-doc-plan`, `podforger`, `cv`) will pick up the new `assertions` QV gate at their next `iw sync-skills` run (a post-merge operator step). Not done from this worktree (out of scope per design "Scope discipline" rule). `skills/iw-ai-core-testing/` is project-specific (per CR-00045) — not propagated.
- **Mypy scope** — `make typecheck` runs `mypy orch/ dashboard/`, so the new scanner under `scripts/` is not type-checked. Followed existing project convention (other scripts under `scripts/` are also outside the mypy scope).

## TDD evidence

`tdd_red_evidence` for the result contract:

> `tests/unit/test_assertion_scanner.py` — RED before deliverable 2: 29/29 failed. First failure `test_scanner_script_exists` → `AssertionError: is_file() False` for `scripts/check_test_assertions.py`; subsequent tests cascaded through `json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)` because the scanner script did not yet exist (`subprocess.run` on the missing path produced no JSON). After deliverable 2 lands the scanner, 29/29 pass — full GREEN.
