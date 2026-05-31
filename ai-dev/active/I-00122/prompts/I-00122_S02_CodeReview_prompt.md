# I-00122_S02_CodeReview_prompt

**Work Item**: I-00122 — db-start guard against empty-DB displacement
**Step**: S02
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits

Read-only Docker introspection only. Do not change container/volume state, and
do not run `./ai-core.sh db start/stop/restart` against the live DB.

## Input Files

- `uv run iw item-status I-00122 --json` — runtime step state.
- `ai-dev/active/I-00122/I-00122_Issue_Design.md` — design doc.
- `ai-dev/active/I-00122/reports/I-00122_S01_Backend_report.md` — S01 report.
- The S01 diff (`ai-core.sh`, `.env.example`, `docs/IW_AI_Core_DB_Setup.md`).

## Output Files

- `ai-dev/active/I-00122/reports/I-00122_S02_CodeReview_report.md`.

## Context

Review the S01 implementation of the identity-aware `cmd_db start` guard and the
`start-prod` recovery path. The goal of the fix: an empty bootstrap DB must never
be created on the production port when a production identity is pinned and the DB
is down.

## Review Checklist

Verify each, citing `file:line`:

1. **Guard correctness** — When `db_ready` is false **and**
   `IW_CORE_EXPECTED_INSTANCE_ID` is set/non-empty, `cmd_db start` returns
   non-zero and the `docker compose ... up -d db` line is **not reached**.
   Confirm there is no code path where the bootstrap compose still runs in this
   case (e.g. fall-through, missing `return`, `set -e` interactions).
2. **Dev path preserved** — When no instance identity is pinned, the bootstrap
   compose still runs exactly as before. The early-return-when-`db_ready` branch
   is unchanged.
3. **No hardcoded paths/ports/creds** — `IW_CORE_DB_DATA_DIR` is read from the
   environment; no literal `/opt/...` path, no literal `5433`, no password in the
   script. The `start-prod` path errors cleanly when `IW_CORE_DB_DATA_DIR` is
   unset.
4. **Image + restart policy** — `start-prod` uses `postgres:15-alpine`,
   `--restart=always`, the configured port and data dir, a stable container name
   distinct from the bootstrap `iw-ai-core-db`, and reuses an existing container
   via `docker start` rather than failing on a name clash.
5. **Message quality** — The refusal message is actionable: names the prod-down
   condition, says it will not bootstrap, and points to `db start-prod` /
   `docs/IW_AI_Core_DB_Setup.md`.
6. **Shell hygiene** — Proper quoting, uses existing `print_*`/`wait_for_db`
   helpers, `bash -n ai-core.sh` passes; no unrelated refactors. Flag any
   shellcheck-class issues (unquoted expansions, etc.).
7. **Docs/example** — `.env.example` documents `IW_CORE_DB_DATA_DIR`;
   `docs/IW_AI_Core_DB_Setup.md` documents the guard and the recovery path
   consistently with the existing incident narrative.
8. **Scope** — Only `ai-core.sh`, `.env.example`, `docs/IW_AI_Core_DB_Setup.md`
   are touched (plus the item's `ai-dev/active/**`). No stray edits.

## Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "I-00122",
  "completion_status": "complete",
  "findings": [
    {"severity": "CRITICAL|HIGH|MEDIUM|LOW", "file": "ai-core.sh:NNN", "issue": "...", "recommendation": "..."}
  ],
  "approved": true,
  "notes": ""
}
```

Report CRITICAL/HIGH findings clearly so the fix step can address them. Approve
only if the guard provably blocks the bootstrap path when an identity is pinned.
