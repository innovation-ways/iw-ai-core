# Module Documentation Template

Use this template when generating module documentation. Replace all `{placeholders}` with actual content from the source code.

---

```markdown
# {Module Name}

<!-- generated: {YYYY-MM-DD} -->

## Purpose

{One paragraph: what this module does and its role in the InnoForge system. Derived from module docstrings and service class docstrings.}

## Architecture

This module follows the standard InnoForge layered architecture:

```
Router (api/v1/{module}.py) → Service ({module}_service.py) → Repository ({module}_repository.py) → Model ({module}.py)
```

{If the module deviates from this pattern, explain why.}

## Key Components

| Component | Layer | Responsibility |
|-----------|-------|---------------|
| `{ClassName}` | Model | {One sentence from class docstring} |
| `{ServiceName}` | Service | {One sentence} |
| `{RepoName}` | Repository | {One sentence} |
| `{RouterName}` | Router | {One sentence: which endpoints it exposes} |

## API Endpoints

{Only if the module has a router. Table of endpoints.}

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/api/v1/{resource}` | {One sentence} | {scope required} |
| `POST` | `/api/v1/{resource}` | {One sentence} | {scope required} |

## Data Model

{Mermaid ER diagram showing this module's tables and their relationships.}

```mermaid
erDiagram
    {TABLE1} ||--o{ {TABLE2} : "has many"
    {TABLE1} {
        bigint {table1}_id PK
        varchar name
    }
```

## Dependencies

### Depends On

| Module | What It Uses | Why |
|--------|-------------|-----|
| `{module}` | `{ClassName}` | {One sentence} |

### Depended On By

| Module | What It Uses | Why |
|--------|-------------|-----|
| `{module}` | `{ClassName}` | {One sentence} |

## Configuration

{If the module reads from system_config or settings.py, list the keys.}

| Key | Default | Description |
|-----|---------|-------------|
| `{config_key}` | `{default}` | {One sentence} |

{If no configuration, write: "This module has no configurable settings."}

## Business Rules

{List the key business rules enforced by the service layer. These are the non-obvious rules that a developer needs to know.}

1. {Rule from service validation logic}
2. {Rule from CHECK constraints}
3. {Rule from conditional logic}

## Error Handling

| Error | HTTP Status | When |
|-------|------------|------|
| `{ExceptionClass}` | {code} | {One sentence} |

## Multi-Tenancy

{How tenant isolation is enforced in this module. Typically: "All queries filter by `tenant_id`. RLS policies enforce isolation at the database level."}

{If the module has global (non-tenant-scoped) data, explain which tables and why.}

## Extension Points

{How to extend this module's behavior without modifying core code.}

- {Extension point 1: e.g., "Add new document types by inserting into document_type_config"}
- {Extension point 2: e.g., "Custom validation by subclassing BaseValidator"}

{If no extension points, write: "This module does not currently expose extension points."}

## Test Coverage

| Test Type | Location | Count |
|-----------|----------|-------|
| Unit tests | `tests/unit/test_{module}*.py` | {N} tests |
| Integration tests | `tests/integration/test_{module}*.py` | {N} tests |
| Property tests | `tests/unit/properties/test_{module}*.py` | {N} tests |

{If any test type is missing, note it as a gap.}
```
