# I00108_S01_Backend_prompt

**Work Item**: I-00108 -- `iw doc-update` new-doc without `--tier`/`--editorial-category` crashes with raw TypeError (exit 3) instead of clean usage error (exit 2)
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Allowed exceptions: testcontainer fixtures in pytest, read-only `docker ps`/`docker logs`/`docker inspect`, and `./ai-core.sh` / `make` targets.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT create, modify, or apply any alembic migration. **This work item adds no schema change.** If your fix appears to require one, STOP and raise a blocker — the scope is wrong.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00108 --json` for the current step list (workflow-manifest.json is a design-time snapshot).
- `ai-dev/active/I-00108/I-00108_Issue_Design.md` -- Design document (read first, especially §Root Cause Analysis and §Acceptance Criteria).
- `ai-dev/active/I-00108/I-00108_Functional.md` -- Human-facing summary.
- `orch/cli/doc_commands.py` -- The file you'll modify (the `doc_update` callback, ~lines 110-260).
- `orch/doc_service.py` -- Read-only reference: `DocService.get_doc`, `DocService.upsert_doc`, `DocService.create_doc` (the source of the missing-required-arg `TypeError`).
- `tests/integration/cli/test_doc_update_contract.py` -- Read-only: the strict `xfail` test `test_doc_update_new_doc_without_tier_is_clean_usage_error` is the contract you must satisfy. S03 (tests-impl) will remove the xfail marker; do not touch this file from S01.

## Output Files

- `ai-dev/active/I-00108/reports/I-00108_S01_Backend_report.md` -- Step report.

## Context

`iw doc-update` is an **upsert**: it accepts partial-update calls (where `--tier`/`--editorial-category` are legitimately optional, because they're only changing content of an existing doc) AND new-doc creates (where `DocService.create_doc()` *requires* them as keyword arguments). The current callback `try: ... except Exception: output_error(ctx, f"Database error: {exc}", 3)` swallows the `TypeError` raised by `create_doc()` and surfaces it as exit 3 "Database error", which is both the wrong code (usage errors are exit 2) and the wrong label.

The fix is a single runtime branch in the CLI callback: detect the new-doc-with-missing-required-args case **before** delegating to `upsert_doc`, and refuse it cleanly with exit 2.

Read the design doc's §Root Cause Analysis and §Acceptance Criteria fully before editing. The fix must preserve update semantics (the regression test in S03 pins that).

## Requirements

### 1. Add the pre-check in `orch/cli/doc_commands.py::doc_update`

In the `doc_update` callback, after `resolve_project(ctx)` and the project-existence check, but **before** the `svc.upsert_doc(...)` call:

1. Look up the existing doc once via `svc.get_doc(project_id, doc_id)`. (The callback already calls this for the `old_content_hash` computation — reuse the same call site rather than calling `get_doc` twice.)
2. If `existing is None` (new-doc create path) AND (`tier is None` OR `editorial_category is None`), refuse with `output_error(ctx, "<message>", 2)`.

**Message wording (use verbatim or very close)**: `Creating a new doc requires --tier and --editorial-category (no existing doc '<doc_id>' to update)`. The substring `"tier"` MUST appear in stderr — the contract test asserts `assert "tier" in (result.stderr or "").lower()`.

`output_error(ctx, msg, 2)` raises a `SystemExit(2)` (matches the existing `output_error(..., 1)` calls in this file) — `CliRunner` records `result.exit_code == 2`. Do NOT use `click.UsageError` or `sys.exit(2)` directly; the rest of `iw` uses `output_error` and so should this branch.

### 2. Preserve the update path

If `existing is not None` (the doc exists — update path), the new branch MUST NOT fire. `tier`/`editorial_category` stay optional on updates; an existing doc updated with only `--title`/`--content` continues to succeed with exit 0. The S03 regression test `test_doc_update_existing_doc_update_without_tier_succeeds` pins this.

### 3. Preserve all other behaviour

- The mutual-exclusivity check (`--content` + `--content-file` → exit 2) at the top of `doc_update` is untouched.
- The content size cap (10 MB → exit 2) is untouched.
- The project-not-found check (exit 1) is untouched.
- The broad `except Exception → exit 3 "Database error"` catch-all stays — it is the right behaviour for actual database errors (lost connection, FK violation, etc.), and the new pre-check fires before the `try` block can reach `create_doc`.
- The JSON output shape on success is unchanged.

### 4. Scope discipline

You may modify ONLY `orch/cli/doc_commands.py`. Do NOT edit `orch/doc_service.py` (the `create_doc` signature is intentional — required args for new docs are part of the data model). Do NOT add Click `required=True` on `--tier`/`--editorial-category` (that would break the update path). Do NOT touch any test file in this step; S03 owns the test changes.

### 5. Test verification (targeted only)

Run **only** the doc-update contract file from this step:

```bash
uv run pytest tests/integration/cli/test_doc_update_contract.py -v --no-cov
```

Expected post-fix:
- `test_doc_update_new_doc_without_tier_is_clean_usage_error` is currently `@pytest.mark.xfail(strict=True)`. After your fix it asserts exit 2 cleanly → pytest reports it as `XPASS(strict)` which **fails** the run, because `strict=True` treats unexpected passes as failures. **This is expected at this step** — S03 removes the xfail marker, after which the test goes GREEN. Record this in your report and the result contract's `notes` field. Do NOT remove the xfail marker yourself — that is S03's responsibility.
- The other 5 `test_doc_update_*` tests must all still pass.

Do NOT run `make test-unit`, `make test-integration`, or the full CLI contract suite — those are S10/S11 QV gates.

### 6. TDD evidence

The reproduction test already exists (`test_doc_update_new_doc_without_tier_is_clean_usage_error` as a strict xfail). Your fix makes it `XPASS(strict)` — that **is** the RED→GREEN demonstration: the test pinned the desired behaviour before the fix, and the unexpected-pass is the proof that your fix delivered it. Capture the `XPASS(strict)` line from pytest output in your report and pass it as `tdd_red_evidence` in the result contract — for example: `"tdd_red_evidence": "tests/integration/cli/test_doc_update_contract.py::test_doc_update_new_doc_without_tier_is_clean_usage_error XPASS(strict) — the strict xfail test now passes (asserts exit 2 + 'tier' in stderr); S03 will remove the xfail marker"`.

## Project Conventions

Read `CLAUDE.md` and `orch/CLAUDE.md`. Specific to this fix:

- Use `output_error(ctx, msg, exit_code)` for all CLI error paths in `orch/cli/` (consistent with the rest of `doc_commands.py`).
- Match existing snake_case + descriptive-message style. The new branch is a 3-4 line conditional, not a refactor.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`, run in order and fix anything they report:

1. **`make format`** — auto-fixes formatting drift.
2. **`make type-check`** — zero errors involving the file you touched.
3. **`make lint`** — zero errors.

Record results in the `preflight` field of your result contract.

## Test Verification (NON-NEGOTIABLE)

Targeted only — `uv run pytest tests/integration/cli/test_doc_update_contract.py -v --no-cov`. See Requirement 5 for the expected post-fix outcome (5 pass + 1 XPASS(strict); the XPASS is the GREEN signal, not a failure of your fix).

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "I-00108",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["orch/cli/doc_commands.py"],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "<N> passed, 1 XPASS(strict) on test_doc_update_new_doc_without_tier_is_clean_usage_error (expected — S03 removes the xfail marker)",
  "tdd_red_evidence": "<verbatim XPASS(strict) line from pytest>",
  "blockers": [],
  "notes": "S03 must remove the @pytest.mark.xfail(strict=True) marker from test_doc_update_new_doc_without_tier_is_clean_usage_error so the GREEN result is recorded as a normal pass instead of an XPASS-strict failure."
}
```
