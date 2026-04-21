# Tools Reference

Tool inventory used by `iw-oss-publish`: install commands, invocation patterns, and per-tool justification (citing R-00061 / R-00062 findings).

---

## Tier 1 — Required

Installed automatically by `scripts/install_tools.sh`. The skill aborts any mode if these are missing.

| Tool | Purpose | License | Install command |
|------|---------|---------|-----------------|
| `gitleaks` | Primary secrets scanner (tree + history) | MIT | `curl -sSfL https://github.com/gitleaks/gitleaks/releases/latest/download/gitleaks_linux_x64.tar.gz \| tar -xz -C ~/.local/bin` |
| `git-filter-repo` | Surgical history rewrite | MIT | `uv tool install git-filter-repo` |
| `ripgrep` | Fast regex scanner for internal-ref patterns | MIT / Unlicense | `sudo apt install ripgrep` (or pre-installed on most dev boxes) |
| `syft` | SBOM generation (SPDX / CycloneDX) | Apache-2.0 | `curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh \| sh -s -- -b ~/.local/bin` |
| `grant` | License-policy enforcement against SBOM | Apache-2.0 | `curl -sSfL https://raw.githubusercontent.com/anchore/grant/main/install.sh \| sh -s -- -b ~/.local/bin` |
| `grype` | Vulnerability scan against SBOM | Apache-2.0 | `curl -sSfL https://raw.githubusercontent.com/anchore/grype/main/install.sh \| sh -s -- -b ~/.local/bin` |
| `osv-scanner` | Google OSV.dev vulnerability scanner with call-graph analysis | Apache-2.0 | `go install github.com/google/osv-scanner/cmd/osv-scanner@latest` (or release binary) |
| `pinact` | SHA-pin GitHub Actions references | MIT | `go install github.com/suzuki-shunsuke/pinact/cmd/pinact@latest` |
| `gh` | GitHub CLI for API and repo operations | MIT | `sudo apt install gh` or [GitHub docs](https://github.com/cli/cli#installation) |
| `pre-commit` | Git hook installer | MIT | `uv tool install pre-commit` |

### Tier 1 invocation per check

| Check domain | Tool | Command template |
|--------------|------|-------------------|
| OSS-SEC-01 (tree) | gitleaks | `gitleaks detect --no-git --source {target} --report-format sarif --report-path {target}/.iw/gitleaks-tree.sarif` |
| OSS-SEC-02 (history) | gitleaks | `gitleaks detect --source {target} --log-opts='--all' --report-format sarif --report-path {target}/.iw/gitleaks-history.sarif` |
| OSS-HIST-02 (rewrite) | git-filter-repo | emitted in publish-playbook only (never auto-run) |
| OSS-REF-01..05 | ripgrep | `rg -n --hidden --no-messages -g '!docs/' -g '!tests/' '{pattern}' {target}` |
| OSS-DEP-05 (SBOM) | syft | `syft {target} -o spdx-json={target}/.iw/sbom.spdx.json -o cyclonedx-json={target}/.iw/sbom.cyclonedx.json` |
| OSS-DEP-01 (licenses) | grant | `grant check {target}/.iw/sbom.spdx.json --config .claude/skills/iw-oss-publish/references/grant-policy.yaml` |
| OSS-DEP-03/04 (vulns) | grype | `grype sbom:{target}/.iw/sbom.spdx.json --fail-on critical -o json` |
| OSS-DEP-03/04 (vulns, Py/Rs/Go) | osv-scanner | `osv-scanner --lockfile={target}/{lockfile}` per ecosystem |
| OSS-CI-02 | pinact | `pinact run --check` (in `{target}`) |
| OSS-GH-* | gh | `gh api /repos/{org}/{repo}/{endpoint}` |

---

## Tier 2 — Recommended

Installed on request (flag `--tier2` to `install_tools.sh`) or when the skill detects the relevant ecosystem. Missing Tier-2 tools demote the related checks from MUST/SHOULD to INFO with a warning.

| Tool | Purpose | License | Install | When used |
|------|---------|---------|---------|-----------|
| `trufflehog` | One-time pre-flip history audit with live verification | AGPL-3.0 | `curl -sSfL https://raw.githubusercontent.com/trufflesecurity/trufflehog/main/scripts/install.sh \| sh -s -- -b ~/.local/bin` | `publish` mode only, single history scan |
| `semgrep` | AST-aware internal-ref rules | LGPL-2.1 (CE) | `uv tool install semgrep` | OSS-REF-06 for Python/TS/Go projects |
| `licensee` | GitHub-compatible LICENSE detection | MIT | `gem install licensee` (requires Ruby) | OSS-LIC-02 verification; falls back to syft license detection when Ruby unavailable |
| `pip-licenses` | Python dep license text for THIRD_PARTY_LICENSES | MIT | `uv tool install pip-licenses` | OSS-DEP-06 for Python projects |
| `license-checker` | npm dep license dump | MIT (Apache/BSD OK) | `npm install -g license-checker` | OSS-DEP-06 for Node projects |
| `go-licenses` | Go module license detection | Apache-2.0 | `go install github.com/google/go-licenses@latest` | OSS-DEP-06 for Go projects |
| `cosign` | Sigstore keyless signing | Apache-2.0 | `go install github.com/sigstore/cosign/v2/cmd/cosign@latest` | Reference in release-please workflow template |
| `git-sizer` | Large-object / history size analysis | MIT | `go install github.com/github/git-sizer@latest` | OSS-HYG-04, OSS-HYG-05 |
| `reuse` | FSFE per-file SPDX headers | GPL-3.0 | `uv tool install reuse` | OSS-LIC-08 (opt-in only) |
| `detect-secrets` | Baseline-file brownfield scanner | Apache-2.0 | `uv tool install detect-secrets` | OSS-SEC-05 (opt-in) |
| `pip-audit` | Python vuln scanner | Apache-2.0 | `uv tool install pip-audit` | OSS-DEP-07 for Python |
| `cargo-audit` | Rust vuln scanner | Apache/MIT | `cargo install cargo-audit` | OSS-DEP-07 for Rust |
| `govulncheck` | Go vuln scanner | BSD-3-Clause | `go install golang.org/x/vuln/cmd/govulncheck@latest` | OSS-DEP-07 for Go |

---

## External Services (not installed; referenced)

These live on GitHub / GitHub Apps / GitHub Actions. The skill emits install/configuration instructions; it never performs the installation itself.

| Service | Purpose | Action |
|---------|---------|--------|
| `cncf/dco2` GitHub App | DCO enforcement on PRs | One-time org install at https://github.com/apps/dco; surfaced in publish-playbook |
| `actions/attest-build-provenance@v2` | SLSA build provenance attestation | Referenced in release-please workflow template (OSS-REL-04) |
| `slsa-framework/slsa-github-generator` | SLSA Level 3 reusable workflows | Recommended in release-please template for packages published to PyPI/npm/crates.io |
| `ossf/scorecard-action` | OpenSSF Scorecard scoring | Referenced in scorecard.yml template (OSS-CI-07) |
| `github/codeql-action` | CodeQL SAST | Referenced in codeql.yml template (OSS-CI-06) |

---

## Defaults

Used when `.iw/oss-publish.toml` is absent or missing keys.

| Key | Default value |
|-----|---------------|
| `project_name` | basename of target directory |
| `license` | `Apache-2.0` |
| `company_legal_name` | `Innovation Ways - Unipessoal LDA` |
| `company_brand` | `Innovation Ways` |
| `company_github_org` | `innovation-ways` |
| `company_contact_email` | `info@innovation-ways.com` |
| `homepage` | `https://innovation-ways.com` |
| `contributor_agreement` | `DCO` |
| `coc_version` | `v3` |
| `sbom_formats` | `["spdx", "cyclonedx"]` |
| `internal_email_domains` | `["innovation-ways.com"]` |
| `internal_fqdn_suffixes` | `[".internal", ".corp", ".local", ".lan", ".intranet"]` |
| `disable_gh_live_checks` | `false` |

---

## Tool Version Pinning

The skill pins minimum tool versions in `scripts/install_tools.sh`. If an older version is detected, the installer refuses to proceed:

| Tool | Minimum version | Rationale |
|------|-----------------|-----------|
| gitleaks | 8.20.0 | SARIF output + latest generic-secret detectors |
| git-filter-repo | 2.47.0 | Git 2.36+ compatibility |
| syft | 1.14.0 | CycloneDX v1.6 support |
| grant | 0.3.0 | Policy DSL stabilized |
| grype | 0.85.0 | OSV.dev integration |
| osv-scanner | 2.0.0 | V2 call-graph analysis |
| pinact | 3.9.0 | SHA-pin with inline version comments |
| gh | 2.62.0 | `gh api --method PUT` for branch-protection endpoints |
| pre-commit | 4.0.1 | Python 3.13 support |

Version drift on Tier-2 tools is tolerated; the skill emits a warning but proceeds.

---

## Runtime Cost (approximate, medium repo ~10k files / 1k commits)

| Tier | Cold-cache runtime | Warm-cache runtime |
|------|---------------------|---------------------|
| Tier 1 only | 90-120s | 25-40s |
| Tier 1 + Tier 2 (Python project) | 150-180s | 40-60s |
| Tier 1 + Tier 2 (polyglot: Py/JS/Go) | 200-250s | 60-90s |

Grype and osv-scanner download vulnerability databases on first run (~200 MB total). Subsequent runs use the local cache.

---

## Removing or Overriding a Tool

To disable a tool (e.g., `licensee` when Ruby is unavailable), add to `.iw/oss-publish.toml`:

```toml
[tools.disabled]
licensee = "Ruby unavailable in this CI image"

[tools.override]
gitleaks = "/usr/local/bin/gitleaks"  # custom install path
```

Disabling a tool demotes the checks that depend on it to INFO severity with a `[tool-unavailable]` tag on the finding.
