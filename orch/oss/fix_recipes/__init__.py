from __future__ import annotations

from .base import FixPreview as FixPreview
from .base import FixRecipe as FixRecipe

__all__ = ["FixPreview", "FixRecipe", "register", "get_recipe", "list_recipes"]

_REGISTRY: dict[str, FixRecipe] = {}


def register(recipe: FixRecipe) -> FixRecipe:
    if recipe.check_id in _REGISTRY:
        raise ValueError(f"Duplicate recipe for {recipe.check_id}")
    _REGISTRY[recipe.check_id] = recipe
    return recipe


def get_recipe(check_id: str) -> FixRecipe | None:
    return _REGISTRY.get(check_id)


def list_recipes() -> list[FixRecipe]:
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
