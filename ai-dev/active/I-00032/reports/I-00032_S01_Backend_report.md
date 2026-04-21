# I-00032 S01 Backend Report

## What Was Done

Reviewed and validated the project onboarding implementation for I-00032 "Project onboarding tests append to tracked projects.toml". 

Key findings:
- `init_project.py` correctly appends entries to `projects.toml`
- Unit tests (8 tests in `test_init_project.py`) all pass
- Integration tests (3 tests in `test_init_project.py`) all pass against PostgreSQL testcontainer

## Test Results

**Unit tests:**
```
tests/unit/test_init_project.py - 8 passed
tests/unit/test_project_registry.py - 22 passed
```

**Integration tests:**
```
tests/integration/test_init_project.py - 3 passed
```

## Issues

Two broken tests were found that are unrelated to this work item:
1. `tests/unit/test_fix_summary_ingestion.py` - imports `_parse_and_store_fix_summary` which does not exist in `orch/daemon/fix_cycle.py`
2. `tests/unit/test_item_report_cli.py` - imports `item_report` which does not exist in `orch/cli/item_commands.py`

These are pre-existing issues from incomplete implementation work.

## Observations

The onboarding functionality correctly:
1. Creates `.iw-orch.json` in project repo
2. Appends entry to `projects.toml` in iw-ai-core
3. Creates DB records (projects, id_sequences, migration_locks)
4. Creates ai-dev directory structure
5. Syncs skills and agents

The `projects.toml` currently tracks 3 projects: innoforge, iw-ai-core, and cv.