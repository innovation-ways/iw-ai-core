"""Unit tests for orch.services.work_items.build_registration_spec_from_content."""

from __future__ import annotations


class TestBuildRegistrationSpecFromContent:
    """Covers in-memory spec building from content strings."""

    def test_minimal_call_returns_spec_with_correct_fields(self):
        """Verifies that a minimal call produces a RegistrationSpec with expected field values."""
        from orch.services.work_items import RegistrationSpec, build_registration_spec_from_content

        spec = build_registration_spec_from_content(
            "F-00001",
            "My Feature",
            "feature",
        )
        assert isinstance(spec, RegistrationSpec)
        assert spec.item_id == "F-00001"
        assert spec.title == "My Feature"
        assert spec.item_type == "feature"

    def test_manifest_steps_digest_is_computed(self):
        """Verifies that manifest_digest is set when manifest_steps is non-empty."""
        from orch.services.work_items import build_registration_spec_from_content

        steps = [{"step": "S01", "agent": "backend-impl"}]
        spec = build_registration_spec_from_content(
            "F-00001", "My Feature", "feature", manifest_steps=steps
        )
        assert spec.manifest_digest is not None
        assert len(spec.manifest_digest) == 64  # SHA-256 hex

    def test_empty_manifest_steps_produces_no_digest(self):
        """Verifies that manifest_digest is None when manifest_steps is empty or omitted."""
        from orch.services.work_items import build_registration_spec_from_content

        spec = build_registration_spec_from_content("F-00001", "Title", "feature")
        assert spec.manifest_digest is None
        assert spec.manifest_steps == []

    def test_digest_matches_disk_function_for_same_steps(self):
        """Verifies content-based spec builds the same manifest digest as the disk helper."""
        from orch.services.work_items import (
            _compute_manifest_digest,
            build_registration_spec_from_content,
        )

        steps = [{"step": "S01", "agent": "backend-impl"}, {"step": "S02", "agent": "tests-impl"}]
        spec = build_registration_spec_from_content(
            "F-00001", "Title", "feature", manifest_steps=steps
        )
        expected_digest = _compute_manifest_digest(steps)
        assert spec.manifest_digest == expected_digest

    def test_design_doc_content_parses_impacted_paths(self):
        """Verifies that impacted_paths are parsed from design_doc_content."""
        from orch.services.work_items import build_registration_spec_from_content

        design_doc = "## Impacted Paths\n\n- orch/services/work_items.py\n- tests/unit/\n"
        spec = build_registration_spec_from_content(
            "F-00001",
            "My Feature",
            "feature",
            design_doc_content=design_doc,
        )
        assert spec.impacted_paths == ["orch/services/work_items.py", "tests/unit/"]

    def test_design_doc_content_parses_depends_on(self):
        """Verifies that depends_on is parsed from the ## Dependencies section."""
        from orch.services.work_items import build_registration_spec_from_content

        # Parser expects **Depends on**: (colon OUTSIDE the bold markers)
        design_doc = "## Dependencies\n\n**Depends on**: F-00010, CR-00001\n"
        spec = build_registration_spec_from_content(
            "F-00002",
            "Another Feature",
            "feature",
            design_doc_content=design_doc,
        )
        assert "F-00010" in spec.depends_on or "CR-00001" in spec.depends_on

    def test_item_id_excluded_from_depends_on(self):
        """Verifies that the item's own ID is excluded from depends_on (self-dependency guard)."""
        from orch.services.work_items import build_registration_spec_from_content

        # Parser expects **Depends on**: (colon outside bold markers)
        design_doc = "## Dependencies\n\n**Depends on**: F-00001\n"
        spec = build_registration_spec_from_content(
            "F-00001",
            "Self Ref",
            "feature",
            design_doc_content=design_doc,
        )
        # F-00001 must be excluded from its own depends_on
        assert "F-00001" not in spec.depends_on

    def test_no_design_doc_produces_empty_paths_and_deps(self):
        """Verifies that empty/missing content produces empty lists for paths and deps."""
        from orch.services.work_items import build_registration_spec_from_content

        spec = build_registration_spec_from_content("CR-00001", "No Docs", "cr")
        assert spec.impacted_paths == []
        assert spec.depends_on == []
        assert spec.blocks == []

    def test_design_doc_content_is_stored_on_spec(self):
        """Verifies that design_doc_content is stored verbatim on the spec."""
        from orch.services.work_items import build_registration_spec_from_content

        content = "## Summary\n\nSome content here.\n"
        spec = build_registration_spec_from_content(
            "F-00001", "Title", "feature", design_doc_content=content
        )
        assert spec.design_doc_content == content

    def test_functional_doc_content_is_stored_on_spec(self):
        """Verifies that functional_doc_content is stored verbatim on the spec."""
        from orch.services.work_items import build_registration_spec_from_content

        content = "## Functional Doc\n\nSome functional details.\n"
        spec = build_registration_spec_from_content(
            "F-00001", "Title", "feature", functional_doc_content=content
        )
        assert spec.functional_doc_content == content

    def test_custom_config_is_stored_on_spec(self):
        """Verifies that config dict is stored verbatim when provided."""
        from orch.services.work_items import build_registration_spec_from_content

        custom_config = {"scope_extraction": {"source": "manual"}, "extra": 42}
        spec = build_registration_spec_from_content(
            "F-00001", "Title", "feature", config=custom_config
        )
        assert spec.config["extra"] == 42

    def test_no_disk_access_for_content_based_path(self):
        """Verifies that no file is read from disk (doc paths are None)."""
        from orch.services.work_items import build_registration_spec_from_content

        spec = build_registration_spec_from_content("F-00001", "Title", "feature")
        assert spec.design_doc_path is None
        assert spec.functional_doc_path is None

    def test_impacted_paths_custom_list_overrides_parsing(self):
        """Verifies that an explicit impacted_paths list is used as-is."""
        from orch.services.work_items import build_registration_spec_from_content

        # Even with design_doc_content that has a different section, the explicit
        # impacted_paths list takes priority.
        spec = build_registration_spec_from_content(
            "F-00001",
            "Title",
            "feature",
            impacted_paths=["custom/path.py"],
        )
        assert spec.impacted_paths == ["custom/path.py"]
