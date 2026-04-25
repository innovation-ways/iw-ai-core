# F-00062_S08_CodeReview_report

**Reviewer**: code-review-impl
**Step Reviewed**: S07 (backend-impl)
**Work Item**: F-00062 — Per-worktree container isolation
**Verdict**: PASS

---

## Summary

Reviewed the iw-ai-core reference implementation: `ai-dev/iw-config/` (compose template, env.toml, seed.sh) and the placeholder substitution in `orch/daemon/batch_manager.py`.

---

## Files Reviewed

| File | Status |
|------|--------|
| `ai-dev/iw-config/worktree-compose.template.yml` | ✅ Correct |
| `ai-dev/iw-config/worktree-env.toml` | ✅ Correct |
| `ai-dev/iw-config/worktree-seed.sh` | ✅ Correct |
| `orch/daemon/batch_manager.py` (placeholder substitution + env flag) | ✅ Correct |
| `tests/unit/daemon/test_prompt_substitution.py` | ✅ Correct |
| `.gitignore` | ✅ Correct |

---

## Checklist Results

### 1. Compose template
- ✅ Renders cleanly with test vars (`batch_item_id="TEST-001"`, `worktree_path="/tmp/wt"`, `project_name="iw-ai-core"`) — validated with Jinja2 render + YAML parse
- ✅ Both services have `iwcore.role` and `iwcore.batch_item` labels (Invariant #5)
- ✅ Uses `tmpfs` for db data dir (`tmpfs: - /var/lib/postgresql/data` — "no data left after destroyed")
- ✅ App service has `extra_hosts: ["host.docker.internal:host-gateway"]` (Linux host-gateway requirement)
- ✅ Both services declare `ports: ["..."]` with NO host port (dynamic allocation per design)
- ✅ Healthcheck on db; app `depends_on: db: condition: service_healthy`
- ✅ App command uses `dashboard.app:create_app --factory` (verified `dashboard/app.py:80` has `def create_app() -> FastAPI`)
- ✅ Bind-mount `{{ worktree_path }}:/workspace` with `working_dir: /workspace`

### 2. `worktree-env.toml`
- ✅ `[port_to_env]` uses `<service>:<container_port>` format (`db:5432`, `app:9900`)
- ✅ All exposed services have corresponding port_to_env entries
- ✅ `[env_overrides]` covers per-worktree-specific values (host, db name, credentials)
- ✅ `[env_passthrough].keep` includes `IW_CORE_ORCH_DB_*` glob (CRITICAL — allows iw CLI from worktree to reach 5433)

### 3. `worktree-seed.sh`
- ✅ `set -euo pipefail` at top
- ✅ `pg_dump` uses `--no-owner --no-acl` (avoids role-mismatch errors)
- ✅ Uses `--clean --if-exists` (idempotent/re-runnable)
- ✅ Connection strings properly quoted; no `eval`, no string-interpolation into SQL
- ✅ Echoes go to stderr (`>&2`) — follows project bash conventions
- ✅ Executable bit set (`test -x` passes)
- ✅ `bash -n` syntax check passes (zero output)
- ✅ Does NOT echo or leak `${IW_CORE_*_PASSWORD}` values

### 4. Placeholder substitution
- ✅ All five placeholders handled: `${WORKTREE_APP_PORT}`, `${WORKTREE_DB_PORT}`, `${WORKTREE_PATH}`, `${BATCH_ITEM_ID}`, `${PROJECT_NAME}`
- ✅ Legacy-mode items (NULL compose path) raise `UnresolvedWorktreePlaceholderError` with clear message (not silent "None")
- ✅ Unknown placeholders preserved verbatim
- ✅ Insertion point verified: `batch_manager.py:738` (prompt is built, then browser env substitutions applied, then `substitute_worktree_placeholders` called, then written to prompt file)

### 5. `IW_CORE_PER_WORKTREE_DB` flag
- ✅ Set to `"true"` at `batch_manager.py:777-778` when `worktree_info.get("worktree_compose_path") is not None`
- ✅ NOT set in legacy mode (safe_migrate continues to forbid alembic operations from agents)
- ✅ Insertion point verified: agent subprocess spawn at `batch_manager.py:783-791`

### 6. `.gitignore`
- ✅ `.env` listed (line 2)
- ✅ `.iw/` listed (line 66)

---

## Test Verification

| Test | Result |
|------|--------|
| `make test-unit` | 1527 passed, 0 failed |
| `bash -n ai-dev/iw-config/worktree-seed.sh` | Zero output (pass) |
| Jinja2 render + YAML parse | Valid YAML |
| `test -x ai-dev/iw-config/worktree-seed.sh` | Executable |
| `uv run pytest tests/unit/daemon/test_prompt_substitution.py -v` | 8 passed |

**Note**: `make lint` shows 11 pre-existing errors in unrelated files (`orch/rag/doc_job.py`, `tests/integration/test_doc_index_job_runner.py`, `tests/unit/test_qa_engine_classifier.py`). None are in the files under review.

---

## Findings

No CRITICAL or HIGH issues found.

**MEDIUM_SUGGESTION** (non-blocking): The `worktree-env.toml` `IW_CORE_DB_HOST = "localhost"` in `[env_overrides]` assumes the app container can reach the db via `localhost` from its own container network. Since both services are on the same compose network and the db is named `db`, this is correct. No change needed.

---

## Verdict

```
pass
```

**Mandatory fix count**: 0
**Tests passed**: true
**Test summary**: 1527 passed, 0 failed