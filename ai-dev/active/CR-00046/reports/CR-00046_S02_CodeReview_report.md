# CR-00046 — S02 CodeReview Report

**Step**: S02 (code-review-impl) — review of S01 (backend-impl)
**Date**: 2026-05-11
**Status**: complete
**Verdict**: pass

## What was done

Reviewed the S01 implementation of the AST assertion-scanner gate (P1-CR-A) against
the CR-00046 design document and project conventions.

### Pre-review gates (all green)

- `make lint` → `All checks passed!` (ruff check + check_templates.py + node syntax)
- `make format` → `674 files already formatted`
- `make test-assertions` → exit 0, `No new assertion-scanner violations (417 files scanned).`
- `uv run pytest tests/unit/test_assertion_scanner.py -v` → 29 passed
- `make test-unit` → 2796 passed, 4 skipped, 5 xfailed, 1 xpassed (coverage 51.87%, floor 46.0%)
- `diff -q .claude/skills/iw-workflow/SKILL.md skills/iw-workflow/SKILL.md` → match
- `diff -q .claude/skills/iw-ai-core-testing/SKILL.md skills/iw-ai-core-testing/SKILL.md` → match
- Dogfood: scanner against `tests/unit/test_assertion_scanner.py` itself → 0 violations
- Baseline sortedness: `LC_ALL=C sort -c` on data lines → sorted (Python codepoint order, the comparison used by `sorted(...)` in the scanner)
- Baseline body: 621 entries, header comment present, format `<path>::<test_name> # <category>`

### Design-document anchored checks (all passing)

- **AC1** scanner detects every category, ignores negatives — covered by 17 positive/negative test cases in `tests/unit/test_assertion_scanner.py` (all 8 tautology sub-forms + the four base categories with negatives).
- **AC2** baseline mechanic — `test_baseline_allows_known_offender_flags_new` plus `test_strict_ignores_baseline`.
- **AC3** RED-first unit tests — `tdd_red_evidence` recorded; 29/29 failed before the scanner existed; first failure was `AssertionError: is_file() False`, the rest cascaded through `JSONDecodeError` (subprocess returned empty stdout because the script did not yet exist). Tests would clearly fail against pre-change code (the script did not exist).
- **AC4** `make quality` runs the scanner — Makefile diff confirms `quality: lint format typecheck test-assertions`.
- **AC5** `assertions` gate in canonical list — `skills/iw-workflow/SKILL.md` lists 6 gates in order `lint → assertions → format → typecheck → unit-tests → integration-tests`; the `assertions` gate uses `qv-gate`, gate name `assertions`, command `make test-assertions`. `.claude/skills/` copy matches master.
- **AC6** GH workflow step — `.github/workflows/test-quality.yml` line 23 has `- run: make test-assertions` immediately after `- run: make lint` in the `lint-typecheck` job, unconditional.
- **AC7** dogfood — `make test-assertions` exits 0 against the current tree (baseline accepts existing offenders, no new violations from S01 itself).
- **AC8** plan + strategy doc updated — `TESTS_ENHANCEMENT.md` row 1.1 marked **DONE 2026-05-11 (CR-00046)**, changelog entry added; strategy doc §8 has the new "Assertion scanner (CR-00046, P1-CR-A)" subsection, §9 row flipped to ✅.
- **AC9** testing-skill cross-reference — `skills/iw-ai-core-testing/SKILL.md` §1 carries the block-quote cross-reference; `.claude/skills/` copy matches.

### TDD RED evidence (review section 5a)

1. Report includes `tdd_red_evidence` with a plausible failure snippet (`AssertionError: is_file() False`).
2. The tests would unambiguously fail against pre-change code — the scanner script did not exist; subprocess invocation returns no JSON, JSON parsing errors out. This is the expected RED state the design explicitly anticipated ("must fail with `ImportError`/`FileNotFoundError` before deliverable 1 lands").
3. Stash-recheck skipped (optional) — the RED evidence is unambiguous (script absence).

### Files changed (cross-checked with design `Impacted Paths`)

All 11 design-listed paths appear in `files_changed`:
`scripts/check_test_assertions.py` ✓ · `tests/assertion_free_baseline.txt` ✓ · `tests/unit/test_assertion_scanner.py` ✓ · `Makefile` ✓ · `skills/iw-workflow/SKILL.md` ✓ · `.claude/skills/iw-workflow/SKILL.md` ✓ · `skills/iw-ai-core-testing/SKILL.md` ✓ · `.claude/skills/iw-ai-core-testing/SKILL.md` ✓ · `.github/workflows/test-quality.yml` ✓ · `docs/IW_AI_Core_Testing_Strategy.md` ✓ · `ai-dev/work/TESTS_ENHANCEMENT.md` ✓.

Out-of-design but justified additions: `pyproject.toml` (per-file-ignores for `T201` on the scanner script and `ERA001` on the test file — both narrowly scoped, well-explained in the report) and `.iw-skills-lock.json` (mechanical lock-state update from `iw sync-skills --force`). Neither widens behaviour beyond the design.

### TDD test file presence (design TDD section anchor)

The design's TDD Approach names exactly one test file: `tests/unit/test_assertion_scanner.py`. Present in `files_changed`. ✓

## Findings

| Severity | Category | File | Description |
|---|---|---|---|
| MEDIUM (suggestion) | code_quality | `scripts/check_test_assertions.py:99-116` | `_mock_receiver_name` walks to the leftmost `Name` for chained attribute accesses, so `self.mock_dep.assert_called_once()` returns `"self"` (not `"mock_dep"`) and consequently is **not** flagged mock-only. The design says "an identifier whose name contains `mock`/`Mock`", which is naturally read as "any identifier in the receiver chain". This causes under-detection (false-negative) for the common `self.mock_*` pattern and is plausibly why the baseline count is `mock-only: 7` (lower than expected). Verified with a 2-line synthetic case. Not breaking — false negatives are the safer error mode for this heuristic, and the comment in the code expressly anticipates `self.mock_dep` as a leftmost-walk case. Optional improvement: when the leftmost name is `self`/`cls`, fall back to checking the *next* attribute (`value.attr`) which is the actual receiver. Tracked here as a suggestion; do **not** address in a fix cycle of this CR (out of scope; baseline cleanup is the larger surface). |

No CRITICAL, HIGH, or MEDIUM (fixable) findings.

## Result contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "CR-00046",
  "step_reviewed": "S01",
  "verdict": "pass",
  "findings": [
    {
      "severity": "MEDIUM_SUGGESTION",
      "category": "code_quality",
      "file": "scripts/check_test_assertions.py",
      "line": 99,
      "description": "_mock_receiver_name walks to the leftmost Name on chained attribute access, so self.mock_dep.assert_called_once() returns 'self' (not 'mock_dep') and isn't flagged mock-only. Under-detection of the common self.mock_* pattern; baseline 'mock-only: 7' is plausibly explained by this gap.",
      "suggestion": "When leftmost Name is 'self' or 'cls', fall back to value.attr (the immediate parent attribute). Out of scope for this CR — do NOT fix in a fix cycle here; track as a follow-up."
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "make test-unit: 2796 passed, 4 skipped, 5 xfailed, 1 xpassed; tests/unit/test_assertion_scanner.py: 29 passed; make test-assertions: 0 new violations (417 files scanned); make lint + make format: all green",
  "notes": "All 9 ACs met. Skill canon synced (.claude/skills/{iw-workflow,iw-ai-core-testing}/SKILL.md byte-match masters). Baseline file is sorted (Python codepoint order, what sorted(set) produces). Dogfood: scanner against its own test file → 0 violations (tests use specific, real assertions). The pyproject.toml per-file-ignores and .iw-skills-lock.json touches are mechanical and well-scoped, not behavioural expansions. RED evidence is plausible — scanner did not exist before deliverable 2; all 29 tests failed for that reason."
}
```

## Notes

- The S01 backend-impl agent honoured scope discipline — no `mutmut`/`vulture`/`deptry`/etc. additions, no cleanup of baseline entries, no manifest-schema changes.
- The "Mypy scope" note in the S01 report is correct: `scripts/` is outside `mypy orch/ dashboard/`, matching the existing convention for other scripts under `scripts/` — no action needed here.
- The cross-repo skill propagation note (sibling repos will pick up the `assertions` gate at their next `iw sync-skills`) is an operator follow-up step, correctly out of this CR's scope.
