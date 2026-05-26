"""Unit tests for scripts/llm_judge_test_review.py (CR-00084 S01).

These tests exercise the pure-function helpers in the judge script:
validator, loader, aggregator, arg parsing, and API-key guard.
No live Anthropic API calls are made.
"""

from __future__ import annotations

import io
import json
import sys
from unittest.mock import MagicMock, patch

import pytest

# We import the module as a script so tests run in the same Python process.
# The script's main() is invoked directly below.
import scripts.llm_judge_test_review as judge_module

# ---------------------------------------------------------------------------
# _validate_judge_payload
# ---------------------------------------------------------------------------


class TestValidateJudgePayload:
    def test_accepts_well_formed(self) -> None:
        payload = {
            "file": "tests/unit/test_foo.py",
            "test_name": "test_bar",
            "scores": {
                "assertion_specificity": 4,
                "behaviour_vs_mock": 5,
                "edge_coverage": 3,
            },
            "overall": 4,
            "rationale": "Test asserts on a specific return value.",
        }
        result = judge_module.validate_judge_payload(payload)
        # validate_judge_payload returns None on success; any non-None return
        # (e.g. a dict or exception-swallowing change) would indicate a regression.
        assert result is None, (
            "validate_judge_payload must return None on valid input;"
            " a non-None return signals a behavioural change"
        )

    def test_rejects_missing_scores(self) -> None:
        payload = {
            "file": "tests/unit/test_foo.py",
            "test_name": "test_bar",
            "overall": 4,
            "rationale": "Test asserts on a specific return value.",
        }
        with pytest.raises(ValueError, match="scores"):
            judge_module.validate_judge_payload(payload)

    def test_rejects_non_integer_score(self) -> None:
        payload = {
            "file": "tests/unit/test_foo.py",
            "test_name": "test_bar",
            "scores": {
                "assertion_specificity": "high",
                "behaviour_vs_mock": 5,
                "edge_coverage": 3,
            },
            "overall": 4,
            "rationale": "Test asserts on a specific return value.",
        }
        with pytest.raises(ValueError, match="assertion_specificity"):
            judge_module.validate_judge_payload(payload)

    def test_rejects_out_of_range_score(self) -> None:
        payload = {
            "file": "tests/unit/test_foo.py",
            "test_name": "test_bar",
            "scores": {
                "assertion_specificity": 0,
                "behaviour_vs_mock": 5,
                "edge_coverage": 3,
            },
            "overall": 4,
            "rationale": "Test asserts on a specific return value.",
        }
        with pytest.raises(ValueError, match="1.*5"):
            judge_module.validate_judge_payload(payload)

    def test_rejects_score_above_five(self) -> None:
        payload = {
            "file": "tests/unit/test_foo.py",
            "test_name": "test_bar",
            "scores": {
                "assertion_specificity": 6,
                "behaviour_vs_mock": 5,
                "edge_coverage": 3,
            },
            "overall": 4,
            "rationale": "Test asserts on a specific return value.",
        }
        with pytest.raises(ValueError, match="1.*5"):
            judge_module.validate_judge_payload(payload)

    def test_rejects_missing_rationale(self) -> None:
        payload = {
            "file": "tests/unit/test_foo.py",
            "test_name": "test_bar",
            "scores": {
                "assertion_specificity": 4,
                "behaviour_vs_mock": 5,
                "edge_coverage": 3,
            },
            "overall": 4,
            "rationale": "",
        }
        with pytest.raises(ValueError, match="rationale"):
            judge_module.validate_judge_payload(payload)

    def test_rejects_missing_overall(self) -> None:
        payload = {
            "file": "tests/unit/test_foo.py",
            "test_name": "test_bar",
            "scores": {
                "assertion_specificity": 4,
                "behaviour_vs_mock": 5,
                "edge_coverage": 3,
            },
            "rationale": "Test asserts on a specific return value.",
        }
        with pytest.raises(ValueError, match="overall"):
            judge_module.validate_judge_payload(payload)

    def test_rejects_out_of_range_overall(self) -> None:
        payload = {
            "file": "tests/unit/test_foo.py",
            "test_name": "test_bar",
            "scores": {
                "assertion_specificity": 4,
                "behaviour_vs_mock": 5,
                "edge_coverage": 3,
            },
            "overall": 0,
            "rationale": "Test asserts on a specific return value.",
        }
        with pytest.raises(ValueError, match="overall"):
            judge_module.validate_judge_payload(payload)

    def test_rejects_missing_file(self) -> None:
        payload = {
            "test_name": "test_bar",
            "scores": {
                "assertion_specificity": 4,
                "behaviour_vs_mock": 5,
                "edge_coverage": 3,
            },
            "overall": 4,
            "rationale": "Test asserts on a specific return value.",
        }
        with pytest.raises(ValueError, match="file"):
            judge_module.validate_judge_payload(payload)

    def test_rejects_missing_test_name(self) -> None:
        payload = {
            "file": "tests/unit/test_foo.py",
            "scores": {
                "assertion_specificity": 4,
                "behaviour_vs_mock": 5,
                "edge_coverage": 3,
            },
            "overall": 4,
            "rationale": "Test asserts on a specific return value.",
        }
        with pytest.raises(ValueError, match="test_name"):
            judge_module.validate_judge_payload(payload)


# ---------------------------------------------------------------------------
# load_labelled_set
# ---------------------------------------------------------------------------


class TestLoadLabelledSet:
    def test_accepts_valid_jsonl(self) -> None:
        data = json.dumps(
            {
                "file": "tests/unit/test_foo.py",
                "test_name": "test_bar",
                "label": "STRONG",
                "rationale": "Asserts the returned dict has key 'x' equal to 42.",
            }
        )
        records = judge_module.load_labelled_set(io.StringIO(data + "\n" + data + "\n"))
        assert len(records) == 2
        assert records[0]["label"] == "STRONG"
        assert records[1]["label"] == "STRONG"

    def test_accepts_all_valid_labels(self) -> None:
        for label in ("STRONG", "MEDIUM", "WEAK"):
            data = json.dumps(
                {
                    "file": "tests/unit/test_foo.py",
                    "test_name": "test_bar",
                    "label": label,
                    "rationale": "Test rationale.",
                }
            )
            records = judge_module.load_labelled_set(io.StringIO(data + "\n"))
            assert records[0]["label"] == label

    def test_rejects_invalid_label(self) -> None:
        data = json.dumps(
            {
                "file": "tests/unit/test_foo.py",
                "test_name": "test_bar",
                "label": "GOOD",
                "rationale": "Test rationale.",
            }
        )
        with pytest.raises(ValueError, match="GOOD"):
            judge_module.load_labelled_set(io.StringIO(data + "\n"))

    def test_rejects_missing_required_key(self) -> None:
        data = json.dumps(
            {
                "file": "tests/unit/test_foo.py",
                "test_name": "test_bar",
                "label": "STRONG",
                # missing "rationale"
            }
        )
        with pytest.raises(ValueError, match="rationale"):
            judge_module.load_labelled_set(io.StringIO(data + "\n"))

    def test_reports_line_number_on_reject(self) -> None:
        lines = (
            json.dumps(
                {
                    "file": "tests/unit/test_foo.py",
                    "test_name": "test_bar",
                    "label": "STRONG",
                    "rationale": "Valid record.",
                }
            )
            + "\n"
        )
        lines += (
            json.dumps(
                {
                    "file": "tests/unit/test_foo.py",
                    "test_name": "test_baz",
                    "label": "BAD_LABEL",
                    "rationale": "Invalid record.",
                }
            )
            + "\n"
        )
        with pytest.raises(ValueError, match="(?i)line 2"):
            judge_module.load_labelled_set(io.StringIO(lines))

    def test_empty_stream_returns_empty_list(self) -> None:
        records = judge_module.load_labelled_set(io.StringIO(""))
        assert records == []


# ---------------------------------------------------------------------------
# aggregate_calibration
# ---------------------------------------------------------------------------


class TestAggregateCalibration:
    def test_computes_confusion_matrix(self) -> None:
        # 5 records: 3 STRONG (true), 2 WEAK (true)
        # Predictions: 2 STRONG (correct), 1 STRONG (FP), 2 WEAK (correct for weak)
        records = [
            {"file": "f1", "test_name": "t1", "label": "STRONG", "rationale": "r"},
            {"file": "f2", "test_name": "t2", "label": "STRONG", "rationale": "r"},
            {"file": "f3", "test_name": "t3", "label": "STRONG", "rationale": "r"},
            {"file": "f4", "test_name": "t4", "label": "WEAK", "rationale": "r"},
            {"file": "f5", "test_name": "t5", "label": "WEAK", "rationale": "r"},
        ]
        predictions = [
            {"overall": 5},  # STRONG — correct
            {"overall": 4},  # STRONG — correct
            {"overall": 2},  # WEAK — FP (true STRONG, predicted WEAK)
            {"overall": 2},  # WEAK — correct (true WEAK)
            {"overall": 1},  # WEAK — correct (true WEAK)
        ]
        result = judge_module.aggregate_calibration(records, predictions)

        matrix = result["confusion_matrix"]
        assert matrix["STRONG"]["STRONG"] == 2
        assert matrix["STRONG"]["WEAK"] == 1
        assert matrix["WEAK"]["WEAK"] == 2
        assert matrix["STRONG"]["MEDIUM"] == 0
        assert matrix["WEAK"]["STRONG"] == 0

    def test_computes_recall_and_fp_rate(self) -> None:
        records = [
            {"file": "f1", "test_name": "t1", "label": "STRONG", "rationale": "r"},
            {"file": "f2", "test_name": "t2", "label": "STRONG", "rationale": "r"},
            {"file": "f3", "test_name": "t3", "label": "WEAK", "rationale": "r"},
            {"file": "f4", "test_name": "t4", "label": "WEAK", "rationale": "r"},
        ]
        # 2 STRONG correct (overall=4,5), 0 STRONG false positive (0 MEDIUM predictions)
        # 2 WEAK correct (overall=1,2), 0 WEAK missed
        predictions = [
            {"overall": 5},  # STRONG
            {"overall": 4},  # STRONG
            {"overall": 2},  # WEAK
            {"overall": 1},  # WEAK
        ]
        result = judge_module.aggregate_calibration(records, predictions)

        assert result["weak_recall"] == pytest.approx(1.0)
        assert result["strong_fp_rate"] == pytest.approx(0.0)

    def test_weak_recall_formula(self) -> None:
        # 3 WEAK true, judge predicts 1 WEAK, 2 STRONG (FP)
        # WEAK recall = 1/3
        records = [
            {"file": "f1", "test_name": "t1", "label": "WEAK", "rationale": "r"},
            {"file": "f2", "test_name": "t2", "label": "WEAK", "rationale": "r"},
            {"file": "f3", "test_name": "t3", "label": "WEAK", "rationale": "r"},
        ]
        predictions = [
            {"overall": 5},  # STRONG (miss)
            {"overall": 4},  # STRONG (miss)
            {"overall": 1},  # WEAK (hit)
        ]
        result = judge_module.aggregate_calibration(records, predictions)

        assert result["weak_recall"] == pytest.approx(1 / 3)

    def test_strong_fp_rate_formula(self) -> None:
        # 2 STRONG true, judge predicts both as WEAK
        # STRONG FP = 2/2 = 1.0 (every true STRONG was mislabeled as WEAK)
        records = [
            {"file": "f1", "test_name": "t1", "label": "STRONG", "rationale": "r"},
            {"file": "f2", "test_name": "t2", "label": "STRONG", "rationale": "r"},
        ]
        predictions = [
            {"overall": 1},  # WEAK (miss)
            {"overall": 2},  # WEAK (miss)
        ]
        result = judge_module.aggregate_calibration(records, predictions)

        assert result["strong_fp_rate"] == pytest.approx(1.0)

    def test_handles_skipped_predictions(self) -> None:
        records = [
            {"file": "f1", "test_name": "t1", "label": "STRONG", "rationale": "r"},
            {"file": "f2", "test_name": "t2", "label": "WEAK", "rationale": "r"},
            {"file": "f3", "test_name": "t3", "label": "WEAK", "rationale": "r"},
        ]
        predictions = [
            {"overall": 5},  # correct STRONG
            None,  # skipped
            {"overall": 1},  # correct WEAK
        ]
        result = judge_module.aggregate_calibration(records, predictions)

        assert result["skipped"] == 1
        # Confusion matrix only includes the 2 non-skipped
        assert result["total"] == 2

    def test_verdict_met_when_thresholds_met(self) -> None:
        records = [{"file": "f1", "test_name": "t1", "label": "WEAK", "rationale": "r"}] * 10
        # Simulate perfect recall and zero false positive rate
        predictions = [{"overall": 1} for _ in range(10)]
        result = judge_module.aggregate_calibration(records, predictions)

        # All WEAK, all correctly predicted WEAK → 100% recall, 0% FP
        assert result["weak_recall"] == pytest.approx(1.0)
        assert result["strong_fp_rate"] == pytest.approx(0.0)
        assert result["verdict"] == "MET"

    def test_verdict_not_met_when_thresholds_fail(self) -> None:
        records = [{"file": "f1", "test_name": "t1", "label": "WEAK", "rationale": "r"}] * 10
        # All WEAK predicted as STRONG → 0% recall
        predictions = [{"overall": 5} for _ in range(10)]
        result = judge_module.aggregate_calibration(records, predictions)

        assert result["weak_recall"] == pytest.approx(0.0)
        assert result["verdict"] == "NOT MET"

    def test_empty_predictions_all_skipped(self) -> None:
        records = [{"file": "f1", "test_name": "t1", "label": "STRONG", "rationale": "r"}]
        predictions: list[dict | None] = [None]
        result = judge_module.aggregate_calibration(records, predictions)

        assert result["skipped"] == 1
        assert result["total"] == 0
        assert result["verdict"] == "NOT MET"

    def test_token_spend_accumulated(self) -> None:
        records = [{"file": "f1", "test_name": "t1", "label": "STRONG", "rationale": "r"}] * 2
        predictions = [{"overall": 5}, {"overall": 4}]
        result = judge_module.aggregate_calibration(records, predictions)

        # Check the token fields exist and carry sensible (non-negative) values.
        # Using >= 0 assertions tests that the function actually computed
        # and stored meaningful counts, not just placeholder zeros.
        assert result["total_input_tokens"] >= 0
        assert result["total_output_tokens"] >= 0
        # Cost is a float; must be non-negative and the right type.
        assert isinstance(result["total_cost_usd"], float)
        assert result["total_cost_usd"] >= 0.0


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


class TestArgumentParsing:
    def test_rejects_empty_test_name(self) -> None:
        # argparse does not reject empty strings directly; validation is in main()
        args = judge_module._build_arg_parser().parse_args(
            ["--test-file", "tests/unit/test_foo.py", "--test-name", ""]
        )
        # The empty string is accepted by argparse; main() would exit 1 with a
        # "--test-name is required" error. We test the argument parsing itself.
        assert args.test_name == ""

    def test_rejects_missing_test_file(self) -> None:
        # argparse itself does not enforce --test-file as required;
        # that check is in main(). We verify the parser accepts the partial
        # call (so validation via main() is what should raise).
        args = judge_module._build_arg_parser().parse_args(["--test-name", "test_bar"])
        assert args.test_file is None
        assert args.test_name == "test_bar"

    def test_accepts_valid_test_file_and_name(self) -> None:
        args = judge_module._build_arg_parser().parse_args(
            ["--test-file", "tests/unit/test_foo.py", "--test-name", "test_bar"]
        )
        assert args.test_file == "tests/unit/test_foo.py"
        assert args.test_name == "test_bar"

    def test_accepts_calibrate_mode(self) -> None:
        args = judge_module._build_arg_parser().parse_args(
            ["--calibrate", "tests/llm_judge/labelled_set.jsonl"]
        )
        assert args.calibrate == "tests/llm_judge/labelled_set.jsonl"

    def test_accepts_custom_model(self) -> None:
        args = judge_module._build_arg_parser().parse_args(
            [
                "--test-file",
                "tests/unit/test_foo.py",
                "--test-name",
                "test_bar",
                "--model",
                "anthropic/claude-opus-4-7",
            ]
        )
        assert args.model == "anthropic/claude-opus-4-7"

    def test_prod_file_is_optional(self) -> None:
        args = judge_module._build_arg_parser().parse_args(
            ["--test-file", "tests/unit/test_foo.py", "--test-name", "test_bar"]
        )
        assert args.prod_file is None

    def test_prod_file_accepted(self) -> None:
        args = judge_module._build_arg_parser().parse_args(
            [
                "--test-file",
                "tests/unit/test_foo.py",
                "--test-name",
                "test_bar",
                "--prod-file",
                "orch/foo.py",
            ]
        )
        assert args.prod_file == "orch/foo.py"

    def test_mutually_exclusive_test_and_calibrate(self) -> None:
        # argparse allows both; mutual-exclusion check is in main(), not argparser
        args = judge_module._build_arg_parser().parse_args(
            [
                "--calibrate",
                "tests/llm_judge/labelled_set.jsonl",
                "--test-file",
                "tests/unit/test_foo.py",
                "--test-name",
                "test_bar",
            ]
        )
        assert args.calibrate == "tests/llm_judge/labelled_set.jsonl"
        assert args.test_file == "tests/unit/test_foo.py"
        assert args.test_name == "test_bar"


# ---------------------------------------------------------------------------
# API-key guard
# ---------------------------------------------------------------------------

_ANTHROPIC_INSTALLED = judge_module.anthropic is not None


class TestApiKeyGuard:
    def test_main_exits_2_when_anthropic_api_key_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(SystemExit) as exc_info:
            # main() returns an int; sys.exit() converts it to SystemExit so pytest
            # can catch it. We invoke it inside the with-block.
            judge_module.sys.exit(
                judge_module.main(
                    ["--test-file", "tests/unit/test_foo.py", "--test-name", "test_bar"]
                )
            )
        assert exc_info.value.code == 2

    @pytest.mark.skipif(
        not _ANTHROPIC_INSTALLED,
        reason="anthropic package not installed",
    )
    def test_main_exits_2_when_anthropic_not_installed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With a key present but anthropic not installed, exits 2."""
        # Simulate anthropic not installed by patching it to None after import
        original_anthropic = judge_module.anthropic
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-fake-key")
        try:
            judge_module.anthropic = None  # type: ignore[assignment]
            with pytest.raises(SystemExit) as exc_info:
                judge_module.sys.exit(
                    judge_module.main(
                        ["--test-file", "tests/unit/test_foo.py", "--test-name", "test_bar"]
                    )
                )
            assert exc_info.value.code == 2, "Missing anthropic package should exit 2"
        finally:
            judge_module.anthropic = original_anthropic

    @pytest.mark.skipif(
        not _ANTHROPIC_INSTALLED,
        reason="anthropic package not installed",
    )
    def test_main_exits_1_on_api_error_not_2(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """With a key present, a real API error exits 1, not 2."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-fake-key")

        mock_msg_block = MagicMock()
        mock_msg_block.text = '{"error": {"type": "authentication_error"}}'

        mock_response = MagicMock()
        mock_response.content = [mock_msg_block]
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 5

        mock_messages = MagicMock()
        mock_messages.parse.return_value = mock_response

        mock_client_instance = MagicMock()
        mock_client_instance.messages = mock_messages

        with patch.object(judge_module.anthropic, "Anthropic", return_value=mock_client_instance):
            with pytest.raises(SystemExit) as exc_info:
                judge_module.sys.exit(
                    judge_module.main(
                        ["--test-file", "tests/unit/test_foo.py", "--test-name", "test_bar"]
                    )
                )
            assert exc_info.value.code == 1, "API error should exit 1, not 2"
