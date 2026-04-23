# CR-00013 S10 QV Fix Cycle 1/5

Quality gate S10 for work item CR-00013 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 64 ruff lint errors (E501, S607, S108, T201, F821, F401, PT018, etc.)

**Command output**:
```
...(truncated)...
ff2"))
28 |         assert len(woff2_files) >= 4, (
29 |             f"Expected at least 4 Inter woff2 files (400, 500, 600, 700), found {len(woff2_files)}: {woff2_files}"
   |                                                                                                     ^^^^^^^^^^^^^^
30 |         )
   |

E501 Line too long (103 > 100)
  --> tests/unit/test_static_assets.py:40:101
   |
39 |         assert found_weights == expected_weights, (
40 |             f"Expected Inter woff2 files for weights {expected_weights}, found weights {found_weights}"
   |                                                                                                     ^^^
41 |         )
   |

E501 Line too long (111 > 100)
  --> tests/unit/test_static_assets.py:54:101
   |
52 | class TestStylesCssContent:
53 |     def test_styles_css_contains_tailwind_directives(self) -> None:
54 |         styles_css_path = Path(__file__).resolve().parent.parent.parent / "dashboard" / "static" / "styles.css"
   |                                                                                                     ^^^^^^^^^^^
55 |         content = styles_css_path.read_text()
56 |         assert "@tailwind" in content or "tailwind" in content.lower(), (
   |

E501 Line too long (109 > 100)
  --> tests/unit/test_static_assets.py:61:101
   |
60 |     def test_theme_css_contains_font_face(self) -> None:
61 |         theme_css_path = Path(__file__).resolve().parent.parent.parent / "dashboard" / "static" / "theme.css"
   |                                                                                                     ^^^^^^^^^
62 |         content = theme_css_path.read_text()
63 |         assert "@font-face" in content, (
   |

Found 64 errors.
[*] 3 fixable with the `--fix` option (22 hidden fixes can be enabled with the `--unsafe-fixes` option).
make: *** [Makefile:17: lint] Error 1
[0m
[0m$ [0muv run iw step-start CR-00013 --step S10
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Started CR-00013 step S10 (already in progress)
[0m
**FAIL** — 64 lint errors found.
[0m← [0mWrite ai-dev/active/CR-00013/reports/CR-00013_S10_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail CR-00013 --step S10 --reason "64 ruff lint errors (E501, S607, S108, T201, F821, F401, PT018, etc.)"
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed CR-00013 step S10: 64 ruff lint errors (E501, S607, S108, T201, F821, F401, PT018, etc.)
[0m
**FAIL** — 64 lint errors across 14 files (E501 long lines, S607/S108 security hints, T201 prints, F821/F401 imports, PT018 assertions, etc.). Report written to `ai-dev/active/CR-00013/reports/CR-00013_S10_QvGate_report.md`.

```


## Gate Command

The quality gate that failed runs:
```bash
make lint
```

After applying fixes, re-run this command to verify the issues are resolved.

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
