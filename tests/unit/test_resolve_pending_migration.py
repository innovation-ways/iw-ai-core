from __future__ import annotations

from pathlib import Path

from scripts.resolve_pending_migration import resolve_pending_migration


def _migration_content(revision: str, down_revision: str | None) -> str:
    down = "None" if down_revision is None else f'"{down_revision}"'

    return f'''"""Migration {revision}."""

revision = "{revision}"
down_revision = {down}


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
'''


def test_no_pending_files_is_noop(tmp_path: Path) -> None:
    versions = tmp_path / "versions"
    versions.mkdir()
    (versions / "a.py").write_text(_migration_content("aabb", None), encoding="utf-8")
    (versions / "b.py").write_text(_migration_content("bbcc", "aabb"), encoding="utf-8")

    before = {p.name: p.read_text(encoding="utf-8") for p in versions.glob("*.py")}

    result = resolve_pending_migration(versions)

    after = {p.name: p.read_text(encoding="utf-8") for p in versions.glob("*.py")}
    assert result == []
    assert before == after


def test_resolves_single_pending_file(tmp_path: Path) -> None:
    versions = tmp_path / "versions"
    versions.mkdir()
    (versions / "a.py").write_text(_migration_content("aaa111", None), encoding="utf-8")
    (versions / "b.py").write_text(_migration_content("bbb222", "aaa111"), encoding="utf-8")
    c_file = versions / "c.py"
    c_file.write_text(_migration_content("ccc333", "PENDING"), encoding="utf-8")

    resolve_pending_migration(versions)

    content = c_file.read_text(encoding="utf-8")
    assert 'down_revision = "bbb222"' in content
    assert 'down_revision = "PENDING"' not in content


def test_resolves_pending_when_it_is_the_only_migration(tmp_path: Path) -> None:
    versions = tmp_path / "versions"
    versions.mkdir()
    only = versions / "only.py"
    only.write_text(_migration_content("abc999", "PENDING"), encoding="utf-8")

    resolve_pending_migration(versions)

    content = only.read_text(encoding="utf-8")
    assert "down_revision = None" in content
    assert 'down_revision = "None"' not in content


def test_resolver_idempotent(tmp_path: Path) -> None:
    versions = tmp_path / "versions"
    versions.mkdir()
    (versions / "a.py").write_text(_migration_content("aaa111", None), encoding="utf-8")
    pending = versions / "b.py"
    pending.write_text(_migration_content("bbb222", "PENDING"), encoding="utf-8")

    resolve_pending_migration(versions)
    once = pending.read_text(encoding="utf-8")

    resolve_pending_migration(versions)
    twice = pending.read_text(encoding="utf-8")

    assert once == twice
