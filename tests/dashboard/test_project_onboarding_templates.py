"""Template smoke tests for CR-00011 project onboarding fragments."""

from __future__ import annotations

from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape


def _template_dir() -> str:
    return str((Path(__file__).parent.parent.parent / "dashboard" / "templates").resolve())


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(_template_dir()),
        autoescape=select_autoescape(enabled_extensions=()),
    )


class TestNewProjectModalTemplate:
    @pytest.fixture
    def tmpl(self):
        return _env().get_template("fragments/new_project_modal.html")

    def test_renders_form(self, tmpl):
        html = tmpl.render(
            form={"project_id": "", "display_name": "", "repo_root": ""},
            errors={},
        )
        assert '<form hx-post="/api/projects/create"' in html

    def test_has_project_id_field(self, tmpl):
        html = tmpl.render(
            form={"project_id": "", "display_name": "", "repo_root": ""},
            errors={},
        )
        assert 'id="project_id"' in html
        assert 'name="project_id"' in html

    def test_has_display_name_field(self, tmpl):
        html = tmpl.render(
            form={"project_id": "", "display_name": "", "repo_root": ""},
            errors={},
        )
        assert 'id="display_name"' in html
        assert 'name="display_name"' in html

    def test_has_repo_root_field(self, tmpl):
        html = tmpl.render(
            form={"project_id": "", "display_name": "", "repo_root": ""},
            errors={},
        )
        assert 'id="repo_root"' in html
        assert 'name="repo_root"' in html

    def test_has_browse_button(self, tmpl):
        html = tmpl.render(
            form={"project_id": "", "display_name": "", "repo_root": ""},
            errors={},
        )
        assert "Browse" in html
        assert "onclick=" in html
        assert "openDirectoryBrowser()" in html

    def test_shows_project_id_error(self, tmpl):
        html = tmpl.render(
            form={"project_id": "bad ID"},
            errors={"project_id": "Invalid project ID format."},
        )
        assert "Invalid project ID format" in html

    def test_shows_global_error(self, tmpl):
        html = tmpl.render(
            form={"project_id": "", "display_name": "", "repo_root": ""},
            errors={"_global": "Something went wrong."},
        )
        assert "Something went wrong" in html

    def test_has_cancel_button(self, tmpl):
        html = tmpl.render(
            form={"project_id": "", "display_name": "", "repo_root": ""},
            errors={},
        )
        assert "Cancel" in html

    def test_has_register_project_button(self, tmpl):
        html = tmpl.render(
            form={"project_id": "", "display_name": "", "repo_root": ""},
            errors={},
        )
        assert "Register Project" in html

    def test_prepopulates_form_values(self, tmpl):
        html = tmpl.render(
            form={
                "project_id": "my-test-project",
                "display_name": "My Test Project",
                "repo_root": "/home/user/repos/my-test",
            },
            errors={},
        )
        assert 'value="my-test-project"' in html
        assert 'value="My Test Project"' in html
        assert 'value="/home/user/repos/my-test"' in html

    def test_directory_browser_modal_placeholder_present(self, tmpl):
        html = tmpl.render(
            form={"project_id": "", "display_name": "", "repo_root": ""},
            errors={},
        )
        assert 'id="directory-browser-modal"' in html


class TestDirectoryBrowserTemplate:
    @pytest.fixture
    def tmpl(self):
        return _env().get_template("fragments/directory_browser.html")

    def test_renders_breadcrumbs(self, tmpl):
        html = tmpl.render(
            current_path="/home/user",
            breadcrumbs=[
                {"name": "Home", "path": "/home/user"},
                {"name": "repos", "path": "/home/user/repos"},
            ],
            entries=[],
            show_hidden=False,
            safe_root="/home/user",
            error=None,
        )
        assert "Home" in html
        assert "repos" in html

    def test_renders_entries(self, tmpl):
        html = tmpl.render(
            current_path="/home/user/repos",
            breadcrumbs=[{"name": "Home", "path": "/home/user/repos"}],
            entries=[
                {"name": "project-a", "path": "/home/user/repos/project-a", "is_symlink": False},
                {"name": "project-b", "path": "/home/user/repos/project-b", "is_symlink": True},
            ],
            show_hidden=False,
            safe_root="/home/user",
            error=None,
        )
        assert "project-a" in html
        assert "project-b" in html
        assert "symlink" in html

    def test_renders_error(self, tmpl):
        html = tmpl.render(
            current_path="/home/user/repos",
            breadcrumbs=[{"name": "Home", "path": "/home/user/repos"}],
            entries=[],
            show_hidden=False,
            safe_root="/home/user",
            error="Permission denied reading '/home/user/repos'.",
        )
        assert "Permission denied" in html

    def test_shows_no_subdirectories_message(self, tmpl):
        html = tmpl.render(
            current_path="/home/user/repos",
            breadcrumbs=[{"name": "Home", "path": "/home/user/repos"}],
            entries=[],
            show_hidden=False,
            safe_root="/home/user",
            error=None,
        )
        assert "No subdirectories found" in html

    def test_has_select_this_folder_button(self, tmpl):
        html = tmpl.render(
            current_path="/home/user/repos",
            breadcrumbs=[{"name": "Home", "path": "/home/user/repos"}],
            entries=[],
            show_hidden=False,
            safe_root="/home/user",
            error=None,
        )
        assert "Select This Folder" in html

    def test_has_path_input(self, tmpl):
        html = tmpl.render(
            current_path="/home/user/repos",
            breadcrumbs=[{"name": "Home", "path": "/home/user/repos"}],
            entries=[],
            show_hidden=False,
            safe_root="/home/user",
            error=None,
        )
        assert 'id="dir-browser-path"' in html

    def test_path_input_prepopulated(self, tmpl):
        html = tmpl.render(
            current_path="/home/user/repos/my-project",
            breadcrumbs=[{"name": "Home", "path": "/home/user/repos"}],
            entries=[],
            show_hidden=False,
            safe_root="/home/user",
            error=None,
        )
        assert 'value="/home/user/repos/my-project"' in html

    def test_has_close_button(self, tmpl):
        html = tmpl.render(
            current_path="/home/user/repos",
            breadcrumbs=[{"name": "Home", "path": "/home/user/repos"}],
            entries=[],
            show_hidden=False,
            safe_root="/home/user",
            error=None,
        )
        assert "closeDirectoryBrowser" in html
