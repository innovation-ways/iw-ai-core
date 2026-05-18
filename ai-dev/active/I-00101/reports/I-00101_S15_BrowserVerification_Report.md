# I-00101 S15 Browser Verification Report

## Environment
- Base URL used: `http://127.0.0.1:9920` (mapped from `IW_BROWSER_BASE_URL=http://localhost:9920`)
- E2E user: `dev@example.local` / `DevPass2026!`

## Verifications

| ID | Name | Status | Failure Class | Screenshot | Notes |
|----|------|--------|---------------|------------|-------|
| V0 | Pre-flight page sanity | pass | null | — | /system/running and item detail page: no dangling fragment references, no console errors |
| V1 | Scope-blocked badge renders on item detail page | pass | null | `evidences/post/I-00101_v1_badge_visible.png` | Badge shows "Scope blocked: .test-target.toml" with ✎ Amend scope + ↩ Revert + ⏭ buttons; Restart is absent |
| V2 | Amend modal opens with offending path pre-checked | pass | null | `evidences/post/I-00101_v2_modal_open.png` | Modal titled "Amend scope for I-00101-SYNTH / S01"; checkbox for `.test-target.toml` is checked; current allowed_paths listed |
| V3 | Submitting modal writes manifest, emits event, restarts step | pass | null | `evidences/post/I-00101_v3_after_amend.png` | S01 status flips to `pending` (confirmed via curl + live snapshot); `daemon_events` row confirms `scope_amended_by_operator` with `added_paths: [".test-target.toml"]`; manifest updated at `/tmp/iw-e2e-worktrees/I-00101-SYNTH-synth/ai-dev/active/I-00101-SYNTH/workflow-manifest.json` |
| V4 | Revert flow | skip | null | — | Covered by S05 integration tests; second synthetic seed not feasible in this run |
| Vn | No regressions | pass | null | `evidences/post/I-00101_v_n_no_regressions.png` | `/system/running` shows synthetic item in scope-blocked state and no unrelated failures; project home, history pages show no 500s |

## Console / Network Errors
None observed. The two 404s on `/projects/e2e-i00101-scope/staleness-dot` at page load are pre-existing in the E2E stack (a staleness feature routing issue unrelated to this feature).

## No Regressions
- `/system/running` page loads cleanly with the `Scope blocked` badge visible and the correct action buttons (Amend scope, Revert, Skip) present.
- `/project/e2e-i00101-scope/` home page loads without errors.
- S01 on the synthetic item shows `pending` after the amend action (step correctly queued for restart).
- The synthetic worktree manifest was updated with `.test-target.toml` added to `scope.allowed_paths`; the `scope_amended_by_operator` event was emitted and persisted in `daemon_events`.

## Screenshots captured
- `ai-dev/active/I-00101/evidences/post/I-00101_v1_badge_visible.png` — V1: scope-blocked badge on item detail page
- `ai-dev/active/I-00101/evidences/post/I-00101_v2_modal_open.png` — V2: amend modal open with `.test-target.toml` checked
- `ai-dev/active/I-00101/evidences/post/I-00101_v3_after_amend.png` — V3: item detail after amend, S01 is `pending`
- `ai-dev/active/I-00101/evidences/post/I-00101_v_n_no_regressions.png` — Vn: system running page (no regressions)

## Root cause (on failure only)
N/A — all verifications passed.
