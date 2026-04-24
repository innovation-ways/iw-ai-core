# CR-00019_S03_Backend_prompt

**Work Item**: CR-00019 -- Selection-driven OSS Prepare with reviewable worktree lifecycle
**Step**: S03
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

No docker mutation commands. Testcontainers + read-only `docker ps/inspect/logs` are allowed. `./ai-core.sh` and `make` are allowed.

## ⛔ Migrations: agents generate, daemon applies

No `alembic upgrade/downgrade/stamp` against the live DB.

## Input Files

- `ai-dev/active/CR-00019/CR-00019_CR_Design.md` — read Desired Behavior, AC1/AC4/AC13, and Notes on skill mirror sync
- `skills/iw-oss-publish/scripts/scan.py` — current `run_make_oss` at lines 158-305
- `skills/iw-oss-publish/scripts/lib/types.py` — `Finding` dataclass (~line 25)
- `skills/iw-oss-publish/scripts/checks/*.py` — all 14 check modules that emit findings
- `skills/iw-oss-publish/scripts/lib/fixes.py` — `apply_fix` registry
- `orch/oss/persistence.py` — how scanner output maps to `OssFinding` rows (rationale must pass through here)
- `orch/db/models.py` — `OssFinding.rationale` added in S01
- `.claude/skills/iw-oss-publish/` — mirror directory; every edit under `skills/` must be copied here

## Output Files

- Modified files under `skills/iw-oss-publish/`
- Mirrored copies under `.claude/skills/iw-oss-publish/`
- `orch/oss/persistence.py` updates to persist the new field
- `skills/iw-oss-publish/README.md` updated
- `ai-dev/work/CR-00019/reports/CR-00019_S03_Backend_report.md`

## Context

You are updating the OSS compliance **skill** so it (a) accepts a `--check` filter in make_oss mode, (b) drops the four unconditional always-try fixes, and (c) emits a new per-check `rationale` field on every `Finding`. The `orch/oss/persistence.py` mapper and the `Finding.to_dict()` path must carry the new field through to the `OssFinding` table.

You are **not** touching the CLI entry point (`orch/cli/oss_commands.py`) or the dashboard worker — those are S05.

## Requirements

### 1. `Finding` dataclass (`skills/iw-oss-publish/scripts/lib/types.py`)

Add one new field with a default value:

```python
@dataclass
class Finding:
    ...
    auto_fix_available: bool = False
    osps_control: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    tool: str | None = None
    source_research: list[str] = field(default_factory=list)
    rationale: str = ""   # NEW — why this check exists, risk it mitigates, who's affected
```

Update `to_dict()` to include `"rationale": self.rationale`.

**Do NOT add** `osps_control_url` as a field. The URL is derived at render time in Jinja from `osps_control`; do not duplicate it in data.

### 2. Rationale content — every check in `scripts/checks/*.py`

For every `Finding(...)` constructor in every check module, add a `rationale="..."` kwarg. One paragraph (2–4 sentences) per check, in your own words, covering:

- **Why this check exists** — what risk it mitigates.
- **Who is affected if it's wrong** — downstream consumers, the project itself, end users, or operators.
- **What class of vulnerability / policy failure** it guards against (licensing exposure, credential leak, supply-chain attack, privacy, etc.).

Tone: calm and explanatory, not preachy. 2-to-4 sentences. The text will render in a details modal next to the remediation block.

Coverage (by module):
- `ci_cd.py`
- `community.py`
- `contributor.py`
- `dependencies.py`
- `environment.py`
- `export_control.py`
- `github.py`
- `governance.py`
- `history.py`
- `hygiene.py`
- `internal_refs.py`
- `license_check.py`
- `privacy.py`
- `release.py`
- `secrets.py`
- `trademark.py`

Every emitted `Finding` must carry a non-empty rationale. Default-empty `rationale=""` is acceptable ONLY for future checks added after this CR; every check that exists today must be authored.

### 3. `run_make_oss` filter (`skills/iw-oss-publish/scripts/scan.py`)

At `scan.py:158`:

1. Add a `check_ids: set[str] | None = None` parameter to `run_make_oss(ctx, args)` — read it from `args.checks` (where `args.checks` is a new argparse option — see step 4).
2. In the baseline-findings loop (currently `scan.py:242-249`), apply the filter:
   - If `check_ids` is None → legacy behavior (every fail/human_required + auto_fix_available finding is eligible).
   - If `check_ids` is a set → only include findings whose `f.id in check_ids`.
3. **Delete the always-try block** at `scan.py:252-256` entirely. The four fixes (`OSS-ENV-03`, `OSS-ENV-04`, `OSS-SEC-04`, `PRE-COMMIT-CONFIG`) no longer apply unconditionally.
4. When `check_ids` is provided, the baseline scan is still run (needed to determine which findings are auto-fixable at all), but `applied` skips anything not in the set.

### 4. argparse `--check` repeatable flag (`skills/iw-oss-publish/scripts/scan.py`)

Find the argparse setup (search for `mode=`, around `scan.py:120-148`). Add:

```python
parser.add_argument(
    "--check",
    dest="checks",
    action="append",
    default=None,
    help="(make_oss) Apply only the specified check ID. Repeat for multiple IDs.",
)
```

When `args.checks` is set and `args.mode == "make_oss"`, pass it (as a set) to `run_make_oss`.

### 5. Validation — empty or wrong-mode selection

- When `args.mode != "make_oss"` but `--check` is passed, print a warning to stderr and exit 2 (misuse).
- When `args.mode == "make_oss"` and `--check` is **not** passed, print an error to stderr explaining that at least one `--check` is required, and exit 2. (The CLI wrapper in S05 will enforce this first, but the skill itself must also guard, because it's invoked directly in tests and could be called standalone.)

### 6. Persist `rationale` — `orch/oss/persistence.py`

Inspect how the scanner JSON output is mapped to `OssFinding` rows. Add `rationale=finding_dict.get("rationale")` to the row insert. If the column is NULL, that's fine — pre-existing scans from before the migration will have NULL and the UI will fall back to `detail`.

### 7. Skill mirror sync

Every edit under `skills/iw-oss-publish/` must be copied to `.claude/skills/iw-oss-publish/`. Use `cp` or a short shell block:

```bash
rsync -a --delete skills/iw-oss-publish/ .claude/skills/iw-oss-publish/
```

Verify with a diff afterward.

Do **not** attempt to push the change to IW-AI-DEV or InnoForge — that's an operator-invoked `iw skills sync` after merge. Mention in your report.

### 8. README update

Edit `skills/iw-oss-publish/README.md`:

- Document `--check <ID>` flag with an example.
- Note that the previous always-try list (OSS-ENV-03, OSS-ENV-04, OSS-SEC-04, PRE-COMMIT-CONFIG) is **no longer applied unconditionally**; each surfaces as a regular finding and must be explicitly selected.

## Project Conventions

Read `CLAUDE.md` and `orch/CLAUDE.md`. Match existing code style:
- Python typing with modern syntax (`set[str] | None`, `str | None`).
- No `from typing import Set, Optional` — use built-ins + `|` unions.
- Snake_case for vars and functions, PascalCase for classes.
- Logger per module (`logger = logging.getLogger(__name__)`).

## TDD Requirement

Tests for the skill layer land in S11, but for this step:

1. **RED**: Write unit tests for:
   - `Finding.to_dict()` includes `rationale`.
   - `run_make_oss` with `check_ids={"OSS-LIC-01"}` only applies `OSS-LIC-01`, not `OSS-LIC-06`, not `OSS-ENV-03`.
   - argparse parses `--check A --check B` into `{"A", "B"}`.
   - argparse rejects `--check` outside make_oss mode.
   - argparse rejects make_oss without any `--check`.
2. **GREEN**: Make them pass.
3. **REFACTOR**.

## Test Verification (NON-NEGOTIABLE)

Before reporting completion:
1. `make test-unit` — zero failures.
2. `make lint` — clean.
3. `uv run mypy orch/ dashboard/` — clean (skill files aren't in the mypy target, but verify imports from `orch/oss/persistence.py` still type-check).
4. Verify mirror diff is zero: `diff -rq skills/iw-oss-publish/ .claude/skills/iw-oss-publish/ | grep -v __pycache__`.
5. Run your new unit tests — all pass.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "backend-impl",
  "work_item": "CR-00019",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "skills/iw-oss-publish/scripts/lib/types.py",
    "skills/iw-oss-publish/scripts/scan.py",
    "skills/iw-oss-publish/scripts/checks/*.py (list each file actually edited)",
    "skills/iw-oss-publish/README.md",
    ".claude/skills/iw-oss-publish/ (mirror)",
    "orch/oss/persistence.py",
    "tests/unit/test_cr_00019_skill_rationale_and_filter.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Mirror sync verified; IW-AI-DEV and InnoForge sync is deferred to operator-run iw skills sync post-merge."
}
```
