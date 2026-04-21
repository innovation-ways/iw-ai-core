# Fix Recipes

One recipe per auto-fixable check. Each recipe describes the exact action `make_oss` mode takes, the input files/config it reads, and the output it produces.

General rules:

- Every recipe is **idempotent** — re-running produces the same result (or a no-op).
- Every recipe writes to the working tree on the `iw-oss-publish/prep-YYYY-MM-DD` branch. **No commits.**
- Templates under `.claude/skills/iw-oss-publish/templates/` are rendered with `{{var}}` substitution from the resolved config.
- If the target file already exists, the recipe either skips it or merges in new content (per-recipe behavior documented below).

---

## OSS-ENV-04 — Add `.iw/` to `.gitignore`

**Trigger**: `.iw/` missing from `.gitignore`.
**Action**: Append `.iw/\n` to `.gitignore` (creating the file if absent).
**Merge behavior**: Append-only; never deletes existing entries.

---

## OSS-HYG-01 — `.gitignore` excludes secret file patterns

**Trigger**: any of `.env`, `*.pem`, `*.key`, `*.pfx`, `*.p12`, `private-key.*` not in `.gitignore`.
**Action**: Append the missing patterns with a `# iw-oss-publish: secret hygiene` comment block.
**Merge behavior**: Append-only.

---

## OSS-HYG-03 — `.gitignore` excludes language artifacts

**Trigger**: per detected ecosystem, the standard ignores for that language are missing.
**Action**: Append the relevant per-language `.gitignore` stanza (sourced from https://github.com/github/gitignore master copies, bundled under `templates/gitignore/`).
**Merge behavior**: Append-only; skip stanza if it's already wholly present.

Stanzas bundled:
- `Python.gitignore` (for Python projects)
- `Node.gitignore` (for Node/npm projects)
- `Go.gitignore` (for Go)
- `Rust.gitignore` (for Cargo)
- `JetBrains.gitignore` (for IDE files — always applied)
- `macOS.gitignore` + `Linux.gitignore` + `Windows.gitignore` (always applied)

---

## OSS-SEC-04 — `.gitleaks.toml` present with IW-specific rules

**Trigger**: `.gitleaks.toml` missing.
**Action**: Render `templates/gitleaks.toml.j2` with:
- `{{internal_email_domains}}` (from config, default `["innovation-ways.com"]`)
- `{{internal_fqdn_suffixes}}` (from config)
**Merge behavior**: Write only if absent; if present, log "custom gitleaks config detected; leaving untouched."

---

## OSS-SEC-05 — detect-secrets baseline (opt-in)

**Trigger**: config flag `[secrets] detect_secrets_baseline = true` AND no `.secrets.baseline` file.
**Action**: Run `detect-secrets scan --baseline .secrets.baseline` and write the output.
**Merge behavior**: Never overwrite; skip if already present.

---

## OSS-CI-02 — SHA-pin GitHub Actions

**Trigger**: `pinact run --check` reports any unpinned third-party action.
**Action**: Run `pinact run` (in-place rewrite of `.github/workflows/*.yml`) to SHA-pin with inline `# vX.Y.Z` comments.
**Merge behavior**: pinact modifies files in place; changes surface in the branch's diff.

---

## OSS-CI-06 — `.github/workflows/codeql.yml`

**Trigger**: File absent.
**Action**: Render `templates/.github/workflows/codeql.yml` with detected languages (`{{codeql_languages}}`: `python`, `javascript`, `go`, etc.).
**Merge behavior**: Write only if absent.

---

## OSS-CI-07 — `.github/workflows/scorecard.yml`

**Trigger**: File absent.
**Action**: Render `templates/.github/workflows/scorecard.yml` (OpenSSF Scorecard action pinned to latest SHA).
**Merge behavior**: Write only if absent.

---

## OSS-CI-08 — `.github/dependabot.yml`

**Trigger**: File absent.
**Action**: Render `templates/.github/dependabot.yml` with enabled ecosystems per detected lockfiles (`pip`, `npm`, `cargo`, `gomod`, `github-actions`).
**Merge behavior**: Write only if absent; if present, log and skip.

---

## OSS-CI-09 — `.github/workflows/compliance-scan.yml`

**Trigger**: File absent.
**Action**: Render `templates/.github/workflows/compliance-scan.yml` (runs `iw-oss-publish scan` on every PR to `main`).
**Merge behavior**: Write only if absent.

---

## OSS-DEP-05 — SBOM

**Trigger**: `.iw/sbom.spdx.json` or `.iw/sbom.cyclonedx.json` missing.
**Action**: Run `syft {target} -o spdx-json={path}` and `syft {target} -o cyclonedx-json={path}`.
**Merge behavior**: Always regenerate (SBOM is an artifact, not source).

---

## OSS-DEP-06 — `THIRD_PARTY_LICENSES.md`

**Trigger**: File missing OR more than 30 days old OR SBOM has changed since last generation.
**Action**: Regenerate by concatenating outputs from per-ecosystem tools:
- Python: `pip-licenses --format=markdown --with-license-file --with-notice-file`
- Node: `license-checker --json --out {temp}; convert to markdown`
- Go: `go-licenses report ./... --template {templates/go_licenses.tmpl}`
Write to `THIRD_PARTY_LICENSES.md` in repo root with sections per ecosystem.
**Merge behavior**: Always regenerate; diff against prior content shown in branch.

---

## OSS-LIC-01 — `LICENSE` file present

**Trigger**: No `LICENSE*`, `COPYING`, or `LICENSE/` found.
**Action**: Render `templates/LICENSE-{{config.license}}.j2` to `LICENSE` with:
- `{{year}}` → current year
- `{{company_legal_name}}` → `"Innovation Ways - Unipessoal LDA"`
**Supported licenses**: `Apache-2.0`, `MIT` (others can be added to templates/; skill warns if unsupported).
**Merge behavior**: Write only if absent.

---

## OSS-LIC-04 — Copyright line uses legal entity

**Trigger**: Existing `LICENSE` missing the `{{company_legal_name}}` string.
**Action**: Prompt user via punchlist — do not auto-edit LICENSE (too risky).
**Merge behavior**: No-op in make_oss; surfaces in punchlist instead.

*(Exception: for LICENSEs generated by this skill in the same run, the line is correct by construction.)*

---

## OSS-LIC-05 — Copyright year

**Trigger**: Year in LICENSE not in `[current_year - 1, current_year]` range.
**Action**: Rewrite the year to `"YYYY-current_year"` range if existing year is older, or to current year if within range.
**Merge behavior**: In-place substitution with pre-edit backup in `.iw/backups/LICENSE.pre-YYYY-MM-DD`.

---

## OSS-LIC-06 — `NOTICE` for Apache-2.0

**Trigger**: `config.license == "Apache-2.0"` AND `NOTICE` missing.
**Action**: Render `templates/NOTICE.j2`:
```
{{project_name}}
Copyright {{year}} {{company_legal_name}}

This product includes software developed at
{{company_brand}} (https://innovation-ways.com/).
```
Then append the aggregated `NOTICE` content from Apache-2.0 dependencies (parsed from syft SBOM + each dep's upstream NOTICE if retrievable).
**Merge behavior**: Write only if absent; log upstream-NOTICE aggregation count.

---

## OSS-LIC-07 — NOTICE aggregates upstream attributions

**Trigger**: NOTICE exists but does not contain attributions from Apache-2.0 deps present in SBOM.
**Action**: Append a `## Third-party Apache-2.0 attributions` section with attributions from upstream NOTICE files (best-effort; some PyPI/npm packages do not ship a NOTICE, in which case a marker line is added).
**Merge behavior**: Append only; never modifies existing content.

---

## OSS-CH-01 — `README.md` stub

**Trigger**: File absent OR missing a clear title/description/install/usage/license section.
**Action**: Render `templates/README.md.j2` with:
- `{{project_name}}`, `{{project_description}}`, `{{license}}`, `{{company_brand}}`, `{{homepage}}`, `{{coc_version}}`
- Badges: license, OpenSSF Scorecard, CI
- Sections: Overview (placeholder), Installation (placeholder), Usage (placeholder), Contributing, Code of Conduct, Security, License, Trademark
**Merge behavior**: Write only if absent. If present but incomplete, surface a SHOULD warning for the human to fill gaps.

---

## OSS-CH-02 — `SECURITY.md`

**Trigger**: File absent.
**Action**: Render `templates/SECURITY.md.j2` with supported-versions placeholder, PVR link, `{{company_contact_email}}`, and a 3-business-day SLA statement.
**Merge behavior**: Write only if absent.

---

## OSS-CH-03 — `CODE_OF_CONDUCT.md`

**Trigger**: File absent.
**Action**: Render `templates/CODE_OF_CONDUCT.md` — full Contributor Covenant v3 text with `{{company_contact_email}}` substituted into the enforcement contact line.
**Merge behavior**: Write only if absent.

---

## OSS-CH-04 — CoC version is v2.1+

**Trigger**: Existing `CODE_OF_CONDUCT.md` identifies as Contributor Covenant older than v2.1.
**Action**: Emit warning in punchlist — do not auto-replace a custom CoC. The maintainer must decide.
**Merge behavior**: No-op in make_oss.

---

## OSS-CH-05 — CoC contact is group email

**Trigger**: Detected enforcement contact does not match `{{company_contact_email}}` OR looks like a personal email (`firstname.lastname@`).
**Action**: Surface in punchlist.
**Merge behavior**: No auto-edit for existing CoCs; only the freshly-generated CoC uses the configured email.

---

## OSS-CH-06 — `CONTRIBUTING.md`

**Trigger**: File absent.
**Action**: Render `templates/CONTRIBUTING.md.j2` with:
- How to file issues
- Branch naming conventions
- `{{contributor_agreement}}` section (DCO by default — includes `git commit -s` instructions; CLA variant available)
- Coding style pointer
- PR checklist
**Merge behavior**: Write only if absent.

---

## OSS-CH-07 — CONTRIBUTING explains DCO

**Trigger**: Existing `CONTRIBUTING.md` does not grep for "Signed-off-by" or "DCO".
**Action**: Surface in punchlist; do not edit existing `CONTRIBUTING.md`.
**Merge behavior**: No-op in make_oss. If `config.contributor_agreement == "CLA"`, the check is reversed (warn if DCO language present).

---

## OSS-CH-08 — `CODEOWNERS`

**Trigger**: `.github/CODEOWNERS` absent.
**Action**: Render `templates/.github/CODEOWNERS.j2`:
```
* @{{company_github_org}}/maintainers
```
**Merge behavior**: Write only if absent.

---

## OSS-CH-09, OSS-CH-10 — PR / Issue templates

**Trigger**: File(s) absent.
**Action**: Render `.github/PULL_REQUEST_TEMPLATE.md`, `.github/ISSUE_TEMPLATE/bug_report.yml`, `.github/ISSUE_TEMPLATE/feature_request.yml`.
**Merge behavior**: Write only if absent.

---

## OSS-CH-11 — `SUPPORT.md`

**Trigger**: File absent.
**Action**: Render `templates/SUPPORT.md.j2` with Discussions link + `{{company_contact_email}}`.
**Merge behavior**: Write only if absent.

---

## OSS-TM-01 — `TRADEMARK.md`

**Trigger**: File absent.
**Action**: Render `templates/TRADEMARK.md.j2` with:
- `{{company_brand}}` and `{{company_legal_name}}` declarations
- Permitted nominative uses
- Prohibited uses
- Contact: `{{company_contact_email}}`
**Merge behavior**: Write only if absent.

---

## OSS-TM-08 — README trademark notice

**Trigger**: `TRADEMARK.md` absent AND README does not contain a trademark line.
**Action**: Append a `## Trademark` section to README referencing the mark.
**Merge behavior**: Only appended if the README was generated in this same run (not retroactively).

---

## OSS-CA-01 — DCO configuration detection

**Trigger**: `config.contributor_agreement == "DCO"` AND no `.github/dco.yml` AND no org-level dco2 install detected.
**Action**: Render `templates/.github/dco.yml`:
```yaml
require:
  members: true
```
And add a punchlist item: "Install cncf/dco2 GitHub App at org level: https://github.com/apps/dco"
**Merge behavior**: Write only if absent.

---

## OSS-REL-01 — `CHANGELOG.md` stub

**Trigger**: File absent.
**Action**: Render `templates/CHANGELOG.md.j2` with Keep-a-Changelog v1.1.0 skeleton:
```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
```
**Merge behavior**: Write only if absent.

---

## OSS-REL-03 — `release-please.yml`

**Trigger**: File absent.
**Action**: Render `templates/.github/workflows/release-please.yml` using `googleapis/release-please-action@v4` with per-ecosystem release-type detection.
**Merge behavior**: Write only if absent.

---

## OSS-REL-04 — Build provenance attestation in release workflow

**Trigger**: No reference to `actions/attest-build-provenance` in any `.github/workflows/*.yml`.
**Action**: The rendered `release-please.yml` template already includes `actions/attest-build-provenance@v2` steps. If the template was already present without the step, surface in punchlist.
**Merge behavior**: Only applies when release-please.yml is written by this skill in the same run.

---

## Pre-commit Config — `.pre-commit-config.yaml`

**Trigger**: File absent.
**Action**: Render `templates/.pre-commit-config.yaml.j2` with:
- `gitleaks` pre-commit hook (pinned)
- `pinact` check
- `conventional-commits` commit-msg hook
- `check-yaml`, `end-of-file-fixer`, `trailing-whitespace` (pre-commit/pre-commit-hooks)
**Merge behavior**: Write only if absent.

---

## `.iw/oss-publish.toml` Resolved Config

**Trigger**: File absent.
**Action**: Write the resolved config (merged defaults + any CLI overrides used in this run) to `.iw/oss-publish.toml` so future runs are reproducible.
**Merge behavior**: Write only if absent; `scan` mode never writes config.

---

## Summary Table: Check → Recipe Map

| Check ID | Recipe | Idempotent | Writes to target? |
|----------|--------|------------|-------------------|
| OSS-ENV-04 | Append `.iw/` to `.gitignore` | Yes | `.gitignore` |
| OSS-HYG-01 | Append secret patterns to `.gitignore` | Yes | `.gitignore` |
| OSS-HYG-03 | Append language stanzas to `.gitignore` | Yes | `.gitignore` |
| OSS-SEC-04 | Write `.gitleaks.toml` | Yes | `.gitleaks.toml` |
| OSS-SEC-05 | Write `.secrets.baseline` (opt-in) | Yes | `.secrets.baseline` |
| OSS-CI-02 | `pinact run` | Yes | `.github/workflows/*` |
| OSS-CI-06 | Write `codeql.yml` | Yes | `.github/workflows/` |
| OSS-CI-07 | Write `scorecard.yml` | Yes | `.github/workflows/` |
| OSS-CI-08 | Write `dependabot.yml` | Yes | `.github/dependabot.yml` |
| OSS-CI-09 | Write `compliance-scan.yml` | Yes | `.github/workflows/` |
| OSS-DEP-05 | Regenerate SBOM | Yes | `.iw/sbom.*` |
| OSS-DEP-06 | Regenerate `THIRD_PARTY_LICENSES.md` | Yes | `THIRD_PARTY_LICENSES.md` |
| OSS-LIC-01 | Write `LICENSE` | Yes | `LICENSE` |
| OSS-LIC-05 | Fix copyright year | Yes | `LICENSE` |
| OSS-LIC-06 | Write `NOTICE` (Apache-2.0) | Yes | `NOTICE` |
| OSS-LIC-07 | Append upstream attributions to NOTICE | Yes | `NOTICE` |
| OSS-CH-01 | Write `README.md` | Yes | `README.md` |
| OSS-CH-02 | Write `SECURITY.md` | Yes | `SECURITY.md` |
| OSS-CH-03 | Write `CODE_OF_CONDUCT.md` (v3) | Yes | `CODE_OF_CONDUCT.md` |
| OSS-CH-06 | Write `CONTRIBUTING.md` | Yes | `CONTRIBUTING.md` |
| OSS-CH-08 | Write `CODEOWNERS` | Yes | `.github/CODEOWNERS` |
| OSS-CH-09 | Write `PULL_REQUEST_TEMPLATE.md` | Yes | `.github/` |
| OSS-CH-10 | Write `ISSUE_TEMPLATE/*.yml` | Yes | `.github/ISSUE_TEMPLATE/` |
| OSS-CH-11 | Write `SUPPORT.md` | Yes | `SUPPORT.md` |
| OSS-TM-01 | Write `TRADEMARK.md` | Yes | `TRADEMARK.md` |
| OSS-TM-08 | Append trademark notice to README | Yes | `README.md` |
| OSS-CA-01 | Write `.github/dco.yml` | Yes | `.github/` |
| OSS-REL-01 | Write `CHANGELOG.md` stub | Yes | `CHANGELOG.md` |
| OSS-REL-03 | Write `release-please.yml` | Yes | `.github/workflows/` |
| OSS-ENV-03 | Write `.iw/oss-publish.toml` | Yes | `.iw/` |
| Pre-commit | Write `.pre-commit-config.yaml` | Yes | `.pre-commit-config.yaml` |

---

## Not Auto-Fixed (surfaced in punchlist)

The following checks are detection-only — no recipe auto-applies them. See `compliance-punchlist.md` for how these surface to the user.

- OSS-SEC-01..03 — secret removal (requires history rewrite)
- OSS-HIST-01..06 — history strategy decisions
- OSS-REF-01..06 — internal-reference remediation (code edits)
- OSS-HYG-02, OSS-HYG-04, OSS-HYG-05 — tracked sensitive files / large objects
- OSS-DEP-01..04, OSS-DEP-07 — license incompatibility, CVEs (requires dep changes)
- OSS-LIC-02, OSS-LIC-04 — existing LICENSE verification (human review)
- OSS-PII-01..03 — PII in fixtures (code edits)
- OSS-EXP-01..02 — crypto classification (legal judgment)
- OSS-TM-02..07 — name collision and trademark searches (external actions)
- OSS-CA-03 — branch protection (gh playbook, not make_oss)
- OSS-REL-02, OSS-REL-05 — conventional commits and semver tags (behavioral)
- OSS-GH-* — GitHub live settings (publish playbook only)
- OSS-GOV-01..02 — governance docs (maintainer-count-dependent)
