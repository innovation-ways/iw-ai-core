# CR-00057_S08_CodeReview_Final_prompt

**Work Item**: CR-00057 — AI Assistant chat model allowlist (per-project, with Ollama provider)
**Step**: S08
**Agent**: code-review-final-impl

---

## Standard Policy Headers

Standard `⛔ Docker is off-limits` and `⛔ Migrations: agents generate, daemon applies` policies apply.

## Input Files

- `ai-dev/active/CR-00057/CR-00057_CR_Design.md`
- All per-step reports under `ai-dev/active/CR-00057/reports/`
- All implementation files declared in `workflow-manifest.json` under `scope.allowed_paths`
- `ai-dev/active/CR-00057/reports/CR-00057_S07_CodeReview_FIX_report.md`

## Output Files

- `ai-dev/active/CR-00057/reports/CR-00057_S08_CodeReview_Final_report.md`

## Review Focus

Cross-agent / cross-layer concerns that a per-agent review can't see:

1. **End-to-end allowlist round-trip.** Walk a single allowlist entry (e.g. `ollama/gemma4:26b`) from `projects.toml` → `project_registry` → `Project.config["ai_assistant"]` → `dashboard/routers/chat.py::get_config` → JSON response → `chat.js` dropdown. Are the labels and the wire format consistent at every hop?
2. **Fail-open paths.** Confirm the four fail-open branches (no project_id, unknown project, no ai_assistant key, empty intersection) all behave consistently — same response shape, same status code, same log level discipline. A mismatch (e.g. one branch logs WARNING while the others log INFO) is a HIGH finding.
3. **Cache TTL semantics.** Verify the project-keyed cache plays well with the operator workflow described in AC2 (SIGHUP + 30 s TTL → new list visible). If a stale cache could outlive a SIGHUP, flag it.
4. **Doc / code consistency.** The new doc page `docs/IW_AI_Core_AI_Assistant_Models.md` (S05) describes operator-facing behavior. Confirm every claim it makes is true of the code as-built — especially the "label honesty" paragraph and the example opencode JSON shape.
5. **Scope discipline.** The `scope.allowed_paths` in the manifest should match the actual changed file set. Any file edited outside that set is a CRITICAL finding (will block merge).
6. **No regression in the test suite shape.** S04 added integration tests; confirm they actually use a testcontainer (not a mocked Session). Confirm the new tests don't accidentally import or call against the live DB on 5433.

## Subagent Result Contract

Use the standard code-review-final-impl JSON contract.
