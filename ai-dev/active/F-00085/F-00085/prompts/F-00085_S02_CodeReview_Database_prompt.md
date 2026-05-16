# F-00085_S02_CodeReview_Database_prompt

**Work Item**: F-00085
**Step**: S02 (Per-agent review of S01)
**Agent**: code-review-impl

---

## Inputs

- `ai-dev/active/F-00085/F-00085_Feature_Design.md`
- `ai-dev/active/F-00085/reports/F-00085_S01_Database_report.md`
- Diff of files in `files_changed`

## Output

- `ai-dev/active/F-00085/reports/F-00085_S02_CodeReview_report.md`

## Review Checklist

### `merge_auto_verdicts`

- [ ] Composite PK `(project_id, daemon_event_id)`.
- [ ] FK `daemon_event_id → daemon_events(id)` with `ON DELETE CASCADE`.
- [ ] FK `project_id → projects(id)` with `ON DELETE CASCADE`.
- [ ] CHECK constraint enforces `verdict IN ('pending','correct','wrong','partial')`.
- [ ] `verdict_notes` defaults to empty string (NOT NULL DEFAULT '').
- [ ] `verdicted_at` is TIMESTAMPTZ with `server_default=func.now()`.
- [ ] ORM class is named `MergeAutoVerdict` and uses `Mapped[]` style.

### `auto_merge_project_config`

- [ ] Single PK on `project_id`.
- [ ] FK `project_id → projects(id)` with cascade.
- [ ] FK `runtime_option_id → agent_runtime_options(id)` with `ON DELETE SET NULL`.
- [ ] CHECK constraint enforces `phase IS NULL OR phase IN (0, 1)` — Phase 2/3 reserved (Invariant 5).
- [ ] `phase` and `runtime_option_id` are both nullable.
- [ ] ORM class is named `AutoMergeProjectConfig`.

### Migration

- [ ] One file under `orch/db/migrations/versions/`.
- [ ] `down_revision` correctly points to the previous head.
- [ ] Both tables created in one alembic upgrade.
- [ ] `downgrade()` drops both tables in reverse order.
- [ ] `make migration-check` PASSED in S01's report.

### Invariants (Inv 1: append-only on daemon_events)

- [ ] No code in this diff UPDATEs or DELETEs `daemon_events` rows.
- [ ] No new columns added to `daemon_events`.

### Project conventions

- [ ] SQLAlchemy 2.0 `Mapped[]` style.
- [ ] `_TIMESTAMPTZ` alias reused (don't redefine).
- [ ] Composite-PK pattern matches other examples in `orch/db/models.py`.
- [ ] No psycopg2 references; pyhon3 stdlib + psycopg v3 only.

### Out-of-scope guard

- [ ] No code touched outside `orch/db/models.py` + the new migration file.
- [ ] No daemon-side, dashboard, or test changes.

## Severity Mapping

- **CRITICAL** — composite PK wrong; CHECK constraint missing or wrong; FK target wrong; migration round-trip fails; daemon_events touched.
- **HIGH** — phase constraint allows 2 or 3; ORM model doesn't match table; downgrade() drops in wrong order.
- **MEDIUM** — type annotations missing; styling drift from neighbours.
- **LOW** — comment / docstring nits.

## Result Contract

Standard code-review JSON.
