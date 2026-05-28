# CR-00092_S03_Database_prompt

**Work Item**: CR-00092 -- Column-docs baseline scrub (wave 3: OSS / chat / runtime)
**Step**: S03
**Agent**: database-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY docker commands that change container/volume/network state. Testcontainers from pytest fixtures and read-only introspection are the only exceptions. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This step adds NO migration. Do NOT run alembic. Do NOT touch `orch/db/migrations/versions/**`.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00092 --json`.
- `ai-dev/active/CR-00092/CR-00092_CR_Design.md` — Design document.
- `ai-dev/work/CR-00092/reports/CR-00092_S01_Database_report.md` and `CR-00092_S02_Database_report.md` — prior wave reports.
- `orch/db/column_docs_baseline.txt` — baseline (already shrunk by S01 + S02).
- `docs/IW_AI_Core_Database_Schema.md` — primary source for column descriptions.
- `orch/db/models.py` — the file you will edit.

## Output Files

- `ai-dev/work/CR-00092/reports/CR-00092_S03_Database_report.md`.
- Edits in `orch/db/models.py`.

## Context

You are implementing **wave 3 of 4**. Wave 3 owns the ten OSS / chat / runtime classes:

| Class | Entries in baseline |
|-------|---------------------|
| `OssFinding` (line 2162) | 15 |
| `DocIndexJob` (line 2049) | 15 |
| `ProjectOssJob` (line 2271) | 13 |
| `PendingMigrationLog` (line 1576) | 13 |
| `FixCycle` (line 1018) | 12 |
| `OssScan` (line 2118) | 11 |
| `ChatTab` (line 2745) | 11 |
| `ChatSummarizationJob` (line 2659) | 11 |
| `ChatConversation` (line 2521) | 11 |
| `AgentRuntimeOption` (line 56) | 11 |
| **Total** | **123** |

Wave 4 (S04) handles the remaining 21 small classes AND removes the baseline file AND flips the gate. DO NOT do those in this step.

## Requirements

### 1. Read S01/S02 reports and the design

Confirm both prior waves reported `completion_status: complete` and the expected `wave_scrub_count` (103 for S01, 90 for S02; cumulative 193). If either is partial / blocked, STOP and raise a blocker.

Re-read the design's **Notes → Description sourcing rule**.

### 2. Scrub all 123 columns in `orch/db/models.py`

Same rules as S01/S02. Wave-3 class-specific notes:

- **OssScan / OssFinding / OssFindingDetail / OssToolRun** model the per-project OSS-compliance scan pipeline (driven by the `iw-oss-publish` skill). `severity` is an SAEnum (`OssFindingSeverity`); `status` is `OssFindingStatus`; `tool` and `rule_id` are free-text identifying the scanner that produced the finding.
- **ProjectOssJob** rows are background jobs that re-scan a project; `kind` is `ProjectOssJobKind` (e.g. `secrets`, `licenses`), `status` is `ProjectOssJobStatus`.
- **PendingMigrationLog** rows are written by `orch/daemon/migration_rebase.py` when it resolves a `PENDING` `down_revision` sentinel at merge time (see CR-00091). Columns track the original sentinel, the resolved revision, and the timestamp.
- **FixCycle** rows record each fix-cycle attempt the daemon makes after a QV gate fails; `trigger` is `FixTrigger`, `status` is `FixStatus`, `cycle_index` counts up to `MAX_FIX_CYCLE`.
- **ChatConversation / ChatMessage / ChatSummarizationJob / ChatTab** model the dashboard AI-assistant pane (F-00091). `tab_id` is the per-tab key; `summary_status` is `JobStatus`; the recent `chat_tabs.column_comment` migration (committed 2026-05-28) means at least one column already has a SQL-side COMMENT — confirm the python `doc=` matches the comment text where one exists.
- **DocIndexJob** rows track LanceDB doc-doc indexing (sibling to `CodeIndexJob`).
- **AgentRuntimeOption** rows back the AI Assistant model allowlist (`projects.toml` `[projects.X.ai_assistant]` sync target). `cli_tool` is `claude` or `opencode`; `model` is the model ID string; `context_window_tokens` and `max_output_tokens` are budget caps surfaced to the dashboard.

### 3. Verify wave 3 is fully scrubbed

```bash
uv run python scripts/check_db_column_docs.py --baseline orch/db/column_docs_baseline.txt 2>&1 | grep -E "(OssFinding|DocIndexJob|ProjectOssJob|PendingMigrationLog|FixCycle|OssScan|ChatTab|ChatSummarizationJob|ChatConversation|AgentRuntimeOption)\." | wc -l
# Expected: 0 new violations for these ten classes
```

Do NOT run `--write-baseline`. S04 owns final regeneration.

### 4. Targeted test verification

```bash
uv run pytest tests/orch/db/test_column_docs.py -v
```

All tests must pass.

## Pre-flight Quality Gates

1. `make format` 2. `make typecheck` 3. `make lint`

## TDD Requirement

```
"tdd_red_evidence": "n/a — content-only doc= additions on existing Column declarations; no new behavioural tests"
```

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "database-impl",
  "work_item": "CR-00092",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["orch/db/models.py"],
  "preflight": {"format": "...", "typecheck": "...", "lint": "..."},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed (tests/orch/db/test_column_docs.py)",
  "tdd_red_evidence": "n/a — content-only doc= additions on existing Column declarations; no new behavioural tests",
  "wave_scrub_count": 123,
  "cumulative_scrub_count": 316,
  "remaining_baseline_count": "<integer — should be ~134 (the remainder for S04)>",
  "blockers": [],
  "notes": "Wave 3 of 4 (OSS + chat + runtime). 123 columns documented. Cumulative through S03 = 316 of 450. ~134 entries remain for S04. Baseline file unchanged; S04 regenerates and deletes."
}
```
