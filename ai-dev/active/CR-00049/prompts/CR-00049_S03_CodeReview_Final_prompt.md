# CR-00049_S03_CodeReview_Final_prompt

**Work Item**: CR-00049 -- Re-enable `pytest-randomly` by default (P1-CR-C-followup-randomly)
**Review Step**: S03

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope.

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This CR adds **no** migrations. Flag any migration appearing in `files_changed`
as a CRITICAL scope violation.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00049 --json`.
- `ai-dev/active/CR-00049/CR-00049_CR_Design.md` -- Design document
- All implementation step reports: `ai-dev/active/CR-00049/reports/CR-00049_S*_*_report.md`
- The per-agent code review report: `ai-dev/active/CR-00049/reports/CR-00049_S02_CodeReview_report.md`
- All files listed in implementation reports' `files_changed`

## Output Files

- `ai-dev/active/CR-00049/reports/CR-00049_S03_CodeReview_Final_report.md`

## Context

You are performing the **final cross-agent review** of ALL implementation work for **CR-00049 — Re-enable `pytest-randomly` by default**. This CR has a single implementation step (S01 backend-impl) followed by S02's per-agent review; your job is the cross-cutting view S02 could not have. Specifically:

1. Verify the change is **complete** — the fallback is removed (AC1), the failures from CR-00048's blocked diff-coverage gate are addressed (AC2), the docs are flipped (AC3), the plan is closed out (AC4), and the QV chain S04–S10 will pass (your runtime verification simulates this).
2. Verify the change is **internally consistent** — no doc says "off-by-default" while another says "default-on"; the `.claude/skills/` copy matches its master; the §5 row and the §11 changelog tell the same story; the historical "Earlier fallback (CR-00048)" notes appear consistently across the four flipped doc sites.
3. Verify the change has **no scope creep** — only the files in Impacted Paths were touched; no production code; no new tests; no Makefile targets; no GH workflow changes; no sync to sibling projects.
4. **Re-run the full test suite under randomisation** as your independent check — this is the definitive proof. CR-00048's lesson: S01's bounded sweep missed `make diff-coverage`'s combined invocation, and only the QV gate caught it 5 fix cycles too late. Don't repeat that mistake — your full-suite run here is exactly the catch S03 should provide.

## Read the Design Document FIRST

Read the design document **before** running gates and **before** opening files:

- Read `## Acceptance Criteria` AC1–AC5 in full. Every criterion is a mandatory check.
- Read `## Impacted Paths`. Any file in S01's `files_changed` outside that list is a **CRITICAL** scope violation (especially anything under `orch/`, `dashboard/`, `executor/`).
- Read the `## Notes` section — it explains why CR-00048 missed this and what the pressure-relief valve is. The acceptance bar is "addopts no longer carries `-p no:randomly` AND every still-broken test has a marker + xfail + tracking comment" — NOT "zero quarantines."

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading any code, run these on `files_changed`. Fix nothing yourself.

```bash
make lint          # ruff check
make format-check  # ruff format --check
```

Any NEW violation is a CRITICAL finding (`"category": "conventions"`).

## Review Checklist

### 1. Completeness vs Design Document

- AC1 (fallback removed): `grep -n 'no:randomly' pyproject.toml` returns nothing.
- AC2 (modules fixed or quarantined): for each of the 12 modules listed in *Current Behavior*, either the random-order failure is gone OR a quarantine marker with substantive `reason` + tracking comment is in place. Run the design's seed-12345 reproduction (see Test Verification below) and confirm.
- AC3 (docs flipped): `tests/CLAUDE.md` §7, `docs/IW_AI_Core_Testing_Strategy.md` §3 + §9 row, `skills/iw-ai-core-testing/SKILL.md` §2 — all four locations now say "default-on" + the historical "Earlier fallback (CR-00048)" note is preserved (not silently deleted). `.claude/skills/iw-ai-core-testing/SKILL.md` matches its master.
- AC4 (plan updated): `ai-dev/work/TESTS_ENHANCEMENT.md` §5 row marked DONE (CR-00049, YYYY-MM-DD); item 1.4 row flipped to DONE; §11 has a new changelog entry.
- AC5 (QV chain): your independent test run (below) is the proxy for S04–S10 passing.

### 2. Cross-Agent Consistency

CR-00049 has only one impl step (S01), so cross-agent consistency is mostly cross-file consistency:

- The "default-on" prose in `tests/CLAUDE.md`, the strategy doc, and the skill all describe the same recipe, the same reproduce commands, and the same quarantine policy. Pick one of the three, read it carefully, then verify the other two say the same thing in the same direction.
- The §5 row status, the item 1.4 status, and the §11 changelog entry are mutually consistent: same date, same counts, same description of the fix vs. the quarantines.
- The §11 changelog entry's "fixes" + "quarantines" counts equal S01's `files_changed` evidence (e.g. if 12 fixture-level diffs and 38 quarantine markers are claimed in the changelog, count them in the diff).

### 3. Scope Discipline

- No files under `orch/`, `dashboard/`, `executor/`, `bin/`, `scripts/` (production code) in `files_changed`.
- No new test files. Diffs under `tests/**` are limited to: fixture fixes (with `# CR-00049:` site comments) and quarantine markers (with `# NOTE(P1-CR-C-followup-randomly):` tracking comments).
- No changes to `Makefile`, `.github/workflows/`, `CLAUDE.md` (the project root one — `tests/CLAUDE.md` is allowed).
- No new dev deps in `pyproject.toml` or `uv.lock` changes (this CR adds nothing — `pytest-randomly` is already installed from CR-00048).
- No `iw sync-templates` run (no template edits).
- No sync to sibling projects (`iw-doc-plan/podforger/cv`'s `.claude/skills/` not touched here).

### 4. Quarantine Quality

Independently audit every `@pytest.mark.order_dependent` introduced by S01 (skip the one pre-existing in `test_browser_env.py:423`):

- Marker is exactly `@pytest.mark.order_dependent` (no typo, no `order-dependent`, no `order_dependant`).
- Paired with `@pytest.mark.xfail(strict=False, reason="…")`. `strict=False` is mandatory.
- `reason` is *substantive*: names what's leaking, not just "order-dependent". A reason of `"order-dependent"` is a HIGH finding.
- A `# NOTE(P1-CR-C-followup-randomly):` tracking comment exists naming the suspected leak source.
- The test isn't hidden (`@pytest.mark.skip` would be a CRITICAL finding — that's the deliberately-rejected anti-pattern).

### 5. Historical Note Preservation

The four flipped doc locations must each contain a brief "Earlier fallback (CR-00048): …" note explaining why `-p no:randomly` was introduced and why this CR removed it. If any location silently deletes the historical context, that's a MEDIUM (fixable) finding — future readers need to know the journey.

### 6. Architecture / Security

Tests-only CR. No architecture or security surface. Skip these checklists unless something surprises you.

## Test Verification (NON-NEGOTIABLE — this is the definitive proof)

Run **the design's exact reproduction recipe** against `tests/integration/` + `tests/dashboard/` at multiple seeds. If any seed surfaces a collection-time error (NOT counting `xfailed` quarantines), that is a **CRITICAL** finding — the implementation failed AC1 and AC2.

```bash
# Mirror S01's deliverable-4 sweep, plus one extra seed for independence
for seed in 12345 67890 11111 42424 99999; do
  echo "=== seed $seed ==="
  uv run pytest tests/integration/ tests/dashboard/ --ignore=tests/dashboard/browser -p randomly --randomly-seed=$seed -q 2>&1 | tail -10
done
```

All 5 must exit 0. (Quarantined tests showing as `xfailed` count as passing.)

Also run `make test-unit` once (no extra flags — the default randomisation is now active):

```bash
make test-unit
```

— must exit 0. Confirm the run output prints `Using --randomly-seed=<N>` near the top (proof that `pytest-randomly` is indeed active by default; if the output is missing this, the implementation failed AC1).

Do **NOT** run `make diff-coverage` or `make test-integration` directly — those are S09/S10's job and burn time. The five-seed sweep above is the equivalent diagnostic and is much faster.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | AC failure, scope violation, suite still broken under randomisation, hidden test (skip/comment-out) | Must fix |
| **HIGH** | Weak quarantine `reason`, inconsistency between doc locations, missing tracking comment | Must fix |
| **MEDIUM (fixable)** | Silently deleted historical note, minor convention violation | Should fix |
| **MEDIUM (suggestion)** | Better pattern available | Optional |
| **LOW** | Style nit | Informational |

## Review Result Contract

```json
{
  "step": "S03",
  "agent": "CodeReview_Final",
  "work_item": "CR-00049",
  "steps_reviewed": ["S01", "S02"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|integration|testing|architecture|security",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it",
      "cross_cutting": true
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "5-seed sweep (12345/67890/11111/42424/99999) of tests/integration/ + tests/dashboard/ under -p randomly: all green. make test-unit (default randomisation): X passed, 0 failed. Seed line printed: yes.",
  "missing_requirements": [],
  "notes": ""
}
```

- `verdict`: `pass` if zero CRITICAL + zero HIGH + zero MEDIUM (fixable). `fail` otherwise.
- `missing_requirements`: any AC1–AC5 not met. Each is automatically CRITICAL.
- `cross_cutting`: set to `true` on findings that span multiple doc locations or affect the consistency of the historical narrative.
