---
version: "1.2.0"
name: iw-doc-generator
description: Generate or update documentation for InnoForge modules, architecture areas, release notes, error catalog, or webhook reference. Use when asked to "generate docs", "update documentation", "document module", "document architecture", "generate release notes", "update error catalog", "/iw-doc-generator".
allowed-tools: Read, Grep, Glob, Edit, Write, Bash(git:*), Bash(wc:*), Bash(python3:*)
argument-hint: <target-type> [target-name] (e.g., "module auth", "release-notes v1.2.0", "error-catalog")
---

# InnoForge Documentation Generator

Generate or update documentation for: **$ARGUMENTS**

## Supported Targets

| Target Type | Syntax | Output |
|-------------|--------|--------|
| `module <name>` | `/iw-doc-generator module auth` | Module deep-dive in `docs/architecture/modules/` |
| `release-notes <version>` | `/iw-doc-generator release-notes v1.2.0` | Release notes in `docs/releases/` |
| `error-catalog` | `/iw-doc-generator error-catalog` | Updated `docs/api/ERROR_CATALOG.md` |
| `webhook-reference` | `/iw-doc-generator webhook-reference` | Updated `docs/api/webhooks.md` |

## Step 1: Parse Target

**If `$ARGUMENTS` starts with `doc-job`** (e.g. `doc-job 4914211f-...`): skip directly to the **[Job lifecycle](#job-lifecycle-when-invoked-via-iw-doc-generator-doc-job-job-id)** section at the bottom of this skill. Do not execute Steps 2–6.

Otherwise, extract the target type and name from `$ARGUMENTS`. If ambiguous, ask the user to clarify.

## Step 2: Read Context

Before generating anything, read the relevant source files:

**For module docs:**
1. Read `docs/documentation-strategy.md` section 4.3 for the module doc template
2. Read `src/innoforge/CLAUDE.md` for backend architecture context
3. Read the target module's source files:
   - `src/innoforge/models/{module}.py` (if exists)
   - `src/innoforge/services/{module}_service.py` (if exists)
   - `src/innoforge/repositories/{module}_repository.py` (if exists)
   - `src/innoforge/api/v1/{module}.py` (if exists)
   - `src/innoforge/schemas/{module}.py` (if exists)
4. Read existing tests: `tests/unit/test_{module}*.py`, `tests/integration/test_{module}*.py`
5. Read existing docs in `docs/architecture/modules/{module}.md` (if updating)

**For release notes:**
1. Run `git log --oneline v{previous}..v{version}` to get commits in the release
2. Read `CHANGELOG.md` for git-cliff generated content
3. Read the release-notes template from [references/release-notes-template.md](references/release-notes-template.md)

**For error catalog:**
1. Grep for all exception classes in `src/innoforge/`
2. Grep for all `status_code` assignments and HTTP error returns
3. Read existing `docs/api/ERROR_CATALOG.md`

**For webhook reference:**
1. Grep for event type definitions in `src/innoforge/`
2. Read webhook-related schemas and services
3. Read existing `docs/api/webhooks.md`

## Step 3: Generate Documentation

Use the appropriate template from `references/` directory. Follow these rules:

### Writing Rules (NON-NEGOTIABLE)

1. **Accuracy over completeness** — only document what you can verify from the code. Never guess or hallucinate behavior.
2. **One sentence per description** — column descriptions, component descriptions, config descriptions: one clear sentence each.
3. **Show, don't tell** — use code snippets and Mermaid diagrams instead of long prose.
4. **Use the glossary** — read `docs/glossary.md` (if it exists) and use InnoForge-standard terminology.
5. **Mark generated sections** — add `<!-- generated: {YYYY-MM-DD} -->` comment at the top of generated content.
6. **Active voice, present tense** — "The service validates..." not "The service will validate..."
7. **No marketing language** — technical documentation, not sales material.

### Module Documentation Specifics

For module docs, follow the template in [references/module-doc-template.md](references/module-doc-template.md):

- **Purpose**: One paragraph from the module docstring + your analysis
- **Key Components**: Table of classes/functions with one-line responsibilities
- **Dependencies**: What this module imports from and what imports from it (use Grep)
- **Data Flow**: Mermaid diagram showing request flow through the layers
- **Configuration**: Extract from settings.py or system_config references
- **Extension Points**: How to customize behavior (e.g., subclass, config, plugin)

### Release Notes Specifics

- Group commits by type (feat, fix, refactor, etc.)
- Highlight breaking changes prominently
- Add one-sentence human-readable context per notable change
- Link to relevant documentation for new features

## Step 4: Write Output

- Module docs → `docs/architecture/modules/{module}.md`
- Release notes → `docs/releases/{version}.md`
- Error catalog → `docs/api/ERROR_CATALOG.md`
- Webhook reference → `docs/api/webhooks.md`

If the file already exists, update it (preserve any human-authored sections marked with `<!-- human-authored -->`).

## Step 5: Verify

1. Check that all internal links in the generated doc are valid (files exist)
2. Check that all referenced source files exist
3. Run `wc -l` on the output and report the size

## Step 6: Report

Present to the user:
- What was generated/updated
- Files created or modified
- Any gaps found (e.g., undocumented functions, missing tests)
- Suggested commit message: `docs(<scope>): update <target> documentation`

## Constraints

- **NEVER** invent API endpoints, configuration keys, or behaviors not present in the code
- **NEVER** copy large blocks of source code into docs (reference file paths instead)
- **NEVER** modify source code — this skill only generates documentation
- **NEVER** generate documentation for modules that don't exist
- If a module has no tests, note this as a gap but still generate the documentation

## Job lifecycle (when invoked via `/iw-doc-generator doc-job <job-id>`)

When this skill is invoked by the platform's `DocJobPoller` (i.e. the slash command `/iw-doc-generator doc-job <job-id>` is issued), you are running inside a queued documentation generation job. Your responsibilities:

1. **Read the job context.** Run `uv run iw doc-job-status <job-id> --json`. The JSON output gives you `editorial_category`, `doc_id`, `project_id`, `doc_title`, `section_guides_snapshot`, and `guide_snapshot` — everything you need to produce the right content. If this command exits non-zero, do NOT proceed — close the job immediately with `iw doc-job-done <job-id> --error 'job context not found'`.

2. **Generate the document content** following the editorial guide rules described in the rest of this skill.

   **OUTPUT FORMAT — NON-NEGOTIABLE:**
   - Output **plain Markdown** only. NEVER output JSON, XML, or any structured data format.
   - Diagrams MUST be embedded as fenced Mermaid code blocks directly in the Markdown:
     ````
     ```mermaid
     flowchart TB
         A["Node A"] --> B["Node B"]
     ```
     ````
   - For `doc_type=diagram` or `editorial_category=diagram`: the entire document MUST consist of Markdown headings, prose context, and `\`\`\`mermaid` code blocks. No JSON wrappers. No "diagrams array". Just Markdown.
   - Each diagram MUST be preceded by a blockquote explaining **why** the reader should look at it:
     ```
     > **Why this diagram?** Use this to understand X when Y.
     ```
   - For flowchart diagrams, add ELK layout frontmatter inside the fence:
     ````
     ```mermaid
     ---
     config:
       layout: elk
     ---
     flowchart TB
         ...
     ```
     ````
   - Verify classDef names do not collide with node IDs — if you name a node `data`, do NOT also name a classDef `data`. Use distinct names like `dbstyle` or `dbcls`.

3. **Persist content via `iw doc-update`:**
   ```
   uv run iw doc-update <doc-id> \
     --content-file - \
     --generated-by skill:<this-skill-name> \
     --trigger-reason job:<job-id>
   ```
   `<doc-id>` is the inner `ProjectDoc.doc_id` slug (e.g. `code-index`) returned by `iw doc-job-status`, NOT the UUID. Project is auto-resolved from the worktree's `.iw-orch.json` — do not pass project as a positional arg (the CLI accepts only `<doc-id>` and will reject extra positionals). Pipe markdown via stdin. Run this exactly once for the job's target doc. Do NOT call `iw doc-update` for any unrelated doc.

4. **Close the job** by calling EXACTLY ONE of:
   - `uv run iw doc-job-done <job-id>` — on success
   - `uv run iw doc-job-done <job-id> --error '<one-line message>'` — on failure

   Failing to close the job leaves it in `running` until the daemon's PID-liveness probe (within ~60s if your process exits) or the 15-minute wall-clock stall guard kicks in. Always close.

5. **Do NOT call `iw item-status`, `iw step-start`, `iw step-done`, or any work-item-oriented CLI commands.** Doc jobs are not work items. Mistakenly calling these will succeed-but-do-nothing for the job's outcome.
