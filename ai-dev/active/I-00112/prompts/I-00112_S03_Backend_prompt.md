# I-00112_S03_Backend_prompt

**Work Item**: I-00112 -- Keep-Alive Scheduler logs `status=success` for silent no-op CLI fires
**Step**: S03
**Agent**: Backend

---

## ⛔ Docker is off-limits

You MUST NOT execute any docker state-change command. Testcontainers spun up by pytest fixtures are the only exception; read-only `docker ps/inspect/logs` is fine. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run alembic upgrade/downgrade/stamp against the live DB. This step does NOT touch migrations — S01 already produced the revision and S02 reviewed it. If you find yourself reaching for alembic, STOP — you are out of scope. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00112 --json`.
- `ai-dev/active/I-00112/I-00112_Issue_Design.md` — design document (read **Root Cause Analysis**, **Acceptance Criteria AC1–AC2**, **Notes** for the 500 ms rationale, and **Test to Reproduce** for the contract you must satisfy).
- `orch/keep_alive_service.py` — current `fire_claude`, `log_run`, and helpers.
- `orch/daemon/keep_alive_poller.py` — current `_fire_slot` and `_log_run`.
- S01's report: `ai-dev/active/I-00112/reports/I-00112_S01_Database_report.md` — confirms the four new model fields you can now write to.

## Output Files

- `orch/keep_alive_service.py` — refactored `fire_claude` + `log_run`.
- `orch/daemon/keep_alive_poller.py` — refactored `_fire_slot` + `_log_run`; the stricter success contract lives here.
- `ai-dev/active/I-00112/reports/I-00112_S03_Backend_report.md` — step report.

## Context

The bug: silent no-op CLI fires are logged as `status='success'` because the daemon discards stdout/stderr/elapsed_ms/returncode and only inspects `result.returncode`. S01 added the columns; S03 makes the service/poller actually capture and apply the stricter contract.

Read `ai-dev/active/I-00112/I-00112_Issue_Design.md` first (especially **Root Cause Analysis**, **Affected Components**, **Test to Reproduce**, **Notes**). Then read `CLAUDE.md` (root + `orch/CLAUDE.md`) for layer conventions.

## Requirements

### 1. Introduce `FireResult` dataclass in `orch/keep_alive_service.py`

Add a frozen dataclass:

```python
from dataclasses import dataclass

_MIN_SUCCESS_ELAPSED_MS = 500  # I-00112: a real Sonnet round-trip cannot complete faster

@dataclass(frozen=True, slots=True)
class FireResult:
    returncode: int
    stdout: str
    stderr: str
    elapsed_ms: int

    @property
    def is_success(self) -> bool:
        """I-00112 success contract: rc==0 AND stdout non-empty AND elapsed >= 500ms."""
        return (
            self.returncode == 0
            and self.stdout.strip() != ""
            and self.elapsed_ms >= _MIN_SUCCESS_ELAPSED_MS
        )

    @property
    def error_summary(self) -> str:
        """Compact failure description for the `error` column."""
        if self.returncode != 0:
            return (self.stderr or self.stdout or f"exit {self.returncode}").strip()
        if not self.stdout.strip():
            return f"silent no-op: rc=0, empty stdout, {self.elapsed_ms}ms elapsed (I-00112)"
        return f"too fast: rc=0, {self.elapsed_ms}ms elapsed (< {_MIN_SUCCESS_ELAPSED_MS}ms floor) (I-00112)"
```

Keep `_MIN_SUCCESS_ELAPSED_MS` as a module-level constant. The 500 ms floor MUST be derived from this constant in `is_success` — do not duplicate the magic number.

### 2. Refactor `fire_claude` to return `FireResult`

Replace the current `tuple[bool, str | None]` signature:

```python
def fire_claude(message: str, model: str, timeout: int = 30) -> FireResult:
    """Spawn `claude --model <model> -p <message>` and capture full result.

    Returns a FireResult carrying returncode, stdout, stderr, and elapsed_ms.
    Use FireResult.is_success to apply the I-00112 success contract.
    TimeoutExpired and FileNotFoundError are reflected as non-zero returncode
    with the diagnostic text in `stderr`.
    """
    import time
    start = time.perf_counter()
    try:
        result = subprocess.run(
            ["claude", "--model", model, "-p", message],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return FireResult(
            returncode=result.returncode,
            stdout=result.stdout or "",
            stderr=result.stderr or "",
            elapsed_ms=elapsed_ms,
        )
    except subprocess.TimeoutExpired:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return FireResult(returncode=-1, stdout="", stderr="subprocess timed out", elapsed_ms=elapsed_ms)
    except FileNotFoundError:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return FireResult(returncode=-1, stdout="", stderr="claude binary not found on PATH", elapsed_ms=elapsed_ms)
    except Exception as exc:  # noqa: BLE001 — caller logs full detail; treat as failure
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return FireResult(returncode=-1, stdout="", stderr=str(exc), elapsed_ms=elapsed_ms)
```

Place the `import time` at module-top with the other imports (do NOT keep it local). Use `time.perf_counter` — it is monotonic and immune to wall-clock jumps.

### 3. Extend `log_run` to persist the captured fields

```python
def log_run(
    db: Session,
    slot_id: int | None,
    slot_time: str,
    status: str,
    error: str | None = None,
    *,
    stdout: str | None = None,
    stderr: str | None = None,
    elapsed_ms: int | None = None,
    returncode: int | None = None,
) -> KeepAliveRun:
    """Insert a KeepAliveRun row. status must be one of VALID_RUN_STATUSES.

    I-00112: persist the four diagnostic fields alongside status/error on every run.
    """
    if status not in VALID_RUN_STATUSES:
        raise ValueError(f"Invalid status {status!r}; must be one of {VALID_RUN_STATUSES}")
    run = KeepAliveRun(
        slot_id=slot_id,
        slot_time=slot_time,
        status=status,
        error=error,
        stdout=stdout,
        stderr=stderr,
        elapsed_ms=elapsed_ms,
        returncode=returncode,
    )
    db.add(run)
    db.flush()
    return run
```

Keyword-only enforcement on the new fields prevents callers from positionally swapping `error` with `stdout`.

### 4. Refactor `_fire_slot` and `_log_run` in `orch/daemon/keep_alive_poller.py`

`_fire_slot` consumes `FireResult` directly and applies the I-00112 contract via `result.is_success`. The single existing retry still applies to the failure case — but a "fast/empty success" counts as a failure for the retry-policy purposes (so the retry attempt may yet land a real fire).

```python
def _fire_slot(self, slot_id: int, slot_time: str, model: str) -> None:
    """Fire a single slot: attempt + optional retry, then log result.

    I-00112: success requires FireResult.is_success (rc==0 AND non-empty stdout
    AND elapsed >= 500ms). A "silent no-op" — rc==0 but empty stdout or
    <500ms — is treated like any other failure and triggers the single retry.
    """
    message_1 = pick_message()
    result_1 = fire_claude(message_1, model)

    if result_1.is_success:
        self._log_run(slot_id, slot_time, status="success", result=result_1)
        return

    # Retry once with a new message
    message_2 = pick_message()
    result_2 = fire_claude(message_2, model)

    if result_2.is_success:
        self._log_run(slot_id, slot_time, status="retried_success", result=result_2)
    else:
        combined_error = f"{result_1.error_summary}; retry: {result_2.error_summary}"
        # Capture detail from the retry attempt (it's the more recent / authoritative one)
        self._log_run(slot_id, slot_time, status="retried_failed", result=result_2, error=combined_error)
```

`_log_run` accepts the FireResult and forwards every diagnostic field:

```python
def _log_run(
    self,
    slot_id: int,
    slot_time: str,
    status: str,
    result: FireResult,
    error: str | None = None,
) -> None:
    """Log a run record within a fresh session. I-00112: persist full FireResult."""
    effective_error = error if error is not None else (result.error_summary if not result.is_success else None)
    with SessionLocal() as db:
        log_run(
            db,
            slot_id=slot_id,
            slot_time=slot_time,
            status=status,
            error=effective_error,
            stdout=result.stdout,
            stderr=result.stderr,
            elapsed_ms=result.elapsed_ms,
            returncode=result.returncode,
        )
        db.commit()
    logger.info(
        "KeepAlive slot=%s time=%s status=%s rc=%s elapsed_ms=%s stdout_len=%s",
        slot_id,
        slot_time,
        status,
        result.returncode,
        result.elapsed_ms,
        len(result.stdout),
    )
```

Note the log line additions — they now carry rc / elapsed_ms / stdout_len so the daemon log alone is enough to triage a suspicious fire without hitting the DB.

### 5. Import `FireResult` in the poller

Add `FireResult` to the existing `from orch.keep_alive_service import …` block.

### 6. Do NOT touch any other file

- **Do NOT** touch `orch/db/models.py` or any migration (S01's scope).
- **Do NOT** touch any template, fragment, router, or `dashboard/static/` (S05's scope).
- **Do NOT** add or modify test files (S07's scope). Existing tests that use `fire_claude`'s old `(bool, error)` return shape will break — that is **expected** and is S07's RED evidence. Your job is to make the contract change cleanly; S07 rewrites the tests to match.

If you find yourself reaching for any of the above, STOP — the work belongs to a downstream step.

## Project Conventions

Read `CLAUDE.md` for:
- Layer boundaries (`orch/keep_alive_service.py` is the only place subprocess + business logic live; `orch/daemon/keep_alive_poller.py` is the polling shim).
- Logging style (use `logger.info(...)` with `%`-format placeholders, never f-strings).
- Type style: PEP 604 unions (`str | None`), `Mapped[]` for ORM (not used here).
- `noqa` codes must include the rule (`# noqa: BLE001`, never bare `# noqa`).

## TDD Requirement

`tdd_red_evidence` IS REQUIRED for this Backend step. The RED evidence comes from running an existing keep-alive test against the refactored code — the change in return signature will break any test that asserts on `(bool, error)` shape. Capture the failure (`AttributeError` on `.is_success` / `tuple` unpack failure / etc.) before reporting completion. The fix is to make the test mock match the new signature, but S07 will own the rewrite — for S03, simply record the RED line as evidence and move on. (The tests you may currently break will be re-authored in S07; meanwhile, your contract change is correct.)

If you find that no existing test exercises the changed boundary, use `"n/a — no pre-existing behavioural test covers fire_claude's return shape; new behavioural coverage owned by S07"`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting completion:

1. **`make format`** — auto-fixes formatting drift on `orch/keep_alive_service.py` and `orch/daemon/keep_alive_poller.py`.
2. **`make typecheck`** — zero errors on touched files. Pay attention: `FireResult.is_success` returns `bool`; mypy must agree.
3. **`make lint`** — zero errors.

## Test Verification

Run only the targeted unit tests for keep-alive code:

```bash
uv run pytest tests/unit/test_keep_alive_service.py tests/unit/test_keep_alive_poller.py -v
```

Existing tests that mock `fire_claude` to return `(True, None)` / `(False, "…")` WILL fail — note them under `notes` as "expected RED; S07 will rewrite". Do **NOT** rewrite them yourself.

Do NOT run `make test-unit` or `make test-integration` — those are S16/S17 QV gates.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "Backend",
  "work_item": "I-00112",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/keep_alive_service.py",
    "orch/daemon/keep_alive_poller.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": false,
  "test_summary": "<n existing> failed (expected RED — existing tests assume old (bool, error) shape; S07 will rewrite). New behavioural correctness is verified by S07's targeted suite.",
  "tdd_red_evidence": "tests/unit/test_keep_alive_service.py::test_… — AttributeError: 'FireResult' object has no attribute '…'  // captured RED run; expected — S07 owns rewrite",
  "blockers": [],
  "notes": "FireResult is frozen + slots + property is_success encoding the I-00112 contract. _MIN_SUCCESS_ELAPSED_MS = 500. Retry policy unchanged: silent no-op triggers the existing single retry, same as rc!=0 did before. Tests broken by the contract change: <list>. These are S07's RED evidence and will be rewritten there."
}
```

## Lifecycle Commands

```bash
uv run iw step-start I-00112 --step S03
# work
mkdir -p ai-dev/active/I-00112/reports
uv run iw step-done I-00112 --step S03 --report ai-dev/active/I-00112/reports/I-00112_S03_Backend_report.md
```
