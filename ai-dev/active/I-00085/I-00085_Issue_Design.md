# I-00085: `.mypy_cache/` triggers false-positive gitleaks findings (S12 → S16 ordering bug)

**Type**: Issue
**Severity**: Low
**Created**: 2026-05-15
**Reported By**: sergio (operator); diagnosed during CR-00053 manual rescue
**Status**: Draft

---

## ⛔ Docker is off-limits

(Standard policy. No Docker usage.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. No migration impact.)

## Description

`make security-secrets` runs `gitleaks detect --no-git`, which scans the
working tree directly, ignoring `.gitignore`. When QV gates run in their
canonical order, S12 (`make type-check`) populates `.mypy_cache/` with
cached type stubs from vendored packages. Some of those cache files
contain strings (e.g., `*.threading.local`, `*.local`) that match IW's
custom `iw-internal-fqdn` rule, so S16 (`make security-secrets`) reports
false-positive leaks every time it runs after S12.

CR-00053's S16 produced 3 such false positives on
`.mypy_cache/3.12/{sqlalchemy/event/attr.data.json, sqlalchemy/event/base.data.json, threading.data.json}`.
Workaround: `rm -rf .mypy_cache && make security-secrets`. Real fix: one
allowlist entry in `.gitleaks.toml`.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard
rules. Most relevant: `.gitleaks.toml` `[allowlist].paths` block.

## Steps to Reproduce

1. From a clean worktree, run `make type-check`. Observe `.mypy_cache/`
   is populated.
2. Run `make security-secrets`.
3. Observe: `gitleaks` reports `leaks found: 3` on cache files. The
   gate fails.

**Expected**: gates are independent — running them in any order produces
the same outcome.

**Actual**: S12 leaves cache state that breaks S16.

## Root Cause Analysis

`.gitleaks.toml`'s `[allowlist].paths` block has:

```toml
'''(?i)(?:^|/)__pycache__/''',
```

But not `.mypy_cache/`, `.ruff_cache/`, or `.pytest_cache/`. All three
are tool-managed cache directories that:

- Are gitignored (so should never reach commits — gitleaks's `--no-git`
  flag bypasses this).
- May contain vendored type/test data that incidentally matches IW
  custom rules.

The fix is appending three lines to the allowlist. There is no behaviour
change; gitleaks already skips `__pycache__/` for the same reason.

## Affected Components

| Component | Impact |
|-----------|--------|
| `.gitleaks.toml` | Missing 3 cache-directory allowlist entries |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Pipeline | Append `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/` to `[allowlist].paths` in `.gitleaks.toml` | — |
| S02 | CodeReview | Per-agent review of S01 | — |
| S03 | Tests | Reproduction test: `make type-check && make security-secrets` produces zero leaks | — |
| S04 | CodeReview | Per-agent review of S03 | — |
| S05 | CodeReview_Final | Cross-agent global review | — |
| S06..S13 | QV Gates | lint, assertions, format, typecheck, unit-tests, integration-tests, diff-coverage, security-secrets | — |
| S14 | SelfAssess | Self-assessment via iw-item-analyze skill | — |

### Database Changes

- **New tables**: None.
- **Modified tables**: None.
- **Migration notes**: No schema impact.

### Code Changes

- **Files to modify**: `.gitleaks.toml`.
- **Nature of change**: 3-line allowlist addition, with comment.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `I-00085_Issue_Design.md` | Design | This document |
| `I-00085_Functional.md` | Design | Human-facing summary |
| `workflow-manifest.json` | Manifest | Step definitions |
| `prompts/I-00085_S01_Pipeline_prompt.md` | Prompt | S01 fix |
| `prompts/I-00085_S02_CodeReview_Pipeline_prompt.md` | Prompt | S02 review |
| `prompts/I-00085_S03_Tests_prompt.md` | Prompt | S03 tests |
| `prompts/I-00085_S04_CodeReview_Tests_prompt.md` | Prompt | S04 test review |
| `prompts/I-00085_S05_CodeReview_Final_prompt.md` | Prompt | S05 global review |
| `prompts/I-00085_S14_SelfAssess_prompt.md` | Prompt | S14 self-assess |

## Test to Reproduce

```python
def test_i00085_security_secrets_clean_after_type_check(tmp_path, monkeypatch):
    """make type-check must not leave cache state that triggers
    false-positive gitleaks findings.

    This test should FAIL before the fix and PASS after.
    """
    import subprocess

    project_root = ...  # path to the project
    monkeypatch.chdir(project_root)
    # Clean baseline
    subprocess.run(["rm", "-rf", ".mypy_cache"], check=True)
    # Populate cache
    subprocess.run(["make", "type-check"], check=True)
    # Run gitleaks via the project gate
    result = subprocess.run(
        ["make", "security-secrets"], capture_output=True, text=True
    )

    # Assert
    assert result.returncode == 0, (
        f"gitleaks must not flag .mypy_cache/ contents; "
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "leaks found: 0" in result.stdout or "no leaks found" in result.stdout, (
        "gitleaks output must report zero leaks"
    )
```

This test mutates global project state (`.mypy_cache/`), so it must be
marked appropriately (e.g., `@pytest.mark.serial` if the project has
such a marker, or guarded so it doesn't run under `pytest -n auto`).

## Acceptance Criteria

### AC1: Bug is fixed

```
Given an empty .mypy_cache directory
When `make type-check` runs followed by `make security-secrets`
Then `make security-secrets` exits 0 with zero leaks reported
```

### AC2: Regression test exists

```
Given the fix is applied
When the test suite runs
Then tests/integration/test_security_secrets_cache_independence.py passes
```

### AC3: Real secret detection still works

```
Given a fake real secret is committed (e.g., a test fixture under tests/fixtures/)
When `make security-secrets` runs
Then the secret is detected (allowlist additions must NOT mask real secrets)
```

## Regression Prevention

- The reproduction test exercises the exact S12 → S16 sequence.
- AC3's negative test (real secret still detected) prevents over-broad
  allowlist edits.
- Inline comment in `.gitleaks.toml` cites I-00085 so future contributors
  understand why the cache directories are listed.

## Dependencies

- **Depends on**: None.
- **Blocks**: None (purely diagnostic-noise reduction).

## Impacted Paths

- `.gitleaks.toml`
- `tests/integration/test_security_secrets_cache_independence.py`

## TDD Approach

- Reproducing test: as above. Note the global-state caveat.
- Unit tests: not applicable (config-only change).
- Integration tests: the reproduction test + AC3's negative test.

## Notes

This is the smallest of the four sibling incidents (I-00082..I-00085).
The fix is three lines in `.gitleaks.toml` plus a regression test. Filed
Low severity because:

- Does not block any work (operator workaround is `rm -rf .mypy_cache`).
- Was discovered cleanly during CR-00053's S16 manual run; would have
  triggered I-00082-style fix-cycle drift if the daemon had been the
  one to encounter it.

Concrete CR-00053 evidence: gitleaks reported 3 findings on
`.mypy_cache/3.12/{sqlalchemy/event/attr.data.json,
sqlalchemy/event/base.data.json, threading.data.json}` — all
`iw-internal-fqdn` rule matches on cached vendored Python type stubs.
