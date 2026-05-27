# CR-00089 — Functional Design

<!--
Audience: humans (product owners, support, onboarding engineers).
DO NOT include file paths, class names, SQL, code fences, or implementation
steps. If you need to capture those, they belong in the technical design doc.
Keep the total body at most 500 words (the review skill blocks >500).
-->

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

This item adds no migrations. No schema changes.

## Why

After incident I-00113 spent five days cycling between fix attempts and scope
violations, a root cause analysis identified three compounding defects in the
automated fix pipeline. Each defect independently causes a work item to stall
indefinitely and require operator intervention to unstick. Left unfixed, every
future item that touches global project files (such as a test baseline list)
or that runs long-duration quality checks will face the same loop.

## What Changed (for the User)

- Global project files that any item may legitimately need to update can now
  be declared once in project configuration. Items no longer get stuck because
  the pipeline refuses to touch a file that was never in the item's scope list.

- The pipeline now recognises when a quality check has already finished
  successfully before performing a crash check. A clean-finish that was
  previously misread as a crash no longer launches a pointless fix attempt.

- When an automated fix only changed a configuration or data file (not source
  code), the pipeline no longer re-runs code-quality checks that are irrelevant
  to those files. This reduces unnecessary wait time after each fix cycle.

## How It Behaves

When a fix cycle completes, the pipeline first checks what files were changed.
If all changes are to data or configuration files, code-quality checks such as
style and type-checking are skipped from the cascade reset — only checks that
actually inspect those file types are re-queued. Checks that only care about
source code are left in their already-passing state.

When the pipeline polls a running check and finds the process has exited, it
now first asks whether the check already reported a clean result. If it did,
no crash is recorded and no fix cycle is started.

When a fix cycle agent edits a file that is listed in the project's global
always-allowed list, that edit is accepted without a scope violation, regardless
of whether the file was declared in the individual item's scope manifest.

Edge cases: if the pipeline cannot determine what files were changed, it falls
back to resetting all relevant checks (the previous behavior). If a project has
no global always-allowed files configured, behavior is unchanged.

## Out of Scope

- Changing the maximum number of fix cycles allowed per item or per gate.
- Adding new quality gates or modifying existing gate commands.
- Any changes to the dashboard or operator-facing UI.
