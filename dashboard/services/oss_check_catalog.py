"""Loader for the per-check editorial copy catalog used in the OSS compliance dashboard."""

from __future__ import annotations

import os
from functools import cache
from pathlib import Path
from typing import Annotated

import yaml
from pydantic import BaseModel, Field

CATALOG_PATH = Path(__file__).parent / "oss_check_catalog.yaml"


class CheckCopy(BaseModel):
    """Editorial copy for a single OSS compliance check, loaded from ``oss_check_catalog.yaml``.

    Attributes:
        what_it_checks: One-sentence description of what the check inspects.
        how_it_tests: Brief explanation of the detection mechanism used.
        risk_if_failing: Business or security risk if the check is not resolved.
        how_to_fix: Actionable remediation guidance shown in the dashboard tooltip.
        references: Optional list of URLs to external standards or documentation.
    """

    what_it_checks: Annotated[str, Field(min_length=1)]
    how_it_tests: Annotated[str, Field(min_length=1)]
    risk_if_failing: Annotated[str, Field(min_length=1)]
    how_to_fix: Annotated[str, Field(min_length=1)]
    references: list[str] = []


def _load_catalog_uncached() -> dict[str, CheckCopy]:
    """Parse ``oss_check_catalog.yaml`` and return a mapping of check_id to CheckCopy.

    Returns:
        Mapping from check identifier string to its validated CheckCopy model.

    Raises:
        ValueError: If the YAML root is not a mapping.
    """
    raw = yaml.safe_load(CATALOG_PATH.read_text())
    if not isinstance(raw, dict):
        raise ValueError(f"Catalog YAML must be a mapping, got {type(raw).__name__}")
    return {check_id: CheckCopy.model_validate(entry) for check_id, entry in raw.items()}


@cache
def _load_catalog_cached() -> dict[str, CheckCopy]:
    return _load_catalog_uncached()


def load_catalog() -> dict[str, CheckCopy]:
    """Load the per-check copy catalog.

    In production (DEBUG=False), loads once and caches.
    In debug mode (DEBUG=True), re-reads on every call so authors can
    iterate on copy without restarting the dashboard.
    """
    if os.getenv("IW_CORE_DEBUG", "false").lower() == "true":
        return _load_catalog_uncached()
    return _load_catalog_cached()


def get_copy(check_id: str) -> CheckCopy | None:
    """Return per-check copy or None if not in catalog (test enforces never None in prod)."""
    return load_catalog().get(check_id)
