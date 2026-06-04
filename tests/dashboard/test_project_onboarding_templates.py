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
    """Tests for the new project registration modal template."""

    @pytest.fixture
    def tmpl(self):
        """Load the relevant onboarding template from the Jinja2 environment."""
        return _env().get_template("fragments/new_project_modal.html")

    def test_renders_form(self, tmpl):
        """Verifies that the modal renders a form element."""
        html = tmpl.render(
            form={"project_id": "", "display_name": "", "repo_root": ""},
            errors={},
        )
        assert '<form hx-post="/api/projects/create"' in html

    def test_has_project_id_field(self, tmpl):
        """Verifies that the modal has a project_id input field."""
        html = tmpl.render(
            form={"project_id": "", "display_name": "", "repo_root": ""},
            errors={},
        )
        assert 'id="project_id"' in html
        assert 'name="project_id"' in html

    def test_has_display_name_field(self, tmpl):
        """Verifies that the modal has a display_name input field."""
        html = tmpl.render(
            form={"project_id": "", "display_name": "", "repo_root": ""},
            errors={},
        )
        assert 'id="display_name"' in html
        assert 'name="display_name"' in html

    def test_has_repo_root_field(self, tmpl):
        """Verifies that the modal has a repo_root input field."""
        html = tmpl.render(
            form={"project_id": "", "display_name": "", "repo_root": ""},
            errors={},
        )
        assert 'id="repo_root"' in html
        assert 'name="repo_root"' in html

    def test_has_browse_button(self, tmpl):
        """Verifies that the modal has a browse button for repo selection."""
        html = tmpl.render(
            form={"project_id": "", "display_name": "", "repo_root": ""},
            errors={},
        )
        assert "Browse" in html
        assert "onclick=" in html
        assert "openDirectoryBrowser()" in html

    def test_shows_project_id_error(self, tmpl):
        """Verifies that a project_id error message is rendered when provided."""
        html = tmpl.render(
            form={"project_id": "bad ID"},
            errors={"project_id": "Invalid project ID format."},
        )
        assert "Invalid project ID format" in html

    def test_shows_global_error(self, tmpl):
        """Verifies that a global error message is rendered when provided."""
        html = tmpl.render(
            form={"project_id": "", "display_name": "", "repo_root": ""},
            errors={"_global": "Something went wrong."},
        )
        assert "Something went wrong" in html

    def test_has_cancel_button(self, tmpl):
        """Verifies that the modal has a Cancel button."""
        html = tmpl.render(
            form={"project_id": "", "display_name": "", "repo_root": ""},
            errors={},
        )
        assert "Cancel" in html

    def test_has_register_project_button(self, tmpl):
        """Verifies that the modal has a Register Project button."""
        html = tmpl.render(
            form={"project_id": "", "display_name": "", "repo_root": ""},
            errors={},
        )
        assert "Register Project" in html

    def test_prepopulates_form_values(self, tmpl):
        """Verifies that the modal pre-populates form fields with existing values."""
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
        """Verifies that the directory browser modal placeholder element is present."""
        html = tmpl.render(
            form={"project_id": "", "display_name": "", "repo_root": ""},
            errors={},
        )
        assert 'id="directory-browser-modal"' in html


class TestDirectoryBrowserTemplate:
    """Tests for the directory browser modal template."""

    @pytest.fixture
    def tmpl(self):
        """Load the relevant onboarding template from the Jinja2 environment."""
        return _env().get_template("fragments/directory_browser.html")

    def test_renders_breadcrumbs(self, tmpl):
        """Verifies that the directory browser renders breadcrumb navigation."""
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
        """Verifies that the directory browser renders directory entries."""
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
        """Verifies that the directory browser renders an error message when provided."""
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
        """Verifies that the directory browser shows a message when no subdirectories exist."""
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
        """Verifies that the directory browser has a 'Select this folder' button."""
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
        """Verifies that the directory browser has a path input field."""
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
        """Verifies that the directory browser path input is pre-populated with the current path."""
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
        """Verifies that the directory browser has a Close button."""
        html = tmpl.render(
            current_path="/home/user/repos",
            breadcrumbs=[{"name": "Home", "path": "/home/user/repos"}],
            entries=[],
            show_hidden=False,
            safe_root="/home/user",
            error=None,
        )
        assert "closeDirectoryBrowser" in html
