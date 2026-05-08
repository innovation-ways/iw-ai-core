---
description: Execute a documentation generation job (e.g., /doc-job 727a12bd-...). Reads job context via `iw doc-job-status`, selects the doc-generation skill by editorial category, generates content via `iw doc-update`, closes via `iw doc-job-done`.
agent: build
---

Execute the documentation generation job specified by `<job-id>`.

1. Read job context: `uv run iw doc-job-status <job-id> --json`. The output includes `editorial_category`, `doc_id`, `project_id`, `doc_title`, `section_guides_snapshot`, and `guide_snapshot`. If the command exits non-zero, IMMEDIATELY close the job: `uv run iw doc-job-done <job-id> --error 'job context not found'` — do NOT proceed.
2. Select the skill based on `editorial_category`:
   - `guide`, `compliance`, `marketing`, `release` → `iw-doc-system`
   - everything else → `iw-doc-generator`
3. Invoke the chosen skill with the job context. The skill is responsible for:
   - producing markdown content
   - persisting it via `iw doc-update <doc-id> --content-file - --generated-by skill:<skill> --trigger-reason job:<job-id>` (project auto-resolved from the worktree's `.iw-orch.json`; `<doc-id>` is the inner `ProjectDoc.doc_id` slug, NOT the UUID)
   - closing the job via `iw doc-job-done <job-id>` on success or `iw doc-job-done <job-id> --error '<short message>'` on failure.
4. ALWAYS terminate by calling `iw doc-job-done` exactly once. Never leave the job in `running` state.
