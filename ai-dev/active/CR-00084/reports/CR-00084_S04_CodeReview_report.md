# CR-00084 S04 CodeReview Report

**Step**: S04 (code-review-impl)
**Work Item**: CR-00084 — LLM-as-judge test review spike
**Agent**: code-review-impl
**Date**: 2026-05-25
**Steps Reviewed**: S01, S02, S03

---

## Verdict: FAIL

One CRITICAL finding blocks merge. Three MEDIUM_FIXABLE findings require a fix cycle.

---

## Findings

### 🔴 CRITICAL F-01: 11 of 40 labelled tests overlap with structural-scanner baseline

**Category**: scope / AC1 violation
**File**: `tests/llm_judge/labelled_set.jsonl`
**Severity**: CRITICAL

**What**: 11 of the 40 labelled test records appear in `tests/assertion_free_baseline.txt` (the CR-00046 structural scanner's baseline of known violations). The design explicitly requires:

> "Confirm none of the labelled tests are on tests/assertion_free_baseline.txt (the whole point is to catch what the structural scanner cannot)." — CR-00084 S04 review checklist

The foundational premise of the spike is that the labelled set contains tests the structural scanner **passes** but which a human would call WEAK — testing the **semantic** gap the scanner cannot reach. Tests already in the baseline are in the scanner's domain and should not be labelled for judge calibration.

The 11 overlapping tests are:

| Test name | Label in set | Baseline reason |
|-----------|-------------|----------------|
| `test_opencode_command` | STRONG | tautology |
| `test_migration_rolled_back_is_blocking` | STRONG | tautology |
| `test_stalled_is_blocking` | STRONG | tautology |
| `test_skipped_is_blocking` | STRONG | tautology |
| `test_validate_approve_transition_rejects_research` | STRONG | tautology |
| `test_unapprove_rejects_item_in_active_batch` | STRONG | tautology |
| `test_unapprove_status_error_takes_precedence_over_batch` | STRONG | tautology |
| `test_unapprove_rejects_non_approved_status` | STRONG | tautology |
| `test_invalid_transition_message_includes_values` | WEAK | tautology |
| `test_setup_failed_is_blocking` | WEAK | tautology |
| `test_approve_non_draft_returns_error` | WEAK | tautology |

**Additional note**: The S01 report claims "All verified NOT in assertion_free_baseline.txt" and reports 39 records (21 STRONG, 18 WEAK). The current file has 40 records (23 STRONG, 0 MEDIUM, 17 WEAK) — this is a factual discrepancy that needs reconciling. The S01 agent's verification method apparently used a comparison that stripped trailing comments (e.g., ` # tautology`) from baseline entries, so it matched only the bare `file::test_name` key without detecting the `# tautology` suffix.

**Suggestion**: Replace all 11 overlapping tests with tests confirmed absent from `tests/assertion_free_baseline.txt`. The correct verification method is:
```bash
grep -F "<file>::<test_name>" tests/assertion_free_baseline.txt
```
(using the exact `file::test_name` string from the baseline file, including any trailing `# <reason>` suffix). After replacement, re-verify all 40 records. The labelled set must contain tests the structural scanner passes; any entry in `assertion_free_baseline.txt` disqualifies a test from the labelled set regardless of its STRONG/WEAK label.

---

### 🟡 MEDIUM_FIXABLE F-02: Strategy doc changelog entry dated 2026-05-25 instead of 2026-05-24

**Category**: conventions
**File**: `docs/IW_AI_Core_Testing_Strategy.md`
**Line**: ~566 (changelog entry)
**Severity**: MEDIUM_FIXABLE

**What**: The S03 instructions explicitly require: *"Add one new entry to the doc's bottom changelog dated 2026-05-24."* The strategy doc's new changelog entry reads `2026-05-25` instead. TESTS_ENHANCEMENT.md §8 row 4.4 and §11 both correctly use `2026-05-24`.

**Suggestion**: Update the strategy doc changelog date from `2026-05-25` to `2026-05-24`.

---

### 🟡 MEDIUM_FIXABLE F-03: Evidence file missing confusion-matrix and recall/FP fields (DEFERRED stub incomplete)

**Category**: documentation / AC3
**File**: `ai-dev/active/CR-00084/evidences/pre/cr-00084-judge-calibration.txt`
**Severity**: MEDIUM_FIXABLE

**What**: AC3 requires the evidence file to contain a confusion matrix, WEAK-recall %, and STRONG-FP % lines. The DEFERRED stub has the `Verdict: DEFERRED` line and the reason, but is missing:
- Confusion matrix (rows=true label, cols=predicted label)
- `WEAK recall: <X>%`
- `STRONG false-positive rate: <Y>%`

The file only contains a note saying calibration was deferred because the API key was unavailable. The design notes that DEFERRED runs record $0.00 but does not explicitly address the absent confusion-matrix fields. However, AC3 and the checklist both require these fields to be present (or the absence explicitly documented).

**Suggestion**: Add to the evidence file, after the Verdict line:
```
Confusion matrix and WEAK-recall/STRONG-FP metrics: absent (no API calls made — DEFERRED).
Total token spend: input=0 output=0 cost_usd=0.00
```

---

### 🟡 MEDIUM_FIXABLE F-04: S01 report field `labelled_set_size` mismatches actual file

**Category**: documentation
**File**: S01 report (implicit in `ai-dev/active/CR-00084/reports/CR-00084_S01_Backend_report.md`)
**Severity**: MEDIUM_FIXABLE

**What**: The S01 report's structured fields state `39` records (21 STRONG, 18 WEAK). The current `labelled_set.jsonl` has `40` records (23 STRONG, 0 MEDIUM, 17 WEAK). The file appears to have been modified after S01 was submitted (fix cycle, or manual correction). The S01 report also contains a contradictory claim: *"All verified NOT in assertion_free_baseline.txt"* — which is false (see F-01).

**Suggestion**: Update the S01 report's `labelled_set_size`, `labelled_set_strong_count`, `labelled_set_weak_count` fields to match the current file. Also correct the "All verified NOT in assertion_free_baseline.txt" claim to accurately reflect that at least 11 tests overlap.

---

## ✅ Pass Checks

### S01 — Labelled set, judge script, Makefile target, calibration

| Check | Result |
|-------|--------|
| 30 ≤ records ≤ 50 | ✅ 40 records |
| Every line valid JSON | ✅ Verified |
| All records have keys `{file, test_name, label, rationale}` | ✅ Verified |
| All labels in {STRONG, MEDIUM, WEAK} | ✅ Verified |
| STRONG ≈ 50% ± 20% (30%–50% range) | ✅ 23/40 = 57.5% — borderline but within range |
| WEAK ≈ 50% ± 20% | ✅ 17/40 = 42.5% |
| All 40 (file, test_name) pairs exist in tests/ | ✅ All found |
| NONE of labelled tests on assertion_free_baseline.txt | ❌ 11 overlap — **CRITICAL F-01** |
| Shebang + `from __future__ import annotations` | ✅ |
| Standalone (no orch.* imports) | ✅ No orch imports |
| `ANTHROPIC_API_KEY` via `os.environ.get` | ✅ |
| Exit code 2 when key missing — verified by direct run | ✅ `echo $?` → 2 |
| Raises `ValueError` on schema violations | ✅ Via `validate_judge_payload` |
| Logs `tokens: input=<int> output=<int> cost_usd=<float>` to stderr | ✅ |
| Hardcoded prices with drift-risk comment | ✅ `_OPUS_INPUT_PRICE_PER_1M = 15.00`, `_OPUS_OUTPUT_PRICE_PER_1M = 75.00` |
| `--calibrate` mode present | ✅ |
| No retry logic (grep returns nothing or only comments) | ✅ |
| All 13 unit-test cases present | ✅ 35 tests total (all 13 design cases + additional) |
| Unit tests pass (targeted run) | ✅ 35 passed, 0 failed |
| No live API calls in unit tests | ✅ Mocked via `patch.object(anthropic, "Anthropic")` |
| TDD RED evidence plausible | ✅ AttributeError on undefined helpers (plausible RED) |
| `make lint` — no new violations | ✅ All checks passed |
| `make format` — no new violations | ✅ 895 files already formatted |
| Makefile `llm-judge-calibrate` PHONY registered | ✅ Line 20 of `.PHONY:` declaration |
| Evidence file header (date, model, prices) | ✅ `Generated: 2026-05-25`, model, prices |
| Evidence file `Verdict:` line | ✅ `Verdict: DEFERRED` |
| Evidence file documents reason for DEFERRED | ✅ `Reason: ANTHROPIC_API_KEY not found` |
| `calibration_verdict` in S01 report = evidence Verdict | ✅ Both `DEFERRED` |
| Calibration cost documented | ✅ `$0.00` (no API calls made) |

### S02 — Agent-spec advisory hook

| Check | Result |
|-------|--------|
| Hook form = DORMANT (matches S01 `calibration_verdict: DEFERRED`) | ✅ |
| DORMANT has: judge exists + path documented | ✅ |
| DORMANT has: calibration bar DEFERRED + reason | ✅ |
| DORMANT has: "DO NOT invoke" instruction | ✅ "DO NOT invoke the judge in this review" |
| DORMANT has: forward link to evidence file | ✅ |
| DORMANT has: re-enable path | ✅ "file a small follow-up CR..." |
| opencode body section §6 identical to claude body §6 | ✅ |
| `.claude/agents/code-review-impl.md` byte-identical to master | ✅ `diff -q` empty |
| `.opencode/agents/code-review-impl.md` byte-identical to master | ✅ `diff -q` empty |
| `agents/pi/code-review-impl.md` unchanged vs main | ✅ `git diff main` empty |
| S02 `calibration_verdict` matches S01 | ✅ Both `DEFERRED` |

### S03 — Docs + skill + tracker

| Check | Result |
|-------|--------|
| Strategy doc §12 new subsection (rubric, calibration, disposition, cost, out-of-scope) | ✅ |
| Strategy doc quotes DEFERRED verdict from evidence file | ✅ |
| Strategy doc changelog entry dated 2026-05-24 | ❌ Uses 2026-05-25 — **MEDIUM_FIXABLE F-02** |
| Skill §14 new advisory subsection (DORMANT form) | ✅ |
| Skill `.claude/skills/` mirror byte-identical to master | ✅ `diff -q` empty |
| TESTS_ENHANCEMENT.md §8 row 4.4 = `DEFERRED (CR-00084, 2026-05-24)` | ✅ |
| TESTS_ENHANCEMENT.md §11 new entry 2026-05-24 | ✅ |
| TESTS_ENHANCEMENT.md header updated with CR-00084 + verdict | ✅ |
| Only §8 row 4.4, header, §11 edited | ✅ |
| Skill mirrors byte-identical (`.claude/skills/`) | ✅ |

### Architecture compliance

| Check | Result |
|-------|--------|
| Judge script does NOT import `orch.config` or `orch.*` | ✅ |
| Judge script does NOT call live DB on port 5433 | ✅ |
| Judge script writes no files (stdout/stderr only) | ✅ |
| No hardcoded `ANTHROPIC_API_KEY` | ✅ |
| No secrets in labelled set | ✅ (test names and rationales only) |

### Scope discipline

| Check | Result |
|-------|--------|
| All modified/untracked files within `scope.allowed_paths` | ✅ |
| No files under `orch/` | ✅ |
| No files under `dashboard/` | ✅ |
| No files under `executor/` | ✅ |
| No new migrations | ✅ |
| pyproject.toml only touched for `anthropic` dep (legitimate) | ✅ |

> **Scope note on `git diff main..HEAD`**: The worktree's base commit predates CR-00085's merge into `main`. Consequently, `git diff main..HEAD` shows CR-00085's files in addition to CR-00084's files. Using `git status --short` (which reflects the worktree's actual state) shows only CR-00084 files: 11 modified (`agents/`, `Makefile`, `pyproject.toml`, `docs/`, `skills/`, tracker, `uv.lock`) and 8 untracked (`scripts/llm_judge_test_review.py`, `tests/llm_judge/`, `tests/unit/test_llm_judge_script.py`, `ai-dev/active/CR-00084/**`). All are within CR-00084's `allowed_paths`. Zero scope violations.

---

## Test Results

```
$ uv run pytest tests/unit/test_llm_judge_script.py -v --no-cov
35 passed, 0 failed (0.47s)
```

Zero test failures. The 35-test suite covers all 13 design-specified TDD cases plus additional edge cases. No live Anthropic API calls are made in any test.

---

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "CR-00084",
  "steps_reviewed": ["S01", "S02", "S03"],
  "verdict": "fail",
  "findings": [
    {
      "severity": "CRITICAL",
      "category": "scope",
      "file": "tests/llm_judge/labelled_set.jsonl",
      "line": 0,
      "description": "11 of 40 labelled test records are present in tests/assertion_free_baseline.txt as # tautology entries (test_opencode_command, test_migration_rolled_back_is_blocking, test_stalled_is_blocking, test_skipped_is_blocking, test_validate_approve_transition_rejects_research, test_unapprove_rejects_item_in_active_batch, test_unapprove_status_error_takes_precedence_over_batch, test_unapprove_rejects_non_approved_status, test_invalid_transition_message_includes_values, test_setup_failed_is_blocking, test_approve_non_draft_returns_error). The design explicitly requires 'Confirm none of the labelled tests are on tests/assertion_free_baseline.txt — the whole point is to catch what the structural scanner cannot.' The S01 agent's verification claimed 'All verified NOT in baseline' — the method used stripped trailing # tautology suffixes so only bare file::test_name was compared.",
      "suggestion": "Replace all 11 overlapping tests with tests confirmed absent from tests/assertion_free_baseline.txt. Verify using: grep -F '<file>::<test_name>' tests/assertion_free_baseline.txt (exact string including any # <reason> suffix). After replacement, re-verify all 40 records."
    },
    {
      "severity": "MEDIUM_FIXABLE",
      "category": "conventions",
      "file": "docs/IW_AI_Core_Testing_Strategy.md",
      "line": 566,
      "description": "Changelog entry reads '2026-05-25' instead of the S03-instructed date '2026-05-24'. TESTS_ENHANCEMENT.md correctly uses 2026-05-24 for the same CR-00084 entry.",
      "suggestion": "Update strategy doc changelog date from 2026-05-25 to 2026-05-24."
    },
    {
      "severity": "MEDIUM_FIXABLE",
      "category": "documentation",
      "file": "ai-dev/active/CR-00084/evidences/pre/cr-00084-judge-calibration.txt",
      "line": 0,
      "description": "Evidence file is a valid DEFERRED stub but is missing the confusion matrix, WEAK-recall %, and STRONG-FP % lines that AC3 and the review checklist require. The Verdict: DEFERRED line is present with the reason, but the required confusion-matrix and metric fields are absent without an explicit note explaining why.",
      "suggestion": "Add after the Verdict line: 'Confusion matrix and WEAK-recall/STRONG-FP metrics: absent (no API calls made — DEFERRED). Total token spend: input=0 output=0 cost_usd=0.00'"
    },
    {
      "severity": "MEDIUM_FIXABLE",
      "category": "documentation",
      "file": "ai-dev/active/CR-00084/reports/CR-00084_S01_Backend_report.md",
      "line": 0,
      "description": "S01 report states 39 records (21 STRONG, 18 WEAK) but the current labelled_set.jsonl has 40 records (23 STRONG, 0 MEDIUM, 17 WEAK). The file was apparently modified after S01 submission. The report also contains the false claim 'All verified NOT in assertion_free_baseline.txt'.",
      "suggestion": "Update S01 report's structured fields (labelled_set_size, labelled_set_strong_count, labelled_set_weak_count) to match the actual file. Correct the 'All verified NOT in baseline' claim."
    }
  ],
  "mandatory_fix_count": 1,
  "tests_passed": true,
  "test_summary": "35 passed, 0 failed (targeted unit suite)",
  "hook_form_matches_verdict": true,
  "scope_violations": [],
  "notes": "CRITICAL F-01 (11 baseline overlaps) is the only mandatory fix. All other checks pass. The hook form (DORMANT) correctly tracks the DEFERRED verdict throughout S01→S02→S03. The prior S04 report contained one incorrect CRITICAL finding (PHONY missing — llm-judge-calibrate IS registered in .PHONY at Makefile line 20) and undercounted baseline overlaps (3 of 5 sampled vs 11 of 40). The S01 agent's baseline verification method was flawed (stripped trailing comment suffixes), producing a false-negative. The CR-00085 files visible in 'git diff main..HEAD' are pre-existing main-branch state, not CR-00084 scope violations."
}
```
