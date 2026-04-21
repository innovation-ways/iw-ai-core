# CR-00011 S02 Frontend Report

## What Was Done

Implemented S02 (Frontend-impl) for CR-00011: created the HTML fragment templates for the "+ New Project" button feature.

### Templates Created

**`dashboard/templates/fragments/new_project_modal.html`**

Modal dialog for registering a new project with:
- Project ID field (lowercase, numbers, hyphens)
- Display Name field
- Repository Root field with "Browse" button
- Field-level validation error messages
- Global error message area
- htmx-powered form submission

**`dashboard/templates/fragments/directory_browser.html`**

Directory browser fragment for selecting repository root with:
- Breadcrumb navigation
- Directory listing with click-to-navigate
- Symlink indicator
- Current path display
- "Select This Folder" action button

### Key Design Decisions

- **htmx-powered**: Both modals use htmx for dynamic content loading and form submission
- **Two-modal pattern**: Directory browser loads inside the new-project modal when "Browse" is clicked
- **Consistent styling**: Uses existing Tailwind CSS custom properties (bg-card, border-border, etc.) matching the dashboard theme
- **Parent window communication**: Directory browser uses `window.opener`/`window.parent` pattern to pass selected path back to the form

## Files Changed

- `dashboard/templates/fragments/new_project_modal.html` — new modal template (267 lines)
- `dashboard/templates/fragments/directory_browser.html` — new directory browser template (185 lines)

## Test Results

- **Linting** (`ruff check dashboard/routers/projects.py dashboard/utils/project_onboarding.py`): All checks passed
- **Type checking** (`mypy dashboard/routers/projects.py dashboard/utils/project_onboarding.py`): No issues found
- **Existing project tests** (`pytest -k "project_onboarding or projects"`): 5 tests passed (same tests as S01)

## Issues/Observations

- Pre-existing test collection errors (`test_fix_summary_ingestion.py`, `test_item_report_cli.py`) are unrelated to this CR's changes
- The templates reference `selectDirectory()` and `openDirectoryBrowser()` functions defined inline — these could be extracted to a shared JS module in future refactoring
- Directory browser navigates via htmx AJAX calls to `/api/projects/browse`
- The `show_hidden` toggle functionality is plumbed through query params but not exposed in the UI (intentional per design: hidden files accessible via direct URL manipulation if needed)

(End of file - total 56 lines)
