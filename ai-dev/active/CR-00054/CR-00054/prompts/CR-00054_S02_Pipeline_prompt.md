# CR-00054_S02_Pipeline_prompt

**Work Item**: CR-00054 -- Add OpenCode stub to worktree E2E stack
**Step**: S02
**Agent**: pipeline-impl

---

## ⛔ Docker is off-limits

Same policy as S01. You may EDIT `Dockerfile.e2e` (a declarative file) but you MUST NOT run `docker build`, `docker compose build/up/down`, or any container-state-changing command. The daemon's worktree-compose launch path will rebuild the image when the next browser_verification step needs it.

Allowed exception: you MAY inspect the existing image's contents via `docker run --rm <image> ...` if you need to confirm a path inside the image — but prefer reading the Dockerfile lines directly.

## ⛔ Migrations: agents generate, daemon applies

This step does NOT touch migrations.

## Input Files

- `Dockerfile.e2e` — to be modified
- `scripts/e2e_opencode_stub.py` — created in S01; S02 must reference its path
- `.opencode/config.json` (project root) — must end up in the image (already covered by existing `COPY . .`; verify, do not duplicate)
- `ai-dev/active/CR-00054/CR-00054_CR_Design.md` — design contract
- `ai-dev/active/CR-00054/reports/CR-00054_S01_Pipeline_report.md` — S01 report

## Output Files

- `Dockerfile.e2e` — modified
- `ai-dev/active/CR-00054/reports/CR-00054_S02_Pipeline_report.md` — step report

## Context

You are implementing **S02** — adding a `/usr/local/bin/opencode` shim inside `Dockerfile.e2e` so `OpencodeRuntime` can locate "the binary" when it spawns `opencode serve --hostname ... --port ...`.

## Requirements

### 1. The shim script

Add a layer that writes `/usr/local/bin/opencode` containing:

```sh
#!/bin/sh
exec uv run python /app/scripts/e2e_opencode_stub.py "$@"
```

Make it world-executable (`chmod 755`).

**Placement**: insert the layer **before** `USER app` so the write to `/usr/local/bin/` succeeds (only root can write there). The current `Dockerfile.e2e` flow is:

```
RUN apt-get install ... && uv installer    ← root, line ~17
RUN groupadd / useradd / chown            ← root, line ~38
USER app                                  ← drops to non-root
COPY pyproject.toml uv.lock ./            ← chown=app:app
RUN uv sync --frozen --no-dev --no-install-project
COPY --chown=app:app . .                  ← brings in scripts/e2e_opencode_stub.py
RUN uv sync --frozen --no-dev             ← finalises the venv
RUN git init ...
```

Put the shim-creation `RUN` immediately after the `apt-get` block (still under root, before `USER app`). The shim references `/app/scripts/...` which is COPYed later — the shim is just a text file at this point, so the deferred reference is fine.

### 2. Preserve .opencode/config.json

Verify the existing `COPY --chown=app:app . .` line picks up the project-root `.opencode/config.json` file (R-00074 §5 permission block). Add a comment above the COPY line that documents this dependency so future cleanup of `.dockerignore` doesn't accidentally exclude it. If `.dockerignore` already excludes `.opencode/`, add a `!` un-ignore line for `.opencode/config.json`. Do NOT modify `.dockerignore` otherwise.

### 3. Comment block

Add a comment block above the new shim layer:

```dockerfile
# ----------------------------------------------------------------------
# OpenCode stub shim (CR-00054)
#
# The production daemon runs against the real `opencode` binary on the
# host's PATH. The per-worktree e2e stack does NOT install the real
# binary because it would balloon the image with ~100 MB plus an
# LLM-provider config that the stack does not own. Instead we install
# a shim at /usr/local/bin/opencode that execs a Python stub
# (scripts/e2e_opencode_stub.py) implementing opencode v1.15.0's
# HTTP+SSE wire protocol.
#
# When v1.15.0's protocol bumps, update both:
#   - scripts/e2e_opencode_stub.py (event shapes / endpoint payloads)
#   - this Dockerfile (shim path / wrapper invocation, if changed)
# ----------------------------------------------------------------------
```

### 4. Build-time validation

**Placement is load-bearing.** The shim execs `uv run python /app/scripts/e2e_opencode_stub.py`, so the source tree AND the project venv (`uv sync`) must already exist before the shim can run end-to-end. That means the validation `RUN` must be placed **after** the second `RUN uv sync --frozen --no-dev` line in `Dockerfile.e2e` (the one that comes after `COPY --chown=app:app . .`). Do NOT place it next to the shim-creation layer — the script will not be in the image yet and `uv run` will fail (silently masked by `|| true`, defeating the check).

Add this line immediately after the second `uv sync`:

```dockerfile
# Build-time sanity: shim resolves, script imports cleanly.
# (We rely on a tiny --selftest entrypoint in scripts/e2e_opencode_stub.py
# that imports the FastAPI app and exits 0 without binding a port. If S01
# did not add --selftest, fall back to `--help` and drop the `|| true` only
# once that succeeds end-to-end locally.)
RUN /usr/local/bin/opencode --selftest
```

If S01's stub does **not** implement `--selftest`, request its addition in your step report (block S02 on it — do NOT push the validation down to `|| true`). The point of this RUN is to catch shim typos and broken Python imports at build time, not to pretend-pass.

### 5. No other changes

The Dockerfile may NOT install the real `opencode` binary, change Python versions, or add new system packages. Keep the new RUN layer minimal so build time stays under ~3 minutes.

## Project Conventions

Read `CLAUDE.md`. Dockerfile.e2e specifics:
- Non-root `app` user, `WORKDIR /app`, `HOME=/app`.
- Existing `RUN apt-get install …` layer covers the base system packages.
- `COPY` layers must use `--chown=app:app` after the initial setup.

## TDD Requirement

This is a Dockerfile change with no Python logic to TDD. Use `tdd_red_evidence: "n/a — Dockerfile config, no production logic"`.

## Pre-flight Quality Gates

- `make format`: not applicable to Dockerfile (record as `n/a`).
- `make typecheck`: not applicable (record as `n/a`).
- `make lint`: not applicable (Dockerfile is not in the ruff scope; record as `n/a`).

Instead, manually verify your Dockerfile change is syntactically valid by running:
```bash
docker build --target base -f Dockerfile.e2e --check . 2>&1 | head -20
```
Read-only `--check` flag is BuildKit's linter — it does NOT produce an image and does NOT consult or invalidate any cache, so the `--no-cache` flag is intentionally omitted (it would be a no-op here). If `--check` is not available in the installed Docker / Buildx version, skip this check and note it in the report.

## Test Verification

There are no Python tests for a Dockerfile-only change. Record `tests_passed: true` with `test_summary: "n/a — Dockerfile change, validated by image build"`.

S04's integration tests assert the stub script's behaviour, not the Dockerfile.

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "pipeline-impl",
  "work_item": "CR-00054",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["Dockerfile.e2e"],
  "preflight": {
    "format": "n/a",
    "typecheck": "n/a",
    "lint": "n/a"
  },
  "tests_passed": true,
  "test_summary": "n/a — Dockerfile change",
  "tdd_red_evidence": "n/a — Dockerfile config, no production logic",
  "blockers": [],
  "notes": "Dockerfile syntax validated via `docker build --check` (or noted as skipped)."
}
```
