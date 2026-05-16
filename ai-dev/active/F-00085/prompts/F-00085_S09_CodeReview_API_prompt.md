# F-00085_S09_CodeReview_API_prompt

**Work Item**: F-00085
**Step**: S09 (Per-agent review of S08)
**Agent**: code-review-impl

---

## Inputs

- F-00085 Feature Design (ACs, Boundary table)
- S08 report + diff

## Output

- `ai-dev/active/F-00085/reports/F-00085_S09_CodeReview_report.md`

## Review Checklist

### Endpoint contracts

- [ ] All 7 endpoints present at the documented paths.
- [ ] GET endpoints are idempotent + side-effect-free.
- [ ] POST `/config` validates `phase ∈ {0, 1, null}` and rejects 2/3 with explicit "reserved for future CR" 400 (Inv 5).
- [ ] POST `/config` validates `runtime_option_id` is currently `enabled=True` — defence-in-depth re-check at API layer (AC14).
- [ ] POST `/verdict` validates `verdict ∈ {'pending','correct','wrong','partial'}` (CHECK constraint matches).
- [ ] POST `/verdict` validates target event is `merge_auto_resolved` (Boundary "Verdict on non-resolved event").
- [ ] POST `/verdict` enforces `len(notes) ≤ 8192 bytes` (Boundary "Verdict with very long notes").

### Audit event emission

- [ ] POST `/config` emits one `auto_merge_config_updated` event with `metadata.old` AND `metadata.new` (Inv 9).
- [ ] No event is emitted on a no-op POST (request body matches existing row exactly).
- [ ] `updated_by` is the literal sentinel `"dashboard"` (or `X-Operator` header if present).

### Diff viewer safety

- [ ] `subprocess.run(["git", "show", ...])` uses `timeout=10`, `check=False`, `cwd=<repo root>`.
- [ ] Wrapped in try/except → falls back to placeholder string; never raises to FastAPI.
- [ ] Non-zero returncode → `current_text=None` → placeholder "(file no longer exists on main)" (Boundary "File no longer on main").
- [ ] `difflib.HtmlDiff` used (not custom HTML generation).

### htmx integration

- [ ] Fragment endpoints return `HTMLResponse`.
- [ ] Verdict / config POSTs return either the re-rendered fragment OR JSON (based on `Accept` header).
- [ ] No mixing of full-page render with fragment render.

### Disabled-runtime defence in depth

- [ ] API rejects POST with a disabled-row id even though template (S10) won't show it.

### Empty / boundary states

- [ ] `?page=999999` returns empty fragment with "No more events" message (no 500) — Boundary table.
- [ ] Missing project_id in path → standard FastAPI 404 (auto-handled).
- [ ] Verdict notes default to `""` when omitted from request body.

### Out-of-scope guard

- [ ] No template files created (S10).
- [ ] No CSS changes (S10).
- [ ] No daemon-side code touched (S04/S06).

### Project conventions

- [ ] Router uses existing `Depends(get_db)`, `Depends(get_templates)` patterns.
- [ ] Matches `dashboard/routers/jobs_ui.py` for the page+fragment pattern.
- [ ] Registered in `dashboard/app.py`.

## Severity Mapping

- **CRITICAL** — disabled runtime accepted by API; phase=2 or 3 accepted; verdict on non-resolved event accepted; `git show` raises to FastAPI; SQL injection via `event_type` filter.
- **HIGH** — missing audit event on config write; verdict notes oversize accepted; fragment endpoint has side effects.
- **MEDIUM** — pagination boundary 500s; JSON-vs-HTML response selection wrong.
- **LOW** — style.

## Result Contract

Standard code-review JSON.
