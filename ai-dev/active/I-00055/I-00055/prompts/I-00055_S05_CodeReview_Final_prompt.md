# I-00055_S05_CodeReview_Final_prompt

**Work Item**: I-00055 -- Architecture Diagram renders twice on Code page; inline copy unreadable in dark mode
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S04

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state.
Read-only introspection (`docker ps`, `docker inspect`, `docker logs`) is allowed.
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Do not run `alembic upgrade/downgrade/stamp` against the live DB. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00055 --json`.
- `ai-dev/active/I-00055/I-00055_Issue_Design.md`
- All step reports: `ai-dev/active/I-00055/reports/I-00055_S0{1..4}_*_report.md`
- All files listed in those reports' `files_changed`

## Output Files

- `ai-dev/active/I-00055/reports/I-00055_S05_CodeReview_Final_report.md`

## Context

This is the global cross-step review for I-00055. Verify the mapgen change, the render-time strip helper, the dashboard wiring, and the test coverage **compose** into a complete fix. Per-agent reviews already covered each piece in isolation — your job is the integration view.

## Pre-Review Gate

```bash
make lint && make format && make typecheck
```

NEW violations on changed files → CRITICAL.

## Cross-Step Review Checklist

### 1. End-to-end fix coverage

Trace the bug fix arc:

- **Authoring path** (mapgen): new architecture-map content does not contain the diagram block.
- **Storage path**: the standalone `diagram-architecture` ProjectDoc is still being created and stored (mapgen `_finalise_arch_doc` / `store_arch_diagram` path untouched).
- **Render path**: `_render_architecture_html` strips legacy trailing diagram sections before mermaid pre-processing and markdown rendering.
- **Tests**: cover all three above. Reproduction test counts mermaid containers; mapgen unit test asserts no diagram fence; strip helper unit tests cover positive, idempotent, no-op, and non-trailing-H2 cases.

If any of these is missing, raise a finding.

### 2. Reproduction test correctness

The reproduction test in `tests/dashboard/` MUST:

- Seed an architecture-map ProjectDoc with the legacy-shape content (trailing `## Architecture Diagram` + mermaid fence).
- Seed a separate `diagram-architecture` ProjectDoc with a clean DSL.
- GET `/project/{id}/code` and assert exactly one mermaid container.

If the test would pass on `main` (pre-fix), it's not a real reproduction — flag CRITICAL.

### 3. Operational follow-up

Verify the design doc's "Operational Follow-up" section is intact and accurately describes the post-merge regen step. The fix itself does NOT trigger regen; the strip helper covers the gap. Confirm no part of S01..S04 silently regenerates docs (which would touch live DB unsafely).

### 4. No scope creep

Out-of-scope changes that should NOT appear:

- Components-cards layout / chip strip (Incident B's territory).
- Chat panel toggle UI changes (Incident C's territory).
- Mapgen prompt-length tuning (Incident B).
- Any change to `_clean_diagram_dsl` or the bottom-render template.

If you see any of the above, raise HIGH.

### 5. CLAUDE.md conformance

Sweep the diff for violations of project-wide rules in `CLAUDE.md`, `orch/CLAUDE.md`, `orch/rag/CLAUDE.md`, `dashboard/CLAUDE.md`, `tests/CLAUDE.md`. Most likely watch-points:

- No new direct DB connections from tests.
- No `docker compose up` commands anywhere.
- No alembic upgrade/downgrade calls.

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
make test-integration   # if green on main
```

Both must pass.

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| CRITICAL | Fix is incomplete; one of the three arms missing | Must fix |
| HIGH | Scope creep, architectural violation across steps | Must fix |
| MEDIUM (fixable) | Cross-cut convention violation | Should fix |
| MEDIUM (suggestion) | Optional improvement | Author decides |
| LOW | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "I-00055",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
