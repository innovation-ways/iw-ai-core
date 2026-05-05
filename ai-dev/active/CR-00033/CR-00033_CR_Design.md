# CR-00033: Document Tailwind CLI Fallback Strategy in Tech Stack Docs

**Type**: Change Request
**Priority**: Medium
**Reason**: Tech debt / operability — Tailwind CLI is unreliable in agent worktrees (incomplete `node_modules`) and `make css` is a no-op stub. The working fallback (append plain CSS directly to `dashboard/static/styles.css`) is undocumented, causing preventable fix-cycles. Surfaced by I-00067 self-assessment finding [3].
**Created**: 2026-05-05
**Status**: Draft

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

This CR is documentation-only. No migrations are added, modified, or required.
The standard agent-context migration restrictions still apply: do not run
`alembic upgrade/downgrade/stamp` against the live orchestration DB.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

---

## Description

The Tailwind CLI is unreliable inside agent worktrees: `node_modules` is sometimes
incomplete (e.g., `postcss-selector-parser` is missing) and the `make css` target
is declared in `.PHONY` but has no rule body, so invoking it silently does
nothing. The working fallback is to append plain CSS directly to
`dashboard/static/styles.css` (which is the deployed file). This CR documents the
fallback strategy in `docs/IW_AI_Core_Tech_Stack.md` so future agents and
operators can apply it without re-discovering it during a fix cycle.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules.
The Quick Navigation table points at `docs/IW_AI_Core_Tech_Stack.md` for
Technology choices. The Dashboard layer is described in `dashboard/CLAUDE.md`.

## Current Behavior

`docs/IW_AI_Core_Tech_Stack.md` §2.4 ("Dashboard") currently describes Tailwind
CSS in three places:

1. The stack table lists `Tailwind CSS (CDN) | 3.4+ | MIT` as the styling
   choice (line 88).
2. The "Why Tailwind CSS via CDN" prose (line 95) states: *"For production-feel
   without npm, a standalone Tailwind CLI binary can generate a static CSS
   file."* This sentence implies CLI compilation is a reliable production path,
   with no acknowledgement of failure modes.
3. The "Why not the current custom CSS" prose (line 99) frames Tailwind as the
   default styling foundation.

§10 Decisions Log (line 830) does not mention any decision about CSS authoring
when the CLI is unavailable.

What is **not** documented today:

- That `make css` is a `.PHONY` stub with no rule body (Makefile line 8 declares
  `css` in `.PHONY` only). Running `make css` prints `Nothing to be done for
  'css'`.
- That `dashboard/tailwind.config.js`, `dashboard/static/tailwind.src.css`, and
  `dashboard/static/styles.css` exist but the Tailwind CLI wired to them is
  unreliable when the agent worktree's `node_modules` is incomplete.
- That `dashboard/static/styles.css` is the file the dashboard actually serves,
  so plain CSS appended to it ships unchanged — Tailwind compilation is not
  required for the new rules to take effect.
- The decision rule for when to use the fallback vs. retry the CLI.

This gap caused the I-00067 fix cycle. Evidence:

- `.worktrees/I-00067/ai-dev/logs/I-00067_S01_run1.log:392-393` —
  `$ make css → make: Nothing to be done for 'css'`.
- `.worktrees/I-00067/ai-dev/logs/I-00067_S05_run1.log:256-258` — *"The
  `make css` target is declared in .PHONY but has no actual rule body"*.
- `.worktrees/I-00067/ai-dev/logs/I-00067_S05_fix1.log:28-50` — Tailwind CLI
  fails with `MODULE_NOT_FOUND` for `postcss-selector-parser`; fix cycle
  appends CSS directly to `styles.css`, 7 tests pass, lint passes.

## Desired Behavior

`docs/IW_AI_Core_Tech_Stack.md` explicitly documents the Tailwind CLI fallback
strategy so future fix-cycles do not re-discover it. After this CR, a reader
of the doc learns:

1. The CDN is the day-to-day styling vehicle (unchanged claim).
2. The local Tailwind CLI exists but may fail in worktrees due to incomplete
   `node_modules`, and `make css` is intentionally a stub today.
3. **Fallback rule**: when adding new styles, append plain CSS directly to
   `dashboard/static/styles.css`. The dashboard serves this file as-is — no
   compilation step is required for plain CSS rules to take effect.
4. The fallback is preferred over: editing `tailwind.src.css` and hoping for
   compilation, scaffolding new build tooling inside a fix-cycle, or installing
   missing npm packages from agent context.
5. The Decisions Log entry for "CSS framework" is updated to reference the
   fallback so the trade-off is captured alongside the original choice.

The doc continues to be self-consistent: §2.4 Dashboard, §6 Makefile, and §10
Decisions Log all agree on the fallback. No other doc claims compilation is
mandatory.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `docs/IW_AI_Core_Tech_Stack.md` §2.4 prose | Says CLI "can generate a static CSS file" without caveats | Adds an explicit "Tailwind CLI fallback strategy" subsection with failure modes, rule, and rationale |
| `docs/IW_AI_Core_Tech_Stack.md` §10 Decisions Log | "CSS framework" row mentions Tailwind only | Row updated (or new row added) to point at the fallback rule |

No code, schema, configuration, or runtime behavior is changed.

### Breaking Changes

- None. This is a documentation-only edit.

### Data Migration

- None. No data is touched.
- Reversibility: trivial — revert the commit.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Edit `docs/IW_AI_Core_Tech_Stack.md`: add fallback subsection under §2.4, update "Why Tailwind CSS via CDN" prose, update §10 Decisions Log row | — |
| S02 | code-review-impl | Per-agent review of S01: factual accuracy vs. Makefile + `dashboard/static/` layout + I-00067 evidence; tone matches surrounding doc; no broken Markdown | — |
| S03 | code-review-final-impl | Global review across S01 (single-impl CR) | — |
| S04 | qv-gate | Lint (`make lint`) — guards against accidental code edits | — |
| S05 | qv-gate | Format check (`make format-check`) | — |
| S06 | qv-gate | Type check (`make typecheck`) | — |
| S07 | qv-gate | Architecture (`make arch-check`) | — |
| S08 | qv-gate | Security SAST (`make security-sast`) | — |
| S09 | qv-gate | Unit tests (`make test-unit`) | — |
| S10 | qv-gate | Integration tests (`make test-integration`, timeout 900s) | — |
| S11 | self-assess-impl | Self-assessment of this item's execution history (last step per workflow invariant) | — |

No tests step: there is no testable runtime behavior to assert beyond the QV
gates, which already verify nothing else regressed.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None

### API Changes

- **New endpoints**: None
- **Modified endpoints**: None
- **Removed endpoints**: None

### Frontend Changes

- **New components**: None
- **Modified components**: None
- **Removed components**: None

## File Manifest

All files for this work item live under `ai-dev/active/CR-00033/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00033_CR_Design.md` | Design | This document |
| `CR-00033_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00033_S01_BackendImpl_prompt.md` | Prompt | S01 doc edit instructions |
| `prompts/CR-00033_S02_CodeReview_prompt.md` | Prompt | S02 per-agent review |
| `prompts/CR-00033_S03_CodeReview_Final_prompt.md` | Prompt | S03 final cross-agent review |
| `prompts/CR-00033_S11_SelfAssess_prompt.md` | Prompt | S11 self-assessment (last step) |

QV gate steps S04–S10 (`qv-gate` agent) execute Makefile targets directly via the manifest's `command` field and require no per-step prompt file (per the orchestrator contract).

Reports are created during execution under `ai-dev/active/CR-00033/reports/`.

## Acceptance Criteria

### AC1: Fallback subsection exists with required content

```
Given a reader of docs/IW_AI_Core_Tech_Stack.md
When they read §2.4 Dashboard
Then they find a subsection titled exactly "Tailwind CLI fallback strategy"
  AND it states that the Tailwind CLI may fail in agent worktrees due to
      incomplete node_modules
  AND it states that `make css` is a .PHONY stub with no rule body today
  AND it states the rule: "append plain CSS directly to
      dashboard/static/styles.css"
  AND it explains that dashboard/static/styles.css is served as-is, so plain
      CSS rules take effect without a Tailwind compilation step
```

### AC2: "Why Tailwind CSS via CDN" prose no longer implies CLI is reliable

```
Given the existing prose at line ~95 of docs/IW_AI_Core_Tech_Stack.md
When the CR is applied
Then the sentence claiming the CLI "can generate a static CSS file" is either
     removed or qualified to point at the new fallback subsection
  AND no other sentence in §2.4 claims CLI compilation is the production path
```

### AC3: Decisions Log entry references the fallback

```
Given §10 Decisions Log
When the CR is applied
Then the row referencing the CSS framework choice (currently "D3") either
     mentions the fallback rule directly OR a new row immediately after
     references "Tailwind CLI fallback" with a one-line rationale
```

### AC4: Doc remains internally consistent

```
Given the full file docs/IW_AI_Core_Tech_Stack.md after the edit
When a reader cross-references §2.4 Dashboard, §6 Makefile, and §10 Decisions Log
Then no two sections contradict each other about whether CLI compilation is
     required
  AND no claim is made that `make css` produces output today
```

### AC5: No code or non-doc changes

```
Given the diff produced by this CR
When inspected at merge time
Then exactly one file is modified: docs/IW_AI_Core_Tech_Stack.md
  AND no Python, JavaScript, CSS, Makefile, or configuration files are touched
```

## Rollback Plan

- **Database**: Not applicable.
- **Code**: Revert the merge commit. The change is purely additive prose; reverting
  restores the prior text exactly.
- **Data**: No data loss possible — no data is touched.

## Dependencies

- **Depends on**: None.
- **Blocks**: None. (A separate, future change to give `make css` a real rule body
  or to remove it from `.PHONY` would naturally update the same subsection, but
  that work is out of scope here.)

## Impacted Paths

- `docs/IW_AI_Core_Tech_Stack.md`
- `ai-dev/active/CR-00033/**`

## TDD Approach

- Unit tests: None — documentation-only change, no runtime behavior to assert.
- Integration tests: None — same reason.
- Updated tests: None.
- QV gates (lint/format/unit/integration) run as a safety net to prove no other
  file changed.

## Notes

- I-00067 self-assessment finding [3] suggested either `docs/IW_AI_Core_Tech_Stack.md`
  *or* `orch/daemon/worktree_compose.py` as the documentation target. Per
  user direction, this CR scopes to the Tech Stack doc.
- A separate, related improvement — adding a `CLAUDE.md` Critical Rule to
  surface the same fallback rule to agents at prompt time — is intentionally
  **not** in scope for this CR. It can be filed as a follow-up CR if desired.
- The fallback rule is a documentation of an existing operational pattern, not
  a new architectural decision. The Tailwind CDN remains the primary styling
  vehicle for runtime; the fallback only affects how new rules are authored
  inside agent worktrees.
