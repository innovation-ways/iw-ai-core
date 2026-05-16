# CR-00054_S06_CodeReview_prompt

**Work Item**: CR-00054 -- Add OpenCode stub to worktree E2E stack
**Step Being Reviewed**: S01–S05
**Review Step**: S06

---

## ⛔ Docker is off-limits

Standard policy. Read-only introspection allowed.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This CR adds NO migrations.

## Input Files

- `uv run iw item-status CR-00054 --json` — current step list and statuses
- `ai-dev/active/CR-00054/CR-00054_CR_Design.md` — design contract
- `ai-dev/active/CR-00054/reports/CR-00054_S01_Pipeline_report.md`
- `ai-dev/active/CR-00054/reports/CR-00054_S02_Pipeline_report.md`
- `ai-dev/active/CR-00054/reports/CR-00054_S03_Pipeline_report.md`
- `ai-dev/active/CR-00054/reports/CR-00054_S04_Tests_report.md`
- `ai-dev/active/CR-00054/reports/CR-00054_S05_Template_report.md`
- All files listed in each implementation step's `files_changed`

## Output Files

- `ai-dev/active/CR-00054/reports/CR-00054_S06_CodeReview_report.md`

## Context

You are doing a **per-agent code review** of S01–S05 of CR-00054. The CR adds a Python stub server, a Dockerfile shim, compose-file wiring, an integration test suite, and a docs update — all behind a strict scope.allowed_paths list.

## Required severities

### CRITICAL (blocks merge)

1. **Scope creep**: any modified file outside `scope.allowed_paths` (the five entries in `workflow-manifest.json`'s `scope.allowed_paths`). Even one byte changed in `orch/chat/**`, `dashboard/routers/chat.py`, `dashboard/templates/chat_assistant/**`, `dashboard/static/chat_assistant/**` is CRITICAL — F-00083 owns those.
2. **Non-loopback binding**: the stub's HTTP server MUST bind only to `127.0.0.1`. Any code that resolves `--hostname 0.0.0.0` (or any non-loopback default) is CRITICAL.
3. **Auth bypass**: any protected endpoint that returns a non-401 response when the `Authorization` header is missing or wrong. The unauthenticated `/global/health` exception is the only allowed bypass.
4. **Secret leakage**: `OPENCODE_SERVER_PASSWORD` appearing in any `logger.info/warning/error/debug` call, in `print()`, in `subprocess` stdout/stderr without redaction, or in a test assertion message. Grep `scripts/e2e_opencode_stub.py` and `tests/integration/test_e2e_opencode_stub.py` for the substring.
5. **New dependencies**: any new entry in `pyproject.toml` or `uv.lock` not already present. The stub must use only existing deps (`fastapi`, `uvicorn`, `httpx`, `httpx-sse`).
6. **Modifications to F-00083 territory**: `orch/chat/**`, `dashboard/routers/chat.py`, `dashboard/templates/chat_assistant/**`, `dashboard/static/chat_assistant/**`. None.
7. **Database mock or live-DB connection in tests**: per `tests/CLAUDE.md`, tests must not connect to port 5433. The stub tests should not touch any DB at all.
8. **Image-build network-fetch in offline conditions**: `Dockerfile.e2e` must not introduce a new `curl | sh` or `pip install` step that requires internet at build time (the existing `RUN apt-get install` is already there).

### HIGH (blocks merge unless explicitly waived)

1. **Missing ring-buffer for `/event` replay** or ring buffer size diverges from `deque(maxlen=256)`.
2. **HTTP shape divergence**: any endpoint returns a payload shape that `OpencodeClient` would `raise_for_status` or `RuntimeError` on. Cross-check against `orch/chat/opencode_client.py`.
3. **Healthcheck regression**: `docker-compose.e2e.yml`'s new healthcheck for `e2e-dashboard` must keep the original `/health` probe AND add the `/api/chat/config` probe — both required for healthy. If only one is checked, that's HIGH.
4. **Image size grew >50 MB** as a result of S02's changes. Estimate via `docker images <image>:before` vs `docker images <image>:after`. If S02 didn't rebuild (skipped per docker-off-limits), the inspection of Dockerfile changes alone is sufficient — flag any new RUN that fetches large binaries.
5. **Assertion weakness in tests**: vacuous `assert x` or `assert resp.status_code` (without comparison). Per `tests/CLAUDE.md` + `iw-ai-core-testing` skill.
6. **Missing `Last-Event-ID` semantics**: the stub MUST return only events with id > Last-Event-ID after reconnect. If it replays the whole buffer regardless, that's HIGH.
7. **Permission flow correctness**: deny must terminate; allow must continue. If the stub's behaviour is ambiguous or test coverage is missing, that's HIGH.

### MEDIUM (note, do not block)

1. Stub log level too noisy (DEBUG by default; should be INFO).
2. Comment-block density too low to maintain when v1.16 ships.
3. Tests reuse the session-scoped subprocess across tests that should be isolated.

## Review Output

Write `ai-dev/active/CR-00054/reports/CR-00054_S06_CodeReview_report.md` with the standard findings table:

```
| ID | Severity | File:Line | Issue | Fix |
|----|----------|-----------|-------|-----|
| F1 | CRITICAL | scripts/e2e_opencode_stub.py:42 | Stub binds 0.0.0.0 by default | Default hostname to 127.0.0.1 |
| ... | ... | ... | ... | ... |
```

## Result Contract

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "CR-00054",
  "completion_status": "complete",
  "findings": [
    {"id": "F1", "severity": "CRITICAL|HIGH|MEDIUM|LOW", "file": "...", "line": 0, "issue": "...", "fix": "..."}
  ],
  "blockers": [],
  "notes": ""
}
```
