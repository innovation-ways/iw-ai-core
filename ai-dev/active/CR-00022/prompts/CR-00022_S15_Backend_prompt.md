# CR-00022_S15_Backend_prompt

**Work Item**: CR-00022
**Step**: S15
**Agent**: backend-impl (Phase E — CI workflow honors `.iw/oss-accepted.yaml`)

---

## ⛔ Docker / Migrations off-limits

Standard rules. You can edit `.github/workflows/*.yml`; do NOT trigger workflow runs.

## Input Files

- Design (§ "CI integration shape")
- `.github/workflows/compliance-scan.yml` (current)
- `dashboard/services/oss_accepted.py` (S09 — for the file format)
- `skills/iw-oss-publish/scripts/scan.py` (orchestrator that produces SARIF)

## Output Files

- Modified: `.github/workflows/compliance-scan.yml`
- New: `skills/iw-oss-publish/scripts/honor_accepted.py` — script that mutates SARIF to downgrade matched findings (master copy; the existing `install_tools.sh` lives next to it as a precedent)
- New: `docs/IW_AI_Core_OSS_Accepted_Risk.md` — short reference doc explaining the file format and CI behavior
- `ai-dev/active/CR-00022/reports/CR-00022_S15_Backend_report.md`

The CI workflow references the synced location at `.claude/skills/iw-oss-publish/scripts/honor_accepted.py` (matching the existing `install_tools.sh` invocation). After writing the master, run `uv run iw skills sync` so the `.claude/skills/` copy is up to date in this repo. Both locations are tracked (see existing layout for `install_tools.sh`).

## Context

The dashboard "Mark accepted" action writes to `.iw/oss-accepted.yaml` in the user's working tree. CI runs the same scan and must downgrade matched findings from blocking errors to warnings — otherwise the dashboard accept is meaningless for merge gating.

## Requirements

### 1. SARIF post-processor — `honor_accepted.py`

```python
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
    accepted_keys = {(e["check_id"], e["finding_hash"]) for e in (accepted or {}).get("accepted", [])}
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
    print(f"Downgraded {downgraded} accepted finding(s).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Write to `skills/iw-oss-publish/scripts/honor_accepted.py` (master). The CI workflow invokes the synced copy at `.claude/skills/iw-oss-publish/scripts/honor_accepted.py` (mirroring the existing `install_tools.sh` invocation). Run `uv run iw skills sync` after authoring so the `.claude/skills/` copy in this repo is updated.

### 2. Workflow update — `.github/workflows/compliance-scan.yml`

Insert a step **after** scan SARIF is produced and **before** SARIF is uploaded:

```yaml
      - name: Honor .iw/oss-accepted.yaml — downgrade matched findings
        if: hashFiles('.iw/gitleaks-tree.sarif') != '' || hashFiles('.iw/oss-publish.sarif') != ''
        run: |
          set -euo pipefail
          for sarif in .iw/*.sarif; do
            [ -e "$sarif" ] || continue
            python3 .claude/skills/iw-oss-publish/scripts/honor_accepted.py \
              --sarif "$sarif" \
              --accepted .iw/oss-accepted.yaml \
              --out "$sarif"   # in-place rewrite via temp+mv inside the script if preferred
          done

      - name: Recompute fail-on-MUST gate after accept-honoring
        run: |
          # Re-evaluate whether any unaccepted MUST findings remain.
          set -euo pipefail
          if [ -f .iw/oss-publish-findings.json ]; then
            python3 - <<'PY'
          import json, sys, yaml, hashlib
          from pathlib import Path

          accepted_path = Path(".iw/oss-accepted.yaml")
          accepted = (yaml.safe_load(accepted_path.read_text()) if accepted_path.exists() else {}) or {}
          keys = {(e["check_id"], e["finding_hash"]) for e in accepted.get("accepted", [])}

          def fh(check_id, summary, evidence):
              h = hashlib.sha256()
              h.update(check_id.encode()); h.update(b"\x00")
              h.update(summary.encode()); h.update(b"\x00")
              if evidence is not None:
                  h.update(json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode())
              return h.hexdigest()[:16]

          findings = json.loads(Path(".iw/oss-publish-findings.json").read_text())
          unaccepted = [
              f for f in findings.get("findings", [])
              if f.get("severity") == "MUST"
              and f.get("status") == "fail"
              and (f["check_id"], fh(f["check_id"], f["summary"], f.get("evidence"))) not in keys
          ]
          if unaccepted:
              print(f"::error::{len(unaccepted)} unaccepted MUST finding(s)", file=sys.stderr)
              for f in unaccepted:
                  print(f"  - {f['check_id']}: {f['summary']}", file=sys.stderr)
              sys.exit(1)
          PY
          fi
```

Adjust paths and SARIF filename to match what the scanner emits today (verify by inspecting `.github/workflows/compliance-scan.yml` line 33-58 — the current step does `gitleaks detect ... --report-path .iw/gitleaks-tree.sarif` and `--report-path .iw/gitleaks-history.sarif`).

### 3. Reference doc — `docs/IW_AI_Core_OSS_Accepted_Risk.md`

A short page (1-2 screens) covering:
- Purpose: residual-risk acceptance for MUST findings
- File location and schema (`accepted: [{check_id, finding_hash, reason, accepted_at, accepted_by}]`)
- How `finding_hash` is computed (link to `compute_finding_hash` source)
- Dashboard accept flow
- CI honoring flow (link to `compliance-scan.yml`)
- Lifecycle: when a check rewords its summary the hash changes → entry stops matching → CI re-prompts → user re-accepts (intentional; documents that wording changes are equivalent to a re-evaluation)

### 4. Verification

Locally:
```bash
# Create a synthetic accepted file and verify the downgrade
mkdir -p .iw
printf "accepted:\n  - check_id: OSS-CH-99\n    finding_hash: deadbeef0000beef\n    reason: test\n    accepted_at: 2026-04-25T00:00:00Z\n    accepted_by: tester\n" > .iw/oss-accepted.yaml

# Synthetic SARIF with a matching result
printf '{"runs":[{"results":[{"ruleId":"OSS-CH-99","message":{"text":"Test"},"level":"error","properties":{"evidence":null}}]}]}' > /tmp/in.sarif

# Run the post-processor
python3 .claude/skills/iw-oss-publish/scripts/honor_accepted.py --sarif /tmp/in.sarif --accepted .iw/oss-accepted.yaml --out /tmp/out.sarif
jq . /tmp/out.sarif    # level should be "warning", message should contain [ACCEPTED RISK]
```

Note: the synthetic finding_hash must match `compute_finding_hash("OSS-CH-99", "Test", None)` — compute the real value with the helper before testing.

### 5. Update SECURITY note

If `.github/workflows/compliance-scan.yml` had a hard-fail line `exit 1` for any secret, the recompute step now owns gating. Remove the unconditional fail and let the recompute step govern exit status. Be precise — secrets in the working tree are MUST findings; they can be accepted via the same mechanism (which is intentional but should be rare and documented as risky).

## Project Conventions

- YAML 1.2-safe constructs only (`yaml.safe_load`, `yaml.safe_dump`).
- Pin GitHub Actions by SHA — `compliance-scan.yml` already does this; preserve.
- No new external dependencies. `yaml` is pre-installed in the workflow's Python; if not, `pip install pyyaml` in the step.

## TDD Requirement

Tests for `honor_accepted.py` go in `tests/unit/test_oss_honor_accepted.py` (S17). For S15, manual verification per §4 is sufficient.

## Output / Report

Report contains:
- Workflow file diff
- New script summary
- Reference doc path
- Manual verification output (downgrade confirmed, recompute step works on synthetic data)
- Open questions for reviewer

End with `iw step-done` / `iw step-fail`.
