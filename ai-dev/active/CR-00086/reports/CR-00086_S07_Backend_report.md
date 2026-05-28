# CR-00086 S07 Backend — CI Workflow + Docs + Skill + Tracker

**Step**: S07 — Backend (CI workflow + docs + skill + tracker)
**Agent**: backend-impl
**Work Item**: CR-00086
**Status**: complete

---

## What was done

### 1. `.github/workflows/test-health.yml` (new)

New CI workflow for test-health snapshot capture. Key design decisions:

- **`runs-on: [self-hosted, iw-core]`** — self-hosted runner with network access
  to the orchestration DB on port 5433. This is a hard prerequisite: rows must
  survive across runs for trend-over-time. An ephemeral GH-Actions service-container
  Postgres would have its rows disappear at runner exit — explicitly rejected per
  the design.
- **No `services: postgres:` block** — does NOT copy the `test-quality.yml`
  pattern of an inline `postgres:` service. The `IW_CORE_*` GitHub secrets point
  at the live orch DB.
- **Triggers**: `push` to `main` + nightly cron `0 3 * * *` UTC + `workflow_dispatch`.
- **`concurrency: { group: test-health, cancel-in-progress: false }`** — concurrent
  on-push + cron runs queue rather than cancel.
- Steps: checkout → setup-uv → `uv sync --frozen` → `iw test-health-capture` with
  `IW_CORE_*` secrets → `actions/upload-artifact@v4` (30-day retention).
- Header comment documents the three operator prerequisites explicitly so future
  maintainers know what is needed before the workflow will succeed.

### 2. `docs/IW_AI_Core_Testing_Strategy.md` — §10 Self-dashboarding (new)

New top-level section between the old §10 (Regression-rate KPI) and §11 (Quick
reference). Covers:

- **Four metrics** table (mutation_score, coverage_pct, flaky_test_count,
  assertion_baseline_size) with source artefact links.
- **Panel mount points** (Tests and Quality pages via htmx `hx-get` mount).
- **Capture cadence** (push to main + nightly + manual).
- **Persistence model** — self-hosted runner reaches live orch DB on port 5433
  via `IW_CORE_*` secrets; ephemeral service-container Postgres explicitly
  rejected; rationale explained for future maintainers.
- **Operator prerequisites** (self-hosted runner online, `IW_CORE_*` secrets,
  network access to 5433).
- **Idempotency contract** (one row per `(project_id, metric, ts_minute)`).
- **Empty-state behaviour** (per-metric "no data yet" + combined empty state).
- **Links** to CR-00086 design + manifest + all implementation files.
- **`last updated: 2026-05-28`** line.

Also updated §9 roadmap table: row 4.6 flipped to ✅, added self-dashboarding
entry with CR-00086 link. Renumbered subsequent sections (§11→§12, §12→§13,
§13→§14). Added changelog entry.

### 3. `docs/IW_AI_Core_Database_Schema.md` — §11 DDL block (new)

New section 11 "CR-00086: Test Health Snapshots — Self-dashboarding" appended
after the CR-00022 section. DDL for `test_health_snapshots` in the same style
as other tables: `id BIGSERIAL`, `project_id BIGINT FK CASCADE`, `ts TIMESTAMPTZ`,
`metric TEXT`, `value DOUBLE PRECISION`, `meta JSONB`, unique index on
`(project_id, metric, date_trunc('minute', ts))`. Includes index comment,
idempotency rationale, downgrade SQL, and CR-00086 cross-reference links.

### 4. `ai-dev/work/TESTS_ENHANCEMENT.md`

- **§8 row 4.6**: status `DRAFT → DONE`, text updated with actual delivery
  description (table + CLI + panel + workflow + docs + skill cross-ref, date
  2026-05-24 per instructions, `browser_verification: true` preserved).
- **Header version**: v1.6 → v1.7, date 2026-05-28.
- **§11 changelog**: new entry dated 2026-05-28 with two-line summary.

### 5. `skills/iw-ai-core-testing/SKILL.md` §17 — new section

Added a new §17 "Test Health Self-Dashboarding (CR-00086)" section after the
daemon-chaos §16. Contains:

- A metrics table (same four metrics as the strategy doc).
- Persistence model note (self-hosted runner, live orch DB on 5433, NOT ephemeral
  service-container Postgres).
- Operator prerequisites list.
- Idempotency note.
- Cross-reference links to CR-00086 design, strategy doc §10, workflow YAML.

Ran `cp skills/iw-ai-core-testing/SKILL.md .claude/skills/iw-ai-core-testing/SKILL.md`
to mirror the mirror (since `iw sync-skills` skips project-override skills).
`diff -u` confirms byte-identical.

---

## TDD / Test Verification

**Not applicable** — this step is workflow + docs + tracker + skill edits only,
no production logic implemented. `tdd_red_evidence` recorded as:
`"n/a — workflow + docs + tracker + skill edits only, no production logic"`.

No new tests were added or run. Sanity-checked skill mirror:
```bash
diff -u skills/iw-ai-core-testing/SKILL.md .claude/skills/iw-ai-core-testing/SKILL.md
# empty — byte-identical
```

---

## Preflight Results

| Gate | Result |
|------|--------|
| `make format` | ok |
| `make typecheck` | ok |
| `make lint` | ok |

---

## Files Changed

- `.github/workflows/test-health.yml` — new workflow
- `docs/IW_AI_Core_Testing_Strategy.md` — §10 new section + §9 row 4.6 → ✅ + section renumbering + changelog
- `docs/IW_AI_Core_Database_Schema.md` — §11 new DDL block
- `ai-dev/work/TESTS_ENHANCEMENT.md` — §8 row 4.6 → DONE + v1.7 header bump + §11 changelog entry
- `skills/iw-ai-core-testing/SKILL.md` — new §17 cross-reference section
- `.claude/skills/iw-ai-core-testing/SKILL.md` — mirrored (byte-identical to master)

---

## Blockers

**Operator action required before the workflow will run successfully:**

1. A self-hosted runner labelled `iw-core` must be provisioned and online.
2. GitHub secrets `IW_CORE_DB_HOST`, `IW_CORE_DB_PORT`, `IW_CORE_DB_NAME`,
   `IW_CORE_DB_USER`, `IW_CORE_DB_PASSWORD` must be created, pointing at the
   live orchestration DB on port 5433.
3. The runner's network must be able to reach `IW_CORE_DB_HOST:5433`.

Without all three the workflow fails at the `iw test-health-capture` step.

---

## Notes

- The `[self-hosted, iw-core]` runner label was chosen based on the pattern
  described in the step instructions. If the operator uses a different label
  for IW-managed self-hosted workflows, the `runs-on` in the workflow YAML
  needs to be updated to match.
- No Python production code was changed in this step; `make typecheck` was a
  no-op.
- The Jinja2 `namespace()` workaround from S05's Jinja2 scoping bug is not
  relevant here — no template changes in this step.
- The workflow YAML uses SHA-pinned `actions/checkout` and `actions/upload-artifact`
  (matching `codeql.yml` and `test-quality.yml` conventions).
