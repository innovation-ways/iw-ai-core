# I-00102 S03 — Tests Implementation Report

## Step Summary

**Step**: S03 — Tests (reproduction + regression net)
**Agent**: tests-impl
**Work Item**: I-00102
**Completion**: complete

## What Was Done

Built the regression net for the manifest-drift detection + auto-refresh feature
(S01 column + S02 backend logic).

### Unit tests — `tests/unit/test_item_commands_digest.py`

15 tests for `_compute_manifest_digest` covering AC4 determinism and the digest
invariants: stability across key order and whitespace, sensitivity to step-id /
prompt-path / step-count / ordering changes, None / empty-string key stripping,
hex-format, and the top-level-fields exclusion contract. All assert specific
digest equality / inequality — never truthiness or length.

### Integration tests — `tests/integration/test_item_register_drift.py`

Rewritten harness. Drives the real `iw register` / `iw approve` Click commands
against a PostgreSQL testcontainer via `CliRunner`, with a test-supplied
`get_session` that mirrors production transaction semantics (per-invocation
SAVEPOINT, released on success, rolled back on any exception). 7 tests:

- `test_approve_auto_refreshes_workflow_steps_when_manifest_drifted_after_register`
  — the CR-00067/S08 reproduction: register 2-step v1, edit on disk to renumbered
  3-step v2, approve; asserts the exact post-refresh `step_id` + `agent_label`
  layout, exactly one `manifest_refreshed` event with correct old/new step counts
  and digests, and the stored digest updated to v2.
- `test_approve_no_drift_does_not_emit_refresh_event` — happy path: no event,
  digest unchanged.
- `test_register_stores_initial_digest` — digest populated and correct at register.
- `test_approve_with_null_digest_treats_as_drift_and_refreshes` — AC5 backfill:
  NULL digest treated as drift, `old_digest is None` in the event.
- `test_approve_with_missing_manifest_fails_loudly` — deleted manifest → exit 1,
  no event, `workflow_steps` untouched, status stays `draft`.
- `test_approve_on_non_draft_item_does_not_refresh` — AC3: the draft-only status
  guard fires before the drift path; no event, rows + digest unchanged.
- `test_approve_drift_rebuild_is_atomic_on_failure` — `_insert_workflow_steps_
  from_manifest` monkeypatched to raise after the DELETE; asserts the SAVEPOINT
  rolled the DELETE back — rows, digest and status all intact, no event.

### Harness fixes applied during the rewrite

The earlier draft of the integration file did not run. Corrected:

- `CliRunner(mix_stderr=False)` → `CliRunner()` — `mix_stderr` was removed in
  Click 8.3 (project is on click 8.3.2).
- The `cwd` argument was accepted but never applied; the CLI resolved
  `--design-doc` / `--steps-from` / `repo_root` against the process cwd. Tests
  now `monkeypatch.chdir(tmp_path)` and pass repo-root-relative paths.
- The `get_session` helper was constructed incorrectly (a context-manager object
  passed where a callable was expected). Replaced with `_make_get_session`.
- `agent_label` assertions corrected: `qv-gate` → `"QvGate"` (per `agent_to_label`).
- The non-draft error assertion corrected: the guard message names the actual
  status (`"approved"`), not `"draft"`.
- Test scaffolding now writes a Functional doc, which `approve`'s
  `ensure_active_files_committed` git-adds as part of the fixed design-package set.

## Files Changed

| File | Change |
|------|--------|
| `tests/unit/test_item_commands_digest.py` | 15 digest-invariant unit tests (extends S02's seed) |
| `tests/integration/test_item_register_drift.py` | New — 7 register/approve drift integration tests |

## Preflight Quality Gates

| Gate | Result |
|------|--------|
| `make format` | ok — 831 files already formatted |
| `make typecheck` | ok — no issues in 274 source files |
| `make lint` | ok — all checks passed |

## Test Results

```
uv run pytest tests/unit/test_item_commands_digest.py tests/integration/test_item_register_drift.py -v
tests/unit/test_item_commands_digest.py: 15 passed
tests/integration/test_item_register_drift.py: 7 passed
22 passed
```

Also green under `pytest-randomly` default ordering and seed 42424.

## Acceptance Criteria Coverage

| AC | Covered by |
|----|-----------|
| AC1 | `test_approve_auto_refreshes_workflow_steps_when_manifest_drifted_after_register` |
| AC2 | the reproduction test above passes against the S01+S02 fix |
| AC3 | `test_approve_on_non_draft_item_does_not_refresh` |
| AC4 | `tests/unit/test_item_commands_digest.py` (15 determinism/invariant tests) |
| AC5 | `test_approve_with_null_digest_treats_as_drift_and_refreshes` |

## Observations / Cross-Step Issue

**S02 regression — not in S03 scope, must be fixed before S13 can pass.**
S02 made `iw approve` unconditionally require an on-disk `workflow-manifest.json`.
This breaks 4 of 5 tests in `tests/integration/test_phantom_gate_auto_skip.py`,
which create items directly in the DB with no manifest:

```
FAILED test_iw_approve_auto_skips_phantom_makefile_gate
FAILED test_iw_approve_auto_skips_phantom_cd_gate
FAILED test_iw_approve_does_not_skip_real_gates
FAILED test_iw_batch_approve_runs_safety_net
```

All fail with `Manifest file not found: … cannot approve without the current
manifest`. `make test-integration` (S13) will fail until this is resolved — by
either relaxing the approve manifest check or giving those tests a manifest.
Flagged here for S04/S05 (code review + fix).

## Blockers

None for S03. The S02 phantom-gate regression above is a cross-step issue for the
backend layer, not a tests-step blocker.

## TDD

`tdd_red_evidence: n/a — dedicated test-coverage step` (per the S03 prompt).
