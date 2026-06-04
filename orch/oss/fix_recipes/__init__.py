"""Registry and public API for OSS compliance fix recipes."""

from __future__ import annotations

from .base import FixPreview as FixPreview
from .base import FixRecipe as FixRecipe

__all__ = ["FixPreview", "FixRecipe", "register", "get_recipe", "list_recipes"]

_REGISTRY: dict[str, FixRecipe] = {}


def register(recipe: FixRecipe) -> FixRecipe:
    """Register a fix recipe so it can be retrieved by check ID.

    Args:
        recipe: Recipe instance to register; its check_id must be unique.

    Returns:
        The same recipe, allowing use as a decorator or inline call.

    Raises:
        ValueError: If a recipe with the same check_id is already registered.
    """
    if recipe.check_id in _REGISTRY:
        raise ValueError(f"Duplicate recipe for {recipe.check_id}")
    _REGISTRY[recipe.check_id] = recipe
    return recipe


def get_recipe(check_id: str) -> FixRecipe | None:
    """Look up a registered recipe by its OSS check ID.

    Args:
        check_id: The check identifier string (e.g. ``"OSS-LIC-01"``).

    Returns:
        The registered FixRecipe, or None when no recipe matches.
    """
    return _REGISTRY.get(check_id)


def list_recipes() -> list[FixRecipe]:
    """Return all registered fix recipes in insertion order.

    Returns:
        List of every FixRecipe that has been registered via register().
    """
    return list(_REGISTRY.values())


from orch.oss.fix_recipes import (  # noqa: E402, I001
    ci_cd as ci_cd,
    community as community,
    contributor as contributor,
    governance as governance,
    hygiene as hygiene,
    internal_refs as internal_refs,
    license_check as license_check,
    release as release,
    secrets as secrets,
)
