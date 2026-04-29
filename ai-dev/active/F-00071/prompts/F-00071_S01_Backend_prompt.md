# F-00071_S01_Backend_prompt

**Work Item**: F-00071 -- Local + CI Security Scanning
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

(Standard policies. Trivy image scans read existing images; do not start/stop/build infra containers as part of this step.)

## Input Files

- `uv run iw item-status F-00071 --json`
- `ai-dev/active/F-00071/F-00071_Feature_Design.md`
- `Makefile` — current targets
- `pyproject.toml` — current dev deps
- `.gitignore`
- `.github/workflows/compliance-scan.yml` — pattern reference for SHA pinning, permissions, SARIF upload
- `docker-compose.yml`, `docker-compose.bootstrap.yml`, `docker-compose.e2e.yml`, all Dockerfiles — Trivy IaC scan targets
- `CLAUDE.md`, `tests/CLAUDE.md`

## Output Files

- Modified: `Makefile`, `pyproject.toml`, `.gitignore`, README or `docs/IW_AI_Core_Tech_Stack.md`
- New: `.trivyignore`, `.github/workflows/security-scan.yml`
- `ai-dev/active/F-00071/reports/F-00071_S01_Backend_report.md`

## Context

Implement local + CI security scanning. Tests are S03; reviews are S02/S04/S05; QV gates are S06+. Your scope is Makefile + workflow + config + dep additions.

## Requirements

### 1. Add `pip-audit` and `bandit` to dev deps

In `pyproject.toml` `[dependency-groups] dev`:

```toml
"pip-audit>=2.7",
"bandit[toml]>=1.7",
```

Run `uv sync`.

Add `[tool.bandit]` config to pyproject.toml:

```toml
[tool.bandit]
exclude_dirs = ["tests", "scripts", "orch/db/migrations/versions", ".venv"]
skips = ["B101"]   # assert statements (rare in non-test code; explicit skip for sanity)
```

Per the design, do NOT use a separate `.bandit.yml` — pyproject is canonical.

### 2. Update `.gitignore`

Add `tests/output/security/` if not already covered. (F-00069 added `tests/output/`; verify whether the broader path is in the gitignore. If `tests/output/` covers everything, no change needed.)

### 3. Create `.trivyignore`

```
# .trivyignore — justified Trivy ignores live here.
#
# Format:
#   <CVE-ID>             # Reason (expiry: YYYY-MM-DD)
#   <misconfig-rule-id>  # Reason (expiry: YYYY-MM-DD)
#
# Every entry MUST have a reason and an expiry date. Stale entries (past
# expiry) should be reviewed and either renewed with new reason or removed.
#
# (No active ignores at the time of F-00071.)
```

### 4. Add Make targets

Add these targets to `Makefile`. Place them in a clearly delimited "Security" section. Add all new target names to `.PHONY`.

```makefile
# --- Security ---
SECURITY_DIR := tests/output/security

security-deps:
	@command -v pip-audit >/dev/null 2>&1 || { \
		echo "ERROR: 'pip-audit' not found."; \
		echo "Install: uv add --dev pip-audit"; \
		exit 1; \
	}
	@command -v bandit >/dev/null 2>&1 || { \
		echo "ERROR: 'bandit' not found."; \
		echo "Install: uv add --dev bandit[toml]"; \
		exit 1; \
	}
	@mkdir -p $(SECURITY_DIR)
	@echo "[security-deps] pip-audit ..."
	@uv run pip-audit --format=json --output=$(SECURITY_DIR)/pip-audit.json || true
	@uv run pip-audit --strict   # fails on any vuln
	@echo "[security-deps] bandit ..."
	@uv run bandit -r orch dashboard executor -c pyproject.toml -f json -o $(SECURITY_DIR)/bandit.json -ll || true
	@uv run bandit -r orch dashboard executor -c pyproject.toml -ll
	@echo "[security-deps] OK"

security-iac:
	@command -v trivy >/dev/null 2>&1 || { \
		echo "ERROR: 'trivy' not found."; \
		echo "Install: brew install trivy   (or)   curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin"; \
		exit 1; \
	}
	@mkdir -p $(SECURITY_DIR)
	@echo "[security-iac] trivy config ..."
	@trivy config --severity HIGH,CRITICAL --format json --output $(SECURITY_DIR)/trivy-iac.json --exit-code 1 .

security-image-dashboard:
	@command -v trivy >/dev/null 2>&1 || { echo "ERROR: 'trivy' not found. See 'make security-iac' for install hint."; exit 1; }
	@docker image inspect iw-ai-core-dashboard:local >/dev/null 2>&1 || { \
		echo "ERROR: image 'iw-ai-core-dashboard:local' not found."; \
		echo "Build it first via your usual build pipeline."; \
		exit 1; \
	}
	@mkdir -p $(SECURITY_DIR)
	@trivy image --severity HIGH,CRITICAL --format json --output $(SECURITY_DIR)/trivy-image-dashboard.json --exit-code 1 iw-ai-core-dashboard:local

security-all: security-deps security-iac
	@echo "[security-all] complete (image scans run separately if images are built)"

security-report:
	@uv run python scripts/security_report.py
```

If the project does NOT have a separate dashboard image (i.e., it runs from source via `make dashboard-start`), make `security-image-dashboard` print a one-line "no built image — N/A for this project" message and exit 0 (so it doesn't block `security-all`). Verify by inspecting `docker-compose*.yml`.

Create `scripts/security_report.py` that aggregates `pip-audit.json`, `bandit.json`, and `trivy-iac.json` into a single `report.json` and Markdown summary. Treat missing inputs as "skipped — tool unavailable".

### 5. Create `.github/workflows/security-scan.yml`

```yaml
# Security scan — pip-audit, bandit, trivy (IaC + image)
#
# Failure policy: HIGH + CRITICAL findings block the workflow.
# MEDIUM/LOW findings appear in GitHub Code Scanning but do not fail.
# Action versions are pinned to commit SHAs to prevent supply-chain risk.

name: Security Scan

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]
  schedule:
    - cron: "0 6 * * 1"   # weekly, Monday 06:00 UTC

permissions:
  contents: read
  security-events: write

jobs:
  deps-audit:
    name: Python deps + bandit
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@<PIN>          # pin to a real SHA — see compliance-scan.yml
        with:
          persist-credentials: false

      - name: Install uv
        uses: astral-sh/setup-uv@<PIN>        # pin to a real SHA

      - name: Install deps
        run: uv sync --frozen

      - name: pip-audit
        run: |
          set -euo pipefail
          mkdir -p .iw
          uv run pip-audit --format=sarif --output=.iw/pip-audit.sarif || true
          uv run pip-audit --strict   # fails on any HIGH/CRITICAL

      - name: Bandit
        run: |
          set -euo pipefail
          uv run bandit -r orch dashboard executor -c pyproject.toml -f sarif -o .iw/bandit.sarif -ll || true
          uv run bandit -r orch dashboard executor -c pyproject.toml -ll

      - name: Upload pip-audit SARIF
        if: always()
        uses: github/codeql-action/upload-sarif@<PIN>
        with:
          sarif_file: .iw/pip-audit.sarif
          category: pip-audit

      - name: Upload Bandit SARIF
        if: always()
        uses: github/codeql-action/upload-sarif@<PIN>
        with:
          sarif_file: .iw/bandit.sarif
          category: bandit

  iac-scan:
    name: Trivy IaC scan
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@<PIN>
        with:
          persist-credentials: false

      - name: Run Trivy config scan
        uses: aquasecurity/trivy-action@<PIN>
        with:
          scan-type: config
          severity: HIGH,CRITICAL
          exit-code: '1'
          format: sarif
          output: trivy-iac.sarif

      - name: Upload SARIF
        if: always()
        uses: github/codeql-action/upload-sarif@<PIN>
        with:
          sarif_file: trivy-iac.sarif
          category: trivy-iac
```

Resolve `<PIN>` placeholders to actual commit SHAs by:
1. Looking up the latest stable release of each action (e.g. `actions/checkout` v4 → look at `compliance-scan.yml` for the SHA already pinned there).
2. Use `gh api repos/<owner>/<repo>/git/refs/tags/<tag>` to resolve a tag to a SHA if needed.
3. NEVER pin to `@v4`, `@main`, or any non-SHA reference.
4. Add a `# vX.Y.Z` comment after each SHA per `compliance-scan.yml` convention.

Do NOT add an image-scan job initially — the project doesn't yet build versioned images in CI. Add a TODO comment in the workflow file explaining the absent job and what would be required to add it later (a build step + a docker save + trivy image).

### 6. README / Tech Stack doc

Add a short paragraph (≤120 words) to either `README.md` (preferred if it has a Security section already) or `docs/IW_AI_Core_Tech_Stack.md` explaining:

- The three security axes (SAST/secrets/deps+IaC) and which workflow covers each.
- The local Make targets developers can run.
- The HIGH/CRITICAL gating threshold.

### 7. NOT in this step

- Tests — S03 owns them.
- Frontend — none.
- Browser verification — none (no UI changes).

## Project Conventions

- Follow `compliance-scan.yml`'s patterns exactly: SHA pins, permissions block, `set -euo pipefail`.
- Match Makefile style of existing targets in the project (one-tab indent, no recursive `make` calls).
- Bandit config in `[tool.bandit]` (not `.bandit.yml`).

## TDD Requirement

The Makefile + workflow are exercised by S03's tests. For S01, smoke-check by hand:
- `make security-deps` (after installing pip-audit + bandit via `uv sync`).
- `make security-iac` if Trivy is available locally; if not, confirm the install-hint path works.
- `gh workflow view "Security Scan"` is meaningless until the file is on a branch — defer to CI verification.

## Pre-flight Quality Gates

1. `make format`
2. `make typecheck`
3. `make lint`
4. `make test-unit`

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "F-00071",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "Makefile",
    "pyproject.toml",
    ".gitignore",
    ".trivyignore",
    ".github/workflows/security-scan.yml",
    "scripts/security_report.py",
    "README.md or docs/IW_AI_Core_Tech_Stack.md"
  ],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "action_pins_resolved": [
    {"action": "actions/checkout", "sha": "<40-char>", "tag": "v4.x.y"}
  ],
  "blockers": [],
  "notes": ""
}
```
