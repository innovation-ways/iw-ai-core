# F-00079 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

This work adds one new migration. The migration is a pure ADD COLUMN change
on two existing tables and is safe to apply online.

## Why

The work-item detail page exposes overview, reports, evidences, logs, and a
generic "Artifacts" tab, but it does not show what the AI agent actually
changed in the codebase. Reviewers have to leave the dashboard and dig into
git history or open the worktree manually to see which files were touched and
how. This forces a context switch every time someone audits an in-progress
run or validates a completed item, and it gets harder once the worktree is
deleted on merge or the item is archived. Reviewers asked for a single
in-page view that answers "what did this item change?" at a glance.

## What Changed (for the User)

- A new "Files" tab replaces the previous "Artifacts" tab on every work item.
- The tab shows a tree of every file the item added, modified, deleted, or
  renamed, with status badges and counts of added/removed lines next to each
  filename.
- Clicking a file shows the unified diff with syntax highlighting; very large
  diffs collapse with a "Load full diff" button so the page stays responsive.
- A toolbar dropdown lets the reviewer switch between "All steps" (the full
  aggregate change) and a single workflow step (e.g., look only at what the
  backend phase did versus the tests phase).
- An "Export PDF" button downloads a branded report containing the file
  summary and per-file diffs, suitable for sharing or attaching to a
  deliverable bundle.
- Untracked files the agent dropped in the worktree (notes, generated docs,
  ad-hoc screenshots) are still reachable through a collapsible
  "Other worktree files" section inside the same tab — nothing reviewers
  used to find under "Artifacts" is lost.
- The tab works for items in any state: while the run is still in progress,
  after merge, and even after the worktree has been cleaned up and the item
  archived.

## How It Behaves

When a reviewer opens the Files tab, the tab pulls the diff from the most
appropriate source for the item's current state. For an item that is still
running, the diff is computed live from the active worktree. For a
completed-not-archived item, it is computed against the squash commit on the
main branch. For an archived item it is loaded from a snapshot stored in the
database at merge time, so no shell or filesystem access is needed.

The tree groups files by directory, with directories first and files
alphabetical within each level. If the item changed ten files or fewer, every
diff is expanded by default; otherwise diffs start collapsed so the reader
can scan the tree first. Generated files (lock files, minified assets) are
always collapsed regardless of the item size, because they rarely add value
to the review.

The step toggle changes which slice of the diff is shown. "All steps" is the
aggregate; selecting a single step shows what that step's commit contributed,
which is useful for understanding which phase introduced a particular change.

If a step produced no commit (for example, a review-only step), the dropdown
still lists it but selecting it shows an empty state. If the entire item
produced no commits yet, the tab shows a friendly empty state rather than an
error.

The PDF export honours the current step selection — exporting from "backend"
view yields a PDF of just that step's diff. Files larger than a sensible
threshold are summarised in the PDF rather than included verbatim, to keep
the document readable. For changesets with more than 100 files, the PDF
body shows the first 100 (alphabetical by path) and notes how many more
appear in the summary table only — this caps render time and document size.

## Out of Scope

- Inline comments or threaded review discussions on diff lines.
- Side-by-side diff layout (unified only in this version).
- Search inside diff content (the filter only matches file paths).
