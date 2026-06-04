#!/usr/bin/env python3
"""LLM-as-judge test reviewer for CR-00084 (S01 spike).

Invokes Claude Opus 4.7 (default) to score a test against a three-axis
assertion-strength rubric. See CR-00084_CR_Design.md §0 for the full context.

Usage:
    # Single-test mode:
    python scripts/llm_judge_test_review.py \
        --test-file tests/unit/test_foo.py \
        --test-name test_bar

    # Calibration mode (runs judge over a labelled set):
    python scripts/llm_judge_test_review.py \
        --calibrate tests/llm_judge/labelled_set.jsonl

Exit codes:
    0  — success (JSON emitted to stdout)
    1  — upstream error (API failure, parse failure)
    2  — ANTHROPIC_API_KEY not set
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import io

try:
    import anthropic
except ImportError:
    anthropic = None  # type: ignore[assignment, misc]

# Pricing as of 2026-05-25. May drift — the calibration evidence file records
# the prices used so a future re-calibration can audit the discrepancy.
_OPUS_INPUT_PRICE_PER_1M = 15.00
_OPUS_OUTPUT_PRICE_PER_1M = 75.00

_DEFAULT_MODEL = "anthropic/claude-opus-4-7"

JUDGE_PROMPT_TEMPLATE = textwrap.dedent(r"""
You are an expert test-quality reviewer evaluating a Python test function against
the production code it exercises.

## Three-axis rubric

Score each axis 1–5 where 5 is best:

1. **assertion_specificity** — Does the test assert on a specific observable
   behaviour (return value, DB row, HTTP response body, log line via caplog)?
   A score of 5 means mutating the production line under test would make the
   test fail. A score of 1 means the assertion is generic and survives most
   mutations (e.g. `assert result is not None`, `assert isinstance(result, dict)`).

2. **behaviour_vs_mock** — Does the test exercise real production logic or only
   that a mock was called? A score of 5 means the test drives real code paths
   and makes observable assertions. A score of 1 means every assertion is a
   `mock.assert_called*` / `mock.assert_await*` on a mock receiver, with no
   other behavioural check.

3. **edge_coverage** — Does the test exercise edge cases and boundary conditions
   (exact boundary values, error paths, empty inputs)? A score of 5 means the
   test covers meaningful edge cases. A score of 1 means the test exercises
   only the happy path with no boundary checks.

## Score bucketing for calibration

When aggregating per-test scores into a confusion matrix, bucket the `overall`
score as follows:
- overall >= 4  →  STRONG
- overall == 3  →  MEDIUM
- overall <= 2  →  WEAK

## Output format

Return ONLY a single JSON object with this exact shape (no markdown fences,
no extra text):

{
  "file": "<relative path from repo root, e.g. tests/unit/test_foo.py>",
  "test_name": "<test function name>",
  "scores": {
    "assertion_specificity": <int 1-5>,
    "behaviour_vs_mock": <int 1-5>,
    "edge_coverage": <int 1-5>
  },
  "overall": <int 1-5>,
  "rationale": "<1-3 sentences explaining the scores>"
}

## Test code

```python
{test_code}
```

## Production code under test

```python
{prod_code}
```
""").strip()


# ---------------------------------------------------------------------------
# Lazy import helper (allows unit tests to run without anthropic installed)
# ---------------------------------------------------------------------------

_ANTHROPIC_CLIENT: type | None = None


def _get_anthropic_client() -> type:
    """Lazily import and return the Anthropic client class.

    Raises ImportError if the anthropic package is not installed.
    """
    global _ANTHROPIC_CLIENT  # noqa: PLW0603
    if _ANTHROPIC_CLIENT is None:
        import anthropic

        _ANTHROPIC_CLIENT = anthropic.Anthropic
    return _ANTHROPIC_CLIENT


# ---------------------------------------------------------------------------
# Pure-function helpers (also unit-tested)
# ---------------------------------------------------------------------------


def validate_judge_payload(payload: dict) -> None:
    """Validate the judge's JSON output against the required schema.

    Raises ValueError with a specific message on any violation.
    """
    required_str_keys = {"file", "test_name", "rationale"}
    for key in required_str_keys:
        if key not in payload:
            raise ValueError(f"Missing required key: '{key}'")
        if not isinstance(payload[key], str):
            raise ValueError(f"'{key}' must be a string, got {type(payload[key]).__name__}")

    if not payload["rationale"].strip():
        raise ValueError("'rationale' must be a non-empty string")

    if "scores" not in payload or not isinstance(payload["scores"], dict):
        raise ValueError("Missing or non-dict 'scores'")
    scores = payload["scores"]

    score_keys = {"assertion_specificity", "behaviour_vs_mock", "edge_coverage"}
    for axis in score_keys:
        if axis not in scores:
            raise ValueError(f"Missing score axis: '{axis}'")
        val = scores[axis]
        if not isinstance(val, int):
            raise ValueError(f"'{axis}' score must be an int, got {type(val).__name__}")
        if not (1 <= val <= 5):
            raise ValueError(f"'{axis}' score must be in range 1–5, got {val}")

    if "overall" not in payload:
        raise ValueError("Missing 'overall'")
    overall = payload["overall"]
    if not isinstance(overall, int):
        raise ValueError(f"'overall' must be an int, got {type(overall).__name__}")
    if not (1 <= overall <= 5):
        raise ValueError(f"'overall' must be in range 1–5, got {overall}")


def _infer_prod_module(test_file: str) -> str | None:
    """Infer the production module path from a test file path.

    Convention: ``tests/unit/test_foo.py`` → ``<project>/foo.py``
    Strips the ``tests/unit/`` (or similar) prefix and the ``test_`` name prefix.

    Args:
        test_file: Relative path to the test file (e.g. ``tests/unit/test_foo.py``).

    Returns:
        Inferred production module path relative to the repo root, or None when
        the path does not match the expected convention.
    """
    import re as _re

    pattern = r"^tests?/[^/]+/test_(.+)\.py$"
    m = _re.match(pattern, test_file)
    if m:
        return m.group(1) + ".py"
    return None


def load_labelled_set(fp: io.StringIO) -> list[dict]:
    """Load a labelled set from a .jsonl file handle.

    Each record must have: file, test_name, label (STRONG/MEDIUM/WEAK), rationale.
    Raises ValueError with line number on any parsing or validation error.
    """
    records: list[dict] = []
    for lineno, line in enumerate(fp, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            record = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Line {lineno}: invalid JSON — {exc}") from exc

        required_keys = {"file", "test_name", "label", "rationale"}
        missing = [k for k in required_keys if k not in record]
        if missing:
            raise ValueError(f"Line {lineno}: missing keys {missing}")

        if record["label"] not in {"STRONG", "MEDIUM", "WEAK"}:
            raise ValueError(
                f"Line {lineno}: label must be STRONG/MEDIUM/WEAK, got '{record['label']}'"
            )

        records.append(record)

    return records


def _bucket_overall(overall: int) -> str:
    """Bucket an overall score into a STRONG / MEDIUM / WEAK label.

    Args:
        overall: Integer score in the range 1–5.

    Returns:
        ``"STRONG"`` for 4–5, ``"MEDIUM"`` for 3, ``"WEAK"`` for 1–2.
    """
    if overall >= 4:
        return "STRONG"
    if overall == 3:
        return "MEDIUM"
    return "WEAK"


def aggregate_calibration(records: list[dict], predictions: list[dict | None]) -> dict:
    """Aggregate calibration results across a labelled set.

    Args:
        records: list of ground-truth records from the labelled set
                 (each must have 'label': STRONG/MEDIUM/WEAK)
        predictions: list of judge responses (each a dict with 'overall')
                     or None for skipped/failed invocations

    Returns a dict with:
        - confusion_matrix: dict[true_label][pred_label] → count
        - weak_recall: float (0–1)
        - strong_fp_rate: float (0–1) — STRONG predictions among non-STRONG true
        - verdict: "MET" | "NOT MET"
        - skipped: int
        - total: int
        - total_input_tokens, total_output_tokens, total_cost_usd
    """
    labels = ["STRONG", "MEDIUM", "WEAK"]
    matrix: dict[str, dict[str, int]] = {lbl: dict.fromkeys(labels, 0) for lbl in labels}

    total_input = 0
    total_output = 0
    total_cost = 0.0
    skipped = 0
    total = 0

    # Track for recall/FP calculations
    true_strong = 0
    true_weak = 0
    strong_predicted_as_weak = 0
    weak_predicted_correctly = 0

    for record, pred in zip(records, predictions, strict=False):
        true_label = record["label"]

        if true_label == "STRONG":
            true_strong += 1
        elif true_label == "WEAK":
            true_weak += 1

        if pred is None:
            skipped += 1
            continue

        total += 1
        predicted_label = _bucket_overall(pred["overall"])
        matrix[true_label][predicted_label] += 1

        # Track for metrics
        if true_label == "WEAK" and predicted_label == "WEAK":
            weak_predicted_correctly += 1
        if true_label == "STRONG" and predicted_label == "WEAK":
            strong_predicted_as_weak += 1

        # Accumulate token info if present
        if "input_tokens" in pred:
            total_input += pred["input_tokens"]
        if "output_tokens" in pred:
            total_output += pred["output_tokens"]
        if "cost_usd" in pred:
            total_cost += pred["cost_usd"]

    # Calculate metrics
    weak_recall = (weak_predicted_correctly / true_weak) if true_weak > 0 else 0.0
    strong_fp_rate = (strong_predicted_as_weak / true_strong) if true_strong > 0 else 0.0

    verdict = "MET" if (weak_recall >= 0.70 and strong_fp_rate <= 0.30) else "NOT MET"

    return {
        "confusion_matrix": matrix,
        "weak_recall": weak_recall,
        "strong_fp_rate": strong_fp_rate,
        "verdict": verdict,
        "skipped": skipped,
        "total": total,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_cost_usd": total_cost,
    }


# ---------------------------------------------------------------------------
# Script helpers
# ---------------------------------------------------------------------------


def _call_judge(
    client: anthropic.Anthropic,
    model: str,
    test_code: str,
    prod_code: str,
    file_path: str,
    test_name: str,
) -> tuple[dict, int, int, float]:
    """Call the judge model and return (parsed_payload, input_tokens, output_tokens, cost_usd).

    Raises ValueError on parse/validation failure; raises upstream errors as-is.
    """
    prompt = JUDGE_PROMPT_TEMPLATE.format(
        test_code=test_code,
        prod_code=prod_code,
    )

    response = client.messages.parse(
        model=model,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        response_schema={
            "type": "object",
            "properties": {
                "file": {"type": "string"},
                "test_name": {"type": "string"},
                "scores": {
                    "type": "object",
                    "properties": {
                        "assertion_specificity": {"type": "integer"},
                        "behaviour_vs_mock": {"type": "integer"},
                        "edge_coverage": {"type": "integer"},
                    },
                    "required": [
                        "assertion_specificity",
                        "behaviour_vs_mock",
                        "edge_coverage",
                    ],
                },
                "overall": {"type": "integer"},
                "rationale": {"type": "string"},
            },
            "required": ["file", "test_name", "scores", "overall", "rationale"],
        },
    )

    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    cost_usd = (input_tokens * _OPUS_INPUT_PRICE_PER_1M / 1_000_000) + (
        output_tokens * _OPUS_OUTPUT_PRICE_PER_1M / 1_000_000
    )

    # response.content is a list of ContentBlock; the first is the parsed JSON
    content = response.content[0].text
    payload = json.loads(content)

    # Override file/test_name from args so we always return the canonical identity
    payload["file"] = file_path
    payload["test_name"] = test_name

    validate_judge_payload(payload)

    # Attach token info for aggregation
    payload["input_tokens"] = input_tokens
    payload["output_tokens"] = output_tokens
    payload["cost_usd"] = cost_usd

    return payload, input_tokens, output_tokens, cost_usd


def _load_test_code(test_file: str) -> str:
    """Read and return the full source of a test file, exiting on error.

    Args:
        test_file: Path to the test file.

    Returns:
        UTF-8 file contents as a string.
    """
    path = Path(test_file)
    if not path.exists():
        print(f"ERROR: test file not found: {test_file}", file=sys.stderr)
        sys.exit(1)
    return path.read_text(encoding="utf-8")


def _load_prod_code(prod_file: str | None, test_file: str) -> str:
    """Read and return the production module source, exiting on error.

    Args:
        prod_file: Explicit production file path; when None the path is inferred
                   from ``test_file`` via ``_infer_prod_module``.
        test_file: Test file path used for inference when ``prod_file`` is None.

    Returns:
        UTF-8 file contents as a string.
    """
    if prod_file:
        path = Path(prod_file)
    else:
        inferred = _infer_prod_module(test_file)
        if inferred is None:
            print(
                f"ERROR: Could not infer production module from test path: {test_file}\n"
                "Hint: use --prod-file to specify the production code path explicitly.",
                file=sys.stderr,
            )
            sys.exit(1)
        # Try to find it relative to the repo root (two levels up from scripts/)
        repo_root = Path(__file__).resolve().parent.parent
        path = repo_root / inferred

    if not path.exists():
        print(f"ERROR: production file not found: {path}", file=sys.stderr)
        sys.exit(1)
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Main entry points
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="llm_judge_test_review",
        description=(
            "Score a test function against a three-axis assertion-strength rubric "
            "using Claude Opus 4.7. Or run calibration over a labelled set."
        ),
    )
    parser.add_argument(
        "--calibrate",
        metavar="JSONL",
        help="Path to a labelled_set.jsonl file. Runs calibration instead of single-test mode.",
    )
    parser.add_argument(
        "--test-file",
        help="Path to the test file (required in single-test mode).",
    )
    parser.add_argument(
        "--test-name",
        help="Name of the test function to score (required in single-test mode).",
    )
    parser.add_argument(
        "--prod-file",
        help="Path to the production module under test. If omitted, inferred from --test-file.",
    )
    parser.add_argument(
        "--model",
        default=_DEFAULT_MODEL,
        help=f"Judge model (default: {_DEFAULT_MODEL}).",
    )
    return parser


def _run_single_test(args: argparse.Namespace, api_key: str) -> int:
    """Invoke the LLM judge on a single test function and emit the scored payload.

    Args:
        args: Parsed CLI namespace with ``test_file``, ``test_name``,
              ``prod_file``, and ``model`` attributes.
        api_key: Anthropic API key for the judge model.

    Returns:
        0 on success, 1 on parse or validation failure.
    """
    anthropic_cls = _get_anthropic_client()
    client = anthropic_cls(api_key=api_key)

    test_code = _load_test_code(args.test_file)
    prod_code = _load_prod_code(args.prod_file, args.test_file)

    try:
        payload, input_tokens, output_tokens, cost_usd = _call_judge(
            client=client,
            model=args.model,
            test_code=test_code,
            prod_code=prod_code,
            file_path=args.test_file,
            test_name=args.test_name,
        )
    except json.JSONDecodeError as exc:
        print(f"ERROR: Failed to parse judge response as JSON — {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"ERROR: Judge response validation failed — {exc}", file=sys.stderr)
        return 1

    # Log token spend to stderr
    print(
        f"tokens: input={input_tokens} output={output_tokens} cost_usd={cost_usd:.6f}",
        file=sys.stderr,
    )

    # Emit payload to stdout (without internal token fields)
    output_payload = {
        k: v for k, v in payload.items() if k not in {"input_tokens", "output_tokens", "cost_usd"}
    }
    print(json.dumps(output_payload))
    return 0


def _run_calibration(args: argparse.Namespace, api_key: str) -> int:
    """Run the LLM judge over a labelled set and print a calibration confusion matrix.

    Args:
        args: Parsed CLI namespace with ``calibrate`` (path to ``.jsonl`` file)
              and ``model`` attributes.
        api_key: Anthropic API key for the judge model.

    Returns:
        0 when calibration completes (regardless of whether the acceptance
        threshold is met), 1 when the labelled-set file is not found.
    """
    labelled_path = Path(args.calibrate)
    if not labelled_path.exists():
        print(f"ERROR: labelled set not found: {args.calibrate}", file=sys.stderr)
        return 1

    with labelled_path.open(encoding="utf-8") as fp:
        records = load_labelled_set(fp)

    print(f"Calibrating judge on {len(records)} records from {args.calibrate}")
    print(f"Model: {args.model}", file=sys.stderr)
    print(
        f"Token pricing: ${_OPUS_INPUT_PRICE_PER_1M}/M input,"
        f" ${_OPUS_OUTPUT_PRICE_PER_1M}/M output",
        file=sys.stderr,
    )
    print("---", file=sys.stderr)

    anthropic_cls = _get_anthropic_client()
    client = anthropic_cls(api_key=api_key)

    predictions: list[dict | None] = []
    total_input = 0
    total_output = 0
    total_cost = 0.0
    errors = 0

    for record in records:
        test_file = record["file"]
        test_name = record["test_name"]

        test_code = _load_test_code(test_file)
        prod_code = _load_prod_code(None, test_file)

        try:
            payload, input_tokens, output_tokens, cost_usd = _call_judge(
                client=client,
                model=args.model,
                test_code=test_code,
                prod_code=prod_code,
                file_path=test_file,
                test_name=test_name,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  [SKIP] {test_file}::{test_name} — {exc}", file=sys.stderr)
            predictions.append(None)
            errors += 1
            continue

        # Log per-invocation spend
        print(
            f"tokens: input={input_tokens} output={output_tokens} cost_usd={cost_usd:.6f}",
            file=sys.stderr,
        )

        total_input += input_tokens
        total_output += output_tokens
        total_cost += cost_usd

        # For aggregation, keep only the overall + token fields
        pred = {"overall": payload["overall"]}
        predictions.append(pred)

    # Aggregate
    result = aggregate_calibration(records, predictions)

    # Print calibration report
    print("", file=sys.stderr)
    print("=== Calibration Report ===", file=sys.stderr)
    print("", file=sys.stderr)

    labels = ["STRONG", "MEDIUM", "WEAK"]
    print("Confusion matrix (rows=true, cols=predicted):", file=sys.stderr)
    header = f"{'true':<10}" + "".join(f"{lbl:>12}" for lbl in labels)
    print(header, file=sys.stderr)
    print("-" * len(header), file=sys.stderr)
    for row_label in labels:
        row = f"{row_label:<10}" + "".join(
            f"{result['confusion_matrix'][row_label][col]:>12}" for col in labels
        )
        print(row, file=sys.stderr)

    print("", file=sys.stderr)
    print(f"WEAK recall: {result['weak_recall'] * 100:.1f}%", file=sys.stderr)
    print(f"STRONG false-positive rate: {result['strong_fp_rate'] * 100:.1f}%", file=sys.stderr)
    print(f"Skipped: {result['skipped']}", file=sys.stderr)
    print(f"Verdict: {result['verdict']}", file=sys.stderr)
    print(
        f"Total token spend: input={total_input} output={total_output} cost_usd={total_cost:.6f}",
        file=sys.stderr,
    )

    if total_cost > 2.00:
        print(
            f"WARNING: Calibration exceeded $2.00 budget (actual: ${total_cost:.2f})",
            file=sys.stderr,
        )

    return 0


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and dispatch to single-test or calibration mode.

    Args:
        argv: Argument list; defaults to ``sys.argv[1:]`` when None.

    Returns:
        0 on success, 1 on upstream errors, 2 when ``ANTHROPIC_API_KEY`` is unset.
    """
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY is not set", file=sys.stderr)
        return 2

    if anthropic is None:
        print(
            "ERROR: the anthropic package is not installed; pip install anthropic",
            file=sys.stderr,
        )
        return 2

    if args.calibrate:
        if args.test_file or args.test_name:
            print(
                "ERROR: --calibrate and --test-file/--test-name are mutually exclusive",
                file=sys.stderr,
            )
            return 1
        return _run_calibration(args, api_key)
    if not args.test_file or not args.test_name:
        print(
            "ERROR: --test-file and --test-name are required in single-test mode",
            file=sys.stderr,
        )
        return 1
    return _run_single_test(args, api_key)


if __name__ == "__main__":
    sys.exit(main())
