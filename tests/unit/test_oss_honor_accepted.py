"""CR-00022 AC6: honor_accepted compute_finding_hash matches oss_accepted.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


def _load_skill_honor_accepted():
    """Load honor_accepted.compute_finding_hash via importlib."""
    import importlib.util

    skill_script = (
        Path(__file__).parents[2] / "skills" / "iw-oss-publish" / "scripts" / "honor_accepted.py"
    )
    if not skill_script.exists():
        return None

    spec = importlib.util.spec_from_file_location("honor_accepted_skill", skill_script)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestHonorAcceptedComputeHash:
    def test_compute_finding_hash_deterministic(self) -> None:
        from dashboard.services.oss_accepted import compute_finding_hash as dashboard_hash

        skill_module = _load_skill_honor_accepted()
        if skill_module is None:
            pytest.skip("honor_accepted.py not found in skills")

        check_id = "OSS-CH-01"
        summary = "Missing README file"
        evidence = {"path": "README.md"}

        dashboard_h = dashboard_hash(check_id, summary, evidence)
        skill_h = skill_module.compute_finding_hash(check_id, summary, evidence)

        assert dashboard_h == skill_h, (
            "compute_finding_hash mismatch between dashboard/services/oss_accepted.py "
            "and skills/iw-oss-publish/scripts/honor_accepted.py"
        )

    def test_compute_finding_hash_evidence_order_independent(self) -> None:
        from dashboard.services.oss_accepted import compute_finding_hash as dashboard_hash

        skill_module = _load_skill_honor_accepted()
        if skill_module is None:
            pytest.skip("honor_accepted.py not found in skills")

        check_id = "OSS-CH-01"
        summary = "Test finding"

        ev1 = {"a": 1, "b": 2}
        ev2 = {"b": 2, "a": 1}

        assert dashboard_hash(check_id, summary, ev1) == dashboard_hash(check_id, summary, ev2)
        assert skill_module.compute_finding_hash(
            check_id, summary, ev1
        ) == skill_module.compute_finding_hash(check_id, summary, ev2)

    def test_compute_finding_hash_16_hex_chars(self) -> None:
        from dashboard.services.oss_accepted import compute_finding_hash

        h = compute_finding_hash("OSS-CH-01", "test", None)
        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h)


class TestHonorAcceptedCli:
    def test_honor_accepted_downgrades_matching(self, tmp_path: Path) -> None:
        skill_script = (
            Path(__file__).parents[3]
            / "skills"
            / "iw-oss-publish"
            / "scripts"
            / "honor_accepted.py"
        )
        if not skill_script.exists():
            pytest.skip("honor_accepted.py not found in skills")

        accepted_file = tmp_path / "accepted.yaml"
        accepted_file.write_text(
            "accepted:\n"
            "  - check_id: OSS-CH-01\n"
            "    finding_hash: abcd1234efgh5678\n"
            "    reason: Accepted risk\n"
            "    accepted_at: '2026-04-26T00:00:00Z'\n"
            "    accepted_by: test\n"
        )

        sarif_file = tmp_path / "input.sarif"
        sarif_file.write_text(
            json.dumps(
                {
                    "runs": [
                        {
                            "results": [
                                {
                                    "ruleId": "OSS-CH-01",
                                    "message": {"text": "Missing README"},
                                    "level": "error",
                                    "properties": {"evidence": {"path": "README.md"}},
                                }
                            ]
                        }
                    ]
                }
            )
        )

        from dashboard.services.oss_accepted import compute_finding_hash

        finding_hash = compute_finding_hash("OSS-CH-01", "Missing README", {"path": "README.md"})

        accepted_with_hash = tmp_path / "accepted_with_hash.yaml"
        accepted_with_hash.write_text(
            f"accepted:\n"
            f"  - check_id: OSS-CH-01\n"
            f"    finding_hash: {finding_hash}\n"
            f"    reason: Accepted risk\n"
            f"    accepted_at: '2026-04-26T00:00:00Z'\n"
            f"    accepted_by: test\n"
        )

        out_file = tmp_path / "output.sarif"

        result = subprocess.run(
            [
                sys.executable,
                str(skill_script),
                "--sarif",
                str(sarif_file),
                "--accepted",
                str(accepted_with_hash),
                "--out",
                str(out_file),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"honor_accepted failed: {result.stderr}"

        output = json.loads(out_file.read_text())
        result_entry = output["runs"][0]["results"][0]
        assert result_entry["level"] == "warning"
        assert "ACCEPTED RISK" in result_entry["message"]["text"]

    def test_honor_accepted_nonmatching_unchanged(self, tmp_path: Path) -> None:
        skill_script = (
            Path(__file__).parents[3]
            / "skills"
            / "iw-oss-publish"
            / "scripts"
            / "honor_accepted.py"
        )
        if not skill_script.exists():
            pytest.skip("honor_accepted.py not found in skills")

        accepted_file = tmp_path / "accepted.yaml"
        accepted_file.write_text(
            "accepted:\n"
            "  - check_id: OSS-CH-01\n"
            "    finding_hash: abcd1234efgh5678\n"
            "    reason: Accepted\n"
            "    accepted_at: '2026-04-26T00:00:00Z'\n"
            "    accepted_by: test\n"
        )

        sarif_file = tmp_path / "input.sarif"
        sarif_file.write_text(
            json.dumps(
                {
                    "runs": [
                        {
                            "results": [
                                {
                                    "ruleId": "OSS-CH-01",
                                    "message": {"text": "Missing README"},
                                    "level": "error",
                                }
                            ]
                        }
                    ]
                }
            )
        )

        out_file = tmp_path / "output.sarif"

        result = subprocess.run(
            [
                sys.executable,
                str(skill_script),
                "--sarif",
                str(sarif_file),
                "--accepted",
                str(accepted_file),
                "--out",
                str(out_file),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0

        output = json.loads(out_file.read_text())
        result_entry = output["runs"][0]["results"][0]
        assert result_entry["level"] == "error"
