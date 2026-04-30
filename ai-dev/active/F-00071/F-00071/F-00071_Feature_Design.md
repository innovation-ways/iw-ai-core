# F-00071: Local + CI Security Scanning

**Type**: Feature
**Priority**: High
**Created**: 2026-04-29
**Status**: Draft

---

## ⛔ Docker is off-limits

(Standard policy. Trivy image scanning IS in scope — but the agent never starts/stops/recreates infrastructure containers. Trivy reads images as build artefacts.)

## ⛔ Migrations: agents generate, daemon applies

This feature does NOT modify migrations.

## Description

Add explicit dependency-CVE, infrastructure-as-code, and container-image scanning to AI Core, both as local Make targets developers can run and as a CI workflow that runs on PRs and weekly. Today AI Core has CodeQL (SAST) and gitleaks (secrets) in CI but ZERO dependency-CVE auditing — a known gap surfaced in the podforger comparison. This feature closes that gap.

## Project Context

Read `CLAUDE.md`. Existing security CI:
- `.github/workflows/codeql.yml` — SAST for Python + JS
- `.github/workflows/compliance-scan.yml` — gitleaks (secrets) + OSS license/structure
- `.github/workflows/scorecard.yml` — OpenSSF Scorecard

This feature adds a third axis: **dependency CVEs and IaC misconfigurations**.

## Scope

### In Scope

1. **Local Make targets**
   - `make security-deps` — runs `pip-audit` (Python deps) and `bandit -r orch/ dashboard/ executor/` (Python static security analysis). Emits findings to terminal and to `tests/output/security/` as JSON. Exits non-zero if any HIGH/CRITICAL finding.
   - `make security-iac` — runs `trivy config` against the repo root (scans Dockerfiles, docker-compose YAMLs, GitHub Actions workflows for misconfigurations). Output to `tests/output/security/trivy-iac.json`. Exits non-zero on HIGH/CRITICAL.
   - `make security-image-dashboard` — `trivy image` against the locally built dashboard image (assumes the developer ran the appropriate build first; if the image is absent, target prints a clear "build first" hint and exits non-zero).
   - `make security-image-daemon` — same pattern for the daemon image, IF the project has separate daemon and dashboard images (verify by inspecting `docker-compose*.yml`; consolidate into a single `security-image` target if there's only one).
   - `make security-all` — runs `security-deps`, `security-iac`, and any image scans available, aggregating exit codes.
   - `make security-report` — generates a single combined JSON report at `tests/output/security/report.json` (aggregates pip-audit, bandit, trivy outputs) and a human-readable Markdown summary at `tests/output/security/report.md`.

2. **Tool installation guards**
   - Each Make target MUST check for the required CLI on PATH and emit a clear install hint if missing (`pip-audit` → uv add, `bandit` → uv add, `trivy` → brew/apt/curl install). The target exits non-zero on missing tool — never silently no-op.

3. **Configuration files**
   - `.bandit.yml` (or `[tool.bandit]` in pyproject.toml) — exclude `tests/`, `scripts/`, `orch/db/migrations/versions/`. Skip `B101` (assert) for tests if Bandit is configured to scan tests anyway. Pin severity threshold so MEDIUM warnings don't fail CI but can be reviewed locally.
   - `.trivyignore` — empty initially; placeholder for future justified ignores. Comment block at the top explaining the ignore-comment convention (`# CVE-YYYY-NNNN: <reason> (<expiry-date>)`).
   - `pyproject.toml` — add `pip-audit` and `bandit` to the `dev` dependency group.

4. **CI workflow**
   - New file `.github/workflows/security-scan.yml`:
     - Triggers: `pull_request` to main, `push` to main, weekly cron (`0 6 * * 1` — Monday 06:00 UTC).
     - Permissions: `contents: read`, `security-events: write` (for SARIF upload).
     - Three jobs (or one job with three steps — pick whichever surfaces failures more clearly in the GitHub PR check list):
       - **deps-audit** — install `pip-audit` and `bandit`; run them with SARIF output; upload SARIF to GitHub Code Scanning.
       - **iac-scan** — install Trivy; run `trivy config` with SARIF output; upload.
       - **image-scan** — build the dashboard image (or pull a tagged release if one exists); run `trivy image` with SARIF output; upload. Skip if no buildable image is committed at the time the job runs.
     - Action versions pinned to commit SHAs (matching the convention in `compliance-scan.yml` — that file pins `actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5`).
     - Step that runs the scans uses `set -euo pipefail`.
     - Failure threshold: HIGH + CRITICAL block the merge; MEDIUM/LOW reported but non-blocking. Document this in a comment block at the top of the workflow.

5. **Documentation**
   - Add a brief "Security Scanning" section to the README or `docs/IW_AI_Core_Tech_Stack.md` explaining the three scan axes (SAST/secrets/deps+IaC) and how to run each locally. One short paragraph; no separate doc.

### Out of Scope

- Adding gitleaks to local Make targets — `compliance-scan.yml` already covers it in CI, and a local pre-commit hook is owned by F-00070 (already excluded from F-00070 scope per its design — could be a future CR).
- License scanning — `compliance-scan.yml` already runs license checks via the OSS publish skill.
- Mutation testing, SAST tools beyond CodeQL.
- Snyk, Dependabot configuration changes.
- Container runtime security (falco etc.).
- Automatic vulnerability patching / PRs.
- Codecov / coverage reporting (owned by F-00069).

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Makefile targets, pyproject deps, `.bandit.yml`/pyproject `[tool.bandit]`, `.trivyignore`, `.github/workflows/security-scan.yml`, README/docs section | — |
| S02 | code-review-impl | Review S01 (Makefile + workflow + configs) | — |
| S03 | tests-impl | Smoke tests asserting Make targets present and workflow file structure (yaml-parseable, expected jobs) | — |
| S04 | code-review-impl | Review S03 | — |
| S05 | code-review-final-impl | Cross-cutting global review | — |
| S06–S09 | qv-gate | lint, format, typecheck, unit-tests | — |

No frontend step. No browser verification.

### Database Changes

None.

### API Changes

None.

### Frontend Changes

None.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `ai-dev/active/F-00071/F-00071_Feature_Design.md` | Design | This document |
| `ai-dev/active/F-00071/workflow-manifest.json` | Manifest | Step definitions |
| `ai-dev/active/F-00071/prompts/F-00071_S01_Backend_prompt.md` | Prompt | S01 implementation |
| `ai-dev/active/F-00071/prompts/F-00071_S02_CodeReview_prompt.md` | Prompt | Review of S01 |
| `ai-dev/active/F-00071/prompts/F-00071_S03_Tests_prompt.md` | Prompt | Test step |
| `ai-dev/active/F-00071/prompts/F-00071_S04_CodeReview_Tests_prompt.md` | Prompt | Review of S03 |
| `ai-dev/active/F-00071/prompts/F-00071_S05_CodeReview_Final_prompt.md` | Prompt | Final review |
| `Makefile` | Modified | Add `security-deps`, `security-iac`, `security-image-*`, `security-all`, `security-report` targets |
| `pyproject.toml` | Modified | Add `pip-audit` and `bandit` to dev deps; add `[tool.bandit]` config (or `.bandit.yml`) |
| `.trivyignore` | New | Placeholder with documentation |
| `.github/workflows/security-scan.yml` | New | CI workflow for deps/IaC/image scans |
| `tests/unit/test_security_targets.py` | New | Smoke test for Makefile + workflow presence |
| `scripts/security_report.py` | New | Aggregates pip-audit, bandit, trivy JSON outputs into combined report.json + report.md |
| `README.md` or `docs/IW_AI_Core_Tech_Stack.md` | Modified | Add brief Security Scanning section |

## Acceptance Criteria

### AC1: Local dependency audit works

```
Given a developer has run `uv sync` so dev deps are installed
When the developer runs `make security-deps`
Then pip-audit runs against the project's installed packages
And bandit runs against orch/, dashboard/, executor/
And both write JSON output under tests/output/security/
And the target exits 0 if no HIGH/CRITICAL findings
And the target exits non-zero if any HIGH/CRITICAL finding exists
```

### AC2: IaC scan works

```
Given Trivy is installed locally
When the developer runs `make security-iac`
Then Trivy scans Dockerfiles, docker-compose*.yml, and .github/workflows/*.yml
And produces JSON output at tests/output/security/trivy-iac.json
And exits non-zero on HIGH/CRITICAL misconfigurations
```

### AC3: Tool-missing UX

```
Given pip-audit (or bandit, or trivy) is not on PATH
When the developer runs `make security-deps` (or security-iac, or security-image-*)
Then the target prints a clear install hint (uv add / brew / apt / curl URL)
And exits non-zero
And does not silently no-op or attempt automatic installation
```

### AC4: CI workflow runs on PRs

```
Given a PR is opened against main
When the security-scan.yml workflow triggers
Then deps-audit, iac-scan, and image-scan jobs run
And all upload SARIF findings to GitHub Code Scanning
And the workflow fails if any HIGH/CRITICAL finding is reported
And MEDIUM/LOW findings are visible but do not fail the workflow
```

### AC5: Smoke test catches deletions

```
Given a developer accidentally removes one of the Makefile security targets
When `make test-unit` runs
Then tests/unit/test_security_targets.py fails with a clear message naming the missing target
```

### AC6: Aggregate report

```
Given all scans completed (or were skipped due to missing tools)
When the developer runs `make security-report`
Then a single JSON file at tests/output/security/report.json exists summarising pip-audit, bandit, trivy outputs
And a human-readable tests/output/security/report.md summary is generated
And missing scans are listed as "skipped — tool unavailable" rather than crashing
```

## Boundary Behavior

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| pip-audit not installed | Missing CLI | `make security-deps` prints install hint, exits non-zero |
| bandit reports MEDIUM only | No HIGH/CRITICAL | `make security-deps` exits 0 (success) but writes findings to JSON |
| trivy not installed | Missing CLI | `make security-iac` prints install hint, exits non-zero |
| No buildable image | First-time run | `make security-image-*` prints "image not found, build first" and exits non-zero |
| `tests/output/security/` missing | Directory absent | Targets create it lazily; do not fail |
| pip-audit finds HIGH CVE | Real vuln | `make security-deps` exits non-zero; CI blocks PR |
| HIGH CVE has documented `.trivyignore` entry | Justified ignore | Trivy excludes from results; scan passes |
| No CVEs anywhere | Clean state | `make security-all` exits 0; SARIF uploaded as empty |
| GitHub Actions runs in fork PR | No write permission | Workflow runs in read-only mode; SARIF upload is gracefully skipped |

## Invariants

1. No security target may silently no-op when its required CLI is missing.
2. All GitHub Action versions in `security-scan.yml` are pinned to commit SHAs (no `@v4`, no `@main`).
3. The CI workflow MUST request only `contents: read` and `security-events: write` permissions — no broader scopes.
4. The HIGH/CRITICAL gating threshold is consistent between local Make targets and the CI workflow (so a passing local run predicts a passing CI run modulo timing/network).
5. `tests/output/security/` is gitignored (do not commit scan artefacts).
6. The Bandit configuration excludes `tests/`, `scripts/`, and migrations to avoid noise.
7. No new `[project] dependencies` are added — `pip-audit` and `bandit` are dev-only.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## TDD Approach

- **Unit tests** (`tests/unit/test_security_targets.py`):
  - Read `Makefile` as text; assert each new target name exists (`security-deps`, `security-iac`, `security-image-`, `security-all`, `security-report`).
  - Parse `.github/workflows/security-scan.yml` with `pyyaml`; assert the expected `jobs:` keys exist; assert action versions are pinned to a 40-character SHA (regex `^[0-9a-f]{40}$`).
  - Assert `pip-audit` and `bandit` are present in `[dependency-groups] dev`.
  - Assert `tests/output/security/` is in `.gitignore`.
- **Integration tests**: None.
- **Edge cases**: pinning regex tolerates the optional `# vN.N.N` comment after the SHA (don't accidentally fail on commented action versions).

## Notes

- The `pip-audit` vs Trivy choice for Python deps was made in the planning conversation: pip-audit + Bandit locally (lighter, no Docker required), Trivy for IaC and images. Don't substitute Trivy for the Python deps scan.
- Action SHA pinning matters here because security tools that themselves are compromised would invert the trust model. Match the pinning convention used by `compliance-scan.yml`.
- This feature is independent of F-00069 and F-00070 — the batch executor can run all three in parallel.
- After this lands, AI Core has SAST (CodeQL) + secrets (gitleaks) + deps-CVE (pip-audit) + IaC (trivy config) + image (trivy image) + Python static-security (bandit) — comparable to podforger's `make security-all` surface.
