# Output Format

All artifacts the skill emits, with exact schemas so the Phase-1 orchestrator (and downstream consumers like a future dashboard or CI gate) have a stable contract.

Emitted under `{target}/.iw/` (which the skill adds to `.gitignore` automatically).

---

## File Inventory

| File | Purpose | Modes | Format |
|------|---------|-------|--------|
| `oss-publish-report.md` | Human-readable findings report | scan | Markdown |
| `oss-publish-findings.json` | Machine-readable findings | scan | JSON Schema below |
| `gitleaks-tree.sarif` | Working-tree secrets, uploadable to GitHub Code Scanning | scan | SARIF 2.1.0 |
| `gitleaks-history.sarif` | Full-history secrets | scan | SARIF 2.1.0 |
| `sbom.spdx.json` | SPDX 2.3 software bill of materials | scan (if syft available) | SPDX 2.3 JSON |
| `sbom.cyclonedx.json` | CycloneDX 1.6 SBOM | scan (if syft available) | CycloneDX 1.6 JSON |
| `grype-vulnerabilities.json` | Vulnerability findings | scan | Grype JSON |
| `osv-vulnerabilities.json` | OSV.dev vulnerability findings | scan (if lockfiles present) | OSV-Scanner JSON |
| `THIRD_PARTY_LICENSES.md` | Aggregated human-readable third-party licenses | fix | Markdown (written to target repo root via fix) |
| `compliance-punchlist.md` | Remaining human-judgment items | fix | Markdown |

---

## `oss-publish-findings.json` Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "skill_version": "0.1.0",
  "generated_at": "2026-04-21T14:32:00Z",
  "target": "/absolute/path/to/repo",
  "mode": "scan",
  "config": {
    "project_name": "my-oss-project",
    "license": "Apache-2.0",
    "company_legal_name": "Innovation Ways - Unipessoal LDA",
    "company_brand": "Innovation Ways",
    "company_github_org": "innovation-ways",
    "contributor_agreement": "DCO",
    "coc_version": "v3"
  },
  "repo": {
    "current_branch": "main",
    "head_sha": "abc123def456",
    "visibility": "private",
    "remote_url": "git@github.com:innovation-ways/my-oss-project.git",
    "commit_count": 847,
    "contributor_email_count": 3,
    "ecosystems_detected": ["python", "javascript"]
  },
  "tools_available": {
    "gitleaks": "8.21.2",
    "git-filter-repo": "2.47.0",
    "syft": "1.15.0",
    "grant": "0.3.1",
    "grype": "0.86.0",
    "osv-scanner": "2.0.3",
    "ripgrep": "14.1.0",
    "pinact": "3.9.0",
    "gh": "2.63.0",
    "trufflehog": null,
    "semgrep": null
  },
  "findings": [
    {
      "id": "OSS-LIC-01",
      "severity": "MUST",
      "status": "fail",
      "domain": "license",
      "summary": "LICENSE file not present in repository root",
      "detail": "No file named LICENSE, LICENSE.md, LICENSE.txt, or COPYING found.",
      "remediation": "Run `uv run iw oss fix <CHECK_ID> --apply` to auto-generate LICENSE from template based on config.license.",
      "auto_fix_available": true,
      "osps_control": "OSPS-LE-03.01",
      "evidence": {
        "paths_checked": ["LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"],
        "none_matched": true
      },
      "tool": null,
      "source_research": ["R-00062 #7", "R-00062 #17"]
    },
    {
      "id": "OSS-SEC-02",
      "severity": "MUST",
      "status": "pass",
      "domain": "secrets",
      "summary": "No secrets detected in full git history",
      "detail": "gitleaks scanned 847 commits; 0 findings.",
      "remediation": null,
      "auto_fix_available": false,
      "osps_control": null,
      "evidence": {
        "tool": "gitleaks",
        "tool_version": "8.21.2",
        "scan_range": "--all",
        "finding_count": 0,
        "sarif_path": ".iw/gitleaks-history.sarif"
      },
      "source_research": ["R-00061 #2"]
    },
    {
      "id": "OSS-SEC-02",
      "severity": "MUST",
      "status": "fail",
      "domain": "secrets",
      "summary": "Secrets detected in git history",
      "detail": "gitleaks found 3 secret(s) across 2 commits.",
      "remediation": "Rewrite history to remove. Use `iw-oss-publish publish` → choose filter-repo or nuke strategy.",
      "auto_fix_available": false,
      "osps_control": null,
      "evidence": {
        "tool": "gitleaks",
        "tool_version": "8.21.2",
        "scan_range": "--all",
        "finding_count": 3,
        "sarif_path": ".iw/gitleaks-history.sarif",
        "sample_findings": [
          {
            "rule_id": "aws-access-token",
            "commit": "abc123def456",
            "file": "config/.env.production",
            "line": 12
          }
        ]
      },
      "source_research": ["R-00061 #2"]
    }
  ],
  "summary": {
    "must_pass": 24,
    "must_fail": 2,
    "should_pass": 55,
    "should_fail": 7,
    "may_pass": 7,
    "may_fail": 2,
    "total": 97,
    "exit_code": 1
  }
}
```

### Field conventions

- `severity`: `"MUST" | "SHOULD" | "MAY" | "INFO"` (INFO for demoted checks per config)
- `status`: `"pass" | "fail" | "skip" | "human_required"`
- `domain`: slug matching the check ID prefix (`"secrets"`, `"history"`, `"license"`, `"community"`, `"dependencies"`, `"trademark"`, `"export"`, `"privacy"`, `"ci"`, `"hygiene"`, `"release"`, `"github"`, `"governance"`, `"environment"`)
- `evidence`: free-form object with per-check fields; fields stable within a check ID
- `source_research`: array of `"R-NNNNN #N"` references
- `auto_fix_available`: `true` | `false` — informs punchlist inclusion

### Special status values

- `status: "skip"` — check was disabled via config (`[checks.disabled]`) or a required tool is missing
- `status: "human_required"` — the check needs a human attestation (e.g., crypto classification, trademark search) that has not yet been recorded in config

---

## `oss-publish-report.md` Layout

```markdown
# IW OSS Publish — {mode} — {project_name}

**Date**: 2026-04-21 14:32:00Z
**Target**: /absolute/path/to/repo
**Mode**: scan
**License**: Apache-2.0
**Visibility**: private
**HEAD**: abc123de
**Branch**: main

## Summary

| Severity | Pass | Fail | Total |
|----------|------|------|-------|
| MUST     |   24 |    2 |    26 |
| SHOULD   |   55 |    7 |    62 |
| MAY      |    7 |    2 |     9 |

**Exit code**: 1 (MUST failures present)

## Blockers (MUST)

### OSS-LIC-01 — LICENSE file not present in repository root
- **Remediation**: `uv run iw oss fix <CHECK_ID> --apply` will auto-generate.
- **OSPS**: OSPS-LE-03.01
- **Source**: R-00062 #7, #17

### OSS-SEC-02 — Secrets detected in git history (3 findings)
- **Remediation**: `iw-oss-publish publish` → choose filter-repo or nuke.
- **Evidence**: `.iw/gitleaks-history.sarif`
- **Source**: R-00061 #2

## Warnings (SHOULD)

{ grouped by domain; one line per finding }

## Info (MAY)

{ one line per finding }

## Human Judgment Required

- **OSS-EXP-01**: Python imports `cryptography`. Confirm standard-library crypto only (no custom algorithms). If non-standard, EAR notification to BIS/NSA may be required.
- **OSS-TM-06**: Run manual USPTO Trademark Search for "{project_name}" at https://tmsearch.uspto.gov/
- **OSS-TM-07**: Run manual WIPO Global Brand Database search at https://branddb.wipo.int/

## Artifacts

- `.iw/oss-publish-findings.json` — machine-readable findings
- `.iw/gitleaks-history.sarif` — upload to GitHub Code Scanning
- `.iw/sbom.spdx.json` / `.iw/sbom.cyclonedx.json` — Software Bill of Materials
- `.iw/grype-vulnerabilities.json` — vulnerability scan

## Next Step

Run `uv run iw oss fix <CHECK_ID> --apply` to auto-generate the missing LICENSE and other community health files.
```

---

## `publish-playbook.sh` Structure

The playbook is a bash script that the user reads and runs manually. Every destructive action is commented with a preceding confirmation prompt (`read -p "..."`) so the user opts in step-by-step.

```bash
#!/usr/bin/env bash
# Generated by iw-oss-publish on 2026-04-21T14:32:00Z
# Target: innovation-ways/my-oss-project
# Review this script before running. Each section is independently re-runnable.

set -euo pipefail
ORG="innovation-ways"
REPO="my-oss-project"

confirm() {
  read -p "$1 [y/N] " -n 1 -r; echo
  [[ $REPLY =~ ^[Yy]$ ]] || { echo "Skipped."; return 1; }
}

# ---- Step 1: Flip to public (IRREVERSIBLE) --------------------------------
confirm "Flip $ORG/$REPO to public visibility?" && \
  gh repo edit "$ORG/$REPO" --visibility public

# ---- Step 2: Description, topics, homepage --------------------------------
gh repo edit "$ORG/$REPO" \
  --description "One-line project description from config.project_description" \
  --homepage    "https://innovation-ways.com/projects/my-oss-project" \
  --add-topic   "python" \
  --add-topic   "ai" \
  --add-topic   "cli"

# ---- Step 3: Merge settings ----------------------------------------------
gh repo edit "$ORG/$REPO" \
  --enable-squash-merge \
  --disable-merge-commit \
  --delete-branch-on-merge

# ---- Step 4: Branch protection on main -----------------------------------
confirm "Apply branch protection to main?" && \
gh api repos/"$ORG"/"$REPO"/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["dco","compliance-scan"]}' \
  --field enforce_admins=true \
  --field required_pull_request_reviews='{"required_approving_review_count":1,"require_code_owner_reviews":true,"dismiss_stale_reviews":true}' \
  --field allow_deletions=false \
  --field allow_force_pushes=false \
  --field restrictions=null

# ---- Step 5: Secret scanning + push protection ---------------------------
gh api repos/"$ORG"/"$REPO" --method PATCH \
  --field security_and_analysis='{"secret_scanning":{"status":"enabled"},"secret_scanning_push_protection":{"status":"enabled"}}'

# ---- Step 6: Dependabot --------------------------------------------------
gh api repos/"$ORG"/"$REPO"/vulnerability-alerts --method PUT
gh api repos/"$ORG"/"$REPO"/automated-security-fixes --method PUT

# ---- Step 7: Private Vulnerability Reporting -----------------------------
gh api repos/"$ORG"/"$REPO"/private-vulnerability-reporting --method PUT

# ---- Step 8: Reminders ---------------------------------------------------
cat <<REMINDERS

  MANUAL FOLLOW-UPS (not automatable):
  
  [ ] Install cncf/dco2 GitHub App on the org (if not already):
      https://github.com/apps/dco
  
  [ ] Run USPTO and WIPO trademark searches for "my-oss-project":
      https://tmsearch.uspto.gov/
      https://branddb.wipo.int/
  
  [ ] (IF HISTORY WAS REWRITTEN) Open GitHub Support ticket for SHA cache purge:
      https://support.github.com/contact
  
  [ ] Tag first release and create GitHub Release:
      git tag -s v0.1.0 -m "Initial public release"
      git push origin v0.1.0
      gh release create v0.1.0 --generate-notes
  
  [ ] Add OpenSSF Scorecard badge to README:
      https://api.securityscorecards.dev/projects/github.com/$ORG/$REPO/badge

REMINDERS

echo "Playbook complete. Verify settings with: gh repo view $ORG/$REPO --web"
```

---

## `compliance-punchlist.md` Layout

```markdown
# Compliance Punchlist — {project_name}

Generated by `iw-oss-publish scan` on 2026-04-21.
Branch: `iw-oss-publish/prep-2026-04-21`

Remaining items require human judgment or external action. Address each, then
re-run `iw-oss-publish scan` to verify, and finally `iw-oss-publish publish`.

---

## MUST (block publish)

### [OSS-EXP-01] Crypto import classification
Python imports detected: `cryptography`, `hashlib`.
- [ ] Standard library / standard algorithms only → record in `.iw/oss-publish.toml`:
      `[export_control] standard_crypto_only = true`
- [ ] Non-standard or custom cryptography → BIS/NSA notification required before publish.
      See R-00062 finding #10 for procedure.

### [OSS-PII-01] Real-looking email in tests/
Path: `tests/fixtures/sample_users.json` line 14: `jane.doe@acme.com`
- [ ] Replace with `@example.com` or `@test.invalid` per GDPR and IETF RFC 6761.

## SHOULD (publish permitted with warning)

### [OSS-HIST-03] 4 non-noreply author emails in history
- alice@personal-gmail.com (3 commits)
- bob@old-employer.com (12 commits)
- ...
- [ ] Contact contributors to confirm email exposure is acceptable, OR
- [ ] Plan a history rewrite (filter-repo) to pseudonymize

### [OSS-TM-02..04] Name collision checks
- `my-oss-project` on PyPI: ❌ already registered
- `my-oss-project` on npm: ✅ available
- `my-oss-project` on crates.io: ✅ available
- [ ] Decide: rename project, publish under a scoped name, or accept PyPI collision

### [OSS-TM-06,07] Manual trademark searches
- [ ] USPTO Trademark Search: https://tmsearch.uspto.gov/
- [ ] WIPO Global Brand Database: https://branddb.wipo.int/
- [ ] Record outcome in `.iw/oss-publish.toml`:
      `[trademark] uspto_searched = "2026-04-21"`
      `[trademark] wipo_searched  = "2026-04-21"`

---

## Applied automatically (review on your branch)

The following files were generated or updated on branch `iw-oss-publish/prep-2026-04-21`:

- `LICENSE` (Apache-2.0, copyright Innovation Ways - Unipessoal LDA)
- `NOTICE` (Apache-2.0 attribution)
- `README.md` (stub — please fill Installation and Usage sections)
- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md` (Contributor Covenant v3)
- `SECURITY.md`
- `CODEOWNERS`
- `TRADEMARK.md`
- `.github/PULL_REQUEST_TEMPLATE.md`
- `.github/ISSUE_TEMPLATE/bug_report.yml`
- `.github/ISSUE_TEMPLATE/feature_request.yml`
- `.github/workflows/scorecard.yml`
- `.github/workflows/codeql.yml`
- `.github/workflows/release-please.yml`
- `.github/workflows/compliance-scan.yml`
- `.github/dependabot.yml`
- `.gitleaks.toml`
- `.pre-commit-config.yaml`
- `THIRD_PARTY_LICENSES.md`
- `.gitignore` (added entries)
- `.iw/oss-publish.toml`

Review with: `git diff --cached`
```

---

## SARIF Output

`gitleaks-tree.sarif` and `gitleaks-history.sarif` follow SARIF 2.1.0 produced directly by gitleaks (`--report-format sarif`). No transformation.

GitHub Code Scanning upload path (for CI):

```bash
gh api --method POST /repos/{org}/{repo}/code-scanning/sarifs \
  -F commit_sha=$(git rev-parse HEAD) \
  -F ref=refs/heads/main \
  -F sarif=@.iw/gitleaks-history.sarif
```

---

## Exit Codes Summary

| Code | Meaning |
|------|---------|
| 0 | Clean (all MUST pass) or successful playbook emission |
| 1 | At least one MUST-level finding is `fail` or `human_required` |
| 2 | Setup / environment error (not a compliance verdict) |
| 130 | User-cancelled (Ctrl-C) |
