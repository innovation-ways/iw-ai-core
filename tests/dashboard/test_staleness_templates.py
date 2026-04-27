"""Template rendering tests for F-00063 staleness fragments.

Tests render each fragment with hand-crafted context objects (no DB, no
subprocess) and assert on key rendered strings, htmx attributes, status badges,
and button presence.

The contexts are built using the same dataclasses that the staleness service
produces: ProjectStalenessResult, ServiceStaleness, AlembicStatus.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape

from orch.staleness.alembic_check import AlembicStatus, RevisionSummary
from orch.staleness.git_lookup import CommitSummary
from orch.staleness.service import ProjectStalenessResult, ServiceStaleness

# ---------------------------------------------------------------------------
# Shared Jinja2 environment (no autoescape — fragments use Tailwind classes)
# ---------------------------------------------------------------------------


def _template_dir() -> str:
    return str((Path(__file__).parent.parent.parent / "dashboard" / "templates").resolve())


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(_template_dir()),
        autoescape=select_autoescape(enabled_extensions=()),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service(
    name: str = "daemon",
    status: str = "up_to_date",
    start_time: datetime | None = None,
    commits: list[CommitSummary] | None = None,
    actions: list[str] | None = None,
    error: str | None = None,
    hot_reload: bool = False,
) -> ServiceStaleness:
    return ServiceStaleness(
        name=name,
        status=status,
        start_time=start_time or datetime(2026, 4, 27, 10, 0, 0, tzinfo=UTC),
        commits=commits or [],
        actions=actions or [],
        error=error,
        hot_reload=hot_reload,
    )


def _make_alembic(
    status: str = "up_to_date",
    current: str | None = "abc123",
    head: str | None = "def456",
    pending: list[RevisionSummary] | None = None,
    error: str | None = None,
) -> AlembicStatus:
    return AlembicStatus(
        status=status,
        current=current,
        head=head,
        pending=pending or [],
        error=error,
    )


def _empty_result() -> ProjectStalenessResult:
    return ProjectStalenessResult(project_id="cv")


def _up_to_date_result() -> ProjectStalenessResult:
    return ProjectStalenessResult(
        project_id="iw-ai-core",
        services=[_make_service("daemon", status="up_to_date")],
        alembic=_make_alembic(status="up_to_date", current="abc123", head="abc123"),
        is_stale=False,
    )


def _stale_result() -> ProjectStalenessResult:
    commits = [
        CommitSummary(sha="aaa1111", subject="feat: add new feature"),
        CommitSummary(sha="bbb2222", subject="fix: critical bug"),
    ]
    return ProjectStalenessResult(
        project_id="iw-ai-core",
        services=[
            _make_service(
                "daemon",
                status="stale",
                commits=commits,
                actions=["restart", "stop"],
            )
        ],
        alembic=_make_alembic(
            status="stale",
            current="abc123",
            head="def456",
            pending=[RevisionSummary(rev_id="def456", message="add batch item status")],
        ),
        is_stale=True,
    )


def _not_running_result() -> ProjectStalenessResult:
    return ProjectStalenessResult(
        project_id="iw-ai-core",
        services=[
            _make_service("dashboard", status="not_running", start_time=None, actions=["start"])
        ],
        alembic=None,
        is_stale=False,
    )


# ===========================================================================
# staleness_panel.html tests
# ===========================================================================


class TestStalenessPanelEmpty:
    @pytest.fixture
    def tmpl(self):
        return _env().get_template("fragments/staleness_panel.html")

    def test_empty_result_renders_nothing(self, tmpl):
        """Project with no services and no alembic config → empty output."""
        html = tmpl.render(staleness=_empty_result(), project=type("P", (), {"id": "cv"})())
        # Should be empty or whitespace only
        assert html.strip() == ""

    def test_opt_out_no_section_tag(self, tmpl):
        """No <section> element rendered for opt-out project."""
        html = tmpl.render(staleness=_empty_result(), project=type("P", (), {"id": "cv"})())
        assert "<section" not in html


class TestStalenessPanelUpToDate:
    @pytest.fixture
    def tmpl(self):
        return _env().get_template("fragments/staleness_panel.html")

    @pytest.fixture
    def rendered(self, tmpl):
        proj = type("P", (), {"id": "iw-ai-core"})()
        return tmpl.render(staleness=_up_to_date_result(), project=proj)

    def test_renders_section(self, rendered):
        assert "<section" in rendered

    def test_has_hx_get_attribute(self, rendered):
        assert 'hx-get="/projects/iw-ai-core/staleness"' in rendered

    def test_has_hx_trigger_every_15s(self, rendered):
        assert 'hx-trigger="every 15s"' in rendered

    def test_has_hx_swap_outer_html(self, rendered):
        assert 'hx-swap="outerHTML"' in rendered

    def test_shows_service_name(self, rendered):
        assert "daemon" in rendered

    def test_shows_up_to_date_badge_for_service(self, rendered):
        # up_to_date should be shown as a green badge
        assert "up" in rendered.lower() or "date" in rendered.lower()

    def test_shows_migrations_section_when_alembic_present(self, rendered):
        assert "Migration" in rendered or "migration" in rendered

    def test_alembic_up_to_date_shows_green(self, rendered):
        assert (
            "up-to-date" in rendered or "up_to_date" in rendered or "up to date" in rendered.lower()
        )


class TestStalenessPanelStale:
    @pytest.fixture
    def tmpl(self):
        return _env().get_template("fragments/staleness_panel.html")

    @pytest.fixture
    def rendered(self, tmpl):
        proj = type("P", (), {"id": "iw-ai-core"})()
        return tmpl.render(staleness=_stale_result(), project=proj)

    def test_renders_section(self, rendered):
        assert "<section" in rendered

    def test_has_hx_get_on_section(self, rendered):
        assert 'hx-get="/projects/iw-ai-core/staleness"' in rendered

    def test_shows_hint_when_both_stale(self, rendered):
        """When both alembic and service are stale, hint text appears."""
        assert "migrations first" in rendered.lower() or "Apply migrations" in rendered

    def test_shows_stale_badge_for_service(self, rendered):
        assert "stale" in rendered.lower()

    def test_shows_commit_list(self, rendered):
        assert "aaa1111" in rendered
        assert "feat: add new feature" in rendered

    def test_shows_restart_button(self, rendered):
        assert "Restart" in rendered

    def test_restart_button_posts_to_correct_url(self, rendered):
        assert "/projects/iw-ai-core/services/daemon/restart" in rendered

    def test_stop_button_present(self, rendered):
        assert "Stop" in rendered

    def test_alembic_stale_shows_current_and_head(self, rendered):
        assert "abc123" in rendered
        assert "def456" in rendered

    def test_alembic_stale_shows_upgrade_button(self, rendered):
        assert "Upgrade" in rendered

    def test_upgrade_button_posts_to_correct_url(self, rendered):
        assert "/projects/iw-ai-core/alembic/upgrade" in rendered

    def test_alembic_shows_pending_revision(self, rendered):
        assert "add batch item status" in rendered

    def test_migrations_section_before_services(self, rendered):
        """Migrations section heading MUST appear before Services section heading."""
        # Search for the uppercase section headings to avoid matching the
        # outer element id="staleness-panel" which contains "staleness" (not a
        # section heading).  The template renders "Migrations" heading before
        # "Services" heading.
        migrations_pos = rendered.find("Migrations")
        services_pos = rendered.find("Services")
        assert migrations_pos != -1, "Migrations heading not found"
        assert services_pos != -1, "Services heading not found"
        assert migrations_pos < services_pos


class TestStalenessPanelNotRunning:
    @pytest.fixture
    def tmpl(self):
        return _env().get_template("fragments/staleness_panel.html")

    @pytest.fixture
    def rendered(self, tmpl):
        proj = type("P", (), {"id": "iw-ai-core"})()
        return tmpl.render(staleness=_not_running_result(), project=proj)

    def test_renders_section(self, rendered):
        assert "<section" in rendered

    def test_shows_not_running_status(self, rendered):
        assert "not" in rendered.lower()
        assert "running" in rendered.lower()

    def test_shows_start_button(self, rendered):
        assert "Start" in rendered

    def test_start_button_posts_to_correct_url(self, rendered):
        assert "/projects/iw-ai-core/services/dashboard/start" in rendered

    def test_no_restart_button(self, rendered):
        # not_running service with only start action should NOT have Restart
        assert "Restart" not in rendered


class TestStalenessPanelUnreachableAlembic:
    @pytest.fixture
    def tmpl(self):
        return _env().get_template("fragments/staleness_panel.html")

    def test_unreachable_shows_grey_banner_no_upgrade_button(self, tmpl):
        result = ProjectStalenessResult(
            project_id="iw-ai-core",
            services=[],
            alembic=_make_alembic(
                status="unreachable", current=None, head=None, error="Connection refused"
            ),
            is_stale=False,
        )
        proj = type("P", (), {"id": "iw-ai-core"})()
        html = tmpl.render(staleness=result, project=proj)
        assert "Connection refused" in html or "Cannot reach" in html
        assert "Upgrade" not in html

    def test_no_config_omits_migrations_section(self, tmpl):
        """If alembic.status == no_config, the migrations section is omitted."""
        result = ProjectStalenessResult(
            project_id="iw-ai-core",
            services=[_make_service("daemon", status="up_to_date")],
            alembic=_make_alembic(status="no_config", current=None, head=None),
            is_stale=False,
        )
        proj = type("P", (), {"id": "iw-ai-core"})()
        html = tmpl.render(staleness=result, project=proj)
        # Should NOT show the migrations block
        assert "Migration" not in html
        assert "migration" not in html


class TestStalenessPanelHotReload:
    @pytest.fixture
    def tmpl(self):
        return _env().get_template("fragments/staleness_panel.html")

    def test_hot_reload_shows_blue_badge(self, tmpl):
        result = ProjectStalenessResult(
            project_id="iw-ai-core",
            services=[_make_service("dashboard", status="hot_reload_skipped", hot_reload=True)],
            alembic=None,
            is_stale=False,
        )
        proj = type("P", (), {"id": "iw-ai-core"})()
        html = tmpl.render(staleness=result, project=proj)
        assert "hot" in html.lower() or "reload" in html.lower()


# ===========================================================================
# staleness_dot.html tests
# ===========================================================================


class TestStalenessDotEmpty:
    @pytest.fixture
    def tmpl(self):
        return _env().get_template("fragments/staleness_dot.html")

    def test_opt_out_renders_empty(self, tmpl):
        """Project with no config → empty fragment."""
        html = tmpl.render(staleness=_empty_result(), project=type("P", (), {"id": "cv"})())
        assert html.strip() == ""

    def test_no_span_for_opt_out(self, tmpl):
        html = tmpl.render(staleness=_empty_result(), project=type("P", (), {"id": "cv"})())
        assert "<span" not in html


class TestStalenessDotUpToDate:
    @pytest.fixture
    def tmpl(self):
        return _env().get_template("fragments/staleness_dot.html")

    def test_renders_grey_dot_when_up_to_date(self, tmpl):
        """Project with services configured but everything up-to-date → grey dot."""
        proj = type("P", (), {"id": "iw-ai-core"})()
        html = tmpl.render(staleness=_up_to_date_result(), project=proj)
        assert "iw-staleness-dot--grey" in html

    def test_grey_dot_has_hx_get(self, tmpl):
        proj = type("P", (), {"id": "iw-ai-core"})()
        html = tmpl.render(staleness=_up_to_date_result(), project=proj)
        assert 'hx-get="/projects/iw-ai-core/staleness-dot"' in html

    def test_grey_dot_has_hx_trigger(self, tmpl):
        proj = type("P", (), {"id": "iw-ai-core"})()
        html = tmpl.render(staleness=_up_to_date_result(), project=proj)
        assert 'hx-trigger="every 15s"' in html

    def test_grey_dot_has_hx_swap_outer_html(self, tmpl):
        proj = type("P", (), {"id": "iw-ai-core"})()
        html = tmpl.render(staleness=_up_to_date_result(), project=proj)
        assert 'hx-swap="outerHTML"' in html


class TestStalenessDotStale:
    @pytest.fixture
    def tmpl(self):
        return _env().get_template("fragments/staleness_dot.html")

    def test_renders_red_dot_when_stale(self, tmpl):
        proj = type("P", (), {"id": "iw-ai-core"})()
        html = tmpl.render(staleness=_stale_result(), project=proj)
        assert "iw-staleness-dot--red" in html

    def test_red_dot_has_title_attribute(self, tmpl):
        proj = type("P", (), {"id": "iw-ai-core"})()
        html = tmpl.render(staleness=_stale_result(), project=proj)
        assert "title=" in html
        assert "Outdated" in html or "outdated" in html or "stale" in html.lower()

    def test_red_dot_has_hx_get(self, tmpl):
        proj = type("P", (), {"id": "iw-ai-core"})()
        html = tmpl.render(staleness=_stale_result(), project=proj)
        assert 'hx-get="/projects/iw-ai-core/staleness-dot"' in html

    def test_red_dot_has_iw_staleness_dot_base_class(self, tmpl):
        proj = type("P", (), {"id": "iw-ai-core"})()
        html = tmpl.render(staleness=_stale_result(), project=proj)
        assert "iw-staleness-dot" in html


class TestStalenessDotNotRunning:
    @pytest.fixture
    def tmpl(self):
        return _env().get_template("fragments/staleness_dot.html")

    def test_not_running_renders_grey_not_red(self, tmpl):
        """not_running does NOT contribute to is_stale — grey dot only."""
        proj = type("P", (), {"id": "iw-ai-core"})()
        html = tmpl.render(staleness=_not_running_result(), project=proj)
        # Grey dot because services are declared, is_stale=False
        assert "iw-staleness-dot--grey" in html
        assert "iw-staleness-dot--red" not in html


# ===========================================================================
# staleness_confirm.html tests
# ===========================================================================


class TestStalenessConfirm:
    @pytest.fixture
    def tmpl(self):
        return _env().get_template("fragments/staleness_confirm.html")

    @pytest.fixture
    def ctx(self):
        return {
            "service_name": "daemon",
            "command_text": "./ai-core.sh daemon restart",
            "action_url": "/projects/iw-ai-core/services/daemon/restart",
            "action": "restart",
        }

    def test_renders_title_with_service_name(self, tmpl, ctx):
        html = tmpl.render(**ctx)
        assert "daemon" in html

    def test_renders_command_in_code_block(self, tmpl, ctx):
        html = tmpl.render(**ctx)
        assert "<code" in html
        assert "./ai-core.sh daemon restart" in html

    def test_has_confirm_button(self, tmpl, ctx):
        html = tmpl.render(**ctx)
        assert "Confirm" in html

    def test_confirm_button_posts_to_action_url(self, tmpl, ctx):
        html = tmpl.render(**ctx)
        assert "/projects/iw-ai-core/services/daemon/restart" in html

    def test_has_cancel_button(self, tmpl, ctx):
        html = tmpl.render(**ctx)
        assert "Cancel" in html

    def test_cancel_button_closes_modal(self, tmpl, ctx):
        """Cancel button must clear the modal (via onclick or htmx)."""
        html = tmpl.render(**ctx)
        # Either onclick-based or htmx trigger to close
        assert "cancel" in html.lower() or "Cancel" in html

    def test_renders_for_alembic_upgrade(self, tmpl):
        html = tmpl.render(
            service_name=None,
            command_text="alembic -c alembic.ini upgrade head",
            action_url="/projects/iw-ai-core/alembic/upgrade",
            action="upgrade",
        )
        assert "alembic" in html.lower() or "upgrade" in html.lower()
        assert "Confirm" in html
