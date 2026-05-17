# CR-00058_S04_Template_prompt

**Work Item**: CR-00058 — Configurable per-project scope-overlap gate with block/allow policy
**Step**: S04
**Agent**: template-impl

---

## ⛔ Docker is off-limits

Standard policy. Doc edits only — no docker commands needed.

## ⛔ Migrations: agents generate, daemon applies

No migrations.

## Input Files

- `ai-dev/active/CR-00058/CR-00058_CR_Design.md`
- `docs/IW_AI_Core_Daemon_Design.md` — main doc you are extending
- `docs/IW_AI_Core_Architecture.md` — brief mention of the gate
- `.iw-orch.json` — this repo's project config; add an explicit `overlap_gate` block equivalent to the synthesized default
- `dashboard/templates/_partials/help/batches.html`, `_partials/help/queue.html`, `_partials/help/batch_detail.html` — operator-facing help copy
- `ai-dev/active/AUTO_MERGE_RESOLUTION.md`, `docs/research/R-00076-llm-automated-merge-resolution.md` — motivation context (cite, don't paraphrase at length)
- Runtime step state via `uv run iw item-status CR-00058 --json`

## Output Files

- `ai-dev/active/CR-00058/reports/CR-00058_S04_Template_report.md`
- Modified: `docs/IW_AI_Core_Daemon_Design.md`
- Modified: `docs/IW_AI_Core_Architecture.md`
- Modified: `.iw-orch.json`
- Modified: `dashboard/templates/_partials/help/batches.html`
- Modified: `dashboard/templates/_partials/help/queue.html`
- Modified: `dashboard/templates/_partials/help/batch_detail.html`

## Context

S01–S03 land the implementation. This step documents the new `overlap_gate` block, the decision tree, the new event type, and the dashboard pill — and ships an explicit default config in this repo's `.iw-orch.json` so operators have a working example checked in.

## Requirements

### 1. `docs/IW_AI_Core_Daemon_Design.md` — new "Cross-batch overlap gate (configurable)" subsection

Find the existing F-00076 / cross-batch gate section. Replace or extend it with:

- A short description of the gate's role (1 paragraph).
- The `.iw-orch.json` `overlap_gate` schema, including:
  - `block_on_overlap: list[glob]` — default `["**/*"]`. Empty list disables the gate entirely.
  - `allow_on_overlap: list[glob]` — default `["tests/**", "test/**", "__tests__/**", "**/*conftest*", "**/*.test.*", "**/*.spec.*"]`.
  - Allow-precedence semantics: applied **per conflicting glob** after the intersection step; a glob matched by any allow pattern is dropped; if the result is empty, the candidate launches.
- The decision tree (small Mermaid flowchart is fine if you keep it short):
  1. Compute overlapping globs via `find_blocking_items`.
  2. Filter overlapping globs against `allow_on_overlap`.
  3. If filtered list non-empty → hold, emit `item_held_for_scope` per blocking item.
  4. If empty AND default policy would have held → emit `item_overlap_allowed_by_policy` once, then launch.
  5. If empty AND default policy would also have allowed → launch silently (no extra event).
- The two `DaemonEvent` types and their `metadata` shape.
- SIGHUP reload semantics (operator edits `.iw-orch.json`, runs `./ai-core.sh daemon reload`, next poll uses the new policy; in-flight items unaffected).
- Operator guidance paragraph: "If you relax `overlap_gate` for a directory, consider enabling `scope_gate_enabled` to catch divergence at merge time. The two flags are independent today; they may be coupled in a future CR." Link to `ai-dev/active/AUTO_MERGE_RESOLUTION.md` as motivation for relaxing.

### 2. `docs/IW_AI_Core_Architecture.md`

In the existing daemon/batch overview, add one or two sentences pointing to the new section in `Daemon_Design.md`. Do not duplicate the full schema.

### 3. `.iw-orch.json` — add explicit default `overlap_gate` block

At the top level of this repo's `.iw-orch.json` (the one at the repo root), add the equivalent of the synthesized default in alphabetical-ish order near `scope_gate_enabled`-style flags:

```json
"overlap_gate": {
  "block_on_overlap": ["**/*"],
  "allow_on_overlap": [
    "tests/**",
    "test/**",
    "__tests__/**",
    "**/*conftest*",
    "**/*.test.*",
    "**/*.spec.*"
  ]
}
```

This produces zero behaviour change but documents the shape for operators. Do not add comments inside the JSON (JSON doesn't support them).

### 4. Dashboard help partials

In each of `dashboard/templates/_partials/help/batches.html`, `_partials/help/queue.html`, and `_partials/help/batch_detail.html`, add a single-line note describing the new info pill ("Items released by an allow-on-overlap rule show an info pill — see Daemon Design for policy details"). Link to the daemon-design doc anchor if the page already uses anchored links to docs; otherwise just plain text. Match the surrounding tone — these are short operator notes.

### 5. CLAUDE.md / orch CLAUDE.md

Do **not** modify these files. They're outside `scope.allowed_paths` for this CR. If you find yourself wanting to update them, note it under `notes` for the operator to handle separately.

## Project Conventions

- Markdown docs follow the existing voice: terse, definitional, no marketing copy.
- Mermaid diagrams are fine in `docs/`; keep them under ~20 nodes.
- Help partials are Jinja2 — use `%`-style `format` filter if needed (lint enforces this).
- JSON: no comments, no trailing commas.

## TDD Requirement

`n/a — doc/template/config edits only; no production logic.` Record this in `tdd_red_evidence`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format` (formatter passes over template edits as well)
2. `make typecheck` (no-op for docs but run anyway)
3. `make lint` (includes the Jinja2 template check)

## Test Verification (NON-NEGOTIABLE)

Validate JSON: `python -c "import json; json.load(open('.iw-orch.json'))"`. No test-suite execution needed for this step beyond preflight.

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "template-impl",
  "work_item": "CR-00058",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "docs/IW_AI_Core_Daemon_Design.md",
    "docs/IW_AI_Core_Architecture.md",
    ".iw-orch.json",
    "dashboard/templates/_partials/help/batches.html",
    "dashboard/templates/_partials/help/queue.html",
    "dashboard/templates/_partials/help/batch_detail.html"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "skipped — doc/template/config edits only",
  "tdd_red_evidence": "n/a — doc/template/config edits only; no production logic",
  "blockers": [],
  "notes": ""
}
```
