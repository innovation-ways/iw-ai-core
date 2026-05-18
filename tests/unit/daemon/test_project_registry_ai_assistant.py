"""Unit tests for ai_assistant parsing in project registry."""

from __future__ import annotations

import logging

from orch.daemon import project_registry


def test_parse_valid_block() -> None:
    raw = {
        "models": ["anthropic/claude-opus-4-7", "openai/gpt-5.3-codex"],
        "default_model": "anthropic/claude-opus-4-7",
    }

    parsed = project_registry._parse_ai_assistant_block("iw-ai-core", raw)

    assert parsed == raw


def test_parse_missing_block() -> None:
    parsed = project_registry._parse_ai_assistant_block("iw-ai-core", None)
    assert parsed is None


def test_parse_empty_models_list(caplog) -> None:
    with caplog.at_level(logging.WARNING):
        parsed = project_registry._parse_ai_assistant_block("iw-ai-core", {"models": []})

    assert parsed is None
    assert "missing or invalid `models`" in caplog.text


def test_parse_drops_invalid_entries(caplog) -> None:
    raw = {
        "models": [
            "anthropic/claude-opus-4-7",
            "MiniMax-M2.7",
            "bad provider/model",
            "ollama/gemma4:26b",
        ]
    }

    with caplog.at_level(logging.WARNING):
        parsed = project_registry._parse_ai_assistant_block("iw-ai-core", raw)

    assert parsed == {"models": ["anthropic/claude-opus-4-7", "ollama/gemma4:26b"]}
    assert "invalid ai_assistant model entry" in caplog.text


def test_parse_deduplicates_preserving_order() -> None:
    raw = {
        "models": [
            "anthropic/claude-opus-4-7",
            "openai/gpt-5.3-codex",
            "anthropic/claude-opus-4-7",
            "openai/gpt-5.3-codex",
            "ollama/gemma4:26b",
        ]
    }

    parsed = project_registry._parse_ai_assistant_block("iw-ai-core", raw)

    assert parsed == {
        "models": [
            "anthropic/claude-opus-4-7",
            "openai/gpt-5.3-codex",
            "ollama/gemma4:26b",
        ]
    }


def test_parse_default_model_not_in_models(caplog) -> None:
    raw = {
        "models": ["anthropic/claude-opus-4-7"],
        "default_model": "openai/gpt-5.3-codex",
    }

    with caplog.at_level(logging.WARNING):
        parsed = project_registry._parse_ai_assistant_block("iw-ai-core", raw)

    assert parsed == {"models": ["anthropic/claude-opus-4-7"]}
    assert "default_model" in caplog.text


def test_parse_default_model_survives_filter() -> None:
    raw = {
        "models": ["anthropic/claude-opus-4-7", "ollama/gemma4:26b"],
        "default_model": "ollama/gemma4:26b",
    }

    parsed = project_registry._parse_ai_assistant_block("iw-ai-core", raw)

    assert parsed == {
        "models": ["anthropic/claude-opus-4-7", "ollama/gemma4:26b"],
        "default_model": "ollama/gemma4:26b",
    }


def test_parse_non_string_entries_dropped(caplog) -> None:
    raw = {"models": ["valid/x", 42, None]}

    with caplog.at_level(logging.WARNING):
        parsed = project_registry._parse_ai_assistant_block("iw-ai-core", raw)

    assert parsed == {"models": ["valid/x"]}
    assert "invalid ai_assistant model entry" in caplog.text
