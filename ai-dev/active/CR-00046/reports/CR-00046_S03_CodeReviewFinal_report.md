# CR-00046 — S03 CodeReviewFinal Report

**Step**: S03 (code-review-final-impl) — global cross-agent review
**Date**: 2026-05-11
**Status**: complete
**Verdict**: pass

## What was done

Performed the final cross-agent review of the **AST assertion-scanner gate (P1-CR-A)**
implementation as delivered by S01 and verified by S02. The review focuses on
cross-cutting concerns: integration coherence across the scanner ↔ unit-tests ↔
baseline ↔ Makefile ↔ skill canon ↔ GH workflow ↔ docs chain.

### Pre-review lint & format gate

- `make lint` → `All checks passed!` (ruff check + check_templates.py + node syntax)
- `make format` → `674 files already formatted` (no drift)

Both green on the modified file set; **zero new lint/format violations** compared
to main. No `T201` / `ERA001` / `ARG001` / `F811` / unused-import / formatting
issues in any file in the implementation's `files_changed`.

### Design-document acceptance criteria (all 9 met)

- **AC1** Scanner detects each category, ignores negatives — `tests/unit/test_assertion_scanner.py` has 17 positive/negative cases covering all 8 tautology sub-forms + the four base categories. Verified by re-running `uv run pytest tests/unit/test_assertion_scanner.py` → 29 passed.
- **AC2** Baseline mechanic blocks new violations only — `test_baseline_allows_known_offender_flags_new` exercises the path; verified `make test-assertions` exits 0 against the current tree.
- **AC3** RED-first unit tests — `tdd_red_evidence` recorded in S01 report (29/29 failed before the scanner existed; the first failure was `AssertionError: is_file() False` and subsequent tests cascaded through `JSONDecodeError` because the script did not yet exist). Plausible and matches the design's expectation.
- **AC4** `make quality` runs the scanner — `Makefile:65` reads `quality: lint format typecheck test-assertions`; `test-assertions` is in `.PHONY` line 7.
- **AC5** `assertions` gate in canonical list — `skills/iw-workflow/SKILL.md:127-134` lists 6 gates in order `lint → assertions → format → typecheck → unit-tests → integration-tests`; gate name `assertions`, agent `qv-gate`, command `make test-assertions`. `.claude/skills/iw-workflow/SKILL.md` byte-matches the master.
- **AC6** GH workflow step — `.github/workflows/test-quality.yml:23` has `- run: make test-assertions` immediately after `- run: make lint` (line 22), in the `lint-typecheck` job, unconditional on pull_request + push to main.
- **AC7** Dogfood — `make test-assertions` exits 0; running the scanner with `--strict --json` against `tests/unit/test_assertion_scanner.py` returns `{"violations": []}` (no vacuous tests in the scanner's own test file).
- **AC8** Plan + strategy doc updated — `ai-dev/work/TESTS_ENHANCEMENT.md:92` row 1.1 marked **DONE 2026-05-11 (CR-00046)**, changelog entry at line 190. `docs/IW_AI_Core_Testing_Strategy.md:190` has the new "Assertion scanner (CR-00046, P1-CR-A)" subsection with the "fix the test, not the baseline" rule; line 205 `§9` row flipped to ✅.
- **AC9** Testing-skill cross-reference — `skills/iw-ai-core-testing/SKILL.md:103` carries the block-quote cross-reference; `.claude/skills/iw-ai-core-testing/SKILL.md` byte-matches the master (verified with `diff -q`).

### Design TDD section ↔ files_changed cross-check

The design's TDD Approach (`## TDD Approach`) names exactly **one** test file by path:
`tests/unit/test_assertion_scanner.py`. Present in S01's `files_changed`. ✓

### Cross-agent / cross-file coherence

This CR was implemented by a single agent (S01 `backend-impl`), so "cross-agent"
reduces to internal coherence across the 11+ modified files. Verified end-to-end:

| Pair | Coherence |
|---|---|
| scanner ↔ unit tests | Scanner CLI surface (positional paths, `--baseline`, `--write-baseline`, `--strict`, `--json`) matches the calls in `tests/unit/test_assertion_scanner.py`. Output schema `{path, line, category, test_name, message}` matches `test_json_output_shape`. Human-readable format `path:line: category: test_name: message` matches `test_human_readable_output_format`. |
| scanner ↔ baseline file | Scanner writes `<path>::<test_name> # <category>`; the committed baseline (644 lines = 23 header + 621 data) follows that exact format with sorted body. Header references the script path correctly. |
| Makefile ↔ scanner CLI | `Makefile:63` invokes `uv run python scripts/check_test_assertions.py --baseline tests/assertion_free_baseline.txt tests/` — matches the scanner's argparse contract. |
| Makefile ↔ skill canon | Gate name `assertions`, command `make test-assertions` — match. |
| skill canon ↔ GH workflow | GH workflow step is `make test-assertions` (same command surface) — match. Note: GH workflow doesn't pass `--strict`, matching local behaviour (baseline-admitted). |
| skills/ ↔ .claude/skills/ | `diff -q .claude/skills/iw-workflow/SKILL.md skills/iw-workflow/SKILL.md` → byte-match; same for `iw-ai-core-testing`. `iw sync-skills --force` was run by S01. |
| strategy doc §8 ↔ testing skill cross-reference | Both reference the scanner, `make test-assertions`, the `assertions` QV gate, the GH workflow step, the baseline-as-cleanup-backlog framing, and the "fix the test, not the baseline" rule. No drift. |
| plan doc 1.1 ↔ implementation | Plan row 1.1 marked DONE with `(CR-00046)`; changelog entry summarises the actual deliverables (621 baseline entries, four categories, `assertions` gate added to canon, GH workflow step, etc.). |

### Test verification

- `uv run pytest tests/unit/test_assertion_scanner.py -v` → **29 passed** in 10.26 s
- `make test-unit` → **2796 passed, 4 skipped, 5 xfailed, 1 xpassed** in 67.24 s (coverage 51.87%, above floor 46.0%)
- `make test-integration` → **2256 passed, 33 skipped, 3 xfailed** in 562.42 s (coverage 61.14%, above floor)
- `make test-assertions` → exit 0, `No new assertion-scanner violations (417 files scanned).`
- `make lint` → green
- `make format` → green

### Scope discipline

The implementation respected the design's "Scope discipline" rule:
- No `mutmut` / `vulture` / `deptry` / `gitleaks` / `semgrep` / `pytest-randomly` / `diff-cover` additions.
- No cleanup of existing baseline entries.
- No agent-definition edits.
- No workflow-manifest schema change.

Two in-scope-but-not-design-named additions are justified and well-scoped:
- `pyproject.toml` per-file ignores: `T201` for the scanner script (which prints by design) and `ERA001` for the test file (whose parametrize labels look like commented-out code). Both narrowly scoped; both follow an established pattern in the file (`scripts/e2e_health_check.py` and `scripts/arch_check.py` already have `T201`).
- `.iw-skills-lock.json` lock-state update — mechanical side-effect of `iw sync-skills --force`.

### Observation (not a finding)

The active worktree contains a stray nested directory `ai-dev/active/CR-00046/CR-00046/` that mirrors the parent `ai-dev/active/CR-00046/`. It is **untracked** (does not appear in `git diff --stat`), is unrelated to the implementation, and falls outside the scope of this CR. Not raised as a finding.

## Findings

| Severity | Category | File | Description |
|---|---|---|---|
| (none) | — | — | No CRITICAL, HIGH, or MEDIUM (fixable) findings. |

S02's MEDIUM_SUGGESTION (`_mock_receiver_name` walks past `self.` to leftmost
`Name`, under-detecting `self.mock_dep.assert_called_once()`) carries over from
the per-agent review. It is correctly **out of scope** for this CR — the
implementation matches the design's stated heuristic ("an identifier whose name
contains `mock`/`Mock`"), and fixing it would expand the baseline (currently
`mock-only: 7`) without aligning with the design's "don't clean up existing
offenders in this CR" rule. Track as follow-up.

## Result contract

```json
{
  "step": "S03",
  "agent": "CodeReview_Final",
  "work_item": "CR-00046",
  "steps_reviewed": ["S01"],
  "verdict": "pass",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "make test-unit: 2796 passed, 4 skipped, 5 xfailed, 1 xpassed (coverage 51.87% / floor 46.0%); make test-integration: 2256 passed, 33 skipped, 3 xfailed (coverage 61.14%); tests/unit/test_assertion_scanner.py: 29 passed; make test-assertions: 0 new violations (417 files scanned); make lint + make format: all green.",
  "missing_requirements": [],
  "notes": "All 9 ACs met. End-to-end chain is coherent: scanner CLI ↔ unit tests ↔ committed baseline ↔ Makefile ↔ skill canon (master + .claude/ copy in sync) ↔ GH workflow ↔ docs (strategy §8 + §9 + testing-skill cross-reference + plan 1.1). Scope discipline respected — no out-of-CR additions (no mutmut/vulture/deptry/etc., no baseline cleanup, no manifest-schema change). pyproject.toml per-file-ignore additions are narrow and pattern-consistent with existing entries. .claude/skills/{iw-workflow,iw-ai-core-testing}/SKILL.md byte-match their masters (iw sync-skills --force was run). Dogfood: scanner against its own test file → 0 violations. S02's MEDIUM_SUGGESTION on _mock_receiver_name self.* walk is correctly out-of-scope here (would expand baseline cleanup the design forbids in this CR)."
}
```

## Files changed

None — this is a review step.

## Test results

See "Test verification" above. All gates green.
