# CR-00006 S11 — Quality Validation + Browser Verification

## Input Files

- All source files changed by CR-00006
- `CLAUDE.md` — Playwright CLI usage rules (headless, use `playwright-cli` only, never `npx playwright install`)
- `ai-dev/active/CR-00006/CR-00006_CR_Design.md`

## Output Files

- `ai-dev/work/CR-00006/reports/S11_qv_results.md` — gate pass/fail results
- Screenshots captured via `playwright-cli` stored in `ai-dev/work/CR-00006/reports/screenshots/`

## Context

**Work item**: CR-00006
**Step**: S11
**Agent**: quality-validation-impl

Run automated QV gates AND manual browser verification of the three user-visible changes.

## Gates

Run each gate and record PASS/FAIL with the actual output (trimmed). ALL gates must PASS before signaling done.

### Gate 1: Ruff lint

```bash
uv run ruff check .
```

### Gate 2: Ruff format check

```bash
uv run ruff format --check .
```

### Gate 3: mypy type check

```bash
uv run mypy orch/ dashboard/
```

### Gate 4: Unit tests

```bash
make test-unit
```

### Gate 5: Integration tests

```bash
make test-integration
```

### Gate 6: Route registration smoke-test

```bash
uv run python -c "from dashboard.app import create_app; app = create_app(); paths = sorted([r.path for r in app.routes if 'jobs' in r.path]); [print(p) for p in paths]"
```

Expected output (exact):

```
/project/{project_id}/jobs
/project/{project_id}/jobs/fragment/table
/project/{project_id}/jobs/{job_type}/{job_id}
```

### Gate 7: Event-type consistency grep

```bash
grep -rn "code_map_completed" orch/ dashboard/ | wc -l
```

Expected: at least 3 lines (insert site + `_TOAST_EVENTS` + `_TOAST_SEVERITY`).

### Gate 8: Old green-banner content is gone

```bash
grep -rn "Code map generated successfully" dashboard/templates/
```

Expected: **no matches**.

```bash
grep -rn "bg-green-50" dashboard/templates/fragments/code_job_report.html
```

Expected: **no matches**.

### Gate 9: Browser verification — prep

The daemon/dashboard must be running. Start them manually or confirm they are up:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:9900/
```

Expected: `200` (or `307` redirect — both fine). If not, run `make dashboard-start` in the background first.

Pick a `project_id` with an existing code index:

```bash
uv run python -c "from orch.db.session import SessionLocal; from orch.db.models import Project; from sqlalchemy import select; s = SessionLocal(); ps = s.scalars(select(Project)).all(); [print(p.id) for p in ps]; s.close()"
```

Store the first project id as `PROJECT_ID`.

### Gate 10: Browser verification — sidebar has Jobs link

```bash
playwright-cli kill-all
playwright-cli open "http://localhost:9900/project/$PROJECT_ID/"
playwright-cli snapshot > /tmp/sidebar-snapshot.txt
grep -i "Jobs" /tmp/sidebar-snapshot.txt
playwright-cli screenshot
# Save the screenshot file path
```

Expected: snapshot contains "Jobs" link; screenshot shows sidebar with Jobs between History and Tests.

### Gate 11: Browser verification — Jobs list page

```bash
playwright-cli open "http://localhost:9900/project/$PROJECT_ID/jobs"
playwright-cli snapshot > /tmp/jobs-page.txt
playwright-cli screenshot
```

Expected: page renders with "Jobs" heading, filters visible, table visible (may be empty if no async ops yet — that's OK for verification).

### Gate 12: Browser verification — Code page, no green banner, neutral Last-Run summary if a job exists

```bash
playwright-cli open "http://localhost:9900/project/$PROJECT_ID/code"
playwright-cli snapshot > /tmp/code-page.txt
playwright-cli screenshot
grep -i "code map generated successfully" /tmp/code-page.txt && echo "FAIL: banner text still present" || echo "OK: banner text absent"
```

Expected: "code map generated successfully" is absent. If a recent completed job exists, a neutral "Last run … View →" line is visible; otherwise nothing appears in that slot.

### Gate 13: Browser verification — Q&A streaming

Requires a code index AND running Ollama. If either is missing, SKIP with note.

```bash
# Trigger a question via the browser UI
playwright-cli open "http://localhost:9900/project/$PROJECT_ID/code"
playwright-cli fill "#qa-input" "Explain the overall architecture in 5 sentences."
playwright-cli click "#qa-submit-btn"
# Sleep a short moment to let tokens begin arriving (but not to let the full response finish)
sleep 1.5
playwright-cli snapshot > /tmp/qa-mid.txt
# The assistant bubble should already contain text — proves streaming
grep -A2 "Assistant" /tmp/qa-mid.txt | head -10
# Wait for the response to finish
sleep 20
playwright-cli snapshot > /tmp/qa-done.txt
# Capture screenshot
playwright-cli screenshot
```

Expected:
- `/tmp/qa-mid.txt` shows partial text in the assistant bubble.
- `/tmp/qa-done.txt` shows fully rendered markdown (headings, lists, inline/block code if the model produced them) — not raw markdown characters.

### Gate 14: Browser verification — markdown XSS sanitization

Manual: create a mock assistant response by temporarily monkeypatching or by selecting a model prompt likely to echo markdown. Since this is intrusive, the acceptable alternative is the template-grep test from S07 (already covered by Gate 4/5). Record as PASS-BY-TEST if the relevant unit test (`test_qa_markdown_sanitize.py`) passed in Gate 4.

### Gate 15: Browser verification — Jobs detail navigation

If a completed code mapping job exists for the project:

```bash
# Find a job id
JOB_ID=$(uv run python -c "from orch.db.session import SessionLocal; from orch.db.models import CodeIndexJob; from sqlalchemy import select; s = SessionLocal(); j = s.scalars(select(CodeIndexJob).where(CodeIndexJob.project_id == '$PROJECT_ID').order_by(CodeIndexJob.triggered_at.desc()).limit(1)).first(); print(j.id if j else ''); s.close()")

if [ -n "$JOB_ID" ]; then
  playwright-cli open "http://localhost:9900/project/$PROJECT_ID/jobs/code_mapping/$JOB_ID"
  playwright-cli snapshot > /tmp/job-detail.txt
  playwright-cli screenshot
  grep -i "llm_model\|files_indexed\|chunks_created" /tmp/job-detail.txt
fi
```

Expected: detail page shows type-specific fields.

## Report format

Write `ai-dev/work/CR-00006/reports/S11_qv_results.md`:

```markdown
# CR-00006 S11 Quality Validation Results

| Gate | Result | Notes |
|------|--------|-------|
| 1 Ruff lint | PASS | |
| 2 Ruff format | PASS | |
| 3 mypy | PASS | |
| 4 Unit tests | PASS | N tests, M assertions |
| 5 Integration tests | PASS | |
| 6 Route registration | PASS | |
| 7 Event-type consistency | PASS | 3 matches |
| 8 Old banner content gone | PASS | 0 matches |
| 9 Dashboard reachable | PASS | HTTP 200 |
| 10 Sidebar Jobs link | PASS | Screenshot saved to screenshots/sidebar.png |
| 11 Jobs list page | PASS | Screenshot saved |
| 12 Code page — no green banner | PASS | |
| 13 Q&A streaming | PASS | Tokens visible mid-stream; markdown rendered on completion |
| 14 Markdown sanitization | PASS-BY-TEST | Covered by test_qa_markdown_sanitize.py |
| 15 Jobs detail navigation | PASS | |

## Screenshots

- screenshots/sidebar.png
- screenshots/jobs-list.png
- screenshots/code-page.png
- screenshots/qa-mid-stream.png
- screenshots/qa-done.png
- screenshots/job-detail.png
```

## Signal completion

If ALL gates PASS:

```bash
iw step-done CR-00006 S11 --summary "All 15 QV gates passed. Lint/format/mypy clean, unit + integration tests pass, routes registered correctly, event-type consistency verified, old green banner removed, Q&A streams tokens live, markdown renders sanitized, Jobs navigation works end-to-end."
```

If ANY gate fails:

```bash
iw step-fail CR-00006 S11 --reason "Gate <N> failed: <trimmed error output>"
```
