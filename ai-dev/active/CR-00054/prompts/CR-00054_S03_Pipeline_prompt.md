# CR-00054_S03_Pipeline_prompt

**Work Item**: CR-00054 -- Add OpenCode stub to worktree E2E stack
**Step**: S03
**Agent**: pipeline-impl

---

## ⛔ Docker is off-limits

Same policy as S01/S02. You may EDIT `docker-compose.e2e.yml`. You MUST NOT run `docker compose up/down/restart/build`.

## ⛔ Migrations: agents generate, daemon applies

This step does NOT touch migrations.

## Input Files

- `docker-compose.e2e.yml` — to be modified
- `Dockerfile.e2e` — modified by S02 (read for context)
- `scripts/e2e_opencode_stub.py` — written by S01 (read for context)
- `dashboard/routers/chat.py` — for the `/api/chat/config` endpoint contract
- `orch/chat/opencode_runtime.py` — for the runtime's port + bin env var contract
- `ai-dev/active/CR-00054/CR-00054_CR_Design.md` — design contract

## Output Files

- `docker-compose.e2e.yml` — modified
- `ai-dev/active/CR-00054/reports/CR-00054_S03_Pipeline_report.md` — step report

## Context

You are implementing **S03** — wiring the new shim's path and port into `docker-compose.e2e.yml` so the dashboard service finds it at runtime, and extending the healthcheck so the container is `healthy` only when `/api/chat/config` returns 200.

## Requirements

### 1. New env vars on `e2e-dashboard`

Add to the existing `environment:` block on the `e2e-dashboard` service:

```yaml
      IW_CORE_OPENCODE_BIN: /usr/local/bin/opencode
      IW_CORE_OPENCODE_PORT: "4096"
```

Place them after `IW_E2E_OLLAMA_URL` to preserve grouping (worktree-stack-specific vars).

### 2. Healthcheck extension

The current healthcheck on `e2e-dashboard`:

```yaml
    healthcheck:
      test: ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:9900/health', timeout=2).read()\""]
      interval: 3s
      timeout: 5s
      retries: 40
```

Extend it so the container is `healthy` only when **both** `/health` AND `/api/chat/config` return 200. Replace with:

```yaml
    healthcheck:
      test:
        - "CMD-SHELL"
        - |
          python - <<'PY'
          import sys, urllib.request
          for path in ("/health", "/api/chat/config"):
              try:
                  resp = urllib.request.urlopen(f"http://localhost:9900{path}", timeout=2)
                  if resp.status != 200:
                      sys.exit(1)
              except Exception:
                  sys.exit(1)
          PY
      interval: 3s
      timeout: 5s
      retries: 60
```

(`retries: 60` instead of `40` — the OpencodeRuntime's startup health-poll adds up to 10 s; bumping the budget keeps the e2e-dashboard healthy-deadline well clear of the OpencodeRuntime's own retry window.)

### 3. Preserve other services

Do NOT modify `e2e-db`, `e2e-ollama`, or `e2e-daemon-stub`. Do NOT add new services.

### 4. No port exposure for OpenCode

The OpenCode stub binds to `127.0.0.1:4096` inside the container — never expose it to the host network. Do NOT add an `IW_CORE_OPENCODE_PORT` entry under the `ports:` section.

### 5. YAML lint

Verify the file still parses as valid YAML:

```bash
uv run python -c "import yaml; yaml.safe_load(open('docker-compose.e2e.yml'))"
```

If `pyyaml` is not available in the project venv, use `python -c "import json, subprocess; r = subprocess.run(['docker', 'compose', '-f', 'docker-compose.e2e.yml', 'config', '--quiet'], capture_output=True); print(r.returncode, r.stderr.decode())"` — `docker compose config --quiet` is read-only (just parses the file) so it's allowed under the docker-off-limits exemption.

## Project Conventions

Read `CLAUDE.md`. The compose file already documents its conventions in its top comment block (per-(project_id, item_id) port allocation, COMPOSE_PROJECT_NAME, etc.). Match that style.

## TDD Requirement

This is a config-only change with no Python logic. Use `tdd_red_evidence: "n/a — compose config, no production logic"`.

## Pre-flight Quality Gates

- `make format`: n/a (YAML).
- `make typecheck`: n/a.
- `make lint`: must still pass (the project's lint scope may include YAML; verify locally).

## Test Verification

`tests_passed: true` with `test_summary: "n/a — compose config, validated by YAML parse"`. S15 (test-integration) and S18 (qv-browser) will exercise the wiring end-to-end downstream.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "pipeline-impl",
  "work_item": "CR-00054",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["docker-compose.e2e.yml"],
  "preflight": {
    "format": "n/a",
    "typecheck": "n/a",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "n/a — compose config",
  "tdd_red_evidence": "n/a — compose config, no production logic",
  "blockers": [],
  "notes": ""
}
```
