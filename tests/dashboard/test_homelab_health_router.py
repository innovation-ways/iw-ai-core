"""Tests for GET /api/homelab/health — server-side homelab health endpoint.

Covers:
- Happy path: all hosts OK, filesystems OK → overall "ok"
- Alerts firing → overall "critical", alertState "critical"
- Host down (up != 1) → host state "critical"
- CPU pressure >=90% → cpu_state "critical"
- CPU pressure >=80% → cpu_state "warning"
- RAM pressure >=90% → mem_state "critical"
- Proxmox RAM exception: iw-home-01 mem_state is always "ok" regardless of RAM%
- Filesystem near-full (usedPct>=95) → fs state "critical"
- Filesystem warning zone (usedPct>=80) → fs state "warning"
- iw-nas-02 backup mounts excluded from filesystems
- Unknown host (no Prometheus data) → up "unknown", state "unknown"
- Prometheus unreachable → HTTP 200, overall "unknown", stale True, errors populated
- Response shape matches strict contract (all top-level keys present)
- Integration smoke test against live Prometheus (skipped when unreachable)
"""

from __future__ import annotations

import os
from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db

if True:
    # TYPE_CHECKING guard stripped to avoid circular-import issues with conftest re-exports.
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Test client fixture (mirrors test_staleness_router.py pattern)
# ---------------------------------------------------------------------------


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient using testcontainer db_session; homelab cache cleared between tests."""
    # Clear the module-level cache so tests don't share stale state.
    try:
        import dashboard.routers.homelab as _hl

        _hl._cache.clear()  # type: ignore[attr-defined]
    except (ImportError, AttributeError):
        pass

    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:

        def override_get_db() -> Generator[Session, None, None]:
            """Yield the test db_session for FastAPI dependency injection."""
            yield db_session

        app = create_app()
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

        app.dependency_overrides.clear()
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original

    # Clear cache after test
    try:
        import dashboard.routers.homelab as _hl

        _hl._cache.clear()  # type: ignore[attr-defined]
    except (ImportError, AttributeError):
        pass


# ---------------------------------------------------------------------------
# Prometheus mock builder helpers
# ---------------------------------------------------------------------------


def _prom_result(metric: dict[str, str], value: float) -> dict[str, Any]:
    """Build a single Prometheus instant-query result item."""
    return {"metric": metric, "value": [1_700_000_000, str(value)]}


def _ok_up_results() -> list[dict[str, Any]]:
    """Return `up` results for all four expected hosts, all up."""
    return [
        _prom_result({"job": "netdata-home", "instance": "home-srv:19999"}, 1),
        _prom_result({"job": "node-exporter", "instance": "home-srv:9100"}, 1),
        _prom_result({"job": "netdata-dev", "instance": "iw-dev-01:19999"}, 1),
        _prom_result({"job": "node-exporter-proxmox", "instance": "iw-home-01:9100"}, 1),
        _prom_result({"job": "qnap-exporter", "instance": "iw-nas-02:9100"}, 1),
    ]


def _ok_cpu_results() -> list[dict[str, Any]]:
    """Return node_cpu results for home-srv and iw-home-01 at low (10%) usage."""
    return [
        _prom_result({"job": "node-exporter", "instance": "home-srv:9100"}, 10.0),
        _prom_result({"job": "node-exporter-proxmox", "instance": "iw-home-01:9100"}, 10.0),
    ]


def _ok_netdata_cpu_results() -> list[dict[str, Any]]:
    """Return netdata CPU results for iw-dev-01 at low usage."""
    return [
        _prom_result(
            {"job": "netdata-dev", "instance": "iw-dev-01:19999", "dimension": "user"}, 5.0
        ),
    ]


def _ok_netdata_ram_results() -> list[dict[str, Any]]:
    """Return netdata RAM results for iw-dev-01 (free+used+cached+buffers dimensions)."""
    # Providing used and free so total>0 and mem % is computable
    return [
        _prom_result(
            {"job": "netdata-dev", "instance": "iw-dev-01:19999", "dimension": "used"}, 2000.0
        ),
        _prom_result(
            {"job": "netdata-dev", "instance": "iw-dev-01:19999", "dimension": "free"}, 6000.0
        ),
    ]


def _ok_node_mem_results() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (totals, avails) node_memory results for home-srv and iw-home-01 at 50% usage."""
    t1, a1 = _ok_node_mem("home-srv:9100", total=8e9, avail=4e9)
    t2, a2 = _ok_node_mem("iw-home-01:9100", total=8e9, avail=4e9)
    t2["metric"]["job"] = "node-exporter-proxmox"
    a2["metric"]["job"] = "node-exporter-proxmox"
    return [t1, t2], [a1, a2]


def _ok_node_cpu(host_instance: str, pct: float = 10.0) -> dict[str, Any]:
    """Return a node_cpu result for a given instance at a given CPU %."""
    return _prom_result({"job": "node-exporter", "instance": host_instance}, pct)


def _ok_node_mem(host_instance: str, total: float = 8e9, avail: float = 4e9) -> tuple:
    """Return (total, avail) node_memory results for a given instance."""
    return (
        _prom_result(
            {
                "job": "node-exporter",
                "instance": host_instance,
                "__name__": "node_memory_MemTotal_bytes",
            },
            total,
        ),
        _prom_result(
            {
                "job": "node-exporter",
                "instance": host_instance,
                "__name__": "node_memory_MemAvailable_bytes",
            },
            avail,
        ),
    )


def _make_prom_side_effect(
    *,
    up: list | None = None,
    alerts: list | None = None,
    net_cpu: list | None = None,
    net_ram: list | None = None,
    net_fs: list | None = None,
    node_size: list | None = None,
    node_avail: list | None = None,
    node_cpu: list | None = None,
    node_mem_tot: list | None = None,
    node_mem_avail: list | None = None,
    qnap_cpu: list | None = None,
    qnap_mem: list | None = None,
    qnap_cpu_temp: list | None = None,
    qnap_sys_temp: list | None = None,
    qnap_disk_temp: list | None = None,
    qnap_disk_alert: list | None = None,
    qnap_net: list | None = None,
    qnap_uptime: list | None = None,
    net_temp: list | None = None,
    node_hwmon: list | None = None,
    gpu_temp: list | None = None,
    nvme_temp: list | None = None,
    node_hwmon_label: list | None = None,
) -> list[dict[str, Any]]:
    """Return a fixed response list in the order that _fetch_all issues queries.

    The order matches the query list inside ``_fetch_all`` in homelab.py:
    up, alerts, net_cpu, net_ram, net_fs, node_size, node_avail, node_cpu,
    node_mem_tot, node_mem_avail, qnap_cpu, qnap_mem,
    qnap_cpu_temp, qnap_sys_temp, qnap_disk_temp, qnap_disk_alert,
    qnap_net, qnap_uptime.
    """
    return [
        {"status": "success", "data": {"result": up or []}},
        {"status": "success", "data": {"result": alerts or []}},
        {"status": "success", "data": {"result": net_cpu or []}},
        {"status": "success", "data": {"result": net_ram or []}},
        {"status": "success", "data": {"result": net_fs or []}},
        {"status": "success", "data": {"result": node_size or []}},
        {"status": "success", "data": {"result": node_avail or []}},
        {"status": "success", "data": {"result": node_cpu or []}},
        {"status": "success", "data": {"result": node_mem_tot or []}},
        {"status": "success", "data": {"result": node_mem_avail or []}},
        {"status": "success", "data": {"result": qnap_cpu or []}},
        {"status": "success", "data": {"result": qnap_mem or []}},
        {"status": "success", "data": {"result": qnap_cpu_temp or []}},
        {"status": "success", "data": {"result": qnap_sys_temp or []}},
        {"status": "success", "data": {"result": qnap_disk_temp or []}},
        {"status": "success", "data": {"result": qnap_disk_alert or []}},
        {"status": "success", "data": {"result": qnap_net or []}},
        {"status": "success", "data": {"result": qnap_uptime or []}},
        {"status": "success", "data": {"result": net_temp or []}},
        {"status": "success", "data": {"result": node_hwmon or []}},
        {"status": "success", "data": {"result": gpu_temp or []}},
        {"status": "success", "data": {"result": nvme_temp or []}},
        {"status": "success", "data": {"result": node_hwmon_label or []}},
    ]


def _patch_prometheus(responses: list[dict[str, Any]]) -> Any:
    """Context manager that replaces _prom_query with canned responses in order."""
    call_iter = iter(responses)

    async def _fake_prom_query(session: Any, query: str) -> list[dict[str, Any]]:
        """Return pre-canned Prometheus query results for testing."""
        payload = next(call_iter)
        if payload["status"] != "success":
            raise RuntimeError("Prometheus error")
        return payload["data"]["result"]

    return patch("dashboard.routers.homelab._prom_query", side_effect=_fake_prom_query)


# ---------------------------------------------------------------------------
# Response shape contract
# ---------------------------------------------------------------------------


_REQUIRED_TOP_LEVEL_KEYS = {
    "generated_at",
    "generated_ts",
    "overall",
    "alerts",
    "hosts_ok",
    "hosts_total",
    "hosts",
    "filesystems",
    "worst_filesystem",
    "qnap",
    "proxmox",
    "stale",
    "errors",
}

_REQUIRED_HOST_KEYS = {
    "name",
    "role",
    "up",
    "cpu",
    "mem",
    "cpu_state",
    "mem_state",
    "state",
    "detail",
}

_REQUIRED_QNAP_KEYS = {
    "up",
    "cpu",
    "mem",
    "uptime_seconds",
    "cpu_temp_c",
    "system_temp_c",
    "disk_temps",
    "disk_temp_alert",
    "network",
}

_REQUIRED_PROXMOX_KEYS = {"up", "cpu", "mem_reserved_pct", "filesystems"}


class TestResponseShape:
    """GET /api/homelab/health must return all required top-level keys."""

    def test_all_required_top_level_keys_present(self, client: TestClient) -> None:
        """Response contains every key in the strict downstream contract."""
        responses = _make_prom_side_effect(up=_ok_up_results())

        with _patch_prometheus(responses):
            r = client.get("/api/homelab/health")

        assert r.status_code == 200
        body = r.json()
        missing = _REQUIRED_TOP_LEVEL_KEYS - set(body.keys())
        assert not missing, f"Missing top-level keys: {missing}"

    def test_each_host_has_required_keys(self, client: TestClient) -> None:
        """Every host object in 'hosts' carries all required per-host keys."""
        responses = _make_prom_side_effect(up=_ok_up_results())

        with _patch_prometheus(responses):
            r = client.get("/api/homelab/health")

        body = r.json()
        for host in body["hosts"]:
            missing = _REQUIRED_HOST_KEYS - set(host.keys())
            assert not missing, f"Host {host.get('name')} missing keys: {missing}"

    def test_qnap_section_has_required_keys(self, client: TestClient) -> None:
        """The 'qnap' section carries all required per-QNAP keys."""
        responses = _make_prom_side_effect(up=_ok_up_results())

        with _patch_prometheus(responses):
            r = client.get("/api/homelab/health")

        body = r.json()
        qnap = body["qnap"]
        missing = _REQUIRED_QNAP_KEYS - set(qnap.keys())
        assert not missing, f"QNAP section missing keys: {missing}"

    def test_proxmox_section_has_required_keys(self, client: TestClient) -> None:
        """The 'proxmox' section carries all required per-Proxmox keys."""
        responses = _make_prom_side_effect(up=_ok_up_results())

        with _patch_prometheus(responses):
            r = client.get("/api/homelab/health")

        body = r.json()
        proxmox = body["proxmox"]
        missing = _REQUIRED_PROXMOX_KEYS - set(proxmox.keys())
        assert not missing, f"Proxmox section missing keys: {missing}"

    def test_hosts_total_equals_expected_hosts_count(self, client: TestClient) -> None:
        """hosts_total is always 4 (the four expected hosts)."""
        responses = _make_prom_side_effect(up=_ok_up_results())

        with _patch_prometheus(responses):
            r = client.get("/api/homelab/health")

        body = r.json()
        assert body["hosts_total"] == 4

    def test_host_roles_match_spec(self, client: TestClient) -> None:
        """Each host has its specified role string."""
        responses = _make_prom_side_effect(up=_ok_up_results())

        with _patch_prometheus(responses):
            r = client.get("/api/homelab/health")

        body = r.json()
        role_map = {h["name"]: h["role"] for h in body["hosts"]}
        assert role_map.get("home-srv") == "Servidor Docker/Casa"
        assert role_map.get("iw-dev-01") == "Servidor de Desenvolvimento"
        assert role_map.get("iw-home-01") == "Servidor Proxmox"
        assert role_map.get("iw-nas-02") == "NAS QNAP"


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    """All hosts up, no alerts, filesystems OK → overall 'ok'."""

    def test_overall_ok_when_all_hosts_up_no_alerts_no_critical_fs(
        self, client: TestClient
    ) -> None:
        """overall is 'ok' when every host is up with known low-pressure metrics and no alerts."""
        # Provide CPU + RAM for all hosts so no host stays in 'unknown' state.
        node_cpu = _ok_cpu_results()
        net_cpu = _ok_netdata_cpu_results()
        net_ram = _ok_netdata_ram_results()
        qnap_cpu = [_prom_result({"job": "qnap-exporter", "instance": "iw-nas-02:9100"}, 10.0)]
        qnap_mem = [_prom_result({"job": "qnap-exporter", "instance": "iw-nas-02:9100"}, 40.0)]
        mem_tots, mem_avails = _ok_node_mem_results()
        responses = _make_prom_side_effect(
            up=_ok_up_results(),
            net_cpu=net_cpu,
            net_ram=net_ram,
            node_cpu=node_cpu,
            node_mem_tot=mem_tots,
            node_mem_avail=mem_avails,
            qnap_cpu=qnap_cpu,
            qnap_mem=qnap_mem,
        )

        with _patch_prometheus(responses):
            r = client.get("/api/homelab/health")

        assert r.status_code == 200
        body = r.json()
        assert body["overall"] == "ok", f"Expected 'ok', got '{body['overall']}'; body={body}"

    def test_all_known_hosts_in_response(self, client: TestClient) -> None:
        """Response includes all four expected hosts."""
        responses = _make_prom_side_effect(up=_ok_up_results())

        with _patch_prometheus(responses):
            r = client.get("/api/homelab/health")

        body = r.json()
        names = {h["name"] for h in body["hosts"]}
        assert names == {"home-srv", "iw-dev-01", "iw-home-01", "iw-nas-02"}

    def test_hosts_ok_count_equals_four_when_all_up(self, client: TestClient) -> None:
        """hosts_ok equals 4 when all hosts are up with known low-pressure metrics."""
        # Provide CPU + RAM data so no host ends up 'unknown' from missing metrics.
        node_cpu = _ok_cpu_results()
        net_cpu = _ok_netdata_cpu_results()
        net_ram = _ok_netdata_ram_results()
        # QNAP: provide cpu+mem directly
        qnap_cpu = [_prom_result({"job": "qnap-exporter", "instance": "iw-nas-02:9100"}, 10.0)]
        qnap_mem = [_prom_result({"job": "qnap-exporter", "instance": "iw-nas-02:9100"}, 40.0)]
        mem_tots, mem_avails = _ok_node_mem_results()
        responses = _make_prom_side_effect(
            up=_ok_up_results(),
            net_cpu=net_cpu,
            net_ram=net_ram,
            node_cpu=node_cpu,
            node_mem_tot=mem_tots,
            node_mem_avail=mem_avails,
            qnap_cpu=qnap_cpu,
            qnap_mem=qnap_mem,
        )

        with _patch_prometheus(responses):
            r = client.get("/api/homelab/health")

        body = r.json()
        assert body["hosts_ok"] == 4

    def test_stale_false_when_prometheus_responds(self, client: TestClient) -> None:
        """stale is False when Prometheus answers successfully."""
        responses = _make_prom_side_effect(up=_ok_up_results())

        with _patch_prometheus(responses):
            r = client.get("/api/homelab/health")

        body = r.json()
        assert body["stale"] is False

    def test_errors_empty_when_no_issues(self, client: TestClient) -> None:
        """errors list is empty when Prometheus responds without errors."""
        responses = _make_prom_side_effect(up=_ok_up_results())

        with _patch_prometheus(responses):
            r = client.get("/api/homelab/health")

        body = r.json()
        assert body["errors"] == []


# ---------------------------------------------------------------------------
# Alert state
# ---------------------------------------------------------------------------


class TestAlertState:
    """Firing alerts drive alertState and overall to 'critical'."""

    def test_firing_alerts_produce_critical_overall(self, client: TestClient) -> None:
        """When ALERTS{alertstate='firing'} returns results, overall is 'critical'."""
        alerts = [_prom_result({"alertname": "HostDown", "alertstate": "firing"}, 1)]
        responses = _make_prom_side_effect(up=_ok_up_results(), alerts=alerts)

        with _patch_prometheus(responses):
            r = client.get("/api/homelab/health")

        body = r.json()
        assert body["overall"] == "critical"
        assert body["alerts"]["state"] == "critical"
        assert body["alerts"]["firing"] == 1

    def test_no_firing_alerts_ok_state(self, client: TestClient) -> None:
        """When no alerts fire, alerts.state is 'ok' and alerts.firing is 0."""
        responses = _make_prom_side_effect(up=_ok_up_results())

        with _patch_prometheus(responses):
            r = client.get("/api/homelab/health")

        body = r.json()
        assert body["alerts"]["state"] == "ok"
        assert body["alerts"]["firing"] == 0


# ---------------------------------------------------------------------------
# Host state transitions
# ---------------------------------------------------------------------------


class TestHostUpState:
    """up==0 for a host job → host state 'critical'."""

    def test_host_down_produces_critical_host_state(self, client: TestClient) -> None:
        """When netdata-home reports up=0, home-srv state is 'critical'."""
        up_results = [
            _prom_result({"job": "netdata-home", "instance": "home-srv:19999"}, 0),  # DOWN
            _prom_result({"job": "node-exporter", "instance": "home-srv:9100"}, 1),
            _prom_result({"job": "netdata-dev", "instance": "iw-dev-01:19999"}, 1),
            _prom_result({"job": "node-exporter-proxmox", "instance": "iw-home-01:9100"}, 1),
            _prom_result({"job": "qnap-exporter", "instance": "iw-nas-02:9100"}, 1),
        ]
        responses = _make_prom_side_effect(up=up_results)

        with _patch_prometheus(responses):
            r = client.get("/api/homelab/health")

        body = r.json()
        home_srv = next(h for h in body["hosts"] if h["name"] == "home-srv")
        assert home_srv["up"] == "critical"
        assert home_srv["state"] == "critical"

    def test_no_prometheus_target_produces_unknown_host(self, client: TestClient) -> None:
        """A host with no Prometheus data at all has up='unknown', state='unknown'."""
        # Provide up results for all EXCEPT iw-dev-01
        up_results = [
            _prom_result({"job": "netdata-home", "instance": "home-srv:19999"}, 1),
            _prom_result({"job": "node-exporter", "instance": "home-srv:9100"}, 1),
            _prom_result({"job": "node-exporter-proxmox", "instance": "iw-home-01:9100"}, 1),
            _prom_result({"job": "qnap-exporter", "instance": "iw-nas-02:9100"}, 1),
        ]
        responses = _make_prom_side_effect(up=up_results)

        with _patch_prometheus(responses):
            r = client.get("/api/homelab/health")

        body = r.json()
        dev01 = next(h for h in body["hosts"] if h["name"] == "iw-dev-01")
        assert dev01["up"] == "unknown"
        assert dev01["state"] == "unknown"


# ---------------------------------------------------------------------------
# CPU pressure states
# ---------------------------------------------------------------------------


class TestCpuPressureStates:
    """CPU pressure thresholds drive cpu_state correctly."""

    def test_cpu_below_80_produces_ok_cpu_state(self, client: TestClient) -> None:
        """CPU at 50% → cpu_state 'ok'."""
        node_cpu = [_prom_result({"job": "node-exporter", "instance": "home-srv:9100"}, 50.0)]
        responses = _make_prom_side_effect(up=_ok_up_results(), node_cpu=node_cpu)

        with _patch_prometheus(responses):
            r = client.get("/api/homelab/health")

        body = r.json()
        home_srv = next(h for h in body["hosts"] if h["name"] == "home-srv")
        assert home_srv["cpu_state"] == "ok"

    def test_cpu_at_80_produces_warning_cpu_state(self, client: TestClient) -> None:
        """CPU at exactly 80% → cpu_state 'warning'."""
        node_cpu = [_prom_result({"job": "node-exporter", "instance": "home-srv:9100"}, 80.0)]
        responses = _make_prom_side_effect(up=_ok_up_results(), node_cpu=node_cpu)

        with _patch_prometheus(responses):
            r = client.get("/api/homelab/health")

        body = r.json()
        home_srv = next(h for h in body["hosts"] if h["name"] == "home-srv")
        assert home_srv["cpu_state"] == "warning"

    def test_cpu_at_90_produces_critical_cpu_state(self, client: TestClient) -> None:
        """CPU at 90% → cpu_state 'critical'."""
        node_cpu = [_prom_result({"job": "node-exporter", "instance": "home-srv:9100"}, 90.0)]
        responses = _make_prom_side_effect(up=_ok_up_results(), node_cpu=node_cpu)

        with _patch_prometheus(responses):
            r = client.get("/api/homelab/health")

        body = r.json()
        home_srv = next(h for h in body["hosts"] if h["name"] == "home-srv")
        assert home_srv["cpu_state"] == "critical"

    def test_critical_cpu_state_drives_host_state_critical(self, client: TestClient) -> None:
        """When cpu_state is 'critical', host state is also 'critical'."""
        node_cpu = [_prom_result({"job": "node-exporter", "instance": "home-srv:9100"}, 95.0)]
        responses = _make_prom_side_effect(up=_ok_up_results(), node_cpu=node_cpu)

        with _patch_prometheus(responses):
            r = client.get("/api/homelab/health")

        body = r.json()
        home_srv = next(h for h in body["hosts"] if h["name"] == "home-srv")
        assert home_srv["state"] == "critical"


# ---------------------------------------------------------------------------
# RAM pressure states + Proxmox exception
# ---------------------------------------------------------------------------


class TestRamPressureStates:
    """RAM pressure thresholds and the Proxmox iw-home-01 exception."""

    def test_ram_below_80_produces_ok_mem_state(self, client: TestClient) -> None:
        """RAM at 50% → mem_state 'ok'."""
        # node exporter override for home-srv: 50% used
        total, avail = _ok_node_mem("home-srv:9100", total=8e9, avail=4e9)  # 50% avail → 50% used
        responses = _make_prom_side_effect(
            up=_ok_up_results(),
            node_mem_tot=[total],
            node_mem_avail=[avail],
        )

        with _patch_prometheus(responses):
            r = client.get("/api/homelab/health")

        body = r.json()
        home_srv = next(h for h in body["hosts"] if h["name"] == "home-srv")
        assert home_srv["mem_state"] == "ok"

    def test_ram_at_90_produces_critical_mem_state(self, client: TestClient) -> None:
        """RAM at 90% used → mem_state 'critical'."""
        # 10% available of 10 GiB = 90% used
        total, avail = _ok_node_mem("home-srv:9100", total=10e9, avail=1e9)
        responses = _make_prom_side_effect(
            up=_ok_up_results(),
            node_mem_tot=[total],
            node_mem_avail=[avail],
        )

        with _patch_prometheus(responses):
            r = client.get("/api/homelab/health")

        body = r.json()
        home_srv = next(h for h in body["hosts"] if h["name"] == "home-srv")
        assert home_srv["mem_state"] == "critical"

    def test_proxmox_mem_state_always_ok_regardless_of_pct(self, client: TestClient) -> None:
        """iw-home-01 mem_state is always 'ok' even at 99% RAM (Proxmox exception)."""
        # 99% used: only 100 MB available of 10 GiB
        total, avail = _ok_node_mem("iw-home-01:9100", total=10e9, avail=0.1e9)
        # node-exporter-proxmox job maps to iw-home-01
        total["metric"]["job"] = "node-exporter-proxmox"
        avail["metric"]["job"] = "node-exporter-proxmox"
        responses = _make_prom_side_effect(
            up=_ok_up_results(),
            node_mem_tot=[total],
            node_mem_avail=[avail],
        )

        with _patch_prometheus(responses):
            r = client.get("/api/homelab/health")

        body = r.json()
        proxmox = next(h for h in body["hosts"] if h["name"] == "iw-home-01")
        assert proxmox["mem_state"] == "ok", (
            f"Proxmox mem_state must always be 'ok' (reserved RAM). Got: {proxmox['mem_state']}"
        )

    def test_proxmox_mem_reserved_pct_in_proxmox_section(self, client: TestClient) -> None:
        """proxmox.mem_reserved_pct carries the raw used-% (display only)."""
        total, avail = _ok_node_mem("iw-home-01:9100", total=10e9, avail=1e9)
        total["metric"]["job"] = "node-exporter-proxmox"
        avail["metric"]["job"] = "node-exporter-proxmox"
        responses = _make_prom_side_effect(
            up=_ok_up_results(),
            node_mem_tot=[total],
            node_mem_avail=[avail],
        )

        with _patch_prometheus(responses):
            r = client.get("/api/homelab/health")

        body = r.json()
        # Should be approximately 90% (= 1 - avail/total * 100)
        mem_pct = body["proxmox"]["mem_reserved_pct"]
        assert mem_pct is not None
        assert 88.0 < mem_pct < 92.0, f"Expected ~90% mem_reserved_pct, got {mem_pct}"


# ---------------------------------------------------------------------------
# Filesystem states
# ---------------------------------------------------------------------------


class TestFilesystemStates:
    """Filesystem inclusion, state thresholds, and iw-nas-02 backup exclusion."""

    def _make_node_fs_entry(
        self,
        instance: str,
        job: str,
        mountpoint: str,
        device: str,
        fstype: str,
        size_bytes: float,
        avail_bytes: float,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Build a (size, avail) node_filesystem pair."""
        metric = {
            "job": job,
            "instance": instance,
            "mountpoint": mountpoint,
            "device": device,
            "fstype": fstype,
        }
        return (
            _prom_result(dict(metric), size_bytes),
            _prom_result(dict(metric), avail_bytes),
        )

    def test_root_fs_included_and_has_ok_state_when_low_usage(self, client: TestClient) -> None:
        """'/' on home-srv with 30% usage appears in filesystems with state 'ok'."""
        size, avail = self._make_node_fs_entry(
            "home-srv:9100",
            "node-exporter",
            "/",
            "/dev/sda1",
            "ext4",
            100 * 1024**3,  # 100 GiB
            70 * 1024**3,  # 70 GiB avail → 30% used
        )
        responses = _make_prom_side_effect(
            up=_ok_up_results(),
            node_size=[size],
            node_avail=[avail],
        )

        with _patch_prometheus(responses):
            r = client.get("/api/homelab/health")

        body = r.json()
        root_entries = [
            f for f in body["filesystems"] if f["mount"] == "/" and f["host"] == "home-srv"
        ]
        assert len(root_entries) == 1, f"Expected 1 root entry, got {root_entries}"
        assert root_entries[0]["state"] == "ok"

    def test_fs_at_95_pct_is_critical(self, client: TestClient) -> None:
        """Filesystem at 95% usage → state 'critical'."""
        size, avail = self._make_node_fs_entry(
            "home-srv:9100",
            "node-exporter",
            "/",
            "/dev/sda1",
            "ext4",
            100 * 1024**3,
            5 * 1024**3,  # 5% avail → 95% used
        )
        responses = _make_prom_side_effect(
            up=_ok_up_results(),
            node_size=[size],
            node_avail=[avail],
        )

        with _patch_prometheus(responses):
            r = client.get("/api/homelab/health")

        body = r.json()
        root_entries = [f for f in body["filesystems"] if f["mount"] == "/"]
        assert len(root_entries) >= 1
        assert root_entries[0]["state"] == "critical"

    def test_fs_at_80_pct_is_warning(self, client: TestClient) -> None:
        """Filesystem at 80% usage → state 'warning'."""
        size, avail = self._make_node_fs_entry(
            "home-srv:9100",
            "node-exporter",
            "/",
            "/dev/sda1",
            "ext4",
            100 * 1024**3,
            20 * 1024**3,  # 20% avail → 80% used
        )
        responses = _make_prom_side_effect(
            up=_ok_up_results(),
            node_size=[size],
            node_avail=[avail],
        )

        with _patch_prometheus(responses):
            r = client.get("/api/homelab/health")

        body = r.json()
        root_entries = [f for f in body["filesystems"] if f["mount"] == "/"]
        assert len(root_entries) >= 1
        assert root_entries[0]["state"] == "warning"

    def test_qnap_backup_mounts_excluded(self, client: TestClient) -> None:
        """Filesystems on iw-nas-02 whose mount contains 'backup' are excluded."""
        # Use a NFS-style device (//nas.example.test/...) so sourceHost → iw-nas-02
        size_backup, avail_backup = self._make_node_fs_entry(
            "home-srv:9100",
            "node-exporter",
            "/mnt/backups-nas",
            "//nas.example.test/backups",
            "cifs",
            10 * 1024**3,
            5 * 1024**3,
        )
        size_media, avail_media = self._make_node_fs_entry(
            "home-srv:9100",
            "node-exporter",
            "/mnt/media-nas",
            "//nas.example.test/media",
            "cifs",
            10 * 1024**3,
            5 * 1024**3,
        )
        responses = _make_prom_side_effect(
            up=_ok_up_results(),
            node_size=[size_backup, size_media],
            node_avail=[avail_backup, avail_media],
        )

        with _patch_prometheus(responses):
            r = client.get("/api/homelab/health")

        body = r.json()
        backup_mounts = [
            f
            for f in body["filesystems"]
            if "backup" in (f.get("mount") or "").lower() and f["host"] == "iw-nas-02"
        ]
        assert not backup_mounts, (
            f"iw-nas-02 backup mounts must be excluded, found: {backup_mounts}"
        )

        # /mnt/media-nas must remain
        media_mounts = [
            f
            for f in body["filesystems"]
            if f.get("mount") == "/mnt/media-nas" and f["host"] == "iw-nas-02"
        ]
        assert len(media_mounts) == 1, (
            f"/mnt/media-nas on iw-nas-02 should be included, found: {media_mounts}"
        )

    def test_tmpfs_excluded_from_filesystems(self, client: TestClient) -> None:
        """tmpfs filesystems are never included."""
        size, avail = self._make_node_fs_entry(
            "home-srv:9100",
            "node-exporter",
            "/run",
            "tmpfs",
            "tmpfs",
            500 * 1024**2,
            490 * 1024**2,
        )
        responses = _make_prom_side_effect(
            up=_ok_up_results(),
            node_size=[size],
            node_avail=[avail],
        )

        with _patch_prometheus(responses):
            r = client.get("/api/homelab/health")

        body = r.json()
        tmpfs_entries = [f for f in body["filesystems"] if f.get("mount") == "/run"]
        assert not tmpfs_entries, f"tmpfs /run must be excluded, found: {tmpfs_entries}"

    def test_worst_filesystem_reflects_highest_severity(self, client: TestClient) -> None:
        """worst_filesystem is the filesystem with highest severity."""
        # Two filesystems: one critical (95%), one ok (30%)
        size_crit, avail_crit = self._make_node_fs_entry(
            "home-srv:9100",
            "node-exporter",
            "/",
            "/dev/sda1",
            "ext4",
            100 * 1024**3,
            5 * 1024**3,  # 95% used
        )
        size_ok, avail_ok = self._make_node_fs_entry(
            "home-srv:9100",
            "node-exporter",
            "/home",
            "/dev/sda2",
            "ext4",
            200 * 1024**3,
            140 * 1024**3,  # 30% used
        )
        responses = _make_prom_side_effect(
            up=_ok_up_results(),
            node_size=[size_crit, size_ok],
            node_avail=[avail_crit, avail_ok],
        )

        with _patch_prometheus(responses):
            r = client.get("/api/homelab/health")

        body = r.json()
        wfs = body["worst_filesystem"]
        assert wfs is not None
        assert wfs["state"] == "critical"
        assert wfs["mount"] == "/"


# ---------------------------------------------------------------------------
# Overall state computation
# ---------------------------------------------------------------------------


class TestOverallState:
    """worst() precedence: critical > warning > unknown > ok."""

    def test_critical_fs_makes_overall_critical_even_if_hosts_ok(self, client: TestClient) -> None:
        """A critical filesystem drives overall to 'critical' even when all hosts are up."""
        size, avail = TestFilesystemStates()._make_node_fs_entry(
            "home-srv:9100",
            "node-exporter",
            "/",
            "/dev/sda1",
            "ext4",
            100 * 1024**3,
            2 * 1024**3,  # 98% used → critical
        )
        responses = _make_prom_side_effect(
            up=_ok_up_results(),
            node_size=[size],
            node_avail=[avail],
        )

        with _patch_prometheus(responses):
            r = client.get("/api/homelab/health")

        body = r.json()
        assert body["overall"] == "critical"

    def test_unknown_host_contributes_unknown_to_overall(self, client: TestClient) -> None:
        """A host with no Prometheus data (unknown) makes overall at least 'unknown'."""
        # Only provide partial up results — exclude iw-dev-01
        up_results = [
            _prom_result({"job": "netdata-home", "instance": "home-srv:19999"}, 1),
            _prom_result({"job": "node-exporter", "instance": "home-srv:9100"}, 1),
            _prom_result({"job": "node-exporter-proxmox", "instance": "iw-home-01:9100"}, 1),
            _prom_result({"job": "qnap-exporter", "instance": "iw-nas-02:9100"}, 1),
        ]
        responses = _make_prom_side_effect(up=up_results)

        with _patch_prometheus(responses):
            r = client.get("/api/homelab/health")

        body = r.json()
        allowed = {"unknown", "warning", "critical"}
        assert body["overall"] in allowed, (
            f"Expected overall in {allowed} when a host is unknown, got '{body['overall']}'"
        )


# ---------------------------------------------------------------------------
# Prometheus unreachable
# ---------------------------------------------------------------------------


class TestPrometheusUnreachable:
    """When Prometheus is unreachable, return HTTP 200 with overall 'unknown'."""

    def test_prometheus_error_returns_200_with_unknown_overall(self, client: TestClient) -> None:
        """On Prometheus connection failure, HTTP 200 with overall='unknown' and stale=True."""

        async def _fail_prom(session: Any, query: str) -> list:
            """Raise to simulate Prometheus unreachable."""
            raise ConnectionError("Prometheus unreachable")

        with patch("dashboard.routers.homelab._prom_query", side_effect=_fail_prom):
            r = client.get("/api/homelab/health")

        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        body = r.json()
        assert body["overall"] == "unknown"
        assert body["stale"] is True
        assert len(body["errors"]) > 0

    def test_prometheus_error_populates_errors_list(self, client: TestClient) -> None:
        """On Prometheus failure, errors list contains at least one error string."""

        async def _fail_prom(session: Any, query: str) -> list:
            """Raise to simulate Prometheus unreachable."""
            raise RuntimeError("connection refused")

        with patch("dashboard.routers.homelab._prom_query", side_effect=_fail_prom):
            r = client.get("/api/homelab/health")

        body = r.json()
        assert isinstance(body["errors"], list)
        assert len(body["errors"]) >= 1
        # Error string should mention the failure somehow
        err_str = " ".join(body["errors"]).lower()
        has_keyword = (
            err_str.find("prom") != -1
            or err_str.find("connect") != -1
            or err_str.find("unavail") != -1
        )
        assert has_keyword, f"Error string lacks expected keyword: {err_str!r}"

    def test_prometheus_error_all_required_keys_present(self, client: TestClient) -> None:
        """Even on Prometheus failure, the response has all required top-level keys."""

        async def _fail_prom(session: Any, query: str) -> list:
            """Raise to simulate Prometheus unreachable."""
            raise RuntimeError("offline")

        with patch("dashboard.routers.homelab._prom_query", side_effect=_fail_prom):
            r = client.get("/api/homelab/health")

        body = r.json()
        missing = _REQUIRED_TOP_LEVEL_KEYS - set(body.keys())
        assert not missing, f"Missing keys on error response: {missing}"


# ---------------------------------------------------------------------------
# Cache behaviour
# ---------------------------------------------------------------------------


class TestCacheBehaviour:
    """Server-side 30s cache prevents hammering Prometheus on every call."""

    def test_second_call_within_ttl_does_not_issue_new_prometheus_queries(
        self, client: TestClient
    ) -> None:
        """A second GET within cache TTL reuses cached data (no new _prom_query calls)."""
        call_count = 0

        async def _counting_prom(session: Any, query: str) -> list:
            """Count calls to simulate checking cache reuse."""
            nonlocal call_count
            call_count += 1
            return []

        with patch("dashboard.routers.homelab._prom_query", side_effect=_counting_prom):
            client.get("/api/homelab/health")
            calls_after_first = call_count
            client.get("/api/homelab/health")
            calls_after_second = call_count

        # Second call must not issue more Prometheus queries than the first
        assert calls_after_second == calls_after_first, (
            f"Cache miss on second call: first={calls_after_first} queries, "
            f"second={calls_after_second} (expected no new queries within TTL)"
        )


# ---------------------------------------------------------------------------
# QNAP-specific section
# ---------------------------------------------------------------------------


class TestQnapSection:
    """QNAP-specific fields in the 'qnap' response section."""

    def test_qnap_disk_temps_populated_from_prometheus(self, client: TestClient) -> None:
        """qnap.disk_temps carries disk temperature data from qnap_disk_temperature_celsius."""
        disk_temp = _prom_result(
            {"job": "qnap-exporter", "instance": "iw-nas-02:9100", "disk": "sda"},
            42.0,
        )
        responses = _make_prom_side_effect(
            up=_ok_up_results(),
            qnap_disk_temp=[disk_temp],
        )

        with _patch_prometheus(responses):
            r = client.get("/api/homelab/health")

        body = r.json()
        disk_temps = body["qnap"]["disk_temps"]
        assert isinstance(disk_temps, list)
        assert len(disk_temps) >= 1
        assert disk_temps[0]["temp_c"] == pytest.approx(42.0)

    def test_qnap_uptime_populated_from_prometheus(self, client: TestClient) -> None:
        """qnap.uptime_seconds carries value from qnap_uptime_seconds."""
        uptime = _prom_result(
            {"job": "qnap-exporter", "instance": "iw-nas-02:9100"},
            86400.0,  # 1 day
        )
        responses = _make_prom_side_effect(
            up=_ok_up_results(),
            qnap_uptime=[uptime],
        )

        with _patch_prometheus(responses):
            r = client.get("/api/homelab/health")

        body = r.json()
        assert body["qnap"]["uptime_seconds"] == 86400

    def test_qnap_disk_temp_alert_true_when_any_alert(self, client: TestClient) -> None:
        """qnap.disk_temp_alert is True when qnap_disk_temperature_alert returns 1."""
        alert = _prom_result(
            {"job": "qnap-exporter", "instance": "iw-nas-02:9100", "disk": "sdb"},
            1.0,
        )
        responses = _make_prom_side_effect(
            up=_ok_up_results(),
            qnap_disk_alert=[alert],
        )

        with _patch_prometheus(responses):
            r = client.get("/api/homelab/health")

        body = r.json()
        assert body["qnap"]["disk_temp_alert"] is True

    def test_qnap_disk_temp_alert_false_when_no_alert(self, client: TestClient) -> None:
        """qnap.disk_temp_alert is False when no qnap_disk_temperature_alert results."""
        responses = _make_prom_side_effect(up=_ok_up_results())

        with _patch_prometheus(responses):
            r = client.get("/api/homelab/health")

        body = r.json()
        assert body["qnap"]["disk_temp_alert"] is False

    def test_qnap_disk_temp_alert_false_when_all_disks_report_zero(
        self, client: TestClient
    ) -> None:
        """Populated alert series that are all 0 must NOT trip the alert (regression)."""
        zero_alerts = [
            _prom_result(
                {"job": "qnap-exporter", "instance": "iw-nas-02:9100", "disk": str(d)},
                0.0,
            )
            for d in range(1, 5)
        ]
        responses = _make_prom_side_effect(
            up=_ok_up_results(),
            qnap_disk_alert=zero_alerts,
        )

        with _patch_prometheus(responses):
            r = client.get("/api/homelab/health")

        body = r.json()
        assert body["qnap"]["disk_temp_alert"] is False

    def test_qnap_network_status_populated(self, client: TestClient) -> None:
        """qnap.network contains nic entries from qnap_network_status."""
        net = _prom_result(
            {"job": "qnap-exporter", "instance": "iw-nas-02:9100", "nic": "eth0"},
            1.0,  # 1 = up
        )
        responses = _make_prom_side_effect(up=_ok_up_results(), qnap_net=[net])

        with _patch_prometheus(responses):
            r = client.get("/api/homelab/health")

        body = r.json()
        network = body["qnap"]["network"]
        assert isinstance(network, list)
        assert len(network) >= 1
        eth0 = next((n for n in network if n["nic"] == "eth0"), None)
        assert eth0 is not None
        assert eth0["status"] == "up"


# ---------------------------------------------------------------------------
# Proxmox-specific section
# ---------------------------------------------------------------------------


class TestProxmoxSection:
    """Proxmox-specific fields in the 'proxmox' response section."""

    def test_proxmox_up_reflects_node_exporter_proxmox_target(self, client: TestClient) -> None:
        """proxmox.up is 'ok' when node-exporter-proxmox reports up=1."""
        responses = _make_prom_side_effect(up=_ok_up_results())

        with _patch_prometheus(responses):
            r = client.get("/api/homelab/health")

        body = r.json()
        assert body["proxmox"]["up"] == "ok"

    def test_proxmox_filesystems_populated_from_iw_home_01(self, client: TestClient) -> None:
        """proxmox.filesystems contains filesystems sourced from iw-home-01."""
        # Use iw-home-01: device prefix which forces sourceHost → iw-home-01
        metric = {
            "job": "node-exporter-proxmox",
            "instance": "iw-home-01:9100",
            "mountpoint": "/",
            "device": "/dev/sda1",
            "fstype": "ext4",
        }
        size = _prom_result(metric, 100 * 1024**3)
        avail = _prom_result(metric, 70 * 1024**3)
        responses = _make_prom_side_effect(
            up=_ok_up_results(),
            node_size=[size],
            node_avail=[avail],
        )

        with _patch_prometheus(responses):
            r = client.get("/api/homelab/health")

        body = r.json()
        proxmox_fs = body["proxmox"]["filesystems"]
        assert isinstance(proxmox_fs, list)
        assert len(proxmox_fs) >= 1
        root_fs = next((f for f in proxmox_fs if f["mount"] == "/"), None)
        assert root_fs is not None


# ---------------------------------------------------------------------------
# Integration test (skip when Prometheus unreachable)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_live_prometheus_health_check_returns_200_with_valid_shape(
    client: TestClient,
) -> None:
    """Integration smoke test: real Prometheus (IW_CORE_HOMELAB_PROMETHEUS_URL) returns valid JSON.

    Skipped automatically when Prometheus is unreachable.
    """
    import socket
    from urllib.parse import urlparse

    from dashboard.routers import homelab

    parsed = urlparse(homelab._PROM_BASE)
    host, port = parsed.hostname or "localhost", parsed.port or 9090
    try:
        sock = socket.create_connection((host, port), timeout=2)
        sock.close()
    except (OSError, ConnectionRefusedError):
        pytest.skip(f"Prometheus at {host}:{port} is unreachable")

    # Do NOT patch _prom_query — use the live Prometheus
    r = client.get("/api/homelab/health")

    assert r.status_code == 200
    body = r.json()
    missing = _REQUIRED_TOP_LEVEL_KEYS - set(body.keys())
    assert not missing, f"Live Prometheus response missing keys: {missing}"
    assert body["overall"] in {"ok", "warning", "critical", "unknown"}
    assert isinstance(body["hosts"], list)
    assert len(body["hosts"]) == 4
