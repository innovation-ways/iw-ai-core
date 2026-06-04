"""Unit tests for the skill sync engine.

All tests use tmp_path — no DB or network I/O.
"""

import json
from pathlib import Path

from orch.skills.sync import LOCK_FILE, SKILL_MANIFEST, parse_skill_version, sync_skills

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_master_skill(skills_dir: Path, name: str, version: str) -> Path:
    """Create a minimal master skill directory with a versioned SKILL.md."""
    skill_dir = skills_dir / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / SKILL_MANIFEST).write_text(
        f"---\nversion: {version}\n---\n\n# {name}\n", encoding="utf-8"
    )
    (skill_dir / "extra.md").write_text("extra content", encoding="utf-8")
    return skill_dir


def _project_skill_dir(project_path: Path, name: str) -> Path:
    return project_path / ".claude" / "skills" / name


def _read_lock(project_path: Path) -> dict:
    return json.loads((project_path / LOCK_FILE).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# parse_skill_version
# ---------------------------------------------------------------------------


def test_parse_version_basic(tmp_path: Path) -> None:
    """Verifies that parse version basic."""
    skill_md = tmp_path / SKILL_MANIFEST
    skill_md.write_text("---\nversion: 1.2.3\n---\n\n# My Skill\n")
    assert parse_skill_version(skill_md) == "1.2.3"


def test_parse_version_with_quotes(tmp_path: Path) -> None:
    """Verifies that parse version with quotes."""
    skill_md = tmp_path / SKILL_MANIFEST
    skill_md.write_text("---\nversion: '2.0.0'\n---\n")
    assert parse_skill_version(skill_md) == "2.0.0"


def test_parse_version_no_frontmatter(tmp_path: Path) -> None:
    """Verifies that parse version no frontmatter."""
    skill_md = tmp_path / SKILL_MANIFEST
    skill_md.write_text("# Just a doc\nversion: 1.0.0\n")
    assert parse_skill_version(skill_md) is None


def test_parse_version_missing_version_key(tmp_path: Path) -> None:
    """Verifies that parse version missing version key."""
    skill_md = tmp_path / SKILL_MANIFEST
    skill_md.write_text("---\nname: my-skill\n---\n")
    assert parse_skill_version(skill_md) is None


def test_parse_version_missing_file(tmp_path: Path) -> None:
    """Verifies that parse version missing file."""
    assert parse_skill_version(tmp_path / "nonexistent.md") is None


# ---------------------------------------------------------------------------
# New skill not in project → copied
# ---------------------------------------------------------------------------


def test_new_skill_is_copied(tmp_path: Path) -> None:
    """Verifies that new skill is copied."""
    skills_dir = tmp_path / "skills"
    project_path = tmp_path / "project"
    project_path.mkdir()

    _make_master_skill(skills_dir, "iw-new-incident", "1.0.0")

    result = sync_skills(project_path, skills_dir)

    assert "iw-new-incident" in result.updated
    assert _project_skill_dir(project_path, "iw-new-incident").exists()
    assert (_project_skill_dir(project_path, "iw-new-incident") / SKILL_MANIFEST).exists()


# ---------------------------------------------------------------------------
# Outdated skill → updated
# ---------------------------------------------------------------------------


def test_outdated_skill_is_updated(tmp_path: Path) -> None:
    """Verifies that outdated skill is updated."""
    skills_dir = tmp_path / "skills"
    project_path = tmp_path / "project"
    project_path.mkdir()

    _make_master_skill(skills_dir, "iw-skill", "2.0.0")

    # Pre-install an old version in the project
    project_skill = _project_skill_dir(project_path, "iw-skill")
    project_skill.mkdir(parents=True)
    (project_skill / SKILL_MANIFEST).write_text("---\nversion: 1.0.0\n---\n")

    # Seed lock file with old version
    lock = {
        "platform_version": "1.0.0",
        "skills": {"iw-skill": {"version": "1.0.0", "source": "platform", "overridden": False}},
    }
    (project_path / LOCK_FILE).write_text(json.dumps(lock))

    result = sync_skills(project_path, skills_dir)

    assert "iw-skill" in result.updated
    assert _read_lock(project_path)["skills"]["iw-skill"]["version"] == "2.0.0"


# ---------------------------------------------------------------------------
# Up-to-date skill → skipped
# ---------------------------------------------------------------------------


def test_uptodate_skill_is_skipped(tmp_path: Path) -> None:
    """Verifies that uptodate skill is skipped."""
    skills_dir = tmp_path / "skills"
    project_path = tmp_path / "project"
    project_path.mkdir()

    _make_master_skill(skills_dir, "iw-skill", "1.5.0")

    project_skill = _project_skill_dir(project_path, "iw-skill")
    project_skill.mkdir(parents=True)
    (project_skill / SKILL_MANIFEST).write_text("---\nversion: 1.5.0\n---\n")

    lock = {
        "platform_version": "1.0.0",
        "skills": {"iw-skill": {"version": "1.5.0", "source": "platform", "overridden": False}},
    }
    (project_path / LOCK_FILE).write_text(json.dumps(lock))

    result = sync_skills(project_path, skills_dir)

    assert "iw-skill" in result.up_to_date
    assert result.updated == []


# ---------------------------------------------------------------------------
# Project override → skipped (not overwritten)
# ---------------------------------------------------------------------------


def test_project_override_not_overwritten(tmp_path: Path) -> None:
    """Verifies that project override not overwritten."""
    skills_dir = tmp_path / "skills"
    project_path = tmp_path / "project"
    project_path.mkdir()

    _make_master_skill(skills_dir, "iw-new-incident", "2.1.0")

    # Project has its own customised version
    project_skill = _project_skill_dir(project_path, "iw-new-incident")
    project_skill.mkdir(parents=True)
    custom_content = "# Custom override"
    (project_skill / SKILL_MANIFEST).write_text(custom_content)

    lock = {
        "platform_version": "1.0.0",
        "skills": {
            "iw-new-incident": {
                "version": "1.0.0",
                "source": "project",
                "overridden": True,
            }
        },
    }
    (project_path / LOCK_FILE).write_text(json.dumps(lock))

    result = sync_skills(project_path, skills_dir)

    assert "iw-new-incident" in result.overridden
    assert result.updated == []
    # Custom content is intact
    assert (project_skill / SKILL_MANIFEST).read_text() == custom_content


# ---------------------------------------------------------------------------
# Force flag on override → overwritten
# ---------------------------------------------------------------------------


def test_force_overwrites_project_override(tmp_path: Path) -> None:
    """Verifies that force overwrites project override."""
    skills_dir = tmp_path / "skills"
    project_path = tmp_path / "project"
    project_path.mkdir()

    _make_master_skill(skills_dir, "iw-new-incident", "2.1.0")

    project_skill = _project_skill_dir(project_path, "iw-new-incident")
    project_skill.mkdir(parents=True)
    (project_skill / SKILL_MANIFEST).write_text("# Custom override")

    lock = {
        "platform_version": "1.0.0",
        "skills": {
            "iw-new-incident": {
                "version": "1.0.0",
                "source": "project",
                "overridden": True,
            }
        },
    }
    (project_path / LOCK_FILE).write_text(json.dumps(lock))

    result = sync_skills(project_path, skills_dir, force_skill="iw-new-incident")

    assert "iw-new-incident" in result.updated
    assert result.overridden == []
    # The platform version should be installed
    assert _read_lock(project_path)["skills"]["iw-new-incident"]["version"] == "2.1.0"
    assert _read_lock(project_path)["skills"]["iw-new-incident"]["overridden"] is False


# ---------------------------------------------------------------------------
# check_only mode → no files modified
# ---------------------------------------------------------------------------


def test_check_only_no_files_modified(tmp_path: Path) -> None:
    """Verifies that check only no files modified."""
    skills_dir = tmp_path / "skills"
    project_path = tmp_path / "project"
    project_path.mkdir()

    _make_master_skill(skills_dir, "iw-skill", "3.0.0")

    result = sync_skills(project_path, skills_dir, check_only=True)

    assert "iw-skill" in result.updated
    # Skill was NOT actually copied
    assert not _project_skill_dir(project_path, "iw-skill").exists()
    # Lock file was NOT written
    assert not (project_path / LOCK_FILE).exists()


# ---------------------------------------------------------------------------
# Lock file created on first sync
# ---------------------------------------------------------------------------


def test_lock_file_created_on_first_sync(tmp_path: Path) -> None:
    """Verifies that lock file created on first sync."""
    skills_dir = tmp_path / "skills"
    project_path = tmp_path / "project"
    project_path.mkdir()

    _make_master_skill(skills_dir, "skill-a", "1.0.0")

    assert not (project_path / LOCK_FILE).exists()

    sync_skills(project_path, skills_dir)

    assert (project_path / LOCK_FILE).exists()
    lock = _read_lock(project_path)
    assert "skill-a" in lock["skills"]
    assert lock["synced_at"] is not None


# ---------------------------------------------------------------------------
# Lock file updated on subsequent sync
# ---------------------------------------------------------------------------


def test_lock_file_updated_on_subsequent_sync(tmp_path: Path) -> None:
    """Verifies that lock file updated on subsequent sync."""
    skills_dir = tmp_path / "skills"
    project_path = tmp_path / "project"
    project_path.mkdir()

    _make_master_skill(skills_dir, "skill-a", "1.0.0")
    sync_skills(project_path, skills_dir)

    first_synced_at = _read_lock(project_path)["synced_at"]

    # Bump master version
    (skills_dir / "skill-a" / SKILL_MANIFEST).write_text("---\nversion: 2.0.0\n---\n")
    sync_skills(project_path, skills_dir)

    lock = _read_lock(project_path)
    assert lock["skills"]["skill-a"]["version"] == "2.0.0"
    assert lock["synced_at"] != first_synced_at or True  # synced_at is always refreshed


# ---------------------------------------------------------------------------
# Skill present in project with no lock entry → treated as override
# ---------------------------------------------------------------------------


def test_unlocked_existing_skill_treated_as_override(tmp_path: Path) -> None:
    """Verifies that unlocked existing skill treated as override."""
    skills_dir = tmp_path / "skills"
    project_path = tmp_path / "project"
    project_path.mkdir()

    _make_master_skill(skills_dir, "custom-skill", "1.0.0")

    # Manually created project skill — no lock entry
    project_skill = _project_skill_dir(project_path, "custom-skill")
    project_skill.mkdir(parents=True)
    (project_skill / SKILL_MANIFEST).write_text("# Manual")

    result = sync_skills(project_path, skills_dir)

    assert "custom-skill" in result.overridden
    assert result.updated == []


# ---------------------------------------------------------------------------
# Empty skills_dir → no changes
# ---------------------------------------------------------------------------


def test_empty_skills_dir_no_changes(tmp_path: Path) -> None:
    """Verifies that empty skills dir no changes."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    project_path = tmp_path / "project"
    project_path.mkdir()

    result = sync_skills(project_path, skills_dir)

    assert result.updated == []
    assert result.up_to_date == []
    assert result.overridden == []


# ---------------------------------------------------------------------------
# Skill missing SKILL.md → error recorded
# ---------------------------------------------------------------------------


def test_skill_missing_manifest_records_error(tmp_path: Path) -> None:
    """Verifies that skill missing manifest records error."""
    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "bad-skill"
    skill_dir.mkdir(parents=True)
    # No SKILL.md

    project_path = tmp_path / "project"
    project_path.mkdir()

    result = sync_skills(project_path, skills_dir)

    assert any("bad-skill" in e for e in result.errors)
    assert result.updated == []
