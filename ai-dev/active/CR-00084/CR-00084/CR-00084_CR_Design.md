# CR-00084: LLM-as-judge test review (spike) — a stronger model scores newly-written tests against an assertion-strength rubric; advisory-only signal in the CodeReview step

**Type**: Change Request
**Priority**: Medium
**Reason**: Phase 4 testing-enhancement spike (TESTS_ENHANCEMENT.md §8 item 4.4). Phase 1's structural assertion scanner (CR-00046) catches *patterns* (no-assert / tautology / mock-only / broad-raises) but cannot judge whether a present assertion is **semantically strong enough** to detect a real regression. This CR explores whether a stronger LLM (Claude Opus 4.7) can score that semantic dimension as a useful advisory signal — calibrated against a hand-labelled set before any wiring into CodeReview.
**Created**: 2026-05-24
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt. This CR does not touch Docker.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This CR leaves migrations unchanged — no schema work.

## Description

Spike a stronger-model "judge" that scores newly-written tests against a three-axis assertion-strength rubric (assertion specificity, behaviour-vs-mock, edge coverage). Calibrate the judge against a hand-labelled set of 30–50 real iw-ai-core tests **before** wiring anything into CodeReview. If the calibration bar (≥ 70% recall on WEAK with ≤ 30% false positives on STRONG) is met, the spike concludes by adding an **advisory-only** invocation to `code-review-impl` that logs scores without blocking; if not, the CR ships infrastructure only with the hook disabled and the tracker entry → DEFERRED. Cost discipline is mandatory: every invocation logs token spend, the calibration run is capped (S01 budget < $2), and there is no auto-loop or retry.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Of particular relevance: the Anthropic CLI invocation pattern (project default model is `anthropic/claude-opus-4-7`, see `projects.toml`), the testing skill `skills/iw-ai-core-testing/SKILL.md` (the rubric must mirror its language), the `scripts/` convention (one-off scripts live there with an `if __name__ == "__main__":` entry, see `scripts/check_test_assertions.py` for the closest precedent), and the agent-spec convention (`agents/{claude,opencode}/code-review-impl.md` plus the mirrored `.claude/agents/` / `.opencode/agents/` copies).

## Current Behavior

Today the only automated signal on test quality is the structural assertion scanner introduced by **CR-00046** (`scripts/check_test_assertions.py`, exposed via `make test-assertions` and the `assertions` QV gate). It detects:

- `no-assert` — function defines no `assert` statement anywhere.
- `tautology` — `assert True`, `assert 1 == 1`, `assert x == x`, etc.
- `mock-only` — only assertion is `mock.assert_called*`.
- `broad-raises` — `pytest.raises(Exception)` with no narrower type.

These are all **structural** signals: a test with a single `assert response.status_code < 600` will pass the scanner because the assertion is syntactically real, even though it is semantically useless (almost any code returns a status code under 600). There is no automated review that reads the test against the production code under test and asks "would this assertion catch a meaningful regression?" — that judgement currently rests entirely on the `code-review-impl` agent (running on Sonnet), and there is no second opinion.

The `code-review-impl` agent spec (`agents/claude/code-review-impl.md` + `agents/opencode/code-review-impl.md`) does not invoke any external scoring or sampling — it just produces findings inline.

## Desired Behavior

After this CR ships (and only if calibration is met):

1. A repeatable judge script `scripts/llm_judge_test_review.py` exists. It takes one test file or test function plus the production code it exercises, sends them to Claude Opus 4.7, and emits per-test JSON: `{file, test_name, scores: {assertion_specificity, behaviour_vs_mock, edge_coverage}, overall, rationale}`. Token spend is logged to stderr on every invocation.
2. A hand-labelled set lives at `tests/llm_judge/labelled_set.jsonl` with 30–50 records (`{file, test_name, label, rationale}`, half STRONG, half MEDIUM/WEAK).
3. A `make llm-judge-calibrate` target runs the judge over the labelled set and emits a confusion matrix + per-axis distribution to stdout; the operator pipes that to `ai-dev/active/CR-00084/evidences/pre/cr-00084-judge-calibration.txt`.
4. The `code-review-impl` agent spec optionally invokes the judge on any new test files in the step's `files_changed` list. The judge's output is logged into the review report as an **advisory** line; it never sets `verdict: fail`, never increments `mandatory_fix_count`, and never blocks the QV gate.
5. The testing strategy doc (§ new "LLM-as-judge spike" section) and skill (advisory-signal subsection) document the rubric, the calibration evidence, and the disabled-by-default fallback if calibration failed.
6. The tracker entry in `ai-dev/work/TESTS_ENHANCEMENT.md` §8 row 4.4 is updated to `DONE` (if calibration met) or `DEFERRED` (if not) with a forward link to the evidence file.

If calibration was **not** met, requirements 1–3 still ship (the script exists, the labelled set exists, the calibration evidence file documents the failure), but requirement 4 ships in the **disabled** form (the agent spec mentions the judge exists but instructs the agent not to invoke it pending re-calibration) and requirement 6 marks the row DEFERRED with a one-line rationale.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `scripts/check_test_assertions.py` | Structural test-quality scanner — only signal | Unchanged — judge is a complementary semantic signal, NOT a replacement |
| `scripts/llm_judge_test_review.py` | Does not exist | New — invokes Claude Opus 4.7 with the rubric, prints per-test JSON, logs token spend |
| `tests/llm_judge/` | Does not exist | New directory — holds `labelled_set.jsonl` (calibration ground truth) and any unit tests for the judge script |
| `agents/{claude,opencode}/code-review-impl.md` (+ `.claude/agents/` / `.opencode/agents/` mirrors) | No judge invocation | Optional advisory invocation on new test files, output logged but never blocks |
| `Makefile` | No `llm-judge-calibrate` target | New `make llm-judge-calibrate` target |
| `docs/IW_AI_Core_Testing_Strategy.md` | No LLM-as-judge content | New subsection documenting the spike, the rubric, the calibration outcome, and the advisory-only disposition |
| `skills/iw-ai-core-testing/**` (+ `.claude/skills/` mirror) | No mention of the judge | New "Advisory: LLM-as-judge signal" subsection summarising the rubric and the advisory-only contract |
| `ai-dev/work/TESTS_ENHANCEMENT.md` | §8 row 4.4 → TODO | → DONE (if calibration met) or → DEFERRED (if not) with evidence link; §11 changelog entry |

### Breaking Changes

- None. The judge is a new advisory signal; nothing existing changes behaviour. The structural scanner (CR-00046) is **complementary, not replaced**, and the assertion-baseline file (`tests/assertion_free_baseline.txt`) is untouched.

### Data Migration

- None. No schema changes, no migrations, no database rows touched. Reversibility: trivially reversible by `git revert` — the only persistent artefact is the labelled-set file and the calibration evidence text file, both under `ai-dev/` and `tests/llm_judge/`.

## Implementation Plan

### Agents and Execution Order

> **Step-granularity rule**: each implementation step targets one cohesive concern. See `skills/iw-workflow/SKILL.md` for the canonical rule.

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Labelled set + judge script + `make llm-judge-calibrate` target + calibration run → evidences/pre/cr-00084-judge-calibration.txt | — |
| S02 | backend-impl | Agent-spec advisory hook (claude + opencode + `.claude/agents/` + `.opencode/agents/` mirrors) gated on calibration outcome — enabled if calibration met, disabled-with-rationale if not | depends on S01 |
| S03 | backend-impl | Docs sync: testing strategy §, testing skill subsection (master + `.claude/` mirror), tracker §8 row 4.4 + §11 changelog; `iw sync-skills` | depends on S01 + S02 |
| S04 | code-review-impl | Per-agent review of S01 + S02 + S03 (single review pass — small CR, all impl steps reviewed together) | — |
| S05 | code-review-final-impl | Global cross-agent review against AC1–AC7 | depends on S04 |
| S06–S13 | qv-gate | 8 standard gates: lint / format / typecheck / unit-tests / integration-tests / diff-coverage / assertions / security-secrets | sequential |
| S14 | self-assess-impl | iw-item-analyze: did the calibration spike behave; did the advisory hook stay advisory; cost discipline observed | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: N/A — this CR adds no migrations.

### API Changes

- **New endpoints**: None
- **Modified endpoints**: None
- **Removed endpoints**: None

### Frontend Changes

- **New components**: None
- **Modified components**: None
- **Removed components**: None
- **UI visibility**: `browser_verification: false` — no UI surface; the judge runs from CLI and the advisory log is captured in agent reports only.

## File Manifest

All files for this work item live under `ai-dev/active/CR-00084/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00084_CR_Design.md` | Design | This document |
| `CR-00084_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00084_S01_Backend_prompt.md` | Prompt | S01 — labelled set + judge script + calibration |
| `prompts/CR-00084_S02_Backend_prompt.md` | Prompt | S02 — agent-spec advisory hook |
| `prompts/CR-00084_S03_Backend_prompt.md` | Prompt | S03 — docs + skill + tracker sync |
| `prompts/CR-00084_S04_CodeReview_prompt.md` | Prompt | S04 — per-agent code review |
| `prompts/CR-00084_S05_CodeReview_Final_prompt.md` | Prompt | S05 — final cross-agent review |
| `prompts/CR-00084_S14_SelfAssess_prompt.md` | Prompt | S14 — self-assessment |
| `evidences/pre/cr-00084-judge-calibration.txt` | Evidence | Calibration run output (precision/recall + per-axis distribution) — produced by S01 |

QV gate steps (S06–S13) are pure-command and need no prompt file.

Reports are created during execution in `ai-dev/work/CR-00084/reports/`.

## Acceptance Criteria

### AC1: Labelled set exists with valid records

```
Given the CR has shipped
When an operator inspects tests/llm_judge/labelled_set.jsonl
Then there are between 30 and 50 records, one per line
And each record is valid JSON with keys {file, test_name, label, rationale}
And each label is exactly one of {STRONG, MEDIUM, WEAK}
And the STRONG count is approximately half of the total (within ±20%)
And every (file, test_name) pair references a real test that exists in tests/ as of this CR's main-branch base commit
```

### AC2: Judge script runs end-to-end on one test and emits the documented JSON shape

```
Given an ANTHROPIC_API_KEY in the environment (read from .env per the project's dotenv pattern)
When an operator runs `uv run python scripts/llm_judge_test_review.py --test-file tests/unit/<some_test>.py --test-name <some_test_function>`
Then the script exits 0
And stdout is valid JSON with shape {file, test_name, scores: {assertion_specificity: int 1-5, behaviour_vs_mock: int 1-5, edge_coverage: int 1-5}, overall: int 1-5, rationale: string}
And stderr contains one line of the form "tokens: input=<int> output=<int> cost_usd=<float>"
And the script returns exit code 2 (not 0, not 1) when ANTHROPIC_API_KEY is missing — distinguishable from a real API failure
```

### AC3: Calibration evidence file exists and documents the precision/recall outcome

```
Given the CR has shipped
When an operator opens ai-dev/active/CR-00084/evidences/pre/cr-00084-judge-calibration.txt
Then the file contains a confusion matrix (rows = true label, cols = predicted label, both over {STRONG, MEDIUM, WEAK})
And the file states the WEAK-recall percentage and the STRONG-false-positive percentage as named lines
And the file states explicitly whether the bar (WEAK-recall ≥ 70% AND STRONG-FP ≤ 30%) was MET, NOT MET, or DEFERRED (DEFERRED is reserved for the case where ANTHROPIC_API_KEY is unavailable in the worktree and the calibration did not run — the file is a stub naming the missing key, and the verdict is treated as NOT_MET for hook-form / tracker-row purposes)
And the file records the total token spend in USD and confirms it is < $2.00 (the S01 budget) — DEFERRED runs record 0.00
```

### AC4: Advisory hook in code-review-impl is conditional on the calibration outcome

```
Given the calibration outcome from AC3
When an operator reads agents/claude/code-review-impl.md and agents/opencode/code-review-impl.md
Then (if MET) both files contain a new section instructing the agent to optionally invoke scripts/llm_judge_test_review.py on each newly added test file in files_changed AND to log the judge JSON as an "advisory" line in the review report AND to never raise the verdict to fail based solely on the judge
And (if NOT MET) both files contain a note that the judge exists but instructs the agent NOT to invoke it pending re-calibration, with a forward link to ai-dev/active/CR-00084/evidences/pre/cr-00084-judge-calibration.txt
And the .claude/agents/ and .opencode/agents/ mirrors are byte-identical to their master copies after `iw sync-agents` (or whatever sync command the project uses for agents)
```

### AC5: No production code outside the agent specs is touched

```
Given the diff against main at merge time
When the operator runs `git diff --name-only main..HEAD`
Then no files under orch/ are modified
And no files under dashboard/ are modified
And no files under executor/ are modified
And the only paths touched are exactly those declared in workflow-manifest.json scope.allowed_paths
```

### AC6: Documentation and tracker are consistent

```
Given the CR has shipped
When an operator opens docs/IW_AI_Core_Testing_Strategy.md
Then a new subsection (under §10 or a new §) documents the rubric, the calibration outcome, and the advisory-only disposition
And skills/iw-ai-core-testing/SKILL.md contains a new "Advisory: LLM-as-judge signal" subsection mirroring the strategy doc
And .claude/skills/iw-ai-core-testing/SKILL.md is byte-identical to the master copy after `iw sync-skills`
And ai-dev/work/TESTS_ENHANCEMENT.md §8 row 4.4 reads DONE (if calibration met) or DEFERRED (if not), in either case with the date 2026-05-24 and a link to the calibration evidence file
And ai-dev/work/TESTS_ENHANCEMENT.md §11 has a new changelog entry dated 2026-05-24 summarising the spike outcome
```

### AC7: All QV gates pass

```
Given the CR has shipped
When the daemon runs S06..S13 in sequence
Then make lint passes (S06)
And make format-check passes (S07)
And make type-check passes (S08)
And make test-unit passes (S09)
And make test-integration / make allure-integration passes (S10)
And make diff-coverage passes (S11)
And make test-assertions passes (S12 — the structural scanner; this CR adds no new no-assert/tautology/mock-only/broad-raises violations)
And make security-secrets passes (S13 — no committed secrets; ANTHROPIC_API_KEY is read from environment only)
```

## Rollback Plan

- **Database**: N/A — no schema changes.
- **Code**: Revert the squash-merge commit. The judge script, labelled set, Makefile target, agent-spec hook, docs, and tracker rows all go away in one revert. No feature flag needed because the hook is advisory-only and disabled-if-uncalibrated.
- **Data**: No data loss possible — the only writes are stdout/stderr from the judge script and the static labelled-set file.

## Dependencies

- **Depends on**: CR-00046 (assertion scanner, DONE) — soft dependency: the labelled set is selected to **complement** the structural scanner (we want tests the scanner already passes but which a human would still call WEAK).
- **Soft-ordering preference**: If CR-00081 (assertion-baseline scrub, draft) is going to run in the same window, prefer running it **before** this CR so the labelled set is picked from a cleaner baseline. Not a hard blocker — if CR-00081 has not merged, the labelled set is picked from the current baseline.
- **Blocks**: None. This is a spike; downstream tightening (e.g., a low-score-blocks gate) is explicitly out of scope for this CR.

## Impacted Paths

```
tests/llm_judge/**
scripts/llm_judge_test_review.py
agents/claude/code-review-impl.md
agents/opencode/code-review-impl.md
.claude/agents/code-review-impl.md
.opencode/agents/code-review-impl.md
Makefile
docs/IW_AI_Core_Testing_Strategy.md
skills/iw-ai-core-testing/**
.claude/skills/iw-ai-core-testing/**
ai-dev/work/TESTS_ENHANCEMENT.md
ai-dev/active/CR-00084/**
ai-dev/archive/CR-00084/**
```

## TDD Approach

- **Unit tests** (new — `tests/unit/test_llm_judge_script.py`):
  - The judge script's JSON-shape validator accepts a well-formed payload and rejects each of: missing `scores` key, non-integer score, score out of range [1, 5], missing `rationale`.
  - The judge script's `--test-file <path> --test-name <name>` argument parsing produces a usable target descriptor and rejects an empty `--test-name`.
  - The judge script exits with code 2 (not 0, not 1) when `ANTHROPIC_API_KEY` is unset; this is distinguishable from a real upstream failure (exit 1) and from success (exit 0).
  - The labelled-set loader accepts a valid `.jsonl` and rejects (with line number) records missing required keys or carrying labels outside {STRONG, MEDIUM, WEAK}.
  - The calibration aggregator, given a list of `(true_label, predicted_label)` pairs, returns the documented confusion-matrix dict and the WEAK-recall / STRONG-FP percentages.
- **Integration tests** (none — the judge involves a live LLM call which we do not exercise in CI; the calibration run is a one-off operator-driven artefact, captured in evidences). The labelled-set loader and aggregator are pure-function and unit-testable without touching the LLM.
- **Updated tests**: None — no existing tests need modification. CR-00046's scanner tests are independent.
- **Out of scope for TDD**: We do not write tests against the live Anthropic API. The judge's behaviour against the labelled set is exercised by the manual calibration run (S01), not by CI.

## Notes

- **Cost discipline (operator commitment)**: The S01 budget is < $2.00. Every judge invocation prints `tokens: input=<int> output=<int> cost_usd=<float>` to stderr. The Makefile target `make llm-judge-calibrate` echoes a cumulative total at the end. If the cumulative exceeds $2.00 the script does NOT auto-abort (we want the calibration to complete) but the report records the overrun explicitly for self-assess to surface.
- **No auto-loop, no retry on judge failure**: A single judge invocation that returns an HTTP error or unparseable JSON is recorded as `null` for that test in the calibration output. The script does not retry. This is intentional — retries inflate cost unpredictably during a spike.
- **Why advisory-only (not blocking)**: The tracker entry is explicit ("no judge is uniformly reliable") and the research artefact this descends from (Phase 4 plan) emphasises calibrate-first / advisory-second. Promoting the judge to a blocking gate is a follow-up CR contingent on multiple weeks of advisory-line evidence — explicitly out of scope here.
- **Why Claude Opus 4.7 (not Sonnet)**: The project default per `projects.toml` `[projects.iw-ai-core.ai_assistant]` is `anthropic/claude-opus-4-7`. The whole point of the judge is to use a **stronger** model than the one that wrote the test (CodeReview runs on Sonnet, per `agents/claude/code-review-impl.md`'s `model: sonnet` field). Hardcoding the judge to Opus 4.7 makes the asymmetry explicit.
- **API key handling**: `ANTHROPIC_API_KEY` is read directly from the process environment (`os.environ.get`); the script does NOT call `orch.config.load_config()` because it is a standalone utility outside the orchestration runtime. The key is gitignored via the existing `.env` rule.
- **Risk if calibration fails**: The CR still ships infrastructure (judge script + labelled set + Makefile target + evidence file). The advisory hook ships in the disabled form. Future re-calibration can flip it on without a new design doc — just a small follow-up CR that updates the agent specs and the tracker row. This is the "don't over-invest until proven" discipline the tracker calls out.
