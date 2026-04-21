# Private-to-Public Repository Technical Compliance for Permissive OSS Release

**Research ID**: R-00061
**Date**: 2026-04-21
**Mode**: deep
**Depth**: deep
**Primary Question**: What is the complete, tool-backed technical checklist a project owner must execute — and an automated Skill must enforce — to safely release a previously-private GitHub repository as public open-source, with zero leakage of secrets, internal infrastructure, PII, or vulnerable/incompatible code?

---

## Executive Summary

Safely releasing a private GitHub repository as public OSS requires a defense-in-depth pipeline spanning five domains: secrets eradication (gitleaks + TruffleHog), history hygiene (git-filter-repo or nuke-and-reinit), dependency/license vetting (syft + grant + grype + osv-scanner), CI/CD hardening (pinact + workflow auditing), and post-publish protection activation (secret scanning, Dependabot, SLSA Level 3 attestation). No single GitHub-native control is sufficient — GitHub push protection covers only ~254 secret detector types with no historical scanning capability, making pre-publish tooling mandatory. The recommended scaffolding pattern for Innovation Ways is copier-based template propagation with pre-commit as the hook distribution mechanism and release-please for release automation, giving durable compliance as projects evolve.

## Background

Innovation Ways operates a portfolio of repositories — including iw-ai-core itself — that began as private internal tooling and may be candidates for public OSS release under permissive licenses (Apache 2.0, MIT). The primary risk is inadvertent exposure of secrets, internal infrastructure topology, PII (contributor email addresses, internal FQDNs), or incompatibly-licensed dependencies embedded across commit history. This research directly drives the design of a reusable iw-ai-core Skill that can automate the pre-publish compliance checklist — checking, blocking, and remediating each risk class before the visibility flip occurs.

---

## Findings

### 1. GitHub Push Protection Has Significant Coverage Gaps That Mandate Additional Tooling [HIGH confidence]

GitHub push protection detects [254 secret detector types as of early 2026](https://blog.gitguardian.com/github-push-protection-enhancing-open-source-security-with-limitations-to-consider/), with only 39 having push protection enabled by default after a [March 2026 expansion](https://github.blog/changelog/2026-03-10-secret-scanning-pattern-updates-march-2026/). Three critical gaps render it insufficient as a sole control: (1) it performs **no historical scanning** — secrets already committed to history are invisible to it, which is the exact failure mode when flipping a private repo public; (2) it misses **generic secrets** (credentials lacking distinctive format patterns), which [GitGuardian estimates comprised 67% of leaks in 2022](https://blog.gitguardian.com/github-push-protection-enhancing-open-source-security-with-limitations-to-consider/); (3) **size-timeout bypass**: pushes that take over 5 seconds to analyse may be silently passed. GitHub also allows developers to [bypass protection by marking findings as false positives](https://docs.github.com/en/code-security/secret-scanning/introduction/about-push-protection), making it a soft control. These gaps confirm that pre-publish history scanning with dedicated tools is non-negotiable.

### 2. Gitleaks Is the Optimal Primary Secret Scanner; TruffleHog Is the Right One-Time History Auditor [HIGH confidence]

[Gitleaks](https://github.com/gitleaks/gitleaks) is MIT-licensed, written in Go, operates entirely offline, supports 150+ built-in regex rules, produces SARIF output (uploadable to GitHub Advanced Security via `github/codeql-action/upload-sarif`), and runs `git log -p` history scans with configurable `--log-opts` ranges. Its speed and SARIF integration make it the right primary tool for both pre-commit hooks and CI gates. [TruffleHog v3.94.3](https://github.com/trufflesecurity/trufflehog) (released April 8, 2026, AGPL-3.0) classifies 800+ secret types and uniquely performs **live credential verification** — it calls service APIs to confirm whether a detected secret is still active, reducing emergency false-positive triage. However, verification requires network access, making TruffleHog unsuitable as an offline pre-commit hook. The [rafter.so comparison](https://rafter.so/blog/secrets/secret-scanning-tools-comparison) confirms: gitleaks for fast pre-commit blocking, TruffleHog for periodic full-history sweeps before publication. Note: TruffleHog does not currently document SARIF output support, and its AGPL license complicates embedding in proprietary tooling.

### 3. detect-secrets Is the Right Brownfield Baseline Tool for Legacy Codebases [MEDIUM confidence]

[detect-secrets](https://rafter.so/blog/secrets/secret-scanning-tools-comparison) uses Shannon entropy thresholds and a plugin architecture that teams extend with custom detectors for internal secret formats. Its defining feature is a **baseline file** that snapshots existing findings — allowing teams to acknowledge legacy issues and avoid alert fatigue on day one in large codebases. It runs offline and requires no special infrastructure. Its false positive rate is higher than gitleaks (which uses smarter composite rules), so it is best used as a transition aid when a repo has many pre-existing detected secrets that need triaging before clean pre-commit enforcement is possible. The Skill should use gitleaks for enforcement but may offer detect-secrets as a brownfield-mode initialisation step.

### 4. git-filter-repo Is the Correct Surgical History Tool; Nuke-and-Reinit Is Correct for Preservation-Free Cases [HIGH confidence]

[git-filter-repo](https://github.com/newren/git-filter-repo) is the Git project's officially recommended replacement for `git filter-branch`, offering orders-of-magnitude speed improvement and a clean Python API for scripting custom rewrites. Key pitfalls: (1) **Signed commits**: fast-export strips existing GPG signatures because they are invalidated by any content change; re-signing requires a separate pass and is impractical at scale — this is a known limitation [discussed in the project's own issue tracker](https://github.com/newren/git-filter-repo/discussions/209); (2) **LFS objects**: `--sensitive-data-removal` flag creates manifests of orphaned LFS objects that must be separately purged via LFS admin commands; (3) **Submodules**: filter-repo operates on the fast-export stream and does not rewrite submodule references — submodules pointing to internal URLs must be removed or redirected before running; (4) **Tags**: lightweight tags are rewritten; annotated tags that contain signed data lose their signatures. The **nuke-and-reinit** approach (`git checkout --orphan`, single squash commit, `git push --force`) sidesteps all of these pitfalls at the cost of full history — correct when history has no archeological value (personal projects, early-stage tooling). Use git-filter-repo only when specific commits must be preserved.

### 5. GitHub SHA Cache Requires GitHub Support Intervention to Fully Purge [HIGH confidence]

After a force-push that rewrites history, GitHub maintains [cached views of old commits accessible by their SHA-1 hashes](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository) — these are not automatically garbage-collected. Full purge requires: submitting a [GitHub Support portal](https://support.github.com/) ticket providing the repository name, affected PR list, and first-changed commit SHA; GitHub Support then dereferences affected PRs, runs server-side garbage collection, and clears cached views. GitHub Support will only assist when the risk cannot be mitigated by rotating credentials. The Skill should emit a blocking checklist item: "Open GitHub Support ticket after force-push if any secrets were found in history."

### 6. BFG Repo-Cleaner Is 10-720x Faster Than filter-branch for Simple Bulk Removal but Has Architectural Limitations [MEDIUM confidence]

[BFG Repo-Cleaner](https://rtyley.github.io/bfg-repo-cleaner/) processes tree objects directly, operating on file basenames without full path context — meaning it cannot distinguish `secrets.env` at the repo root from one in a subdirectory. It also [does not modify the HEAD commit by default](https://github.com/newren/git-filter-repo/blob/main/Documentation/converting-from-bfg-repo-cleaner.md), a significant divergence from git-filter-repo behavior. For simple "delete this file everywhere" or "strip all blobs over 50MB" operations it remains fast and reliable, but for path-specific rewrites (targeting specific files in specific subtrees), git-filter-repo is strictly superior. `git filter-branch` itself is [explicitly deprecated by the Git project](https://git-scm.com/docs/git-filter-branch) and must not be used in 2026.

### 7. Ripgrep Regexes Are the Right Baseline for Internal Reference Detection; Semgrep Adds Precision for Code Files [MEDIUM confidence]

Ripgrep (`rg`) with patterns for RFC 1918 address ranges (`10\.\d+\.\d+\.\d+`, `172\.(1[6-9]|2\d|3[01])\.\d+\.\d+`, `192\.168\.\d+\.\d+`), internal FQDNs (`.internal`, `.corp`, `.local`, `.lan`), absolute home paths (`/home/\w+/`, `/Users/\w+/`), and internal email domains is fast, language-agnostic, and zero-dependency. The [Semgrep registry](https://registry.semgrep.dev/) offers AST-aware rules for hardcoded string literals in source code — the advantage being that Semgrep will not flag a comment or a test assertion string in the same way grep would, [reducing false positives by an estimated 25% on real codebases per Semgrep's own analysis](https://semgrep.dev/products/community-edition/). However, Semgrep's Community Edition is language-specific and slower, and rules for RFC 1918 and FQDN detection are not prominently maintained in the public registry (based on a single source — LOW confidence addendum). The practical recommendation: run ripgrep regexes on all files as the primary gate, add Semgrep rules for high-value languages (Python, TypeScript, Go) where false positive rate from grep is high. False positives from documentation and test fixtures are the main burden; a `.rg-ignore` or `.semgrepignore` exclusion list for `docs/`, `tests/`, and `fixtures/` is the recommended mitigation.

### 8. Syft + Grant + Grype + osv-scanner Is the Minimal Correct Dependency/License Chain [HIGH confidence]

[Syft](https://github.com/anchore/syft) (Apache 2.0, 8.4k stars) generates SBOMs in SPDX and CycloneDX from container images, filesystems, or source repos, covering 30+ ecosystems (Python, JS, Go, Rust, Java, Ruby, PHP, .NET, Alpine, Debian, RPM). [Grant](https://github.com/anchore/grant) (Apache 2.0, v0.3.0, 2025) consumes Syft SBOMs and enforces allow/deny license policies — the [Anchore introduction post](https://anchore.com/blog/introducing-grant-a-new-oss-project-from-anchore/) confirms it works seamlessly with Syft JSON output. [Grype](https://anchore.com/opensource/) scans SBOMs against NVD, GitHub Advisories, and distribution feeds with EPSS/KEV scoring. [OSV-Scanner V2](https://github.com/google/osv-scanner) (Google, Apache 2.0) adds dependency-graph call analysis to determine whether vulnerable functions are actually reachable, reducing false-positive fix prioritisation burden — it covers 11+ ecosystems and 19+ lockfile types and also offers offline scanning. The [key operational insight from the Open Source Security podcast](https://opensourcesecurity.io/2025/2025-04-syft-grype-grant-alan-pope/) is to store generated SBOMs as JSON artifacts so Grype can re-run against them in milliseconds when new CVEs emerge (e.g., a Log4Shell-style event). The Skill should run: `syft . -o spdx-json > sbom.json && grant check sbom.json && grype sbom:sbom.json && osv-scanner --lockfile pyproject.toml`.

### 9. Per-Ecosystem Tools Complement but Do Not Replace the Unified Chain [MEDIUM confidence]

[pip-audit](https://github.com/pypa/pip-audit) (PyPA + Trail of Bits), `cargo audit`, `govulncheck` (Go), and `npm audit` provide ecosystem-native context — they understand yanked crates, unmaintained PyPI packages, and npm advisory nuances that general scanners may miss or misclassify. [Per a January 2026 dependency scanning guide](https://oneuptime.com/blog/post/2026-01-24-dependency-vulnerability-scanning/view), Rust teams in particular rely on `cargo audit` for detecting yanked packages. These tools run fast and produce minimal false positives because they operate within their own advisory databases. For polyglot projects, they complement Grype and osv-scanner rather than replacing them. The Skill should run per-ecosystem tools as supplementary checks for any language present in the repository.

### 10. reuse-tool Is Recommended but Not Required for a Permissive-Outbound First Release [MEDIUM confidence]

The [FSFE REUSE tool](https://github.com/fsfe/reuse-tool) (specification v3.3, tool v5.0.0, Apache 2.0) adds machine-readable per-file SPDX copyright headers (`SPDX-FileCopyrightText:` + `SPDX-License-Identifier:`), enabling automated license compliance audits at the file level. The [Fedora Magazine beginner's guide](https://fedoramagazine.org/beginners-guide-for-open-source-developers-for-software-licensing-with-fsfe-reuse/) confirms that retrofitting an existing codebase requires touching every source file — a significant one-time cost. For Innovation Ways' initial OSS releases the pragmatic position is: include a root `LICENSE` file and top-level `SPDX-License-Identifier` headers, run `reuse lint` in CI to detect non-compliant new files going forward, but do not block publish on historical non-compliance. `reuse addheader` can automate retrofitting if the decision is made to go full REUSE-compliant.

### 11. pinact Is the Correct Tool for SHA-Pinning GitHub Actions Workflows [HIGH confidence]

[pinact](https://github.com/suzuki-shunsuke/pinact) (latest: v3.9.0, February 2026) converts action references from mutable tags (`uses: actions/checkout@v4`) to immutable commit SHAs with inline version comments (`uses: actions/checkout@1234abcd... # v4.1.0`). This addresses the March 2026 Trivy-action incident where [attackers compromised 75 of 76 trivy-action version tags via force-push, exfiltrating secrets from CI pipelines](https://www.stepsecurity.io/blog/pinning-github-actions-for-enhanced-security-a-complete-guide). `pinact run --check` validates pinning without modifying files, making it suitable as a blocking CI gate. Since August 2025, [GitHub's Actions policy supports SHA-pinning enforcement at the organisation level](https://github.blog/changelog/2025-08-15-github-actions-policy-now-supports-blocking-and-sha-pinning-actions/), allowing workflows using unpinned actions to fail. The Skill should run `pinact run --check` on all `.github/workflows/*.yml` files.

### 12. Dockerfile, devcontainer.json, and Terraform State Are High-Risk CI/CD Leak Surfaces [MEDIUM confidence]

Beyond workflow files, three additional surfaces require scanning before publish: (1) **Dockerfiles** often contain internal registry hostnames (`FROM registry.internal.company.com/base:latest`) and hardcoded build-time args that embed credentials — ripgrep against known internal domain patterns catches these; (2) **`.devcontainer/devcontainer.json`** can reference internal extension registries or container images — the [Claude Code devcontainer documentation](https://code.claude.com/docs/en/devcontainer) and general security guidance note that malicious devcontainers can exfiltrate credentials; (3) **Terraform state files** (`*.tfstate`, `*.tfstate.backup`) often contain sensitive resource attributes in plaintext and must be in `.gitignore` and absent from history. A [November 2025 scan of Docker Hub images found 4,000+ AI keys exposed](https://flare.io/learn/resources/docker-hub-secrets-exposed), primarily via CI/CD pipeline misconfiguration, confirming this surface is actively exploited.

### 13. .gitignore Completeness and Large-Object Detection Are Pre-Publish Prerequisites [HIGH confidence]

GitHub's [github/gitignore repository](https://github.com/github/gitignore) provides canonical per-language templates (Python, Node, Go, Rust, Terraform) that must be verified complete. The critical check is **what is already tracked** — files already in git history are not protected by `.gitignore`. The Skill must: run `git ls-files | grep -E "\.(env|pem|p12|pfx|key|tfstate)$"` to find tracked sensitive file types; run `git rev-list --objects --all | sort -k2 | git cat-file --batch-check='%(objectsize) %(rest)' | sort -n | tail -20` to detect large objects (>50 MB blobs) that will create clone overhead. [git-sizer](https://github.com/github/git-sizer) provides a more comprehensive repository size analysis. All binary assets above a threshold (suggest 10 MB) should be migrated to Git LFS or removed before publish.

### 14. Contributor Email Exposure Requires Audit Before Publish [HIGH confidence]

Running `git shortlog -sea --all` or `git log --all --format='%ae'` enumerates all contributor email addresses across every branch. Real personal email addresses embedded in commit history become permanently public once the repo flips public. GitHub's noreply addresses (`ID+username@users.noreply.github.com`) are safe; personal addresses are not. The [GitHub blog "Private emails, now more private"](https://github.blog/news-insights/product-news/private-emails-now-more-private/) confirms that the noreply format is the recommended substitute. The Skill must enumerate exposed personal emails and emit a warning with instructions to configure `git config user.email` to the noreply format for future commits. Rewriting historical commit author emails via git-filter-repo is possible but has the same signed-commit pitfalls noted in Finding 4.

### 15. GitHub-Native Post-Publish Protections Have a Correct Activation Sequence [HIGH confidence]

The recommended activation order for a newly-public repo is: (1) enable **secret scanning + push protection** (`gh api --method PUT /repos/ORG/REPO/vulnerability-alerts`; push protection toggleable via API since 2024); (2) enable **Dependabot alerts and security updates** (`gh api --method PUT /repos/ORG/REPO/automated-security-fixes`); (3) enable **Private Vulnerability Reporting** (PVR) via `gh api --method PUT /repos/ORG/REPO/private-vulnerability-reporting` (API-available); (4) configure **branch protection** on `main` with required status checks, no-force-push, and required review (via `gh api --method PUT /repos/ORG/REPO/branches/main/protection`); (5) add **CODEOWNERS** file at `.github/CODEOWNERS`; (6) add **CodeQL** workflow from GitHub's starter workflow; (7) add **OpenSSF Scorecard** action; (8) optionally enforce signed commits (`gh api` branch protection `required_signatures`). Per [OpenSSF Scorecard v5.4.0 checks](https://github.com/ossf/scorecard/blob/main/docs/checks.md), the highest-value checks that map to these settings are Branch-Protection, SAST, Dependency-Update-Tool, Signed-Releases, and Token-Permissions. Most post-publish protection toggles are [accessible via the `gh api` CLI](https://dev.to/nodesecure/securize-your-github-org-4lb7) — no UI interaction required, making them automatable by the Skill.

### 16. GHCR Is the Preferred OSS Image Registry in 2026; SLSA Level 3 Requires Reusable Workflow Isolation [HIGH confidence]

[GHCR is free for public repos](https://blog.devops.dev/docker-hub-or-ghcr-or-ecr-lazy-mans-guide-4da1d943d26e) with no pull rate limits, tightly integrated with GitHub Actions and GitHub packages, and the natural home for images built from GitHub-hosted source. Docker Hub remains relevant for maximum discovery (CLI default) but imposes pull rate limits for unauthenticated pulls. **Minimum OSS image bar**: SBOM attestation attached via `actions/attest-build-provenance@v2`, cosign keyless signing via Sigstore, and a Trivy/Grype scan on the image before push. **SLSA Level 3** requires the signing step to run in an [isolated, separate reusable workflow](https://github.com/slsa-framework/slsa-github-generator) — the `slsa-framework/slsa-github-generator` project provides these for Go, Node.js, Maven, Gradle, Bazel, and Docker, plus a generic generator for any artifact type. GitHub's January 2026 announcement confirms [SLSA Build Level 3 compliance via `actions/attest-build-provenance`](https://github.blog/changelog/2026-01-20-strengthen-your-supply-chain-with-code-to-cloud-traceability-and-slsa-build-level-3-security/). Note: [slsa-github-generator workflows do not cover provenance distribution or verification themselves](https://github.com/slsa-framework/slsa-github-generator) — `slsa-verifier` must be used by consumers.

### 17. cosign Keyless Signing via Sigstore Is Stable and Widely Adopted in 2026 [HIGH confidence]

[Cosign's keyless signing mode](https://docs.sigstore.dev/cosign/signing/overview/) uses Fulcio (OIDC-to-certificate authority) and Rekor (transparency log) to bind artifact signatures to GitHub Actions OIDC identities, eliminating the need to manage long-lived private keys. Supported OIDC providers include GitHub, Google, and Microsoft. PyPI, npm, Maven, and Kubernetes package ecosystems now integrate or plan to integrate with Sigstore — per the [OpenSSF blog](https://openssf.org/blog/2024/02/16/scaling-up-supply-chain-security-implementing-sigstore-for-seamless-container-image-signing/). This is no longer bleeding edge: keyless signing is the recommended approach for all new OSS image releases in 2026. The Skill should emit a workflow snippet that includes `cosign sign --yes ghcr.io/ORG/IMAGE@sha256:...` in a post-push step with `COSIGN_EXPERIMENTAL=1` for keyless mode.

### 18. pre-commit Is the Right Hook Distribution Framework; Its Reusable Repo Model Enables One-Command Consumer Adoption [HIGH confidence]

[pre-commit](https://pre-commit.com/) supports cross-language hook distribution via a simple model: a repository publishes a `.pre-commit-hooks.yaml` manifest, and consumers add a `repos:` entry pointing to it in their `.pre-commit-config.yaml`. Running `pre-commit install` is all that is needed. Pre-commit manages isolated per-hook environments, automatically installing required runtimes (Python, Node, Go, Rust) without polluting the developer's global toolchain. Per the [March 2026 git hooks comparison](https://www.andymadge.com/2026/03/10/git-hooks-comparison/), pre-commit offers "the broadest ecosystem of pre-built checks" with full environment isolation. Lefthook (Go binary, no runtime dep) is faster and supports parallel hook execution, and its `remotes:` feature (currently beta) allows centralised config distribution — but its ecosystem of community-maintained hooks is smaller. Husky is inappropriate for non-JavaScript projects. The IW compliance Skill should publish a `iw-compliance-hooks` repository with a `.pre-commit-hooks.yaml` that wires gitleaks, ripgrep internal-ref rules, and pinact-check, allowing any IW project to adopt them with four lines in `.pre-commit-config.yaml`.

### 19. copier Beats cookiecutter for Ongoing Compliance Propagation [HIGH confidence]

[copier](https://copier.readthedocs.io/en/stable/updating/) supports `copier update`, which uses a three-way diff (old template + old answers vs. new template + new answers) to propagate template changes into existing projects while preserving project-specific customisations. The `.copier-answers.yml` file in the generated project tracks template source, version (Git tag), and all prompt answers. Running `copier update --vcs-ref HEAD` updates to the latest template commit. [Cookiecutter](https://pypi.org/project/copier/) has no equivalent — `cruft` is a third-party wrapper that adds this capability but adds toolchain complexity. For Innovation Ways, a `iw-oss-baseline` copier template can encode the compliance baseline (`.gitignore`, pre-commit config, CI workflow stubs, LICENSE, CODEOWNERS, dependabot.yml), and as compliance rules evolve, `copier update` propagates them to all IW OSS repos. GitHub template repos offer zero update propagation — they are one-shot scaffolding only.

### 20. release-please (googleapis/release-please-action v4.4.1) Is the Right Pick for GitHub-First Python/JS Polyglot Projects [HIGH confidence]

[googleapis/release-please-action](https://github.com/googleapis/release-please-action) v4.4.1 (April 13, 2026) is actively maintained, supports Python (`python` release type handling `pyproject.toml`, `setup.py`, `version.py`, and `CHANGELOG.md`), and supports monorepos via manifest configuration (`release-please-config.json` + `.release-please-manifest.json`). It creates and maintains **Release PRs** updated automatically as conventional commits merge — the human explicitly merges the PR to trigger a release, providing review control absent from fully-automated tools. [Semantic-release](https://npmtrends.com/changesets-vs-publish-please-vs-release-it-vs-semantic-release) (2.4M weekly npm downloads, maintenance score 80/100) is fully automated and widely adopted but is not natively monorepo-aware (the `semantic-release-monorepo` plugin has limited maintenance). [Changesets](https://brianschiller.com/blog/2023/09/18/changesets-vs-semantic-release/) is purpose-built for monorepos but has low weekly downloads (2K) and a maintenance score of 20/100, making it a risk for long-running projects. **uv compatibility**: release-please updates version strings in `pyproject.toml` files directly; there is no documented uv-specific integration, but since uv reads `pyproject.toml` natively, the version bump mechanism is compatible. The archived `google-github-actions/release-please-action` must not be used — all workflows must reference `googleapis/release-please-action@v4`.

### 21. No Single Canonical "Release Pipeline Compliance" Schema Exists Yet — CycloneDX VEX + SLSA Provenance Is the Closest Composite [LOW confidence]

There is no widely-adopted single schema that combines SBOM + vulnerability + license + provenance into a single compliance report for OSS release pipelines. The closest composite is: a **CycloneDX SBOM** (v1.6, which includes vulnerability data in the `vulnerabilities` component and license metadata in `licenses` per component) supplemented by a **SLSA provenance attestation** (in-toto format, produced by `slsa-github-generator` or `actions/attest-build-provenance`). The [SPDX 3.0.1 specification](https://spdx.dev/learn/overview/) added a Security profile that begins to unify SBOM and VEX (Vulnerability Exploitability eXchange) data. OpenSSF Scorecard outputs JSON with a defined schema covering 23 checks. For the Skill's output, the practical recommendation is to emit: a Syft SPDX JSON SBOM, a gitleaks SARIF report, an OpenSSF Scorecard JSON, and a SLSA provenance bundle — these four artifacts together constitute the disclosure package. This is an inference based on current tool capabilities, not a formally standardised schema.

### 22. Semgrep for Internal Reference Detection Reduces False Positives Versus Pure Ripgrep, but Has Runtime Cost [MEDIUM confidence]

[Semgrep Community Edition](https://semgrep.dev/products/community-edition/) is structure-aware: a pattern matching the string `"10.0.0.1"` as a literal in code will not match the same string in a comment or documentation string, because Semgrep parses the AST before matching. Semgrep's own data [claims 25% false positive reduction and 250% true positive increase](https://semgrep.dev/products/community-edition/) over grep-based approaches for security rules. However, the public [Semgrep Rules Registry](https://registry.semgrep.dev/) does not maintain prominently-curated rules specifically targeting RFC 1918 ranges or internal FQDN patterns — these would need to be authored by Innovation Ways. The practical strategy is: ripgrep for all-file, all-language RFC 1918 and domain pattern scanning (fast, zero false negatives); Semgrep for Python, TypeScript, and Go source files where the ripgrep signal-to-noise ratio in string literals is poor. Both tools support ignore files (`.rgignore`, `.semgrepignore`) for excluding documentation and test fixture directories.

---

## Recommendations

1. **Primary — Secrets Tooling**: Adopt gitleaks as the primary secrets scanner for both pre-commit and CI, configured with SARIF output and uploaded to GitHub Advanced Security. Run TruffleHog once as a history audit with `--since-commit=initial --branch=--all` immediately before the visibility flip. This combination covers both fast gating (gitleaks) and live verification (TruffleHog) without requiring ggshield's commercial licence.

2. **Primary — History Strategy**: Use the nuke-and-reinit approach (`git checkout --orphan new-root && git add -A && git commit -m "Initial public release"`) for any Innovation Ways repo where commit history has no external consumer value. Apply git-filter-repo with `--sensitive-data-removal` only when meaningful commit history must be preserved. In both cases, contact GitHub Support to purge cached SHA views after force-push.

3. **Primary — Dependency and License Chain**: Run `syft . -o spdx-json > sbom.json`, then `grant check sbom.json` for license policy validation, `grype sbom:sbom.json` for vulnerability scanning, and `osv-scanner --lockfile <lockfile>` for each language lockfile present. Supplement with pip-audit (Python), `cargo audit` (Rust), and `govulncheck` (Go) for ecosystem-native signal. Store the SBOM artifact in each GitHub Release for retrospective CVE scanning.

4. **Primary — CI/CD Hardening**: Run `pinact run --check` on all `.github/workflows/*.yml` files as a blocking CI gate. Scan Dockerfiles with ripgrep for internal registry hostnames. Verify `.gitignore` completeness against GitHub's canonical templates and check that `*.tfstate`, `*.tfstate.backup`, `.env`, and `*.pem` are both in `.gitignore` and absent from tracked history (`git ls-files` check).

5. **Primary — Scaffolding and Propagation**: Create an `iw-oss-baseline` copier template encoding the full compliance baseline. All new IW OSS repos should be generated from it. Existing repos should run `copier update` when the template receives compliance rule updates. Pair with a `iw-compliance-hooks` pre-commit hook repository that downstream projects add in four lines, enabling one-command compliance hook installation.

6. **Primary — Release Automation**: Adopt `googleapis/release-please-action@v4` for all IW OSS repos using Conventional Commits. Configure a `release-please-config.json` manifest for monorepos. For Python repos managed with uv, confirm the `pyproject.toml` version field is correctly updated by release-please's `python` release type before going live.

7. **Alternative — If pre-commit adoption is blocked by Python runtime requirement**: Use lefthook as the hook distribution mechanism. The `remotes:` feature (beta) allows centralised config pull. Accept the smaller community ecosystem as a tradeoff.

8. **Avoid**: (a) `git filter-branch` — deprecated, error-prone, and slow; (b) relying solely on GitHub push protection — it misses ~67% of credential types and has zero historical scanning; (c) `google-github-actions/release-please-action` — archived since August 2024; (d) cookiecutter for ongoing compliance propagation — it has no update mechanism; (e) Docker Hub as the sole registry for OSS images — GHCR is free and integrated; (f) managing long-lived cosign signing keys — use keyless Sigstore OIDC instead.

---

## Limitations

- **TruffleHog SARIF**: No documentation was found confirming TruffleHog produces SARIF output. The Skill design may need to convert TruffleHog JSON to SARIF for GitHub Advanced Security upload — this requires verification against the current TruffleHog changelog.
- **reuse-tool retrofit cost**: No quantified case study data was found for the cost of retrofitting SPDX per-file headers on a real codebase of ~10k-50k LoC. The "significant" characterisation is qualitative.
- **Semgrep RFC 1918 rules**: The public Semgrep registry was not exhaustively searched for existing RFC 1918 / internal domain rules. Rules may exist in third-party repositories (e.g., Trail of Bits' semgrep-rules) not surfaced by the searches conducted.
- **release-please + uv**: No explicit documentation was found confirming or denying compatibility between release-please's Python release type and uv-managed `pyproject.toml` projects. Testing is required before adoption.
- **GitHub push protection CLI toggle**: The exact `gh api` endpoint for enabling push protection on a single repo was not confirmed from primary docs — the general pattern (`--method PUT /repos/ORG/REPO/...`) was sourced from community articles, not official API docs.
- **CycloneDX vs SPDX for the canonical disclosure package**: The choice between these two formats for the Skill's primary SBOM output was not definitively resolved; both are supported by syft and either would be acceptable.
- **Contributor PII rewriting**: Rewriting historical commit author emails to noreply addresses was not tested for compatibility with GitHub's contribution graph attribution — this is a known side effect that may matter to contributors.

---

## Sources

| # | Source | Credibility | URL |
|---|--------|-------------|-----|
| 1 | GitHub Docs — About Push Protection | HIGH | https://docs.github.com/en/code-security/secret-scanning/introduction/about-push-protection |
| 2 | GitGuardian — GitHub Push Protection Limitations | MEDIUM | https://blog.gitguardian.com/github-push-protection-enhancing-open-source-security-with-limitations-to-consider/ |
| 3 | GitHub Changelog — Secret Scanning Pattern Updates March 2026 | HIGH | https://github.blog/changelog/2026-03-10-secret-scanning-pattern-updates-march-2026/ |
| 4 | GitHub Changelog — Nine New Secret Types March 2026 | HIGH | https://github.blog/changelog/2026-03-31-github-secret-scanning-nine-new-types-and-more/ |
| 5 | gitleaks — GitHub Repository | HIGH | https://github.com/gitleaks/gitleaks |
| 6 | gitleaks-action — GitHub Repository | HIGH | https://github.com/gitleaks/gitleaks-action |
| 7 | TruffleHog v3 — GitHub Repository | HIGH | https://github.com/trufflesecurity/trufflehog |
| 8 | Rafter.so — Secret Scanning Tools Comparison | MEDIUM | https://rafter.so/blog/secrets/secret-scanning-tools-comparison |
| 9 | Jit.io — TruffleHog vs Gitleaks | MEDIUM | https://www.jit.io/resources/appsec-tools/trufflehog-vs-gitleaks-a-detailed-comparison-of-secret-scanning-tools |
| 10 | AppSec Santa — 8 Best Secret Scanning Tools 2026 | MEDIUM | https://appsecsanta.com/sast-tools/secret-scanning-tools |
| 11 | git-filter-repo — GitHub Repository | HIGH | https://github.com/newren/git-filter-repo |
| 12 | git-filter-repo — Converting from BFG Repo-Cleaner | HIGH | https://github.com/newren/git-filter-repo/blob/main/Documentation/converting-from-bfg-repo-cleaner.md |
| 13 | BFG Repo-Cleaner — Official Site | HIGH | https://rtyley.github.io/bfg-repo-cleaner/ |
| 14 | git-filter-repo — GPG Signed Commits Discussion #209 | HIGH | https://github.com/newren/git-filter-repo/discussions/209 |
| 15 | Warp — Remove Secret from Git History | MEDIUM | https://www.warp.dev/terminus/remove-secret-git-history |
| 16 | GitHub Docs — Removing Sensitive Data from a Repository | HIGH | https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository |
| 17 | git-scm.com — git-filter-branch Documentation | HIGH | https://git-scm.com/docs/git-filter-branch |
| 18 | Syft — GitHub Repository | HIGH | https://github.com/anchore/syft |
| 19 | Grant — GitHub Repository | HIGH | https://github.com/anchore/grant |
| 20 | Anchore — Introducing Grant | HIGH | https://anchore.com/blog/introducing-grant-a-new-oss-project-from-anchore/ |
| 21 | Grant v0.3.0 Release Post | HIGH | https://anchore.com/blog/grants-release-0-3-0-smarter-policies-faster-scans-and-simpler-compliance/ |
| 22 | Jit.io — Syft and Grype Guide | MEDIUM | https://www.jit.io/resources/appsec-tools/a-guide-to-generating-sbom-with-syft-and-grype |
| 23 | OSV-Scanner — GitHub Repository | HIGH | https://github.com/google/osv-scanner |
| 24 | Open Source Security Podcast — Syft, Grype, Grant | MEDIUM | https://opensourcesecurity.io/2025/2025-04-syft-grype-grant-alan-pope/ |
| 25 | AppSec Santa — Open-Source SCA Tools 2026 | MEDIUM | https://appsecsanta.com/sca-tools/open-source-sca-tools |
| 26 | pip-audit — GitHub Repository | HIGH | https://github.com/pypa/pip-audit |
| 27 | OneUptime — Dependency Vulnerability Scanning 2026 | MEDIUM | https://oneuptime.com/blog/post/2026-01-24-dependency-vulnerability-scanning/view |
| 28 | FSFE REUSE Tool — GitHub Repository | HIGH | https://github.com/fsfe/reuse-tool |
| 29 | REUSE Specification v3.3 | HIGH | https://reuse.software/spec-3.3/ |
| 30 | Fedora Magazine — Beginner's Guide to REUSE | MEDIUM | https://fedoramagazine.org/beginners-guide-for-open-source-developers-for-software-licensing-with-fsfe-reuse/ |
| 31 | pinact — GitHub Repository | HIGH | https://github.com/suzuki-shunsuke/pinact |
| 32 | StepSecurity — Pinning GitHub Actions | MEDIUM | https://www.stepsecurity.io/blog/pinning-github-actions-for-enhanced-security-a-complete-guide |
| 33 | GitHub Changelog — Actions Policy SHA Pinning August 2025 | HIGH | https://github.blog/changelog/2025-08-15-github-actions-policy-now-supports-blocking-and-sha-pinning-actions/ |
| 34 | OpenSSF Scorecard — GitHub Repository | HIGH | https://github.com/ossf/scorecard |
| 35 | OpenSSF Scorecard — Checks Documentation | HIGH | https://github.com/ossf/scorecard/blob/main/docs/checks.md |
| 36 | DEV Community — Securizing GitHub Org | MEDIUM | https://dev.to/nodesecure/securize-your-github-org-4lb7 |
| 37 | GitHub Changelog — SLSA Build Level 3 January 2026 | HIGH | https://github.blog/changelog/2026-01-20-strengthen-your-supply-chain-with-code-to-cloud-traceability-and-slsa-build-level-3-security/ |
| 38 | slsa-github-generator — GitHub Repository | HIGH | https://github.com/slsa-framework/slsa-github-generator |
| 39 | Sigstore Cosign Docs — Signing Overview | HIGH | https://docs.sigstore.dev/cosign/signing/overview/ |
| 40 | OpenSSF Blog — Sigstore Supply Chain Security | HIGH | https://openssf.org/blog/2024/02/16/scaling-up-supply-chain-security-implementing-sigstore-for-seamless-container-image-signing/ |
| 41 | DevOps.dev — Docker Hub vs GHCR vs ECR | MEDIUM | https://blog.devops.dev/docker-hub-or-ghcr-or-ecr-lazy-mans-guide-4da1d943d26e |
| 42 | GitHub Blog — Enhance Build Security SLSA Level 3 | HIGH | https://github.blog/enterprise-software/devsecops/enhance-build-security-and-reach-slsa-level-3-with-github-artifact-attestations/ |
| 43 | pre-commit.com — Official Documentation | HIGH | https://pre-commit.com/ |
| 44 | AndyMadge.com — Git Hooks Comparison March 2026 | MEDIUM | https://www.andymadge.com/2026/03/10/git-hooks-comparison/ |
| 45 | Edopedia — Lefthook vs Husky 2026 | MEDIUM | https://www.edopedia.com/blog/lefthook-vs-husky/ |
| 46 | copier ReadTheDocs — Updating a Project | HIGH | https://copier.readthedocs.io/en/stable/updating/ |
| 47 | AIEchoes Substack — Template Once Update Everywhere with Copier | MEDIUM | https://aiechoes.substack.com/p/template-once-update-everywhere-build-ab3 |
| 48 | DEV Community — Copier vs Cookiecutter | MEDIUM | https://dev.to/cloudnative_eng/copier-vs-cookiecutter-1jno |
| 49 | googleapis/release-please-action — GitHub Repository | HIGH | https://github.com/googleapis/release-please-action |
| 50 | Oleksii Popov — NPM Release Automation Guide | MEDIUM | https://oleksiipopov.com/blog/npm-release-automation/ |
| 51 | Hamza K — Release-please vs Semantic-release | MEDIUM | https://www.hamzak.xyz/blog-posts/release-please-vs-semantic-release |
| 52 | npmtrends — Changesets vs Semantic-release | MEDIUM | https://npmtrends.com/changesets-vs-publish-please-vs-release-it-vs-semantic-release |
| 53 | Brian Schiller — Changesets vs Semantic Release | MEDIUM | https://brianschiller.com/blog/2023/09/18/changesets-vs-semantic-release/ |
| 54 | GitHub Docs — Email Addresses Reference | HIGH | https://docs.github.com/en/account-and-profile/reference/email-addresses-reference |
| 55 | GitHub Blog — Private Emails Now More Private | HIGH | https://github.blog/news-insights/product-news/private-emails-now-more-private/ |
| 56 | Nelson Figueroa — Scrape Contributor Emails from Git | MEDIUM | https://nelson.cloud/scrape-contributor-emails-from-any-git-repository/ |
| 57 | GitHub Changelog — Dependabot Org-Level Private Registries April 2026 | HIGH | https://github.blog/changelog/2026-04-14-dependabot-and-code-scanning-org-level-private-registries/ |
| 58 | github/gitignore — Repository | HIGH | https://github.com/github/gitignore |
| 59 | Semgrep Community Edition | HIGH | https://semgrep.dev/products/community-edition/ |
| 60 | Semgrep Rules Registry | HIGH | https://registry.semgrep.dev/ |
| 61 | Trail of Bits — Semgrep Rules | HIGH | https://github.com/trailofbits/semgrep-rules |
| 62 | Flare.io — Secrets Exposed in Docker Hub | MEDIUM | https://flare.io/learn/resources/docker-hub-secrets-exposed |
| 63 | SPDX Overview | HIGH | https://spdx.dev/learn/overview/ |
| 64 | OpsTree Blog — Git History Rewrite at Scale April 2026 | MEDIUM | https://opstree.com/blog/2026/04/07/git-history-rewrite-at-scale-removing-100mb-files-safely/ |
| 65 | GitHub Changelog — Push Protection Exemptions March 2026 | HIGH | https://github.blog/changelog/2026-03-23-push-protection-exemptions-from-repository-settings/ |

---

## Appendix: Research Log

**Date range**: 2026-04-21
**Queries run**: 22 WebSearch, 18 WebFetch, 0 context7
**Mode used**: deep
**Depth level**: deep

Context7 was not used because the library-specific documentation needs (gitleaks, git-filter-repo, syft, grype, osv-scanner, cosign, pre-commit, copier, semantic-release, release-please) were well-served by direct GitHub repository fetches and official documentation pages. One WebFetch to slsa.dev/how-to/get-started timed out and was substituted with a direct fetch to the slsa-github-generator repository and the GitHub changelog entry for SLSA Level 3 support, providing equivalent depth. The key unresolved gap is TruffleHog SARIF output — the tool's README, GitHub page, and secondary sources were all checked and none confirmed SARIF support, which is flagged in Limitations.
