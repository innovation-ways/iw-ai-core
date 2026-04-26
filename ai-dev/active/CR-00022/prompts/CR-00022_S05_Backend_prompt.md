# CR-00022_S05_Backend_prompt (SLIMMED — recovery from prior failed run)

**Work Item**: CR-00022
**Step**: S05
**Agent**: backend-impl (Phase B — per-check catalog wiring)

---

## ⛔ Docker / Migrations off-limits

No live alembic apply, no docker compose, read-only docker introspection only.

## Why this prompt is slimmed

The previous S05 run died after authoring only the loader stub. The two largest pieces of work — the 71-entry YAML catalog and the loader Python — have already been completed out-of-band:

- ✅ **`dashboard/services/oss_check_catalog.yaml`** — 71 entries, ~1359 lines, schema-validated. **DO NOT REWRITE.**
- ✅ **`dashboard/services/oss_check_catalog.py`** — loader with Pydantic v2 + cache + debug hot-reload. **DO NOT REWRITE.**

Your job is the **remaining** code-wiring work. It is mechanical, contained, and small. Do not regenerate or rewrite the two files above; just verify they load.

## Required Edits (do exactly these — nothing else)

### 1. `skills/iw-oss-publish/scripts/lib/types.py` — `Finding` dataclass

Add `auto_apply_safe: bool = False` to the `Finding` dataclass directly **after** the existing `auto_fix_available: bool = False` line. Then add `"auto_apply_safe": self.auto_apply_safe,` to the `to_dict()` return value, in the same relative position (right after the existing `auto_fix_available` entry).

### 2. `skills/iw-oss-publish/scripts/checks/*.py` — annotate every `Finding(...)` constructor

There are **110** `Finding(...)` constructor calls across 16 check modules. Every single one needs an `auto_apply_safe=True` or `auto_apply_safe=False` keyword argument, placed adjacent to the existing `auto_fix_available=` argument (or, if absent, alongside the other constructor kwargs).

Decision rules (default to **False** when in doubt — `False` is conservative):

- `True` — the dashboard can safely render the fix without human judgement:
  - Template renders for missing files (README, SECURITY, CODE_OF_CONDUCT, CONTRIBUTING, GOVERNANCE, LICENSE, NOTICE, CHANGELOG, etc.)
  - Idempotent additive `.gitignore` patches (adding new patterns to an existing/new `.gitignore`)
  - New CI workflow file additions (creating `.github/workflows/ci.yml` from a template) — but **not** edits to existing workflows
  - Adding "Signed-off-by" instructions to CONTRIBUTING.md (DCO instruction insertion)
  - Adding standard `osps_control` markers / labels to repo metadata files
- `False` — requires human judgement, removes tracked files, rotates secrets, edits existing config:
  - Any `OSS-SEC-*` / secrets-in-history / PII findings (no safe auto-rotation)
  - Hygiene findings that would require **deleting** tracked files (e.g. removing checked-in build artefacts)
  - Modifying existing GitHub workflows
  - Trademark / export-control / governance findings that need legal/maintainer judgement
  - Any release/history check that would rewrite git history
  - Any internal-references / `OSS-REF-*` findings (require manual edits to specific code)
  - All `*-ALL` aggregate markers (`OSS-GH-ALL`, `OSS-REF-ALL`) — these are meta, not directly fixable

Audit module-by-module. Read each `Finding(...)` constructor in context, decide the flag, and add the kwarg. **Do not** add comments unless the choice is genuinely surprising.

Modules to cover (counts of `Finding(...)` calls per module — verify your edits cover all of them):

```
skills/iw-oss-publish/scripts/checks/ci_cd.py          (9)
skills/iw-oss-publish/scripts/checks/governance.py     (4)
skills/iw-oss-publish/scripts/checks/license_check.py  (8)
skills/iw-oss-publish/scripts/checks/contributor.py    (6)
skills/iw-oss-publish/scripts/checks/community.py      (15)
skills/iw-oss-publish/scripts/checks/environment.py    (5)
skills/iw-oss-publish/scripts/checks/privacy.py        (6)
skills/iw-oss-publish/scripts/checks/trademark.py      (4)
skills/iw-oss-publish/scripts/checks/history.py        (6)
skills/iw-oss-publish/scripts/checks/release.py        (9)
skills/iw-oss-publish/scripts/checks/internal_refs.py  (1)
skills/iw-oss-publish/scripts/checks/github.py         (14)
skills/iw-oss-publish/scripts/checks/dependencies.py   (9)
skills/iw-oss-publish/scripts/checks/export_control.py (6)
skills/iw-oss-publish/scripts/checks/hygiene.py        (6)
skills/iw-oss-publish/scripts/checks/secrets.py        (2)
                                              total = 110
```

After your edits, verify the count is preserved:
```bash
grep -cE "auto_apply_safe=" skills/iw-oss-publish/scripts/checks/*.py | awk -F: '{s+=$2} END {print s}'
# Expect: 110
```

### 3. `orch/oss/persistence.py` — write `auto_apply_safe` to the DB

In the `OssFinding(...)` constructor (currently around line 49–63), add a single line right after `auto_fix_available=f.get("auto_fix_available", False),`:

```python
auto_apply_safe=f.get("auto_apply_safe", False),
```

The DB column already exists (added by S01 migration `c062b6bf5eb3`); the ORM field already exists (`orch/db/models.py:1627`). You are wiring the dict → ORM mapping only.

## Verification (run these — paste results in the report)

```bash
# 1. Catalog loads to 71 entries
uv run python -c "from dashboard.services.oss_check_catalog import load_catalog; print(len(load_catalog()))"
# Expected: 71

# 2. Constructor coverage = 110
grep -cE "auto_apply_safe=" skills/iw-oss-publish/scripts/checks/*.py | awk -F: '{s+=$2} END {print s}'
# Expected: 110

# 3. Scan emits the new field
uv run iw oss scan --project iw-ai-core || true
jq '.findings[0] | {id: .id, auto_fix_available, auto_apply_safe}' .iw/oss-publish-findings.json
# Expected: object containing auto_apply_safe: true|false (boolean, not null)

# 4. Distribution sanity check
jq '[.findings[].auto_apply_safe] | group_by(.) | map({val: .[0], count: length})' .iw/oss-publish-findings.json
# Expected: roughly half true / half false
```

## Out of Scope (DO NOT do these)

- Do **not** rewrite `dashboard/services/oss_check_catalog.yaml` — it is authored.
- Do **not** rewrite `dashboard/services/oss_check_catalog.py` — it is authored.
- Do **not** add a CI completeness test — that is S17's job.
- Do **not** modify any persistence read path or dashboard router — separate steps.
- Do **not** restructure existing checks beyond adding the one kwarg.

## Project Conventions

- Pydantic v2 syntax. Type hints everywhere. `from __future__ import annotations` already in place.
- No `print()` debug statements.
- No comments alongside `auto_apply_safe=` unless the choice is genuinely non-obvious.

## Output / Report

Write `ai-dev/active/CR-00022/reports/CR-00022_S05_Backend_report.md` containing:

- One-line confirmation of each of the three edits (`types.py` field + `to_dict`, 110 `auto_apply_safe=` annotations, `persistence.py` mapping)
- A per-module breakdown of how many `True` vs `False` you assigned (table or list)
- Output from each of the four verification commands above
- Any check IDs where the `auto_apply_safe` choice felt ambiguous and merits reviewer judgement

End with `iw step-done` (or `iw step-fail` with reason on failure).
