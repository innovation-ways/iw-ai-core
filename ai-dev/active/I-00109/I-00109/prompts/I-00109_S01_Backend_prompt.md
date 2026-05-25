# I00109_S01_Backend_prompt

**Work Item**: I-00109 -- `GET /project/{project_id}/docs/{doc_id}/pdf` raises unhandled `PermissionError` → HTTP 500 when on-disk PDF cache dir is not writable
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

Allowed exceptions: testcontainer fixtures in pytest, read-only
`docker ps` / `docker logs` / `docker inspect`, and `./ai-core.sh` / `make`
targets.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT create, modify, or apply any alembic migration. **This work
item adds no schema change.** If your fix appears to require one, STOP
and raise a blocker — the scope is wrong.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00109 --json` for the current step list (workflow-manifest.json is a design-time snapshot).
- `ai-dev/active/I-00109/I-00109_Issue_Design.md` -- Design document (read first, especially §Root Cause Analysis and §Acceptance Criteria).
- `ai-dev/active/I-00109/I-00109_Functional.md` -- Human-facing summary.
- `dashboard/routers/docs.py` -- The file you'll modify (`docs_pdf` callback at lines 271-330; mirror the guard pattern already present in `docs_pdf_view` at lines 188-268, specifically the cache-write `try/except` at lines 256-266).
- `dashboard/CLAUDE.md` -- Dashboard layer conventions (routers thin, no docker, no migrations).
- `tests/dashboard/test_route_contract_sweep.py` -- Read-only at this step: contains the `EXPECTED_5XX` entry pinning the bug. S03 (tests-impl) will remove the entry; **do not touch this file from S01**.

## Output Files

- `ai-dev/active/I-00109/reports/I-00109_S01_Backend_report.md` -- Step report.

## Context

The download-PDF route `docs_pdf` at `dashboard/routers/docs.py:271-330` generates a PDF on-the-fly, then unconditionally writes a cache file to `project.repo_root / "docs" / ".generated" / project_id / `. On hosts where `repo_root` (or any segment) is not writable, the unguarded write raises `PermissionError`, which FastAPI surfaces as HTTP 500 — even though the PDF bytes were already generated successfully on the line above.

The sibling handler `docs_pdf_view` (the iframe-embedded variant, same file, lines 188-268) does the **identical** cache-write sequence but wraps it in `try / except Exception` at lines 256-266 with a `logging.getLogger(__name__).warning("Failed to write pdf_path cache for doc %s/%s", project_id, doc_id)`. Your job is to mirror that exact guard in `docs_pdf`.

Read the design doc's §Root Cause Analysis and §Acceptance Criteria fully before editing. The fix must keep the response path unchanged when the cache write succeeds (the existing happy path is correct), and must return the PDF bytes unconditionally when the cache write fails (the bytes were generated successfully — the response should not depend on the cache).

## Requirements

### 1. Wrap the cache-write block in `dashboard/routers/docs.py::docs_pdf`

In the `docs_pdf` callback at `dashboard/routers/docs.py:271-330`, locate the unguarded block at lines 320-324:

```python
cache_dir = Path(project.repo_root) / "docs" / ".generated" / project_id
cache_dir.mkdir(parents=True, exist_ok=True)
cache_file = cache_dir / f"{doc_id}-v{doc.version}.pdf"
cache_file.write_bytes(pdf_bytes)
svc.update_doc(project_id, doc_id, pdf_path=str(cache_file))
```

Wrap this block in `try / except Exception` mirroring the exact pattern already present in `docs_pdf_view` at lines 254-266. The post-fix shape:

```python
cache_dir = Path(project.repo_root) / "docs" / ".generated" / project_id
try:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{doc_id}-v{doc.version}.pdf"
    cache_file.write_bytes(pdf_bytes)
    svc.update_doc(project_id, doc_id, pdf_path=str(cache_file))
except Exception:  # noqa: BLE001 — read-only fs, permission error, etc.
    import logging

    logging.getLogger(__name__).warning(
        "Failed to write pdf_path cache for doc %s/%s", project_id, doc_id
    )
```

**The pattern MUST match `docs_pdf_view` lines 256-266 exactly**:

- Same `except Exception:  # noqa: BLE001 — read-only fs, permission error, etc.` comment (verbatim — the comment carries the rationale for the broad catch).
- Same `import logging` inside the except block (matches the existing handler's style; do not hoist it to the module top unless `docs_pdf_view`'s copy is also hoisted in the same change, which it should NOT be — out of scope).
- Same logger call: `logging.getLogger(__name__).warning("Failed to write pdf_path cache for doc %s/%s", project_id, doc_id)`. Use the same format string verbatim — the message is part of the operator-visible contract.

### 2. Return the PDF bytes unconditionally

The existing `return Response(content=pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": ...})` at lines 326-330 stays exactly as-is. It executes whether the cache write succeeded or raised — that is the whole point of the fix. Do NOT move the return inside the `try` block, do NOT add a second return inside the `except` block.

### 3. Preserve all other behaviour

- The `_get_project_or_404` + 404 lookups (lines 278-287) are untouched.
- The cached-PDF fast path (lines 289-298) is untouched.
- The on-the-fly render + Chromium-not-installed 503 (lines 300-318) is untouched.
- The `Content-Disposition: attachment; filename="..."` header is preserved verbatim.
- `docs_pdf_view` (lines 188-268) MUST NOT be edited — the fix is in `docs_pdf` only. They are sibling handlers and the existing `docs_pdf_view` guard is the reference, not a target.

### 4. Scope discipline

You may modify ONLY `dashboard/routers/docs.py`. Do NOT edit:

- `dashboard/routers/docs.py::docs_pdf_view` (sibling — already correct).
- `tests/dashboard/test_route_contract_sweep.py` (S03 owns the `EXPECTED_5XX` removal).
- Any template, service, or other router.

If you find yourself wanting to refactor the duplicated `try/except` into a shared helper, STOP — that is out of scope for this incident. File a follow-up CR after merge if you want consolidation.

### 5. Test verification (targeted only)

Run **only** the dashboard route-sweep test file from this step to confirm your fix doesn't break existing route coverage:

```bash
uv run pytest tests/dashboard/test_route_contract_sweep.py -v --no-cov
```

Expected post-fix:
- The parametrized case `test_route_returns_no_5xx[GET /project/{project_id}/docs/{doc_id}/pdf]` is currently `xfail(strict=True)` via the `EXPECTED_5XX` entry. After your fix it should report `XPASS(strict)` which **fails** the run, because `strict=True` treats unexpected passes as failures. **This is expected at this step** — S03 removes the `EXPECTED_5XX` entry, after which the case records as a normal pass. Record this in your report and in the result contract's `notes` field. Do NOT remove the `EXPECTED_5XX` entry yourself — that is S03's responsibility.
- All other sweep cases must still pass.

Do NOT run `make test-unit`, `make test-integration`, or the full dashboard test suite — those are S10/S11 QV gates.

### 6. TDD evidence

The reproduction test (`tests/dashboard/test_docs_pdf_cache_failure.py::test_docs_pdf_returns_200_when_cache_dir_not_writable`) does not yet exist — it will be written by S03 (tests-impl) under the **xfail(strict)** + sweep-marker pattern is not applicable here because the test is a brand new file. The RED-first evidence for S01 is the **existing** strict-xfail case in `test_route_contract_sweep.py`:

- Pre-fix: `test_route_returns_no_5xx[GET /project/{project_id}/docs/{doc_id}/pdf]` is `xfailed` (returns 500, marker holds).
- Post-fix: same case becomes `XPASS(strict)` → reported as FAIL by pytest because `strict=True`. That is the RED→GREEN demonstration — the strict-xfail flipped is the proof the bug is gone.

Capture the `XPASS(strict)` line from pytest output in your report and pass it as `tdd_red_evidence` in the result contract — for example: `"tdd_red_evidence": "tests/dashboard/test_route_contract_sweep.py::test_route_returns_no_5xx[GET /project/{project_id}/docs/{doc_id}/pdf] XPASS(strict) — the strict-xfail allowlist entry now passes (route returns < 500); S03 removes the EXPECTED_5XX entry and adds a dedicated regression test under tests/dashboard/test_docs_pdf_cache_failure.py"`.

## Project Conventions

Read `CLAUDE.md` and `dashboard/CLAUDE.md`. Specific to this fix:

- Routers stay thin — no business logic moves out of `docs_pdf`. The fix is a defensive wrap of an existing five-line block.
- Match the exact pattern of `docs_pdf_view`'s guard (lines 256-266) — same comment, same logger call, same warning message format. Consistency between the two handlers is part of the regression-prevention story.
- Use `logging.getLogger(__name__)` (matches the file's existing convention — `docs_pdf_view` does the same).

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`, run in order and fix anything they report:

1. **`make format`** — auto-fixes formatting drift.
2. **`make type-check`** — zero errors involving the file you touched.
3. **`make lint`** — zero errors.

Record results in the `preflight` field of your result contract.

## Test Verification (NON-NEGOTIABLE)

Targeted only — `uv run pytest tests/dashboard/test_route_contract_sweep.py -v --no-cov`. See Requirement 5 for the expected post-fix outcome (1 XPASS(strict) on the docs-pdf case, all others pass; the XPASS is the GREEN signal, not a failure of your fix).

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "I-00109",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["dashboard/routers/docs.py"],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "<N> passed, 1 XPASS(strict) on test_route_returns_no_5xx[GET /project/{project_id}/docs/{doc_id}/pdf] (expected — S03 removes the EXPECTED_5XX entry)",
  "tdd_red_evidence": "<verbatim XPASS(strict) line from pytest>",
  "blockers": [],
  "notes": "S03 must remove the EXPECTED_5XX entry for '/project/{project_id}/docs/{doc_id}/pdf' from tests/dashboard/test_route_contract_sweep.py and add the dedicated regression test tests/dashboard/test_docs_pdf_cache_failure.py::test_docs_pdf_returns_200_when_cache_dir_not_writable, so the GREEN result is recorded as a normal pass instead of an XPASS-strict failure."
}
```
