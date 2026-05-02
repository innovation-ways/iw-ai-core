# I-00055_S02_CodeReview_Backend_prompt

**Work Item**: I-00055 -- Architecture Diagram renders twice on Code page; inline copy unreadable in dark mode
**Step Being Reviewed**: S01 (Backend)
**Review Step**: S02

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
- `ai-dev/active/I-00055/reports/I-00055_S01_Backend_report.md`
- All files listed in S01's `files_changed` (typically `orch/rag/mapgen.py`, `dashboard/routers/code_ui.py`)

## Output Files

- `ai-dev/active/I-00055/reports/I-00055_S02_CodeReview_report.md`

## Context

Review the Backend implementation at S01. The fix has two parts:
1. Stop emitting the trailing `## Architecture Diagram` section in `MapGenerator._assemble_markdown`.
2. Add a `strip_trailing_arch_diagram_section` helper and apply it in `_render_architecture_html` so legacy stored docs render only one diagram on the Code page.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run on the files listed in S01's `files_changed`:

```bash
make lint
make format
```

Any NEW violation that wasn't on `main` for those files → CRITICAL finding (`category: conventions`, with `file`, `line`, exact code/message).

## Review Checklist

### 1. Mapgen content fix

- `_assemble_markdown` no longer emits `## Architecture Diagram`, the `<!-- purpose: -->` HTML comment, or any ` ```mermaid ` fence.
- Function signature unchanged. The `mermaid` and `purpose` parameters may now be unused locally — verify other call sites in `mapgen.py` still rely on them being passed in (they do, for the standalone diagram-architecture doc).
- No accidental change to the `_GROUNDING_TEMPLATE`, `QUESTIONS`, or other shared structure.

### 2. Strip helper correctness

- Helper lives in `orch/rag/mapgen.py` and is exported (no leading underscore) so it can be imported from the dashboard router.
- Regex anchors to end of string (`\Z`) and matches only **trailing** `## Architecture Diagram`. Confirm a non-trailing same-named H2 is NOT stripped.
- Helper is **idempotent**: calling it twice yields the same string.
- Helper is a pure function (no I/O, no DB access, no logging side effects).
- Returns the input unchanged when there is no match.
- Pattern is conservative: exactly two `#` (H2) followed by a single space, then `Architecture Diagram` as a word boundary. H1/H3 of the same name should NOT match.

### 3. Render-time wiring

- `dashboard/routers/code_ui.py:_render_architecture_html` calls the helper before `_preprocess_mermaid` and `render_markdown`.
- Import comes from `orch.rag.mapgen` — no circular import risk (orch/rag → ok).
- The stored ProjectDoc is NOT mutated; the helper operates on the in-memory string.
- The other render path (`/api/code/architecture` fragment endpoint) inherits the fix because it shares `_render_architecture_html`.

### 4. Code Quality, Conventions, Security, Testing

Cross-check against root `CLAUDE.md`, `orch/CLAUDE.md`, `orch/rag/CLAUDE.md`, `dashboard/CLAUDE.md`. No hardcoded strings, no new I/O, no security surface.

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
```

Report results accurately. Do not invent green numbers.

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| CRITICAL | Breaks functionality / data risk | Must fix before merge |
| HIGH | Significant bug / architectural violation | Must fix before merge |
| MEDIUM (fixable) | Code quality / convention | Should fix in fix cycle |
| MEDIUM (suggestion) | Optional improvement | Author decides |
| LOW | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00055",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

`verdict = pass` requires zero CRITICAL/HIGH and zero MEDIUM (fixable). Otherwise `fail`.
