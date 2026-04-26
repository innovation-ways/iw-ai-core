"""CR-00022 AC5 idempotency contract — every recipe applying twice is a no-op."""

from __future__ import annotations

from pathlib import Path

import pytest

from orch.oss.fix_recipes import FixRecipe, list_recipes


def _snapshot(root: Path) -> dict[Path, bytes]:
    return {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}


class TestFixRecipesIdempotent:
    @pytest.mark.parametrize("recipe", list_recipes(), ids=lambda r: r.check_id)
    def test_recipe_apply_is_idempotent(self, recipe: FixRecipe, tmp_path: Path) -> None:
        recipe.apply(tmp_path)
        state_after_first = _snapshot(tmp_path)
        recipe.apply(tmp_path)
        state_after_second = _snapshot(tmp_path)
        assert state_after_first == state_after_second, (
            f"{recipe.check_id} not idempotent: disk state changed on second apply"
        )

    @pytest.mark.parametrize("recipe", list_recipes(), ids=lambda r: r.check_id)
    def test_preview_does_not_write(self, recipe: FixRecipe, tmp_path: Path) -> None:
        state_before = _snapshot(tmp_path)
        recipe.preview(tmp_path)
        state_after = _snapshot(tmp_path)
        assert state_before == state_after, f"{recipe.check_id}.preview() wrote to disk"

    def test_list_recipes_returns_non_empty(self) -> None:
        recipes = list_recipes()
        assert len(recipes) > 0

    def test_each_recipe_has_check_id(self) -> None:
        for recipe in list_recipes():
            assert recipe.check_id
            assert len(recipe.check_id) > 0

    def test_each_recipe_has_auto_apply_safe(self) -> None:
        for recipe in list_recipes():
            assert hasattr(recipe, "auto_apply_safe")
            assert isinstance(recipe.auto_apply_safe, bool)

    def test_preview_returns_fixpreview(self) -> None:
        for recipe in list_recipes():
            preview = recipe.preview(Path("/tmp"))
            assert hasattr(preview, "target_files")
            assert hasattr(preview, "full_contents")
            assert hasattr(preview, "diffs")
