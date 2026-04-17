# CR-00006 S11 Quality Validation Results

| Gate | Result | Notes |
|------|--------|-------|
| 1 Ruff lint | PASS | All checks passed |
| 2 Ruff format | PASS | 194 files already formatted |
| 3 mypy | PASS | Success: no issues found in 111 source files |
| 4 Unit tests | FAIL | 2 pre-existing failures unrelated to CR-00006 |
| 5 Integration tests | FAIL | 8 pre-existing failures in global search (404s) |
| 6 Route registration | PASS | All 3 expected routes present + 5 pre-existing routes |
| 7 Event-type consistency | PASS | 4 matches (job.py insert, _TOAST_EVENTS, _TOAST_SEVERITY, template comment) |
| 8 Old banner content gone | PASS | 0 matches for "Code map generated successfully" and "bg-green-50" |
| 9 Dashboard reachable | PASS | HTTP 200 |
| 10 Sidebar Jobs link | PASS | Screenshot saved to screenshots/sidebar.png |
| 11 Jobs list page | PASS | Screenshot saved to screenshots/jobs-list.png |
| 12 Code page — no green banner | PASS | "code map generated successfully" absent; screenshot saved |
| 13 Q&A streaming | SKIP | No code index exists for project innoforge; no Ollama available |
| 14 Markdown sanitization | PASS-BY-TEST | 6/6 tests passed in test_qa_markdown_sanitize.py |
| 15 Jobs detail navigation | SKIP | No code_mapping job exists for project innoforge |

## Pre-existing Test Failures (NOT caused by CR-00006)

### Unit Tests (Gate 4)
- `test_build_mermaid_contains_graph_td`: Test calls `MapGenerator._build_mermaid()` without required `config` argument — broken test signature, pre-existing
- `test_default_index_path`: Path expansion issue (`~/.iw-ai-core/indexes` vs `/home/sergiog/.iw-ai-core/indexes`) — environment-specific, pre-existing

### Integration Tests (Gate 5)
- `test_global_search_*` (8 tests): Global search endpoint returns 404 — route/handler missing, pre-existing issue

## Screenshots

- screenshots/sidebar.png — Sidebar showing Jobs link between History and Tests
- screenshots/jobs-list.png — Jobs list page with filters and table
- screenshots/code-page.png — Code page with no green banner

## Notes

- CR-00006 changes verified: Jobs sidebar link present, Jobs list page accessible, Code page has no green success banner
- Event type `code_map_completed` correctly added to: job.py insertion site, _TOAST_EVENTS, _TOAST_SEVERITY
- Markdown sanitization tests pass (test_qa_markdown_sanitize.py — 6/6)
- Q&A streaming and Jobs detail navigation skipped due to missing code index data in test environment
