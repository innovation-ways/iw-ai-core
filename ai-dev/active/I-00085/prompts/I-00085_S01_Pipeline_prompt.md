# I-00085_S01_Pipeline_prompt

**Work Item**: I-00085 — .mypy_cache triggers gitleaks false positives
**Step**: S01
**Agent**: pipeline-impl

---

## ⛔ Docker is off-limits

(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. No migration impact.)

## Input Files

- **Runtime step state**: `uv run iw item-status I-00085 --json`
- `ai-dev/active/I-00085/I-00085_Issue_Design.md` — READ FIRST
- `.gitleaks.toml` — current allowlist

## Output Files

- `ai-dev/work/I-00085/reports/I-00085_S01_Pipeline_report.md`
- Modified: `.gitleaks.toml`

## Context

Single-config-file fix. Three lines added to the `[allowlist].paths`
block, matching the existing style of the `__pycache__/` entry that is
already present.

## Requirements

### 1. `.gitleaks.toml` allowlist additions

Locate the `[allowlist].paths` block (currently contains `__pycache__/`,
`docs/`, `tests/fixtures/`, etc.). Find the `__pycache__/` entry and
immediately after it add:

```toml
  '''(?i)(?:^|/)\.mypy_cache/''',
  '''(?i)(?:^|/)\.ruff_cache/''',
  '''(?i)(?:^|/)\.pytest_cache/''',
```

(Adjust the surrounding indentation / comma style to match the existing
file. The existing entries use the same `(?i)(?:^|/)` prefix; mirror it
exactly.)

### 2. Inline comment

Above the three new entries, add a single comment line:

```toml
  # I-00085: tool-managed cache directories — same rationale as __pycache__/
  # above. .mypy_cache/ in particular contains vendored type-stub strings
  # (e.g., *.local) that match the iw-internal-fqdn rule.
```

### 3. Order matters within the block?

No — gitleaks treats the path list as an unordered set. Place the three
entries adjacent to `__pycache__/` for human readability.

### 4. Verify the fix

After editing, run from the worktree root:

```bash
rm -rf .mypy_cache
make type-check
make security-secrets
```

`make security-secrets` must exit 0. If it doesn't, the regex syntax
is off — debug with `gitleaks detect --no-git --config .gitleaks.toml --verbose`
to see what's still triggering.

## Project Conventions

Read `CLAUDE.md`. Match the existing TOML style in `.gitleaks.toml`
exactly — indentation, quoting, comma placement.

## TDD Requirement

RED first: write the reproduction test from the design doc and confirm
it fails against pre-fix `.gitleaks.toml` (3 leaks reported on
`.mypy_cache/`). Capture the failing line in `tdd_red_evidence`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

- `make format` (likely no-op)
- `make type-check` (will populate `.mypy_cache/`)
- `make lint`

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/integration/test_security_secrets_cache_independence.py -v
```

Do NOT run `make test-integration`.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "pipeline-impl",
  "work_item": "I-00085",
  "completion_status": "complete|partial|blocked",
  "files_changed": [".gitleaks.toml"],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/integration/test_security_secrets_cache_independence.py::test_i00085_security_secrets_clean_after_type_check — AssertionError: gitleaks reported 3 leaks on .mypy_cache/",
  "blockers": [],
  "notes": ""
}
```
