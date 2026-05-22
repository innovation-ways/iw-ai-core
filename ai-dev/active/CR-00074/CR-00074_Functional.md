# CR-00074 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures used by automated tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This work adds no database change and no migration.

## Why

IW AI Core runs AI-assisted development across multiple registered projects at the same time. The platform's most important correctness guarantee is that one project's data never appears in another project's view — a team working on project B must never see project A's work items, documents, jobs, or any other records. Today there is no automated test that systematically checks this guarantee across the full platform surface. A cross-project data leak is a security and correctness defect that could reach production undetected.

## What Changed (for the User)

- A new automated test suite now verifies that every project-scoped surface — every page, every command, every data boundary — keeps projects strictly separated. Any future change that accidentally lets one project's data bleed into another will be caught immediately before it ships.
- Operators and reviewers get a clear signal when a cross-project isolation rule is broken, named by the exact route or command that leaked, rather than discovering the problem when a real user reports it.
- If a genuine isolation gap already exists on the current code when this work lands, it is recorded on a short "known issue" list with a high-priority tracking ticket, and the check still passes for everything else. From that point on, the check fails only for new gaps.
- A convenience shortcut lets developers run the isolation checks on their own without running the full test suite.
- No visible change to the dashboard or any command behaviour — this is purely a safety net.

## How It Behaves

- On every work item and pull request, the isolation suite spins up an isolated test database, creates two projects, fills each with representative records, and runs a series of checks grouped into four areas.
- The first area checks every project-scoped dashboard page: the suite requests each page as if it belongs to the second project and confirms that no identifier, title, or name from the first project appears in the response.
- The second area checks project-scoped command-line commands: the suite runs each command targeting the second project and confirms it neither reveals nor alters the first project's records.
- The third area checks that the platform's global views — the all-projects documents list and the all-projects jobs view — correctly show data from both projects, confirming the isolation checks are not over-aggressive.
- The fourth area checks the boundary between two database environments the platform maintains for runtime isolation (one per active agent worktree, one for the shared orchestration layer), confirming that queries against one never return rows from the other.

## Out of Scope

- Fixing any isolation gap that is found to already exist on the current code — those are tracked separately as their own high-priority tickets.
- Checking authentication or access control (who is allowed to see a project at all) — that is a separate security concern outside the scope of this data-isolation work.
