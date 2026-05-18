# I-00091 S14 Browser Verification Report

## Environment
- Base URL used: http://localhost:9924
- E2E user: dev@example.local

## Verifications

| ID | Name | Status | Failure Class | Screenshot | Notes |
|----|------|--------|---------------|------------|-------|
| V0 | Pre-flight page sanity | pass | code_defect/null | | No dangling refs on homepage/auto-merge/queue/batches. One pre-existing htmx:targetError console message from a prior run (port 9900, not current worktree port 9924) — not caused by current code. |
| V1 | Phase-only override survives reload | pass | code_defect/null | evidences/post/I-00091_v1_phase_only.png | Phase dropdown shows `1 — dry-run` selected immediately post-Save and post-reload. Footer shows `Last changed: ...`. Runtime remains `Use global default`. |
| V2 | Runtime-only override survives reload | pass | code_defect/null | evidences/post/I-00091_v2_runtime_only.png | Runtime dropdown shows `Sonnet 4.6` selected immediately post-Save and post-reload. Footer shows `Last changed: ...`. Phase remains `Use global default`. Status chip updated from `P1 opencode/minimax/MiniMax-M2.7` to `P1 claude/claude-sonnet-4-6` confirming runtime was applied. |
| V3 | Both-axes override survives reload | pass | code_defect/null | evidences/post/I-00091_v3_both_axes.png | Both Phase (`1 — dry-run`) and Runtime (`Sonnet 4.6`) show their selections post-Save and post-reload. Footer shows `Last changed: ...`. |
| V4 | Clear back to global removes the override | pass | code_defect/null | evidences/post/I-00091_v4_clear_to_global.png | Both dropdowns back to `Use global default` immediately post-Save. Footer reads `Using global default` (not `Last changed`). Post-reload, both remain on global and footer still reads `Using global default`. API confirms Phase source: toml / Runtime source: toml (no per_project_db row). |
| V5 | In-place swap, no full-page reload | pass | code_defect/null | evidences/post/I-00091_v5_inplace_swap.png | Pre-Save refs start at e65; post-Save refs start at e226. Both sets are non-reset values (> e1), confirming element refs continued across the htmx in-place swap. No full-page navigation. |
| V6 | No regressions on adjacent flows | pass | code_defect/null | evidences/post/I-00091_v6_no_regressions.png | Verdict rollup 7d and 30d buttons both respond to clicks (content refreshes). Queue page renders normally. Batches page renders normally. No new console errors introduced. |

## Console / Network Errors
- One pre-existing htmx:targetError from an earlier run targeting port 9900 (the prod stack, not this worktree's port 9924). This error was present before this run started and is unrelated to I-00091 changes.

## No Regressions
- Verdict rollup 7d/30d buttons functional (htmx-get path not modified by I-00091)
- Queue page (`/project/iw-ai-core/queue`) renders normally
- Batches page (`/project/iw-ai-core/batches`) renders normally
- No new console errors introduced during V1-V5

## Screenshots captured
- ai-dev/active/I-00091/evidences/post/I-00091_v1_phase_only.png
- ai-dev/active/I-00091/evidences/post/I-00091_v1_phase_only_reload.png
- ai-dev/active/I-00091/evidences/post/I-00091_v2_runtime_only.png
- ai-dev/active/I-00091/evidences/post/I-00091_v3_both_axes.png
- ai-dev/active/I-00091/evidences/post/I-00091_v4_clear_to_global.png
- ai-dev/active/I-00091/evidences/post/I-00091_v5_inplace_swap_before.png
- ai-dev/active/I-00091/evidences/post/I-00091_v5_inplace_swap.png
- ai-dev/active/I-00091/evidences/post/I-00091_v6_no_regressions.png

## Root cause
No failures found. All verifications passed.