"""Unit tests for functional-doc validation logic used by iw-review-design.

The validation rules are embedded in skills/iw-review-design/SKILL.md.
This module extracts them as a pure callable so they can be tested directly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

FILE_EXTENSION_RE = re.compile(
    r"\b[A-Za-z0-9_./-]+\.(py|md|js|ts|tsx|sql|html|json|toml|yaml|yml)\b"
)
PATH_FRAGMENT_RE = re.compile(
    r"(?<![A-Za-z0-9])(orch|dashboard|scripts|ai-dev|tests|skills|templates|executor)/"
)
SQL_DDL_RE = re.compile(
    r"\b(ALTER\s+TABLE|CREATE\s+TABLE|DROP\s+TABLE|INSERT\s+INTO|SELECT\s+\*)",
    re.IGNORECASE,
)
CODE_FENCE_RE = re.compile(r"```")
H1_RE = re.compile(r"^# .+ — Functional Design", re.MULTILINE)
H2_WHY_RE = re.compile(r"^## Why", re.MULTILINE)
H2_WHAT_CHANGED_RE = re.compile(r"^## What Changed \(for the User\)", re.MULTILINE)
H2_BEHAVES_RE = re.compile(r"^## How It Behaves", re.MULTILINE)


@dataclass
class ValidationResult:
    violations: list[str]
    blocking: list[str]


def count_words(text: str) -> int:
    stripped = text.strip()
    if not stripped:
        return 0
    return len(stripped.split())


def validate_functional_doc(
    file_path: Path | str | None,
    content: str | None,
) -> ValidationResult:
    """Validate a functional doc and return blocking errors and warnings.

    Mirrors the rules in skills/iw-review-design/SKILL.md.
    """
    violations: list[str] = []
    blocking: list[str] = []

    if file_path is None or content is None:
        blocking.append("functional doc not found")
        return ValidationResult(violations, blocking)

    path = Path(file_path)
    if not path.exists():
        blocking.append("functional doc not found")
        return ValidationResult(violations, blocking)

    text = content.strip()

    if not H1_RE.search(text):
        blocking.append("missing H1 '# <ID> — Functional Design' heading")

    if not H2_WHY_RE.search(text):
        blocking.append("missing H2 '## Why' section")

    if not H2_WHAT_CHANGED_RE.search(text):
        blocking.append("missing H2 '## What Changed (for the User)' section")

    if not H2_BEHAVES_RE.search(text):
        blocking.append("missing H2 '## How It Behaves' section")

    lines = text.splitlines()
    prose_lines = [
        line
        for line in lines
        if line.strip()
        and not line.startswith("#")
        and not line.strip().startswith("<!--")
        and not line.strip().startswith("-->")
    ]
    prose_body = " ".join(prose_lines)
    word_count = count_words(prose_body)
    if word_count > 500:
        blocking.append(f"word count exceeds 500 ({word_count} words)")

    if FILE_EXTENSION_RE.search(text):
        violations.append("file-extension match: contains forbidden extension pattern")

    if PATH_FRAGMENT_RE.search(text):
        violations.append("path-fragment match: contains forbidden path fragment")

    if SQL_DDL_RE.search(text):
        violations.append("SQL-DDL match: contains forbidden SQL keyword")

    if CODE_FENCE_RE.search(text):
        violations.append("code-fence match: contains fenced code block")

    return ValidationResult(violations, blocking)


class TestValidateFunctionalDocHappyPath:
    def test_valid_doc_passes(self, tmp_path: Path) -> None:
        content = (
            "# F-00099 — Functional Design\n\n"
            "<!-- Author: test -->\n"
            "## Why\n"
            "This feature solves a real problem for users who need to track their work.\n"
            "It was requested by the product team after user research.\n\n"
            "## What Changed (for the User)\n"
            "- Users can now see a new dashboard tab with functional doc.\n"
            "- The tab appears alongside the existing design document tab.\n\n"
            "## How It Behaves\n"
            "When a user opens the item detail page they see two tabs:\n"
            "Design Document and Functional Design. Both render correctly.\n"
            "The functional design tab shows a friendly empty state when no doc exists.\n"
        )
        path = tmp_path / "F-00099_Functional.md"
        path.write_text(content, encoding="utf-8")

        result = validate_functional_doc(path, content)

        assert result.blocking == []
        assert result.violations == []

    def test_valid_doc_at_word_boundary_500(self, tmp_path: Path) -> None:
        body_words = " ".join(["word"] * 491)
        content = (
            "# F-00099 — Functional Design\n\n"
            f"## Why\n{body_words}\n\n"
            "## What Changed (for the User)\nUser sees the new feature.\n\n"
            "## How It Behaves\nWorks as expected.\n"
        )
        path = tmp_path / "F-00099_Functional.md"
        path.write_text(content, encoding="utf-8")

        result = validate_functional_doc(path, content)

        assert result.blocking == []
        assert result.violations == []


class TestValidateFunctionalDocStructural:
    def test_missing_file_blocks(self) -> None:
        result = validate_functional_doc(
            "/does/not/exist/F-00099_Functional.md",
            None,
        )
        assert "functional doc not found" in result.blocking
        assert result.violations == []

    def test_missing_h2_why_blocks(self, tmp_path: Path) -> None:
        content = (
            "# F-00099 — Functional Design\n\n"
            "## What Changed (for the User)\nTest.\n\n"
            "## How It Behaves\nTest.\n"
        )
        path = tmp_path / "F-00099_Functional.md"
        path.write_text(content, encoding="utf-8")

        result = validate_functional_doc(path, content)

        assert "missing H2 '## Why' section" in result.blocking

    def test_missing_h2_what_changed_blocks(self, tmp_path: Path) -> None:
        content = "# F-00099 — Functional Design\n\n## Why\nTest.\n\n## How It Behaves\nTest.\n"
        path = tmp_path / "F-00099_Functional.md"
        path.write_text(content, encoding="utf-8")

        result = validate_functional_doc(path, content)

        assert "missing H2 '## What Changed (for the User)' section" in result.blocking

    def test_missing_h2_how_it_behaves_blocks(self, tmp_path: Path) -> None:
        content = (
            "# F-00099 — Functional Design\n\n"
            "## Why\nTest.\n\n"
            "## What Changed (for the User)\nTest.\n"
        )
        path = tmp_path / "F-00099_Functional.md"
        path.write_text(content, encoding="utf-8")

        result = validate_functional_doc(path, content)

        assert "missing H2 '## How It Behaves' section" in result.blocking


class TestValidateFunctionalDocWordCount:
    def test_499_words_passes(self, tmp_path: Path) -> None:
        body_words = " ".join(["word"] * 485)
        content = (
            "# F-00099 — Functional Design\n\n"
            f"## Why\n{body_words}\n\n"
            "## What Changed (for the User)\nUser sees the new feature.\n\n"
            "## How It Behaves\nWorks as expected.\n"
        )
        path = tmp_path / "F-00099_Functional.md"
        path.write_text(content, encoding="utf-8")

        result = validate_functional_doc(path, content)

        assert result.blocking == []

    def test_500_words_passes(self, tmp_path: Path) -> None:
        body_words = " ".join(["word"] * 486)
        content = (
            "# F-00099 — Functional Design\n\n"
            f"## Why\n{body_words}\n\n"
            "## What Changed (for the User)\nUser sees the new feature.\n\n"
            "## How It Behaves\nWorks as expected.\n"
        )
        path = tmp_path / "F-00099_Functional.md"
        path.write_text(content, encoding="utf-8")

        result = validate_functional_doc(path, content)

        assert result.blocking == []

    def test_501_words_blocks(self, tmp_path: Path) -> None:
        body_words = " ".join(["word"] * 493)
        content = (
            "# F-00099 — Functional Design\n\n"
            f"## Why\n{body_words}\n\n"
            "## What Changed (for the User)\nUser sees the new feature.\n\n"
            "## How It Behaves\nWorks as expected.\n"
        )
        path = tmp_path / "F-00099_Functional.md"
        path.write_text(content, encoding="utf-8")

        result = validate_functional_doc(path, content)

        assert any("exceeds 500" in b for b in result.blocking)


class TestValidateFunctionalDocForbiddenTerms:
    @pytest.mark.parametrize(
        "extension",
        [".py", ".md", ".sql", ".js", ".ts", ".tsx", ".html", ".json", ".toml", ".yaml", ".yml"],
    )
    def test_file_extension_triggers_warning(self, tmp_path: Path, extension: str) -> None:
        safe_word = "foo" + extension
        content = (
            "# F-00099 — Functional Design\n\n"
            f"## Why\nThe code in {safe_word} is updated.\n\n"
            "## What Changed (for the User)\nTest.\n\n"
            "## How It Behaves\nTest.\n"
        )
        path = tmp_path / "F-00099_Functional.md"
        path.write_text(content, encoding="utf-8")

        result = validate_functional_doc(path, content)

        assert any("file-extension" in v for v in result.violations)

    @pytest.mark.parametrize(
        "fragment",
        [
            "orch/",
            "dashboard/",
            "scripts/",
            "ai-dev/",
            "tests/",
            "skills/",
            "templates/",
            "executor/",
        ],
    )
    def test_path_fragment_triggers_warning(self, tmp_path: Path, fragment: str) -> None:
        content = (
            "# F-00099 — Functional Design\n\n"
            f"## Why\nThe {fragment} module was updated.\n\n"
            "## What Changed (for the User)\nTest.\n\n"
            "## How It Behaves\nTest.\n"
        )
        path = tmp_path / "F-00099_Functional.md"
        path.write_text(content, encoding="utf-8")

        result = validate_functional_doc(path, content)

        assert any("path-fragment" in v for v in result.violations), (
            f"{fragment!r} did not trigger path-fragment warning. violations={result.violations}"
        )

    @pytest.mark.parametrize(
        "sql_pattern",
        [
            "ALTER TABLE work_items ADD COLUMN",
            "alter table work_items add column",
            "CREATE TABLE new_table",
            "DROP TABLE old_table",
            "INSERT INTO work_items",
            "SELECT * FROM work_items",
        ],
    )
    def test_sql_ddl_triggers_warning(self, tmp_path: Path, sql_pattern: str) -> None:
        content = (
            "# F-00099 — Functional Design\n\n"
            f"## Why\nThe migration includes {sql_pattern}.\n\n"
            "## What Changed (for the User)\nTest.\n\n"
            "## How It Behaves\nTest.\n"
        )
        path = tmp_path / "F-00099_Functional.md"
        path.write_text(content, encoding="utf-8")

        result = validate_functional_doc(path, content)

        assert any("SQL-DDL" in v for v in result.violations), (
            f"{sql_pattern!r} did not trigger SQL-DDL warning. violations={result.violations}"
        )

    def test_code_fence_triggers_warning(self, tmp_path: Path) -> None:
        content = (
            "# F-00099 — Functional Design\n\n"
            "## Why\nThe code now looks like:\n\n"
            "```python\ndef hello(): pass\n"
            "```\n\n"
            "## What Changed (for the User)\nTest.\n\n"
            "## How It Behaves\nTest.\n"
        )
        path = tmp_path / "F-00099_Functional.md"
        path.write_text(content, encoding="utf-8")

        result = validate_functional_doc(path, content)

        assert any("code-fence" in v for v in result.violations)


class TestValidateFunctionalDocCombined:
    def test_structural_and_content_issues_both_reported(self, tmp_path: Path) -> None:
        content = (
            "# F-00099 — Functional Design\n\n"
            "## Why\nWord count here " + " ".join(["word"] * 501) + "\n\n"
            "## What Changed (for the User)\nThe orch/ module was updated.\n\n"
            "## How It Behaves\nTest.\n"
        )
        path = tmp_path / "F-00099_Functional.md"
        path.write_text(content, encoding="utf-8")

        result = validate_functional_doc(path, content)

        assert any("exceeds 500" in b for b in result.blocking)
        assert any("path-fragment" in v for v in result.violations)
        assert any("missing H2" not in b for b in result.blocking)

    def test_structural_failure_drives_blocking_not_content(self, tmp_path: Path) -> None:
        content = (
            "# F-00099 — Functional Design\n\n"
            "## What Changed (for the User)\nThe orch/ module was updated.\n\n"
            "## How It Behaves\nTest.\n"
        )
        path = tmp_path / "F-00099_Functional.md"
        path.write_text(content, encoding="utf-8")

        result = validate_functional_doc(path, content)

        assert len(result.blocking) > 0
        assert "missing H2 '## Why' section" in result.blocking
        assert any("path-fragment" in v for v in result.violations)
