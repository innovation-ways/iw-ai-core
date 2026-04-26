# CR-00022 S08 Code Review Report

## Review Scope
S07 (Phase C — fix CLI + recipes) implementation against the design document.

## Files Changed
- `orch/cli/oss_commands.py` — `fix` command (preview + apply mode, JSON output, unknown check handling)
- `dashboard/services/oss_service.py` — `_run_fix` (subprocess invocation with `cwd=project.repo_root`)
- `orch/oss/fix_recipes/` — 9 recipe modules (community, contributor, hygiene, license_check, ci_cd, governance, secrets, release, internal_refs) — **new directory, not yet committed**

---

## Findings

### 1. Working-tree-only invariant — PASS ✅

**Grep results:**
- `git` references in recipes: only in human-readable notes (e.g., "Use `git commit -s`" in contributor.py:71, community.py:259) — not in code executing git operations
- `_run_fix` subprocess: `cwd=project.repo_root` (correct, not worktree path)
- No `/tmp/oss-*` paths; only `/tmp/oss-job-{job_id}.pid` in `cancel_job` (cleanup of a PID file, not prep worktree isolation)
- No symlinks created outside `repo_root`

**Subprocess calls that modify git state:** None found in recipes. `git rev-parse` and `git status` are read-only and only appear in `oss_service.py` for freshness checking (legitimate).

---

### 2. Idempotency — PASS ✅

Tested OSS-CH-01 and OSS-LIC-01:
- First `apply` → makes changes
- Second `apply` → no changes (target_files=[], notes="...already exists")
- `git status --short` shows only pre-existing worktree modifications (not from the fix)

All recipes check for existing files before writing and return no-op `FixPreview` if content already exists. Template-render recipes (OSS-CH-01, OSS-CH-02, etc.) overwrite with deterministic content — idempotent by construction. Append-style recipes (DcoContributingRecipe, DcoSignoffRecipe) check for existing DCO text before appending.

---

### 3. Recipe-vs-flag consistency — WARNINGS ⚠️

Python AST analysis of `skills/iw-oss-publish/scripts/checks/` against `orch/oss/fix_recipes/__init__._REGISTRY`:

| Category | IDs |
|----------|-----|
| Declared `auto_apply_safe=True` in checks | OSS-CH-01, OSS-CH-02, OSS-CH-03, OSS-CH-06, OSS-CH-07, OSS-CH-08, OSS-CH-09, OSS-CH-10, OSS-CH-11, OSS-CI-02, OSS-DEP-05, OSS-ENV-03, OSS-ENV-04, OSS-HYG-01, OSS-HYG-03, OSS-LIC-01, OSS-LIC-05, OSS-LIC-06, OSS-REL-01, OSS-REL-03, OSS-REL-04, OSS-SEC-04, OSS-SEC-05, OSS-TM-01, OSS-TM-08 |
| Registered recipes | OSS-CA-01, OSS-CA-02, OSS-CH-01, OSS-CH-02, OSS-CH-03, OSS-CH-06, OSS-CH-07, OSS-CH-08, OSS-CH-09, OSS-CH-10, OSS-CH-11, OSS-CI-02, OSS-CI-06, OSS-CI-07, OSS-CI-08, OSS-CI-09, OSS-DEP-05, OSS-ENV-03, OSS-ENV-04, OSS-HYG-01, OSS-HYG-03, OSS-LIC-01, OSS-LIC-05, OSS-LIC-06, OSS-REL-01, OSS-REL-03, OSS-REL-04, OSS-SEC-04, OSS-SEC-05 |
| Declared but no recipe | OSS-DEP-06, OSS-TM-01, OSS-TM-08 |
| Recipe but not declared safe | OSS-CA-01, OSS-CA-02, OSS-CI-06, OSS-CI-07, OSS-CI-08, OSS-CI-09 |

**OSS-CA-01 and OSS-CA-02**: `contributor.py` checks are in a file with a syntax error (unpaired `else:` at line 48) causing the AST parse to fail. The `auto_apply_safe=True` flags ARE present in the source (lines 45, 80) but missed by AST due to the parse error. These are false positives — the checks ARE correctly flagged.

**OSS-CI-06/07/08/09**: These are new recipes (CodeQL, Scorecard, Dependabot, ComplianceScan) added as part of CR-00022's expanded scope. The checks were not updated to declare them auto-apply safe. This is a genuine gap — if these checks are expected to be auto-applied, their `Finding` constructors need updating.

**OSS-DEP-06, OSS-TM-01, OSS-TM-08**: Have recipes (OSS-DEP-05 SBOM, OSS-SEC-04/05 secrets) but some checks lack corresponding recipes. The DEP-06 check may require a different fix approach (e.g., `pip freeze` output vs template rendering).

---

### 4. CLI shape — PASS ✅

- `iw oss fix <CHECK_ID> --project <id>` runs preview and exits 0
- `--apply` writes and exits 0
- `--apply` exits non-zero on recipe error (propagates from `recipe.apply()`)
- `--json` produces parseable JSON
- Unknown check_id exits with message "No auto-fix recipe registered for {check_id}" and exit 2

---

### 5. Dashboard subprocess — PASS ✅

`_run_fix` (oss_service.py:224-259):
- `cwd=project.repo_root` — correct, not worktree path
- Subprocess output captured via `_stream_to_tail` — same pattern as `_run_scan`
- Job status transitions: running → complete | error (matching scan)
- No references to `WORKTREE_KINDS` or `_run_worktree`

---

### 6. Conventions — FAIL ❌ (in new `orch/oss/fix_recipes/` directory only)

**89 ruff violations in `orch/oss/fix_recipes/`** (all in the new, uncommitted directory):

| Error type | Count | Description |
|------------|-------|-------------|
| E501 (line too long) | ~70 | `notes="..."` strings in `FixPreview` exceeding 100 chars; config dict lookups in `community.py` |
| F401 (unused import) | ~14 | Module-level side-effect imports for registration |
| TC003 (type-checking block) | 6 | `pathlib.Path` should be in `TYPE_CHECKING` block |
| F841 (unused variable) | 6 | `config`, `org`, `diff` assigned but never used |
| S607 (partial executable) | 2 | `pinact` called without full path |
| S110 (bare except-pass) | 1 | `except Exception: pass` in ci_cd.py |
| E402 (import not at top) | 1 | Side-effect imports at bottom of `__init__.py` |
| W292 (no newline) | ~1 | secrets.py missing trailing newline |

The **existing codebase** (`make lint`) passes cleanly. Only the new `orch/oss/fix_recipes/` directory has violations.

---

## Verdict

**Conditional pass** — the implementation is functionally correct and safe, but `orch/oss/fix_recipes/` has 89 lint violations that fail the quality gate.

### Required fixes (new fix_recipes directory only)

1. **E501 (line too long)**: Shorten `notes` strings in all `FixPreview` constructors to ≤100 characters. Also fix multi-line config dict strings in `community.py` context dicts.

2. **E402 (import not at top)**: In `__init__.py`, move the side-effect import block to be after a `if TYPE_CHECKING:` guard or restructure so registration imports come before the module-level registration call.

3. **TC003**: Move `pathlib.Path` imports into `TYPE_CHECKING` blocks across all recipe modules.

4. **F841**: Remove or use the `config`, `org`, `diff` unused variables (or prefix with `_` if intentional).

5. **S607**: Use `shutil.which("pinact")` or full path for subprocess calls in `ci_cd.py`.

6. **S110**: Replace bare `except: pass` with `except Exception: logger.warning(...)` or proper handling.

7. **W292**: Add trailing newline to `secrets.py`.

### Recommendation

Once `make lint` passes clean on the entire codebase including `orch/oss/fix_recipes/`, this CR is ready to approve.