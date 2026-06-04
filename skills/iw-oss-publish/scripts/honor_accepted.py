"""Read .iw/oss-accepted.yaml; downgrade matching SARIF results from error to warning."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import yaml


def compute_finding_hash(check_id: str, summary: str, evidence: dict | None) -> str:
    """Mirror dashboard/services/oss_accepted.py:compute_finding_hash."""
    h = hashlib.sha256()
    h.update(check_id.encode())
    h.update(b"\x00")
    h.update(summary.encode())
    h.update(b"\x00")
    if evidence is not None:
        h.update(json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode())
    return h.hexdigest()[:16]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sarif", required=True, type=Path)
    parser.add_argument("--accepted", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    sarif = json.loads(args.sarif.read_text())
    accepted = (
        yaml.safe_load(args.accepted.read_text()) if args.accepted.exists() else {"accepted": []}
    )
    accepted_keys = {
        (e["check_id"], e["finding_hash"])
        for e in (accepted or {}).get("accepted", [])
    }
    accepted_reasons = {
        (e["check_id"], e["finding_hash"]): e.get("reason", "")
        for e in (accepted or {}).get("accepted", [])
    }

    downgraded = 0
    for run in sarif.get("runs", []):
        for result in run.get("results", []):
            check_id = result.get("ruleId")
            summary = result.get("message", {}).get("text", "")
            evidence = result.get("properties", {}).get("evidence")
            h = compute_finding_hash(check_id, summary, evidence)
            if (check_id, h) in accepted_keys:
                result["level"] = "warning"
                reason = accepted_reasons[(check_id, h)]
                result["message"]["text"] = f"{summary}\n\n[ACCEPTED RISK]: {reason}"
                downgraded += 1

    args.out.write_text(json.dumps(sarif, indent=2))
    print(f"Downgraded {downgraded} accepted finding(s).", file=sys.stderr)  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
