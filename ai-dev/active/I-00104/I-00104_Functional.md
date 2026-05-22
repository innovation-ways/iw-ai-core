# I-00104 — Functional Design

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

This work adds no schema changes and no migrations.

## Why

When an operator opens the Plan tab of a batch, they expect a faithful preview of how the platform will execute it: which items will run in parallel, which will wait, and which conflict with each other. Today, that preview lies in two small but important ways. First, it claims work items have no file conflicts when they actually do — because the preview only matches file paths by exact text, while the live execution engine matches them by directory-style wildcards (the way the rest of the platform handles paths). Second, it always claims the batch is configured to run four items in parallel, regardless of the actual setting. Both errors erode trust and have already misled an operator looking at a real batch this week.

## What Changed (for the User)

- The Plan tab's Dependency Analysis now correctly highlights conflicting files between work items, including the common case where one item declares a whole directory and another declares a file inside it.
- The Warnings section no longer says "all items are independent" when in fact they share files; it lists the actual conflicts instead.
- The "Max Parallel" line in the plan summary now matches the value shown in the batch header and the selector at the top of the Plan tab.

## How It Behaves

When the platform builds a batch's plan — which it does once, when the batch is created — it reads each work item's declared file set and compares them using the same wildcard-aware rules the live engine uses. If two items overlap, both appear in each other's "Overlap With" column and the Warnings section names the conflict. If items are genuinely independent, nothing changes from before. The "Max Parallel" line is now taken straight from the batch's configured value rather than a hard-coded number.

This is a presentation and analysis fix: the live execution engine's behaviour did not need to change. What the operator sees on the Plan tab now matches what the engine actually does at runtime.

## Out of Scope

- Adding any new way to override an overlap warning from the Plan tab. Operators already have the per-file Ignore controls coming in a separate change.
- Teaching the planner to apply per-project allow/block policy. The fix uses the default rules, which match the runtime engine's behaviour for projects that did not customise overlap policy.
