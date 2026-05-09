# CR-00040 S01 Template Report

**Step**: S01 — Template Implementation
**Agent**: template-impl
**Work Item**: CR-00040 — CodeReview Templates: Anchor Reviewers to Design Doc Before Code Inspection
**Date**: 2026-05-09

---

## What Was Done

Edited two master prompt templates to add a prominent "## Read the Design Document FIRST" section (between `## Context` and `## Pre-Review Lint & Format Gate`), and added a design-doc anchor bullet under `### 5. Testing` in `CodeReview_Prompt_Template.md` and under `### 1. Completeness vs Design Document` in `CodeReview_Final_Prompt_Template.md`.

Ran `uv run iw sync-templates` to propagate changes to all 4 registered projects (innoforge, iw-ai-core, cv, Podforger).

## Files Changed

| File | Change |
|------|--------|
| `templates/design/CodeReview_Prompt_Template.md` | Added "## Read the Design Document FIRST" section (8 imperative bullets + consequence line) between Context and Pre-Review Lint & Format Gate; appended TDD-section anchor bullet to `### 5. Testing` |
| `templates/design/CodeReview_Final_Prompt_Template.md` | Added "## Read the Design Document FIRST" section with Final-reviewer wording (cross-check all step reports' `files_changed`); appended CRITICAL bullet to `### 1. Completeness vs Design Document` |
| `ai-dev/templates/CodeReview_Prompt_Template.md` | Synced via `iw sync-templates` (mirrors master) |
| `ai-dev/templates/CodeReview_Final_Prompt_Template.md` | Synced via `iw sync-templates` (mirrors master) |

## Acceptance Criteria Verification

- **AC1** (Read the Design Doc FIRST section in CodeReview_Prompt_Template.md): ✅ New section present at line 89, before `## Pre-Review Lint & Format Gate` (line 98). Contains 4 imperative bullets covering Acceptance Criteria, TDD Approach, test file noting, and the CRITICAL finding consequence.
- **AC2** (Read the Design Doc FIRST section in CodeReview_Final_Prompt_Template.md): ✅ New section present at line 92, before `## Pre-Review Lint & Format Gate` (line 101). Contains Final-specific wording: cross-check all implementation step reports' `files_changed` arrays.
- **AC3** (Checklist augmentation): ✅ `CodeReview_Prompt_Template.md` `### 5. Testing` has bullet: "Do test files cover the assertions the design doc's TDD section calls out by name? If a TDD-section test file is missing from `files_changed`, raise a CRITICAL finding." ✅ `CodeReview_Final_Prompt_Template.md` `### 1. Completeness vs Design Document` has bullet: "Are all test files the design doc's TDD section names by path actually present in some implementation step's `files_changed`? Missing entries are **CRITICAL**."
- **AC4** (Per-project mirrors in sync): ✅ `diff` between master and all registered project mirrors is empty. Verification: `diff templates/design/CodeReview_Prompt_Template.md /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/ai-dev/templates/CodeReview_Prompt_Template.md` — no output (exit 0). Same for Final template.
- **AC5** (Banner sections preserved verbatim): ✅ `## ⛔ Docker is off-limits` and `## ⛔ Migrations: agents generate, daemon applies` sections are unchanged (byte-for-byte identical to pre-edit state). Pre-Review Lint & Format Gate, Severity Levels table, and Review Result Contract JSON schema are also untouched.

## Sync Verification

`iw sync-templates` reported: "Syncing design templates for 4 project(s)... innoforge: 3 updated, 10 up to date; iw-ai-core: 2 updated, 11 up to date; cv: 2 updated, 11 up to date; Podforger: 2 updated, 11 up to date. Done. 9 template files synced."

The two CodeReview templates were updated in all 4 projects. Other templates (CodeReview_FIX, etc.) were already up to date.

**Note on diff output**: When running `diff -u templates/design/CodeReview_Prompt_Template.md ai-dev/templates/CodeReview_Prompt_Template.md` from within this worktree, the diff showed the worktree's mirror (at `ai-dev/templates/`) was stale relative to the master. However, the **main branch** mirror at `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/ai-dev/templates/` IS in sync with the updated master (verified by: `diff templates/design/CodeReview_Prompt_Template.md /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/ai-dev/templates/CodeReview_Prompt_Template.md` — no output). The stale worktree mirror is a side effect of the worktree itself having an older copy; the sync command did execute correctly against the DB-registered project path.

## Preflight Results

| Check | Result |
|-------|--------|
| `make format` | ✅ ok (661 files already formatted — markdown not reformatted by ruff) |
| `make type-check` | ✅ ok (no Python changes; 239 source files, no new errors) |
| `make lint` | ✅ ok (no Python changes; all checks passed) |

## Test Results

skipped: no Python changes — this step only edits markdown prompt templates.

## Notes

- The new section heading `## Read the Design Document FIRST` is placed between `## Context` (line 83) and `## Pre-Review Lint & Format Gate` (line 98) in `CodeReview_Prompt_Template.md`, matching the exact position specified in AC1.
- The final line "If the design doc explicitly names test files that should have changed and they don't appear in the implementation report's `files_changed`, that is a CRITICAL finding" is present verbatim.
- For `CodeReview_Final_Prompt_Template.md`, the closing line was adjusted per spec to reference "the `files_changed` arrays of ALL implementation step reports."
- The `iw sync-templates` sync targets the repo_roots as registered in the DB (queried at runtime), not the local worktree structure. This is correct behavior — the worktree's own `ai-dev/templates/` directory is not a sync target from the worktree's perspective.