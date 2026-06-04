# Check Catalog

The complete set of compliance checks the `iw-oss-publish` skill enforces.

- **Severity** maps to RFC 2119 keywords and exit contract:
  - `MUST` → blocker (exit 1)
  - `SHOULD` → warning (exit 0 with warning line)
  - `MAY` → info (exit 0)
- **Auto-fix** column:
  - `yes` — `uv run iw oss fix <CHECK_ID> --apply` applies automatically
  - `partial` — fix generates a stub or starting point; user must fill in content or confirm
  - `no` — human judgment required
- **OSPS** column maps to [OpenSSF OSPS Baseline v2025-02-25](https://baseline.openssf.org/versions/2025-02-25) where applicable.
- **Source** column cites `[R-00061 #N]` or `[R-00062 #N]` for the research finding that drove the check.

All checks are language-agnostic unless the "Detection" column specifies an ecosystem.

---

## Execution Order

The skill runs checks in this order (later checks may depend on artifacts produced earlier):

1. Pre-flight — `OSS-ENV-*`
2. Repository hygiene — `OSS-HYG-*`
3. Secrets — `OSS-SEC-*`
4. History — `OSS-HIST-*`
5. Internal references — `OSS-REF-*`
6. CI/CD surface — `OSS-CI-*`
7. Dependencies & SBOM — `OSS-DEP-*` (syft SBOM is reused by OSS-LIC-*)
8. License & attribution — `OSS-LIC-*`
9. Community health — `OSS-CH-*`
10. Privacy & PII — `OSS-PII-*`
11. Export control — `OSS-EXP-*`
12. Trademark & brand — `OSS-TM-*`
13. Contributor agreement — `OSS-CA-*`
14. Release provenance — `OSS-REL-*`
15. GitHub live settings — `OSS-GH-*` (only if repo is public or `gh` is authenticated)
16. Governance — `OSS-GOV-*`

---

## OSS-ENV — Environment Pre-flight

| ID | Severity | Auto-fix | OSPS | Description | Detection |
|----|----------|----------|------|-------------|-----------|
| OSS-ENV-01 | MUST | no | — | Target is a git repository | `git rev-parse --git-dir` |
| OSS-ENV-02 | MUST | no | — | All Tier-1 tools installed | `command -v {tool}` for each |
| OSS-ENV-03 | SHOULD | partial | — | `.iw/oss-publish.toml` present with resolved config | File existence + schema validation |
| OSS-ENV-04 | MAY | yes | — | `.iw/` in `.gitignore` | grep `.gitignore` |

---

## OSS-HYG — Repository Hygiene

| ID | Severity | Auto-fix | OSPS | Description | Detection |
|----|----------|----------|------|-------------|-----------|
| OSS-HYG-01 | MUST | yes | — | `.gitignore` excludes `.env`, `*.pem`, `*.key`, `*.pfx`, `*.p12` | grep patterns |
| OSS-HYG-02 | MUST | no | — | No tracked files matching secret/state glob: `*.env`, `*.pem`, `*.tfstate*`, `*.pfx`, `*.p12`, `*.key` (including private keys) | `git ls-files` against pattern |
| OSS-HYG-03 | SHOULD | yes | — | `.gitignore` excludes language artifacts (`__pycache__`, `.venv`, `node_modules`, `.iw/`) | grep patterns |
| OSS-HYG-04 | SHOULD | no | — | No blob >50 MB in history | `git rev-list --objects --all \| git cat-file --batch-check` |
| OSS-HYG-05 | SHOULD | no | — | No blob >10 MB in working tree not in LFS | `git ls-files` + stat |
| OSS-HYG-06 | MAY | no | — | Default branch is `main` | `git symbolic-ref refs/remotes/origin/HEAD` |

---

## OSS-SEC — Secrets

| ID | Severity | Auto-fix | OSPS | Description | Detection | Source |
|----|----------|----------|------|-------------|-----------|--------|
| OSS-SEC-01 | MUST | no | — | No secrets in working tree | `gitleaks detect --no-git` | [R-00061 #2] |
| OSS-SEC-02 | MUST | no | — | No secrets in full git history | `gitleaks detect --log-opts=--all` | [R-00061 #2] |
| OSS-SEC-03 | MUST | no | — | No live-verified secrets in history (one-time pre-flip) | `trufflehog git file://. --branch HEAD --only-verified` (publish mode only) | [R-00061 #2] |
| OSS-SEC-04 | SHOULD | yes | — | `.gitleaks.toml` present with IW-specific rules | File presence + rule count | [R-00061 #2] |
| OSS-SEC-05 | MAY | yes | — | `detect-secrets` baseline present (brownfield-mode projects only) | `.secrets.baseline` file | [R-00061 #3] |

---

## OSS-HIST — Git History

| ID | Severity | Auto-fix | OSPS | Description | Detection | Source |
|----|----------|----------|------|-------------|-----------|--------|
| OSS-HIST-01 | MUST (publish only) | no | — | History strategy chosen (`nuke` / `filter-repo` / `preserve`) | Config or interactive prompt | [R-00061 #4] |
| OSS-HIST-02 | MUST (publish only) | no | — | If OSS-SEC-02 failed, history rewrite completed before flip | Re-run of OSS-SEC-02 post-rewrite | [R-00061 #4, #5] |
| OSS-HIST-03 | SHOULD | no | — | Non-noreply contributor emails surfaced | `git log --all --format='%ae' \| grep -v users.noreply.github.com` | [R-00061 #14, R-00062 #11] |
| OSS-HIST-04 | MUST (publish only) | no | — | No submodules pointing to internal URLs | `git submodule foreach 'echo $url'` + internal-domain pattern | [R-00061 #4] |
| OSS-HIST-05 | SHOULD (publish only) | no | — | Annotated tags preserved across history rewrite (if filter-repo chosen) | `git for-each-ref refs/tags` before/after | [R-00061 #4] |
| OSS-HIST-06 | MUST (publish only) | no | — | GitHub Support ticket reminder surfaced if history rewritten with secrets | Emitted as playbook checklist item | [R-00061 #5] |

---

## OSS-REF — Internal References

| ID | Severity | Auto-fix | OSPS | Description | Detection | Source |
|----|----------|----------|------|-------------|-----------|--------|
| OSS-REF-01 | MUST | no | — | No RFC 1918 private IPs in code (excluding `docs/`, `tests/`, `examples/`) | `ripgrep` regex `(10\.\d+\.\d+\.\d+\|192\.168\.\d+\.\d+\|172\.(1[6-9]\|2\d\|3[01])\.\d+\.\d+)` | [R-00061 #7] |
| OSS-REF-02 | MUST | no | — | No internal FQDNs (`.internal`, `.corp`, `.local`, `.lan`, `.intranet`) | `ripgrep` | [R-00061 #7] |
| OSS-REF-03 | SHOULD | no | — | No absolute user home paths (`/home/{user}/`, `/Users/{user}/`, `C:\Users\{user}\`) | `ripgrep` | [R-00061 #7] |
| OSS-REF-04 | SHOULD | no | — | No employee email addresses matching `@innovation-ways.com` outside SECURITY/CoC/CONTRIBUTING | `ripgrep` with exclusions | [R-00061 #7] |
| OSS-REF-05 | MAY | no | — | No internal Slack/Jira/Linear URLs | `ripgrep` for known internal domain patterns | [R-00061 #7] |
| OSS-REF-06 | SHOULD | no | — | Semgrep internal-ref rules pass (AST-aware, Python/TS/Go only) | `semgrep --config=.semgrep/iw-internal-refs.yml` | [R-00061 #22] |

---

## OSS-CI — CI/CD Leak Surface

| ID | Severity | Auto-fix | OSPS | Description | Detection | Source |
|----|----------|----------|------|-------------|-----------|--------|
| OSS-CI-01 | MUST | no | — | No hardcoded secrets in workflow files | `gitleaks detect --no-git --source .github/workflows` | [R-00061 #12] |
| OSS-CI-02 | SHOULD | partial | — | All third-party Actions SHA-pinned | `pinact run --check` | [R-00061 #11] |
| OSS-CI-03 | SHOULD | no | — | No internal registry hostnames in Dockerfiles | `ripgrep` for internal domain pattern in `Dockerfile*` | [R-00061 #12] |
| OSS-CI-04 | MUST | no | — | No tracked `*.tfstate`, `*.tfstate.backup`, `terraform.tfvars` | `git ls-files` | [R-00061 #12] |
| OSS-CI-05 | SHOULD | no | — | `.devcontainer.json` reviewed for internal refs | `ripgrep` in `.devcontainer/` | [R-00061 #12] |
| OSS-CI-06 | SHOULD | yes | — | `.github/workflows/codeql.yml` present | File presence + starter-workflow match | [R-00061 #15] |
| OSS-CI-07 | SHOULD | yes | — | `.github/workflows/scorecard.yml` present | File presence | [R-00061 #15] |
| OSS-CI-08 | SHOULD | yes | — | `.github/dependabot.yml` present | File presence | [R-00061 #15] |
| OSS-CI-09 | SHOULD | yes | — | `.github/workflows/compliance-scan.yml` present (runs this skill) | File presence | — |

---

## OSS-DEP — Dependencies & SBOM

| ID | Severity | Auto-fix | OSPS | Description | Detection | Source |
|----|----------|----------|------|-------------|-----------|--------|
| OSS-DEP-01 | MUST | no | — | No `GPL-2.0-only` / `AGPL-3.0` / `GPL-3.0` (for Apache-2 outbound) / proprietary / unknown inbound deps | `grant check sbom.json` with IW deny-list policy | [R-00062 #4] |
| OSS-DEP-02 | SHOULD | no | — | LGPL-licensed deps confirmed as dynamic linkage | Human judgment via punchlist | [R-00062 #4] |
| OSS-DEP-03 | MUST | no | — | No CRITICAL-severity unpatched CVEs in runtime deps | `grype sbom:sbom.json --fail-on critical` and `osv-scanner` | [R-00061 #8] |
| OSS-DEP-04 | SHOULD | no | — | No HIGH-severity unpatched CVEs in runtime deps | `grype --fail-on high` | [R-00061 #8] |
| OSS-DEP-05 | SHOULD | yes | — | SBOM generated in both SPDX and CycloneDX | `syft . -o spdx-json,cyclonedx-json` | [R-00061 #8] |
| OSS-DEP-06 | SHOULD | yes | — | `THIRD_PARTY_LICENSES` file present and current | Regenerate via ecosystem tools, diff against committed file | [R-00062 #3] |
| OSS-DEP-07 | MAY | no | — | Per-ecosystem vuln scanners run clean | `pip-audit`, `cargo audit`, `govulncheck`, `npm audit` per ecosystem | [R-00061 #9] |

---

## OSS-LIC — License & Attribution

| ID | Severity | Auto-fix | OSPS | Description | Detection | Source |
|----|----------|----------|------|-------------|-----------|--------|
| OSS-LIC-01 | MUST | yes | OSPS-LE-03.01 | `LICENSE` file present in root | File presence | [R-00062 #7, #17] |
| OSS-LIC-02 | MUST | partial | OSPS-LE-02.01 | License is OSI-approved | `licensee detect` SPDX match against OSI allowlist | [R-00062 #18] |
| OSS-LIC-03 | MUST | partial | — | SPDX identifier matches `config.license` | Diff detected SPDX vs config | [R-00062 #1] |
| OSS-LIC-04 | MUST | yes | — | Copyright line uses full legal entity name | `ripgrep "Copyright.*{company_legal_name}" LICENSE` | [R-00062 #5] |
| OSS-LIC-05 | SHOULD | yes | — | Copyright year within current or last calendar year | Regex against year in LICENSE | [R-00062 §10 soft check] |
| OSS-LIC-06 | SHOULD | yes | — | `NOTICE` file present if license is Apache-2.0 | File presence gated on license | [R-00062 #5] |
| OSS-LIC-07 | SHOULD | partial | — | `NOTICE` aggregates upstream Apache-2.0 dep NOTICE contents | Diff regenerated NOTICE against committed | [R-00062 #5] |
| OSS-LIC-08 | MAY | partial | — | `reuse lint` passes (per-file SPDX headers) | `reuse lint` | [R-00062 #19] |

---

## OSS-CH — Community Health

| ID | Severity | Auto-fix | OSPS | Description | Detection | Source |
|----|----------|----------|------|-------------|-----------|--------|
| OSS-CH-01 | MUST | partial | — | `README.md` present with project name, description, install, usage, license section | File presence + section header grep | [R-00062 #17] |
| OSS-CH-02 | MUST | partial | OSPS-VM-02.01 | `SECURITY.md` present with supported versions + reporting channel | File presence + content grep for "report" + email/PVR | [R-00062 #13, #18] |
| OSS-CH-03 | SHOULD | yes | — | `CODE_OF_CONDUCT.md` present | File presence | [R-00062 #8, #17] |
| OSS-CH-04 | SHOULD | yes | — | CoC is Contributor Covenant v2.1 or later | Version string grep | [R-00062 #8] |
| OSS-CH-05 | SHOULD | yes | — | CoC enforcement contact is group email, not personal | Regex: contact matches `*@{company_domain}` and is not a personal alias | [R-00062 #8, #15] |
| OSS-CH-06 | SHOULD | yes | OSPS-GV-03.01 | `CONTRIBUTING.md` present | File presence | [R-00062 #9, #17] |
| OSS-CH-07 | SHOULD | yes | — | `CONTRIBUTING.md` explains DCO sign-off (`git commit -s`) | Content grep | [R-00062 #9] |
| OSS-CH-08 | SHOULD | yes | — | `CODEOWNERS` file present (required if ≥2 maintainers) | File presence | [R-00062 #17] |
| OSS-CH-09 | SHOULD | yes | — | `.github/PULL_REQUEST_TEMPLATE.md` present | File presence | [R-00062 #17] |
| OSS-CH-10 | SHOULD | yes | — | `.github/ISSUE_TEMPLATE/*.yml` present (bug + feature) | File presence | [R-00062 #17] |
| OSS-CH-11 | MAY | yes | — | `SUPPORT.md` present | File presence | [R-00062 #17] |
| OSS-CH-12 | MAY | no | — | `.github/FUNDING.yml` present | File presence (no auto-fix; IW decides) | [R-00062 #17] |

---

## OSS-PII — Privacy and PII

| ID | Severity | Auto-fix | OSPS | Description | Detection | Source |
|----|----------|----------|------|-------------|-----------|--------|
| OSS-PII-01 | MUST | no | — | No real-looking email addresses in `tests/`, `fixtures/`, `data/`, `seeds/` outside allowlisted domains (`example.com`, `test.`, `*.invalid`) | ripgrep regex + domain allowlist | [R-00062 #11] |
| OSS-PII-02 | MUST | no | — | No real-looking SSN/credit-card/phone patterns in fixtures | ripgrep patterns (Luhn validator for CC) | [R-00062 #11] |
| OSS-PII-03 | SHOULD | no | — | Contributor author emails enumerated and surfaced (shared with OSS-HIST-03) | `git log --all --format='%ae' \| sort -u` | [R-00062 #11] |

---

## OSS-EXP — Export Control

| ID | Severity | Auto-fix | OSPS | Description | Detection | Source |
|----|----------|----------|------|-------------|-----------|--------|
| OSS-EXP-01 | SHOULD (conditional MUST) | no | — | Crypto imports surfaced for human classification (Python: `cryptography`, `pynacl`; JS: `node-forge`, `sjcl`, `tweetnacl`; Go: `crypto/*`; Rust: `ring`, `rustls`, `aes`) | Per-ecosystem import grep | [R-00062 #10] |
| OSS-EXP-02 | MUST (if non-standard crypto) | no | — | BIS/NSA notification confirmed (human attestation via config) | Config flag `export_control.non_standard_crypto_notified = true` | [R-00062 #10] |

---

## OSS-TM — Trademark and Brand

| ID | Severity | Auto-fix | OSPS | Description | Detection | Source |
|----|----------|----------|------|-------------|-----------|--------|
| OSS-TM-01 | SHOULD | yes | — | `TRADEMARK.md` present | File presence | [R-00062 #12] |
| OSS-TM-02 | SHOULD | no | — | No PyPI package name collision | `HTTP GET https://pypi.org/pypi/{name}/json` | [R-00062 #12] |
| OSS-TM-03 | SHOULD | no | — | No npm package name collision | `HTTP GET https://registry.npmjs.org/{name}` | [R-00062 #12] |
| OSS-TM-04 | SHOULD | no | — | No crates.io name collision | `HTTP GET https://crates.io/api/v1/crates/{name}` | [R-00062 #12] |
| OSS-TM-05 | SHOULD | no | — | No GitHub org/repo name collision (outside own org) | `gh search repos` | [R-00062 #12] |
| OSS-TM-06 | SHOULD | no | — | Human has run USPTO Trademark Search | Human attestation via config | [R-00062 #12] |
| OSS-TM-07 | SHOULD | no | — | Human has run WIPO Global Brand Database | Human attestation via config | [R-00062 #12] |
| OSS-TM-08 | SHOULD | yes | — | README contains trademark notice (if TRADEMARK.md absent) | Content grep | [R-00062 #12] |

---

## OSS-CA — Contributor Agreement

| ID | Severity | Auto-fix | OSPS | Description | Detection | Source |
|----|----------|----------|------|-------------|-----------|--------|
| OSS-CA-01 | SHOULD | partial | — | DCO configured on the repo | `.github/dco.yml` present OR `cncf/dco2` installed at org | [R-00062 #9] |
| OSS-CA-02 | SHOULD | yes | — | CONTRIBUTING.md mentions DCO sign-off | Content grep (shared with OSS-CH-07) | [R-00062 #9] |
| OSS-CA-03 | SHOULD | no | OSPS-AC-03.01 | Branch protection requires `dco` status check | `gh api /repos/.../branches/main/protection` | [R-00062 #9, #14] |

---

## OSS-REL — Release Provenance

| ID | Severity | Auto-fix | OSPS | Description | Detection | Source |
|----|----------|----------|------|-------------|-----------|--------|
| OSS-REL-01 | SHOULD | yes | — | `CHANGELOG.md` present (Keep-a-Changelog format) | File presence + header grep | [R-00062 #16] |
| OSS-REL-02 | SHOULD | no | — | Conventional Commits observable (≥70% of last 20 commits) | Parse `git log -20 --format=%s` against `feat:/fix:/chore:/...` | [R-00062 #16] |
| OSS-REL-03 | SHOULD | yes | — | `.github/workflows/release-please.yml` present using `googleapis/release-please-action@v4` | File presence + action ref | [R-00061 #20] |
| OSS-REL-04 | SHOULD | yes | — | Release workflow references `actions/attest-build-provenance` | Content grep | [R-00062 #16, R-00061 #16] |
| OSS-REL-05 | SHOULD | no | — | At least one semver tag exists pre-publish | `git tag -l 'v[0-9]*'` | [R-00062 #16] |

---

## OSS-GH — GitHub Live Settings

(Skipped if `gh` CLI unauthenticated. For `publish` mode, emitted as playbook commands instead of checks.)

| ID | Severity | Auto-fix | OSPS | Description | Detection | Source |
|----|----------|----------|------|-------------|-----------|--------|
| OSS-GH-01 | MUST | no | OSPS-AC-03.01 | Branch protection on `main` blocks direct pushes | `gh api /repos/.../branches/main/protection` | [R-00061 #15, R-00062 #14] |
| OSS-GH-02 | MUST | no | OSPS-AC-03.02 | Branch deletion requires confirmation | Same endpoint, `allow_deletions=false` | [R-00062 #18] |
| OSS-GH-03 | SHOULD | no | — | Secret scanning enabled | `gh api /repos/.../security-and-analysis` | [R-00061 #15] |
| OSS-GH-04 | SHOULD | no | — | Push protection enabled | Same endpoint | [R-00061 #1, #15] |
| OSS-GH-05 | SHOULD | no | — | Dependabot alerts enabled | `gh api /repos/.../vulnerability-alerts` | [R-00061 #15] |
| OSS-GH-06 | SHOULD | no | — | Dependabot security updates enabled | `gh api /repos/.../automated-security-fixes` | [R-00061 #15] |
| OSS-GH-07 | SHOULD | no | — | Private Vulnerability Reporting enabled | `gh api /repos/.../private-vulnerability-reporting` | [R-00062 #13] |
| OSS-GH-08 | SHOULD | no | — | Repo description non-empty | `gh repo view --json description` | [R-00062 #14] |
| OSS-GH-09 | SHOULD | no | — | Repo has ≥3 topics | `gh repo view --json repositoryTopics` | [R-00062 #14] |
| OSS-GH-10 | SHOULD | no | — | Homepage URL set | `gh repo view --json homepageUrl` | [R-00062 #14] |
| OSS-GH-11 | SHOULD | no | — | Squash-merge enabled | `gh api /repos/...` | [R-00062 #14] |
| OSS-GH-12 | MAY | no | — | Merge-commit disabled | Same | [R-00062 #14] |
| OSS-GH-13 | SHOULD | no | — | Delete branch on merge enabled | Same | [R-00062 #14] |
| OSS-GH-14 | SHOULD | no | — | At least one GitHub Release published | `gh release list --limit 1` | [R-00062 #16] |

---

## OSS-GOV — Governance

| ID | Severity | Auto-fix | OSPS | Description | Detection | Source |
|----|----------|----------|------|-------------|-----------|--------|
| OSS-GOV-01 | MAY / SHOULD-conditional | partial | — | `GOVERNANCE.md` present (SHOULD if ≥4 maintainers or foundation-stewardship flag) | File presence + maintainer count (from CODEOWNERS or config) | [R-00062 #15] |
| OSS-GOV-02 | MAY | partial | — | `MAINTAINERS` file or equivalent listing | File presence | [R-00062 #15] |

---

## Check Count Summary

| Domain | MUST | SHOULD | MAY | Total |
|--------|------|--------|-----|-------|
| OSS-ENV | 2 | 1 | 1 | 4 |
| OSS-HYG | 2 | 3 | 1 | 6 |
| OSS-SEC | 3 | 1 | 1 | 5 |
| OSS-HIST | 3 | 2 | 0 | 5 |
| OSS-REF | 2 | 3 | 1 | 6 |
| OSS-CI | 2 | 7 | 0 | 9 |
| OSS-DEP | 2 | 4 | 1 | 7 |
| OSS-LIC | 4 | 3 | 1 | 8 |
| OSS-CH | 2 | 8 | 2 | 12 |
| OSS-PII | 2 | 1 | 0 | 3 |
| OSS-EXP | 0 | 1 | 0 | 2 (1 conditional MUST) |
| OSS-TM | 0 | 8 | 0 | 8 |
| OSS-CA | 0 | 3 | 0 | 3 |
| OSS-REL | 0 | 5 | 0 | 5 |
| OSS-GH | 2 | 11 | 1 | 14 |
| OSS-GOV | 0 | 1 | 1 | 2 |
| **Total** | **26** | **62** | **9** | **99** |

---

## Auto-Fix Coverage

| Auto-fix status | Count | % |
|-----------------|-------|---|
| `yes` (fully automatable) | 33 | 33% |
| `partial` (generates stub / requires confirmation) | 13 | 13% |
| `no` (human judgment or external action required) | 53 | 54% |

The 53 `no` items are predominantly detection-only — they scan for a condition and report it, with the fix being a code edit the skill will not perform autonomously (e.g., removing PII from fixtures, classifying crypto, running a history rewrite). The ~46% auto-fixable column covers the community-file, template, and CI/CD scaffolding bulk.

---

## Configuration Overrides

Any check may be disabled for a specific project via `.iw/oss-publish.toml`:

```toml
[checks.disabled]
ids = ["OSS-TM-06", "OSS-TM-07"]  # manual trademark searches for a non-branded utility
reason = "Internal-only tool, no public name collision risk"

[checks.demoted]
# move a check from MUST to SHOULD
"OSS-LIC-06" = "SHOULD"  # relax NOTICE requirement for a pre-alpha project
```

Demotions and disablings are logged in the report output as `[override]` annotations. MUST-level disables require a documented `reason` string.
