"""Pure helpers for computing LLM context-window usage.

No I/O, no DB, no HTTP — fully unit-testable without mocks or testcontainers.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Literal, TypedDict

DEFAULT_SAFETY_BUFFER_TOKENS = 20_000


@dataclass(frozen=True)
class ContextUsage:
    """Snapshot of context-window usage for a single chat session.

    Attributes:
        status: Whether usage is fully known, the window size is unknown,
            or the runtime itself is unavailable.
        pct: Usage as a percentage in [0, 100], or None when unknown.
        used_tokens: Tokens consumed by the conversation so far, or None.
        window_tokens: The model's context-window size in tokens, or None.
        reason: Human-readable explanation when status is not "known".
    """

    status: Literal["known", "unknown_window", "unknown_runtime"]
    pct: float | None
    used_tokens: int | None
    window_tokens: int | None
    reason: str | None


def _assert_context_usage_invariant(result: ContextUsage) -> None:
    known_by_fields = (
        result.pct is not None
        and isfinite(result.pct)
        and result.used_tokens is not None
        and result.window_tokens is not None
    )
    assert (result.status == "known") == known_by_fields  # noqa: S101


def _finalize_context_usage(result: ContextUsage) -> ContextUsage:
    _assert_context_usage_invariant(result)
    return result


class _TokensShape(TypedDict, total=False):
    input: int
    output: int
    reasoning: int
    cache: dict[str, int]


def normalize_pi_messages(
    messages: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Normalize Pi-shaped messages into OpenCode ``tokens`` shape for ``compute_context_pct``.

    Pi RPC messages carry per-message token usage as::

        {"role": "assistant", "usage": {"input": N, "output": N, "cacheRead": N, "cacheWrite": N}}

    ``compute_context_pct`` reads from ``message["tokens"]`` with snake_case sub-fields
    ``cache.read`` / ``cache.write`` nested under a ``cache`` key::

        {"role": "assistant", "tokens": {"input": N, "output": N,
                                    "cache": {"read": N, "write": N}}}

    This normalizer translates Pi's camelCase ``usage`` into the matching OpenCode
    shape. The translation is applied to every message in the list that carries a
    ``usage`` dict; all other fields pass through unchanged. Non-list input
    returns an empty list (so the caller receives a valid argument to
    ``compute_context_pct`` without additional None-checks).

    Parameters
    ----------
    messages:
        List of message dicts as returned by ``PiRuntime.get_messages()``.
        May be ``None`` or non-list — the function returns ``[]`` in that case.
    """
    if not isinstance(messages, list):
        return []

    result: list[dict[str, Any]] = []
    for msg in messages:
        if not isinstance(msg, dict):
            result.append(msg)
            continue
        normalized = dict(msg)
        usage = msg.get("usage")
        if isinstance(usage, dict):
            # Translate camelCase → snake_case and nest cache fields under "cache".
            normalized["tokens"] = {
                "input": int(usage["input"]) if "input" in usage else 0,
                "output": int(usage["output"]) if "output" in usage else 0,
                "reasoning": int(usage.get("reasoning", 0)),
                "cache": {
                    "read": int(usage.get("cacheRead", 0)),
                    "write": int(usage.get("cacheWrite", 0)),
                },
            }
        result.append(normalized)
    return result


def compute_context_pct(
    messages: list[dict[str, Any]] | None,
    context_window: int | float | None,
) -> float | None:
    """Return context-window usage as a percentage in [0, 100], or None.

    Returns None when usage cannot be determined: no assistant message carries
    positive token usage, or ``context_window`` is missing / not positive.

    Parameters
    ----------
    messages:
        List of message dicts as returned by the runtime's message-history
        endpoint. Each dict is assumed to have a ``role`` field at the top
        level *or* nested under ``info.role`` (OpenCode payload variant).
        Assistant messages may carry a ``tokens`` object shaped like
        ``{"input", "output", "reasoning", "cache": {"read", "write"}}``;
        every sub-field is optional and defaults to 0. Pi messages should be
        normalized via ``normalize_pi_messages`` before calling this function.
    context_window:
        The active model's context-window limit (max tokens). None / 0 /
        negative → return None.
    """
    if context_window is None or context_window <= 0:
        return None

    if not isinstance(messages, list):
        return None

    # Scan from most-recent (end of list) to oldest — find the first assistant
    # message that carries positive token usage.
    used_tokens: int | None = None

    for msg in reversed(messages):
        if not isinstance(msg, dict):
            continue

        # Resolve role: top-level "role" or nested under info.role
        role: str | None = msg.get("role")
        info = msg.get("info")
        if isinstance(info, dict):
            info_role = info.get("role")
            # Prefer info.role when top-level role is absent or "user"/"system"
            # (some OpenCode payloads have the real role only in info)
            if role is None or role in ("user", "system"):
                role = info_role
        if role is None:
            continue
        if role != "assistant":
            continue

        tokens_raw = msg.get("tokens")
        if not isinstance(tokens_raw, dict):
            continue

        # Sum every sub-field; missing / None → 0
        def _int(val: Any) -> int:
            return int(val) if isinstance(val, (int, float)) else 0

        input_t = _int(tokens_raw.get("input"))
        output_t = _int(tokens_raw.get("output"))
        reasoning_t = _int(tokens_raw.get("reasoning"))
        cache_read = _int(
            tokens_raw.get("cache", {}).get("read")
            if isinstance(tokens_raw.get("cache"), dict)
            else None
        )
        cache_write = _int(
            tokens_raw.get("cache", {}).get("write")
            if isinstance(tokens_raw.get("cache"), dict)
            else None
        )

        used_tokens = input_t + output_t + reasoning_t + cache_read + cache_write
        break

    if used_tokens is None or used_tokens <= 0:
        return None

    pct = (used_tokens / context_window) * 100.0

    # Clamp to [0, 100]
    if pct < 0:
        return 0.0
    if pct > 100.0:
        return 100.0
    return pct


def compute_effective_context_pct(
    used_tokens: int | float | None,
    context_window: int | float | None,
    max_output_tokens: int | float | None,
    safety_buffer: int | float = DEFAULT_SAFETY_BUFFER_TOKENS,
) -> float | None:
    """Return context-window usage as a percentage against the EFFECTIVE budget.

    The effective budget is ``context_window − max_output_tokens − safety_buffer``.
    This is the number of input tokens that can actually fit alongside the model's
    maximum possible output without overflowing the context window.

    Unlike ``compute_context_pct`` which divides by the raw ``context_window``,
    this function accounts for the output reservation — required for models where
    ``max_output_tokens`` is a large fraction of the window (e.g. MiniMax-M2.7:
    204,800 window / 131,072 max output → effective budget ~74K).

    The percentage is **allowed to exceed 100%** so callers can display a
    "PAST CEILING" warning; use ``min(result, 100)`` if a clamped gauge is needed.

    Parameters
    ----------
    used_tokens:
        Total tokens accumulated in the conversation so far (input side).
        None / 0 / negative → return None (nothing to compute).
    context_window:
        The model's total context-window limit in tokens.
        None / ≤ 0 → return None.
    max_output_tokens:
        The model's maximum output capacity in tokens (from ``agent_runtime_options``).
        **None → fall back to raw-window behaviour** (divide by ``context_window``)
        so the meter degrades gracefully when no output reservation is stored.
    safety_buffer:
        Extra headroom reserved for the model's response itself, in tokens.
        Defaults to 20,000 (opencode's convention, per R-00078). Set to 0 to
        disable the reserve. The effective budget is always
        ``context_window − max_output − safety_buffer``.

    Returns
    -------
    float | None
        Usage percentage (may exceed 100 when input has passed the effective
        ceiling), or None when the computation is not possible / meaningful.
    """
    # Guard: missing usage data
    if used_tokens is None:
        return None

    # Guard: no meaningful context window
    if context_window is None or context_window <= 0:
        return None

    # Guard: effective budget must be positive (window must exceed output+buffer)
    effective_budget: float
    if max_output_tokens is None:
        # NULL max_output → fall back to raw-window behaviour (degrade gracefully).
        effective_budget = float(context_window)
    else:
        effective_budget = float(context_window) - float(max_output_tokens) - float(safety_buffer)

    if effective_budget <= 0:
        # window is too small for the output reservation to leave any input budget.
        return None

    # Clamp non-positive used_tokens to 0% rather than returning None — the
    # caller distinguishes "no data" (None) from "no input consumed yet" (0%).
    if used_tokens <= 0:
        return 0.0

    return (float(used_tokens) / effective_budget) * 100.0


def lookup_max_output_tokens(
    providers_raw: dict[str, Any],
    provider_id: str,
    model_id: str,
) -> int | None:
    """Return the ``limit.max_output`` value for a given provider+model pair.

    Mirrors the structure of ``lookup_context_window`` but reads the
    ``max_output`` field from the provider configuration. This field is optional
    and may not be present in all provider configs; return None when absent.

    Parameters
    ----------
    providers_raw:
        The decoded JSON from ``GET /config/providers`` —
        ``{"providers": [{"id": "...", "models": {"<modelId>": {"limit": {"max_output": N}}}}]}``.
    provider_id:
        The provider identifier (e.g. ``"openai"``).
    model_id:
        The model identifier (e.g. ``"gpt-4o"``).
    """
    providers = providers_raw.get("providers")
    if not isinstance(providers, list):
        return None

    for p in providers:
        if not isinstance(p, dict):
            continue
        if p.get("id") != provider_id:
            continue
        models = p.get("models")
        if not isinstance(models, dict):
            return None
        model_entry = models.get(model_id)
        if not isinstance(model_entry, dict):
            return None
        limit = model_entry.get("limit")
        if not isinstance(limit, dict):
            return None
        max_output = limit.get("max_output")
        if isinstance(max_output, (int, float)) and max_output > 0:
            return int(max_output)
        return None

    return None


def lookup_context_window(
    providers_raw: dict[str, Any],
    provider_id: str,
    model_id: str,
) -> int | None:
    """Return the ``limit.context`` value for a given provider+model pair.

    Returns ``None`` when the value is absent or not a positive integer.

    Parameters
    ----------
    providers_raw:
        The decoded JSON from ``GET /config/providers`` —
        ``{"providers": [{"id": "...", "models": {"<modelId>": {"limit": {"context": N}}}]}}``.
    provider_id:
        The provider identifier (e.g. ``"openai"``).
    model_id:
        The model identifier (e.g. ``"gpt-4o"``).
    """
    providers = providers_raw.get("providers")
    if not isinstance(providers, list):
        return None

    for p in providers:
        if not isinstance(p, dict):
            continue
        if p.get("id") != provider_id:
            continue
        models = p.get("models")
        if not isinstance(models, dict):
            return None
        model_entry = models.get(model_id)
        if not isinstance(model_entry, dict):
            return None
        limit = model_entry.get("limit")
        if not isinstance(limit, dict):
            return None
        context = limit.get("context")
        if isinstance(context, (int, float)) and context > 0:
            return int(context)
        return None

    return None


def resolve_context_usage_opencode(
    *,
    client_healthy: bool,
    providers: dict[str, Any],
    tab_model: str | None,
    messages: list[Any],
) -> ContextUsage:
    """Compute context usage for an OpenCode-backed chat session.

    Resolves provider and model from message history or tab_model string,
    looks up the context window from the providers catalogue, then delegates
    to compute_context_pct.

    Args:
        client_healthy: Whether the OpenCode runtime is up and reachable.
        providers: Decoded JSON from GET /config/providers.
        tab_model: The tab's currently-selected model string in
            ``"<providerId>/<modelId>"`` form, used as fallback when messages
            carry no provider/model info.
        messages: Full message history for the session.

    Returns:
        ContextUsage with status "known", "unknown_window", or "unknown_runtime".
    """
    if not client_healthy:
        return _finalize_context_usage(
            ContextUsage(
                status="unknown_runtime",
                pct=None,
                used_tokens=None,
                window_tokens=None,
                reason="OpenCode runtime unavailable",
            )
        )

    resolved = resolve_model_from_tab(tab_model, messages)
    if resolved is None:
        model_label = tab_model if isinstance(tab_model, str) and tab_model else "unknown"
        return _finalize_context_usage(
            ContextUsage(
                status="unknown_window",
                pct=None,
                used_tokens=None,
                window_tokens=None,
                reason=f"Context window unknown for opencode/{model_label}",
            )
        )

    provider_id, model_id = resolved
    context_window = lookup_context_window(providers, provider_id, model_id)
    if context_window is None:
        return _finalize_context_usage(
            ContextUsage(
                status="unknown_window",
                pct=None,
                used_tokens=None,
                window_tokens=None,
                reason=f"Context window unknown for opencode/{provider_id}/{model_id}",
            )
        )

    pct = compute_context_pct(messages, context_window)
    if pct is None:
        return _finalize_context_usage(
            ContextUsage(
                status="unknown_window",
                pct=None,
                used_tokens=None,
                window_tokens=None,
                reason=f"Context window unknown for opencode/{provider_id}/{model_id}",
            )
        )

    used_tokens = int(round((context_window * pct) / 100.0))
    return _finalize_context_usage(
        ContextUsage(
            status="known",
            pct=pct,
            used_tokens=used_tokens,
            window_tokens=context_window,
            reason=None,
        )
    )


def resolve_context_usage_pi(
    *,
    pi_healthy: bool,
    agent_runtime_option: Any | None,
    tab_model: str | None,
    messages: list[Any],
) -> ContextUsage:
    """Compute context usage for a Pi-backed chat session.

    Reads context_window_tokens from agent_runtime_option, normalises Pi
    messages to the OpenCode token shape, then delegates to compute_context_pct.

    Args:
        pi_healthy: Whether the Pi runtime binary is available on PATH.
        agent_runtime_option: The AgentRuntimeOption row for the session (may
            be None when not yet resolved or missing from the catalogue).
        tab_model: The tab's currently-selected model string, used in error
            messages when the window size is unknown.
        messages: Full message history as returned by PiRuntime.get_messages().

    Returns:
        ContextUsage with status "known", "unknown_window", or "unknown_runtime".
    """
    if not pi_healthy:
        return _finalize_context_usage(
            ContextUsage(
                status="unknown_runtime",
                pct=None,
                used_tokens=None,
                window_tokens=None,
                reason="Pi runtime unavailable",
            )
        )

    model_label = tab_model if isinstance(tab_model, str) and tab_model else "pi/unknown"
    context_window = (
        int(agent_runtime_option.context_window_tokens)
        if agent_runtime_option is not None
        and getattr(agent_runtime_option, "context_window_tokens", None) is not None
        else None
    )
    if context_window is None:
        return _finalize_context_usage(
            ContextUsage(
                status="unknown_window",
                pct=None,
                used_tokens=None,
                window_tokens=None,
                reason=(
                    f"Context window unknown for {model_label} — "
                    "set context_window_tokens in agent_runtime_options"
                ),
            )
        )

    normalized_msgs = normalize_pi_messages(messages if isinstance(messages, list) else [])
    pct = compute_context_pct(normalized_msgs, context_window)
    if pct is None:
        return _finalize_context_usage(
            ContextUsage(
                status="unknown_window",
                pct=None,
                used_tokens=None,
                window_tokens=None,
                reason=(
                    f"Context window unknown for {model_label} — "
                    "set context_window_tokens in agent_runtime_options"
                ),
            )
        )

    used_tokens = int(round((context_window * pct) / 100.0))
    return _finalize_context_usage(
        ContextUsage(
            status="known",
            pct=pct,
            used_tokens=used_tokens,
            window_tokens=context_window,
            reason=None,
        )
    )


def resolve_model_from_tab(
    tab_model: str | None,
    messages: list[dict[str, Any]],
) -> tuple[str, str] | None:
    """Resolve (provider_id, model_id) from a tab.

    Prefers the provider/model info on the most-recent assistant message;
    falls back to the ``tab_model`` string (``"<providerId>/<modelId>"``).

    Returns ``None`` when neither source yields a usable split.
    """
    # Scan messages most-recent first for a provider+model hint on an assistant
    for msg in reversed(messages):
        if not isinstance(msg, dict):
            continue
        # Only assistant messages carry valid runtime provider/model info
        role: str | None = msg.get("role")
        info = msg.get("info")
        if isinstance(info, dict):
            info_role = info.get("role")
            if role is None or role in ("user", "system"):
                role = info_role
        if role != "assistant":
            continue
        if isinstance(info, dict):
            pid = info.get("providerID") or info.get("providerId")
            mid = info.get("modelID") or info.get("modelId")
            if isinstance(pid, str) and isinstance(mid, str) and pid and mid:
                return (pid, mid)

    # Fall back to tab.model
    if isinstance(tab_model, str) and "/" in tab_model:
        pid, _, mid = tab_model.partition("/")
        if pid and mid:
            return (pid, mid)

    return None
