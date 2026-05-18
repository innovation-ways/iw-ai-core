# CR-00058_S04_Template_report.md

**Step**: S04 — Template + Documentation
**Work Item**: CR-00058 — Configurable per-project scope-overlap gate with block/allow policy
**Agent**: template-impl
**Date**: 2026-05-18

---

## What Was Done

S04 landed the documentation, config example, and dashboard help-copy for the new `overlap_gate` block.

### Files Changed

| File | Change |
|------|--------|
| `docs/IW_AI_Core_Daemon_Design.md` | New §4.9 "Cross-batch Overlap Gate (Configurable)" with role description, `.iw-orch.json` schema table, Mermaid decision tree, two `DaemonEvent` metadata shapes, SIGHUP reload semantics, and operator guidance paragraph linking to `ai-dev/active/AUTO_MERGE_RESOLUTION.md`. |
| `docs/IW_AI_Core_Architecture.md` | One-sentence mention in §4.4 Daemon bullet pointing to Daemon Design §4.9; no schema duplication. |
| `.iw-orch.json` | Added `overlap_gate` block at top level (alphabetical-ish placement near related flags), with the default synthesized values. Produces zero behaviour change but documents the shape for operators. |
| `dashboard/templates/_partials/help/batches.html` | One-line note + anchor link to Daemon Design §4.9, placed before `<footer>`. |
| `dashboard/templates/_partials/help/queue.html` | Same one-line note + anchor link. |
| `dashboard/templates/_partials/help/batch_detail.html` | Same one-line note + anchor link. |

### Decision Tree

The Mermaid flowchart (§4.9) covers: (1) `find_blocking_items` call → overlapping globs list; (2) filter against `allow_on_overlap` per glob; (3) non-empty result → HOLD + `item_held_for_scope`; (4) empty + default-strict would have held → LAUNCH + `item_overlap_allowed_by_policy` (once); (5) empty + default would also allow → silent LAUNCH.

### Event Shapes

Both `DaemonEvent` types (§4.9) have `metadata` documented with exact field shapes:
- `item_held_for_scope`: `{blocking_item_id, conflicting_globs}`
- `item_overlap_allowed_by_policy`: `{candidate_item_id, in_flight_item_ids, matched_allow_patterns, dropped_block_globs}`

### Operator Guidance

Paragraph warns that relaxing `overlap_gate` without `scope_gate_enabled` leaves merge-time divergence unchecked; links to `ai-dev/active/AUTO_MERGE_RESOLUTION.md` as motivation context.

---

## Pre-flight Quality Gates

| Gate | Result |
|------|--------|
| `make format` | ok — 762 files already formatted |
| `make lint` | ok — Ruff + check_templates.py all passed |
| JSON validate | ok — `python -c "import json; json.load(open('.iw-orch.json'))"` clean |

---

## Test Results

Skipped — doc/template/config edits only, no production logic.

---

## TDD Red Evidence

n/a — doc/template/config edits only; no production logic.

---

## Blockers

None.

---

## Notes

- The help partial links use the project-scoped docs path `/project/iw-ai-core/system/docs/...` — matching the pattern used elsewhere in the dashboard.
- CLAUDE.md and `orch/CLAUDE.md` were NOT modified (outside `scope.allowed_paths` for this CR).
- The `overlap_gate` block in `.iw-orch.json` uses `"**/*conftest*"` with a trailing `*` to match `conftest.py` and any path containing `conftest` (as specified in the schema), not `"**/*conftest*" ` (trailing space was a typo risk and is not present).