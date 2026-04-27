# CR-00023_S05_Backend_prompt

**Work Item**: CR-00023 — Make iw item-status the runtime source of truth for step list and per-step runtime info
**Step**: S05
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

(Same Docker rules as other steps — testcontainers only, no compose mutations.)

## ⛔ Migrations

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live orch DB.

## Input Files

- `ai-dev/active/CR-00023/CR-00023_CR_Design.md` — design (AC1)
- `ai-dev/active/CR-00023/reports/CR-00023_S03_Backend_report.md` — S03's wiring (DB columns now populated)
- `ai-dev/active/CR-00023/reports/CR-00023_S04_CodeReview_Backend_report.md` — S04 findings
- `orch/cli/item_commands.py:527-` — `item_status` command (the JSON serializer is at line ~612)
- `orch/db/models.py` — current `WorkflowStep` columns (after S01)

## Output Files

- `orch/cli/item_commands.py` — modified
- `ai-dev/active/CR-00023/reports/CR-00023_S05_Backend_report.md`

## Context

The DB now stores everything an agent could need (after S01+S03). This step
exposes those fields through `iw item-status --json` so agents stop reading the
manifest file. Per AC1, the per-step JSON entries must contain a true superset
of the manifest's per-step fields plus the runtime status.

## Requirements

### 1. Enrich the per-step JSON output

In `item_status` (around line 612-), the steps array currently emits:

```python
"steps": [
    {
        "step_id": s.step_id,
        "label": s.agent_label,           # NOTE: keep "label" for back-compat
        "type": s.step_type.value if s.step_type else None,
        "status": s.status.value if s.status else None,
    }
    for s in steps
]
```

Change to:

```python
"steps": [
    {
        "step_id": s.step_id,
        "step_number": s.step_number,
        "label": s.agent_label,                                  # back-compat alias
        "agent_label": s.agent_label,                            # new explicit name
        "opencode_agent": s.opencode_agent,
        "type": s.step_type.value if s.step_type else None,      # back-compat
        "step_type": s.step_type.value if s.step_type else None, # new explicit name
        "step_label": s.step_label,
        "status": s.status.value if s.status else None,
        "description": s.description,
        "prompt_file": s.prompt_file,
        "command": s.command,
        "gate": s.gate,
        "timeout_secs": s.timeout_secs,
    }
    for s in steps
]
```

Notes:

- Keep `label` and `type` keys present alongside the new `agent_label` and `step_type` for backwards-compatibility. The dashboard or other consumers may rely on the existing names. The "new explicit names" are the preferred forward-going keys per AC1.
- All values must be JSON-serialisable. NULL DB columns become `null` in JSON automatically (Python `None` → `json.dumps` → `null`). Do NOT coerce `None` to empty string.
- The order matters for readability: `step_id` and `step_number` first; identification fields next; status next; runtime/manifest superset fields last.

### 2. Update the JSON output for the top-level `current_step`

The existing `current_step` block (line ~571-577) only has 4 keys. Enrich it with the same fields the per-step entries now expose, so any consumer reading `current_step` gets the full picture without indexing into `steps`:

```python
current_step = {
    "step_id": s.step_id,
    "step_number": s.step_number,
    "label": s.agent_label,
    "agent_label": s.agent_label,
    "opencode_agent": s.opencode_agent,
    "step_type": s.step_type.value if s.step_type else None,
    "step_label": s.step_label,
    "status": s.status.value,
    "description": s.description,
    "prompt_file": s.prompt_file,
    "command": s.command,
    "gate": s.gate,
    "timeout_secs": s.timeout_secs,
    "duration": duration_str,
}
```

### 3. Hard Constraints

- Do NOT remove or rename any existing keys (`step_id`, `label`, `type`, `status`, `current_step`'s `duration`). Adding keys is safe (additive); removing breaks consumers.
- Do NOT touch the non-JSON code path. The CLI also has a human-readable output mode; that mode does not need the new fields surfaced verbatim — leaving it as-is is correct (one-line summary stays compact).
- Do NOT modify `orch/cli/item_commands.py:register` — that was S03's scope.

## Project Conventions

Read `orch/CLAUDE.md` for CLI module structure. The `iw item-status --json`
output is documented in `docs/IW_AI_Core_CLI_Spec.md` — update that doc too
if you can find the relevant section (look for "item-status"). If the doc
doesn't yet describe the `steps` JSON shape in detail, add a brief table
mentioning the 12 keys.

## TDD Requirement

S09 writes the formal coverage. Locally verify before reporting done:

```bash
uv run pytest tests/unit/ -k item_status -q   # existing tests must still pass (only new keys appended)
uv run mypy orch/cli/item_commands.py
make lint
```

End-to-end smoke (against live DB is fine here — it's a read-only operation):

```bash
uv run iw item-status I-00041 --json | python -m json.tool | head -40
```

You should see the new keys present in each `steps[]` entry. Pre-CR-00023 items will have `command`, `gate`, `timeout_secs` as `null`; the new CR-00023 item itself will have them populated.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "backend-impl",
  "work_item": "CR-00023",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/cli/item_commands.py",
    "docs/IW_AI_Core_CLI_Spec.md"
  ],
  "tests_passed": true,
  "test_summary": "existing item-status tests pass; mypy clean; manual smoke verified",
  "blockers": [],
  "notes": "Back-compat keys (label, type) retained; new explicit keys added (agent_label, step_type, …)."
}
```
