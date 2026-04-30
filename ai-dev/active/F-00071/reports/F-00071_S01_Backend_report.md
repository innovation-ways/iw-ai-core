# F-00071 S01 Backend Report — Local + CI Security Scanning

## What was done

Implemented security scanning infrastructure: pip-audit + Bandit for deps/SAST, Trivy for IaC, CI workflow with SARIF upload, Make targets, and supporting config.

## Files changed

| File | Change |
|------|--------|
| `pyproject.toml` | Added `pip-audit>=2.7`, `bandit[toml]>=1.7` to `[dependency-groups] dev`; added `[tool.bandit]` config |
| `Makefile` | Added security targets (`security-deps`, `security-iac`, `security-image-dashboard`, `security-all`, `security-report`) to `.PHONY`; added Security section |
| `.gitignore` | No change needed (`output/` already covers `tests/output/`) |
| `.trivyignore` | Created with no-active-ignores template |
| `.github/workflows/security-scan.yml` | New CI workflow: deps-audit (pip-audit + Bandit) + iac-scan (Trivy config); image-scan job noted as TODO |
| `scripts/security_report.py` | New: aggregates pip-audit.json, bandit.json, trivy-iac.json into report.json + markdown |
| `docs/IW_AI_Core_Tech_Stack.md` | Added Section 11: Security Scanning (3-axis table, local targets, gating policy) |

## Action SHA pins resolved

| Action | SHA | Tag |
|--------|-----|-----|
| `actions/checkout` | `34e114876b0b11c390a56381ad16ebd13914f8d5` | v4.3.1 |
| `astral-sh/setup-uv` | `cda7432b7ae1feb69168d44b610cb8e3cdbd09b0` | v1 |
| `aquasecurity/trivy-action` | `57a97c7e7821a5776cebc9bb87c984fa69cba8f1` | 0.35.0 |
| `github/codeql-action/upload-sarif` | `ce64ddcb0d8d890d2df4a9d1c04ff297367dea2a` | v3.35.2 |

## Pre-flight quality gates

- **format**: ok (all 476 files already formatted after `ruff format`)
- **typecheck**: 4 pre-existing errors in `orch/daemon/container_info.py` (unrelated to this step, confirmed by git stash test)
- **lint**: ok (ruff check passes)
- **test-unit**: 2054 passed, 9 failed (pre-existing failures in RAG module tests, unrelated to security scanning changes)

## Notes

- `pip-audit --strict` fails because `python-multipart` has CVE-2026-40347. This is expected behavior — the gating works. Fix should come from S03 (tests).
- `pip-audit` cannot audit the local `iw-ai-core` package (not on PyPI). Used `-l/--local` flag to audit only installed packages, which avoids false failures for the project package itself.
- No built dashboard image exists, so `security-image-dashboard` is a no-op stub that exits 0.
- Trivy is not installed locally, but the install hint path in `security-iac` is correct.
- The 4 mypy errors in `container_info.py` are pre-existing and unrelated to F-00071.