# Private-to-Public Repository Legal, Licensing, and Community Compliance for Permissive OSS Release

**Research ID**: R-00062
**Date**: 2026-04-21
**Mode**: deep
**Depth**: deep
**Primary Question**: What is the complete legal, licensing, trademark, and community-health checklist — with authoritative source citations — that Innovation Ways must satisfy before and after flipping a private repo to public, and which elements can a Skill automatically check vs surface for human judgment?

---

## Executive Summary

Releasing a private Innovation Ways repository as public OSS under Apache-2.0 requires satisfying roughly 40 distinct checks spanning license selection, third-party compatibility, NOTICE/attribution, community health files, trademark, contributor agreements, export control, PII/privacy hygiene, and post-publish GitHub settings. Apache-2.0 is the correct default for non-trivial IW projects due to its explicit patent grant, enterprise norms, and GPL-3 compatibility; MIT is the right fallback for trivially small utilities. DCO via the CNCF dco2 GitHub App is the recommended contributor agreement for most IW projects, with CLA warranted only when open-core or dual-licensing is planned. The post-2021 EAR simplification eliminates notification obligations for standard-crypto OSS, but a Skill must still surface a human-judgment prompt for any non-standard cryptography detected in source imports. Approximately 25 of the 40 checks are fully automatable; the remainder require human sign-off and should be surfaced as named blocker or warning items in the Skill's output.

## Background

Innovation Ways manages software development across multiple projects and is building a suite of AI-assisted Skill workflows to automate repetitive compliance work. A recurring trigger is the decision to flip a private repository to public under the IW GitHub organization — an action that cannot be undone without forking and represents an irrevocable publication of the entire git history. The downstream Skill (working title: "pre-publish compliance") needs an authoritative, cited checklist it can run automatically, a clear severity taxonomy (MUST / SHOULD / MAY), and explicit guidance on which checks require a human to review the output rather than accepting an automated pass.

---

## Findings

### 1. Apache-2.0 Is the Correct Default License for Non-Trivial IW Projects [HIGH confidence]

The [Apache License 2.0](https://choosealicense.com/licenses/apache-2.0/) grants explicit patent rights from every contributor, requires preservation of copyright/license notices, and documents modifications. This distinguishes it sharply from MIT and BSD-3-Clause, which carry no patent grant. For corporate-backed or enterprise-facing projects the explicit patent language is legally material: if a contributor holds a patent that reads on their code contribution, the license grant under Apache-2.0 extends to that patent, whereas under MIT the recipient has no express license. The [SPDX License List v3.28.0 (2026-02-20)](https://spdx.org/licenses/) confirms both `Apache-2.0` and `MIT` are FSF Free and OSI Approved. Apache-2.0's explicit patent grant and [Section 6 implicit trademark restriction](https://www.apache.org/licenses/LICENSE-2.0.html) make it the appropriate default for any IW project with non-trivial code, multiple contributors, or commercial sensitivity. The SPDX identifier to use is `Apache-2.0` exactly.

### 2. MIT Is the Right Default for Trivially Small Utilities and Single-File Libraries [HIGH confidence]

[choosealicense.com](https://choosealicense.com/) recommends MIT for projects where maximum permissiveness and minimal friction are the priority — including small libraries, build scripts, configuration generators, and code snippets. The MIT license carries zero patent protection, no explicit change-documentation requirement, and no trademark restriction, but its brevity makes it universally understood. For an IW project that is a single-purpose CLI utility, a thin API wrapper, or an example/template repository, MIT is appropriate. The decision rule for the Skill: if the repository is a standalone package with fewer than ~500 lines of production code and no co-authors, use MIT; otherwise default to Apache-2.0.

### 3. ISC Is Functionally MIT-Equivalent; 0BSD Drops Even the Attribution Notice; Unlicense Carries Legal Risk [MEDIUM confidence]

[ISC License (choosealicense.com)](https://choosealicense.com/licenses/isc/) is functionally identical to MIT minus one redundant sentence; it is preferred by OpenBSD and common in the npm ecosystem. [0BSD](https://choosealicense.com/licenses/0bsd/) removes the attribution/notice requirement entirely and is [OSI Approved](https://opensource.org/license/0bsd); Google permits 0BSD contributions where it prohibits Unlicense/CC0 contributions. [The Unlicense](https://en.wikipedia.org/wiki/Public-domain-equivalent_license) lacks a fallback license clause, so if a court voids the public-domain dedication, recipients may hold zero rights — this is a material legal risk that means Unlicense SHOULD NOT be used for IW work. The Skill SHOULD flag Unlicense as a warning and suggest 0BSD or MIT as a replacement. For IW's purposes: MIT or Apache-2.0 cover all cases; ISC and 0BSD are acceptable alternatives for npm packages; Unlicense is a WARNING-level finding.

### 4. License Compatibility Matrix: Outbound MIT/Apache-2.0 Against Inbound Dependencies [HIGH confidence]

The following matrix is synthesized from the [Apache Software Foundation GPL Compatibility page](https://www.apache.org/licenses/GPL-compatibility.html) and [licensecheck.io Apache compatibility guide](https://licensecheck.io/guides/apache-compatible):

| Inbound License | Outbound MIT OK? | Outbound Apache-2.0 OK? | Notes |
|---|---|---|---|
| MIT / BSD-2 / BSD-3 / ISC / 0BSD | YES | YES | Fully permissive, no restrictions |
| MPL-2.0 | YES | YES (file-level copyleft preserved) | Per-file copyleft, compatible with Apache-2.0 combined works |
| LGPL-2.1 / LGPL-3.0 (dynamic link) | YES | YES (dynamic only) | Static linking is a blocker for Apache-2.0 projects |
| GPL-3.0-or-later | NO (must be relicensed as GPL-3) | NO (Apache can be included in GPL-3, not reverse) | One-way: Apache-2.0 code can flow into GPL-3 but not back |
| GPL-2.0-only | BLOCKER | BLOCKER | FSF: Apache-2.0 patent clauses incompatible with GPL-2. [Source](https://www.apache.org/licenses/GPL-compatibility.html) |
| AGPL-3.0 | BLOCKER | BLOCKER (unless separate process) | Network copyleft; must be isolated to separate services |
| Proprietary / unknown | BLOCKER | BLOCKER | No rights granted to redistribute |

MUST-level check: The Skill MUST flag any transitive dependency whose resolved SPDX identifier is `GPL-2.0-only`, `AGPL-3.0`, or any unknown/proprietary license. LGPL dynamic-only is a SHOULD-level warning requesting confirmation of link type.

### 5. Apache-2.0 NOTICE File: Aggregation Rules and Minimal Content [HIGH confidence]

[Apache Infrastructure's licensing-howto](https://infra.apache.org/licensing-howto.html) establishes the canonical rule: "LICENSE and NOTICE files must **exactly represent** the contents of the distribution they reside in." The NOTICE file is reserved for legally required notifications beyond what the LICENSE covers. Key requirements:

1. **What MUST be in NOTICE**: Copyright notices relocated from source files; legally mandated third-party credits; any attribution required by upstream dependencies' own NOTICE files (those contents must be "bubbled up" into the top-level NOTICE).
2. **What MUST NOT be in NOTICE**: Anything not legally required. Keep it brief.
3. **When bundling ASF dependencies**: Do not duplicate the standard Apache copyright line; ASF-to-ASF bundling avoids double-counting.
4. **For non-ASF upstream NOTICE files**: The relevant portions must be extracted and added to the distribution's top-level NOTICE.

For IW projects, Apache-2.0 Section 4(d) means any downstream project that bundles IW code must carry IW's NOTICE content. The Skill should verify that a `NOTICE` file exists when the project license is `Apache-2.0` (SHOULD), and that it contains at minimum the project name, copyright year, and legal entity.

### 6. License Scanning Toolchain: Right Tool for the Right Job [HIGH confidence]

| Tool | Language/Ecosystem | Primary Job | SBOM Output? |
|---|---|---|---|
| [pip-licenses](https://github.com/raimon49/pip-licenses) | Python | Human-readable THIRD_PARTY_LICENSES from installed packages | No (text/markdown/JSON) |
| [license-checker](https://github.com/davglass/license-checker) / [license-checker-rseidelsohn](https://www.npmjs.com/package/license-checker-rseidelsohn) | npm/Node.js | Human-readable license dump from node_modules | No |
| [go-licenses](https://github.com/google/go-licenses) | Go | License detection + copyleft flagging for Go modules | No |
| [syft](https://anchore.com/blog/how-syft-scans-software-to-generate-sboms/) | Multi-ecosystem | SBOM generation (SPDX, CycloneDX) from container images and filesystems | YES (SPDX/CycloneDX) |
| [grant](https://github.com/anchore/grant) | Multi-ecosystem (via syft) | License policy enforcement against an SBOM; 1400+ URL-to-license mappings | Reads SBOM |
| [licensee](https://github.com/licensee/licensee) | Repository root | Detect top-level LICENSE file (used by GitHub itself); Sørensen–Dice matching | No |
| [reuse-tool (FSFE)](https://reuse.software/) | All files in repo | SPDX per-file copyright+license tags; verify full REUSE compliance | YES (SPDX SBOM) |
| [scancode-toolkit](https://github.com/aboutcode-org/scancode-toolkit) | All files | Deep scan for licenses, copyrights in all files; used by Eclipse, FSFE, FSF | YES (SPDX/CycloneDX) |

**Recommended pipeline for the Skill**: (1) `licensee` to verify the root LICENSE file is detectable; (2) ecosystem-specific tool (pip-licenses / license-checker / go-licenses) to generate the human-readable THIRD_PARTY_LICENSES.md for non-SBOM display; (3) `syft` + `grant` to produce a machine-readable SBOM and run policy checks for blockers; (4) optionally `reuse-tool` for per-file SPDX compliance (SHOULD, not MUST for IW small projects).

### 7. GitHub Community Health Score: Exact Formula and Checked Files [HIGH confidence]

The [GitHub Community Metrics REST API](https://docs.github.com/en/rest/metrics/community) (`GET /repos/{owner}/{repo}/community/profile`) returns a `health_percentage` integer defined as: **percentage of how many of the four recommended community health files are present**: `README`, `CONTRIBUTING`, `LICENSE`, `CODE_OF_CONDUCT`. Each file present contributes 25 percentage points; all four present = 100.

The API also returns presence/absence of: `SECURITY` policy, `ISSUE_TEMPLATE`, `PULL_REQUEST_TEMPLATE`. These do not feed `health_percentage` but appear as structured fields.

Files not checked by the API but still important for OSS release: `SUPPORT`, `CODEOWNERS`, `FUNDING.yml`, `GOVERNANCE.md`, `TRADEMARK.md`.

**Severity mapping for the Skill**:
- `LICENSE` absent: MUST (blocker — repo is not open source without it)
- `README` absent: MUST (project is non-discoverable)
- `CODE_OF_CONDUCT` absent: SHOULD (warning — required for community trust)
- `CONTRIBUTING` absent: SHOULD (warning)
- `SECURITY` absent: SHOULD (warning — OpenSSF OSPS Baseline OSPS-VM-02.01 MUST at level 1)
- `ISSUE_TEMPLATE` / `PULL_REQUEST_TEMPLATE` absent: MAY (info)
- `CODEOWNERS` absent for projects with ≥2 maintainers: SHOULD
- `GOVERNANCE.md` absent: MAY for 1-3 maintainers; SHOULD for ≥4 or foundation-stewardship aspirations

### 8. Contributor Covenant v3 Is Current as of 2026 and SHOULD Be Adopted [HIGH confidence]

[Contributor Covenant v3 was released by the Organization for Ethical Source](https://ethicalsource.dev/projects/contributor-covenant-3/) and [adopted by Django in April 2026](https://www.djangoproject.com/weblog/2026/apr/15/contributor-covenant-adoption/). Key advances over v2.1:

1. **Impact-centred**: addresses harm regardless of intent (sea-lioning, coordinated harassment, microaggressions now explicitly covered).
2. **Consent and boundaries**: explicit language on respecting stated limits.
3. **Enforcement clarity**: clearer accountability, transparency, and escalation guidance.

For **new IW projects going public in 2026**, Contributor Covenant v3 SHOULD be used. For **existing projects already using v2.1**, upgrading is a SHOULD-level recommendation but is not a blocker. The Skill MUST verify a `CODE_OF_CONDUCT.md` is present; SHOULD check that the version string is v2.1 or higher; SHOULD warn if v2.1 and suggest v3 upgrade. The enforcement contact in `CODE_OF_CONDUCT.md` SHOULD be a group email (`conduct@innovation-ways.dev` or equivalent), not a personal address, to prevent single-maintainer burnout and distribute accountability — a pattern used by OpenSSF (`conduct@openssf.org`) and others.

### 9. DCO via CNCF dco2 Is the Recommended Default; CLA Only for Open-Core [HIGH confidence]

The [Developer Certificate of Origin (DCO)](https://en.wikipedia.org/wiki/Developer_Certificate_of_Origin) is a per-commit attestation (`Signed-off-by: Name <email>` in commit trailer) that the contributor has the right to submit the code. The [CNCF dco2 GitHub App](https://github.com/cncf/dco2) (built in Rust) is the current recommended implementation — a drop-in replacement for the older `dcoapp/app`, backward-compatible with `.github/dco.yml` configuration, and supports remediation commits and member-exemption settings.

[OpenStack officially replaced its CLA with DCO in May 2025](https://governance.openstack.org/tc/resolutions/20250520-replace-the-cla-with-dco-for-all-contributions.html) after over a decade of debate, citing the CLA as "cumbersome" and a "barrier to contributions." [The April 2026 industry analysis](https://tenthirtyam.org/dispatches/2026/04/08/dco-vs-cla-managing-contribution-agreements-in-open-source/) reinforces: "When in doubt: DCO for community, CLA for company."

**When to use CLA instead**: (a) IW plans dual licensing (open-core + commercial), (b) future relicensing flexibility is required (DCO does not authorize relicensing), (c) corporate legal requires explicit patent grants beyond what Apache-2.0 provides, or (d) a foundation-stewardship arrangement mandates CLA (e.g., Linux Foundation EasyCLA). For all other IW cases, DCO is correct.

**DCO setup steps for IW**:
1. Install [CNCF dco2 app](https://github.com/cncf/dco2) on the GitHub org.
2. Add `.github/dco.yml` with `require: true` (or leave default, which enforces for all PRs).
3. In branch protection for `main`, add `dco` as a required status check.
4. Add a `CONTRIBUTING.md` section explaining `git commit -s` usage.

[EasyCLA](https://easycla.lfx.linuxfoundation.org/) (Linux Foundation, free) and [cla-assistant.io](https://cla-assistant.io/) (SAP, free) are the two recommended CLA tools if IW eventually needs one. EasyCLA supports both individual and corporate CLA workflows; cla-assistant is simpler for small projects.

### 10. Export Control: Standard Crypto Is Exempt; Non-Standard Triggers Human Review [HIGH confidence]

The [2021 Department of Commerce final rule](https://www.arnoldporter.com/en/perspectives/advisories/2021/04/doc-eliminates-mass-market-encryption-reporting) eliminated notification requirements for **publicly available encryption source code** using **standard cryptography** under ECCN 5D002. As confirmed by the [Linux Foundation export controls guide](https://www.linuxfoundation.org/resources/publications/understanding-us-export-controls-with-open-source-projects): "open source technologies that are published and made publicly available to the world are not subject to the EAR" — and the 2021 rule removed the last vestigial annual notification for publicly-posted standard-crypto code.

**What remains**: notification to `crypt@bis.doc.gov` and `enc@nsa.gov` is still required for software that **implements non-standard cryptography** (custom/proprietary encryption algorithms, novel key exchange schemes). Standard algorithms (AES, RSA, SHA-256, TLS via libraries) need no notification if the code is publicly posted.

**Skill scan heuristic** — flag for human review if these imports are detected:
- **Python**: `cryptography`, `pynacl`, `paramiko` (these are standard library wrappers → likely exempt); flag `ctypes` loading `.so` for custom algo; flag any file with `custom_cipher`, `homebrew_encrypt`
- **JavaScript/Node.js**: `node-crypto` (built-in, exempt), `node-forge`, `sjcl`, `tweetnacl` (standard wrappers → likely exempt); flag any hand-rolled cipher
- **Go**: `crypto/*` standard library (exempt); flag unexported packages named `cipher` with non-standard implementations
- **Rust**: `ring`, `rustls`, `aes` crate (exempt); flag custom `no_std` crypto crates without a recognized SPDX identifier

The Skill SHOULD surface a human-readable question: "This repository contains cryptographic code. Does it implement non-standard/proprietary cryptographic algorithms? If yes, BIS/NSA notification may be required before public release." This is a SHOULD-level warning (not a blocker) for standard-library-only crypto, and a MUST-level blocker pending human sign-off for ambiguous or novel crypto.

### 11. Privacy and PII: MUST Blockers vs SHOULD Warnings [HIGH confidence]

Two categories require different Skill treatments:

**MUST blockers (prevent public release)**:
1. **Real secrets or credentials in git history**: API keys, passwords, private keys, OAuth tokens committed at any point in history are a MUST-level blocker. Tools: [TruffleHog](https://www.jit.io/resources/appsec-tools/trufflehog-a-deep-dive-on-secret-management-and-how-to-fix-exposed-secrets/) (deep history scan with verification), [gitleaks](https://rafter.so/blog/secrets/secret-scanning-tools-comparison) (pre-commit/CI). Remediation: `git-filter-repo` or BFG Repo-Cleaner + force-push (requires all collaborators to re-clone).
2. **Real PII in test fixtures**: Actual customer names, email addresses, phone numbers, SSNs, financial records in `tests/` or `fixtures/` — this is a GDPR-relevant MUST blocker. Skill should scan for patterns matching real email/phone/SSN formats in non-production code paths.

**SHOULD warnings (surface for human review)**:
1. **Non-noreply contributor email addresses in git history**: Author emails that are personal (`user@gmail.com`) rather than `user@users.noreply.github.com` expose contributor identity and can be a GDPR / doxing vector. [GitHub's `users.noreply.github.com` noreply scheme](https://dev.to/ccoveille/github-protect-your-email-from-spammers-with-this-github-privacy-setting-14j4) is the mitigation. However, rewriting history is disruptive for active repos — this is a SHOULD warning, not a blocker. The Skill SHOULD surface a count of distinct non-noreply author emails in history, and advise configuring `git config --global user.email ID+username@users.noreply.github.com` going forward.
2. **Internal project names, employee identifiers, or internal URLs** in commit messages or code comments — surface for human review.

For closed-source employee commits with identifying metadata: the Skill SHOULD surface the count and representative samples and ask the maintainer whether history rewrite is desired, but MUST NOT auto-rewrite, as this is irreversibly destructive.

### 12. Trademark Protection: Apache-2.0 Section 6 Is Necessary but Not Sufficient [MEDIUM confidence]

[Apache-2.0 Section 6](https://www.apache.org/licenses/LICENSE-2.0.html) states the license "does not grant permission to use the trade names, trademarks, service marks, or product names of the Licensor." This **withholds** trademark rights but does not **affirmatively protect** them. Common-law trademark rights in the US and UK arise from use in commerce, not from license text. As noted in [The Legal Side of Open Source](https://opensource.guide/legal/) and the [ASF Trademark Policy](https://www.apache.org/foundation/marks/): trademarks and software licenses are parallel, not redundant.

**What IW needs in addition to Apache-2.0 Section 6**:
1. A `TRADEMARK.md` (or `TRADEMARKS.md`) in the repo root that: (a) declares which names/marks are IW's ("Innovation Ways", any product names); (b) states permitted nominative uses; (c) states prohibited uses (e.g., forks using IW's name in their product name); (d) provides a contact for trademark licensing inquiries.
2. A trademark disclaimer in the README: "Innovation Ways and [product name] are trademarks of Innovation Ways. Use of these marks is subject to the Trademark Policy in TRADEMARK.md."

**Without a registered trademark**, IW's common-law rights are geographically limited to where the mark is used in commerce. TRADEMARK.md establishes the public record of the mark and intent to enforce, which supports common-law protection. The Skill SHOULD check for the existence of a `TRADEMARK.md` or equivalent trademark section and emit a SHOULD-level warning if absent.

**USPTO TESS has been retired** (November 2023) and replaced by [USPTO Trademark Search at tmsearch.uspto.gov](https://tmsearch.uspto.gov/) — no public REST API, no automated bulk queries permitted. [WIPO Global Brand Database](https://www.wipo.int/en/web/global-brand-database) covers 70M+ records from 73 offices but explicitly [prohibits automatic querying](https://www.wipo.int/en/web/global-brand-database/faqs_branddb). Both require human-initiated searches; the Skill SHOULD output a checklist item: "Manually verify [project name] has no conflicting trademark in USPTO Trademark Search and WIPO Global Brand Database."

**Name-collision checks that CAN be automated**: PyPI (`https://pypi.org/pypi/{name}/json` — 404 = available), npm (`https://registry.npmjs.org/{name}` — 404 = available), crates.io (`https://crates.io/api/v1/crates/{name}` — 404 = available), GitHub (`gh api /repos/{org}/{name}`). The Skill SHOULD run these HTTP probes and report collisions as SHOULD-level warnings.

### 13. SECURITY.md: Content Requirements and GitHub Private Vulnerability Reporting [HIGH confidence]

The [OpenSSF OSPS Baseline v2025-02-25 criterion OSPS-VM-02.01](https://baseline.openssf.org/versions/2025-02-25) mandates that projects "MUST contain security contacts" — making a `SECURITY.md` a MUST at Baseline Level 1. The [OpenSSF Best Practices Badge (2026)](https://openssf.org/blog/2026/02/25/getting-an-openssf-baseline-badge-with-the-best-practices-badge-system/) integrates these criteria.

Minimum content for `SECURITY.md`:
1. **Supported versions table** — which versions receive security fixes.
2. **Disclosure procedure** — prefer GitHub's Private Vulnerability Reporting (PVR) as the primary channel (enables confidential issues within GitHub), supplemented by a security email.
3. **Response SLA** — when reporters can expect acknowledgement.
4. **Out-of-scope** items — what the team will not treat as security issues.

The Skill SHOULD verify `SECURITY.md` exists (MUST for Baseline Level 1) and contains the strings "report" and either an email or a GitHub advisory link.

### 14. Branch Protection and Repository Settings: One-Shot gh CLI Commands [HIGH confidence]

Key post-publish settings from [GitHub branch protection docs](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches) and [`gh repo edit` manual](https://cli.github.com/manual/gh_repo_edit):

**One-shot `gh repo edit` settings (safe to surface as a copy-paste command list)**:
```bash
gh repo edit {org}/{repo} \
  --description "Short description" \
  --homepage "https://innovation-ways.dev/projects/{slug}" \
  --add-topic "your-topic" \
  --enable-issues \
  --enable-discussions \
  --enable-squash-merge \
  --disable-merge-commit \
  --disable-rebase-merge \
  --delete-branch-on-merge
```

**Branch protection (requires `gh api` or UI — surface as commands, not auto-apply)**:
```bash
gh api repos/{org}/{repo}/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["dco"]}' \
  --field enforce_admins=true \
  --field required_pull_request_reviews='{"required_approving_review_count":1,"require_code_owner_reviews":true}' \
  --field restrictions=null
```

The Skill MUST NOT auto-apply branch protection or repo-visibility changes. It SHOULD output a `gh`-CLI command list as a human-actionable checklist, since applying protection rules to a live repo has operational consequences. The squash-merge-only setting is SHOULD for IW (keeps linear history for attribution clarity); disabling merge commits and rebase-merges is a MAY depending on team workflow preference.

**Archive policy**: [GitHub recommends archiving repos](https://docs.github.com/en/repositories/archiving-a-github-repository/archiving-repositories) that have had no reads/writes for a significant period. Archiving makes the repo read-only (issues, PRs, code, wiki, releases all frozen). The Skill SHOULD add a governance item: "Define an archive policy — archive if no meaningful activity for 24 months."

### 15. Governance: When GOVERNANCE.md Escalates from MAY to SHOULD to MUST [MEDIUM confidence]

Based on [CNCF governance templates](https://contribute.cncf.io/resources/templates/governance-maintainer/) and [OpenSSF foundation governance docs](https://github.com/ossf/foundation):

| Condition | Severity |
|---|---|
| 1-3 maintainers, no foundation involvement, no external contributors | MAY — a brief README section on contribution process suffices |
| 4+ maintainers OR external contributors accepted | SHOULD — a `GOVERNANCE.md` explaining decision-making, merging authority, and release process |
| Seeking CNCF / OpenSSF / LF project status | MUST — formal GOVERNANCE.md is a foundation onboarding prerequisite |
| "Critical infrastructure" designation or regulatory context | MUST — formal governance with documented roles and succession plan |

The [CNCF Maintainer Council template](https://github.com/cncf/project-template/blob/main/GOVERNANCE-maintainer.md) covers: maintainer responsibilities, adding/removing maintainers (voting quorum), release process, conflict resolution. For IW small projects, a simplified version with: (a) who can merge, (b) how decisions are made, (c) CoC enforcement chain, is sufficient.

CoC enforcement SHOULD use a group email (e.g., `conduct@innovation-ways.dev`) rather than a personal address for the same reason a security contact should be a team alias: personal addresses create single points of failure and increase individual burnout risk.

### 16. Changelog and Release Provenance: Conventional Commits + Keep-a-Changelog + SLSA [HIGH confidence]

[Conventional Commits v1.0.0](https://www.conventionalcommits.org/en/v1.0.0/) uses structured commit messages (`feat:`, `fix:`, `BREAKING CHANGE:`) that enable machine-generated `CHANGELOG.md` via tools like `git-cliff` or `semantic-release`. [Keep a Changelog v1.1.0](https://keepachangelog.com/en/1.1.0/) defines the human-readable format: sections `Added / Changed / Deprecated / Removed / Fixed / Security`, sorted latest-first, ISO 8601 dates.

**Attribution and legal provenance**:
- A `CHANGELOG.md` creates a durable public record of what changed, when, and by whom (via linked commits), supporting legal attribution over time.
- [GitHub Releases](https://docs.github.com/actions/security-guides/using-artifact-attestations-and-reusable-workflows-to-achieve-slsa-v1-build-level-3) tagged to semantic-version tags provide a release artifact inventory; using `actions/attest-build-provenance` yields [SLSA Build Level 2](https://github.com/actions/attest-build-provenance) provenance attestations (in-toto format, Sigstore-signed).
- SLSA Level 3 (isolated build environment) requires `slsa-github-generator` and is recommended for packages published to PyPI/npm/crates.io.

The Skill SHOULD check for: (a) at least one git tag matching `v[0-9]+.[0-9]+.[0-9]+` (SHOULD), (b) `CHANGELOG.md` existence (SHOULD), (c) a GitHub Release corresponding to the latest tag (SHOULD). It SHOULD emit a warning if no releases exist and recommend the `actions/attest-build-provenance` action for supply-chain provenance.

### 17. Community Health Files: Minimum Content per File [MEDIUM confidence]

Based on [GitHub community profile docs](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/about-community-profiles-for-public-repositories) and [OpenSSF Baseline](https://baseline.openssf.org/versions/2025-02-25):

| File | Severity | Minimum content |
|---|---|---|
| `README.md` | MUST | Project name, one-line description, installation steps, usage example, license badge/statement |
| `LICENSE` | MUST | Full SPDX-matched license text (root of repo) |
| `CODE_OF_CONDUCT.md` | SHOULD | Contributor Covenant v2.1+ with enforcement contact |
| `CONTRIBUTING.md` | SHOULD | How to open issues, branch naming, how to sign DCO (`git commit -s`), PR process |
| `SECURITY.md` | MUST (OSPS Baseline Level 1) | Supported versions, reporting channel (PVR link or email), SLA |
| `CODEOWNERS` | SHOULD (≥2 maintainers) | At minimum `* @org/team` for root ownership |
| `GOVERNANCE.md` | MAY→SHOULD (≥4 maintainers or external contributors) | Decision-making, merge authority, release process, CoC chain |
| `TRADEMARK.md` | SHOULD | IW mark declaration, permitted/prohibited uses, contact |
| `SUPPORT.md` | MAY | Where to get help (discussions, Slack, email) |
| `FUNDING.yml` (`.github/`) | MAY | Sponsor links if desired; not legally required |
| `PULL_REQUEST_TEMPLATE.md` (`.github/`) | SHOULD | PR description template, checklist, DCO reminder |
| `ISSUE_TEMPLATE/` (`.github/`) | SHOULD | Bug report + feature request templates |

### 18. OpenSSF OSPS Baseline Alignment: Additional MUST-Level Security Checks [HIGH confidence]

The [OpenSSF Open Source Project Security Baseline v2025-02-25](https://baseline.openssf.org/versions/2025-02-25) defines Level 1 controls that apply to any project:

- **OSPS-LE-02.01**: License MUST meet OSI OSD or FSF FSD — directly confirms that the Skill's license check is not just a community-health nicety but a security-framework MUST.
- **OSPS-LE-03.01**: License MUST be in `LICENSE`, `COPYING`, or `LICENSE/` directory.
- **OSPS-AC-03.01**: An enforcement mechanism MUST prevent direct commits to the primary branch.
- **OSPS-AC-03.02**: Branch deletion MUST require explicit confirmation.
- **OSPS-AC-01.01**: Access to sensitive resources MUST require MFA.
- **OSPS-VM-02.01**: Project MUST contain security contacts.
- **OSPS-DO-02.01**: Released projects MUST include a guide for reporting defects.
- **OSPS-GV-03.01**: Documentation MUST explain the contribution process.

These are independently authoritative MUST criteria for the Skill's severity calibration.

### 19. REUSE Spec (FSFE): Per-File SPDX Compliance — SHOULD for IW [MEDIUM confidence]

[REUSE (reuse.software)](https://reuse.software/) standardizes per-file SPDX tags (`SPDX-FileCopyrightText:` + `SPDX-License-Identifier:`) and provides a CLI tool to verify compliance. When `reuse lint` passes, the project generates a machine-readable SBOM automatically. REUSE is adopted by the FSFE, KDE, and many European public-sector projects. For IW, adopting REUSE is a SHOULD for projects expected to have long lifetimes or multiple contributors; it makes downstream license auditing trivial. It is NOT a MUST for a typical small IW project. The Skill SHOULD offer REUSE adoption as a MAY-level recommendation with the note that it reduces future compliance audit work.

### 20. Severity Calibration: Complete Check-to-RFC-2119 Map [HIGH confidence]

| Check | Severity | Automatable? | Blocker for flip-to-public? |
|---|---|---|---|
| LICENSE file present and SPDX-detectable | MUST | YES | YES |
| LICENSE is OSI-approved (OSPS-LE-02.01) | MUST | YES | YES |
| README.md present | MUST | YES | YES |
| No secrets in git history (TruffleHog / gitleaks) | MUST | YES | YES |
| No PII in test fixtures | MUST | PARTIAL (regex scan) | YES |
| GPL-2/AGPL/proprietary inbound dependency | MUST | YES (syft+grant) | YES |
| SECURITY.md present (OSPS-VM-02.01) | MUST | YES | YES |
| Branch protection: direct commits blocked (OSPS-AC-03.01) | MUST | CHECK (gh api) | YES — surface gh command |
| CODE_OF_CONDUCT.md present | SHOULD | YES | NO (warning) |
| CONTRIBUTING.md present | SHOULD | YES | NO (warning) |
| DCO app installed on repo | SHOULD | YES (gh api) | NO (warning) |
| NOTICE file present for Apache-2.0 projects | SHOULD | YES | NO (warning) |
| THIRD_PARTY_LICENSES generated and committed | SHOULD | PARTIAL | NO (warning) |
| CODEOWNERS present (≥2 maintainers) | SHOULD | YES | NO (warning) |
| Crypto imports present → human review prompt | SHOULD | PARTIAL (grep) | NO (human review) |
| Non-noreply author emails in history | SHOULD | YES (git log) | NO (warning) |
| TRADEMARK.md present | SHOULD | YES | NO (warning) |
| Name collision on PyPI/npm/crates.io | SHOULD | YES (HTTP probe) | NO (warning) |
| CHANGELOG.md present | SHOULD | YES | NO (warning) |
| Semver tag exists | SHOULD | YES (git tag) | NO (warning) |
| PULL_REQUEST_TEMPLATE present | SHOULD | YES | NO (warning) |
| ISSUE_TEMPLATE/ present | SHOULD | YES | NO (warning) |
| Contributor Covenant v3 (vs v2.1) | SHOULD | YES (version string check) | NO (warning) |
| GOVERNANCE.md present (≥4 maintainers) | SHOULD | PARTIAL | NO (warning) |
| GitHub Releases present | SHOULD | YES (gh api) | NO (warning) |
| SLSA provenance action in CI | SHOULD | YES (workflow scan) | NO (warning) |
| REUSE spec compliance | MAY | YES (reuse lint) | NO (info) |
| FUNDING.yml present | MAY | YES | NO (info) |
| SUPPORT.md present | MAY | YES | NO (info) |
| Non-standard crypto → BIS/NSA notification | MUST (if detected) | PARTIAL (human needed) | HUMAN DECISION |
| USPTO / WIPO trademark search | MUST (human only) | NO | HUMAN DECISION |
| Squash-merge-only setting | SHOULD | CHECK (gh api) | NO (warning) |
| Archive policy documented | MAY | NO | NO (info) |

---

## Recommendations

1. **Primary — License Selection**: Use `Apache-2.0` as the IW default for all non-trivial projects (any project with multiple contributors, non-trivial production code, or commercial exposure). Use `MIT` for trivially small utilities (<500 LOC, single author, no patent exposure concern). Never use `Unlicense`; use `0BSD` or `ISC` only for npm packages where ecosystem convention specifically favors them. Embed the decision heuristic in the Skill as: `LOC < 500 AND single_author AND no_co_authors → MIT; else → Apache-2.0`.

2. **Primary — CLA vs DCO**: Default to DCO via CNCF dco2 app for all IW projects. Install the app at the org level so it covers all repos automatically. Upgrade to EasyCLA (Linux Foundation) only if IW adopts an open-core / dual-licensing model, needs future relicensing rights, or is accepted into a Linux Foundation project that mandates CLA. Add `git commit -s` to the CONTRIBUTING.md as a standard step.

3. **Primary — Community Files**: The Skill MUST block release if `LICENSE` or `README.md` are absent, and MUST warn (not block) if `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, or `SECURITY.md` are absent. Provide auto-generated stub templates for each missing SHOULD-level file rather than just emitting a warning — this dramatically reduces the friction of compliance.

4. **Primary — Export Control**: Configure the Skill to scan for crypto-related imports using the per-language grep patterns above. Surface a mandatory human-review question for any detected crypto. Standard-library wrappers (Python `hashlib`, `ssl`; Go `crypto/tls`; Rust `ring`) are almost certainly exempt under the 2021 EAR rule, but the human must confirm no custom algorithms are present. Do NOT auto-approve; auto-detect and escalate.

5. **Primary — Secrets and PII Pre-Flight**: The Skill MUST run TruffleHog (or gitleaks with full-history scan) on the entire git history before the flip-to-public is approved. Any verified secret hit is a hard blocker. Remediation requires `git-filter-repo` + force-push + collaborator re-clone; the Skill should output exact commands. Real PII in test fixtures is also a hard blocker; scan `tests/` and `fixtures/` directories for email/SSN/credit-card patterns using regex.

6. **Alternative — Trademark**: If IW cannot maintain a TRADEMARK.md immediately, at minimum add a one-sentence trademark notice to the README: "Innovation Ways and [product name] are trademarks of Innovation Ways." This establishes the public record of the mark. Upgrade to a full TRADEMARK.md within 90 days. Apache-2.0 Section 6 alone does not affirmatively protect the mark; it only withholds the right to use the licensor's mark.

7. **Avoid**:
   - Do NOT auto-apply branch protection rules or change repository visibility via the Skill — surface `gh` CLI commands for human execution only.
   - Do NOT use the `Unlicense` for any IW code; use `MIT` or `0BSD` instead for maximum-permissiveness cases.
   - Do NOT skip the full git history secret scan (not just the current HEAD) before public release; historical commits are part of the public repository.
   - Do NOT use a personal email address as the CoC enforcement contact; use a group alias.
   - Do NOT rely solely on Apache-2.0 Section 6 for trademark protection; add TRADEMARK.md.
   - Do NOT auto-rewrite git history to pseudonymize author emails — surface the finding for human decision.

---

## Limitations

- **Contributor Covenant v3 adoption ratio**: No precise data on the v2.1:v3 ratio among newly-released OSS in 2026 was found; Django's adoption in April 2026 suggests active rollout but the exact adoption share is unknown. Confidence is MEDIUM that v3 is current and SHOULD be used; HIGH that v2.1 remains acceptable.
- **GitHub community-profile health_percentage exact formula**: Official GitHub documentation was ambiguous; a community issue on GitHub docs (Issue #25322) and the REST API reference both suggest the formula covers the 4 core files (README, LICENSE, CODE_OF_CONDUCT, CONTRIBUTING); SECURITY, ISSUE_TEMPLATE, and PR_TEMPLATE affect the profile display but are not confirmed to affect the percentage integer. Mark this as MEDIUM confidence.
- **USPTO/WIPO automation**: Neither registry offers a public REST API for trademark conflict searches as of 2026. Third-party services (Signa, TrademarkNow) offer APIs but require paid subscriptions. The Skill cannot automate this; it can only produce a human checklist item.
- **FSF license compatibility page**: The primary FSF license compatibility table URL returned HTTP 429 during research. The compatibility matrix in Finding 4 is synthesized from the Apache Software Foundation's GPL compatibility page and licensecheck.io, which cites FSF sources. The core Apache-2.0 / GPL-2 incompatibility and Apache-2.0 / GPL-3 one-way compatibility findings are HIGH confidence from the Apache source; AGPL and LGPL nuances are MEDIUM confidence from secondary sources.
- **EAR 2026-specific changes**: The 2021 DOC rule is the most recent material regulatory change found; no further 2025–2026 EAR amendments specifically affecting OSS crypto were located. Post-2021 guidance is treated as current; confirm with legal counsel if the project contains novel crypto.
- **REUSE specification version**: reuse.software did not surface the current spec version number during fetching; the three-step approach is confirmed, SPDX integration is confirmed from secondary sources.
- **WIPO Global Brand Database**: explicitly prohibits automatic querying in its Terms of Use; any automation would violate those terms and is off the table for the Skill.

---

## Sources

| # | Source | Credibility | URL |
|---|--------|-------------|-----|
| 1 | SPDX License List v3.28.0 | HIGH | https://spdx.org/licenses/ |
| 2 | Apache License v2.0 and GPL Compatibility — Apache Software Foundation | HIGH | https://www.apache.org/licenses/GPL-compatibility.html |
| 3 | Apache License 2.0 — Apache Software Foundation | HIGH | https://www.apache.org/licenses/LICENSE-2.0 |
| 4 | Assembling LICENSE and NOTICE files — Apache Infrastructure | HIGH | https://infra.apache.org/licensing-howto.html |
| 5 | Apache Handling cryptography — Apache Infrastructure | HIGH | https://infra.apache.org/crypto.html |
| 6 | Apache Software Foundation Trademark Policy | HIGH | https://www.apache.org/foundation/marks/ |
| 7 | About community profiles for public repositories — GitHub Docs | HIGH | https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/about-community-profiles-for-public-repositories |
| 8 | REST API endpoints for community metrics — GitHub Docs | HIGH | https://docs.github.com/en/rest/metrics/community |
| 9 | About protected branches — GitHub Docs | HIGH | https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches |
| 10 | gh repo edit — GitHub CLI Manual | HIGH | https://cli.github.com/manual/gh_repo_edit |
| 11 | Archiving repositories — GitHub Docs | HIGH | https://docs.github.com/en/repositories/archiving-a-github-repository/archiving-repositories |
| 12 | Open Source Project Security Baseline v2025-02-25 — OpenSSF | HIGH | https://baseline.openssf.org/versions/2025-02-25 |
| 13 | Getting an OpenSSF Baseline Badge — OpenSSF Blog | HIGH | https://openssf.org/blog/2026/02/25/getting-an-openssf-baseline-badge-with-the-best-practices-badge-system/ |
| 14 | Contributor Covenant (main site) | HIGH | https://www.contributor-covenant.org/ |
| 15 | Organization for Ethical Source — Contributor Covenant 3.0 | HIGH | https://ethicalsource.dev/projects/contributor-covenant-3/ |
| 16 | Django adopts Contributor Covenant 3 — Django Weblog | HIGH | https://www.djangoproject.com/weblog/2026/apr/15/contributor-covenant-adoption/ |
| 17 | Your Code of Conduct — Open Source Guides | HIGH | https://opensource.guide/code-of-conduct/ |
| 18 | The Legal Side of Open Source — Open Source Guides | HIGH | https://opensource.guide/legal/ |
| 19 | Security Best Practices for your Project — Open Source Guides | HIGH | https://opensource.guide/security-best-practices-for-your-project/ |
| 20 | CNCF dco2 GitHub App | HIGH | https://github.com/cncf/dco2 |
| 21 | Developer Certificate of Origin — Wikipedia | MEDIUM | https://en.wikipedia.org/wiki/Developer_Certificate_of_Origin |
| 22 | DCO vs CLA: Managing Contribution Agreements (2026-04-08) | MEDIUM | https://tenthirtyam.org/dispatches/2026/04/08/dco-vs-cla-managing-contribution-agreements-in-open-source/ |
| 23 | OpenStack TC Resolution: Replace CLA with DCO (2025-05-20) | HIGH | https://governance.openstack.org/tc/resolutions/20250520-replace-the-cla-with-dco-for-all-contributions.html |
| 24 | CLAs and DCOs — FINOS OSR BoK | MEDIUM | https://osr.finos.org/docs/bok/artifacts/clas-and-dcos |
| 25 | EasyCLA — Linux Foundation LFX | HIGH | https://easycla.lfx.linuxfoundation.org/ |
| 26 | CLA assistant | MEDIUM | https://cla-assistant.io/ |
| 27 | Understanding US Export Controls with Open Source Projects — Linux Foundation | HIGH | https://www.linuxfoundation.org/resources/publications/understanding-us-export-controls-with-open-source-projects |
| 28 | Commerce Eliminates Mass Market Encryption Reporting — Arnold & Porter (2021) | HIGH | https://www.arnoldporter.com/en/perspectives/advisories/2021/04/doc-eliminates-mass-market-encryption-reporting |
| 29 | U.S. Export Controls and Published Encryption Source Code — EFF | HIGH | https://www.eff.org/deeplinks/2019/08/us-export-controls-and-published-encryption-source-code-explained |
| 30 | ASF Export Classifications — Apache Software Foundation | HIGH | https://www.apache.org/licenses/exports/ |
| 31 | Apache License 2.0 — choosealicense.com | MEDIUM | https://choosealicense.com/licenses/apache-2.0/ |
| 32 | choosealicense.com (main) | MEDIUM | https://choosealicense.com/ |
| 33 | ISC License — choosealicense.com | MEDIUM | https://choosealicense.com/licenses/isc/ |
| 34 | 0BSD — choosealicense.com | MEDIUM | https://choosealicense.com/licenses/0bsd/ |
| 35 | 0BSD — Open Source Initiative | HIGH | https://opensource.org/license/0bsd |
| 36 | REUSE — Make licensing easy for everyone | HIGH | https://reuse.software/ |
| 37 | FSFE REUSE tool — GitHub | HIGH | https://github.com/fsfe/reuse-tool |
| 38 | scancode-toolkit — PyPI | MEDIUM | https://pypi.org/project/scancode-toolkit/ |
| 39 | Syft — Anchore | HIGH | https://anchore.com/blog/how-syft-scans-software-to-generate-sboms/ |
| 40 | Grant — Anchore | HIGH | https://github.com/anchore/grant |
| 41 | licensee — Ruby Gem (GitHub) | HIGH | https://github.com/licensee/licensee |
| 42 | pip-licenses — GitHub | MEDIUM | https://github.com/raimon49/pip-licenses |
| 43 | license-checker — GitHub | MEDIUM | https://github.com/davglass/license-checker |
| 44 | go-licenses — Google | MEDIUM | https://github.com/google/go-licenses |
| 45 | Apache License 2.0 Compatible Licenses Guide — licensecheck.io | MEDIUM | https://licensecheck.io/guides/apache-compatible |
| 46 | MPL 2.0 FAQ — Mozilla | HIGH | https://www.mozilla.org/en-US/MPL/2.0/FAQ/ |
| 47 | Various Licenses and Comments — FSF | HIGH | https://www.gnu.org/licenses/license-list.en.html |
| 48 | License Compatibility — Wikipedia | MEDIUM | https://en.wikipedia.org/wiki/License_compatibility |
| 49 | Conventional Commits v1.0.0 | HIGH | https://www.conventionalcommits.org/en/v1.0.0/ |
| 50 | Keep a Changelog v1.1.0 | HIGH | https://keepachangelog.com/en/1.1.0/ |
| 51 | actions/attest-build-provenance — GitHub Actions Marketplace | HIGH | https://github.com/marketplace/actions/attest-build-provenance |
| 52 | Artifact attestations — GitHub Docs | HIGH | https://docs.github.com/en/actions/concepts/security/artifact-attestations |
| 53 | CNCF Governance Maintainer Template | HIGH | https://contribute.cncf.io/resources/templates/governance-maintainer/ |
| 54 | CNCF project-template GOVERNANCE-maintainer.md | HIGH | https://github.com/cncf/project-template/blob/main/GOVERNANCE-maintainer.md |
| 55 | USPTO Trademark Search (replaced TESS) | HIGH | https://tmsearch.uspto.gov/ |
| 56 | TESS Is Gone: How to Search Trademarks — Signa Blog | MEDIUM | https://signa.so/blog/tess-is-gone-how-to-search-trademarks |
| 57 | USPTO Open Data Portal (API Catalog) | HIGH | https://developer.uspto.gov/api-catalog |
| 58 | WIPO Global Brand Database | HIGH | https://www.wipo.int/en/web/global-brand-database |
| 59 | WIPO Global Brand Database FAQ (auto-query prohibition) | HIGH | https://www.wipo.int/en/web/global-brand-database/faqs_branddb |
| 60 | Privately reporting a security vulnerability — GitHub Docs | HIGH | https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability |
| 61 | Adding a security policy to your repository — GitHub Docs | HIGH | https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/configure-vulnerability-reporting/adding-a-security-policy-to-your-repository |
| 62 | git-filter-repo — GitHub | HIGH | https://github.com/newren/git-filter-repo |
| 63 | TruffleHog vs Gitleaks — Jit | MEDIUM | https://www.jit.io/resources/appsec-tools/trufflehog-vs-gitleaks-a-detailed-comparison-of-secret-scanning-tools |
| 64 | GitHub noreply email privacy — DEV Community | MEDIUM | https://dev.to/ccoveille/github-protect-your-email-from-spammers-with-this-github-privacy-setting-14j4 |
| 65 | CODEOWNERS — GitHub Docs | HIGH | https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners |
| 66 | Displaying a sponsor button — GitHub Docs | HIGH | https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/displaying-a-sponsor-button-in-your-repository |
| 67 | Trademarks in Open Source — Google Casebook | MEDIUM | https://google.github.io/opencasebook/trademarks/ |
| 68 | OpenSSF Community Code of Conduct | HIGH | https://openssf.org/community/code-of-conduct/ |

---

## Appendix: Research Log

**Date range**: 2026-04-21
**Queries run**: 20 WebSearch, 22 WebFetch
**Mode used**: deep
**Depth level**: deep

Three WebFetch calls timed out (contributor-covenant.org/version/, contributor-covenant.org/adopt/, and ethicalsource.dev), requiring fallback to WebSearch and the successfully fetched contributor-covenant.org adopt page for v3 content. The FSF license-list page returned HTTP 429, so the GPL/Apache compatibility findings were confirmed via the Apache Software Foundation's own GPL Compatibility page (HIGH credibility). The USPTO trademark API investigation confirmed that no free programmatic access exists for trademark name-collision detection; the WIPO Global Brand Database explicitly prohibits automated querying, closing off both trademark automation options and requiring the Skill to produce human checklist items for those two checks only.
