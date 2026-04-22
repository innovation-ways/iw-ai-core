# {TYPE}{NNN}_S{NN}_QualityValidation_prompt

**Work Item**: {ID} -- {Title}
**QV Step**: S{NN}

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/work/{ID}/{ID}_{Type}_Design.md` -- Design document
- Workflow manifest or project Makefile -- for gate commands
- `CLAUDE.md` -- for project-specific test and quality commands

## Output Files

- `ai-dev/work/{ID}/reports/{ID}_S{NN}_QualityValidation_report.md` -- QV report

## Context

You are running the **Quality Validation** gate for **{Work Item Title}**. This is a pass/fail checkpoint: every gate must pass before the work item can be merged.

Read `CLAUDE.md` and the project Makefile to determine the exact commands for each gate.

## Quality Gates

Run each gate in order. Record the exact command, result, and any error output.

### Gate 1: Lint

- **Command**: {lint command from Makefile or CLAUDE.md, e.g., `make lint` or `uv run ruff check .`}
- **Result**: PASS | FAIL
- **Error output** (if FAIL): {paste relevant error lines}

### Gate 2: Format Check

- **Command**: {format command, e.g., `make format-check` or `uv run ruff format --check .`}
- **Result**: PASS | FAIL
- **Error output** (if FAIL): {paste relevant error lines}

### Gate 3: Type Check

- **Command**: {typecheck command, e.g., `make typecheck` or `uv run mypy .`}
- **Result**: PASS | FAIL
- **Error output** (if FAIL): {paste relevant error lines}

### Gate 4: Unit Tests

- **Command**: {unit test command, e.g., `make test-unit`}
- **Result**: PASS | FAIL
- **Error output** (if FAIL): {paste relevant error lines}
- **Summary**: {X passed, Y failed, Z skipped}

### Gate 5: Integration Tests

- **Command**: {integration test command, e.g., `make test-integration`}
- **Result**: PASS | FAIL
- **Error output** (if FAIL): {paste relevant error lines}
- **Summary**: {X passed, Y failed, Z skipped}

### Gate 6: Coverage (if configured)

- **Command**: {coverage command, e.g., `make coverage`}
- **Result**: PASS | FAIL | SKIP (if not configured)
- **Coverage**: {percentage}
- **Threshold**: {minimum required, if configured}

### Gate 7: Security Scan (if configured)

- **Command**: {security command, e.g., `make security` or `uv run bandit -r src/`}
- **Result**: PASS | FAIL | SKIP (if not configured)
- **Error output** (if FAIL): {paste relevant findings}

{Add or remove gates based on the project's workflow manifest or Makefile. The gates above are the standard set; some projects may have additional or fewer gates.}

## Summary Table

| Gate | Command | Result |
|------|---------|--------|
| Lint | `{command}` | PASS/FAIL |
| Format | `{command}` | PASS/FAIL |
| Type Check | `{command}` | PASS/FAIL |
| Unit Tests | `{command}` | PASS/FAIL |
| Integration Tests | `{command}` | PASS/FAIL |
| Coverage | `{command}` | PASS/FAIL/SKIP |
| Security | `{command}` | PASS/FAIL/SKIP |

## Browser Verification (if applicable)

{Include this section only if `browser_verification: true` is set in the workflow manifest.}

If browser verification is required:

1. Start the application server
2. Open the relevant pages/endpoints in a browser
3. Verify visual correctness and interactive behavior
4. Record screenshots or observations

| Page/Endpoint | Expected Behavior | Result |
|---------------|-------------------|--------|
| {URL or route} | {what should happen} | PASS/FAIL |

## QV Result Contract

```json
{
  "step": "S{NN}",
  "agent": "QualityValidation",
  "work_item": "{ID}",
  "overall_status": "pass|fail",
  "gates": {
    "lint": {"status": "pass|fail|skip", "command": "", "error_output": ""},
    "format": {"status": "pass|fail|skip", "command": "", "error_output": ""},
    "typecheck": {"status": "pass|fail|skip", "command": "", "error_output": ""},
    "unit_tests": {"status": "pass|fail|skip", "command": "", "summary": "", "error_output": ""},
    "integration_tests": {"status": "pass|fail|skip", "command": "", "summary": "", "error_output": ""},
    "coverage": {"status": "pass|fail|skip", "command": "", "percentage": null, "threshold": null},
    "security": {"status": "pass|fail|skip", "command": "", "error_output": ""}
  },
  "browser_verification": {
    "required": false,
    "results": []
  },
  "failing_gates": [],
  "notes": ""
}
```

- `overall_status`: `pass` only if ALL non-skipped gates pass. `fail` if any gate fails.
- `failing_gates`: List of gate names that failed. This drives the QV fix cycle.
- Gates marked `skip` do not affect `overall_status`.
