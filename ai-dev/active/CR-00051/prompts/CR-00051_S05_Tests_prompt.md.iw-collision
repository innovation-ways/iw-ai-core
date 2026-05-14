# CR-00051_S05_Tests_prompt

**Work Item**: CR-00051 — Semgrep baseline cleanup
**Step**: S05
**Agent**: Tests (`tests-impl`)

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures are exempt.

## ⛔ Migrations: agents generate, daemon applies

This CR leaves migrations unchanged.

## Input Files

- **Runtime step state** (authoritative): `uv run iw item-status CR-00051 --json`.
- `ai-dev/active/CR-00051/CR-00051_CR_Design.md` — design doc (read "TDD Approach" and AC4 / AC7).
- `ai-dev/active/CR-00051/reports/CR-00051_S01_Backend_report.md`
- `ai-dev/active/CR-00051/reports/CR-00051_S03_Frontend_report.md`
- `tests/CLAUDE.md` and `tests/conftest.py` — required reading; particularly the rules around testcontainers, no-live-DB, and Jinja2 render helpers.
- `dashboard/templates/macros/db_guard.html` — the macro under test (NOT modified by this CR; the test is a forward-looking regression guard).
- `Makefile` line 226–236 — the `security-sast` target with its four `--exclude-rule` flags (your integration test mirrors this exact flag set).

## Output Files

- `ai-dev/active/CR-00051/reports/CR-00051_S05_Tests_report.md`
- `tests/unit/test_db_guard_macro.py` — new
- `tests/integration/test_security_sast_baseline.py` — new

## Context

You are writing **two** tests:

1. A **unit test** that renders the `write_button_attrs` macro and asserts its output is exactly a captured constant for both `is_db_stale=True` / `=False`. The macro is **not** modified by CR-00051 — the test is a forward-looking regression guard. The Class C Makefile `--exclude-rule` is justified only as long as the macro emits a constant attribute string with no user input; if a future edit introduces user-input interpolation in the macro, this test fails and forces a review of the exclude flag. (AC4 / AC5.)

2. An **integration test** that invokes Semgrep as a subprocess (the same three rule packs + four `--exclude-rule` flags the Makefile uses) and asserts zero blocking findings (AC7). The test must skip cleanly when Semgrep is not installed locally — CI installs it; local dev machines may not.

Read `tests/CLAUDE.md` before writing either test. Pay particular attention to:
- The live-DB write guard (irrelevant here — no DB touch).
- Cross-project isolation (irrelevant — no DB).
- Assertion strength (`assert ==`-style, not `assert truthy`).

## Requirements

### 1. `tests/unit/test_db_guard_macro.py`

Use Jinja's standalone `Environment` plus `FileSystemLoader` pointed at `dashboard/templates/`. Render the macro twice with a controllable `is_db_stale` flag.

The `is_db_stale` helper is registered as a Jinja global in `dashboard/app.py` (or a sibling jinja-setup module — confirm by reading `dashboard/app.py`). For the test, register it on a standalone `Environment` as a callable that returns a controllable boolean — do NOT spin up FastAPI just for this.

Skeleton:

```python
"""Regression guard for dashboard/templates/macros/db_guard.html.

The `write_button_attrs` macro emits a constant pre-quoted HTML attribute string
when `is_db_stale(request)` is True, and an empty string when False. This test
locks both outputs.

This invariant is what justifies CR-00051's project-wide Makefile `--exclude-rule`
for `generic.html-templates.security.unquoted-attribute-var.unquoted-attribute-var`:
the rule fires at every macro callsite, but is a false positive because the macro
output is a constant string. If a future edit changes the macro to interpolate
user input, this test fails and forces the team to revisit the exclude flag.
"""

from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = REPO_ROOT / "dashboard" / "templates"

EXPECTED_STALE = (
    'disabled aria-disabled="true" '
    "title=\"Orch DB schema mismatch — run 'make db-migrate' to fix.\""
)
EXPECTED_FRESH = ""


@pytest.fixture
def jinja_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=True,
    )
    return env


def _render(env: Environment, stale: bool) -> str:
    env.globals["is_db_stale"] = lambda _request: stale
    tmpl_source = (
        "{% from 'macros/db_guard.html' import write_button_attrs %}"
        "{{ write_button_attrs(request) }}"
    )
    tmpl = env.from_string(tmpl_source)
    return tmpl.render(request=object()).strip()


def test_write_button_attrs_when_db_is_fresh(jinja_env: Environment) -> None:
    rendered = _render(jinja_env, stale=False)
    assert rendered == EXPECTED_FRESH, (
        f"Expected empty output when DB is fresh, got: {rendered!r}"
    )


def test_write_button_attrs_when_db_is_stale(jinja_env: Environment) -> None:
    rendered = _render(jinja_env, stale=True)
    assert rendered == EXPECTED_STALE, (
        f"Expected pre-quoted attributes when DB is stale, got: {rendered!r}"
    )


def test_write_button_attrs_output_is_well_formed_html_attrs(
    jinja_env: Environment,
) -> None:
    """Sanity: every attribute value, if any, is wrapped in matched double-quotes.

    The exact constant has two quoted values: aria-disabled="true" and title="...".
    """
    rendered = _render(jinja_env, stale=True)
    open_count = rendered.count('="')
    assert open_count == 2, (
        f"Expected 2 quoted attributes, found {open_count} in: {rendered!r}"
    )
```

Refinements you should make:
- If `is_db_stale` is registered via FastAPI request state rather than as a Jinja global, adjust the patching strategy (see `dashboard/app.py` for the registration site). The test must still avoid spinning up the FastAPI app.
- **Capture-then-assert the constant first.** Before committing the test, render the macro once against the current (unmodified) source tree, capture the exact string output for `stale=True`, and pin it as `EXPECTED_STALE`. The constant in the skeleton above is a best guess; the actual rendering may differ in quote style or em-dash treatment. The test must lock the **actual** current output, not the skeleton's guess.

### 2. `tests/integration/test_security_sast_baseline.py`

Invoke Semgrep the same way the Makefile does — including all four `--exclude-rule` flags — and parse its JSON output. Skip cleanly when Semgrep is not installed.

The list of excluded rules is the canonical Class C/F/G/H set; keep it in a tuple at the top of the file so code review (S06, future CR reviewers) can verify it matches the Makefile by inspection (Invariant I4).

Skeleton:

```python
"""Baseline test: `make security-sast` reports zero blocking findings.

Locks in CR-00051's deliverable: the Semgrep baseline is clean. If a future
change introduces a new finding, this test fails loudly in CI.

The `--exclude-rule` set MUST match the Makefile's `security-sast` target. If you
edit one, edit the other — Invariant I4.

Skipped when `semgrep` is not on PATH (local dev convenience — CI installs
semgrep as a dev dependency via `uv sync --dev`).
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

SEMGREP_CONFIGS = ("p/python", "p/owasp-top-ten", "p/security-audit")
SEMGREP_TARGETS = ("orch", "dashboard", "executor")

# Keep this tuple in sync with the four --exclude-rule flags in the Makefile's
# `security-sast` target. Invariant I4 of CR-00051.
SEMGREP_EXCLUDE_RULES = (
    "generic.html-templates.security.unquoted-attribute-var.unquoted-attribute-var",
    "generic.html-templates.security.var-in-href.var-in-href",
    "generic.html-templates.security.var-in-script-tag.var-in-script-tag",
    "html.security.plaintext-http-link.plaintext-http-link",
)


@pytest.mark.skipif(
    shutil.which("semgrep") is None,
    reason="semgrep not installed (install with `uv sync --dev`)",
)
def test_semgrep_baseline_is_zero_blocking_findings() -> None:
    cmd: list[str] = ["uv", "run", "semgrep"]
    for cfg in SEMGREP_CONFIGS:
        cmd.extend(["--config", cfg])
    for rule in SEMGREP_EXCLUDE_RULES:
        cmd.extend(["--exclude-rule", rule])
    cmd.extend(SEMGREP_TARGETS)
    cmd.extend(["--error", "--json"])

    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )

    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError:
        pytest.fail(
            f"Could not parse semgrep JSON output. exit={result.returncode}\n"
            f"stdout (first 500 chars): {result.stdout[:500]!r}\n"
            f"stderr (first 500 chars): {result.stderr[:500]!r}"
        )

    findings = report.get("results", [])
    if findings:
        summary_lines = [f"Expected 0 blocking semgrep findings, got {len(findings)}:"]
        for f in findings[:20]:
            summary_lines.append(
                f"  {f.get('path')}:{f.get('start', {}).get('line')} "
                f"{f.get('check_id')}"
            )
        if len(findings) > 20:
            summary_lines.append(f"  ... ({len(findings) - 20} more)")
        pytest.fail("\n".join(summary_lines))

    assert result.returncode == 0, (
        f"semgrep exited {result.returncode} despite zero results. "
        f"stderr (first 500 chars): {result.stderr[:500]!r}"
    )
```

Refinements:
- The test runs `semgrep` directly (not through `make`) so the path it logs is portable.
- Timeout is 300s — Semgrep on this codebase takes ~13s; 300s gives plenty of headroom.
- The skip uses `shutil.which("semgrep")` rather than wrapping the `uv run semgrep --version` call so a misconfigured `uv` environment fails the test rather than silently skipping.
- The integration suite already uses `tests/integration/` — confirm with `tests/CLAUDE.md` that no special fixture is needed (this test does not touch the DB).

### 3. RED evidence

Per CR-00023, capture RED evidence for the new unit test. The canonical RED option for these regression tests is:

- **Capture the test's RED state at write time, against a deliberately-wrong `EXPECTED_STALE` constant.** Run the test with a placeholder constant (e.g., `EXPECTED_STALE = "WRONG"`); confirm it fails with an `AssertionError` showing the diff between expected and actual. Capture the actual rendered output from that failure message and use it as the locked-in constant. Then re-run the test and confirm GREEN.

  Record the captured failure snippet in your report's `tdd_red_evidence` field.

- **Do NOT** revert any file in the worktree, run `git checkout` on previously-committed source, or use `git stash` to manufacture a RED state. The pre-fix RED is captured by the wrong-constant technique above — no source revert is needed.

For the integration test, the natural RED would be "run it against a pre-CR `main` and watch it fail with 94 findings." That's not practical inside the worktree (the suppressions are already applied by S01 and S03). Document this as: `tdd_red_evidence: "integration test RED state is implicit — pre-CR main would fail with 94 findings. Captured RED for the unit test serves as the CR's overall RED-first anchor."`

### 4. Don't run the full suite

Per CR-00023 / I-00073:

```bash
uv run pytest tests/unit/test_db_guard_macro.py -v
uv run pytest tests/integration/test_security_sast_baseline.py -v
```

Do NOT run `make test-unit` or `make test-integration` here. Those are S12/S14 QV gates and will catch any regressions there.

## Project Conventions

`tests/CLAUDE.md` — read it. Key rules that apply here:
- Use real Jinja2 rendering (no mocking the env). ✅ Done in the skeleton.
- No live-DB writes. ✅ Neither test touches the DB.
- Skip with a clear reason when an external tool is missing. ✅ `shutil.which("semgrep")`.

## TDD Requirement

Capture RED evidence for the macro unit test using the wrong-constant technique (see §3). Document it in your report.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

1. `make format` — must pass.
2. `make typecheck` — both test files must be type-clean.
3. `make lint` — must pass.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "Tests",
  "work_item": "CR-00051",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_db_guard_macro.py",
    "tests/integration/test_security_sast_baseline.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "test_db_guard_macro.py: 3 passed; test_security_sast_baseline.py: 1 passed (or skipped with reason)",
  "tdd_red_evidence": "tests/unit/test_db_guard_macro.py::test_write_button_attrs_when_db_is_stale — AssertionError captured against deliberately-wrong EXPECTED_STALE; captured failure snippet in report body",
  "blockers": [],
  "notes": "If semgrep is not installed in the worktree, the integration test will skip — confirm it would pass when semgrep is present by manually running `make security-sast` and observing exit 0."
}
```
