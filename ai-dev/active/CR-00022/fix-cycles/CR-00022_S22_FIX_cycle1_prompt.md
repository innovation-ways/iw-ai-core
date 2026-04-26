# CR-00022 S22 QV Fix Cycle 1/5

Quality gate S22 for work item CR-00022 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 122 lint errors: unused imports (F401), line length (E501), unused variables (F841), type annotation style (UP007), and other issues in oss/fix_recipes/ and test files

**Unparseable output** (always surfaces):
  !  agent "qv-gate" is a subagent, not a primary agent. Falling back to default agent
  > build · MiniMax-M2.7
  $ uv run iw step-start CR-00022 --step S22
  warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
  Started CR-00022 step S22 (already in progress)
  $ make lint
  ...output truncated...
  Full output saved to: /home/sergiog/.local/share/opencode/tool-output/tool_dcb34af82001xhPehboTznZ5oO
     |
  help: Remove unused import: `sqlalchemy.dialects.postgresql`
  UP007 [*] Use `X | Y` for type annotations
    --> orch/db/migrations/versions/c062b6bf5eb3_cr_00022_oss_redesign_drop_prepare_.py:18:16
     |
  16 | # revision identifiers, used by Alembic.
  17 | revision: str = 'c062b6bf5eb3'
  18 | down_revision: Union[str, Sequence[str], None] = '550aecbbd42b'
     |                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  19 | branch_labels: Union[str, Sequence[str], None] = None
  20 | depends_on: Union[str, Sequence[str], None] = None
     |
  help: Convert to `X | Y`
  UP007 [*] Use `X | Y` for type annotations
    --> orch/db/migrations/versions/c062b6bf5eb3_cr_00022_oss_redesign_drop_prepare_.py:19:16
     |
  17 | revision: str = 'c062b6bf5eb3'
  18 | down_revision: Union[str, Sequence[str], None] = '550aecbbd42b'
  19 | branch_labels: Union[str, Sequence[str], None] = None
     |                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  20 | depends_on: Union[str, Sequence[str], None] = None
     |
  help: Convert to `X | Y`
  UP007 [*] Use `X | Y` for type annotations
    --> orch/db/migrations/versions/c062b6bf5eb3_cr_00022_oss_redesign_drop_prepare_.py:20:13
     |
  18 | down_revision: Union[str, Sequence[str], None] = '550aecbbd42b'
  19 | branch_labels: Union[str, Sequence[str], None] = None
  20 | depends_on: Union[str, Sequence[str], None] = None
     |             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
     |
  help: Convert to `X | Y`
  F401 `pathlib.Path` imported but unused
   --> orch/oss/fix_recipes/__init__.py:3:21
    |
  1 | from __future__ import annotations
  2 |
  3 | from pathlib import Path
    |                     ^^^^
  4 |
  5 | from .base import FixPreview, FixRecipe
    |
  help: Remove unused import: `pathlib.Path`
  F401 `.base.FixPreview` imported but unused; consider removing, adding to `__all__`, or using a redundant alias
   --> orch/oss/fix_recipes/__init__.py:5:19
    |
  3 | from pathlib import Path
  4 |
  5 | from .base import FixPreview, FixRecipe
    |                   ^^^^^^^^^^
  6 |
  7 | _REGISTRY: dict[str, FixRecipe] = {}
    |
  help: Use an explicit re-export: `FixPreview as FixPreview`
  TC001 Move application import `.base.FixRecipe` into a type-checking block
   --> orch/oss/fix_recipes/__init__.py:5:31
    |
  3 | from pathlib import Path
  4 |
  5 | from .base import FixPreview, FixRecipe
    |                               ^^^^^^^^^
  6 |
  7 | _REGISTRY: dict[str, FixRecipe] = {}
    |
  help: Move into type-checking block
  E402 Module level import not at top of file
    --> orch/oss/fix_recipes/__init__.py:25:1
     |
  25 | / from orch.oss.fix_recipes import (
  26 | |     ci_cd,
  27 | |     community,
  28 | |     contributor,
  29 | |     governance,
  30 | |     hygiene,
  31 | |     internal_refs,
  32 | |     license_check,
  33 | |     release,
  34 | |     secrets,
  35 | | )
     | |_^
     |
  F401 `orch.oss.fix_recipes.ci_cd` imported but unused; consider removing, adding to `__all__`, or using a redundant alias
    --> orch/oss/fix_recipes/__init__.py:26:5
     |
  25 | from orch.oss.fix_recipes import (
  26 |     ci_cd,
     |     ^^^^^
  27 |     community,
  28 |     contributor,
     |
  help: Use an explicit re-export: `ci_cd as ci_cd`
  F401 `orch.oss.fix_recipes.community` imported but unused; consider removing, adding to `__all__`, or using a redundant alias
    --> orch/oss/fix_recipes/__init__.py:27:5
     |
  25 | from orch.oss.fix_recipes import (
  26 |     ci_cd,
  27 |     community,
     |     ^^^^^^^^^
  28 |     contributor,
  29 |     governance,
     |
  help: Use an explicit re-export: `community as community`
  F401 `orch.oss.fix_recipes.contributor` imported but unused; consider removing, adding to `__all__`, or using a redundant alias
    --> orch/oss/fix_recipes/__init__.py:28:5
     |
  26 |     ci_cd,
  27 |     community,
  28 |     contributor,
     |     ^^^^^^^^^^^
  29 |     governance,
  30 |     hygiene,
     |
  help: Use an explicit re-export: `contributor as contributor`
  F401 `orch.oss.fix_recipes.governance` imported but unused; consider removing, adding to `__all__`, or using a redundant alias
    --> orch/oss/fix_recipes/__init__.py:29:5
     |
  27 |     community,
  28 |     contributor,
  29 |     governance,
     |     ^^^^^^^^^^
  30 |     hygiene,
  31 |     internal_refs,
     |
  help: Use an explicit re-export: `governance as governance`
  F401 `orch.oss.fix_recipes.hygiene` imported but unused; consider removing, adding to `__all__`, or using a redundant alias
    --> orch/oss/fix_recipes/__init__.py:30:5
     |
  28 |     contributor,
  29 |     governance,
  30 |     hygiene,
     |     ^^^^^^^
  31 |     internal_refs,
  32 |     license_check,
     |
  help: Use an explicit re-export: `hygiene as hygiene`
  F401 `orch.oss.fix_recipes.internal_refs` imported but unused; consider removing, adding to `__all__`, or using a redundant alias
    --> orch/oss/fix_recipes/__init__.py:31:5
     |
  29 |     governance,
  30 |     hygiene,
  31 |     internal_refs,
     |     ^^^^^^^^^^^^^
  32 |     license_check,
  33 |     release,
     |
  help: Use an explicit re-export: `internal_refs as internal_refs`
  F401 `orch.oss.fix_recipes.license_check` imported but unused; consider removing, adding to `__all__`, or using a redundant alias
    --> orch/oss/fix_recipes/__init__.py:32:5
     |
  30 |     hygiene,
  31 |     internal_refs,
  32 |     license_check,
     |     ^^^^^^^^^^^^^
  33 |     release,
  34 |     secrets,
     |
  help: Use an explicit re-export: `license_check as license_check`
  F401 `orch.oss.fix_recipes.release` imported but unused; consider removing, adding to `__all__`, or using a redundant alias
    --> orch/oss/fix_recipes/__init__.py:33:5
     |
  31 |     internal_refs,
  32 |     license_check,
  33 |     release,
     |     ^^^^^^^
  34 |     secrets,
  35 | )
     |
  help: Use an explicit re-export: `release as release`
  F401 `orch.oss.fix_recipes.secrets` imported but unused; consider removing, adding to `__all__`, or using a redundant alias
    --> orch/oss/fix_recipes/__init__.py:34:5
     |
  32 |     license_check,
  33 |     release,
  34 |     secrets,
     |     ^^^^^^^
  35 | )
     |
  help: Use an explicit re-export: `secrets as secrets`
  TC003 Move standard library import `pathlib.Path` into a type-checking block
   --> orch/oss/fix_recipes/base.py:4:21
    |
  3 | from dataclasses import dataclass
  4 | from pathlib import Path
    |                     ^^^^
  5 | from typing import Protocol
    |
  help: Move into type-checking block
  E501 Line too long (110 > 100)
    --> orch/oss/fix_recipes/ci_cd.py:39:101
     |
  37 |         target = repo_root / ".github" / "workflows" / "codeql.yml"
  38 |         if target.exists():
  39 |             return FixPreview(target_files=[], full_contents={}, diffs={}, notes="codeql.yml already exists.")
     |                                                                                                     ^^^^^^^^^^
  40 |         config = _load_config(repo_root)
  41 |         content = dedent("""\
     |
  F841 Local variable `config` is assigned to but never used
    --> orch/oss/fix_recipes/ci_cd.py:40:9
     |
  38 |         if target.exists():
  39 |             return FixPreview(target_files=[], full_contents={}, diffs={}, notes="codeql.yml already exists.")
  40 |         config = _load_config(repo_root)
     |         ^^^^^^
  41 |         content = dedent("""\
  42 |             name: CodeQL
     |
  help: Remove assignment to unused variable `config`
  E501 Line too long (113 > 100)
    --> orch/oss/fix_recipes/ci_cd.py:95:101
     |
  93 |         target = repo_root / ".github" / "workflows" / "scorecard.yml"
  94 |         if target.exists():
  95 |             return FixPreview(target_files=[], full_contents={}, diffs={}, notes="scorecard.yml already exists.")
     |                                                                                                     ^^^^^^^^^^^^^
  96 |         config = _load_config(repo_root)
  97 |         org = config.get("company_github_org", "innovation-ways")
     |
  F841 Local variable `org` is assigned to but never used
    --> orch/oss/fix_recipes/ci_cd.py:97:9
     |
  95 |             return FixPreview(target_files=[], full_contents={}, diffs={}, notes="scorecard.yml already exists.")
  96 |         config = _load_config(repo_root)
  97 |         org = config.get("company_github_org", "innovation-ways")
     |         ^^^
  98 |         content = dedent("""\
  99 |             name: OpenSSF Scorecard
     |
  help: Remove assignment to unused variable `org`
  E501 Line too long (114 > 100)
     --> orch/oss/fix_recipes/ci_cd.py:154:101
      |
  152 |         target = repo_root / ".github" / "dependabot.yml"
  153 |         if target.exists():
  154 |             return FixPreview(target_files=[], full_contents={}, diffs={}, notes="dependabot.yml already exists.")
      |                                                                                                     ^^^^^^^^^^^^^^
  155 |         content = dedent("""\
  156 |             version: 2
      |
  E501 Line too long (119 > 100)
     --> orch/oss/fix_recipes/ci_cd.py:194:101
      |
  192 |         target = repo_root / ".github" / "workflows" / "compliance-scan.yml"
  193 |         if target.exists():
  194 |             return FixPreview(target_files=[], full_contents={}, diffs={}, notes="compliance-scan.yml already exists.")
      |                                                                                                     ^^^^^^^^^^^^^^^^^^^
  195 |         config = _load_config(repo_root)
  196 |         tmpl_path = (
      |
  F841 Local variable `config` is assigned to but never used
     --> orch/oss/fix_recipes/ci_cd.py:195:9
      |
  193 |         if target.exists():
  194 |             return FixPreview(target_files=[], full_contents={}, diffs={}, notes="compliance-scan.yml already exists.")
  195 |         config = _load_config(repo_root)
      |         ^^^^^^
  196 |         tmpl_path = (
  197 |             Path(__file__).parent.parent.parent.parent
      |
  help: Remove assignment to unused variable `config`
  F841 Local variable `tmpl_path` is assigned to but never used
     --> orch/oss/fix_recipes/ci_cd.py:196:9
      |
  194 |             return FixPreview(target_files=[], full_contents={}, diffs={}, notes="compliance-scan.yml already exists.")
  195 |         config = _load_config(repo_root)
  196 |         tmpl_path = (
      |         ^^^^^^^^^
  197 |             Path(__file__).parent.parent.parent.parent
  198 |             / "skills" / "iw-oss-publish" / "templates" / ".pre-commit-config.yaml.j2"
      |
  help: Remove assignment to unused variable `tmpl_path`
  E501 Line too long (107 > 100)
     --> orch/oss/fix_recipes/ci_cd.py:249:101
      |
  247 |         wf_dir = repo_root / ".github" / "workflows"
  248 |         if not wf_dir.exists():
  249 |             return FixPreview(target_files=[], full_contents={}, diffs={}, notes="No workflows directory.")
      |                                                                                                     ^^^^^^^
  250 |         try:
  251 |             r = subprocess.run(
      |
  S607 Starting a process with a partial executable path
     --> orch/oss/fix_recipes/ci_cd.py:252:17
      |
  250 |         try:
  251 |             r = subprocess.run(
  252 |                 ["pinact", "run", "--check"],
      |                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  253 |                 cwd=str(repo_root),
  254 |                 capture_output=True,
      |
  E501 Line too long (115 > 100)
     --> orch/oss/fix_recipes/ci_cd.py:259:101
      |
  257 |             )
  258 |             if r.returncode == 0:
  259 |                 return FixPreview(target_files=[], full_contents={}, diffs={}, notes="All actions already pinned.")
      |                                                                                                     ^^^^^^^^^^^^^^^
  260 |         except Exception:
  261 |             pass
      |
  S110 `try`-`except`-`pass` detected, consider logging the exception
     --> orch/oss/fix_recipes/ci_cd.py:260:9
      |
  258 |               if r.returncode == 0:
  259 |                   return FixPreview(target_files=[], full_contents={}, diffs={}, notes="All actions already pinned.")
  260 | /         except Exception:
  261 | |             pass
      | |________________^
  262 |           try:
  263 |               result = subprocess.run(
      |
  S607 Starting a process with a partial executable path
     --> orch/oss/fix_recipes/ci_cd.py:264:17
      |
  262 |         try:
  263 |             result = subprocess.run(
  264 |                 ["pinact", "run"],
      |                 ^^^^^^^^^^^^^^^^^
  265 |                 cwd=str(repo_root),
  266 |                 capture_output=True,
      |
  E501 Line too long (105 > 100)
    --> orch/oss/fix_recipes/community.py:51:101
     |
  49 | …     "company_brand": config.get("company_brand", "Innovation Ways"),
  50 | …     "company_github_org": config.get("company_github_org", "innovation-ways"),
  51 | …     "company_contact_email": config.get("company_contact_email", "info@innovation-ways.com"),
     |                                                                                           ^^^^^
  52 | …     "coc_version": config.get("coc_version", "2.1"),
  53 | …     "homepage": config.get("homepage", f"https://github.com/{config.get('company_github_org', 'innovation-ways')}/{repo_root.name}"),
     |
  E501 Line too long (145 > 100)
    --> orch/oss/fix_recipes/community.py:53:101
     |
  51 | …pany_contact_email", "info@innovation-ways.com"),
  52 | … "2.1"),
  53 | …ps://github.com/{config.get('company_github_org', 'innovation-ways')}/{repo_root.name}"),
     |                                              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  54 | …
  55 | …
     |
  F841 Local variable `diff` is assigned to but never used
    --> orch/oss/fix_recipes/community.py:77:9
     |
  75 | …         """)
  76 | …     existing = target.read_text() if target.exists() else ""
  77 | …     diff = "" if existing == content else f"--- {target}\n+++ {target}\n@@ -1 +1 @@\n-{existing[:200]}..." if existing else f"--- /d…
     |       ^^^^
  78 | …     return FixPreview(
  79 | …         target_files=[target],
     |
  help: Remove assignment to unused variable `diff`
  E501 Line too long (189 > 100)
    --> orch/oss/fix_recipes/community.py:77:101
     |
  75 | …
  76 | …
  77 | … -1 +1 @@\n-{existing[:200]}..." if existing else f"--- /dev/null\n+++ {target}\n@@ +1 @@\n+{content[:200]}..."
     |                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  78 | …
  79 | …
     |
  E501 Line too long (115 > 100)
     --> orch/oss/fix_recipes/community.py:107:101
      |
  105 |             p = repo_root / c
  106 |             if p.exists():
  107 |                 return FixPreview(target_files=[], full_contents={}, diffs={}, notes="SECURITY.md already exists.")
      |                                                                                                     ^^^^^^^^^^^^^^^
  108 |         target = repo_root / "SECURITY.md"
  109 |         config = _load_config(repo_root)
      |
  E501 Line too long (109 > 100)
     --> orch/oss/fix_recipes/community.py:117:101
      |
  115 |             context = {
  116 |                 "project_name": config.get("project_name", repo_root.name),
  117 |                 "company_contact_email": config.get("company_contact_email", "security@innovation-ways.com"),
      |                                                                                                     ^^^^^^^^^
  118 |                 "company_brand": config.get("company_brand", "Innovation Ways"),
  119 |                 "year": "2026",
      |
  E501 Line too long (128 > 100)
     --> orch/oss/fix_recipes/community.py:134:101
      |
  132 |                 ## Reporting a Vulnerability
  133 |
  134 |                 Please report security vulnerabilities to {config.get('company_contact_email', 'security@innovation-ways.com')}.
      |                                                                                                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  135 |                 Include as much detail as possible so we can respond quickly and effectively.
  136 |                 We aim to respond within 48 hours.
      |
  E501 Line too long (122 > 100)
     --> orch/oss/fix_recipes/community.py:167:101
      |
  165 |             p = repo_root / c
  166 |             if p.exists():
  167 |                 return FixPreview(target_files=[], full_contents={}, diffs={}, notes="CODE_OF_CONDUCT.md already exists.")
      |                                                                                                     ^^^^^^^^^^^^^^^^^^^^^^
  168 |         target = repo_root / "CODE_OF_CONDUCT.md"
  169 |         tmpl_path = (
      |
  E501 Line too long (105 > 100)
     --> orch/oss/fix_recipes/community.py:177:101
      |
  175 |             context = {
  176 |                 "company_brand": config.get("company_brand", "Innovation Ways"),
  177 |                 "company_contact_email": config.get("company_contact_email", "info@innovation-ways.com"),
      |                                                                                                     ^^^^^
  178 |                 "coc_version": "2.1",
  179 |             }
      |
  E501 Line too long (103 > 100)
     --> orch/oss/fix_recipes/community.py:204:101
      |
  202 |                 All complaints will be reviewed and investigated promptly and fairly.
  203 |
  204 |                 Report violations to: {config.get('company_contact_email', 'info@innovation-ways.com')}
      |                                                                                                     ^^^
  205 |                 """)
  206 |         return FixPreview(
      |
  E501 Line too long (119 > 100)
     --> orch/oss/fix_recipes/community.py:233:101
      |
  231 |             p = repo_root / c
  232 |             if p.exists():
  233 |                 return FixPreview(target_files=[], full_contents={}, diffs={}, notes="CONTRIBUTING.md already exists.")
      |                                                                                                     ^^^^^^^^^^^^^^^^^^^
  234 |         target = repo_root / "CONTRIBUTING.md"
  235 |         tmpl_path = (
      |
  E501 Line too long (105 > 100)
     --> orch/oss/fix_recipes/community.py:245:101
      |
  243 |                 "company_brand": config.get("company_brand", "Innovation Ways"),
  244 |                 "company_github_org": config.get("company_github_org", "innovation-ways"),
  245 |                 "company_contact_email": config.get("company_contact_email", "info@innovation-ways.com"),
      |                                                                                                     ^^^^^
  246 |                 "contributor_agreement": config.get("contributor_agreement", "DCO"),
  247 |             }
      |
  E501 Line too long (114 > 100)
     --> orch/oss/fix_recipes/community.py:303:101
      |
  301 |             p = repo_root / c
  302 |             if p.exists():
  303 |                 return FixPreview(target_files=[], full_contents={}, diffs={}, notes="CODEOWNERS already exists.")
      |                                                                                                     ^^^^^^^^^^^^^^
  304 |         target = repo_root / ".github" / "CODEOWNERS"
  305 |         config = _load_config(repo_root)
      |
  F841 Local variable `config` is assigned to but never used
     --> orch/oss/fix_recipes/community.py:305:9
      |
  303 |                 return FixPreview(target_files=[], full_contents={}, diffs={}, notes="CODEOWNERS already exists.")
  304 |         target = repo_root / ".github" / "CODEOWNERS"
  305 |         config = _load_config(repo_root)
      |         ^^^^^^
  306 |         content = dedent("""\
  307 |             # CODEOWNERS
      |
  help: Remove assignment to unused variable `config`
  E501 Line too long (118 > 100)
     --> orch/oss/fix_recipes/community.py:343:101
      |
  342 |     def preview(self, repo_root: Path) -> FixPreview:
  343 |         candidates = [".github/PULL_REQUEST_TEMPLATE.md", "PULL_REQUEST_TEMPLATE.md", "docs/PULL_REQUEST_TEMPLATE.md"]
      |                                                                                                     ^^^^^^^^^^^^^^^^^^
  344 |         for c in candidates:
  345 |             p = repo_root / c
      |
  E501 Line too long (115 > 100)
     --> orch/oss/fix_recipes/community.py:347:101
      |
  345 |             p = repo_root / c
  346 |             if p.exists():
  347 |                 return FixPreview(target_files=[], full_contents={}, diffs={}, notes="PR template already exists.")
      |                                                                                                     ^^^^^^^^^^^^^^^
  348 |         target = repo_root / ".github" / "PULL_REQUEST_TEMPLATE.md"
  349 |         content = dedent("""\
      |
  E501 Line too long (122 > 100)
     --> orch/oss/fix_recipes/community.py:397:101
      |
  395 |         for c in [bug_path, feature_path]:
  396 |             if c.exists():
  397 |                 return FixPreview(target_files=[], full_contents={}, diffs={}, notes="Issue templates already populated.")
      |                                                                                                     ^^^^^^^^^^^^^^^^^^^^^^
  398 |         bug_content = dedent("""\
  399 |             name: Bug Report
      |
  E501 Line too long (114 > 100)
     --> orch/oss/fix_recipes/community.py:463:101
      |
  461 |             p = repo_root / c
  462 |             if p.exists():
  463 |                 return FixPreview(target_files=[], full_contents={}, diffs={}, notes="SUPPORT.md already exists.")
      |                                                                                                     ^^^^^^^^^^^^^^
  464 |         target = repo_root / "SUPPORT.md"
  465 |         tmpl_path = (
      |
  E501 Line too long (105 > 100)
     --> orch/oss/fix_recipes/community.py:473:101
      |
  471 |             context = {
  472 |                 "company_brand": config.get("company_brand", "Innovation Ways"),
  473 |                 "company_contact_email": config.get("company_contact_email", "info@innovation-ways.com"),
      |                                                                                                     ^^^^^
  474 |             }
  475 |             content = _render_jinja2(tmpl_path, context)
      |
  E501 Line too long (147 > 100)
     --> orch/oss/fix_recipes/community.py:484:101
      |
  482 | …e:
  483 | …
  484 | …b.com/{config.get('company_github_org', 'innovation-ways')}/{repo_root.name}/discussions)
      |                                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  485 | …ig.get('company_github_org', 'innovation-ways')}/{repo_root.name}/issues)
      |
  E501 Line too long (131 > 100)
     --> orch/oss/fix_recipes/community.py:485:101
      |
  484 | …://github.com/{config.get('company_github_org', 'innovation-ways')}/{repo_root.name}/discussions)
  485 | …om/{config.get('company_github_org', 'innovation-ways')}/{repo_root.name}/issues)
      |                                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  486 | …
  487 | …TY.md](SECURITY.md).
      |
  E501 Line too long (136 > 100)
     --> orch/oss/fix_recipes/community.py:524:101
      |
  522 | …
  523 | …
  524 | …contents={}, diffs={}, notes="CONTRIBUTING.md not found — cannot add DCO sign-off.")
      |                                                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  525 | …
  526 | …oper certificate of origin" in text.lower():
      |
  E501 Line too long (134 > 100)
     --> orch/oss/fix_recipes/community.py:527:101
      |
  525 |         text = target.read_text()
  526 |         if "signed-off-by" in text.lower() or "developer certificate of origin" in text.lower():
  527 |             return FixPreview(target_files=[], full_contents={}, diffs={}, notes="DCO sign-off already mentioned in CONTRIBUTING.md.")
      |                                                                                                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  528 |         new_text = text.rstrip() + dedent("""
      |
  TC003 Move standard library import `pathlib.Path` into a type-checking block
   --> orch/oss/fix_recipes/contributor.py:3:21
    |
  1 | from __future__ import annotations
  2 |
  3 | from pathlib import Path
    |                     ^^^^
  4 | from textwrap import dedent
    |
  help: Move into type-checking block
  E501 Line too long (115 > 100)
    --> orch/oss/fix_recipes/contributor.py:17:101
     |
  15 |         target = repo_root / ".github" / "dco.yml"
  16 |         if target.exists():
  17 |             return FixPreview(target_files=[], full_contents={}, diffs={}, notes=".github/dco.yml already exists.")
     |                                                                                                     ^^^^^^^^^^^^^^^
  18 |         content = dedent("""\
  19 |             # DCO (Developer Certificate of Origin)
     |
  E501 Line too long (110 > 100)
    --> orch/oss/fix_recipes/contributor.py:56:101
     |
  54 |                 break
  55 |         if target is None:
  56 |             return FixPreview(target_files=[], full_contents={}, diffs={}, notes="CONTRIBUTING.md not found.")
     |                                                                                                     ^^^^^^^^^^
  57 |         text = target.read_text()
  58 |         if "signed-off-by" in text.lower() or "developer certificate of origin" in text.lower():
     |
  E501 Line too long (116 > 100)
    --> orch/oss/fix_recipes/contributor.py:59:101
     |
  57 |         text = target.read_text()
  58 |         if "signed-off-by" in text.lower() or "developer certificate of origin" in text.lower():
  59 |             return FixPreview(target_files=[], full_contents={}, diffs={}, notes="DCO sign-off already documented.")
     |                                                                                                     ^^^^^^^^^^^^^^^^
  60 |         new_text = text.rstrip() + dedent("""
     |
  E501 Line too long (120 > 100)
    --> orch/oss/fix_recipes/governance.py:28:101
     |
  26 |         target = repo_root / ".iw" / "oss-publish.toml"
  27 |         if target.exists():
  28 |             return FixPreview(target_files=[], full_contents={}, diffs={}, notes=".iw/oss-publish.toml already exists.")
     |                                                                                                     ^^^^^^^^^^^^^^^^^^^^
  29 |         tmpl_path = (
  30 |             Path(__file__).parent.parent.parent.parent
     |
  TC003 Move standard library import `pathlib.Path` into a type-checking block
   --> orch/oss/fix_recipes/hygiene.py:3:21
    |
  1 | from __future__ import annotations
  2 |
  3 | from pathlib import Path
    |                     ^^^^
  4 |
  5 | from . import register
    |
  help: Move into type-checking block
  E501 Line too long (129 > 100)
    --> orch/oss/fix_recipes/hygiene.py:27:101
     |
  26 | def _detect_ecosystems(repo_root: Path) -> list[str]:
  27 |     if (repo_root / "pyproject.toml").exists() or (repo_root / "setup.py").exists() or (repo_root / "requirements.txt").exists():
     |                                                                                                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  28 |         return ["python"]
  29 |     if (repo_root / "package.json").exists():
     |
  E501 Line too long (102 > 100)
    --> orch/oss/fix_recipes/hygiene.py:48:101
     |
  46 |         missing = [p for p in SECRET_PATTERNS if p not in gi_set]
  47 |         if not missing:
  48 |             return FixPreview(target_files=[], full_contents={}, diffs={}, notes="No changes needed.")
     |                                                                                                     ^^
  49 |         new_lines = list(missing)
  50 |         new_content = existing.rstrip() + "\n\n# IW OSS — secrets patterns\n" + "\n".join(new_lines) + "\n"
     |
  E501 Line too long (107 > 100)
    --> orch/oss/fix_recipes/hygiene.py:50:101
     |
  48 |             return FixPreview(target_files=[], full_contents={}, diffs={}, notes="No changes needed.")
  49 |         new_lines = list(missing)
  50 |         new_content = existing.rstrip() + "\n\n# IW OSS — secrets patterns\n" + "\n".join(new_lines) + "\n"
     |                                                                                                     ^^^^^^^
  51 |         import difflib
  52 |         diff = "".join(difflib.unified_diff(existing.splitlines(), new_content.splitlines(), lineterm=""))
     |
  E501 Line too long (106 > 100)
    --> orch/oss/fix_recipes/hygiene.py:52:101
     |
  50 |         new_content = existing.rstrip() + "\n\n# IW OSS — secrets patterns\n" + "\n".join(new_lines) + "\n"
  51 |         import difflib
  52 |         diff = "".join(difflib.unified_diff(existing.splitlines(), new_content.splitlines(), lineterm=""))
     |                                                                                                     ^^^^^^
  53 |         return FixPreview(
  54 |             target_files=[repo_root / ".gitignore"],
     |
  C416 Unnecessary list comprehension (rewrite using `list()`)
    --> orch/oss/fix_recipes/hygiene.py:70:21
     |
  68 |         if not missing:
  69 |             return preview
  70 |         new_lines = [p for p in missing]
     |                     ^^^^^^^^^^^^^^^^^^^^
  71 |         new_content = existing.rstrip() + "\n\n# IW OSS — secrets patterns\n" + "\n".join(new_lines) + "\n"
  72 |         gi.write_text(new_content)
     |
  help: Rewrite using `list()`
  E501 Line too long (107 > 100)
    --> orch/oss/fix_recipes/hygiene.py:71:101
     |
  69 |             return preview
  70 |         new_lines = [p for p in missing]
  71 |         new_content = existing.rstrip() + "\n\n# IW OSS — secrets patterns\n" + "\n".join(new_lines) + "\n"
     |                                                                                                     ^^^^^^^
  72 |         gi.write_text(new_content)
  73 |         return preview
     |
  E501 Line too long (102 > 100)
    --> orch/oss/fix_recipes/hygiene.py:92:101
     |
  90 |                     missing.append(pat)
  91 |         if not missing:
  92 |             return FixPreview(target_files=[], full_contents={}, diffs={}, notes="No changes needed.")
     |                                                                                                     ^^
  93 |         new_content = existing.rstrip() + "\n\n# IW OSS — language ignores\n" + "\n".join(missing) + "\n"
  94 |         import difflib
     |
  E501 Line too long (105 > 100)
    --> orch/oss/fix_recipes/hygiene.py:93:101
     |
  91 |         if not missing:
  92 |             return FixPreview(target_files=[], full_contents={}, diffs={}, notes="No changes needed.")
  93 |         new_content = existing.rstrip() + "\n\n# IW OSS — language ignores\n" + "\n".join(missing) + "\n"
     |                                                                                                     ^^^^^
  94 |         import difflib
  95 |         diff = "".join(difflib.unified_diff(existing.splitlines(), new_content.splitlines(), lineterm=""))
     |
  E501 Line too long (106 > 100)
    --> orch/oss/fix_recipes/hygiene.py:95:101
     |
  93 |         new_content = existing.rstrip() + "\n\n# IW OSS — language ignores\n" + "\n".join(missing) + "\n"
  94 |         import difflib
  95 |         diff = "".join(difflib.unified_diff(existing.splitlines(), new_content.splitlines(), lineterm=""))
     |                                                                                                     ^^^^^^
  96 |         return FixPreview(
  97 |             target_files=[repo_root / ".gitignore"],
     |
  E501 Line too long (105 > 100)
     --> orch/oss/fix_recipes/hygiene.py:118:101
      |
  116 |         if not missing:
  117 |             return preview
  118 |         new_content = existing.rstrip() + "\n\n# IW OSS — language ignores\n" + "\n".join(missing) + "\n"
      |                                                                                                     ^^^^^
  119 |         gi.write_text(new_content)
  120 |         return preview
      |
  E501 Line too long (102 > 100)
     --> orch/oss/fix_recipes/hygiene.py:134:101
      |
  132 |         existing = gi.read_text() if gi.exists() else ""
  133 |         if ".iw" in existing.splitlines():
  134 |             return FixPreview(target_files=[], full_contents={}, diffs={}, notes="No changes needed.")
      |                                                                                                     ^^
  135 |         new_content = existing.rstrip() + "\n\n# IW AI Core\n.iw/\n"
  136 |         import difflib
      |
  E501 Line too long (106 > 100)
     --> orch/oss/fix_recipes/hygiene.py:137:101
      |
  135 |         new_content = existing.rstrip() + "\n\n# IW AI Core\n.iw/\n"
  136 |         import difflib
  137 |         diff = "".join(difflib.unified_diff(existing.splitlines(), new_content.splitlines(), lineterm=""))
      |                                                                                                     ^^^^^^
  138 |         return FixPreview(
  139 |             target_files=[gi],
      |
  TC003 Move standard library import `pathlib.Path` into a type-checking block
   --> orch/oss/fix_recipes/internal_refs.py:3:21
    |
  1 | from __future__ import annotations
  2 |
  3 | from pathlib import Path
    |                     ^^^^
  4 |
  5 | from . import register
    |
  help: Move into type-checking block
  E501 Line too long (118 > 100)
    --> orch/oss/fix_recipes/internal_refs.py:28:101
     |
  26 |                 full_contents={},
  27 |                 diffs={},
  28 |                 notes="syft not available — run `bash .claude/skills/iw-oss-publish/scripts/install_tools.sh` first.",
     |                                                                                                     ^^^^^^^^^^^^^^^^^^
  29 |             )
  30 |         return FixPreview(
     |
  E501 Line too long (121 > 100)
    --> orch/oss/fix_recipes/internal_refs.py:34:101
     |
  32 |             full_contents={},
  33 |             diffs={},
  34 |             notes="SBOM generation requires syft — run `syft scan dir:<path> -o spdx-json=.iw/sbom.spdx.json` manually.",
     |                                                                                                     ^^^^^^^^^^^^^^^^^^^^^
  35 |         )
     |
  E501 Line too long (111 > 100)
    --> orch/oss/fix_recipes/license_check.py:45:101
     |
  43 |         for c in candidates:
  44 |             if (repo_root / c).exists():
  45 |                 return FixPreview(target_files=[], full_contents={}, diffs={}, notes="LICENSE already exists.")
     |                                                                                                     ^^^^^^^^^^^
  46 |         config = _load_config(repo_root)
  47 |         license_type = config.get("license", "Apache-2.0")
     |
  E501 Line too long (103 > 100)
    --> orch/oss/fix_recipes/license_check.py:61:101
     |
  59 |                 http://www.apache.org/licenses/
  60 |
  61 |                 Copyright {2026} {config.get('company_legal_name', 'Innovation Ways - Unipessoal LDA')}
     |                                                                                                     ^^^
  62 |
  63 |                 Licensed under the Apache License, Version 2.0 (the "License");
     |
  E501 Line too long (107 > 100)
     --> orch/oss/fix_recipes/license_check.py:98:101
      |
   96 |                 break
   97 |         if target is None:
   98 |             return FixPreview(target_files=[], full_contents={}, diffs={}, notes="LICENSE file not found.")
      |                                                                                                     ^^^^^^^
   99 |         text = target.read_text()
  100 |         import re
      |
  E501 Line too long (118 > 100)
     --> orch/oss/fix_recipes/license_check.py:104:101
      |
  102 |         current_year = 2026
  103 |         if years_in_text and max(years_in_text) >= current_year - 1:
  104 |             return FixPreview(target_files=[], full_contents={}, diffs={}, notes="Copyright year is already current.")
      |                                                                                                     ^^^^^^^^^^^^^^^^^^
  105 |         new_text = re.sub(
  106 |             r"\b(20\d{2})(-\d{4})?",
      |
  E501 Line too long (107 > 100)
     --> orch/oss/fix_recipes/license_check.py:112:101
      |
  110 |         )
  111 |         if new_text == text:
  112 |             new_text = text.rstrip() + f"\n\nCopyright (c) {current_year} Innovation Ways - Unipessoal LDA"
      |                                                                                                     ^^^^^^^
  113 |         import difflib
  114 |         diff = "".join(difflib.unified_diff(text.splitlines(), new_text.splitlines(), lineterm=""))
      |
  E501 Line too long (107 > 100)
     --> orch/oss/fix_recipes/license_check.py:140:101
      |
  138 |         )
  139 |         if new_text == text:
  140 |             new_text = text.rstrip() + f"\n\nCopyright (c) {current_year} Innovation Ways - Unipessoal LDA"
      |                                                                                                     ^^^^^^^
  141 |         target.write_text(new_text)
  142 |         return preview
      |
  E501 Line too long (110 > 100)
     --> orch/oss/fix_recipes/license_check.py:156:101
      |
  154 |         for c in candidates:
  155 |             if (repo_root / c).exists():
  156 |                 return FixPreview(target_files=[], full_contents={}, diffs={}, notes="NOTICE already exists.")
      |                                                                                                     ^^^^^^^^^^
  157 |         target = repo_root / "NOTICE"
  158 |         tmpl_path = (
      |
  E501 Line too long (107 > 100)
     --> orch/oss/fix_recipes/license_check.py:166:101
      |
  164 |             context = {
  165 |                 "project_name": config.get("project_name", repo_root.name),
  166 |                 "company_legal_name": config.get("company_legal_name", "Innovation Ways - Unipessoal LDA"),
      |                                                                                                     ^^^^^^^
  167 |                 "year": "2026",
  168 |             }
      |
  E501 Line too long (104 > 100)
     --> orch/oss/fix_recipes/license_check.py:178:101
      |
  176 |                 ## Innovation Ways
  177 |
  178 |                 Copyright {2026} {config.get('company_legal_name', 'Innovation Ways - Unipessoal LDA')}.
      |                                                                                                     ^^^^
  179 |                 All rights reserved.
  180 |                 """)
      |
  TC003 Move standard library import `pathlib.Path` into a type-checking block
   --> orch/oss/fix_recipes/release.py:3:21
    |
  1 | from __future__ import annotations
  2 |
  3 | from pathlib import Path
    |                     ^^^^
  4 |
  5 | from . import register
    |
  help: Move into type-checking block
  E501 Line too long (113 > 100)
    --> orch/oss/fix_recipes/release.py:18:101
     |
  16 |         for c in candidates:
  17 |             if (repo_root / c).exists():
  18 |                 return FixPreview(target_files=[], full_contents={}, diffs={}, notes="CHANGELOG already exists.")
     |                                                                                                     ^^^^^^^^^^^^^
  19 |         target = repo_root / "CHANGELOG.md"
  20 |         content = dedent("""\
     |
  E501 Line too long (123 > 100)
    --> orch/oss/fix_recipes/release.py:67:101
     |
  65 |             text = target.read_text()
  66 |             if "googleapis/release-please-action@v4" in text:
  67 |                 return FixPreview(target_files=[], full_contents={}, diffs={}, notes="release-please.yml already uses v4.")
     |                                                                                                     ^^^^^^^^^^^^^^^^^^^^^^^
  68 |             new_text = text.replace("release-please-action@v3", "release-please-action@v4").replace(
  69 |                 "googleapis/release-please-action@v3", "googleapis/release-please-action@v4"
     |
  E501 Line too long (103 > 100)
    --> orch/oss/fix_recipes/release.py:72:101
     |
  70 |             )
  71 |             import difflib
  72 |             diff = "".join(difflib.unified_diff(text.splitlines(), new_text.splitlines(), lineterm=""))
     |                                                                                                     ^^^
  73 |             return FixPreview(
  74 |                 target_files=[target],
     |
  E501 Line too long (107 > 100)
     --> orch/oss/fix_recipes/release.py:125:101
      |
  123 |         wf_dir = repo_root / ".github" / "workflows"
  124 |         if not wf_dir.exists():
  125 |             return FixPreview(target_files=[], full_contents={}, diffs={}, notes="No workflows directory.")
      |                                                                                                     ^^^^^^^
  126 |         for wf in wf_dir.glob("*.yml"):
  127 |             if "actions/attest-build-provenance" in wf.read_text():
      |
  E501 Line too long (131 > 100)
     --> orch/oss/fix_recipes/release.py:128:101
      |
  126 |         for wf in wf_dir.glob("*.yml"):
  127 |             if "actions/attest-build-provenance" in wf.read_text():
  128 |                 return FixPreview(target_files=[], full_contents={}, diffs={}, notes="attest-build-provenance already referenced.")
      |                                                                                                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  129 |         return FixPreview(
  130 |             target_files=[],
      |
  E501 Line too long (108 > 100)
     --> orch/oss/fix_recipes/release.py:133:101
      |
  131 |             full_contents={},
  132 |             diffs={},
  133 |             notes="attest-build-provenance not found in any workflow — requires manual workflow authoring.",
      |                                                                                                     ^^^^^^^^
  134 |         )
      |
  E501 Line too long (106 > 100)
    --> orch/oss/fix_recipes/secrets.py:28:101
     |
  26 |         target = repo_root / ".gitleaks.toml"
  27 |         if target.exists():
  28 |             return FixPreview(target_files=[], full_contents={}, diffs={}, notes=".gitleaks.toml exists.")
     |                                                                                                     ^^^^^^
  29 |         tmpl_path = (
  30 |             Path(__file__).parent.parent.parent.parent
     |
  E501 Line too long (133 > 100)
    --> orch/oss/fix_recipes/secrets.py:45:101
     |
  43 |                 [rules.generic-api-key]
  44 |                 description = "Generic API Key"
  45 |                 regex = '''(?i)(api[_-]?key|apikey|secret[_-]?key|auth_token|access[_-]?token)['\"]?[:=]\\s*['\"]?[a-zA-Z0-9]{16,}'''
     |                                                                                                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  46 |                 tags = ["api-key", "secret"]
     |
  E501 Line too long (109 > 100)
    --> orch/oss/fix_recipes/secrets.py:86:101
     |
  84 |         target = repo_root / ".secrets.baseline"
  85 |         if target.exists():
  86 |             return FixPreview(target_files=[], full_contents={}, diffs={}, notes=".secrets.baseline exists.")
     |                                                                                                     ^^^^^^^^^
  87 |         content = dedent("""\
  88 |             {
     |
  S105 Possible hardcoded password assigned to: "IW_CORE_DB_PASSWORD"
    --> tests/conftest.py:51:41
     |
  49 |     os.environ["IW_CORE_DB_NAME"] = "iw_orch_test_blocked"
  50 |     os.environ["IW_CORE_DB_USER"] = "blocked"
  51 |     os.environ["IW_CORE_DB_PASSWORD"] = "blocked"
     |                                         ^^^^^^^^^
     |
  F811 Redefinition of unused `TestOssPublish` from line 296
     --> tests/integration/test_oss_dashboard_routes.py:399:7
      |
  399 | class TestOssPublish:
      |       ^^^^^^^^^^^^^^ `TestOssPublish` redefined here
  400 |     def test_publish_returns_404(
  401 |         self, client: TestClient, project_with_oss_disabled: Project
      |
     ::: tests/integration/test_oss_dashboard_routes.py:296:7
      |
  296 | class TestOssPublish:
      |       -------------- previous definition of `TestOssPublish` here
  297 |     def test_publish_returns_404(
  298 |         self, client: TestClient, project_with_oss_disabled: Project
      |
  help: Remove definition: `TestOssPublish`
  F841 Local variable `recipe` is assigned to but never used
     --> tests/integration/test_oss_dashboard_service.py:309:9
      |
  307 |         from orch.oss.fix_recipes import get_recipe
  308 |
  309 |         recipe = get_recipe("OSS-CH-01")
      |         ^^^^^^
  310 |
  311 |         import asyncio
      |
  help: Remove assignment to unused variable `recipe`
  E501 Line too long (151 > 100)
     --> tests/integration/test_oss_dashboard_service.py:324:101
      |
  322 | …
  323 | …
  324 | …eck_id":"OSS-CH-01","target_files":[],"full_contents":{},"diffs":{},"notes":null}\n', b""])
      |                                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  325 | …
  326 | …
      |
  I001 [*] Import block is un-sorted or un-formatted
     --> tests/integration/test_oss_dashboard_service.py:353:9
      |
  351 |       ) -> None:
  352 |           """CR-00022 AC5: no tempfile.mkdtemp or /tmp/oss-worktree in service calls."""
  353 | /         from dashboard.services import oss_service
  354 | |         import inspect
      | |______________________^
  355 |
  356 |           source = inspect.getsource(oss_service)
      |
  help: Organize imports
  F841 Local variable `finding_id` is assigned to but never used
     --> tests/integration/test_oss_dashboard_sse.py:301:9
      |
  299 |         oss_sse_session.add(finding)
  300 |         oss_sse_session.commit()
  301 |         finding_id = finding.id
      |         ^^^^^^^^^^
  302 |
  303 |         job = ProjectOssJob(
      |
  help: Remove assignment to unused variable `finding_id`
  F841 Local variable `job_id` is assigned to but never used
     --> tests/integration/test_oss_dashboard_sse.py:312:9
      |
  310 |         oss_sse_session.add(job)
  311 |         oss_sse_session.commit()
  312 |         job_id = job.id
      |         ^^^^^^
  313 |
  314 |         resp = client.get(
      |
  help: Remove assignment to unused variable `job_id`
  F841 Local variable `job_id` is assigned to but never used
     --> tests/integration/test_oss_dashboard_sse.py:366:9
      |
  364 |         oss_sse_session.add(job)
  365 |         oss_sse_session.commit()
  366 |         job_id = job.id
      |         ^^^^^^
  367 |
  368 |         resp = client.get(
      |
  help: Remove assignment to unused variable `job_id`
  F401 [*] `subprocess` imported but unused
   --> tests/unit/test_oss_accepted_yaml.py:4:8
    |
  2 | from __future__ import annotations
  3 |
  4 | import subprocess
    |        ^^^^^^^^^^
  5 | from pathlib import Path
    |
  help: Remove unused import: `subprocess`
  F401 [*] `pytest` imported but unused
   --> tests/unit/test_oss_accepted_yaml.py:7:8
    |
  5 | from pathlib import Path
  6 |
  7 | import pytest
    |        ^^^^^^
    |
  help: Remove unused import: `pytest`
  E501 Line too long (102 > 100)
    --> tests/unit/test_oss_catalog_completeness.py:36:101
     |
  34 | class TestCatalogCompleteness:
  35 |     def test_every_check_id_has_catalog_entry(self) -> None:
  36 |         catalog_path = Path(__file__).parents[2] / "dashboard" / "services" / "oss_check_catalog.yaml"
     |                                                                                                     ^^
  37 |         if not catalog_path.exists():
  38 |             pytest.skip(f"Catalog not found: {catalog_path}")
     |
  E501 Line too long (102 > 100)
    --> tests/unit/test_oss_catalog_completeness.py:45:101
     |
  44 |     def test_no_orphan_catalog_entries(self) -> None:
  45 |         catalog_path = Path(__file__).parents[2] / "dashboard" / "services" / "oss_check_catalog.yaml"
     |                                                                                                     ^^
  46 |         if not catalog_path.exists():
  47 |             pytest.skip(f"Catalog not found: {catalog_path}")
     |
  E501 Line too long (102 > 100)
    --> tests/unit/test_oss_catalog_completeness.py:54:101
     |
  53 |     def test_catalog_entries_have_required_fields(self) -> None:
  54 |         catalog_path = Path(__file__).parents[2] / "dashboard" / "services" / "oss_check_catalog.yaml"
     |                                                                                                     ^^
  55 |         if not catalog_path.exists():
  56 |             pytest.skip(f"Catalog not found: {catalog_path}")
     |
  E501 Line too long (118 > 100)
    --> tests/unit/test_oss_catalog_completeness.py:63:101
     |
  61 |         for check_id, entry in catalog.items():
  62 |             for field in required:
  63 |                 value = entry.get(field, "").strip() if isinstance(entry, dict) else getattr(entry, field, "").strip()
     |                                                                                                     ^^^^^^^^^^^^^^^^^^
  64 |                 assert value, f"{check_id}: field '{field}' is missing or empty"
     |
  E501 Line too long (102 > 100)
    --> tests/unit/test_oss_catalog_completeness.py:67:101
     |
  66 |     def test_catalog_all_entries_are_strings(self) -> None:
  67 |         catalog_path = Path(__file__).parents[2] / "dashboard" / "services" / "oss_check_catalog.yaml"
     |                                                                                                     ^^
  68 |         if not catalog_path.exists():
  69 |             pytest.skip(f"Catalog not found: {catalog_path}")
     |
  F401 [*] `os` imported but unused
   --> tests/unit/test_oss_check_catalog_loader.py:4:8
    |
  2 | from __future__ import annotations
  3 |
  4 | import os
    |        ^^
  5 | from pathlib import Path
  6 | from typing import Any
    |
  help: Remove unused import: `os`
  F401 [*] `pathlib.Path` imported but unused
   --> tests/unit/test_oss_check_catalog_loader.py:5:21
    |
  4 | import os
  5 | from pathlib import Path
    |                     ^^^^
  6 | from typing import Any
    |
  help: Remove unused import: `pathlib.Path`
  F401 [*] `typing.Any` imported but unused
   --> tests/unit/test_oss_check_catalog_loader.py:6:20
    |
  4 | import os
  5 | from pathlib import Path
  6 | from typing import Any
    |                    ^^^
  7 |
  8 | import pytest
    |
  help: Remove unused import: `typing.Any`
  E501 Line too long (133 > 100)
    --> tests/unit/test_oss_honor_accepted.py:68:101
     |
  67 |         assert dashboard_hash(check_id, summary, ev1) == dashboard_hash(check_id, summary, ev2)
  68 |         assert skill_module.compute_finding_hash(check_id, summary, ev1) == skill_module.compute_finding_hash(check_id, summary, ev2)
     |                                                                                                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  69 |
  70 |     def test_compute_finding_hash_16_hex_chars(self) -> None:
     |
  F401 [*] `os` imported but unused
    --> tests/unit/test_safe_migrate_test_context.py:10:8
     |
   8 | from __future__ import annotations
   9 |
  10 | import os
     |        ^^
  11 |
  12 | import pytest
     |
  help: Remove unused import: `os`
  TC002 Move third-party import `pytest` into a type-checking block
    --> tests/unit/test_safe_migrate_test_context.py:12:8
     |
  10 | import os
  11 |
  12 | import pytest
     |        ^^^^^^
  13 |
  14 | from orch.db.safe_migrate import _is_test_context_active
     |
  help: Move into type-checking block
  Found 122 errors.
  [*] 14 fixable with the `--fix` option (21 hidden fixes can be enabled with the `--unsafe-fixes` option).
  make: *** [Makefile:17: lint] Error 1
  **FAIL** — 122 lint errors found.
  $ mkdir -p ai-dev/active/CR-00022/reports
  (no output)
  ← Write ai-dev/active/CR-00022/reports/CR-00022_S22_QvGate_report.md
  Wrote file successfully.


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
