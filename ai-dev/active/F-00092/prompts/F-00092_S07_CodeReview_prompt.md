# F-00092_S07_CodeReview_prompt

**Work Item**: F-00092 — Tier-1 orchestration DB backups
**Step**: S07
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits

Read-only Docker introspection only.

## Input Files

- `uv run iw item-status F-00092 --json`.
- `ai-dev/active/F-00092/F-00092_Feature_Design.md`.
- Reports + diffs for S05 (retention + restore) and S06 (daemon poller).

## Output Files

- `ai-dev/active/F-00092/reports/F-00092_S07_CodeReview_report.md`.

## Review Checklist (cite file:line)

**S05 — retention + restore**
1. Prune never deletes `manual` backups (Invariant 3); age boundary is explicit and
   tested with injected now.
2. Restore defaults to a SAFE non-prod target and **refuses** prod without
   `allow_prod` (Invariant 4 / Boundary guard). Live 5433 cannot be clobbered by
   default.
3. Restore order is globals-first then archive; identity check + row-count print
   happen after restore (AC5).

**S06 — daemon poller**
4. Due/catch-up logic is correct: disabled → never; recent scheduled success →
   not due; missed window → due immediately (AC4). Decision logic is isolated and
   unit-tested with injected time.
5. A failed backup is recorded `failed` so the window stays unsatisfied and retries;
   the daemon loop never crashes on backup failure (matches other pollers'
   resilience).
6. Poller is wired into `daemon/main.py` consistently with existing pollers; no
   tight loop; correct session handling.
7. Layer boundaries, logging, RED evidence for new unit tests.

## Result Contract

```json
{
  "step": "S07",
  "agent": "code-review-impl",
  "work_item": "F-00092",
  "completion_status": "complete",
  "findings": [{"severity": "...", "file": "...", "issue": "...", "recommendation": "..."}],
  "approved": true,
  "notes": ""
}
```

Approve only if the prod-restore guard and the catch-up logic are provably correct.
