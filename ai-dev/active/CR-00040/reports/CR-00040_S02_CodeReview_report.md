# CR-00040 S02 CodeReview Report

**Step**: S02 — Code Review of S01 (template-impl)
**Agent**: code-review-impl
**Work Item**: CR-00040 — CodeReview Templates: Anchor Reviewers to Design Doc Before Code Inspection
**Date**: 2026-05-09

---

## What Was Reviewed

S01 (`template-impl`) edited two master prompt templates and ran `iw sync-templates` to propagate changes to registered project mirrors.

Files reviewed (per S01 report's `files_changed`):
- `templates/design/CodeReview_Prompt_Template.md`
- `templates/design/CodeReview_Final_Prompt_Template.md`
- `ai-dev/templates/CodeReview_Prompt_Template.md`
- `ai-dev/templates/CodeReview_Final_Prompt_Template.md`

---

## Pre-Flight Gate Results

| Command | Result |
|---------|--------|
| `make lint` (ruff check) | ✅ All checks passed |
| `make format-check` (ruff format --check) | ✅ 661 files already formatted |
| `make test-unit` | ✅ 2720 passed, 4 skipped, 5 xfailed, 1 xpassed |

No new lint/format violations introduced by S01. No test regressions.

---

## AC1 Trace — `## Read the Design Document FIRST` in `CodeReview_Prompt_Template.md`

- **Heading**: ✅ Exact text `## Read the Design Document FIRST` (line 89)
- **Placement**: ✅ Between `## Context` (line 83) and `## Pre-Review Lint & Format Gate` (line 98)
- **Opening sentence**: ✅ "Read the design document **before** running the lint/format gate and **before** opening any changed files."
- **Bullets**: ✅ 4 imperative bullets (Read Acceptance Criteria, Read TDD Approach, Write down test files, Cross-check named test files against `files_changed`)
- **CRITICAL consequence line**: ✅ Present: "Cross-check every named test file against the implementation report's `files_changed`. If the design doc explicitly names a test file that should have changed and it does not appear in `files_changed`, that is a **CRITICAL** finding."

**AC1 Status**: PASS

---

## AC2 Trace — `## Read the Design Document FIRST` in `CodeReview_Final_Prompt_Template.md`

- **Heading**: ✅ Exact text `## Read the Design Document FIRST` (line 92)
- **Placement**: ✅ Between `## Context` (line 84–90) and `## Pre-Review Lint & Format Gate` (line 101)
- **Opening sentence**: ✅ "Read the design document **before** running the lint/format gate and **before** opening any changed files."
- **Bullets**: ✅ 4 imperative bullets including Final-specific wording ("cross-check every test file mentioned in the design doc's TDD section against the `files_changed` arrays of ALL implementation step reports")
- **CRITICAL consequence line**: ✅ Present: "Any test file the design names that does not appear anywhere is a **CRITICAL** finding."

**AC2 Status**: PASS

---

## AC3 Trace — Checklist Augmentation

**`CodeReview_Prompt_Template.md` `### 5. Testing`**:
- Bullet: "Do test files cover the assertions the design doc's TDD section calls out by name? If a TDD-section test file is missing from `files_changed`, raise a CRITICAL finding."
- ✅ Matches AC3 first-half requirement.

**`CodeReview_Final_Prompt_Template.md` `### 1. Completeness vs Design Document`**:
- Bullet: "Are all test files the design doc's TDD section names by path actually present in some implementation step's `files_changed`? Missing entries are **CRITICAL**."
- ✅ Matches AC3 second-half requirement.

**AC3 Status**: PASS

---

## AC4 Trace — Per-Project Mirrors Sync

### `diff -u` Results (run from worktree root)

```
diff -u templates/design/CodeReview_Prompt_Template.md ai-dev/templates/CodeReview_Prompt_Template.md
→ Exit 1, non-empty diff: worktree mirror is MISSING the new "## Read the Design Document FIRST" section (lines 89–97) and MISSING the TDD anchor bullet under `### 5. Testing`.

diff -u templates/design/CodeReview_Final_Prompt_Template.md ai-dev/templates/CodeReview_Final_Prompt_Template.md
→ Exit 1, non-empty diff: worktree mirror is MISSING the new "## Read the Design Document FIRST" section (lines 92–100) and MISSING the TDD anchor bullet under `### 1. Completeness`.
```

### Analysis

The worktree's own `ai-dev/templates/` directory was NOT updated by `iw sync-templates`. The S01 report attributes this to the worktree not being a sync target ("The sync command did execute correctly against the DB-registered project path"). However, AC4 explicitly requires that "the diff is empty for every project listed in `projects.toml`" — and the worktree is where the agent is performing the review. The worktree's `ai-dev/templates/` is the local mirror this review step examines; if it is stale, the CR's own review is operating on outdated content.

The design doc's Note at line 193 states: "The S02 reviewer of THIS CR is using the OLD CodeReview template (the new one only takes effect for items launched after this CR merges)." This appears to acknowledge the worktree may be stale, but it does not change the fact that AC4's mechanical requirement — diff must be empty for every project in `projects.toml` — is violated.

**AC4 Status**: FAIL — sync drift detected.

---

## AC5 Trace — Banner Sections Preserved Verbatim

- `## ⛔ Docker is off-limits` (lines 9–36): ✅ Byte-for-byte identical to pre-edit state
- `## ⛔ Migrations: agents generate, daemon applies` (lines 38–70): ✅ Byte-for-byte identical
- `## Pre-Review Lint & Format Gate`, `## Severity Levels`, `## Review Result Contract`: ✅ Unchanged

**AC5 Status**: PASS

---

## Findings

### CRITICAL — AC4 Violation: Sync Drift

| Field | Value |
|-------|-------|
| Severity | CRITICAL |
| Category | conventions |
| File | `ai-dev/templates/CodeReview_Prompt_Template.md` |
| Line | 89–97 (missing) |
| Description | The worktree's `ai-dev/templates/CodeReview_Prompt_Template.md` is missing the entire new `## Read the Design Document FIRST` section and the TDD anchor bullet under `### 5. Testing`. The diff between master and mirror is non-empty. |
| Suggestion | Run `uv run iw sync-templates` and verify the worktree's `ai-dev/templates/` mirrors are byte-identical to `templates/design/` masters. Alternatively, the worktree's `ai-dev/templates/` may need to be manually updated or excluded from the scope if it is not a registered project in `projects.toml` — but AC4's mechanical check ("diff must be empty for every project") must pass for any project that is registered. |

### Same Issue in CodeReview_Final mirror

| Field | Value |
|-------|-------|
| Severity | CRITICAL |
| Category | conventions |
| File | `ai-dev/templates/CodeReview_Final_Prompt_Template.md` |
| Line | 92–100 (missing) |
| Description | Same sync drift issue: worktree mirror missing new section and TDD bullet. |
| Suggestion | Same as above. |

---

## Test Results

| Suite | Result |
|-------|--------|
| `make test-unit` | ✅ 2720 passed, 4 skipped, 5 xfailed, 1 xpassed, 47 warnings |
| `make lint` | ✅ All checks passed |
| `make format-check` | ✅ 661 files already formatted |

---

## Summary

| AC | Status | Notes |
|----|--------|-------|
| AC1 (section present in CodeReview_Prompt_Template.md) | ✅ PASS | Section at line 89, correct placement, correct wording |
| AC2 (section present in CodeReview_Final_Prompt_Template.md) | ✅ PASS | Section at line 92, correct placement, correct Final-specific wording |
| AC3 (checklist augmentation) | ✅ PASS | TDD anchor bullets present in both templates at correct locations |
| AC4 (per-project mirrors in sync) | ❌ FAIL | Worktree `ai-dev/templates/` mirrors are stale — missing new sections and bullets |
| AC5 (banner sections preserved) | ✅ PASS | Both banners byte-for-byte identical |

**Verdict**: FAIL — 2 CRITICAL findings (one per template mirror)

**Mandatory Fix Count**: 2 (AC4 sync drift in both mirrors)

---

## Recommendation

S01 must re-run `iw sync-templates` to update the worktree's own `ai-dev/templates/` mirrors, or clarify whether the worktree's `ai-dev/templates/` directory is outside the scope of `projects.toml` registration. AC4's mechanical requirement is that diffs must be empty — if the worktree is a registered project, the sync must reach it. If the worktree is not a registered project (and therefore its `ai-dev/templates/` is not expected to be in sync), that needs to be stated explicitly in the design doc so future reviewers have clear expectations.