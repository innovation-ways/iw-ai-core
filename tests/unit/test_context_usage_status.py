from __future__ import annotations

import math

from orch.chat.context_usage import (
    resolve_context_usage_opencode,
    resolve_context_usage_pi,
)
from orch.db.models import AgentRuntimeOption


def _shape_assert(result: object) -> None:
    for key in ("status", "pct", "used_tokens", "window_tokens", "reason"):
        assert hasattr(result, key)


def test_opencode_known() -> None:
    providers = {
        "providers": [{"id": "openai", "models": {"gpt-4o": {"limit": {"context": 100000}}}}]
    }
    messages = [{"role": "assistant", "tokens": {"input": 4000, "output": 1000}}]
    result = resolve_context_usage_opencode(
        client_healthy=True,
        providers=providers,
        tab_model="openai/gpt-4o",
        messages=messages,
    )
    _shape_assert(result)
    assert result.status == "known"
    assert result.pct == 5.0
    assert result.used_tokens == 5000
    assert result.window_tokens == 100000
    assert result.reason is None


def test_opencode_unknown_window() -> None:
    result = resolve_context_usage_opencode(
        client_healthy=True,
        providers={"providers": []},
        tab_model="openai/gpt-4o",
        messages=[{"role": "assistant", "tokens": {"input": 1}}],
    )
    _shape_assert(result)
    assert result.status == "unknown_window"
    assert result.pct is None
    assert result.used_tokens is None
    assert result.window_tokens is None


def test_opencode_unknown_runtime() -> None:
    result = resolve_context_usage_opencode(
        client_healthy=False,
        providers={"providers": []},
        tab_model="openai/gpt-4o",
        messages=[],
    )
    _shape_assert(result)
    assert result.status == "unknown_runtime"
    assert result.reason == "OpenCode runtime unavailable"


def test_pi_known() -> None:
    row = AgentRuntimeOption(
        cli_tool="pi",
        model="MiniMax-M2.7",
        cli_label="Pi",
        model_label="MiniMax",
        display_name="Pi MiniMax",
        context_window_tokens=200000,
    )
    messages = [{"role": "assistant", "usage": {"input": 100000, "output": 20000}}]
    result = resolve_context_usage_pi(
        pi_healthy=True,
        agent_runtime_option=row,
        tab_model="pi/MiniMax-M2.7",
        messages=messages,
    )
    _shape_assert(result)
    assert result.status == "known"
    assert result.pct == 60.0
    assert result.used_tokens == 120000
    assert result.window_tokens == 200000


def test_pi_unknown_window() -> None:
    row = AgentRuntimeOption(
        cli_tool="pi",
        model="MiniMax-M2.7",
        cli_label="Pi",
        model_label="MiniMax",
        display_name="Pi MiniMax",
        context_window_tokens=None,
    )
    result = resolve_context_usage_pi(
        pi_healthy=True,
        agent_runtime_option=row,
        tab_model="pi/MiniMax-M2.7",
        messages=[],
    )
    _shape_assert(result)
    assert result.status == "unknown_window"
    assert "set context_window_tokens" in (result.reason or "")


def test_pi_unknown_runtime() -> None:
    result = resolve_context_usage_pi(
        pi_healthy=False,
        agent_runtime_option=None,
        tab_model="pi/MiniMax-M2.7",
        messages=[],
    )
    _shape_assert(result)
    assert result.status == "unknown_runtime"
    assert result.reason == "Pi runtime unavailable"


def test_known_status_equivalence_to_non_null_fields() -> None:
    providers = {"providers": [{"id": "openai", "models": {"gpt-4o": {"limit": {"context": 100}}}}]}
    known = resolve_context_usage_opencode(
        client_healthy=True,
        providers=providers,
        tab_model="openai/gpt-4o",
        messages=[{"role": "assistant", "tokens": {"input": 10}}],
    )
    unknown = resolve_context_usage_opencode(
        client_healthy=True,
        providers={"providers": []},
        tab_model="openai/gpt-4o",
        messages=[{"role": "assistant", "tokens": {"input": 10}}],
    )

    def pred(r: object) -> bool:
        pct = getattr(r, "pct")
        return (
            pct is not None
            and math.isfinite(pct)
            and getattr(r, "used_tokens") is not None
            and getattr(r, "window_tokens") is not None
        )

    assert (known.status == "known") is pred(known)
    assert (unknown.status == "known") is pred(unknown)
