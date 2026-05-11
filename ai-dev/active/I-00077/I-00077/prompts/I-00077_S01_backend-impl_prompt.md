# I-00077_S01_backend-impl_prompt

**Work Item**: I-00077 — Doc-generation jobs abort on missing editorial guide and the failure is invisible on the Docs page
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network state
(`docker kill|stop|rm|restart`, `docker compose up|down|restart`, `docker volume rm|prune`,
`docker system|container|image prune`). The orchestration DB, daemon, dashboard, and any
long-lived infra containers are outside your scope. Allowed: testcontainers spun up by
pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` and `make` targets.
If a task seems to require a prohibited command, STOP and raise a blocker.
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step adds **no** migration. Do not run `alembic upgrade|downgrade|stamp` against the
live DB. The `doc_type_guides._default` row already exists (migration `20260414_add_doc_type_guides.py`).

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00077 --json` for the current step list/status. `workflow-manifest.json` is a design-time snapshot.
- `ai-dev/active/I-00077/I-00077_Issue_Design.md` — design document (read this first)
- `orch/doc_service.py` — the file you change for Fix #1
- `skills/iw-doc-generator/SKILL.md`, `skills/iw-doc-system/SKILL.md` — the files you change for Fix #2
- For context only: `orch/daemon/doc_job_poller.py`, `orch/cli/doc_commands.py` (the `doc-job-status` JSON builder)

## Output Files

- `ai-dev/active/I-00077/reports/I-00077_S01_backend-impl_report.md` — step report
- Modified: `orch/doc_service.py`, `skills/iw-doc-generator/SKILL.md`, `skills/iw-doc-system/SKILL.md`

## Context

You are implementing the backend/skill half of I-00077. Read `ai-dev/active/I-00077/I-00077_Issue_Design.md` in full (especially **Root Cause Analysis** causes #1 and #2, and **Acceptance Criteria** AC1 and AC2). Then read `CLAUDE.md` for project conventions. **Do not touch the dashboard layer** — that's S03's scope.

## Requirements

### 1. Fix #1 — `_effective_guide` falls back to the `_default` `DocTypeGuide` row

In `orch/doc_service.py`, `DocService._effective_guide(self, project_id, doc_id, doc_type)` currently resolves: per-doc instance guide → `get_type_guide(doc_type)`. It returns `None` when neither exists, even though a `_default` row exists in `doc_type_guides` to serve as the global baseline. Change it to a three-level resolution:

1. per-doc instance guide (`get_instance_guide`)
2. the `doc_type`-keyed guide (`get_type_guide(doc_type)`)
3. the `_default` guide (`get_type_guide("_default")`)
4. only `None` if none of the above exist

Guard against the (degenerate) case `doc_type == "_default"` so you don't query it twice — a single extra lookup is fine. Keep the method signature unchanged. Do not change `create_doc_job` itself — it already calls `_effective_guide` and stores the result in `guide_snapshot`; the fix in `_effective_guide` is sufficient. (Note: `section_guides_snapshot` stays as-is — a diagram doc legitimately has no section guides; `None` there is expected and acceptable.)

### 2. Fix #2 — clarify the doc-generation skills' "Job lifecycle" guidance

In **both** `skills/iw-doc-generator/SKILL.md` and `skills/iw-doc-system/SKILL.md`, find the "Job lifecycle (when invoked via `/<skill> doc-job <job-id>`)" section, step 1 ("Read the job context."). Add an explicit clause stating:

- `section_guides_snapshot` and/or `guide_snapshot` being `null` (or empty) is **normal and expected** — many docs have no per-section or per-type editorial guide. It is **not** a reason to abort.
- When the editorial snapshot is null/empty, the agent **MUST proceed** and generate the document using the static editorial guidance bundled with the skill (`references/diagram-guidelines.md` for diagram docs, and the other `references/…-guidelines.md` / the rest of this SKILL.md for prose docs).
- The agent should close a job with `iw doc-job-done <job-id> --error '...'` **only** when `iw doc-job-status <job-id> --json` itself **exits non-zero** (job not found / DB error), or when generation genuinely cannot proceed for a concrete reason — never merely because the editorial snapshot was empty.

Keep the existing wording about "if the command exits non-zero, close the job immediately" — you are adding to it, not removing it. Match the surrounding markdown style. Keep the two files' wording consistent with each other (the relevant paragraph is essentially identical in both today).

Do **not** propagate these skill edits to other repositories — that is a manual post-merge operator step recorded in the design doc's **Notes**.

## Project Conventions

Read `CLAUDE.md` for architecture, layer boundaries, naming, ORM style, and test/build commands. Match existing code in `orch/doc_service.py`.

## TDD Requirement

Follow Red-Green-Refactor. Before changing `_effective_guide`, write (or extend) the unit test in `tests/unit/test_doc_type_guide_service.py` from the design doc ("Reproduction test #1") and confirm it fails; then make it pass. (S05 will add the broader test set — but you must not ship `_effective_guide` without at least the RED→GREEN unit test for it. Adding it to `tests/unit/test_doc_type_guide_service.py` is in scope for this step.)

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`, run in order and fix issues in files you touched:

1. `make format` — auto-fixes formatting drift; inspect the diff, re-stage.
2. `make typecheck` — zero errors involving your files.
3. `make lint` — zero errors. (`make lint` includes the Jinja2 template check, but you aren't touching templates here.)

Record each in the `preflight` object of your result contract (`ok` / `fixed` / `skipped:<reason>`).

## Test Verification (NON-NEGOTIABLE)

Run only the targeted tests for the code you changed — do **NOT** run the full suite:

```bash
uv run pytest tests/unit/test_doc_type_guide_service.py -v
```

Do not report `tests_passed: true` unless that passes with zero failures. Do not run `make test-integration` / `make test-unit` — those are downstream QV gates.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "I-00077",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["orch/doc_service.py", "skills/iw-doc-generator/SKILL.md", "skills/iw-doc-system/SKILL.md", "tests/unit/test_doc_type_guide_service.py"],
  "preflight": {"format": "ok|fixed|skipped:<reason>", "typecheck": "ok|skipped:<reason>", "lint": "ok|skipped:<reason>"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
