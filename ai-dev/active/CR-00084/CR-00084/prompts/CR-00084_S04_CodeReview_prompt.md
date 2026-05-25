# CR-00084_S04_CodeReview_prompt

**Work Item**: CR-00084 -- LLM-as-judge test review (spike) — a stronger model scores newly-written tests against an assertion-strength rubric; advisory-only signal in the CodeReview step
**Steps Being Reviewed**: S01 (backend-impl), S02 (backend-impl), S03 (backend-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits

(Standard policy. See S01 prompt for full text. This step does not touch Docker.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This step adds no migrations and you must not run `alembic upgrade`/`downgrade`/`stamp` against the live orch DB.)

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00084 --json`
- `ai-dev/work/CR-00084/CR-00084_CR_Design.md` — Design document (READ ACs 1–7)
- `ai-dev/work/CR-00084/reports/CR-00084_S01_Backend_report.md`
- `ai-dev/work/CR-00084/reports/CR-00084_S02_Backend_report.md`
- `ai-dev/work/CR-00084/reports/CR-00084_S03_Backend_report.md`
- `ai-dev/active/CR-00084/evidences/pre/cr-00084-judge-calibration.txt`
- All files listed in S01/S02/S03 reports' `files_changed`

## Output Files

- `ai-dev/work/CR-00084/reports/CR-00084_S04_CodeReview_report.md`

## Context

You are reviewing **three implementation steps** (S01, S02, S03) in a single pass. Per-step reviews would duplicate work because S02 and S03 are conditional on S01's outcome — easier to review them together.

Read the design document **before** the lint/format gate. Read all three impl reports. Then review every file in their combined `files_changed`.

## Read the Design Document FIRST

Read every AC in full. Carry the AC list into the review checklist below as the first-class anchor.

Key TDD-section requirements to verify by path:

- `tests/unit/test_llm_judge_script.py` MUST appear in S01's `files_changed` (TDD section names it explicitly).
- `tests/llm_judge/labelled_set.jsonl` MUST appear in S01's `files_changed`.
- `scripts/llm_judge_test_review.py` MUST appear in S01's `files_changed`.
- `Makefile` MUST appear in S01's `files_changed`.
- `agents/{claude,opencode}/code-review-impl.md` + the two mirror files MUST appear in S02's `files_changed`.
- `docs/IW_AI_Core_Testing_Strategy.md`, `skills/iw-ai-core-testing/SKILL.md`, `.claude/skills/iw-ai-core-testing/SKILL.md`, `ai-dev/work/TESTS_ENHANCEMENT.md` MUST appear in S03's `files_changed`.

Any missing → CRITICAL finding.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading any code, run on all changed files:

```bash
make lint
make format
```

If either reports NEW violations in the changed files (not pre-existing on `main`), classify each as a CRITICAL finding (`category: conventions`, exact violation code + message). Fix nothing yourself — only report.

If a command is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. S01 — Labelled set, judge script, Makefile target, calibration

- **Labelled set** (`tests/llm_judge/labelled_set.jsonl`):
  - 30 ≤ records ≤ 50 (count lines: `wc -l tests/llm_judge/labelled_set.jsonl`).
  - Every line is valid JSON (try `python3 -c "import json,sys; [json.loads(l) for l in open(sys.argv[1])]" tests/llm_judge/labelled_set.jsonl`).
  - Every record has keys `{file, test_name, label, rationale}`, every label is in `{STRONG, MEDIUM, WEAK}`.
  - STRONG count is approximately half (within ±20%): `>= 0.30 * total` and `<= 0.50 * total` STRONG; same range for WEAK.
  - Spot-check 5 random `(file, test_name)` pairs: confirm the test exists in `tests/`.
  - Spot-check 3 records: confirm the `rationale` actually justifies the label (read the test, judge it yourself).
  - Confirm none of the labelled tests are on `tests/assertion_free_baseline.txt` (the whole point is to catch what the structural scanner cannot): `grep -F "<test_name>" tests/assertion_free_baseline.txt` returns empty for each sample.
- **Judge script** (`scripts/llm_judge_test_review.py`):
  - Shebang + `from __future__ import annotations` + standalone (does NOT import `orch.config` or `orch.*`).
  - Reads `ANTHROPIC_API_KEY` from `os.environ.get`; **exits with code 2** when missing (specifically, not 0, not 1). Verify by running: `unset ANTHROPIC_API_KEY; uv run python scripts/llm_judge_test_review.py --test-file tests/unit/<x>.py --test-name <y>; echo $?` → 2.
  - Validates the LLM response against the documented schema; raises `ValueError` on shape violations; exits 1 on validation failure or API failure (distinguishable from missing-key = 2).
  - Logs `tokens: input=<int> output=<int> cost_usd=<float>` to stderr (NOT stdout).
  - Hardcoded prices `_OPUS_INPUT_PRICE_PER_1M = 15.00` and `_OPUS_OUTPUT_PRICE_PER_1M = 75.00` with a comment noting drift risk.
  - Has a `--calibrate <jsonl>` mode that drives the loop in-process (the Makefile target is a thin shell wrapper).
  - **No retry** on judge call failure (`grep -i "retry\|attempt" scripts/llm_judge_test_review.py` should return nothing or only comments).
- **Unit tests** (`tests/unit/test_llm_judge_script.py`):
  - All 13 cases the design enumerates are present (each test name maps to one in the TDD section).
  - Tests do NOT call the live Anthropic API — verify by grepping for `Anthropic(` instantiation outside `if __name__` or fixture mocks.
  - Run targeted: `uv run pytest tests/unit/test_llm_judge_script.py -v` — zero failures.
  - TDD RED evidence in S01 report's `tdd_red_evidence` is plausible (AssertionError/AttributeError/NotImplementedError, not ImportError/SyntaxError/collection error).
- **Makefile target**:
  - `grep -E "^llm-judge-calibrate:" Makefile` finds the recipe.
  - `grep -E "^\.PHONY:.*llm-judge-calibrate" Makefile` (or a `.PHONY: llm-judge-calibrate` line) confirms PHONY registration.
  - The recipe is a thin wrapper that invokes the script's `--calibrate` mode.
- **Calibration evidence file** (`ai-dev/active/CR-00084/evidences/pre/cr-00084-judge-calibration.txt`):
  - Header line includes date, model id, input/output prices used.
  - Body contains the confusion matrix, `WEAK recall: <X>%`, `STRONG false-positive rate: <Y>%`, `Verdict: MET|NOT_MET`, `Total token spend: input=<I> output=<O> cost_usd=<C>`.
  - If `Verdict: NOT_MET`, the file documents what went wrong (which axes scored poorly, which records were misclassified) — not just the bare verdict.
  - Total cost < $2.00, OR the overrun is explicitly noted in S01's report `notes`.
  - `calibration_verdict` in S01's report MATCHES the `Verdict:` line in this file (CRITICAL if they disagree).

### 2. S02 — Agent-spec advisory hook

- Hook form (LIVE vs DORMANT) in `agents/claude/code-review-impl.md` MATCHES `calibration_verdict` from S01 (LIVE if MET, DORMANT otherwise). CRITICAL if they disagree.
- The LIVE form has all five mandatory clauses: (1) optional invocation on new test files; (2) advisory subsection in review report; (3) **MUST NOT raise verdict to fail** language is explicit; (4) graceful skip when `ANTHROPIC_API_KEY` is missing; (5) per-review cost cap (< $0.50).
- The DORMANT form has the forward link to the calibration evidence file AND the "DO NOT invoke" instruction AND the re-enable path.
- `agents/opencode/code-review-impl.md` is the same content as `agents/claude/code-review-impl.md` (allowed differences: only YAML frontmatter fields like `model:` if the opencode spec uses them differently; the body section must match). `diff agents/claude/code-review-impl.md agents/opencode/code-review-impl.md` should show only frontmatter delta.
- Mirrors are byte-identical to masters: `diff -q agents/claude/code-review-impl.md .claude/agents/code-review-impl.md` and `diff -q agents/opencode/code-review-impl.md .opencode/agents/code-review-impl.md` both produce no output.
- `agents/pi/code-review-impl.md` is **unchanged** — `git diff main -- agents/pi/code-review-impl.md` is empty (touching it would be a CRITICAL scope violation).

### 3. S03 — Docs + skill + tracker

- Strategy doc has a new subsection with: rubric (3 axes, 1–5 scale, bucketing rule), calibration outcome (verdict + recall + FP + labelled-set size + cost), current disposition (LIVE/DORMANT and where), cost discipline, out-of-scope note. Quote the verdict and percentages from the evidence file — they must match.
- Strategy doc's bottom changelog has one new entry dated 2026-05-24.
- Skill `skills/iw-ai-core-testing/SKILL.md` has a new "Advisory: LLM-as-judge signal (CR-00084)" subsection. Form (LIVE vs DORMANT) matches the agent spec.
- `.claude/skills/iw-ai-core-testing/SKILL.md` is byte-identical to the master: `diff -q skills/iw-ai-core-testing/SKILL.md .claude/skills/iw-ai-core-testing/SKILL.md` produces no output.
- Tracker §8 row 4.4 reads `DONE (CR-00084, 2026-05-24)` or `DEFERRED (CR-00084, 2026-05-24)`. Reference column says `CR-00084`. Status matches S01's verdict.
- Tracker §11 has a new dated entry covering: labelled-set artefact, judge-script artefact, verdict + percentages, cost vs budget, hook form, forward link from CR-00046 mentioned inline.
- Tracker header v1.3 status block has one new sentence mentioning CR-00084 + verdict.
- No other tracker section is edited beyond row 4.4, header, and §11.

### 4. Scope discipline (cross-step)

- `git diff --name-only main..HEAD` shows ONLY files under the CR's `scope.allowed_paths`:
  - `tests/llm_judge/**`
  - `tests/unit/test_llm_judge_script.py`
  - `scripts/llm_judge_test_review.py`
  - `agents/claude/code-review-impl.md` and `agents/opencode/code-review-impl.md`
  - `.claude/agents/code-review-impl.md` and `.opencode/agents/code-review-impl.md`
  - `Makefile`
  - `docs/IW_AI_Core_Testing_Strategy.md`
  - `skills/iw-ai-core-testing/**`
  - `.claude/skills/iw-ai-core-testing/**`
  - `ai-dev/work/TESTS_ENHANCEMENT.md`
  - `ai-dev/active/CR-00084/**`
  - `pyproject.toml` + `uv.lock` (only if S01 added the `anthropic` dep; if it was already present, these should NOT be touched — flag as scope violation if they appear in the diff without justification)
- **Zero files** under `orch/`, `dashboard/`, `executor/` (except the four agent-spec files explicitly above which live under `agents/` and `.claude/agents/` / `.opencode/agents/`).
- No new migrations in `orch/db/migrations/versions/`.

### 5. Architecture compliance

- The judge script does NOT import `orch.config` or any `orch.*` module — it is a standalone utility. CRITICAL if it does.
- The judge script does NOT call the live DB on port 5433. CRITICAL if it does.
- The judge script does NOT write any file outside of stdout/stderr (the labelled set is read-only input; the calibration evidence file is written by the Makefile target via shell redirection, not by Python `open(..., "w")`). MEDIUM_FIXABLE if it does.

### 6. Security

- `ANTHROPIC_API_KEY` is **read from environment only** — no hardcoded key. CRITICAL if hardcoded.
- `gitleaks` / `make security-secrets` will run as S13; pre-check by grepping the diff for anything that looks like an API key (`sk-ant-`, etc.) — CRITICAL if found.
- The labelled set JSONL contains test names and rationales only — no source-code snippets, no API keys.

### 5a. TDD RED Evidence (S01 only — S02 and S03 are doc-only)

- S01's `tdd_red_evidence` is present and plausible (AttributeError on `_validate_judge_payload` not yet defined, AssertionError on the loader, etc. — not ImportError or collection error).
- For at least one of the 13 unit tests, reason whether it would fail against the script *before* S01 implemented it. (You do not need to stash-revert; just reason.)
- S02 and S03 use the `"n/a — <reason>"` form for `tdd_red_evidence`.

## Test Verification (NON-NEGOTIABLE)

Run targeted unit suite (no live API needed):

```bash
uv run pytest tests/unit/test_llm_judge_script.py -v
```

Report results in the contract. **Do NOT** run `make test-integration` or `make llm-judge-calibrate` — those are S10 and an out-of-band operator action respectively.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Breaks functionality, scope violation, hook-form-mismatch-vs-verdict, missing required artefact, API key hardcoded | Must fix before merge |
| **HIGH** | Significant bug, missing AC, advisory hook implicitly blocks (any path where the judge score affects `verdict`/`mandatory_fix_count`) | Must fix before merge |
| **MEDIUM (fixable)** | Code quality, missing edge case, convention drift | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Design improvement | Optional |
| **LOW** | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "CR-00084",
  "steps_reviewed": ["S01", "S02", "S03"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing|scope",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "hook_form_matches_verdict": true,
  "scope_violations": [],
  "notes": ""
}
```

- `verdict`: `pass` iff zero CRITICAL + zero HIGH + zero MEDIUM_FIXABLE findings.
- `mandatory_fix_count`: CRITICAL + HIGH + MEDIUM_FIXABLE.
- `hook_form_matches_verdict`: explicitly track this — it is the single most important consistency check across S01 ↔ S02.
- `scope_violations`: list any file in the diff that is outside the allowed_paths.
