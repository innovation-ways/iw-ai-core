# CR-00062 S11 QvGate Report

## Gate

| Field        | Value           |
|--------------|-----------------|
| Gate         | quality      |
| Command      | `make quality` |
| Exit code    | 0             |
| Result       | PASS         |
| Duration (s) | 2       |

## Output (tail)

```
uv run python scripts/check_templates.py
uv run ruff check .
All checks passed!
uv run ruff format --check .
776 files already formatted
uv run mypy orch/ dashboard/
Success: no issues found in 257 source files
No new assertion-scanner violations (493 files scanned).
uv run vulture || true
orch/daemon/main.py:683: unused variable 'frame' (100% confidence)
orch/daemon/main.py:688: unused variable 'frame' (100% confidence)
orch/doc_service.py:464: unused variable 'requested_by' (100% confidence)
uv run deptry . \
	--per-rule-ignores DEP001=sqlalchemy.ext.mypy.plugin,DEP001=pytest,DEP001=_pytest,DEP001=testcontainers,DEP002=factory-boy,DEP002=freezegun,DEP002=ruff,DEP002=mypy,DEP002=pre-commit,DEP002=types-freezegun,DEP003=yaml,DEP003=pydantic \
	--extend-exclude "skills/.*" || true
Scanning 306 files...

[1m.claude/skills/iw-oss-publish/scripts/checks/ci_cd.py[m[36m:[m7[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/ci_cd.py[m[36m:[m8[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/ci_cd.py[m[36m:[m9[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/community.py[m[36m:[m5[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/community.py[m[36m:[m6[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/community.py[m[36m:[m7[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/contributor.py[m[36m:[m5[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/contributor.py[m[36m:[m6[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/contributor.py[m[36m:[m7[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/dependencies.py[m[36m:[m9[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/dependencies.py[m[36m:[m10[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/dependencies.py[m[36m:[m11[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/dependencies.py[m[36m:[m12[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/environment.py[m[36m:[m5[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/environment.py[m[36m:[m6[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/environment.py[m[36m:[m7[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/environment.py[m[36m:[m8[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/export_control.py[m[36m:[m7[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/export_control.py[m[36m:[m8[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/export_control.py[m[36m:[m9[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/github.py[m[36m:[m8[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/github.py[m[36m:[m9[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/github.py[m[36m:[m10[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/governance.py[m[36m:[m5[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/governance.py[m[36m:[m6[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/governance.py[m[36m:[m7[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/history.py[m[36m:[m7[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/history.py[m[36m:[m8[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/history.py[m[36m:[m9[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/hygiene.py[m[36m:[m8[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/hygiene.py[m[36m:[m9[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/hygiene.py[m[36m:[m10[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/internal_refs.py[m[36m:[m9[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/internal_refs.py[m[36m:[m10[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/internal_refs.py[m[36m:[m11[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/internal_refs.py[m[36m:[m12[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/license_check.py[m[36m:[m8[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/license_check.py[m[36m:[m9[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/license_check.py[m[36m:[m10[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/privacy.py[m[36m:[m8[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/privacy.py[m[36m:[m9[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/privacy.py[m[36m:[m10[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/release.py[m[36m:[m8[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/release.py[m[36m:[m9[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/release.py[m[36m:[m10[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/secrets.py[m[36m:[m13[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/secrets.py[m[36m:[m14[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/secrets.py[m[36m:[m15[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/trademark.py[m[36m:[m9[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/trademark.py[m[36m:[m10[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/checks/trademark.py[m[36m:[m11[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/scan.py[m[36m:[m38[36m:[m8[36m:[m [1m[31mDEP001[m 'checks' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/scan.py[m[36m:[m39[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/scan.py[m[36m:[m40[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/scan.py[m[36m:[m41[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/scan.py[m[36m:[m42[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/scan.py[m[36m:[m48[36m:[m1[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/scan.py[m[36m:[m162[36m:[m5[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/scan.py[m[36m:[m163[36m:[m5[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/scan.py[m[36m:[m306[36m:[m5[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/scan.py[m[36m:[m369[36m:[m5[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-oss-publish/scripts/scan.py[m[36m:[m376[36m:[m5[36m:[m [1m[31mDEP001[m 'lib' imported but missing from the dependency definitions
[1m.claude/skills/iw-pitch-deck/cookbook/architecture-slide.py[m[36m:[m11[36m:[m1[36m:[m [1m[31mDEP001[m 'pptx' imported but missing from the dependency definitions
[1m.claude/skills/iw-pitch-deck/cookbook/architecture-slide.py[m[36m:[m12[36m:[m1[36m:[m [1m[31mDEP001[m 'pptx' imported but missing from the dependency definitions
[1m.claude/skills/iw-pitch-deck/cookbook/architecture-slide.py[m[36m:[m13[36m:[m1[36m:[m [1m[31mDEP001[m 'pptx' imported but missing from the dependency definitions
[1m.claude/skills/iw-pitch-deck/cookbook/architecture-slide.py[m[36m:[m14[36m:[m1[36m:[m [1m[31mDEP001[m 'pptx' imported but missing from the dependency definitions
[1m.claude/skills/iw-pitch-deck/cookbook/closing-slide.py[m[36m:[m10[36m:[m1[36m:[m [1m[31mDEP001[m 'pptx' imported but missing from the dependency definitions
[1m.claude/skills/iw-pitch-deck/cookbook/closing-slide.py[m[36m:[m11[36m:[m1[36m:[m [1m[31mDEP001[m 'pptx' imported but missing from the dependency definitions
[1m.claude/skills/iw-pitch-deck/cookbook/closing-slide.py[m[36m:[m12[36m:[m1[36m:[m [1m[31mDEP001[m 'pptx' imported but missing from the dependency definitions
[1m.claude/skills/iw-pitch-deck/cookbook/closing-slide.py[m[36m:[m13[36m:[m1[36m:[m [1m[31mDEP001[m 'pptx' imported but missing from the dependency definitions
[1m.claude/skills/iw-pitch-deck/cookbook/content-slide.py[m[36m:[m12[36m:[m1[36m:[m [1m[31mDEP001[m 'pptx' imported but missing from the dependency definitions
[1m.claude/skills/iw-pitch-deck/cookbook/content-slide.py[m[36m:[m13[36m:[m1[36m:[m [1m[31mDEP001[m 'pptx' imported but missing from the dependency definitions
[1m.claude/skills/iw-pitch-deck/cookbook/content-slide.py[m[36m:[m14[36m:[m1[36m:[m [1m[31mDEP001[m 'pptx' imported but missing from the dependency definitions
[1m.claude/skills/iw-pitch-deck/cookbook/content-slide.py[m[36m:[m15[36m:[m1[36m:[m [1m[31mDEP001[m 'pptx' imported but missing from the dependency definitions
[1m.claude/skills/iw-pitch-deck/cookbook/quote-slide.py[m[36m:[m11[36m:[m1[36m:[m [1m[31mDEP001[m 'pptx' imported but missing from the dependency definitions
[1m.claude/skills/iw-pitch-deck/cookbook/quote-slide.py[m[36m:[m12[36m:[m1[36m:[m [1m[31mDEP001[m 'pptx' imported but missing from the dependency definitions
[1m.claude/skills/iw-pitch-deck/cookbook/quote-slide.py[m[36m:[m13[36m:[m1[36m:[m [1m[31mDEP001[m 'pptx' imported but missing from the dependency definitions
[1m.claude/skills/iw-pitch-deck/cookbook/quote-slide.py[m[36m:[m14[36m:[m1[36m:[m [1m[31mDEP001[m 'pptx' imported but missing from the dependency definitions
[1m.claude/skills/iw-pitch-deck/cookbook/section-break-slide.py[m[36m:[m11[36m:[m1[36m:[m [1m[31mDEP001[m 'pptx' imported but missing from the dependency definitions
[1m.claude/skills/iw-pitch-deck/cookbook/section-break-slide.py[m[36m:[m12[36m:[m1[36m:[m [1m[31mDEP001[m 'pptx' imported but missing from the dependency definitions
[1m.claude/skills/iw-pitch-deck/cookbook/section-break-slide.py[m[36m:[m13[36m:[m1[36m:[m [1m[31mDEP001[m 'pptx' imported but missing from the dependency definitions
[1m.claude/skills/iw-pitch-deck/cookbook/section-break-slide.py[m[36m:[m14[36m:[m1[36m:[m [1m[31mDEP001[m 'pptx' imported but missing from the dependency definitions
[1m.claude/skills/iw-pitch-deck/cookbook/stats-slide.py[m[36m:[m11[36m:[m1[36m:[m [1m[31mDEP001[m 'pptx' imported but missing from the dependency definitions
[1m.claude/skills/iw-pitch-deck/cookbook/stats-slide.py[m[36m:[m12[36m:[m1[36m:[m [1m[31mDEP001[m 'pptx' imported but missing from the dependency definitions
[1m.claude/skills/iw-pitch-deck/cookbook/stats-slide.py[m[36m:[m13[36m:[m1[36m:[m [1m[31mDEP001[m 'pptx' imported but missing from the dependency definitions
[1m.claude/skills/iw-pitch-deck/cookbook/stats-slide.py[m[36m:[m14[36m:[m1[36m:[m [1m[31mDEP001[m 'pptx' imported but missing from the dependency definitions
[1m.claude/skills/iw-pitch-deck/cookbook/title-slide.py[m[36m:[m14[36m:[m1[36m:[m [1m[31mDEP001[m 'pptx' imported but missing from the dependency definitions
[1m.claude/skills/iw-pitch-deck/cookbook/title-slide.py[m[36m:[m15[36m:[m1[36m:[m [1m[31mDEP001[m 'pptx' imported but missing from the dependency definitions
[1m.claude/skills/iw-pitch-deck/cookbook/title-slide.py[m[36m:[m16[36m:[m1[36m:[m [1m[31mDEP001[m 'pptx' imported but missing from the dependency definitions
[1m.claude/skills/iw-pitch-deck/cookbook/title-slide.py[m[36m:[m17[36m:[m1[36m:[m [1m[31mDEP001[m 'pptx' imported but missing from the dependency definitions
[1m.claude/skills/iw-pitch-deck/cookbook/two-column-slide.py[m[36m:[m11[36m:[m1[36m:[m [1m[31mDEP001[m 'pptx' imported but missing from the dependency definitions
[1m.claude/skills/iw-pitch-deck/cookbook/two-column-slide.py[m[36m:[m12[36m:[m1[36m:[m [1m[31mDEP001[m 'pptx' imported but missing from the dependency definitions
[1m.claude/skills/iw-pitch-deck/cookbook/two-column-slide.py[m[36m:[m13[36m:[m1[36m:[m [1m[31mDEP001[m 'pptx' imported but missing from the dependency definitions
[1m.claude/skills/iw-pitch-deck/cookbook/two-column-slide.py[m[36m:[m14[36m:[m1[36m:[m [1m[31mDEP001[m 'pptx' imported but missing from the dependency definitions
[1mdashboard/app.py[m[36m:[m387[36m:[m9[36m:[m [1m[31mDEP003[m 'starlette' imported but it is a transitive dependency
[1mdashboard/middlewares/alembic_guard.py[m[36m:[m17[36m:[m1[36m:[m [1m[31mDEP003[m 'starlette' imported but it is a transitive dependency
[1mdashboard/routers/items.py[m[36m:[m16[36m:[m1[36m:[m [1m[31mDEP003[m 'pygments' imported but it is a transitive dependency
[1mdashboard/routers/items.py[m[36m:[m17[36m:[m1[36m:[m [1m[31mDEP003[m 'pygments' imported but it is a transitive dependency
[1mdashboard/routers/items.py[m[36m:[m18[36m:[m1[36m:[m [1m[31mDEP003[m 'pygments' imported but it is a transitive dependency
[1mdashboard/utils/markdown.py[m[36m:[m15[36m:[m1[36m:[m [1m[31mDEP004[m 'bs4' imported but declared as a dev dependency
[1mdashboard/utils/timing.py[m[36m:[m11[36m:[m1[36m:[m [1m[31mDEP003[m 'starlette' imported but it is a transitive dependency
[1morch/rag/doc_indexer.py[m[36m:[m195[36m:[m16[36m:[m [1m[31mDEP003[m 'pyarrow' imported but it is a transitive dependency
[1morch/rag/doc_indexer.py[m[36m:[m213[36m:[m16[36m:[m [1m[31mDEP003[m 'numpy' imported but it is a transitive dependency
[1mpyproject.toml[m[36m:[m [1m[31mDEP002[m 'mako' defined as a dependency but not used in the codebase
[1mpyproject.toml[m[36m:[m [1m[31mDEP002[m 'python-multipart' defined as a dependency but not used in the codebase
[1mpyproject.toml[m[36m:[m [1m[31mDEP002[m 'zstandard' defined as a dependency but not used in the codebase
[1mpyproject.toml[m[36m:[m [1m[31mDEP002[m 'types-markdown' defined as a dependency but not used in the codebase
[1mpyproject.toml[m[36m:[m [1m[31mDEP002[m 'pandas' defined as a dependency but not used in the codebase
[1mpyproject.toml[m[36m:[m [1m[31mDEP002[m 'pathspec' defined as a dependency but not used in the codebase
[1mpyproject.toml[m[36m:[m [1m[31mDEP002[m 'pytest' defined as a dependency but not used in the codebase
[1mpyproject.toml[m[36m:[m [1m[31mDEP002[m 'pytest-cov' defined as a dependency but not used in the codebase
[1m[31mFound 111 dependency issues.[m

For more information, see the documentation: https://deptry.com/
```

## Verdict

```
pass
```
