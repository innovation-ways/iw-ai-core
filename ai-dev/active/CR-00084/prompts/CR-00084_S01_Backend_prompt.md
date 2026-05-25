# CR-00084_S01_Backend_prompt

**Work Item**: CR-00084 -- LLM-as-judge test review (spike) — a stronger model scores newly-written tests against an assertion-strength rubric; advisory-only signal in the CodeReview step
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This CR adds NO migrations. If your work seems to require one, STOP and raise a blocker.

You MUST NOT run the following alembic commands against the live
orchestration DB (port 5433) from an agent context:

```
alembic upgrade head
alembic upgrade <revision>
alembic downgrade <anything>
alembic stamp <anything>
```

Allowed for agents:
  - alembic history / current / show           (read-only)
  - Running migrations inside testcontainer fixtures
    (tests/conftest.py does this — agents don't call it directly)

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00084 --json` (prefer this over the manifest snapshot).
- `ai-dev/work/CR-00084/CR-00084_CR_Design.md` — Design document (READ THIS FIRST)
- `ai-dev/work/CR-00084/CR-00084_Functional.md` — Human-facing summary
- `scripts/check_test_assertions.py` — The structural scanner (CR-00046). Your judge is **complementary**, NOT a replacement. Read it to understand the convention for one-off scripts in this project.
- `projects.toml` `[projects.iw-ai-core.ai_assistant]` — confirms the project's default model is `anthropic/claude-opus-4-7`.
- `skills/iw-ai-core-testing/SKILL.md` — read §0 mutation-test heuristic and the assertion-strength language so the rubric mirrors it.
- `agents/claude/code-review-impl.md` — note the `model: sonnet` field (this is *why* the judge runs Opus 4.7: stronger than the reviewer that runs Sonnet).

## Output Files

- `ai-dev/work/CR-00084/reports/CR-00084_S01_Backend_report.md` — Step report
- `tests/llm_judge/labelled_set.jsonl` — Hand-labelled calibration set (30–50 records)
- `tests/llm_judge/__init__.py` — Empty package marker so the directory imports cleanly under pytest collection
- `tests/unit/test_llm_judge_script.py` — Unit tests for the script's pure-function helpers (loader, validator, aggregator, arg parsing, exit-code-2-when-no-API-key)
- `scripts/llm_judge_test_review.py` — Judge script
- `Makefile` — New `llm-judge-calibrate` target appended to `.PHONY` and the body
- `ai-dev/active/CR-00084/evidences/pre/cr-00084-judge-calibration.txt` — Calibration evidence (confusion matrix + per-axis distribution + recall/FP-rate + MET/NOT MET verdict + total token spend in USD)

## Context

You are implementing **Step S01** of CR-00084: the labelled set + judge script + Makefile target + calibration run. This is a **spike** — the calibration outcome decides whether the next step (S02) ships the advisory hook live or dormant. Read the design document end-to-end before writing any code.

## Requirements

### 1. Labelled set (`tests/llm_judge/labelled_set.jsonl`)

Hand-pick **between 30 and 50** real tests from the iw-ai-core suite. **Half STRONG, half MEDIUM/WEAK (within ±20%)**. Selection rules:

- Pick tests that the structural scanner (`scripts/check_test_assertions.py`) currently passes (i.e., not on `tests/assertion_free_baseline.txt`) — the whole point of the judge is to catch what the structural scanner cannot. Verify with `grep <test_name> tests/assertion_free_baseline.txt` returning empty.
- Spread across at least 4 test files; do not concentrate on one module.
- STRONG = test asserts on a specific observable (return value with a specific shape, a DB row with specific columns, a log line via caplog, an HTTP response body with a specific field). Mutating the production code line the test covers would make the test fail.
- WEAK = test asserts something present-but-weak (e.g., `assert response.status_code < 600`, `assert len(result) >= 0`, `assert isinstance(result, dict)` where the function is annotated `-> dict`, a single `mock.assert_called` after a more specific assertion is possible).
- MEDIUM = somewhere in between; e.g., asserts on type and length but not values.

Record format, one JSON record per line (`.jsonl`):

```jsonl
{"file": "tests/unit/test_foo.py", "test_name": "test_bar", "label": "STRONG", "rationale": "Asserts the returned dict has key 'x' equal to 42; mutating the +1 in foo.py:17 would fail this."}
```

`rationale` is mandatory and must be one to three sentences explaining *why* you labelled it that way. The rationale is the human ground truth — the judge's score is compared against your label, not your rationale, but the rationale is what makes the labelled set defensible.

### 2. Judge script (`scripts/llm_judge_test_review.py`)

Standalone Python script. Follows the convention of `scripts/check_test_assertions.py`: shebang, `from __future__ import annotations`, `if __name__ == "__main__":` entry, no dependency on `orch.config` (it is a standalone utility outside the orchestration runtime).

CLI shape (use `argparse`):

```
python scripts/llm_judge_test_review.py --test-file <path> --test-name <function_name> [--prod-file <path>] [--model anthropic/claude-opus-4-7]
```

If `--prod-file` is omitted, infer the production module from `tests/unit/test_foo.py` → `<project>/foo.py` by stripping `test_` and the leading `tests/unit/` segment; if inference fails, exit 1 with a clear message. The model defaults to `anthropic/claude-opus-4-7` (matches `projects.toml` `[projects.iw-ai-core.ai_assistant].default_model`).

Read `ANTHROPIC_API_KEY` from `os.environ.get("ANTHROPIC_API_KEY")`. **If missing, exit with code 2** (distinguishable from real API failure = exit 1; success = exit 0). Print `ERROR: ANTHROPIC_API_KEY is not set` to stderr.

Use the `anthropic` Python SDK (add to `[dependency-groups] dev` in `pyproject.toml` if not already present — check first with `grep '"anthropic' pyproject.toml`). If not present, add `"anthropic>=0.40,<1.0"` to `[dependency-groups] dev` and run `uv lock` to update `uv.lock`. **Do NOT touch any other dependency.**

The prompt template (build it as a Python string constant `JUDGE_PROMPT_TEMPLATE`) must:

- Explain the three-axis rubric (assertion_specificity, behaviour_vs_mock, edge_coverage), each scored 1–5 where 5 is best.
- Quote both the test code and the production code inline.
- Instruct the model to emit ONLY a single JSON object with this exact shape:
  ```
  {"file": "...", "test_name": "...", "scores": {"assertion_specificity": <1-5>, "behaviour_vs_mock": <1-5>, "edge_coverage": <1-5>}, "overall": <1-5>, "rationale": "..."}
  ```
- Forbid markdown fences in the output (the script parses the response as JSON directly).

Validation: after the API call, parse the response with `json.loads` and validate against the schema (use a small dedicated `_validate_judge_payload(payload: dict) -> None` function that raises `ValueError` with the specific violation). On parse/validation failure, print the violation to stderr and exit 1. **No retries.**

Token logging: after the call, print `tokens: input=<int> output=<int> cost_usd=<float>` to stderr (do NOT print to stdout — stdout is reserved for the JSON record). Cost calculation uses Anthropic's public pricing for `claude-opus-4-7` at the time of writing: `$15.00 / 1M input tokens` and `$75.00 / 1M output tokens`. Hardcode these as module-level constants `_OPUS_INPUT_PRICE_PER_1M = 15.00` and `_OPUS_OUTPUT_PRICE_PER_1M = 75.00`; add a one-line comment noting they may drift and the calibration evidence file records the prices used.

Output: emit the validated JSON record to stdout (no surrounding text), exit 0.

### 3. Makefile target

Append `llm-judge-calibrate` to both `.PHONY` and to the recipes section. The target reads `tests/llm_judge/labelled_set.jsonl`, calls the judge script for each record, accumulates predictions and token spend, and prints:

- The confusion matrix (rows = true label, cols = predicted label, both over `{STRONG, MEDIUM, WEAK}` — bucket the judge's `overall` score: `>=4` → STRONG, `3` → MEDIUM, `<=2` → WEAK; document this exact bucketing in the rubric prompt).
- `WEAK recall: <float>%` and `STRONG false-positive rate: <float>%`.
- `Verdict: MET` or `Verdict: NOT MET` based on the bar `WEAK-recall >= 70% AND STRONG-FP <= 30%`.
- `Total token spend: input=<int> output=<int> cost_usd=<float>`.
- A note if cumulative cost exceeded the $2.00 budget (do NOT abort — finish the run, but record the overrun).

The aggregator logic should live in the judge script itself (as `aggregate_calibration(records: list[dict], predictions: list[dict|None]) -> dict`) so it is unit-testable; the Makefile target is a thin shell loop. Failed judge calls (exit code != 0, or unparseable JSON) record `None` for that prediction and the aggregator skips them in the confusion matrix but counts them in a `skipped: <int>` line.

The S01 implementation runs this target end-to-end and pipes the output to `ai-dev/active/CR-00084/evidences/pre/cr-00084-judge-calibration.txt` (with a header line containing the date, the model id, and the input/output token prices used). The recipe should look approximately like:

```make
.PHONY: llm-judge-calibrate
llm-judge-calibrate:
	@uv run python scripts/llm_judge_test_review.py --calibrate tests/llm_judge/labelled_set.jsonl
```

(use the `--calibrate <jsonl_path>` flag inside the judge script — it is cleaner than a shell `while read` loop and reuses the same Python process so the aggregator runs in-memory).

### 4. Unit tests (`tests/unit/test_llm_judge_script.py`)

**TDD: RED first.** Write the failing tests, run them targeted (`uv run pytest tests/unit/test_llm_judge_script.py -v`), confirm they fail for the *expected* reason (AssertionError / AttributeError / NotImplementedError — not ImportError or SyntaxError), then implement.

Required cases (all unit-level, no live API):

- `test_validate_judge_payload_accepts_well_formed` — happy path.
- `test_validate_judge_payload_rejects_missing_scores` — raises ValueError mentioning `scores`.
- `test_validate_judge_payload_rejects_non_integer_score` — raises ValueError mentioning the specific axis.
- `test_validate_judge_payload_rejects_out_of_range_score` — score < 1 or > 5.
- `test_validate_judge_payload_rejects_missing_rationale` — empty string is also a rejection.
- `test_load_labelled_set_accepts_valid_jsonl` — feed an `io.StringIO` with 3 valid records.
- `test_load_labelled_set_rejects_invalid_label` — record with `"label": "GOOD"` raises ValueError mentioning the line number.
- `test_load_labelled_set_rejects_missing_required_key` — record without `rationale` raises ValueError mentioning the key.
- `test_aggregate_calibration_computes_confusion_matrix` — feed synthetic predictions, assert the matrix dict matches expected counts.
- `test_aggregate_calibration_computes_recall_and_fp_rate` — assert numeric values within `pytest.approx`.
- `test_aggregate_calibration_handles_skipped_predictions` — None predictions counted in `skipped`, excluded from matrix.
- `test_argparse_rejects_empty_test_name` — exits non-zero.
- `test_main_exits_2_when_anthropic_api_key_missing` — use `monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)`, invoke `main([...])`, assert `SystemExit` with `.code == 2`.

**Do NOT write a test that calls the live Anthropic API.** Mock the SDK client at the boundary if you need to test the integration glue, but prefer pure-function tests for the validator/loader/aggregator/argparse.

### 5. Calibration run

After implementation, run `make llm-judge-calibrate > ai-dev/active/CR-00084/evidences/pre/cr-00084-judge-calibration.txt 2>&1`. **This requires `ANTHROPIC_API_KEY` in the environment**. If the worktree does not have it, do NOT run the live calibration: write a stub evidence file (header + a single `Verdict: DEFERRED` line + a one-line note explaining the missing key) and set `calibration_verdict: "DEFERRED"` in your step report. This counts as a `complete` step (the spike's infrastructure ships; S02 reads `DEFERRED` and ships the hook dormant). Mention the missing key in `blockers` for surfacing, but do NOT set `completion_status: blocked` — `DEFERRED` is a recognized terminal verdict, not a blocker on the step itself.

If the calibration runs:
- Inspect the resulting file; verify the `Verdict:` line is either `MET` or `NOT MET`.
- Record the verdict in your step report's `notes` — S02 reads this to decide whether to ship the hook live or dormant.
- Verify the total cost is < $2.00; if not, note the overrun in `notes`.

## Project Conventions

Read the project's `CLAUDE.md` for:
- The dotenv-based env-var pattern (`.env` is gitignored; `ANTHROPIC_API_KEY` lives there).
- The `scripts/` directory pattern (one-off utilities, `if __name__ == "__main__":` entry, no `orch.config` dependency for standalone tools).
- `make lint` / `make format` / `make typecheck` invocation.
- `uv run` for all Python execution.

Follow all rules defined there exactly. Match the style of `scripts/check_test_assertions.py` for the script's overall shape.

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED**: Write failing tests in `tests/unit/test_llm_judge_script.py` first. Run targeted (`uv run pytest tests/unit/test_llm_judge_script.py -v`). Confirm `AssertionError` / `AttributeError` / `NotImplementedError` — not `ImportError`/`SyntaxError`/collection error. Capture the failing line(s) into `tdd_red_evidence` in your report.
2. **GREEN**: Implement minimal code to make tests pass.
3. **REFACTOR**: Clean up while keeping tests green.

Do not skip the RED phase.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, you MUST run in order:

1. **`make format`** — auto-fixes formatting drift.
2. **`make typecheck`** — must report zero errors involving the files you touched.
3. **`make lint`** — must report zero errors.

If a tool isn't available, STOP and raise a blocker.

## Test Verification (NON-NEGOTIABLE)

Run only the test file you wrote in this step:

```bash
uv run pytest tests/unit/test_llm_judge_script.py -v
```

Do NOT run `make test-unit` or `make test-integration` — those are S09/S10 QV gates.

## Allowed File Modifications

You MAY ONLY modify files matching the CR's `scope.allowed_paths`:

- `tests/llm_judge/**` — labelled set, package marker
- `tests/unit/test_llm_judge_script.py` — unit tests for the script (under `tests/llm_judge/**` is NOT the right place for the unit tests — they go in `tests/unit/` so they run under `make test-unit`)
- `scripts/llm_judge_test_review.py`
- `Makefile`
- `ai-dev/active/CR-00084/**`
- `pyproject.toml` (to add `anthropic` to dev deps) + `uv.lock` (regenerated)

If you discover a need to touch any other file, STOP and raise a blocker — the operator amends the scope, not you.

## Cost Discipline (Mandatory)

The calibration run's budget is **< $2.00**. Every judge invocation must print token spend to stderr. The Makefile target must print the cumulative total. Do NOT silently exceed the budget; if you would exceed it, finish the run (do not auto-abort) but record the overrun in your report's `notes`.

## Timeout

This step has a **1800-second timeout** (the calibration LLM round-trips take time; 30 minutes is a generous ceiling for 30–50 invocations at ~30s each).

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "CR-00084",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "scripts/llm_judge_test_review.py",
    "tests/llm_judge/labelled_set.jsonl",
    "tests/llm_judge/__init__.py",
    "tests/unit/test_llm_judge_script.py",
    "Makefile",
    "pyproject.toml",
    "uv.lock",
    "ai-dev/active/CR-00084/evidences/pre/cr-00084-judge-calibration.txt"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/unit/test_llm_judge_script.py::test_validate_judge_payload_accepts_well_formed — AttributeError: module 'scripts.llm_judge_test_review' has no attribute '_validate_judge_payload'  // captured RED run before implementation",
  "calibration_verdict": "MET|NOT_MET|DEFERRED",
  "calibration_cost_usd": 0.00,
  "labelled_set_size": 0,
  "labelled_set_strong_count": 0,
  "labelled_set_weak_count": 0,
  "blockers": [],
  "notes": "Calibration verdict: MET/NOT_MET. Total cost: $X.XX (under/over $2.00 budget). S02 should ship the advisory hook live/dormant per this verdict."
}
```

- `calibration_verdict` is the load-bearing signal for S02 — make sure it matches the `Verdict:` line in `cr-00084-judge-calibration.txt`.
- If `ANTHROPIC_API_KEY` is unavailable in the worktree, set `calibration_verdict: "DEFERRED"`, note this in `blockers`, and ship the infrastructure (script + labelled set + Makefile target + stub evidence file) without the live calibration. S02 then ships the hook dormant.
