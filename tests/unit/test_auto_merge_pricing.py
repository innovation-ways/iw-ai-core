from __future__ import annotations

from unittest.mock import MagicMock

from orch.auto_merge_aggregator import MODEL_PRICING, get_token_cost_rollup


def _event(model: str, inp: int, out: int):
    row = MagicMock()
    row.event_metadata = {
        "llm_calls": [{"model": model, "input_tokens": inp, "output_tokens": out}]
    }
    return row


def test_pricing_known_model_claude_sonnet() -> None:
    db = MagicMock()
    db.scalars.return_value.all.return_value = [_event("claude-sonnet-4-6", 1_000_000, 1_000_000)]
    rollup = get_token_cost_rollup(db, "p", "7d")
    assert rollup.total_cost_usd == 18.0


def test_pricing_known_model_minimax() -> None:
    db = MagicMock()
    db.scalars.return_value.all.return_value = [
        _event("minimax/MiniMax-M2.7", 1_000_000, 1_000_000)
    ]
    rollup = get_token_cost_rollup(db, "p", "7d")
    assert rollup.total_cost_usd == 1.2


def test_pricing_unknown_model_returns_zero() -> None:
    db = MagicMock()
    db.scalars.return_value.all.return_value = [_event("unknown/m", 100, 200)]
    assert get_token_cost_rollup(db, "p", "7d").total_cost_usd == 0.0


def test_pricing_unknown_model_sets_has_unknown_models_flag() -> None:
    db = MagicMock()
    db.scalars.return_value.all.return_value = [_event("unknown/m", 100, 200)]
    assert get_token_cost_rollup(db, "p", "7d").has_unknown_models is True


def test_pricing_zero_tokens_returns_zero_cost() -> None:
    db = MagicMock()
    db.scalars.return_value.all.return_value = [_event("openai/gpt-5.3-codex", 0, 0)]
    assert get_token_cost_rollup(db, "p", "7d").total_cost_usd == 0.0


def test_pricing_covers_every_enabled_agent_runtime_option() -> None:
    known_models = set(MODEL_PRICING)
    required = {
        "claude-sonnet-4-6",
        "claude-opus-4-7",
        "openai/gpt-5.3-codex",
        "minimax/MiniMax-M2.7",
    }
    assert required.issubset(known_models)
