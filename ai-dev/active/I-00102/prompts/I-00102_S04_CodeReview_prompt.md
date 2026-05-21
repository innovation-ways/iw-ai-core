# I-00102_S04_CodeReview_prompt

**Work Item**: I-00102 — iw register silently ignores design-package drift; approve must auto-refresh workflow_steps
**Steps Being Reviewed**: S01 (Database), S02 (Backend), S03 (Tests)
**Review Step**: S04
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`

## ⛔ Migrations: agents generate, daemon applies

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`

## Input Files

- **Runtime step state** — `uv run iw item-status I-00102 --json`.
- `ai-dev/active/I-00102/I-00102_Issue_Design.md` — the acceptance contract.
- Reports for S01, S02, S03 under `ai-dev/active/I-00102/reports/` (and `ai-dev/work/I-00102/reports/` if fix-cycles ran).
- Every file listed in those reports' `files_changed`.

## Output Files

- `ai-dev/active/I-00102/reports/I-00102_S04_CodeReview_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Any new violation in a changed file = **CRITICAL** finding.

## Review Checklist

### 1. Database — `orch/db/models.py` + `orch/db/migrations/versions/<rev>_…`

- `WorkItem.manifest_digest` is `Text`, `nullable=True`, no default, no server default — exactly as specified.
- Column placement matches the surrounding field grouping in `WorkItem`.
- The migration's `upgrade()` adds the column; `downgrade()` drops it; round-trip clean (verifiable via `make migration-check`).
- The revision's `down_revision` is the previous head; no silent multi-head merges.
- No unrelated schema changes piggy-backing on this migration.

### 2. Backend — `_compute_manifest_digest` helper

- Pure: no I/O, no DB, no global state. Easy to unit-test.
- Canonicalization is correct: sorted keys, empty/None values dropped, separators normalized, sha256 hex output.
- Ignores top-level manifest fields entirely (only the steps array contributes). The helper signature does NOT accept the full manifest — it takes the `steps` list. (If S02 wired it differently, flag as a HIGH finding: scope creep that turns scope/title/_note edits into spurious drift.)
- Helper lives where the surrounding code can find it without circular imports. Imported by both `register` and `approve` (the new `_insert_workflow_steps_from_manifest` helper too).

### 3. Backend — register path

- Idempotency short-circuit is unchanged (still echoes "Already registered" and returns; the digest is NOT recomputed in that branch).
- Digest is stored on the `WorkItem` only on the first successful insert.
- The step-insert loop has been factored into `_insert_workflow_steps_from_manifest(...)` (or equivalent); the call site reads cleanly.

### 4. Backend — approve path

- The new drift check runs **inside** the existing `with get_session()` block — single transaction, atomic with the status flip.
- Manifest path resolution is robust: prefers a stable derivation (e.g. relative to `repo_root` + `ai-dev/active/<ID>/workflow-manifest.json`). If the file is missing, approve fails with a clear error naming the path. No silent fallback to a "best guess" location.
- Drift branches:
  - Equal digests (both non-NULL) → proceed unchanged, no event emitted.
  - Different digests AND item in `draft` → rebuild.
  - Stored digest is NULL → treat as drift (backfill case, per AC5).
- The rebuild deletes all existing `workflow_steps` for the item, re-inserts via `_insert_workflow_steps_from_manifest(...)`, updates the digest, emits `DaemonEvent(event_type="manifest_refreshed", …)` with `old_digest`, `new_digest`, `old_step_count`, `new_step_count`, `trigger="approve"` in `event_metadata`.
- The phantom-skip pass (`auto_skip_phantom_qv_gates`) runs AFTER the rebuild, so it operates on the fresh rows. (Catch a regression where the order is flipped — it would skip steps that no longer exist.)
- `--json` output includes `manifest_refreshed: true|false`. Plain-text output emits a one-liner naming the row-count delta when refresh ran.
- No new CLI flag (`--refresh`, etc.) introduced — auto-refresh is the only path.

### 5. Backend — defensive assertion

- The "drift + item not in draft" branch is unreachable from `approve` (the existing status guard rejects non-draft), but the code MUST still raise/refuse rather than silently proceed (defends against future callers re-using the helper outside `approve`). Flag absence as a MEDIUM finding.

### 6. Tests — unit

- `tests/unit/test_item_commands_digest.py` covers determinism (key order, whitespace), changes (step_id, prompt path, add, remove, reorder), and the ignored-fields contract (None/empty within a step; top-level fields).
- Each assertion is **specific** (digest equality / inequality with computed expected values) — not "truthy" / "non-empty" shape checks.

### 7. Tests — integration

- `tests/integration/test_item_register_drift.py` reproduces the CR-00067 scenario end-to-end via the CLI commands against a real testcontainer DB.
- The reproduction test asserts:
  - Specific post-refresh `step_id` list and `agent_label` list (not just counts).
  - Exactly one `manifest_refreshed` event with metadata that names the row-count delta.
  - The digest on the row matches what the helper would compute for the v2 manifest.
- Backfill / NULL-digest path tested (AC5).
- Missing-manifest error path tested (no silent success).
- Transaction atomicity tested (rebuild crash → original rows intact).

### 8. Cross-cutting

- No regression in `orch/cli/item_commands.py` — adjacent commands (`unapprove`, `archive`, etc.) unchanged.
- No new live-DB writes from test code (run with the standard test invocation; assert `tests/CLAUDE.md` rules are honoured).
- Imports stay clean (no circular reach into the daemon).

## Finding Severity Definitions

- **CRITICAL** — Acceptance criteria broken; data corruption risk; security regression; new lint/format violation in a changed file.
- **HIGH** — Bug in the new code; missing defensive assertion the design requires; test that cannot fail; missing required test case.
- **MEDIUM_FIXABLE** — Style violations the daemon's QV gates will not catch; minor naming/comment improvements; small redundancy.
- **MEDIUM_INFO** — Observations worth recording but out of scope for S05.
- **LOW** — Nice-to-have suggestions.

## Output Report Shape

The report MUST contain a **Findings** section grouped by severity, each finding with: `file:line` reference, description, rationale, and recommended fix. The Subagent Result Contract MUST include a `verdict` of `pass` / `pass_with_fixes` / `fail`.

## Subagent Result Contract

```bash
mkdir -p ai-dev/active/I-00102/reports
uv run iw step-done I-00102 --step S04 \
  --report ai-dev/active/I-00102/reports/I-00102_S04_CodeReview_report.md
```

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00102",
  "completion_status": "complete",
  "files_changed": [
    "ai-dev/active/I-00102/reports/I-00102_S04_CodeReview_report.md"
  ],
  "preflight": {
    "format": "ok",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "review only — no tests run",
  "tdd_red_evidence": "n/a — review step",
  "verdict": "pass|pass_with_fixes|fail",
  "findings_count": {
    "critical": 0,
    "high": 0,
    "medium_fixable": 0,
    "medium_info": 0,
    "low": 0
  },
  "blockers": [],
  "notes": ""
}
```

If FAILED to complete review: `uv run iw step-fail I-00102 --step S04 --reason "..."`.
