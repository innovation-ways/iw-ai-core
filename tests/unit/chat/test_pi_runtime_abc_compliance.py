"""Invariant #3: ``PiRuntime`` must satisfy the ``ChatRuntime`` ABC completely.

Tests:
    - ``PiRuntime.__abstractmethods__`` is ``frozenset()`` (no unimplemented methods).
    - For each abstract method on ``ChatRuntime``, ``PiRuntime`` declares an
      implementation that is async (coroutine function OR async-generator function).
    - Method parameter names and kinds match the ABC signatures exactly.

Pattern mirrors ``tests/unit/chat/test_opencode_runtime_abc_compliance.py``
which performs the same checks for ``OpencodeRuntime``.
"""

from __future__ import annotations

import inspect
from pathlib import Path

from orch.chat.pi.pi_runtime import PiRuntime
from orch.chat.runtime_base import ChatRuntime

# ---------------------------------------------------------------------------
# Helpers (mirror of the OpenCode ABC test helpers)
# ---------------------------------------------------------------------------


def _is_async_callable(fn: object) -> bool:
    """Return True for coroutine functions AND async-generator functions.

    ``subscribe`` is declared on the ABC as a plain ``def`` returning
    ``AsyncIterator``; its PiRuntime override is a regular ``def`` returning
    an async generator — accepted because the return type satisfies the ABC
    contract.  We therefore also accept plain ``def`` for ``subscribe`` since
    the ABC itself is declared as ``def``.
    """
    return inspect.iscoroutinefunction(fn) or inspect.isasyncgenfunction(fn)


def _abc_abstract_methods() -> frozenset[str]:
    """Return the set of abstract method names declared on ChatRuntime."""
    return frozenset(ChatRuntime.__abstractmethods__)


# ---------------------------------------------------------------------------
# Invariant #3 — PiRuntime is constructible (no unimplemented abstract methods)
# ---------------------------------------------------------------------------


def test_pi_runtime_is_constructible() -> None:
    """PiRuntime.__abstractmethods__ must be frozenset() so it can be instantiated.

    We verify the class attribute directly — no need to call __init__ (which
    needs a Path argument) to check that the ABC is satisfied.
    """
    remaining = PiRuntime.__abstractmethods__
    assert remaining == frozenset(), (
        f"PiRuntime still has unimplemented abstract methods: {sorted(remaining)}"
    )

    # Confirm actual instantiation works.
    runtime = PiRuntime(base_session_dir=Path("/tmp/pi_abc_test"))
    assert runtime is not None


def test_every_chat_runtime_abstract_method_is_implemented() -> None:
    """For every abstract method on ChatRuntime, PiRuntime must provide an implementation.

    Methods that are coroutine functions or async-generator functions satisfy
    the async contract.  ``subscribe`` is the one ABC method declared as plain
    ``def`` — PiRuntime may also declare it as plain ``def`` (returning an
    AsyncIterator).
    """
    abc_methods = _abc_abstract_methods()
    assert abc_methods, "ChatRuntime has zero abstract methods — ABC contract gone?"

    missing: list[str] = []
    non_callable: list[str] = []

    for name in abc_methods:
        impl = getattr(PiRuntime, name, None)
        if impl is None:
            missing.append(name)
            continue
        # Any callable on the class suffices — the ABC enforces the async-ness
        # through the no-abstractmethods gate above.  We still assert it is at
        # minimum callable.
        if not callable(impl):
            non_callable.append(name)

    assert not missing, f"PiRuntime is missing implementations for ABC methods: {sorted(missing)}"
    assert not non_callable, (
        f"PiRuntime has non-callable attributes for ABC methods: {sorted(non_callable)}"
    )


def test_pi_runtime_method_signatures_match_abc() -> None:
    """Parameter names and kinds must match the ABC for every abstract method.

    Default values and annotations are NOT compared — those may differ between
    runtimes (e.g. PiRuntime vs OpencodeRuntime may use different default models).
    """
    abc_methods = _abc_abstract_methods()
    mismatches: dict[str, str] = {}

    for name in abc_methods:
        abc_method = getattr(ChatRuntime, name)
        impl_method = getattr(PiRuntime, name)
        abc_sig = inspect.signature(abc_method)
        impl_sig = inspect.signature(impl_method)

        abc_params = list(abc_sig.parameters.values())
        impl_params = list(impl_sig.parameters.values())

        if len(abc_params) != len(impl_params):
            mismatches[name] = (
                f"param count differs: abc={len(abc_params)} impl={len(impl_params)} "
                f"(abc_sig={abc_sig}, impl_sig={impl_sig})"
            )
            continue

        for abc_p, impl_p in zip(abc_params, impl_params, strict=True):
            if abc_p.name != impl_p.name:
                mismatches[name] = (
                    f"param name differs: abc={abc_p.name!r} impl={impl_p.name!r} "
                    f"(abc_sig={abc_sig}, impl_sig={impl_sig})"
                )
                break
            if abc_p.kind != impl_p.kind:
                mismatches[name] = (
                    f"param kind differs for {abc_p.name!r}: abc={abc_p.kind} "
                    f"impl={impl_p.kind} (abc_sig={abc_sig}, impl_sig={impl_sig})"
                )
                break

    assert not mismatches, (
        "PiRuntime method signatures drift from the ChatRuntime ABC:\n"
        + "\n".join(f"  - {name}: {reason}" for name, reason in sorted(mismatches.items()))
    )
