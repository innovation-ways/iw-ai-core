# CR-00022_S05_Backend_prompt

**Work Item**: CR-00022
**Step**: S05
**Agent**: backend-impl (Phase B — per-check catalog)

---

## ⛔ Docker / Migrations off-limits

Same rules. No live alembic apply, no docker compose, read-only docker introspection only.

## Input Files

- `ai-dev/active/CR-00022/CR-00022_CR_Design.md`
- `ai-dev/active/CR-00022/reports/CR-00022_S03_Backend_report.md`
- `skills/iw-oss-publish/scripts/checks/*.py` — all check modules
- `dashboard/utils/oss_copy.py` — current domain/severity copy (will continue to exist as a fallback)
- `doc-system/` — Innovation Ways editorial guidelines for brand voice

## Output Files

- New: `dashboard/services/oss_check_catalog.py` (Pydantic loader, in-process cache, debug hot-reload)
- New: `dashboard/services/oss_check_catalog.yaml` (per-check copy, complete for every check ID)
- Modified: `skills/iw-oss-publish/scripts/checks/*.py` — every `Finding(id="…")` constructor receives `auto_apply_safe=<bool>`
- Modified: `skills/iw-oss-publish/scripts/lib/types.py` — add `auto_apply_safe: bool = False` to `Finding` dataclass
- `ai-dev/active/CR-00022/reports/CR-00022_S05_Backend_report.md`

## Context

This step authors the **per-check catalog** that powers the new dashboard modal. The catalog is static — populated once now via online research, loaded at runtime, never fetched live. A CI completeness test (S17) enforces every check has an entry.

You also tag every check with `auto_apply_safe: bool` distinguishing checks where the dashboard can safely write the fix automatically (e.g., generate LICENSE) from checks that need manual remediation (e.g., remove secret from git history).

## Requirements

### 1. Enumerate every check ID — two sources, union

Source 1 — runtime scan:
```bash
cd $(pwd)
uv run iw oss scan --project iw-ai-core || true
jq -r '.findings[].check_id' .iw/oss-publish-findings.json | sort -u > /tmp/scan_ids.txt
```

Source 2 — AST walk:
```python
import ast, pathlib
ids = set()
for path in pathlib.Path("skills/iw-oss-publish/scripts/checks").glob("*.py"):
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "Finding":
            for kw in node.keywords:
                if kw.arg == "id" and isinstance(kw.value, ast.Constant):
                    ids.add(kw.value.value)
print("\n".join(sorted(ids)))
```

Take the union. Document the count in the report.

### 2. YAML catalog format

`dashboard/services/oss_check_catalog.yaml`:

```yaml
# Per-check authored copy for the OSS Compliance dashboard modal.
# Every check_id produced by skills/iw-oss-publish/scripts/checks/*.py MUST have an entry.
# CI test tests/unit/test_oss_catalog_completeness.py enforces this.

OSS-CH-01:
  what_it_checks: |
    Whether the repository has a README at its root. README.md, README.rst,
    README.txt, and README (no extension) are all accepted.
  how_it_tests: |
    Looks in the repo root for files matching README, README.md, README.rst,
    or README.txt (case-sensitive on case-sensitive filesystems).
  risk_if_failing: |
    First-time visitors see a bare file tree with no idea what the project
    does, how to install it, or who it's for. Drives away contributors and
    delays adoption.
  how_to_fix: |
    Add a README.md at the repo root with: project tagline, install steps,
    quick-start example, and link to docs. The Apply action renders one
    from the iw-oss-publish template.
  references:
    - https://opensource.guide/starting-a-project/#a-readme
    - https://opensource.guide/starting-a-project/

OSS-CH-02:
  what_it_checks: |
    ...
```

Required fields: `what_it_checks`, `how_it_tests`, `risk_if_failing`, `how_to_fix`. Optional: `references` (list of URLs).

### 3. Author copy via online research — per check

For each check ID:
1. Open the check module (`secrets.py`, `community.py`, `license_check.py`, etc.) and read what the check actually does.
2. Web-search the check's domain (e.g., "github SECURITY.md best practices", "OpenSSF Scorecard branch protection", "gitleaks detection patterns") to ground the copy.
3. Author concise prose following Innovation Ways editorial voice (see `doc-system/` for the style guide):
   - Plain English, no jargon-without-explanation.
   - 2-4 sentences per field.
   - "Risk" framed in concrete consequences, not abstract policy violations.
   - "How to fix" gives the *action*, not a lecture.
   - No emoji.

Cross-check OSPS Baseline references where the check carries an `osps_control` value — link to the relevant OSPS page in `references[]`.

### 4. Loader: `dashboard/services/oss_check_catalog.py`

```python
from __future__ import annotations
import os
from functools import cache
from pathlib import Path
from typing import Annotated
from pydantic import BaseModel, Field, field_validator
import yaml

CATALOG_PATH = Path(__file__).parent / "oss_check_catalog.yaml"


class CheckCopy(BaseModel):
    what_it_checks: Annotated[str, Field(min_length=1)]
    how_it_tests: Annotated[str, Field(min_length=1)]
    risk_if_failing: Annotated[str, Field(min_length=1)]
    how_to_fix: Annotated[str, Field(min_length=1)]
    references: list[str] = []


def _load_catalog_uncached() -> dict[str, CheckCopy]:
    raw = yaml.safe_load(CATALOG_PATH.read_text())
    if not isinstance(raw, dict):
        raise ValueError(f"Catalog YAML must be a mapping, got {type(raw).__name__}")
    return {check_id: CheckCopy.model_validate(entry) for check_id, entry in raw.items()}


@cache
def _load_catalog_cached() -> dict[str, CheckCopy]:
    return _load_catalog_uncached()


def load_catalog() -> dict[str, CheckCopy]:
    """Load the per-check copy catalog.

    In production (DEBUG=False), loads once and caches.
    In debug mode (DEBUG=True), re-reads on every call so authors can
    iterate on copy without restarting the dashboard.
    """
    if os.getenv("IW_CORE_DEBUG", "false").lower() == "true":
        return _load_catalog_uncached()
    return _load_catalog_cached()


def get_copy(check_id: str) -> CheckCopy | None:
    """Return per-check copy or None if not in catalog (test enforces never None in prod)."""
    return load_catalog().get(check_id)
```

Conventions: imports at module top, Pydantic v2 syntax, type-hint everywhere. No silent fallbacks — `get_copy` returns `None` and callers decide what to render.

### 5. `auto_apply_safe` flag on every Finding constructor

Update `skills/iw-oss-publish/scripts/lib/types.py`:

```python
@dataclass
class Finding:
    id: str
    severity: Severity
    status: Status
    domain: str
    summary: str
    detail: str | None = None
    remediation: str | None = None
    auto_fix_available: bool = False
    auto_apply_safe: bool = False        # NEW
    osps_control: str | None = None
    tool: str | None = None
    evidence: dict | None = None
    rationale: str | None = None
```

Then in every check module under `skills/iw-oss-publish/scripts/checks/`, audit each `Finding(...)` constructor and set `auto_apply_safe=True` for checks where the dashboard can safely render the fix without human judgement (template renders, idempotent file writes), and `auto_apply_safe=False` otherwise. Default is `False` so missing assignments are conservative.

Examples:
- `OSS-CH-01` (README missing) → `auto_apply_safe=True` (template render)
- `OSS-CH-02` (SECURITY.md missing) → `auto_apply_safe=True`
- `OSS-CH-03` (CODE_OF_CONDUCT missing) → `auto_apply_safe=True`
- `OSS-LIC-01` (LICENSE missing) → `auto_apply_safe=True`
- `OSS-SEC-*` (secret detected in tree/history) → `auto_apply_safe=False` (no safe auto-apply for secret rotation)
- `OSS-HY-*` (.gitignore patterns) → `auto_apply_safe=True` for additive patches; `False` if requires removing tracked files
- `OSS-CI-*` (missing GitHub workflow) → `auto_apply_safe=True` for new workflow files; `False` if requires modifying existing workflows

When in doubt, default to `False`. Document the rationale in a comment next to the `Finding(...)` call only when non-obvious.

### 6. Persistence: store `auto_apply_safe` on `OssFinding`

Update `orch/oss/persistence.py` (or wherever findings are persisted) to write the `auto_apply_safe` value from the scanned Finding into the new DB column added by S01. The dashboard reads it from the DB row.

### 7. Verification

After authoring:
```bash
uv run python -c "from dashboard.services.oss_check_catalog import load_catalog; print(len(load_catalog()))"
# Expect: count matches the union of scan IDs and AST IDs from step 1
```

Run the scan against this repo and verify findings carry `auto_apply_safe`:
```bash
uv run iw oss scan --project iw-ai-core
jq '.findings[] | {id: .check_id, safe: .auto_apply_safe}' .iw/oss-publish-findings.json | head
```

## Project Conventions

- Pydantic v2 syntax (`field_validator`, `model_validate`).
- YAML uses block scalars (`|`) for multi-line strings.
- Brand voice: read `doc-system/editorial.md` (or equivalent) for tone.
- No comments in catalog YAML beyond the file header — the YAML structure is its own documentation.
- No `print()` debug statements.

## TDD Requirement

Loader unit test (`tests/unit/test_oss_check_catalog_loader.py`) is S17's job. For S05, write a quick smoke check in the report showing `load_catalog()` returns a non-empty dict and every entry validates.

## Output / Report

Report contains:
- Total check IDs enumerated (count + first/last IDs)
- Catalog file size (bytes / lines)
- For each check, a one-line confirmation of `auto_apply_safe` value with rationale
- Sample of three catalog entries copy-pasted so reviewer can spot brand-voice issues quickly
- Manual verification output (load + scan + jq sample)
- Any check IDs that were ambiguous on `auto_apply_safe` and need reviewer judgment

End with `iw step-done` or `iw step-fail`.
