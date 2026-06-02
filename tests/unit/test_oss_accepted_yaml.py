"""CR-00022 AC6: oss_accepted.yaml read/write/hash tests."""

from __future__ import annotations

from pathlib import Path


class TestComputeFindingHash:
    """Tests for ComputeFindingHash scenarios."""

    def test_hash_is_deterministic(self) -> None:
        """Verifies that hash is deterministic."""
        from dashboard.services.oss_accepted import compute_finding_hash

        h1 = compute_finding_hash("OSS-CH-01", "Missing README", {"path": "README.md"})
        h2 = compute_finding_hash("OSS-CH-01", "Missing README", {"path": "README.md"})
        assert h1 == h2

    def test_hash_differs_when_summary_differs(self) -> None:
        """Verifies that hash differs when summary differs."""
        from dashboard.services.oss_accepted import compute_finding_hash

        h1 = compute_finding_hash("OSS-CH-01", "Missing README", None)
        h2 = compute_finding_hash("OSS-CH-01", "Missing README!", None)
        assert h1 != h2

    def test_hash_differs_when_evidence_dict_differs(self) -> None:
        """Verifies that hash differs when evidence dict differs."""
        from dashboard.services.oss_accepted import compute_finding_hash

        h1 = compute_finding_hash("OSS-CH-01", "Missing README", {"path": "README.md"})
        h2 = compute_finding_hash("OSS-CH-01", "Missing README", {"path": "README.txt"})
        assert h1 != h2

    def test_hash_order_independent_for_dict(self) -> None:
        """Verifies that hash order independent for dict."""
        from dashboard.services.oss_accepted import compute_finding_hash

        h1 = compute_finding_hash("OSS-CH-01", "Missing", {"a": 1, "b": 2})
        h2 = compute_finding_hash("OSS-CH-01", "Missing", {"b": 2, "a": 1})
        assert h1 == h2

    def test_hash_is_16_hex_chars(self) -> None:
        """Verifies that hash is 16 hex chars."""
        from dashboard.services.oss_accepted import compute_finding_hash

        h = compute_finding_hash("OSS-CH-01", "test", None)
        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h)


class TestAppendAccepted:
    """Tests for AppendAccepted scenarios."""

    def test_append_accepted_creates_file(self, tmp_path: Path) -> None:
        """Verifies that append accepted creates file."""
        from dashboard.services.oss_accepted import AcceptedEntry, append_accepted, load_accepted

        entry = AcceptedEntry(
            check_id="OSS-CH-01",
            finding_hash="abcd1234efgh5678",
            reason="Accepted risk",
            accepted_at="2026-04-26T00:00:00Z",
            accepted_by="test-user",
        )

        append_accepted(tmp_path, entry)

        accepted_file = load_accepted(tmp_path)
        assert len(accepted_file.accepted) == 1
        assert accepted_file.accepted[0].check_id == "OSS-CH-01"

    def test_append_accepted_is_idempotent(self, tmp_path: Path) -> None:
        """Verifies that append accepted is idempotent."""
        from dashboard.services.oss_accepted import AcceptedEntry, append_accepted, load_accepted

        entry = AcceptedEntry(
            check_id="OSS-CH-01",
            finding_hash="abcd1234efgh5678",
            reason="Accepted risk",
            accepted_at="2026-04-26T00:00:00Z",
            accepted_by="test-user",
        )

        append_accepted(tmp_path, entry)
        append_accepted(tmp_path, entry)

        accepted_file = load_accepted(tmp_path)
        assert len(accepted_file.accepted) == 1

    def test_append_accepted_same_hash_idempotent(self, tmp_path: Path) -> None:
        """Verifies that append accepted same hash idempotent."""
        from dashboard.services.oss_accepted import AcceptedEntry, append_accepted, load_accepted

        entry1 = AcceptedEntry(
            check_id="OSS-CH-01",
            finding_hash="samehash123456",
            reason="First reason",
            accepted_at="2026-04-26T00:00:00Z",
            accepted_by="test-user",
        )
        entry2 = AcceptedEntry(
            check_id="OSS-CH-01",
            finding_hash="samehash123456",
            reason="Second reason",
            accepted_at="2026-04-27T00:00:00Z",
            accepted_by="test-user",
        )

        append_accepted(tmp_path, entry1)
        append_accepted(tmp_path, entry2)

        accepted_file = load_accepted(tmp_path)
        assert len(accepted_file.accepted) == 1


class TestLoadAccepted:
    """Tests for LoadAccepted scenarios."""

    def test_load_accepted_missing_file_returns_empty(self, tmp_path: Path) -> None:
        """Verifies that load accepted missing file returns empty."""
        from dashboard.services.oss_accepted import load_accepted

        result = load_accepted(tmp_path)
        assert result.accepted == []

    def test_load_accepted_parses_existing_file(self, tmp_path: Path) -> None:
        """Verifies that load accepted parses existing file."""
        from dashboard.services.oss_accepted import AcceptedEntry, append_accepted, load_accepted

        entry = AcceptedEntry(
            check_id="OSS-CH-01",
            finding_hash="testhash1234567",
            reason="Test reason",
            accepted_at="2026-04-26T00:00:00Z",
            accepted_by="test-user",
        )
        append_accepted(tmp_path, entry)

        result = load_accepted(tmp_path)
        assert len(result.accepted) == 1
        assert result.accepted[0].check_id == "OSS-CH-01"
        assert result.accepted[0].finding_hash == "testhash1234567"


class TestIsAccepted:
    """Tests for IsAccepted scenarios."""

    def test_is_accepted_matches_exact_check_id_and_hash(self, tmp_path: Path) -> None:
        """Verifies that is accepted matches exact check id and hash."""
        from dashboard.services.oss_accepted import (
            AcceptedEntry,
            append_accepted,
            is_accepted,
            load_accepted,
        )

        entry = AcceptedEntry(
            check_id="OSS-CH-01",
            finding_hash="hash1234567890ab",
            reason="Test",
            accepted_at="2026-04-26T00:00:00Z",
            accepted_by="test-user",
        )
        append_accepted(tmp_path, entry)

        accepted_file = load_accepted(tmp_path)
        result = is_accepted(accepted_file, "OSS-CH-01", "hash1234567890ab")
        assert result is not None
        assert result.check_id == "OSS-CH-01"

    def test_is_accepted_returns_none_for_wrong_hash(self, tmp_path: Path) -> None:
        """Verifies that is accepted returns none for wrong hash."""
        from dashboard.services.oss_accepted import (
            AcceptedEntry,
            append_accepted,
            is_accepted,
            load_accepted,
        )

        entry = AcceptedEntry(
            check_id="OSS-CH-01",
            finding_hash="hash1234567890ab",
            reason="Test",
            accepted_at="2026-04-26T00:00:00Z",
            accepted_by="test-user",
        )
        append_accepted(tmp_path, entry)

        accepted_file = load_accepted(tmp_path)
        result = is_accepted(accepted_file, "OSS-CH-01", "wrong_hash_wrong")
        assert result is None

    def test_is_accepted_returns_none_for_wrong_check_id(self, tmp_path: Path) -> None:
        """Verifies that is accepted returns none for wrong check id."""
        from dashboard.services.oss_accepted import (
            AcceptedEntry,
            append_accepted,
            is_accepted,
            load_accepted,
        )

        entry = AcceptedEntry(
            check_id="OSS-CH-01",
            finding_hash="hash1234567890ab",
            reason="Test",
            accepted_at="2026-04-26T00:00:00Z",
            accepted_by="test-user",
        )
        append_accepted(tmp_path, entry)

        accepted_file = load_accepted(tmp_path)
        result = is_accepted(accepted_file, "OSS-CH-99", "hash1234567890ab")
        assert result is None
