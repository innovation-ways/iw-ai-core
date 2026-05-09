# CR-00039 S01 Frontend Report

## What was done

Implemented the labeled pill redesign for the step pipeline in the IW AI Core dashboard.

### Files Changed

1. **`dashboard/templates/components/step_pipeline.html`** — Full replacement of the macro
   - Replaced 6×14px compressed segment strip with labeled 52×42px fixed-width pills
   - Each pill shows step ID (`S01`) on line 1, formatted duration (`2m35s`) on line 2
   - Fix-cycle reruns render as separate amber pills labeled `↺SXX`
   - Connectors between pills (dashed amber for fix-cycle transitions, solid border for sequential steps)
   - Preserved `data-step-count="{{ steps | length }}"` on outer container (test assertion)
   - Status → CSS modifier mapping matches spec (`completed`, `in-progress`, `failed`, `skipped`, `pending`, `fixcycle`)

2. **`dashboard/templates/fragments/item_overview.html`** — Duration row removed
   - Removed the broken `<!-- Duration row -->` div and its `w-8` column children
   - Kept the `step_pipeline(steps)` macro call and surrounding card structure intact

3. **`dashboard/static/styles.css`** — New CSS appended (old `.iw-step-*` rules preserved)
   - `.iw-pipeline-strip`, `.iw-pipeline-pill`, `.iw-pipeline-pill-id`, `.iw-pipeline-pill-dur`
   - Per-status pill styles (`.iw-pipeline-pill--completed`, `--in-progress`, `--failed`, `--skipped`, `--pending`)
   - `.iw-pipeline-pill--fixcycle` (amber)
   - `.iw-pipeline-connector` and `.iw-pipeline-connector--fixcycle` (dashed amber stripe)

### Verification

| Check | Result |
|-------|--------|
| `make lint` | ✅ All checks passed |
| `make format-check` | ✅ 661 files already formatted |
| `make type-check` | ✅ Success: no issues found in 239 source files |
| `make test-unit` | ⚠️ 2 pre-existing failures in `test_safe_migrate.py` (unrelated to this change — confirmed by git stash test) |

Pipeline-specific test search (`-k "step_pipeline or item_overview or pipeline"`): **87 passed, 2 skipped**.

### Issues / Observations

- The 2 failing tests (`test_safe_migrate.py`) are pre-existing failures unrelated to this change (confirmed by running them against the stashed state without our changes).
- `make css` reports "Nothing to be done" — expected per CLAUDE.md guidance for worktrees (I-00067). Plain CSS is served as-is without Tailwind recompile.
- The old `.iw-step-strip` and `.iw-step-seg` CSS rules are intentionally left in place to avoid breaking any cached references.