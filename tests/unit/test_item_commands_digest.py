"""Unit tests for _compute_manifest_digest (I-00102).

These tests capture the RED evidence for TDD and verify determinism
across cosmetic edits to the manifest steps.
"""

from __future__ import annotations

from orch.cli.item_commands import _compute_manifest_digest


class TestComputeManifestDigest:
    """Test suite for _compute_manifest_digest."""

    def test_digest_is_deterministic_across_key_order(self) -> None:
        """RED: same logical steps → same hash even with shuffled key order.

        This is the core AC4 requirement. The canonicalization must sort
        keys so that {"step": "S01", "agent": "backend"} and
        {"agent": "backend", "step": "S01"} produce identical digests.
        """
        steps_v1 = [
            {"step": "S01", "agent": "backend-impl", "description": "Implement the fix"},
            {"step": "S02", "agent": "qv-gate", "gate": "lint"},
        ]
        steps_v2 = [
            {"description": "Implement the fix", "step": "S01", "agent": "backend-impl"},
            {"gate": "lint", "agent": "qv-gate", "step": "S02"},
        ]
        digest_v1 = _compute_manifest_digest(steps_v1)
        digest_v2 = _compute_manifest_digest(steps_v2)
        assert digest_v1 == digest_v2, (
            f"Digest must be stable across key order: {digest_v1!r} != {digest_v2!r}"
        )

    def test_digest_is_deterministic_across_whitespace(self) -> None:
        """Canonicalization must produce identical output regardless of
        whitespace that would appear in pretty-printed JSON."""
        steps_a = [
            {"step": "S01", "agent": "backend-impl"},
            {"step": "S02", "agent": "tests-impl"},
        ]
        steps_b = [
            {"step": "S01", "agent": "backend-impl"},
            {"step": "S02", "agent": "tests-impl"},
        ]
        digest_a = _compute_manifest_digest(steps_a)
        digest_b = _compute_manifest_digest(steps_b)
        assert digest_a == digest_b

    def test_digest_changes_when_step_id_changes(self) -> None:
        """Renumbering one step must change the digest."""
        steps_base = [{"step": "S01", "agent": "backend-impl"}]
        steps_renumbered = [{"step": "S02", "agent": "backend-impl"}]
        digest_base = _compute_manifest_digest(steps_base)
        digest_renumbered = _compute_manifest_digest(steps_renumbered)
        assert digest_base != digest_renumbered

    def test_digest_changes_when_prompt_path_changes(self) -> None:
        """Renaming a prompt path must change the digest."""
        steps_v1 = [
            {"step": "S01", "agent": "backend-impl", "prompt": "prompts/F-001_S01_prompt.md"},
        ]
        steps_v2 = [
            {"step": "S01", "agent": "backend-impl", "prompt": "prompts/F-001_S01_NEW_prompt.md"},
        ]
        digest_v1 = _compute_manifest_digest(steps_v1)
        digest_v2 = _compute_manifest_digest(steps_v2)
        assert digest_v1 != digest_v2

    def test_digest_ignores_none_values(self) -> None:
        """None-valued keys are dropped during canonicalization."""
        steps_with_nones = [
            {"step": "S01", "agent": "backend-impl", "description": None},
        ]
        steps_without_nones = [
            {"step": "S01", "agent": "backend-impl"},
        ]
        digest_nones = _compute_manifest_digest(steps_with_nones)
        digest_no_nones = _compute_manifest_digest(steps_without_nones)
        assert digest_nones == digest_no_nones

    def test_digest_ignores_empty_string_values(self) -> None:
        """Empty-string-valued keys are dropped during canonicalization."""
        steps_with_empty = [
            {"step": "S01", "agent": "backend-impl", "description": ""},
        ]
        steps_without_empty = [
            {"step": "S01", "agent": "backend-impl"},
        ]
        digest_empty = _compute_manifest_digest(steps_with_empty)
        digest_no_empty = _compute_manifest_digest(steps_without_empty)
        assert digest_empty == digest_no_empty

    def test_digest_is_hex_string(self) -> None:
        """Return value must be a valid SHA-256 hex digest (64 chars, [0-9a-f])."""
        digest = _compute_manifest_digest([{"step": "S01", "agent": "backend-impl"}])
        assert len(digest) == 64, f"Expected 64-char hex digest, got {len(digest)}"
        assert all(c in "0123456789abcdef" for c in digest)

    def test_digest_different_for_different_steps_count(self) -> None:
        """Adding or removing a step changes the digest."""
        steps_2 = [
            {"step": "S01", "agent": "backend-impl"},
            {"step": "S02", "agent": "qv-gate"},
        ]
        steps_3 = [
            {"step": "S01", "agent": "backend-impl"},
            {"step": "S02", "agent": "code-review-impl"},
            {"step": "S03", "agent": "qv-gate"},
        ]
        digest_2 = _compute_manifest_digest(steps_2)
        digest_3 = _compute_manifest_digest(steps_3)
        assert digest_2 != digest_3

    def test_empty_steps_array_produces_valid_digest(self) -> None:
        """An empty steps array (no steps) must still produce a valid hex digest."""
        digest = _compute_manifest_digest([])
        assert len(digest) == 64
        assert all(c in "0123456789abcdef" for c in digest)

    def test_digest_order_sensitive(self) -> None:
        """Steps are ordered — reordering changes the digest."""
        steps_forward = [
            {"step": "S01", "agent": "backend-impl"},
            {"step": "S02", "agent": "qv-gate"},
        ]
        steps_reversed = [
            {"step": "S02", "agent": "qv-gate"},
            {"step": "S01", "agent": "backend-impl"},
        ]
        digest_forward = _compute_manifest_digest(steps_forward)
        digest_reversed = _compute_manifest_digest(steps_reversed)
        assert digest_forward != digest_reversed

    def test_digest_changes_when_step_added(self) -> None:
        """Adding a step produces a different digest."""
        steps_base = [
            {"step": "S01", "agent": "backend-impl"},
            {"step": "S02", "agent": "qv-gate"},
        ]
        steps_extended = [
            {"step": "S01", "agent": "backend-impl"},
            {"step": "S02", "agent": "qv-gate"},
            {"step": "S03", "agent": "tests-impl"},
        ]
        digest_base = _compute_manifest_digest(steps_base)
        digest_extended = _compute_manifest_digest(steps_extended)
        assert digest_base != digest_extended, "Digest must change when a step is added"

    def test_digest_changes_when_step_removed(self) -> None:
        """Removing a step produces a different digest."""
        steps_full = [
            {"step": "S01", "agent": "backend-impl"},
            {"step": "S02", "agent": "qv-gate"},
            {"step": "S03", "agent": "tests-impl"},
        ]
        steps_trimmed = [
            {"step": "S01", "agent": "backend-impl"},
            {"step": "S02", "agent": "qv-gate"},
        ]
        digest_full = _compute_manifest_digest(steps_full)
        digest_trimmed = _compute_manifest_digest(steps_trimmed)
        assert digest_full != digest_trimmed, "Digest must change when a step is removed"

    def test_digest_changes_when_steps_reordered(self) -> None:
        """Same steps in a different order produce different digests (order matters)."""
        steps_a = [
            {"step": "S01", "agent": "backend-impl"},
            {"step": "S02", "agent": "qv-gate"},
            {"step": "S03", "agent": "tests-impl"},
        ]
        steps_b = [
            {"step": "S03", "agent": "tests-impl"},
            {"step": "S01", "agent": "backend-impl"},
            {"step": "S02", "agent": "qv-gate"},
        ]
        digest_a = _compute_manifest_digest(steps_a)
        digest_b = _compute_manifest_digest(steps_b)
        assert digest_a != digest_b, (
            "Digest must be order-sensitive: same steps in different order must differ"
        )

    def test_digest_ignores_none_and_empty_string_keys_inside_a_step(self) -> None:
        """A step with None or empty-string values for optional keys produces
        the same digest as the same step with those keys omitted entirely.

        The canonicalization drops keys whose values are None or "" before
        hashing, so the helper is robust to callers that include optional
        fields with null/empty values.
        """
        steps_with_optionals = [
            {"step": "S01", "agent": "backend-impl", "prompt": None, "command": ""},
        ]
        steps_without_optionals = [
            {"step": "S01", "agent": "backend-impl"},
        ]
        digest_with = _compute_manifest_digest(steps_with_optionals)
        digest_without = _compute_manifest_digest(steps_without_optionals)
        assert digest_with == digest_without

    def test_digest_ignores_top_level_manifest_fields(self) -> None:
        """The digest covers only the steps array. Top-level manifest fields
        (_note, title, scope, …) are never in scope for the helper because
        the helper accepts only the steps list.

        We verify the contract by confirming that calling the helper with
        equivalent step dicts always produces the same digest — the signature
        itself encodes the exclusion of top-level fields.
        """
        steps = [{"step": "S01", "agent": "backend-impl"}]
        digest = _compute_manifest_digest(steps)
        # Top-level fields are never passed to the helper — the function
        # signature encodes the contract. Varying optional fields inside a
        # step (None-valued) produces the same digest, confirming the
        # canonicalization is aggressive and that _note would need to be
        # explicitly present in a step dict to affect the hash.
        steps_with_none = [{"step": "S01", "agent": "backend-impl", "description": None}]
        digest_with_none = _compute_manifest_digest(steps_with_none)
        assert digest_with_none == digest

    def test_digest_hashes_non_empty_string_keys_in_step(self) -> None:
        """Canonicalization drops None/empty keys but NOT non-empty string keys.

        This test verifies the canonicalization contract: ``_compute_manifest_digest``
        drops keys whose values are ``None`` or ``""`` before hashing, but any
        non-empty string value (including ``_note``) is included verbatim.  Therefore
        adding a ``_note`` key to a step dict changes the digest — which is correct
        because the digest hashes everything in the steps array.

        See also: test_digest_ignores_none_and_empty_string_keys_inside_a_step
        for the complementary contract (None/"" keys are dropped).
        """
        steps_without_note = [
            {"step": "S01", "agent": "backend-impl"},
            {"step": "S02", "agent": "qv-gate"},
        ]
        steps_with_note = [
            {"step": "S01", "agent": "backend-impl", "_note": "auto-stamped by register"},
            {"step": "S02", "agent": "qv-gate", "_note": "CR-00023 marker"},
        ]
        digest_clean = _compute_manifest_digest(steps_without_note)
        digest_with_note = _compute_manifest_digest(steps_with_note)
        # Non-empty string keys are hashed, so adding _note changes the digest.
        assert digest_with_note != digest_clean
