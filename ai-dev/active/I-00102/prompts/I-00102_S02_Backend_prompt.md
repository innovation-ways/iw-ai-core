# I-00102_S02_Backend_prompt

**Work Item**: I-00102 — iw register silently ignores design-package drift; approve must auto-refresh workflow_steps
**Step**: S02
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`

## ⛔ Migrations: agents generate, daemon applies

S01 already added the `manifest_digest` column + migration. Do NOT add another migration. Do NOT run `alembic upgrade` against the live orch DB.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00102 --json`.
- `ai-dev/active/I-00102/I-00102_Issue_Design.md` — design document (read **Description**, **Root Cause Analysis**, **Fix Plan / Code Changes**, **Acceptance Criteria** AC1/AC3/AC4/AC5 in full).
- `ai-dev/active/I-00102/reports/I-00102_S01_Database_report.md` — S01's report (so you know the column name and migration revision).
- `orch/cli/item_commands.py` — current `register` and `approve` commands (your edit targets).
- `orch/cli/utils.py` — shared CLI helpers (use existing ones; do not duplicate).
- `orch/db/models.py` — `WorkItem`, `WorkflowStep`, `DaemonEvent` ORM models.
- `orch/qv_gate_validator.py` — pattern for emitting `DaemonEvent` audit rows from a CLI command (use the same shape).

## Output Files

- `orch/cli/item_commands.py` — register stores digest; approve detects + auto-refreshes drift.
- `ai-dev/active/I-00102/reports/I-00102_S02_Backend_report.md` — step report.

## Context

Today `iw register` is silently idempotent (`orch/cli/item_commands.py:343`-ish — the `existing` short-circuit). The user can edit the design package after register and approve never notices, so the DB and disk drift. This step closes that loop by:

1. Persisting a content digest of the manifest's `steps` array on the `WorkItem` at register time.
2. Re-reading the manifest at `iw approve` time, recomputing the digest, and — if it differs and the item is still in `draft` — atomically replacing the `workflow_steps` rows from the current on-disk manifest under a single transaction, then storing the new digest and emitting a `manifest_refreshed` daemon event.

A companion fix (already on `fix/daemon-prompt-file-missing-fail-fast`) ensures the daemon's launch path fails fast on a missing prompt file; this step removes the root cause one level upstream.

The user explicitly chose **auto-refresh on approve** + **draft-only**. There is intentionally NO new CLI flag (`--refresh`, etc.) — auto-refresh on approve fully covers the only legitimate pre-execution editing window.

## Requirements

### 1. `_compute_manifest_digest(steps: list[dict]) -> str`

Add a pure helper near `parse_manifest_steps` in `orch/cli/item_commands.py`. Keep it **in `item_commands.py`** — the workflow-manifest `scope.allowed_paths` admits only `orch/cli/item_commands.py`, not a new `orch/cli/` module, and the design's *Code Changes* section lists no new source file. Do NOT create a sibling module. Contract:

- Input: the `manifest_steps` list (each element is a dict).
- Output: a hex string (sha256 hex digest) — use Python stdlib `hashlib.sha256`.
- Canonicalization rules (to make the digest invariant under cosmetic edits):
  1. For each step dict, drop keys whose values are `None` or empty strings.
  2. Serialize each step via `json.dumps(step, sort_keys=True, separators=(",", ":"))`.
  3. Join with `\n` and hash.
- The helper MUST ignore the manifest's top-level fields (`title`, `_note`, `scope`, `browser_verification`, …). It hashes the steps array only — see design **Notes** for why (`_note` is auto-stamped on register, `title` lives on `WorkItem`, scope is enforced at merge time).
- Pure / no I/O — easy to unit test. S03 will add the determinism unit tests.

### 2. Populate digest at register

In the `register` command, after `parse_manifest_steps(manifest_path)`, compute the digest and pass it through to the new `WorkItem(... manifest_digest=...)` keyword.

Keep this **outside** the idempotency branch — the early "Already registered" exit must continue to short-circuit; that branch is unchanged. The digest is only stored on the first successful insert.

### 3. Approve-time drift detection + auto-refresh

In the `approve` command, BEFORE flipping `status → approved` and BEFORE calling `ensure_active_files_committed` / `ingest_phase_from_disk`:

1. Resolve the on-disk manifest path. Derive it from the design directory: when `WorkItem.design_doc_path` is set, use `Path(design_doc_path).parent / "workflow-manifest.json"`; otherwise fall back to the canonical `ai-dev/active/<ID>/workflow-manifest.json` resolved relative to `repo_root`. Do **not** use `WorkItem.config["scope_extraction"]["source"]` — that field is a marker string (`declared` / `regex_fallback` / `none`), not a path. If the manifest file does **not** exist on disk, fail with a clear `output_error` message naming the missing path (this is the AC-tested missing-manifest branch — never proceed with a "ghost" approve).
2. Re-parse via `parse_manifest_steps(...)` (the same path register uses — keeps canonicalization identical).
3. Recompute the digest via `_compute_manifest_digest(...)`.
4. Compare against `item.manifest_digest`. Three branches:
   - **No drift** (digests equal, and the existing digest is not NULL): proceed with the rest of `approve` unchanged. Do NOT emit any event.
   - **Drift, and `item.status == WorkItemStatus.draft`**: enter the rebuild path (§4).
   - **Drift, and `item.status != WorkItemStatus.draft`**: this case cannot arise inside `approve` (the existing `validate_approve_transition` already rejects non-draft items), but pin it explicitly as a defensive assert (`raise RuntimeError(...)` with a clear message that ties to AC3) so the refresh path stays draft-only by construction even if future callers reuse the helper.
5. **Existing-digest-is-NULL** is treated as drift (per design AC5 — items registered before this column existed always refresh on the first approve, then store the digest).

### 4. The rebuild path (single transaction)

Inside the existing `with get_session() as session:` block (so this is atomic with the approve flip):

1. `session.query(WorkflowStep).filter(...).delete(synchronize_session=False)` — delete all existing `workflow_steps` rows for this `(project_id, item_id)`. The unique constraint on `(project_id, work_item_id, step_number)` makes a naive UPDATE-in-place fragile; full replace is simpler and correct because the item is in `draft` (no run history exists).
2. Re-insert the new rows using exactly the same loop body that `register` uses (extract the body into a shared helper — `_insert_workflow_steps_from_manifest(session, project_id, item_id, manifest_steps, ctx)` — and call it from both `register` and `approve`, so the two sites can never desync).
3. Update `item.manifest_digest` to the new digest.
4. Emit a `DaemonEvent` audit row:
   ```python
   DaemonEvent(
       project_id=project_id,
       event_type="manifest_refreshed",
       entity_id=item_id,
       entity_type="work_item",
       message=f"Manifest drifted since register — workflow_steps rebuilt for {item_id} ({old_step_count} → {new_step_count} steps)",
       event_metadata={
           "old_digest": item.manifest_digest_before_update,  # snapshot before §3
           "new_digest": new_digest,
           "old_step_count": old_step_count,
           "new_step_count": new_step_count,
           "trigger": "approve",
       },
   )
   ```
5. Continue with the rest of `approve` (the `status → approved` flip + the existing evidence ingest + `auto_skip_phantom_qv_gates` call). The phantom-skip pass runs against the freshly-rebuilt rows, so its semantics are unchanged.
6. Echo a one-line success note to stdout (in addition to the existing "Approved …" line): `f"Refreshed workflow_steps from manifest ({old_step_count} → {new_step_count} steps)"`. The `--json` mode adds a `manifest_refreshed: true|false` key.

### 5. No new CLI flag

Do NOT add `iw register --refresh`, `iw approve --refresh`, or similar. Auto-refresh on approve fully covers the case (per the user's explicit choice).

### 6. Reuse, don't fork

The new `_insert_workflow_steps_from_manifest` helper takes the exact same `manifest_steps` shape that `register` already parses today. Refactor `register`'s existing loop (the one inside `with get_session() as session:`) into the helper and call it; do NOT copy-paste. This is what guarantees register and refresh stay byte-identical going forward.

## Project Conventions

Read `CLAUDE.md` (root), `orch/CLAUDE.md`, and the surrounding code in `orch/cli/item_commands.py`. Match the existing CLI error style (`output_error(ctx, msg, exit_code)`), the `click.echo` patterns, and the `--json` toggle. Match the daemon-event metadata shape used by `auto_skip_phantom_qv_gates` (`orch/qv_gate_validator.py`).

## TDD Requirement

Follow TDD. The behavioural test surface for this step is small and lives almost entirely in S03 (which writes the reproduction + regression tests). For this step, you MUST add at least:

- One unit test for `_compute_manifest_digest`'s **determinism** (same logical steps → same hash, even with shuffled key order in the dicts). Place it at `tests/unit/test_item_commands_digest.py`. Capture the RED-evidence snippet for your result contract.

Run the targeted test:

```bash
uv run pytest tests/unit/test_item_commands_digest.py -v
```

Do NOT run the full unit or integration suites — those are S12/S13 QV gates.

The bulk of the behaviour testing (drift → refresh → events recorded; refusal on missing manifest; etc.) is owned by S03 — keep your own tests narrow.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification (NON-NEGOTIABLE)

- `uv run pytest tests/unit/test_item_commands_digest.py -v` (your new digest test).
- Targeted unit tests covering `orch/cli/item_commands.py` if they exist (e.g. `tests/unit/test_item_commands.py` — if present, run only those; do NOT broaden).

## Subagent Result Contract

```bash
mkdir -p ai-dev/active/I-00102/reports
uv run iw step-done I-00102 --step S02 \
  --report ai-dev/active/I-00102/reports/I-00102_S02_Backend_report.md
```

```json
{
  "step": "S02",
  "agent": "backend-impl",
  "work_item": "I-00102",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/cli/item_commands.py",
    "tests/unit/test_item_commands_digest.py"
  ],
  "preflight": {
    "format": "ok|fixed",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "tests/unit/test_item_commands_digest.py: N passed",
  "tdd_red_evidence": "tests/unit/test_item_commands_digest.py::test_digest_is_deterministic_across_key_order — <RED snippet>",
  "blockers": [],
  "notes": ""
}
```

If FAILED: `uv run iw step-fail I-00102 --step S02 --reason "..."`.

**IMPORTANT**: Call `step-done` or `step-fail` before exiting.
