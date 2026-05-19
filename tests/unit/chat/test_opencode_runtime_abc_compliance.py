"""Invariant #1: ``OpencodeRuntime`` must satisfy the ``ChatRuntime`` ABC.

For every abstract method declared on :class:`ChatRuntime`, this module
asserts that :class:`OpencodeRuntime`:

* declares a method of the same name,
* the method is async (``inspect.iscoroutinefunction`` is True OR — in
  the special case of ``subscribe`` — is an ``async def`` generator
  function, which CPython exposes as an *async-generator function*),
* the parameter names and keyword-only markers match the ABC's
  signature (preventing silent signature drift).

If a future runtime (Pi, F-B) joins this contract, this file should be
extended (or generalised) to assert the same against PiRuntime — the
ABC is the single source of truth.
"""

from __future__ import annotations

import inspect

from orch.chat.opencode.runtime import OpencodeRuntime
from orch.chat.runtime_base import ChatRuntime


def _is_async_callable(fn: object) -> bool:
    """Return True for coroutine functions AND async-generator functions.

    ``subscribe`` is declared on the ABC as a plain ``def`` returning
    ``AsyncIterator``; its OpencodeRuntime override is an ``async def``
    with a ``yield`` body, which Python types as
    ``isasyncgenfunction`` rather than ``iscoroutinefunction``.
    Both shapes satisfy the contract (caller awaits the iterator's
    ``__anext__``); we accept either here.
    """
    return inspect.iscoroutinefunction(fn) or inspect.isasyncgenfunction(fn)


def _abc_abstract_methods() -> frozenset[str]:
    """Return the ABC's declared abstract method names."""
    return frozenset(ChatRuntime.__abstractmethods__)


def test_opencode_runtime_implements_every_abstract_method() -> None:
    abc_methods = _abc_abstract_methods()
    # Sanity: at design time the ABC has 13 abstract methods.
    assert abc_methods, "ChatRuntime declared zero abstract methods — ABC contract gone?"

    missing: list[str] = []
    not_async: list[str] = []
    for name in abc_methods:
        method = getattr(OpencodeRuntime, name, None)
        if method is None:
            missing.append(name)
            continue
        if not _is_async_callable(method):
            not_async.append(name)
    assert not missing, f"OpencodeRuntime is missing ABC methods: {sorted(missing)}"
    assert not not_async, (
        f"OpencodeRuntime methods are not async (coroutine or async-gen) for: {sorted(not_async)}"
    )


def test_opencode_runtime_method_signatures_match_abc() -> None:
    """Parameter names + kinds must match the ABC for every abstract method.

    We compare ``inspect.signature(abc).parameters`` to
    ``inspect.signature(impl).parameters`` field-by-field.  Names and
    kinds (POSITIONAL_OR_KEYWORD, KEYWORD_ONLY, VAR_POSITIONAL, ...)
    must match exactly so a caller-side keyword-only argument can never
    silently become positional (the source of subtle bugs when adding a
    second runtime).

    Default values and annotations are NOT compared — those may evolve
    independently per runtime (e.g. a Pi runtime might supply a
    different default ``model`` value).
    """
    abc_methods = _abc_abstract_methods()
    mismatches: dict[str, str] = {}

    for name in abc_methods:
        abc_method = getattr(ChatRuntime, name)
        impl_method = getattr(OpencodeRuntime, name)
        abc_sig = inspect.signature(abc_method)
        impl_sig = inspect.signature(impl_method)

        abc_params = list(abc_sig.parameters.values())
        impl_params = list(impl_sig.parameters.values())

        if len(abc_params) != len(impl_params):
            mismatches[name] = (
                f"param count differs: abc={len(abc_params)} impl={len(impl_params)} "
                f"abc_sig={abc_sig} impl_sig={impl_sig}"
            )
            continue

        for abc_p, impl_p in zip(abc_params, impl_params, strict=True):
            if abc_p.name != impl_p.name:
                mismatches[name] = (
                    f"param name differs at position: abc={abc_p.name!r} "
                    f"impl={impl_p.name!r} (abc_sig={abc_sig}, impl_sig={impl_sig})"
                )
                break
            if abc_p.kind != impl_p.kind:
                mismatches[name] = (
                    f"param kind differs for {abc_p.name!r}: abc={abc_p.kind} "
                    f"impl={impl_p.kind} (abc_sig={abc_sig}, impl_sig={impl_sig})"
                )
                break

    assert not mismatches, "OpencodeRuntime method signatures drift from the ABC:\n" + "\n".join(
        f"  - {name}: {reason}" for name, reason in sorted(mismatches.items())
    )


def test_opencode_runtime_is_concrete() -> None:
    """No abstract methods leak through — OpencodeRuntime is instantiable.

    We don't actually construct one (the constructor needs a Path);
    instead we verify the class has no remaining abstract methods, which
    is the gate Python's ABC machinery uses at instantiation time.
    """
    assert OpencodeRuntime.__abstractmethods__ == frozenset(), (
        f"OpencodeRuntime still has unimplemented abstract methods: "
        f"{sorted(OpencodeRuntime.__abstractmethods__)}"
    )
