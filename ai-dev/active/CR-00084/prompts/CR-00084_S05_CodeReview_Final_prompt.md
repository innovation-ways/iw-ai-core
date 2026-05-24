# CR-00084_S05_CodeReview_Final_prompt

**Work Item**: CR-00084 -- LLM-as-judge test review (spike) — a stronger model scores newly-written tests against an assertion-strength rubric; advisory-only signal in the CodeReview step
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S03

---

## ⛔ Docker is off-limits

(Standard policy. See S01 prompt for full text. This step does not touch Docker.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This step adds no migrations and you must not run `alembic upgrade`/`downgrade`/`stamp` against the live orch DB.)

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00084 --json`
- `ai-dev/work/CR-00084/CR-00084_CR_Design.md` — Design document (READ ACs 1–7 in full)
- `ai-dev/work/CR-00084/CR-00084_Functional.md` — Functional summary (sanity-check it still describes what shipped)
- All implementation step reports: `ai-dev/work/CR-00084/reports/CR-00084_S01_Backend_report.md`, `_S02_Backend_report.md`, `_S03_Backend_report.md`
- Per-agent review report: `ai-dev/work/CR-00084/reports/CR-00084_S04_CodeReview_report.md`
- `ai-dev/active/CR-00084/evidences/pre/cr-00084-judge-calibration.txt`
- All files listed in all implementation reports' `files_changed`

## Output Files

- `ai-dev/work/CR-00084/reports/CR-00084_S05_CodeReview_Final_report.md`

## Context

You are performing the **final cross-step review** of CR-00084. S04 reviewed each impl step on its own; your job is to catch issues that span steps and to verify the AC list end-to-end. The dominant cross-cutting concern in this CR is the **calibration verdict → hook form → docs disposition** consistency chain: the same MET/NOT_MET signal flows through three impl steps and four doc surfaces, and any mismatch is a CRITICAL finding.

## Read the Design Document FIRST

Read ACs 1–7 in full. Carry every AC into your review as a first-class anchor — for each AC, record `PASS` or `FAIL` with the evidence (file + line or command output) that justifies the call.

Read the TDD section. Every test file the design names by path MUST appear in some impl report's `files_changed`:

- `tests/unit/test_llm_judge_script.py` — S01.
- `tests/llm_judge/labelled_set.jsonl` — S01.

Missing → CRITICAL.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

NEW violations in changed files vs `main` → each one is a CRITICAL finding (`category: conventions`, exact violation code).

If a tool isn't available, STOP and raise a blocker.

## Review Checklist

### 1. AC walk-through (NON-NEGOTIABLE — explicit per-AC verdict)

For each of AC1..AC7 in the design doc, write a one-line PASS/FAIL with evidence. AC6 and AC7 are the doc/QV-gate ACs and must be verified explicitly even though they intersect with later steps.

- **AC1** (labelled set: 30–50 records, valid JSON, valid labels, half STRONG, real tests): inspect `tests/llm_judge/labelled_set.jsonl` directly.
- **AC2** (judge script CLI works, JSON shape correct, exit 2 on missing API key): `unset ANTHROPIC_API_KEY; uv run python scripts/llm_judge_test_review.py --test-file ... --test-name ...; echo $?` → 2. Then with the key set, verify on ONE test from the labelled set — note: this costs ~$0.05–$0.15; budget it. If the worktree has no API key, the script's exit-code-2 behaviour is still verifiable; the live-call AC is then partially satisfied — record this caveat.
- **AC3** (calibration evidence file has confusion matrix + recall/FP + MET/NOT_MET + cost under $2): open the file directly.
- **AC4** (advisory hook form matches calibration verdict, mirrors are byte-identical): compare `grep -A 30 "(Advisory) LLM-as-judge" agents/claude/code-review-impl.md` against the verdict in the evidence file; run `diff -q` for both mirror pairs.
- **AC5** (no production code touched outside agent specs): `git diff --name-only main..HEAD | grep -E "^(orch|dashboard|executor)/"` must return empty.
- **AC6** (docs and tracker consistent): cross-check verdict + percentages in strategy doc, skill, tracker §11, tracker row 4.4 — all four surfaces must quote the same numbers.
- **AC7** (QV gates): covered by S06–S13 (you cannot fully verify here; record as "pending S06–S13").

### 2. Calibration → hook form → docs disposition chain (the headline consistency check)

This is the cross-cutting failure mode most likely to slip past per-step review. Verify by reading **all four** surfaces and confirming they tell the same story:

1. `ai-dev/active/CR-00084/evidences/pre/cr-00084-judge-calibration.txt` — `Verdict:` line.
2. `agents/claude/code-review-impl.md` (and `opencode` mirror) — LIVE vs DORMANT body.
3. `docs/IW_AI_Core_Testing_Strategy.md` — "current disposition" sentence.
4. `skills/iw-ai-core-testing/SKILL.md` — LIVE/DORMANT note.
5. `ai-dev/work/TESTS_ENHANCEMENT.md` §8 row 4.4 — DONE vs DEFERRED.
6. `ai-dev/work/TESTS_ENHANCEMENT.md` §11 changelog entry — outcome summary.

Any inconsistency = **CRITICAL**. Example: evidence file says `Verdict: MET` but the skill says "currently disabled" → critical.

### 3. Cost discipline (cross-cutting)

- S01 report's `calibration_cost_usd` < $2.00 (or an explicit overrun note in `notes` AND in the evidence file).
- Agent spec's LIVE form (if applicable) declares the < $0.50 per-review cap.
- No automatic retry anywhere in the script (`grep -i "retry\|attempt\|tenacity\|backoff" scripts/llm_judge_test_review.py` — only comments allowed).

### 4. Scope discipline

`git diff --name-only main..HEAD` matches `scope.allowed_paths` exactly. Files inside the allow-list but with surprising changes (e.g. `Makefile` had a 200-line rewrite) are MEDIUM_FIXABLE; files outside the allow-list are CRITICAL.

### 5. Architecture compliance

- The judge script is standalone (no `from orch` imports).
- No `IW_CORE_DB_*` env vars touched.
- No new dependency added beyond `anthropic` (if S01 added it) — verify with `git diff main -- pyproject.toml`.

### 6. Security (cross-cutting)

- No hardcoded `ANTHROPIC_API_KEY` anywhere (`grep -rn "sk-ant-" .` in the diff scope).
- The labelled set contains no source-code snippets that could leak (it carries test names + rationales only).
- No `.env` file committed.

### 7. Hook is genuinely advisory (the spike's safety property)

Re-read the LIVE form of the agent spec. Confirm the body contains a sentence that **explicitly forbids** the judge score from raising `verdict` to `fail` or incrementing `mandatory_fix_count`. If the wording is weak (e.g., "the agent should consider the score"), flag as HIGH — a future agent reading the spec must be unable to misinterpret the advisory contract.

If the hook is DORMANT, this check is N/A.

## Test Verification (NON-NEGOTIABLE)

1. Run the targeted unit tests:
   ```bash
   uv run pytest tests/unit/test_llm_judge_script.py -v
   ```
2. Run the **full unit suite** to catch any cross-module regression:
   ```bash
   make test-unit
   ```
3. Do NOT run `make test-integration` — that is S10's job (it has its own timeout budget and will run anyway).
4. Do NOT run `make llm-judge-calibrate` here — re-running it would consume the budget twice; the evidence file from S01 is the source of truth.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Breaks functionality, scope violation, calibration-vs-hook-form mismatch, missing required artefact, hardcoded API key, missing AC | Must fix before merge |
| **HIGH** | Significant bug, advisory hook implicitly blocks (any wording that lets a future agent treat the judge score as a fail trigger), architectural violation | Must fix before merge |
| **MEDIUM (fixable)** | Code quality, missing edge case, convention drift, cost overrun without explicit acknowledgement | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Design improvement | Optional |
| **LOW** | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
  "work_item": "CR-00084",
  "steps_reviewed": ["S01", "S02", "S03"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|integration|testing|architecture|security|scope|cost",
      "file": "path/to/file",
      "line": 42,
      "description": "...",
      "suggestion": "...",
      "cross_cutting": true
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, integration pending S10",
  "missing_requirements": [],
  "ac_verdicts": {
    "AC1": "PASS|FAIL",
    "AC2": "PASS|FAIL",
    "AC3": "PASS|FAIL",
    "AC4": "PASS|FAIL",
    "AC5": "PASS|FAIL",
    "AC6": "PASS|FAIL",
    "AC7": "PENDING_S06_S13"
  },
  "calibration_chain_consistent": true,
  "advisory_contract_explicit": true,
  "notes": ""
}
```

- `verdict`: `pass` iff zero CRITICAL + zero HIGH + zero MEDIUM_FIXABLE findings AND every AC is PASS or PENDING_S06_S13.
- `mandatory_fix_count`: CRITICAL + HIGH + MEDIUM_FIXABLE.
- `missing_requirements`: design requirements with no corresponding implementation. Each is automatically CRITICAL.
- `ac_verdicts`: explicit per-AC pass/fail dictionary — non-negotiable transparency.
- `calibration_chain_consistent`: true iff all six surfaces (evidence, agent spec, strategy doc, skill, tracker row, tracker §11) tell the same MET/NOT_MET story.
- `advisory_contract_explicit`: true iff the LIVE hook's body explicitly forbids judge-score → `verdict: fail` (N/A and true if DORMANT).
