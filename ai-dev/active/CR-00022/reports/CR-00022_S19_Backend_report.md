# CR-00022 S19 Backend Report

## Summary

S19 cleanup of dead documentation, references, and local debris from the OSS `make_oss`/`publish` workflow removal (CR-00022).

## Files Deleted

| File | Command |
|------|---------|
| `dashboard/templates/fragments/oss_domain_card.html` | `git rm` |
| `skills/iw-oss-publish/references/history_rewrite.md` | `git rm` |
| `skills/iw-oss-publish/references/fix_recipes.md` | `git rm` |

## Files Modified

| File | Change |
|------|--------|
| `skills/iw-oss-publish/references/modes.md` | Removed `make_oss` and `publish` mode sections; added "Per-finding fix" section documenting `uv run iw oss fix <CHECK_ID> [--apply]` |
| `skills/iw-oss-publish/references/checks.md` | Updated auto-fix column references from `make_oss` to `uv run iw oss fix <CHECK_ID> --apply` |
| `skills/iw-oss-publish/SKILL.md` | Fixed stale `project_description` config row mentioning `make_oss` → `fix` |
| `skills/iw-oss-publish/references/output_format.md` | Updated all make_oss references to use scan/fix modes |
| `dashboard/services/oss_check_catalog.yaml` | Updated 20+ remediation references from `make_oss` to `uv run iw oss fix <CHECK_ID> --apply` |

## Decision: Kept `oss_install_modal.html`

`oss_install_modal.html` is still referenced in `dashboard/routers/oss.py:235`. Per design Notes in the step instructions, kept because the `install` flow remains active.

## Local Debris Cleanup

```bash
# Removed 9 stale worktrees from /tmp/
/tmp/oss-5b3e6186-388e-4e56-8848-71620244cfd5
/tmp/oss-78ecd0b0-1288-4e2a-b9cf-ecdfd275fbf8
/tmp/oss-a2293942-a728-4363-ad7d-c0c6396bb2e9
/tmp/oss-a75bb9d8-9a5c-4c51-be31-67cf3845ebe1
/tmp/oss-aec1c732-4536-433e-9fdd-d897a98d997e
/tmp/oss-afee8def-5561-486a-87fe-a6a754ea8178
/tmp/oss-c99bcf38-e7a7-4f99-b5a4-9f8bc6ff847b
/tmp/oss-e65eb968-2033-44f8-aad3-2dd9822ccf61
/tmp/oss-f7e4b279-1e5f-4b57-b97d-591eb1c8d405

# No iw-oss-publish branches found
git branch --list 'iw-oss-publish*'  # empty

# Worktree list clean
git worktree list  # only main + CR-00022 worktree
```

## Open Items

### 1. Python implementation code still present

The Python scripts in `skills/iw-oss-publish/scripts/` (`scan.py`, `render.py`, `publish.py`, `lib/`) still contain `make_oss` and `publish` implementation code. The S03 report marked these for S19 deletion, but the S19 step instructions did not explicitly include Python script cleanup in scope.

Files with residual implementation:
- `skills/iw-oss-publish/scripts/scan.py` - `run_make_oss()`, `run_publish()` functions
- `skills/iw-oss-publish/scripts/lib/render.py` - template rendering for make_oss
- `skills/iw-oss-publish/scripts/lib/publish.py` - publish mode references
- `skills/iw-oss-publish/scripts/checks/*.py` - remediation strings still reference make_oss

**Recommendation**: Follow-up CR or Sxx to remove the dead Python implementation code.

### 2. Test fixtures still use old enums

Test files (`test_oss_freshness.py`, `test_oss_boundary.py`, `test_oss_dashboard_boundary.py`) create the old `ossscan_mode` enum with `make_oss`/`publish` values for test fixtures. These are not actively testing the old behavior but are setting up test DB state.

**Recommendation**: Low priority - tests pass and are validating removal correctly.

## Verification

```bash
# Worktrees clean
git worktree list
# /home/sergiog/dev/iw-doc-plan/main/iw-ai-core                      1c02f18 [main]
# /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022  99c76df [agent/CR-00022-oss-compliance-per-finding-fix]

# No oss branches
git branch --list 'iw-oss-publish*'  # empty

# /tmp/oss-* worktrees removed
ls /tmp/oss-* 2>/dev/null  # "No such file or directory"
```

## Test Results

- **make lint**: 122 pre-existing errors (not related to this step)
- **make test-unit**: 2 failed, 1649 passed (failures in `test_batch_manager_worktree_hooks.py` and `test_merge_queue.py` - pre-existing, not related to OSS cleanup)

## Historical References (Not Modified)

Per the step instructions, these are historical record and were not modified:
- `docs/IW_AI_Core_Database_Schema.md` lines 700, 836, 840, 873 - document the migration that happened
- `orch/db/migrations/` - migration files documenting schema changes
- Test assertions like `assert "uv run iw oss prepare" not in html` - validate removal happened
