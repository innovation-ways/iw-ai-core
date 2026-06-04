"""Unit tests for ai_assistant parsing in project registry."""

from __future__ import annotations

import logging

from orch.daemon import project_registry


def test_parse_valid_block() -> None:
    """Verifies that a valid ai_assistant block is returned unchanged."""
    raw = {
        "models": ["anthropic/claude-opus-4-7", "openai/gpt-5.3-codex"],
        "default_model": "anthropic/claude-opus-4-7",
    }

    parsed = project_registry._parse_ai_assistant_block("iw-ai-core", raw)

    assert parsed == raw


def test_parse_missing_block() -> None:
    """Verifies that a None ai_assistant block returns None."""
    parsed = project_registry._parse_ai_assistant_block("iw-ai-core", None)
    assert parsed is None


def test_parse_empty_models_list(caplog) -> None:
    """Verifies that an empty models list logs a warning and returns None."""
    with caplog.at_level(logging.WARNING):
        parsed = project_registry._parse_ai_assistant_block("iw-ai-core", {"models": []})

    assert parsed is None
    assert "missing or invalid `models`" in caplog.text


def test_parse_drops_invalid_entries(caplog) -> None:
    """Verifies that invalid model entries are dropped with a warning while valid ones are kept."""
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
    """Verifies that duplicate model entries are removed while preserving the original order."""
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
    """Verifies that a default_model not present in the models list is dropped with a warning."""
    raw = {
        "models": ["anthropic/claude-opus-4-7"],
        "default_model": "openai/gpt-5.3-codex",
    }

    with caplog.at_level(logging.WARNING):
        parsed = project_registry._parse_ai_assistant_block("iw-ai-core", raw)

    assert parsed == {"models": ["anthropic/claude-opus-4-7"]}
    assert "default_model" in caplog.text


def test_parse_default_model_survives_filter() -> None:
    """Verifies that a default_model that passes validation is preserved in the output."""
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
    """Verifies that non-string model entries are dropped with a warning."""
    raw = {"models": ["valid/x", 42, None]}

    with caplog.at_level(logging.WARNING):
        parsed = project_registry._parse_ai_assistant_block("iw-ai-core", raw)

    assert parsed == {"models": ["valid/x"]}
    assert "invalid ai_assistant model entry" in caplog.text


def test_parse_default_runtime_pi() -> None:
    """Verifies that default_runtime 'pi' is accepted and preserved in the parsed block."""
    raw = {"models": ["anthropic/claude-opus-4-7"], "default_runtime": "pi"}

    parsed = project_registry._parse_ai_assistant_block("iw-ai-core", raw)

    assert parsed == {"models": ["anthropic/claude-opus-4-7"], "default_runtime": "pi"}


def test_parse_default_runtime_opencode() -> None:
    """Verifies that default_runtime 'opencode' is accepted and preserved in the parsed block."""
    raw = {"models": ["anthropic/claude-opus-4-7"], "default_runtime": "opencode"}

    parsed = project_registry._parse_ai_assistant_block("iw-ai-core", raw)

    assert parsed == {"models": ["anthropic/claude-opus-4-7"], "default_runtime": "opencode"}


def test_parse_default_runtime_absent_key_omitted() -> None:
    """Verifies that a missing default_runtime key is omitted from the parsed output."""
    raw = {"models": ["anthropic/claude-opus-4-7"]}

    parsed = project_registry._parse_ai_assistant_block("iw-ai-core", raw)

    assert parsed == {"models": ["anthropic/claude-opus-4-7"]}
    assert "default_runtime" not in parsed


def test_parse_default_runtime_invalid_ignored(caplog) -> None:
    """Verifies that an invalid default_runtime value is ignored with a warning."""
    # "claude" is a valid cli_tool but NOT a valid AI Assistant chat runtime.
    raw = {"models": ["anthropic/claude-opus-4-7"], "default_runtime": "claude"}

    with caplog.at_level(logging.WARNING):
        parsed = project_registry._parse_ai_assistant_block("iw-ai-core", raw)

    assert parsed == {"models": ["anthropic/claude-opus-4-7"]}
    assert "default_runtime" not in parsed
    assert "default_runtime" in caplog.text


def test_parse_default_runtime_and_default_model_together() -> None:
    """Verifies that both default_runtime and default_model are preserved when both are valid."""
    raw = {
        "models": ["anthropic/claude-opus-4-7", "minimax/MiniMax-M2.7"],
        "default_model": "minimax/MiniMax-M2.7",
        "default_runtime": "pi",
    }

    parsed = project_registry._parse_ai_assistant_block("iw-ai-core", raw)

    assert parsed == {
        "models": ["anthropic/claude-opus-4-7", "minimax/MiniMax-M2.7"],
        "default_model": "minimax/MiniMax-M2.7",
        "default_runtime": "pi",
    }
