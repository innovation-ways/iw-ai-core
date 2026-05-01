# I-00055_S01_Backend_prompt

**Work Item**: I-00055 -- Architecture Diagram renders twice on Code page; inline copy unreadable in dark mode
**Step**: S01
**Agent**: Backend

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run the following alembic commands against the live
orchestration DB (port 5433) from an agent context:

  alembic upgrade head
  alembic upgrade <revision>
  alembic downgrade <anything>
  alembic stamp <anything>

Your job in a Database step is to WRITE the migration FILE. The daemon
will apply it as part of the merge pipeline (pre-merge dry-run against
a testcontainer, post-merge apply to live DB). If the migration is
broken, the daemon will refuse to merge the batch.

Allowed for agents:
  - alembic revision --autogenerate -m "..."   (writes a file only)
  - alembic history / current / show           (read-only)
  - Running migrations inside testcontainer fixtures
    (tests/conftest.py does this — agents don't call it directly)

Allowed for OPERATORS only (not agents):
  - uv run iw migrations list-pending          (read-only, safe for anyone)
  - uv run iw migrations dry-run               (testcontainer, safe)
  - uv run iw migrations apply --i-am-operator (refuses if IW_CORE_AGENT_CONTEXT=true)
  - Direct invocation via ./ai-core.sh or make db-migrate (operator entry points)

If your task seems to require applying a migration to the live DB,
STOP and raise a blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — for the current step list, status, prompt paths, gate commands, etc., prefer `uv run iw item-status I-00055 --json`. The `workflow-manifest.json` file is a design-time snapshot and may be out of date (CR-00023).
- `ai-dev/active/I-00055/I-00055_Issue_Design.md` -- Design document (read first)
- `orch/rag/mapgen.py` -- mapgen content writer (root cause #1)
- `dashboard/routers/code_ui.py` -- render path (root cause #2 surface; render-time guard goes here)
- `dashboard/templates/fragments/code_architecture_view.html` -- already loads both docs; no change required here
- `dashboard/templates/fragments/code_architecture_diagram.html` -- the canonical bottom render (no change required)

## Output Files

- `ai-dev/active/I-00055/reports/I-00055_S01_Backend_report.md` -- Step report

## Context

You are fixing **I-00055** — the Code Understanding page renders the architecture mermaid diagram twice, and the inline copy is unreadable in dark mode because its YAML frontmatter overrides the dashboard's mermaid theme.

Read the design document first. Then read `CLAUDE.md` and the relevant sub-CLAUDE files (`orch/CLAUDE.md`, `orch/rag/CLAUDE.md`, `dashboard/CLAUDE.md`).

## Requirements

### 1. Stop emitting the diagram block from the architecture-map markdown

In `orch/rag/mapgen.py`, modify `MapGenerator._assemble_markdown()` so it no longer appends:

- the `## Architecture Diagram` H2,
- the `<!-- purpose: ... -->` HTML comment,
- the surrounding blank lines,
- the ` ```mermaid ... ``` ` fenced block.

The standalone `diagram-architecture` ProjectDoc (already created elsewhere in this module) is the canonical home for the diagram; the architecture-map content must be prose only.

The function signature must remain unchanged so existing callers continue to work, but the `mermaid` and `purpose` parameters become unused inside this function. **Do NOT** delete those parameters or rename them. Other code in `mapgen.py` still needs `mermaid` and `purpose` to feed the standalone diagram-architecture doc — only the markdown body changes.

### 2. Add a defensive strip helper for legacy content

Some `architecture-map` ProjectDocs already on disk were written with the old `_assemble_markdown` and contain the trailing `## Architecture Diagram` section. Until those rows are regenerated, the dashboard would still render the duplicate. Add a small helper that strips the trailing section at render time.

Write it in `orch/rag/mapgen.py` (so it lives next to the writer it complements):

```python
def strip_trailing_arch_diagram_section(content: str) -> str:
    """Remove a trailing '## Architecture Diagram' section from a stored
    architecture-map markdown, including everything from that H2 to the end
    of the document. Idempotent (no-op if the section is absent).

    Conservative on purpose:
    - Only matches an H2 (exactly two '#') named 'Architecture Diagram'.
    - Only strips when the section is the LAST H2 in the document.
    - Returns the input unchanged if the regex does not match.
    """
```

Implementation notes:
- Use a single regex anchored at end-of-string: roughly `r"\n##\s+Architecture Diagram\b.*\Z"` with `re.DOTALL`. Strip trailing whitespace.
- Idempotent — calling it twice on the same input returns the same value.
- Do NOT touch any other heading (H1, H3+) and do NOT touch a non-trailing H2 of the same name (defensive against future content authoring patterns).

### 3. Apply the strip helper at render time

In `dashboard/routers/code_ui.py`, in `_render_architecture_html(arch_doc)` at line 81, call the helper before passing the content to `_preprocess_mermaid` and `render_markdown`. Import from `orch.rag.mapgen`.

```python
def _render_architecture_html(arch_doc: Any) -> str | None:
    if arch_doc is None or not arch_doc.content:
        return None
    cleaned = strip_trailing_arch_diagram_section(arch_doc.content)
    processed = _preprocess_mermaid(cleaned)
    return render_markdown(processed)
```

This is a render-time guard. It must NOT mutate the stored doc; just operate on the in-memory copy each request.

### 4. No other changes

Do NOT touch:
- `dashboard/templates/fragments/code_architecture_view.html` — its layout is the right shape.
- `dashboard/templates/fragments/code_architecture_diagram.html` — that is the canonical render.
- `_clean_diagram_dsl` — already correct.
- `code_ui.code_architecture()` (the htmx fragment endpoint) other than what's required to import the helper consistently. Apply the same strip there if and only if it also calls `_render_architecture_html` — currently it does, so it inherits the fix automatically.

### 5. Do not regenerate stored docs from this step

The operational follow-up (queue regen-map for every project) is OUT OF SCOPE for this step. The strip helper is enough to make the page render correctly during the gap between merge and the next regen run.

## Project Conventions

Read the project's `CLAUDE.md` for:

- Architecture patterns and layer boundaries (orch/ vs dashboard/)
- Coding conventions and naming rules
- Test organization and fixtures (`tests/CLAUDE.md`)
- Build and run commands

Follow all rules defined there exactly. When in doubt, match existing code in the repository.

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED**: Run the failing test the Tests step (S03) will own. The unit-level expectation is that `_assemble_markdown` output contains no `## Architecture Diagram`. Write a quick local assertion in a scratch invocation if helpful — but don't add new test files; that's S03's job. Confirm the current behaviour fails the assertion.
2. **GREEN**: Apply the change in `mapgen.py` and re-confirm the assertion passes.
3. **REFACTOR**: Tidy the helper, add a docstring; keep the existing call sites of `_assemble_markdown` unchanged.

Do not skip the RED phase.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, you MUST run these in order
and fix any issues they report.

1. **`make format`** — auto-fixes formatting drift. If it reformats files, inspect the diff and re-stage; do NOT skip.
2. **`make typecheck`** — must report zero errors involving the files you touched. Errors elsewhere are pre-existing — note them in your report but do not ignore your own.
3. **`make lint`** — must report zero errors.

If a tool isn't available in your worktree, STOP and raise a blocker — do not silently skip.

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. `make test-unit` — must pass.
2. `make lint && make typecheck` — must pass.
3. Do NOT report `tests_passed: true` unless ALL unit tests pass with zero failures.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "Backend",
  "work_item": "I-00055",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/rag/mapgen.py",
    "dashboard/routers/code_ui.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
