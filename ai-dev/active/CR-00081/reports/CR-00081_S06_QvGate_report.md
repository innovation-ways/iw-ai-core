# CR-00081 S06 QvGate Report

## Gate

| Field        | Value           |
|--------------|-----------------|
| Gate         | lint      |
| Command      | `make lint` |
| Exit code    | 0             |
| Result       | PASS         |
| Duration (s) | 1       |

## Output (tail)

```
uv run python scripts/check_templates.py
uv run ruff check .
warning: Invalid `# noqa` directive on tests/unit/test_browser_env.py:385: expected a comma-separated list of codes (e.g., `# noqa: F401, F841`).
warning: Invalid `# noqa` directive on tests/unit/test_browser_env.py:391: expected a comma-separated list of codes (e.g., `# noqa: F401, F841`).
warning: Invalid `# noqa` directive on tests/unit/test_browser_env.py:396: expected a comma-separated list of codes (e.g., `# noqa: F401, F841`).
warning: Invalid `# noqa` directive on tests/unit/test_browser_env.py:402: expected a comma-separated list of codes (e.g., `# noqa: F401, F841`).
warning: Invalid `# noqa` directive on tests/unit/test_browser_env.py:411: expected a comma-separated list of codes (e.g., `# noqa: F401, F841`).
All checks passed!
```

## Verdict

```
pass
```
