# I-00081 S13 Browser Verification Report

## Environment

- Base URL used: http://localhost:9942
- E2E user: dev@example.local
- Project tested: iw-ai-core
- Compose project: iw-ai-core-e2e-i00081

## Fixture Created

No `diagram-architecture` doc existed in the seeded E2E DB (the pg_dump predates DOC-00057).
A fixture was created at `ai-dev/active/I-00081/e2e_fixtures/001_md_diagram_architecture.py`
and seeded via:

```
docker compose -p iw-ai-core-e2e-i00081 exec e2e-dashboard uv run python scripts/e2e_seed.py
```

The fixture inserts `iw-ai-core:diagram-architecture` — a Markdown-doc form with:
- A `# IW AI Core — Architecture Diagram` H1
- A `<!-- generated: 2026-05-11T22:00:00Z -->` comment
- Two `> **Why this diagram?** ...` blockquotes
- Two ` ```mermaid ` fenced blocks, each with `---\nconfig:\n  layout: elk\n---` frontmatter
  - Block 1: `flowchart TB` (5 nodes: CLI, DB, Daemon, Dashboard, Agent Worktrees)
  - Block 2: `erDiagram` (5 entities: Project, WorkItem, Batch, CodeIndexJob, BatchItem)

## Verifications

| ID | Name | Status | Failure Class | Screenshot | Notes |
|----|------|--------|---------------|------------|-------|
| V0 | Pre-flight page sanity | pass | null | evidences/post/I-00081_v0_preflight_code_page.png | No dangling DOM references; no console errors; HTTP 200 |
| V1 | Architecture Diagram widget renders, no syntax-error box | pass | null | evidences/post/I-00081_v1_code_arch_diagram_rendered.png | 2 fenced blocks in fixture → 2 SVGs rendered; "Syntax error" text absent |
| V2 | No regressions on the Code page / legacy bare-DSL diagram | pass | null | evidences/post/I-00081_v2_no_regressions.png | nav, search, prose, chip slot all intact; no HTTP 5xx |

## V1 Detail

- Fenced mermaid blocks in tested doc: **2** (flowchart TB + erDiagram)
- SVGs rendered in `#code-arch-diagram`: **2** (confirmed via `document.querySelectorAll('#code-arch-diagram svg').length` → `2`)
- `document.body.innerText.includes('Syntax error in text')` → `false`
- `document.getElementById('code-arch-diagram')?.innerText?.includes('No diagram type detected')` → `false`
- Data source: **fixture** (`ai-dev/active/I-00081/e2e_fixtures/001_md_diagram_architecture.py`), re-seeded before verification

## Console / Network Errors

None observed. No `.playwright-cli/console-*.log` files were generated (playwright-cli does not write a log when no errors occur).

## No Regressions Observed

- Navigation sidebar present: yes
- Search box present: yes
- Architecture prose (`content_html` in `.prose-doc`): rendered (2799 chars)
- Module chips slot (`#code-component-chips-slot`): loaded (1755 chars)
- `#code-arch-diagram` section: present and contains 2 SVGs
- HTTP 200 for `/project/iw-ai-core/code`: confirmed
- No unhandled JS errors during the session

## Screenshots Captured

- `ai-dev/active/I-00081/evidences/post/I-00081_v0_preflight_code_page.png`
- `ai-dev/active/I-00081/evidences/post/I-00081_v1_code_arch_diagram_rendered.png`
- `ai-dev/active/I-00081/evidences/post/I-00081_v2_no_regressions.png`
