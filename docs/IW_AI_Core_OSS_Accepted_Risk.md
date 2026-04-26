# OSS Accepted Risk — CI Behavior

## Purpose

`.iw/oss-accepted.yaml` records **residual-risk acceptances** for MUST-level findings that cannot or should not be auto-remediated. Acceptance downgrades a finding from a blocking error to a warning so the CI merge gate can pass, while preserving a visible record of the accepted risk.

## File Format

**Location**: `{repo_root}/.iw/oss-accepted.yaml`

```yaml
accepted:
  - check_id: OSS-CH-99          # check identifier
    finding_hash: deadbeef0000beef # 16-char hex SHA of (check_id, summary, evidence)
    reason: "Justification text"  # human-readable rationale
    accepted_at: "2026-04-25T00:00:00Z"   # ISO-8601 UTC
    accepted_by: user@example.com         # user identity
```

Schema:

| Field | Type | Description |
|-------|------|-------------|
| `check_id` | string | Check identifier (e.g., `OSS-CH-99`, `GITLEAKS-42`) |
| `finding_hash` | string | 16-char hex SHA-256 of the finding key (see below) |
| `reason` | string | Why this risk is accepted (min 1 char) |
| `accepted_at` | string | ISO-8601 UTC timestamp |
| `accepted_by` | string | User who accepted (from `$USER` env var in dashboard) |

## Finding Hash Computation

`finding_hash` is computed identically in two places:

- **Dashboard**: `dashboard/services/oss_accepted.py::compute_finding_hash`
- **CI post-processor**: `skills/iw-oss-publish/scripts/honor_accepted.py::compute_finding_hash`

```python
import hashlib, json

def compute_finding_hash(check_id: str, summary: str, evidence: dict | None) -> str:
    h = hashlib.sha256()
    h.update(check_id.encode())
    h.update(b"\x00")
    h.update(summary.encode())
    h.update(b"\x00")
    if evidence is not None:
        h.update(json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode())
    return h.hexdigest()[:16]  # 16 hex chars = 64 bits
```

The hash covers `(check_id, summary, sorted-evidence-JSON)` — any change to the check ID or the finding's summary string will produce a different hash.

## Dashboard Accept Flow

1. A user navigates to a MUST finding in the IW AI Core dashboard.
2. They click **Mark accepted** and provide a reason.
3. `dashboard/services/oss_accepted.py::append_accepted` writes an entry to `.iw/oss-accepted.yaml` in the user's working tree.
4. The file is committed (manually or via a follow-up agent step).

**Note**: The dashboard writes to `.iw/oss-accepted.yaml` in the git working tree. The file must be committed for CI to see it. The daemon or an agent should commit the file after it is modified.

## CI Honoring Flow

The `compliance-scan.yml` workflow runs the compliance scan, then:

1. **`honor_accepted.py`** post-processor reads `.iw/oss-accepted.yaml` and downgrades any SARIF result whose `(check_id, finding_hash)` matches an accepted entry:
   - `level`: `"error"` → `"warning"`
   - `message.text`: appended with `[ACCEPTED RISK]: {reason}`
2. **Recompute gate** checks `oss-publish-findings.json` for any remaining unaccepted MUST findings that `status == "fail"`. If any exist, the workflow exits 1.
3. **SARIF upload** sends the (already-downgraded) SARIF to GitHub code scanning — findings appear as warnings, not errors.

```yaml
# In .github/workflows/compliance-scan.yml
- name: Honor .iw/oss-accepted.yaml — downgrade matched findings
  run: |
    for sarif in .iw/gitleaks-tree.sarif .iw/gitleaks-history.sarif .iw/oss-publish.sarif; do
      [ -e "$sarif" ] || continue
      python3 .claude/skills/iw-oss-publish/scripts/honor_accepted.py \
        --sarif "$sarif" --accepted .iw/oss-accepted.yaml --out "$sarif"
    done

- name: Recompute fail-on-MUST gate after accept-honoring
  run: |
    # Re-evaluate whether any unaccepted MUST findings remain...
```

See [`.github/workflows/compliance-scan.yml`](.github/workflows/compliance-scan.yml).

## Lifecycle — Hash Drift

When a check is updated and its **summary string changes**, the computed `finding_hash` changes. The old acceptance entry no longer matches — CI will re-promote the finding to an error and block the merge.

This is **intentional**: a wording change is treated as a re-evaluation trigger. The user must re-accept the finding with the new wording.

Example drift scenario:

| Event | `OSS-CH-99` summary | Hash | Accepted? |
|-------|---------------------|------|-----------|
| Initial accept | "High severity CVE in dependency X" | `a1b2c3d4e5f6...` | ✅ |
| Check updated | "Critical CVE in dependency X" | `f6e5d4c3b2a1...` | ❌ CI blocks |

The acceptance is not automatically migrated — the risk should be re-evaluated under the new wording.

## Secrets Acceptance

Secrets (gitleaks findings) can be accepted via the same mechanism. This should be **rare and deliberate** — accepting a secret in the repository history means the CI merge gate will not block on that secret being present in the future.

For secrets in the **working tree**: acceptance is recorded in `.iw/oss-accepted.yaml` and the secret should still be removed from the file before committing.

For secrets in **git history**: acceptance records the risk but does not remove the secret. A history rewrite may be required (see `iw-oss-publish make-oss`).

## Files

| File | Purpose |
|------|---------|
| `dashboard/services/oss_accepted.py` | Dashboard read/write logic + hash function |
| `skills/iw-oss-publish/scripts/honor_accepted.py` | CI SARIF post-processor (master copy) |
| `.claude/skills/iw-oss-publish/scripts/honor_accepted.py` | Synced copy invoked by CI |
| `.iw/oss-accepted.yaml` | Per-repo accepted risk ledger |
| `.github/workflows/compliance-scan.yml` | CI workflow with honor + gate steps |
