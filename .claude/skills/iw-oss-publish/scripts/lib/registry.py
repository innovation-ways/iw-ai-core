"""Check registration and execution."""

from __future__ import annotations

import logging
import traceback
from collections.abc import Callable
from dataclasses import dataclass

from .context import Context
from .types import Finding, Severity, Status

logger = logging.getLogger(__name__)

CheckFn = Callable[[Context], Finding | list[Finding] | None]


@dataclass
class RegisteredCheck:
    id_prefix: str  # e.g., "OSS-LIC" — one function may emit multiple findings
    order: int
    fn: CheckFn
    domain: str
    name: str  # function name for logs


_REGISTRY: list[RegisteredCheck] = []


def register(
    id_prefix: str,
    order: int,
    domain: str,
) -> Callable[[CheckFn], CheckFn]:
    """Decorator to register a check function.

    One function can emit multiple Findings (one per sub-check) by returning a list.
    """

    def decorator(fn: CheckFn) -> CheckFn:
        _REGISTRY.append(
            RegisteredCheck(
                id_prefix=id_prefix, order=order, fn=fn, domain=domain, name=fn.__name__
            )
        )
        return fn

    return decorator


def all_checks() -> list[RegisteredCheck]:
    """Return checks in execution order."""
    return sorted(_REGISTRY, key=lambda c: (c.order, c.id_prefix, c.name))


def run_all(ctx: Context) -> list[Finding]:
    """Execute every registered check, collecting findings.

    A check exception is caught and converted to a FAIL finding with evidence so
    a single broken check cannot abort the whole scan.
    """
    findings: list[Finding] = []
    disabled = set(ctx.config.get("checks", {}).get("disabled", []))
    demoted = ctx.config.get("checks", {}).get("demoted", {})

    for check in all_checks():
        try:
            result = check.fn(ctx)
        except Exception as exc:  # noqa: BLE001 — we want to catch everything
            logger.warning("check %s raised: %s", check.name, exc)
            findings.append(
                Finding(
                    id=f"{check.id_prefix}-ERROR",
                    severity=Severity.INFO,
                    status=Status.SKIP,
                    domain=check.domain,
                    summary=f"Check {check.name} errored out",
                    detail=f"{type(exc).__name__}: {exc}",
                    evidence={"traceback": traceback.format_exc(limit=5)},
                )
            )
            continue

        if result is None:
            continue
        items = result if isinstance(result, list) else [result]
        for f in items:
            # Apply disables and demotions from config.
            if f.id in disabled:
                f.status = Status.SKIP
                f.detail = f"{f.detail}\n\n[override] disabled via config".strip()
            if f.id in demoted:
                try:
                    f.severity = Severity(demoted[f.id])
                except ValueError:
                    pass
            findings.append(f)
    return findings
