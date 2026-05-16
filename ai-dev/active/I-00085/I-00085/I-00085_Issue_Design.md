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

The test is **isolated** — it runs `gitleaks` against a tmp_path
sandbox using the project's actual `.gitleaks.toml` as `--config`. It
does **not** mutate `.mypy_cache/` in the worktree, does not run
`make type-check`, and does not depend on the rest of the worktree
being gitleaks-clean.

```python
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]  # tests/integration/ → repo root
GITLEAKS_CONFIG = PROJECT_ROOT / ".gitleaks.toml"


def _run_gitleaks(source: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "gitleaks", "detect",
            "--no-git",
            "--source", str(source),
            "--config", str(GITLEAKS_CONFIG),
            "--report-format", "json",
            "--report-path", str(source / "_report.json"),
        ],
        capture_output=True, text=True,
    )


def test_i00085_mypy_cache_does_not_trigger_false_positives(tmp_path):
    """Synthetic .mypy_cache/ payload mirroring the CR-00053 finding
    (`threading.local` matches the iw-internal-fqdn rule) must NOT be
    flagged. FAILS pre-fix, PASSES post-fix.
    """
    cache = tmp_path / ".mypy_cache" / "3.12"
    cache.mkdir(parents=True)
    # Same string CR-00053's S16 flagged on .mypy_cache/3.12/threading.data.json
    (cache / "threading.data.json").write_text('{"fullname": "threading.local"}')

    result = _run_gitleaks(tmp_path)

    assert result.returncode == 0, (
        f"gitleaks must allowlist .mypy_cache/; "
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def test_i00085_real_secret_still_detected(tmp_path):
    """Control test: the allowlist additions must NOT mask real secrets.
    Place an AWS-shaped key (distinct from the AKIAIOSFODNN7EXAMPLE
    pattern that is allowlisted in .gitleaks.toml regexes) at a
    non-allowlisted path; gitleaks must detect it. Passes pre- and
    post-fix — guards against over-broad allowlist edits.
    """
    target = tmp_path / "leak_target"
    target.mkdir()
    # AWS access key shape (AKIA + 16 alphanumerics) that does NOT match the
    # documented-example regex AKIAIOSFODNN7EXAMPLE; suffix chosen to avoid the
    # gitleaks docs-example allowlist entirely.
    (target / "config.py").write_text('AWS_ACCESS_KEY = "AKIA1234567890ABCDEF"\n')

    result = _run_gitleaks(tmp_path)

    assert result.returncode != 0, (
        "gitleaks must flag AKIA1234567890ABCDEF at leak_target/config.py"
    )
    assert "AKIA1234567890ABCDEF" in result.stdout or "leaks found" in result.stdout
```

Notes on the design:

- `tmp_path` is the gitleaks `--source` root, so the project's path
  allowlists like `(?:^|/)tests/fixtures/` match `<tmp>/tests/fixtures/`
  inside the sandbox — keep the synthetic file paths outside any of
  those prefixes (`.mypy_cache/` pre-fix is NOT allowlisted; pick a
  fresh top-level directory like `leak_target/` for the control test).
- No `make type-check` invocation, no `make security-secrets`, no
  mutation of the worktree's `.mypy_cache/`. Safe under `pytest -n auto`.
- The tests still need the `gitleaks` binary on PATH (`make security-secrets`
  has the same dependency). If not installed, the tests should be
  `pytest.skip(...)`-ed with a clear message rather than fail.

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

### AC3: Real secret detection still works (control test)

```
Given an AWS-shaped key string AKIA1234567890ABCDEF (NOT the AKIAIOSFODNN7EXAMPLE
  docs pattern allowlisted in regexes) is planted in a sandbox at a
  non-allowlisted path (leak_target/config.py inside tmp_path)
When gitleaks is invoked against the sandbox with the project's .gitleaks.toml
Then gitleaks exits non-zero and reports the key
  (i.e., the new cache-directory allowlist entries do NOT mask real secrets)
```

## Regression Prevention

- The reproduction test exercises the exact failure mode from CR-00053's
  S16 manual run (a `.mypy_cache/3.12/...data.json` file containing a
  `*.local` string) — using an isolated sandbox so the test is fast and
  deterministic.
- AC3's control test (real-secret-shaped string at a non-allowlisted
  sandbox path) prevents over-broad allowlist edits — it passes pre- and
  post-fix and would fail if someone replaced the three specific cache
  globs with a catch-all like `\.cache/` or `cache/`.
- Inline comment in `.gitleaks.toml` cites I-00085 so future contributors
  understand why the cache directories are listed.

## Dependencies

- **Depends on**: None.
- **Blocks**: None (purely diagnostic-noise reduction).

## Impacted Paths

- `.gitleaks.toml`
- `tests/integration/test_security_secrets_cache_independence.py`

## TDD Approach

- Reproducing test (FAILS pre-fix, PASSES post-fix): the synthetic
  `.mypy_cache/3.12/threading.data.json` sandbox above.
- Unit tests: not applicable (config-only change).
- Integration tests: the reproduction test + AC3's control test. Both
  invoke the `gitleaks` binary against a tmp_path sandbox using the
  project's `.gitleaks.toml`; neither runs `make type-check` or
  `make security-secrets` and neither touches the worktree's
  `.mypy_cache/`. Both must be marked to skip cleanly when `gitleaks`
  is not installed.

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
