# F-00092_S04_CodeReview_prompt

**Work Item**: F-00092 — Tier-1 orchestration DB backups
**Step**: S04
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits

Read-only Docker introspection only.

## Input Files

- `uv run iw item-status F-00092 --json`.
- `ai-dev/active/F-00092/F-00092_Feature_Design.md`.
- Reports + diffs for S01 (model + migration) and S03 (config + engine).

## Output Files

- `ai-dev/active/F-00092/reports/F-00092_S04_CodeReview_report.md`.

## Review Checklist (cite file:line)

**S01 — model + migration**
1. No column named `metadata` (SQLAlchemy reservation). Enum/JSON/timestamp columns
   match existing `*Job` model conventions.
2. Index on (backup_type, status, created_at) present and useful for catch-up/prune.
3. Migration generated via `make migration-pending` (`down_revision = "PENDING"`),
   `downgrade()` drops table + index. `make migration-check` was green.

**S03 — config + engine**
4. Config reads from `.env` with the specified defaults; nothing hardcoded
   elsewhere (Invariant 7).
5. Engine produces all three artifacts (dump `-Fc`, `--globals-only`, manifest) and
   only records `success` after the `pg_restore --list` integrity check (Invariants
   1, 2). Globals are genuinely captured (not omitted).
6. Engine is standalone: no daemon-only imports, callable as a plain function;
   works without the daemon (Invariant 5). Connection comes from config; pg client
   obtained via host binary or `docker run --rm` (self-removing) — no persistent
   container/volume changes.
7. Failure path: integrity-check failure / DB-unreachable → `failed` row + clear
   error + partial cleanup; does not leave a half-set that looks successful.
8. Layer boundaries respected; logging/error style matches the codebase; RED
   evidence present for the new unit tests.
9. **Secrecy + portability**: backup-set dir is created `0700` and the
   `--globals-only` file is written `0600` (Invariant 8); its contents are never
   logged. The manifest records the PostgreSQL **server version**, and the pg-client
   image major is resolved from the server version (not hardcoded `15`). Docker
   pg-client invocation uses host-reachable networking (`--network host` /
   `--add-host host.docker.internal:host-gateway`), not bare `localhost`.

## Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "F-00092",
  "completion_status": "complete",
  "findings": [{"severity": "CRITICAL|HIGH|MEDIUM|LOW", "file": "...", "issue": "...", "recommendation": "..."}],
  "approved": true,
  "notes": ""
}
```

Approve only if globals capture + integrity gating are correct (these are the two
properties that make a restore actually work).
