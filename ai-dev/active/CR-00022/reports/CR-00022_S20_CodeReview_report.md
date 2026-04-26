# CR-00022 S20 Code Review Report

## Summary

Code review of S19 (Phase F — cleanup). Live code paths are clean. One open item from S19 (dead Python implementation in skill scripts) remains unaddressed.

---

## Checklist Results

### 1. No residual references to old flow ✅

Grep hits outside `ai-dev/active/CR-00022/` fall into categories:

| Category | Examples | Finding |
|----------|----------|---------|
| Historical schema docs | `docs/IW_AI_Core_Database_Schema.md:836` — documents the migration that dropped `make_oss`/`publish` | OK — historical record |
| Migration files | `orch/db/migrations/versions/c062b6bf5eb3_cr_00022_oss_redesign_*.py` | OK — migration provenance |
| Test assertions verifying removal | `assert "uv run iw oss prepare" not in html` | OK — validates deletion |
| `.pyc` bytecode cache files | Compiled from old test runs | OK — harmless stale cache |
| **Skill Python scripts (dead code)** | `skills/iw-oss-publish/scripts/scan.py:154` (`run_make_oss`), `scan.py:363` (`run_publish`), `scripts/lib/publish.py`, `scripts/lib/render.py` | ⚠️ See item 3 |

**No HIGH findings** — all hits are either historical documentation, tests validating removal, or known dead code.

### 2. Worktree / branch cleanup ✅

```bash
git worktree list --porcelain | grep -i oss-  # empty
git branch --list 'iw-oss-publish*'             # empty
ls .git/worktrees/oss-* 2>/dev/null             # No such file
```

Clean — no remaining `oss-` prefixed worktrees or branches.

### 3. Skill / docs consistency ⚠️ MEDIUM (pre-existing open item)

| File | Status | Notes |
|------|--------|-------|
| `skills/iw-oss-publish/SKILL.md` | ✅ Updated | No `make_oss`/`publish` references; mentions scan + Phase C fix |
| `skills/iw-oss-publish/references/modes.md` | ✅ Updated | `make_oss`/`publish` sections removed |
| `skills/iw-oss-publish/references/checks.md` | ✅ Updated | Auto-fix references updated to `iw oss fix` |
| `skills/iw-oss-publish/references/output_format.md` | ✅ Updated | References updated |
| `docs/IW_AI_Core_CLI_Spec.md` | ✅ Updated | No `prepare`/`publish`; `iw oss fix` listed |
| `docs/IW_AI_Core_Architecture.md` | ✅ Clean | No stale OSS workflow references |
| **`skills/iw-oss-publish/scripts/scan.py`** | ⚠️ Dead code | Still defines `run_make_oss()` (line 154) and `run_publish()` (line 363); still accepts `make_oss`/`publish` as `--mode` choices (line 126) |
| **`skills/iw-oss-publish/scripts/lib/publish.py`** | ⚠️ Dead code | 409-line module for removed publish mode |
| **`skills/iw-oss-publish/scripts/lib/render.py`** | ⚠️ Dead code | Template rendering for make_oss |

**This was explicitly documented as an open item in S19** (CR-00022_S19_Backend_report.md):
> "Python implementation code still present in `skills/iw-oss-publish/scripts/` (`scan.py`, `render.py`, `publish.py`)... Recommendation: Follow-up CR or Sxx to remove the dead Python implementation code."

The dead code is **not executed** — the live orchestrator (`orch/oss/`) was properly cleaned in S03 and routes through `run_scan(project, "scan")`. However, agents reading `scan.py --help` would see misleading mode choices, and the dead functions create maintenance confusion.

**Verdict**: MEDIUM finding, pre-existing open item. Recommend a follow-up cleanup pass to strip `run_make_oss`, `run_publish`, and related dead code from the skill scripts.

### 4. Conditional deletes ✅

- `oss_install_modal.html` — **retained** as expected (install flow still active)
- Referenced in `dashboard/routers/oss.py:235`
- No template includes it → no orphaned references

### 5. Tests still green ✅

```
make test-unit: 2 failed, 1649 passed
FAILED tests/unit/daemon/test_batch_manager_worktree_hooks.py::TestTerminalTransitionComposeDown::test_terminal_transition_calls_compose_down
FAILED tests/unit/test_merge_queue.py::TestMergeItem::test_rebase_success_continues_to_dry_run_with_worktree_path
```

Both failures are **pre-existing** (identical to S19 report). Not related to OSS cleanup.

### 6. No accidental deletions ✅

- `dashboard/utils/oss_copy.py` — retained (modified, not deleted)
- `DOMAIN_CONTEXT` + `SEVERITY_IMPACT` still imported by routers ✅
- `oss_install_modal.html` — not deleted ✅
- No unintended file removals in git status

---

## Verdict

**PASS** — Live code paths are clean; the system is correctly operating in scan-only mode. One pre-existing open item (dead Python code in skill scripts) does not block approval but should be addressed in a follow-up cleanup pass.

| Finding | Severity | Status |
|---------|----------|--------|
| Dead Python in `skills/iw-oss-publish/scripts/` | MEDIUM | Pre-existing open item (S19) |
| All other checklist items | — | ✅ PASS |

---

## Recommendation

Approve S19. Schedule a follow-up cleanup pass to remove dead implementation from `skills/iw-oss-publish/scripts/scan.py`, `scripts/lib/publish.py`, and `scripts/lib/render.py`.
