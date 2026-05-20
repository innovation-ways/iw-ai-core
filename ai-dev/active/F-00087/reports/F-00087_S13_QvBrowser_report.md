# F-00087 S13 — qv-browser (lifecycle summary)

**Status**: PASS
**Base URL**: `http://localhost:9927` (per-worktree E2E stack `iw-ai-core-e2e-f00087`)
**Run date**: 2026-05-20

## What was done

Drove the F-00087 browser verification end-to-end with `playwright-cli` against
the per-worktree E2E stack. All eight verifications V0..V8 were executed and
**all pass**. Full detail (pass/fail table, screenshots, caveats) is in
`F-00087_S13_BrowserVerification_Report.md`.

## Results

- V0 PASS — `/project/iw-ai-core/` renders HTTP 200, 0 console errors.
- V1 PASS — Create-tab modal Runtime dropdown has exactly OpenCode + Pi.
- V2 PASS — Runtime=Pi re-fetches Model list to the 2 Pi models only; back to
  OpenCode re-fetches the full OpenCode list. No cross-runtime leakage.
- V3 PASS — Tab O (opencode) + Tab P1/P2 (pi, distinct models) in the strip;
  per-tab model dropdown is runtime-isolated.
- V4 PASS — All three tabs streamed their own response; no cross-pollination.
- V5 PASS — Abort on Tab P1 produced a "Run aborted." marker; Tab P2 and Tab O
  unaffected — no cascade.
- V6 PASS — `trigger-approval` raised the Permission Request modal on a Pi tab;
  Allow → `result: ✓ bash — ok`.
- V7 PASS — After reload all 3 tabs persisted; Tab O transcript restored;
  follow-up prompt in Tab P1 returned "Echo: hello again".
- V8 PASS — Home page clean; Ctrl+/ toggle works; Recent closed tabs menu
  works; no new console errors.

## Important correction

This run **supersedes a stale earlier report** that wrongly classified the run
as `ENV_DATA_MISSING` (V3..V7 `n/a`) based on `which pi` returning not-found.
The step prompt explicitly forbids `which pi` as a litmus test. The authoritative
signal — `POST /api/chat/tabs {"runtime":"pi"}` returning 201 — is healthy:
the dashboard lifespan falls back to the bundled stub `tests/integration/stubs/pi`
(present, executable, `IW_E2E_SEED=1`), and Pi tabs were created and fully
exercised. No code defect found.

## Stub caveat (not a defect)

The bundled stub `pi` is stateless: its `get_messages` returns `[]`, so Pi-tab
transcripts render empty after a tab switch / page reload. This is the exact
limitation the V7 prompt note acknowledges. OpenCode tabs (stateful runtime)
persist transcripts. Substantive behaviour — independent streaming, abort
isolation, approval flow, post-reload tab persistence + working follow-up
prompt — all verified.

## Files

- Detailed report: `ai-dev/active/F-00087/reports/F-00087_S13_BrowserVerification_Report.md`
- Pre screenshot: `ai-dev/active/F-00087/evidences/pre/F-00087-create-tab-modal-with-pi.png`
- Post screenshots: `ai-dev/active/F-00087/evidences/post/F-00087_v0..v8*.png` (11 files)
