# F-00058 S11 QV Gate Report: lint

## What was done
Ran `make lint` to check Python (ruff) and JS syntax.

## Result
**FAIL** - 11 lint errors found.

## Errors
| Error | File | Line | Description |
|-------|------|------|-------------|
| I001 | `dashboard/services/oss_service.py` | 26 | Import block is un-sorted or un-formatted |
| S607 | `dashboard/services/oss_service.py` | 98 | Starting a process with a partial executable path |
| S603 | `dashboard/services/oss_service.py` | 104 | subprocess call: check for execution of untrusted input |
| S108 | `dashboard/services/oss_service.py` | 207 | Probable insecure usage of temporary file or directory |
| S607 | `dashboard/services/oss_service.py` | 218 | Starting a process with a partial executable path |
| S108 | `dashboard/services/oss_service.py` | 360 | Probable insecure usage of temporary file or directory |
| SIM105 | `dashboard/services/oss_service.py` | 366 | Use `contextlib.suppress(ProcessLookupError)` |
| S607 | `dashboard/services/oss_service.py` | 378 | Starting a process with a partial executable path |
| S607 | `dashboard/services/oss_service.py` | 489 | Starting a process with a partial executable path |
| S603 | `dashboard/services/oss_service.py` | 513 | subprocess call: check for execution of untrusted input |
| ARG001 | `orch/cli/item_commands.py` | 593 | Unused function argument `archive_dir` |

## Files with issues
- `dashboard/services/oss_service.py` (10 errors)
- `orch/cli/item_commands.py` (1 error)

## Observations
- Most issues are in `oss_service.py` related to subprocess calls and temp file usage
- 1 fixable with `--fix` (the import sorting)
- The S607/S603/S108 warnings are flagged by bandit (security lint)
