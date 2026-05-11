# I-00077_S01_Backend_impl_report — Doc-generation jobs abort on missing editorial guide

## Step

S01 — backend-impl

## Work Item

I-00077 — Doc-generation jobs abort on missing editorial guide and the failure is invisible on the Docs page

---

## What Was Done

### Fix #1 — `_effective_guide` falls back to `_default` DocTypeGuide row

**File:** `orch/doc_service.py`

Changed `_effective_guide` to implement a three-level resolution chain:

1. per-doc instance guide (`get_instance_guide`)
2. the `doc_type`-keyed guide (`get_type_guide(doc_type)`)
3. the `_default` guide (`get_type_guide("_default")`)
4. only `None` if none of the above exist

Also added a guard against `doc_type == "_default"` to avoid a redundant extra lookup when the caller passes `_default` directly.

### Fix #2 — Clarified "Job lifecycle" guidance in both skills

**Files:** `skills/iw-doc-generator/SKILL.md`, `skills/iw-doc-system/SKILL.md`

In step 1 ("Read the job context"), added an explicit note stating:
- `section_guides_snapshot` and/or `guide_snapshot` being `null` (or empty) is **normal and expected** — many docs have no per-section or per-type editorial guide. It is **not** a reason to abort.
- When the editorial snapshot is null/empty, the agent **MUST proceed** using the static `references/…-guidelines.md` bundled with the skill.
- The agent should close a job with `iw doc-job-done <job-id> --error '...'` **only** when `iw doc-job-status <job-id> --json` exits non-zero, or when generation genuinely cannot proceed for a concrete reason — never merely because the editorial snapshot was empty.

The wording is identical in both skill files.

### TDD — Unit test for `_effective_guide`

**File:** `tests/unit/test_doc_type_guide_service.py`

Added `TestEffectiveGuide` class with 4 tests:
- `test_effective_guide_falls_back_to_default_when_no_specific_guide` — the reproduction test (RED→GREEN)
- `test_effective_guide_returns_instance_guide_when_present` — regression: instance takes priority
- `test_effective_guide_returns_doc_type_guide_when_no_instance_guide` — regression: type guide is used when no instance
- `test_effective_guide_returns_none_when_no_guide_exists` — degenerate: no guide at all returns None

---

## Files Changed

| File | Change |
|------|--------|
| `orch/doc_service.py` | `_effective_guide` now falls back to `_default` guide |
| `skills/iw-doc-generator/SKILL.md` | Added null-snapshot guidance in Job lifecycle step 1 |
| `skills/iw-doc-system/SKILL.md` | Added null-snapshot guidance in Job lifecycle step 1 |
| `tests/unit/test_doc_type_guide_service.py` | Added `TestEffectiveGuide` class with 4 tests |

---

## Test Results

```
uv run pytest tests/unit/test_doc_type_guide_service.py -v --no-cov
========================= 8 passed, 1 warning in 0.08s =========================
```

All 8 tests in the file pass (4 pre-existing + 4 new). The reproduction test `test_effective_guide_falls_back_to_default_when_no_specific_guide` went RED on first run and GREEN after the fix.

---

## Preflight Quality Gates

| Check | Result |
|-------|--------|
| `make format` | ok — no formatting drift |
| `make typecheck` | ok — no type errors |
| `make lint` | ok — no lint errors (includes Jinja2 template check) |

---

## Acceptance Criteria Status

- **AC1 (Missing editorial guide no longer aborts):** ✅ `_effective_guide` now resolves `_default` when no instance/type guide exists; `guide_snapshot` in `create_doc_job` will no longer be `None` for diagram docs.
- **AC2 (Skill guidance clarified):** ✅ Both skill SKILL.md files now explicitly state that null editorial snapshots are normal and the agent should proceed using static guidelines.

---

## Notes

- Dashboard-level changes (Fix #3 — surfacing failed jobs on the Docs catalogue page) are **not in scope** for this step; they belong to S03 (frontend-impl).
- Skill propagation to IW-AI-DEV and InnoForge repositories is a manual post-merge operator step, not a workflow step.
- No migrations were needed — the `_default` row already exists in `doc_type_guides` from migration `20260414_add_doc_type_guides.py`.
