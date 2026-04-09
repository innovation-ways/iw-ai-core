# CR-00003 S05 — Quality Validation

## Input Files

- `dashboard/static/logo.png` — static asset to verify
- `dashboard/templates/base.html` — template change to confirm
- All Python source under `orch/` — for lint/typecheck gates

## Output Files

- `ai-dev/work/CR-00003/reports/S05_qv_results.md` — gate pass/fail results (created during execution)

## Context

You are running quality gates for CR-00003. Read `CLAUDE.md` for project conventions.

**Work item**: CR-00003  
**Step**: S05  
**Agent**: quality-validation-impl

## Gates to Run

Run each gate and record pass/fail. All gates must pass before signaling done.

### Gate 1: Ruff lint

```bash
uv run ruff check .
```

Expected: no errors (template change doesn't affect Python linting, but confirm clean)

### Gate 2: Ruff format check

```bash
uv run ruff format --check .
```

Expected: no formatting issues

### Gate 3: mypy type check

```bash
uv run mypy orch/
```

Expected: no type errors (no Python files changed)

### Gate 4: Unit tests

```bash
make test-unit
```

Expected: all pass

### Gate 5: Integration tests

```bash
make test-integration
```

Expected: all pass

### Gate 6: Static asset verification

```bash
ls -lh dashboard/static/logo.png
identify dashboard/static/logo.png
```

Expected: file exists, is a valid 56×56 TrueColorAlpha PNG

## Signal completion

If all gates pass:
```bash
iw step-done CR-00003 S05 --summary "All QV gates passed: lint clean, format clean, mypy clean, unit tests pass, integration tests pass, logo.png valid"
```

If any gate fails:
```bash
iw step-fail CR-00003 S05 --reason "Gate <N> failed: <error details>"
```
