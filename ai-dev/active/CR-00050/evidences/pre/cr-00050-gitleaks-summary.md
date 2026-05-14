# gitleaks RED scan summary — CR-00050 S01

**Scan date**: 2026-05-14
**Command**: `gitleaks detect --no-git --config .gitleaks.toml --report-format json --report-path /tmp/cr-00050-red.json -v`
**Total findings**: 74

## Findings by RuleID

| RuleID | Count |
|--------|-------|
| iw-internal-fqdn | 32 |
| iw-internal-email | 27 |
| iw-rfc1918-ip | 14 |
| generic-api-key | 1 |

## Findings by path (top 20)

| Path | Count |
|------|-------|
| orch/oss/fix_recipes/community.py | 7 |
| tests/unit/test_oss_results_helper.py | 6 |
| dashboard/services/oss_check_catalog.yaml | 6 |
| .tmp/CR-00050_S01.prompt | 5 |
| ai-dev/active/CR-00050/prompts/CR-00050_S01_Backend_prompt.md | 5 |
| ai-dev/active/CR-00050/CR-00050/prompts/CR-00050_S01_Backend_prompt.md | 5 |
| .github/workflows/test-quality.yml | 3 |
| tests/unit/test_oss_dashboard_service.py | 2 |
| orch/oss/fix_recipes/governance.py | 2 |
| orch/oss/config_writer.py | 2 |
| CONTRIBUTING.md | 2 |
| ai-dev/active/CR-00050/CR-00050_CR_Design.md | 2 |
| ai-dev/active/CR-00050/CR-00050/CR-00050_CR_Design.md | 2 |
| tests/unit/test_oss_secrets_parser.py | 1 |
| tests/unit/test_browser_env.py | 1 |
| tests/unit/staleness/test_service.py | 1 |

## Unique (RuleID, file-glob) groups

### 1. `generic-api-key` / `tests/unit/test_oss_secrets_parser.py`
- Match: `API_KEY=sk-abcd1234ZZZZ9999XY`
- Classification: **FALSE_POSITIVE_PATH** — test fixture string deliberately secret-shaped for the secrets-parser unit tests

### 2. `iw-internal-email` / all docs, config, skill files
- Value: `info@innovation-ways.com` (and `security@innovation-ways.com`)
- Classification: **FALSE_POSITIVE_VALUE** — contact email published in public docs (README, CODE_OF_CONDUCT, CONTRIBUTING, SECURITY, SUPPORT); not a secret

### 3. `iw-internal-fqdn` / `tests/unit/` various files
- Values: `dev@example.local`, `foo.local`, `test.local`, `example.local`
- Classification: **FALSE_POSITIVE_PATH** — RFC 6761 reserved test domains used as test fixtures

### 4. `iw-internal-fqdn` / `dashboard/services/oss_check_catalog.yaml`
- Value: `env.local`
- Classification: **FALSE_POSITIVE_VALUE** — YAML config key name, not a real hostname

### 5. `iw-internal-fqdn` / `.dockerignore`, `.gitignore`
- Value: `env.local`
- Classification: **FALSE_POSITIVE_VALUE** — same pattern as above

### 6. `iw-internal-fqdn` / `Dockerfile.e2e`, `.github/workflows/test-quality.yml`
- Value: `iw-ai-core.local`
- Classification: **FALSE_POSITIVE_VALUE** — Docker service name in compose file, not a real internal hostname

### 7. `iw-rfc1918-ip` / `tests/unit/` files
- Values: `10.0.0.1` in test fixtures
- Classification: **FALSE_POSITIVE_PATH** — RFC 1918 address used as test data

### 8. `iw-internal-fqdn` / `orch/` files (browser_env.py, config_writer.py)
- Values: `example.local` in test fixture data embedded in production code
- Classification: **FALSE_POSITIVE_VALUE** — example fixture data

### 9. `iw-internal-fqdn` / `ai-dev/`, `.tmp/` prompt files
- Values: `example.local`, `foo.local`
- Classification: **FALSE_POSITIVE_PATH** — design doc drafts and prompt files, not production code
