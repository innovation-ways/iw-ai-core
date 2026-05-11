# CR-00046: AST assertion-scanner gate — block tests that can't fail

**Type**: Change Request
**Priority**: Medium
**Reason**: Phase 0 mandated "every test must be able to fail" but nothing enforces it — agents writing the next thousand tests can drift back to the smells. This is the cheapest, highest-yield Phase-1 gate.
**Created**: 2026-05-11
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy applies. This CR touches no Docker/compose state. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy applies. **This CR adds no migration and modifies none** — no `orch/db/migrations/versions/**` changes.

## Description

Add a static AST scanner (`scripts/check_test_assertions.py`) that flags four classes of vacuous test — no-assert tests, tautological-assertion tests, mock-only tests, and `pytest.raises(Exception)`-without-`match=` tests — wire it into `make quality`, into a new **`assertions`** daemon QV gate (placed right after `lint` in the canonical sequence), and into the existing `.github/workflows/test-quality.yml` `lint-typecheck` job. A baseline file (`tests/assertion_free_baseline.txt`) admits existing offenders so the gate fires only on *new* violations. This is **P1-CR-A** of the testing-enhancement plan ([`ai-dev/work/TESTS_ENHANCEMENT.md`](../../work/TESTS_ENHANCEMENT.md) item 1.1), the first item of Phase 1.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Standards already in place from Phase 0: [`docs/IW_AI_Core_Testing_Strategy.md`](../../../docs/IW_AI_Core_Testing_Strategy.md) (§6 TDD/RED evidence; §7 red-flag list this scanner enforces statically), [`skills/iw-ai-core-testing/SKILL.md`](../../../skills/iw-ai-core-testing/SKILL.md) (§1 the anti-patterns), and CR-00045's `tdd_red_evidence` contract (which S01 will exercise legitimately — the scanner has real branching logic). The QV-gate canon lives in `skills/iw-workflow/SKILL.md` and is synced to `.claude/skills/` via `iw sync-skills`. The starting structural reference for the scanner is InnoForge's `/home/sergiog/dev/iw-doc-plan/main/iw-doc-plan/scripts/check_test_assertions.py` (~5 KB; 77-entry baseline).

## Current Behavior

- The testing standards (`tests/CLAUDE.md`, the `iw-ai-core-testing` skill §1, the strategy doc §7) **say** every test must be able to fail and **list** the anti-patterns (`assert x is not None`, `assert isinstance(...)`, mock-only assertions, broad `pytest.raises`) — but they are guidance only. There is no automated check.
- `make quality` is `lint format typecheck`. Nothing scans test files for assertion structure.
- `skills/iw-workflow/SKILL.md` lines 126–130 enumerate the 5 canonical QV gates (`lint`, `format`, `typecheck`, `unit-tests`, `integration-tests`). The `assertions` gate does not exist.
- `.github/workflows/test-quality.yml`'s `lint-typecheck` job runs `make lint`, `make format-check || make format`, `make typecheck`. No assertion check.
- No baseline file exists. No scanner script exists.
- Agents producing test files (`backend-impl` doing RED-first, `tests-impl` adding coverage) can ship a new file full of `assert x is not None` and nothing in the pipeline notices.

## Desired Behavior

- **`scripts/check_test_assertions.py`** is a CLI tool that AST-walks Python test files and flags four categories of vacuous test (full spec in §"Scanner contract" below). It supports `--baseline <path>` (treat listed offenders as expected — exit 1 only on new violations), `--write-baseline <path>` (regenerate the baseline file), `--json` (machine-readable output), and `--strict` (no baseline allowance — every flagged test fails). Exit 0 if no new violations, 1 otherwise. Human-readable output is one line per violation: `path:line: <category>: <test_name>: <one-line explanation>`.
- **`tests/assertion_free_baseline.txt`** is committed, sorted, with a comment header explaining its purpose and the cleanup-backlog framing. One offender per line: `path::test_name # category`.
- **`make test-assertions`** runs the scanner against `tests/` with the baseline. **`make quality`** is now `lint format typecheck test-assertions` so local pre-commit catches new violations. `make check` (which is `quality test`) therefore also catches them.
- **Daemon QV gate `assertions`** exists in the canonical list in `skills/iw-workflow/SKILL.md`, positioned right after `lint`. All future Feature/CR/Incident manifests pick it up. `iw sync-skills` propagates the change to `.claude/skills/iw-workflow/SKILL.md`.
- **`.github/workflows/test-quality.yml`** — the `lint-typecheck` job has a new step `- run: make test-assertions` right after the existing `make lint` step.
- **`tests/unit/test_assertion_scanner.py`** exercises every detected category (positive + negative cases) plus the baseline mechanic and JSON output shape — RED-first (the scanner doesn't exist when the tests are written, so they fail with `FileNotFoundError`/`ImportError` until S01's GREEN step).
- **`docs/IW_AI_Core_Testing_Strategy.md`** §8 (or new §8b) documents the scanner's contract; §9 row for "AST assertion scanner" flips to ✅.
- **`skills/iw-ai-core-testing/SKILL.md`** carries a one-line cross-reference noting the bans in §1 are now backed by `make test-assertions` / the `assertions` QV gate.
- **`ai-dev/work/TESTS_ENHANCEMENT.md`** item 1.1 is ticked DONE with `(CR-00046)` link; changelog entry added.

### Scanner contract — what gets flagged

| Category | Flagged when | Examples flagged | Examples NOT flagged |
|---|---|---|---|
| **no-assert** | A `test_*` (or `async def test_*`) function body contains no `assert` statement, no `pytest.raises(...)` / `pytest.warns(...)` context manager or call, and no `mock.assert_called*` / `mock.assert_awaited*` attribute call. (Port InnoForge's `_has_assertion` walk verbatim.) | `def test_x(): result = foo()` | `def test_x(): assert foo() == 42`; `def test_x(): mock.assert_called_once()`; `def test_x():\n    with pytest.raises(ValueError): foo()` |
| **tautology** | **Every** `assert` in the body matches one of the tautological forms: `assert True`; `assert <bare Name>` (truthiness only); `assert x == x` (same identifier both sides — `ast.Name(.id)` equality); `assert isinstance(x, T)` (the *whole* assertion is `isinstance(...)`); `assert x is not None`; `assert len(x) > 0` / `>= 1` / `!= 0`; `assert "k" in x` / `assert k in d`. **Mixed** tests (one tautological assert + one specific) are OK. | `def test_x(): assert isinstance(foo(), dict)`; `def test_x(): assert foo() is not None` | `def test_x(): assert isinstance(r, dict); assert r["k"] == 42`; `def test_x(): assert len(r) == 3` (specific equality, not `> 0`) |
| **mock-only** | The function body contains assertions, but **every** assertion is `mock.assert_called*` / `mock.assert_awaited*` (`ast.Attribute` whose `attr` starts with `assert_call` or `assert_await`) on an identifier whose name contains `mock`/`Mock` (case-insensitive heuristic — we do not do type inference). | `def test_x(): foo(); mock.assert_called_once()` | `def test_x(): result = foo(); assert result == 42; mock_dep.assert_called_once()` |
| **broad-raises** | `with pytest.raises(<expr>):` (or bare call form) where `<expr>` is the literal `Exception` or `BaseException` **and** there is no `match=` kwarg. | `with pytest.raises(Exception): foo()` | `with pytest.raises(Exception, match="not found"): foo()`; `with pytest.raises(ValueError): foo()`; `with pytest.raises(NotImplementedError): foo()` |

Implementation notes for the scanner:
- One pass per file via `ast.parse` + `ast.walk`. Skip non-`test_*` functions. Skip `tests/conftest.py` and `tests/integration/conftest.py` (fixtures, not tests).
- For tautology: gather all `ast.Assert` nodes in the function body; if the set is non-empty and *every* one matches a tautological pattern, flag.
- For mock-only: gather all assertion-bearing statements; if all of them are `mock.assert_*` attribute calls on mock-named identifiers, flag.
- For broad-raises: visit `ast.With` items where the context-manager call is `pytest.raises` (`ast.Attribute(value=Name("pytest"), attr="raises")` or imported as `raises`).
- A test may be flagged under multiple categories (e.g. mock-only + broad-raises) — report each independently; the baseline file lists `<path>::<test_name> # <category>` so the same test can appear with two category suffixes.
- Honour `# noqa: assertion-scanner` on the function def line as an explicit local opt-out — for the rare case where the test legitimately can't have a stronger assertion. Use sparingly; reviewers should push back.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `scripts/check_test_assertions.py` | does not exist | new — ~150–200 LOC, four-category AST scanner with baseline support |
| `tests/assertion_free_baseline.txt` | does not exist | new — committed baseline of current offenders (size determined at S01 time) |
| `Makefile` | `quality: lint format typecheck`; no `test-assertions` target | adds `test-assertions:` target; `quality:` becomes `lint format typecheck test-assertions`; `test-assertions` added to `.PHONY` |
| `skills/iw-workflow/SKILL.md` (+ `.claude/skills/iw-workflow/SKILL.md` via sync) | canonical gate list has 5 gates (lint/format/typecheck/unit-tests/integration-tests) | adds a 6th gate `assertions` → `make test-assertions`, positioned right after `lint` |
| `.github/workflows/test-quality.yml` | `lint-typecheck` job runs lint + format + typecheck | adds `- run: make test-assertions` right after `make lint` |
| `tests/unit/test_assertion_scanner.py` | does not exist | new — covers all four categories (positive + negative) + baseline mechanic + JSON shape |
| `docs/IW_AI_Core_Testing_Strategy.md` | §9 row "AST assertion scanner: ❌"; no §8 paragraph on the scanner | §9 row → ✅ (CR-00046); a new short paragraph in §8 documenting the scanner contract and baseline mechanic |
| `skills/iw-ai-core-testing/SKILL.md` (+ `.claude/skills/` copy via sync) | §1 bans are guidance only | adds a one-line cross-reference: bans backed by `make test-assertions` / the `assertions` QV gate |
| `ai-dev/work/TESTS_ENHANCEMENT.md` | item 1.1 = TODO | item 1.1 = DONE (CR-00046); changelog entry |

### Breaking Changes

- **None.** Adding a gate that admits the current state via a baseline file is by construction non-breaking. No existing test is modified. The result-contract JSON schema is unchanged. The workflow-manifest schema is unchanged. Future Feature/CR/Incident work items will see one extra QV step in their manifest (`assertions`) — that's the *intended* effect, not a break.

### Data Migration

- **None.** No database schema or data changes. Reversible by `git revert` of the merge commit and `iw sync-skills` to regenerate the in-project skill copies from the reverted master.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | `backend-impl` | RED-first: write `tests/unit/test_assertion_scanner.py` covering every detected category (positive + negative) plus `--baseline` allowance, `--write-baseline` regeneration, and `--json` output shape. Run the new tests, capture RED. Then port + extend InnoForge's `scripts/check_test_assertions.py`. Generate `tests/assertion_free_baseline.txt` with `--write-baseline`. Add `Makefile` target + fold into `quality:`. Add `assertions` gate to `skills/iw-workflow/SKILL.md` (right after `lint`). Add the GH workflow step in `.github/workflows/test-quality.yml`. Add the §8 paragraph + flip §9 row in the strategy doc; add the cross-reference line in `skills/iw-ai-core-testing/SKILL.md`. Run `iw sync-skills`. Tick item 1.1 + add changelog entry in `ai-dev/work/TESTS_ENHANCEMENT.md`. | — |
| S02 | `code-review-impl` | Review S01: scanner correctness across all four categories (does it flag what the design says, not flag what it shouldn't); baseline file format + sortedness + comment header; exit-code semantics (`--strict` vs baseline mode); `Makefile` wiring (`quality:` rule); skill canon update (right placement in the gate list, `iw sync-skills` ran); GH workflow step (right job, right position); docs + plan updates; no out-of-scope edits (no `mutmut`/`vulture`/`deptry`/etc.). | — |
| S03 | `code-review-final-impl` | Global review: scanner ↔ unit tests ↔ baseline ↔ Makefile ↔ skill canon ↔ GH workflow ↔ docs chain is internally consistent; the `assertions` gate is wired into both CI surfaces; the testing skill's cross-reference is in sync with the strategy-doc §8 paragraph; `.claude/skills/iw-workflow/SKILL.md` reflects the master. | — |
| S04 | `qv-gate` (`lint`) | `make lint` | — |
| S05 | `qv-gate` (`assertions`) | `make test-assertions` — **the new gate, dogfooded on its own CR.** Baseline file is committed by S01; this step should pass. | — |
| S06 | `qv-gate` (`format`) | `make format-check` | — |
| S07 | `qv-gate` (`typecheck`) | `make type-check` | — |
| S08 | `qv-gate` (`unit-tests`) | `make test-unit` (includes the new `test_assertion_scanner.py`) | — |
| S09 | `qv-gate` (`integration-tests`) | `make allure-integration` (timeout 900) | — |
| S10 | `self-assess-impl` | Self-assessment of the just-completed item via the `iw-item-analyze` skill (project has `self_assess = true`). | — |

Fix cycles (`code-review-fix-impl`, `code-review-fix-final-impl`, and per-`qv-gate` fixes) are dynamic and not listed in the manifest.

### Database Changes

- **New tables**: None · **Modified tables**: None · **Migration notes**: None — no Alembic migration; no `migration-check` gate is needed in the manifest.

### API Changes

- **New endpoints**: None · **Modified endpoints**: None · **Removed endpoints**: None

### Frontend Changes

- **New components**: None · **Modified components**: None · **Removed components**: None — `browser_verification: false`.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `ai-dev/active/CR-00046/CR-00046_CR_Design.md` | Design | This document |
| `ai-dev/active/CR-00046/CR-00046_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `ai-dev/active/CR-00046/workflow-manifest.json` | Manifest | Step definitions |
| `ai-dev/active/CR-00046/prompts/CR-00046_S01_Backend_prompt.md` | Prompt | S01 implementation instructions |
| `ai-dev/active/CR-00046/prompts/CR-00046_S02_CodeReview_prompt.md` | Prompt | S02 review instructions |
| `ai-dev/active/CR-00046/prompts/CR-00046_S03_CodeReview_Final_prompt.md` | Prompt | S03 final review instructions |
| `ai-dev/active/CR-00046/prompts/CR-00046_S10_SelfAssess_prompt.md` | Prompt | S10 self-assessment instructions |

Files **changed** by the implementation (mirrored to `workflow-manifest.json:scope.allowed_paths`):
`scripts/check_test_assertions.py` · `tests/assertion_free_baseline.txt` · `tests/unit/test_assertion_scanner.py` · `Makefile` · `skills/iw-workflow/SKILL.md` · `.claude/skills/iw-workflow/SKILL.md` · `skills/iw-ai-core-testing/SKILL.md` · `.claude/skills/iw-ai-core-testing/SKILL.md` · `.github/workflows/test-quality.yml` · `docs/IW_AI_Core_Testing_Strategy.md` · `ai-dev/work/TESTS_ENHANCEMENT.md`.

Reports are created during execution under `ai-dev/work/CR-00046/reports/`.

## Acceptance Criteria

### AC1: scanner detects every category, ignores negative cases

```
Given the scanner script scripts/check_test_assertions.py
When invoked with --strict against a synthetic test file containing one example per detected category (no-assert / tautology / mock-only / broad-raises) and one negative example per category
Then it reports exactly one violation per positive example with the correct category label
And it reports zero violations against the negative examples
And the exit code is 1 (violations present)
```

### AC2: baseline mechanic blocks NEW violations only

```
Given tests/assertion_free_baseline.txt was generated at S01 time via --write-baseline against tests/
And no new violations have been introduced since
When `make test-assertions` runs (which invokes the scanner with --baseline tests/assertion_free_baseline.txt tests/)
Then exit code is 0

Given a developer adds a new test that matches a flagged category (e.g. `def test_x(): assert isinstance(foo(), dict)`)
When `make test-assertions` runs
Then exit code is 1 and the new test is reported by path:line with its category
And the existing baseline entries do NOT count as violations
```

### AC3: scanner has unit tests, written RED-first

```
Given tests/unit/test_assertion_scanner.py
When `make test-unit` runs
Then it passes
And the S01 step report's tdd_red_evidence field shows these tests failing before the scanner existed (RED-first evidence — likely an ImportError or FileNotFoundError on the scanner module)
```

### AC4: make quality runs the scanner

```
Given the Makefile has been updated
When `make quality` runs
Then it executes lint, format(-check), typecheck, AND test-assertions, in that order
And a failure in any of the four causes `make quality` to exit non-zero
And `make check` (= `quality test`) therefore also fails on new assertion-scanner violations
```

### AC5: assertions QV gate exists in the canonical set

```
Given skills/iw-workflow/SKILL.md
When you read the canonical QV-gate list
Then there are 6 gates (lint, assertions, format, typecheck, unit-tests, integration-tests), in that order
And the `assertions` gate uses agent `qv-gate`, gate name `assertions`, command `make test-assertions`
And `.claude/skills/iw-workflow/SKILL.md` matches (iw sync-skills was run)
```

### AC6: GH workflow runs the scanner

```
Given .github/workflows/test-quality.yml
When you read the lint-typecheck job
Then there is a step `- run: make test-assertions` immediately after the `- run: make lint` step
And the step is unconditional (runs on every pull_request and push to main)
```

### AC7: this CR's own assertions QV gate passes (dogfood)

```
Given S05 is the new `assertions` QV gate running `make test-assertions`
When it executes after S01's implementation has landed
Then it exits 0 (no new violations introduced by S01 — the scanner's own unit tests use real specific assertions)
```

### AC8: the plan and strategy doc are updated

```
Given ai-dev/work/TESTS_ENHANCEMENT.md
When you read the Phase 1 table and the changelog
Then item 1.1's status is DONE (CR-00046) and the changelog has a new entry

Given docs/IW_AI_Core_Testing_Strategy.md
When you read §8 and §9
Then §8 contains a paragraph documenting the scanner contract, the baseline-file mechanic, and the rule "the right way to silence the gate is to fix the test, not to add it to the baseline"
And §9's row for "AST assertion scanner" is ✅ (CR-00046)
```

### AC9: the testing skill carries the cross-reference

```
Given skills/iw-ai-core-testing/SKILL.md
When you read §1 (or §8)
Then there is a one-line note that the §1 bans are now backed by `make test-assertions` / the `assertions` QV gate (a CI failure, not a stylistic suggestion)
And .claude/skills/iw-ai-core-testing/SKILL.md matches (iw sync-skills was run)
```

## Rollback Plan

- **Database**: Not applicable — no schema or data changes.
- **Code**: `git revert` the squash-merge commit. Then run `iw sync-skills` to regenerate `.claude/skills/iw-workflow/SKILL.md` and `.claude/skills/iw-ai-core-testing/SKILL.md` from the reverted masters. The new `Makefile` target, the GH workflow step, the scanner script, the baseline file, and the unit tests are all removed by the revert; the strategy doc reverts to "❌ (1.1)" on the §9 row.
- **Data**: No data loss on rollback.

## Dependencies

- **Depends on**: CR-00045 (the `tdd_red_evidence` contract — this CR's S01 RED step records evidence in that field). CR-00045 is merged.
- **Blocks**: Nothing hard. Subsequent Phase-1 CRs (P1-CR-B coverage gates, P1-CR-C test hygiene, P1-CR-D security gates, P1-CR-E Allure + smoke SLA) are independent.

## Impacted Paths

- `scripts/check_test_assertions.py`
- `tests/assertion_free_baseline.txt`
- `tests/unit/test_assertion_scanner.py`
- `Makefile`
- `skills/iw-workflow/SKILL.md`
- `.claude/skills/iw-workflow/SKILL.md`
- `skills/iw-ai-core-testing/SKILL.md`
- `.claude/skills/iw-ai-core-testing/SKILL.md`
- `.github/workflows/test-quality.yml`
- `docs/IW_AI_Core_Testing_Strategy.md`
- `ai-dev/work/TESTS_ENHANCEMENT.md`

## TDD Approach

- **Unit tests**: `tests/unit/test_assertion_scanner.py` — one positive + one negative example per detected category (no-assert, tautology in each of its sub-forms, mock-only, broad-raises) using `ast.parse` of inline strings or `tmp_path` files; tests for the `--baseline` allowance (a violation listed in the baseline does NOT trigger an exit-1, a new one DOES); tests for `--write-baseline` (overwrites the file with the current set, sorted); tests for `--json` output shape (`{"violations": [{"path": ..., "line": ..., "category": ..., "test_name": ..., "message": ...}, ...]}`); tests for `--strict` (baseline ignored, every violation fails). This file is the RED-first anchor for S01 — written before the scanner exists, must fail with `ImportError`/`FileNotFoundError` before deliverable 1 lands, must all pass after.
- **Integration tests**: None needed — the scanner is a pure-AST script with no I/O concerns beyond file reads. End-to-end behaviour is exercised by S05 (`make test-assertions` against the real test tree with the committed baseline).
- **Updated tests**: None — no existing test is modified by this CR.

## Notes

- **`make allure-integration` for the integration gate** — follows the canonical QV-gate set in `skills/iw-workflow/SKILL.md`. As noted in CR-00045, `allure-integration` is currently a `.PHONY` stub with no recipe (plan item 1.8) — gate is effectively a no-op for now. Real integration coverage comes from `make test-integration` at the merge-queue dry-run. Fixing `allure-*` is plan item 1.8, out of scope here.
- **Baseline size unknown at design time** — InnoForge has 77 entries. We expect a similar order for 4 categories across 413 files; if it comes out very large (say >300), S01 should still commit it as-is (this CR's job is the *gate*, not the cleanup) and a follow-up "scrub the baseline" item is filed. **Do not** delete or modify existing tests to shrink the baseline.
- **`iw sync-templates` is NOT needed** — this CR edits no `templates/design/*.md` file. The QV-gate canon lives in `skills/iw-workflow/SKILL.md` (under `skills/`), and `iw sync-skills` propagates to `.claude/skills/`.
- **Cross-repo skill propagation** — `skills/iw-ai-core-testing/` is project-specific (per CR-00045's clarification) and is **not** propagated to InnoForge/podforger/cv. `skills/iw-workflow/` IS a shared workflow skill; check whether the sibling repos use `iw-workflow` — if so, the canon change there would need cross-repo propagation too (the standard `iw sync-skills` from each sibling reads its own `iw-ai-core/.claude/skills/iw-workflow/` copy via the same mechanism, so a post-merge operator step is sufficient — note in the implementation report).
- **Dogfooding S05** — the new `assertions` gate runs on this very CR (after S01 lands the scanner + baseline). The unit tests in `tests/unit/test_assertion_scanner.py` MUST use real, specific assertions (e.g. `assert violations == [{"path": "...", "line": 7, "category": "no-assert", ...}]`) — they are demonstrably not vacuous. If S05 ever fails, the implementer wrote weak tests for the very tool that detects weak tests, which would be deeply ironic and a real signal.
- **Scope discipline** — do not touch `tests-impl`/`backend-impl`/other agent definitions; do not add `mutmut`/`vulture`/`deptry`/`gitleaks`/`semgrep`/`pytest-randomly`/`diff-cover` (those are subsequent Phase-1 CRs); do not clean up existing baseline offenders; do not change the workflow-manifest schema.
- **Why `backend-impl` is the implementation agent** — the scanner is real Python with branching logic (RED-first TDD fits perfectly), and the rest is markdown + Makefile + workflow YAML edits that `backend-impl` is comfortable with. `template-impl` is for document/template-rendering systems, not this kind of process tooling. `tests-impl` only writes tests.
