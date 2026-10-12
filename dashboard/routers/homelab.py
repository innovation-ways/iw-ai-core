"""Homelab health endpoint — server-side mirror of homepage_homelab_health_embed.html.

Provides GET /api/homelab/health which queries Prometheus (IW_CORE_HOMELAB_PROMETHEUS_URL)
and returns a structured JSON payload describing the health of the homelab hosts,
filesystems, QNAP device, and Proxmox server.

The logic faithfully ports the JavaScript collect() function from
dashboard/static/homepage_homelab_health_embed.html, including all threshold
rules, host→name mappings, filesystem allow/deny rules, and the Proxmox RAM
exception.

A 30-second in-process cache prevents hammering Prometheus; Home Assistant polls
this endpoint every ~120 seconds so the cache only avoids burst-duplicate requests.
On total Prometheus failure the endpoint returns HTTP 200 with overall='unknown',
stale=True, and an errors list — never HTTP 500.
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import re
import time
from typing import Any

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/homelab", tags=["homelab"])

# ---------------------------------------------------------------------------
# Constants — mirrors the JS embed exactly
# ---------------------------------------------------------------------------

#: Prometheus base URL (no auth); set IW_CORE_HOMELAB_PROMETHEUS_URL in .env.
_PROM_BASE = os.environ.get("IW_CORE_HOMELAB_PROMETHEUS_URL", "http://localhost:9090").rstrip("/")

#: job label → canonical host name
_HOSTS: dict[str, str] = {
    "netdata-home": "home-srv",
    "node-exporter": "home-srv",
    "netdata-dev": "iw-dev-01",
    "node-exporter-proxmox": "iw-home-01",
    "qnap-exporter": "iw-nas-02",
}

#: All hosts the dashboard expects to see data for.
_EXPECTED: list[str] = ["home-srv", "iw-dev-01", "iw-home-01", "iw-nas-02"]

#: Human-readable roles for the strict response contract.
_HOST_ROLES: dict[str, str] = {
    "home-srv": "Servidor Docker/Casa",
    "iw-dev-01": "Servidor de Desenvolvimento",
    "iw-home-01": "Servidor Proxmox",
    "iw-nas-02": "NAS QNAP",
}

#: Filesystem types that are always excluded (pseudo/virtual).
_FS_DENY_RE = re.compile(
    r"^(tmpfs|devtmpfs|overlay|squashfs|ramfs|proc|sysfs|cgroup|cgroup2|nsfs|"
    r"tracefs|debugfs|securityfs|pstore|autofs|mqueue|hugetlbfs|configfs|binfmt_misc)$"
)

#: Filesystem mount-points that are explicitly included.
_FS_ALLOW: frozenset[str] = frozenset(
    [
        "/",
        "/home",
        "/opt/data",
        "/var",
        "/var/lib/docker",
        "/mnt/git",
        "/mnt/nas",
        "/mnt/media-nas",
        "/mnt/backups-nas",
        "/mnt/backups",
        "/mnt/media",
        "/mnt/photos",
        "/mnt/appdata",
        "/mnt/databases",
        "/mnt/docker",
        "/mnt/frigate",
    ]
)

#: Prometheus queries in the exact order _fetch_all issues them.
_QUERIES: list[str] = [
    "up",
    'ALERTS{alertstate="firing"}',
    'netdata_system_cpu_percentage_average{dimension!="idle"}',
    "netdata_system_ram_MiB_average",
    "netdata_disk_space_GiB_average",
    (
        'node_filesystem_size_bytes{fstype!~"tmpfs|devtmpfs|overlay|squashfs|fuse.*|ramfs|'
        "proc|sysfs|cgroup.*|nsfs|tracefs|debugfs|securityfs|pstore|autofs|mqueue|"
        'hugetlbfs|configfs|binfmt_misc"}'
    ),
    (
        'node_filesystem_avail_bytes{fstype!~"tmpfs|devtmpfs|overlay|squashfs|fuse.*|ramfs|'
        "proc|sysfs|cgroup.*|nsfs|tracefs|debugfs|securityfs|pstore|autofs|mqueue|"
        'hugetlbfs|configfs|binfmt_misc"}'
    ),
    '100 * (1 - avg by (job,instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])))',
    "node_memory_MemTotal_bytes",
    "node_memory_MemAvailable_bytes",
    "qnap_cpu_usage_percent",
    "qnap_memory_used_percent",
    "qnap_cpu_temperature_celsius",
    "qnap_system_temperature_celsius",
    "qnap_disk_temperature_celsius",
    "qnap_disk_temperature_alert",
    "qnap_network_status",
    "qnap_uptime_seconds",
    # --- temperatures (appended; keep before any future queries and mirror the unpack order) ---
    "netdata_system_hw_sensor_temperature_input_degrees_Celsius_average",  # home-srv, iw-dev-01
    "node_hwmon_temp_celsius",  # home-srv, iw-home-01
    "netdata_nvidia_smi_gpu_temperature_Celsius_average",  # iw-dev-01 GPU
    "nvme_temperature_celsius",  # NVMe disks
    "node_hwmon_sensor_label",  # (chip,sensor)->friendly label
]

#: Cache TTL in seconds — avoids hammering Prometheus on burst requests.
_CACHE_TTL_SECS: int = 30

# Module-level cache dict; cleared between tests.
_cache: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# State helper functions — exact ports of the JS embed equivalents
# ---------------------------------------------------------------------------


def _pressure_state(p: float | None) -> str:
    """Return 'ok', 'warning', or 'critical' for a CPU/RAM percentage.

    Args:
        p: Pressure percentage (0–100) or None/NaN when unknown.

    Returns:
        State string: 'critical' at >=90, 'warning' at >=80, 'ok' otherwise,
        'unknown' when p is None or NaN.
    """
    if p is None or math.isnan(p):
        return "unknown"
    if p >= 90:
        return "critical"
    if p >= 80:
        return "warning"
    return "ok"


def _mem_state_for_host(host_name: str, mem_pct: float | None) -> str:
    """Return mem state, applying the Proxmox iw-home-01 RAM exception.

    iw-home-01 RAM is display-only (reserved by Proxmox guest allocations),
    so its mem_state is always 'ok' regardless of the raw percentage.

    Args:
        host_name: Canonical host name.
        mem_pct: RAM used percentage or None.

    Returns:
        'ok' unconditionally for iw-home-01; otherwise delegates to
        _pressure_state.
    """
    if host_name == "iw-home-01":
        return "ok"
    return _pressure_state(mem_pct)


def _host_state(up: str, cpu_pct: float | None, mem_pct: float | None, host_name: str) -> str:
    """Compute the worst-case host state from up/CPU/RAM.

    Args:
        up: 'ok', 'critical', or 'unknown'.
        cpu_pct: CPU usage percentage or None.
        mem_pct: RAM usage percentage or None.
        host_name: Canonical host name (for Proxmox exception).

    Returns:
        Worst state across up, cpu_state, mem_state.
    """
    return _worst([up, _pressure_state(cpu_pct), _mem_state_for_host(host_name, mem_pct)])


def _worst(states: list[str]) -> str:
    """Return the worst state from a list of state strings.

    Precedence: critical > warning > unknown > ok.

    Args:
        states: List of state strings.

    Returns:
        The highest-severity state.
    """
    if "critical" in states:
        return "critical"
    if "warning" in states:
        return "warning"
    if "unknown" in states:
        return "unknown"
    return "ok"


def _fs_state(used_pct: float | None, avail_gib: float) -> str:
    """Classify a filesystem by used-percentage and available space.

    Mirrors the JS fsState() function exactly:
    - usedPct>=95 OR avail<5 GiB → critical
    - usedPct>=90 OR avail<10 GiB → critical
    - usedPct>=80 OR avail<20 GiB → warning
    - else → ok

    Args:
        used_pct: Percentage of space used (0–100) or None/NaN.
        avail_gib: Available space in GiB.

    Returns:
        State string.
    """
    if used_pct is None or math.isnan(used_pct):
        return "unknown"
    if used_pct >= 95 or avail_gib < 5:
        return "critical"
    if used_pct >= 90 or avail_gib < 10:
        return "critical"
    if used_pct >= 80 or avail_gib < 20:
        return "warning"
    return "ok"


def _metric_key(metric: dict[str, str]) -> str:
    """Build a compound key from job+instance labels.

    Args:
        metric: Prometheus metric label dict.

    Returns:
        '<job>|<instance>' string.
    """
    return f"{metric.get('job', '')}|{metric.get('instance', '')}"


def _source_host(metric: dict[str, str]) -> str:
    """Map a Prometheus metric's labels to a canonical host name.

    Mirrors the JS sourceHost() function, checking device prefixes first
    before falling back to the job→host map.

    Args:
        metric: Prometheus metric label dict.

    Returns:
        Canonical host name string.
    """
    if metric.get("host"):
        return metric["host"]
    dev = metric.get("device", "")
    if dev.startswith("iw-home-01:") or "/hdd-pool/" in dev or "/ssd-pool/" in dev:
        return "iw-home-01"
    if dev.startswith("//") or "media-nas" in dev.lower():
        return "iw-nas-02"
    job = metric.get("job", "")
    if job in _HOSTS:
        return _HOSTS[job]
    return metric.get("instance") or job or "unknown"


def _include_fs(metric: dict[str, str]) -> bool:
    """Decide whether a filesystem metric should be included.

    Mirrors the JS includeFs() function — deny pseudo fstypes first,
    then allow explicitly-listed mounts or NFS/CIFS device prefixes.

    Args:
        metric: Prometheus metric label dict.

    Returns:
        True when the filesystem should appear in the response.
    """
    mount = metric.get("mount_point") or metric.get("mountpoint") or ""
    fstype = metric.get("filesystem") or metric.get("fstype") or ""
    device = metric.get("device", "")
    if not mount:
        return False
    if _FS_DENY_RE.match(fstype):
        return False
    if mount in _FS_ALLOW:
        return True
    # NFS exports from iw-home-01 or CIFS from NAS
    return device.startswith(("iw-home-01:", "//"))


def _safe_float(v: float | None) -> float | None:
    """Return v rounded to 2 dp, or None when v is None or NaN.

    Args:
        v: Raw float or None.

    Returns:
        Rounded float or None.
    """
    if v is None or math.isnan(v):
        return None
    return round(v, 2)


def _val(item: dict[str, Any]) -> float:
    """Extract the numeric value from a Prometheus instant-query result.

    Args:
        item: A single result element with 'value': [ts, stringval].

    Returns:
        Float value, or NaN on parse failure.
    """
    try:
        v = item.get("value", [None, None])
        return float(v[1]) if v and v[1] is not None else math.nan
    except (TypeError, ValueError, IndexError):
        return math.nan


# ---------------------------------------------------------------------------
# Prometheus HTTP helpers
# ---------------------------------------------------------------------------


async def _prom_query(session: httpx.AsyncClient, query: str) -> list[dict[str, Any]]:
    """Execute a single Prometheus instant query and return the result list.

    Args:
        session: Shared httpx.AsyncClient for the batch of queries.
        query: PromQL expression string.

    Returns:
        List of Prometheus result dicts; empty list if the response is empty.

    Raises:
        RuntimeError: When Prometheus returns a non-success status or HTTP error.
        httpx.HTTPError: On network-level failures.
    """
    url = f"{_PROM_BASE}/api/v1/query"
    response = await session.get(url, params={"query": query})
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != "success":
        raise RuntimeError(f"Prometheus query failed for: {query!r}")
    return payload.get("data", {}).get("result") or []


async def _fetch_all() -> list[list[dict[str, Any]]]:
    """Fetch all required Prometheus queries concurrently.

    Returns:
        List of result lists in the same order as _QUERIES.

    Raises:
        Exception: Any network or Prometheus error propagated to the caller.
    """
    async with httpx.AsyncClient(timeout=10.0) as session:
        tasks = [_prom_query(session, q) for q in _QUERIES]
        return list(await asyncio.gather(*tasks))


# ---------------------------------------------------------------------------
# Core computation logic (ported from the JS collect() function)
# ---------------------------------------------------------------------------


def _compute(results: list[list[dict[str, Any]]]) -> dict[str, Any]:
    """Compute the full homelab health payload from raw Prometheus results.

    Faithful port of the JS collect() function plus the QNAP/Proxmox extras.
    All threshold values, include/exclude rules, and state computation functions
    are identical to the embed file.

    Args:
        results: List of result lists from _fetch_all(), in _QUERIES order.

    Returns:
        Dict matching the strict JSON response contract.
    """
    (
        up_r,
        alerts_r,
        net_cpu_r,
        net_ram_r,
        net_fs_r,
        node_size_r,
        node_avail_r,
        node_cpu_r,
        node_mem_tot_r,
        node_mem_avail_r,
        qnap_cpu_r,
        qnap_mem_r,
        qnap_cpu_temp_r,
        qnap_sys_temp_r,
        qnap_disk_temp_r,
        qnap_disk_alert_r,
        qnap_net_r,
        qnap_uptime_r,
        net_temp_r,
        node_hwmon_r,
        gpu_temp_r,
        nvme_temp_r,
        node_hwmon_label_r,
    ) = results

    # -----------------------------------------------------------------------
    # Host states — initialise all expected hosts as unknown
    # -----------------------------------------------------------------------
    # Each entry: {name, up, cpu, mem, state}
    host_map: dict[str, dict[str, Any]] = {
        h: {
            "name": h,
            "up": "unknown",
            "cpu": None,
            "mem": None,
            "state": "unknown",
            "detail": "no Prometheus target",
        }
        for h in _EXPECTED
    }

    # up{job} == 1 → "ok", else "critical"
    for item in up_r:
        m = item["metric"]
        job = m.get("job", "")
        h = _HOSTS.get(job)
        if not h:
            continue
        v = _val(item)
        up_str = "ok" if v == 1 else "critical"
        detail = f"{job} {'up' if v == 1 else 'down'}"
        existing = host_map[h]
        # Merge: if host already had an ok entry, keep it (first wins) unless
        # the new entry is critical (worst wins for up state).
        if existing["up"] == "unknown" or up_str == "critical":
            host_map[h] = {**existing, "up": up_str, "detail": detail}

    # -----------------------------------------------------------------------
    # CPU: netdata summed by job (baseline), then node_cpu overrides
    # -----------------------------------------------------------------------
    cpu_agg: dict[str, float] = {}
    for item in net_cpu_r:
        m = item["metric"]
        h = _HOSTS.get(m.get("job", ""))
        if not h:
            continue
        v = _val(item)
        if not math.isnan(v):
            cpu_agg[h] = cpu_agg.get(h, 0.0) + v

    for h, c in cpu_agg.items():
        if h in host_map:
            host_map[h] = {**host_map[h], "cpu": max(0.0, min(100.0, c))}

    # node_cpu results override the netdata baseline
    for item in node_cpu_r:
        m = item["metric"]
        h = _HOSTS.get(m.get("job", ""))
        if h and h in host_map:
            v = _val(item)
            host_map[h] = {**host_map[h], "cpu": None if math.isnan(v) else v}

    # -----------------------------------------------------------------------
    # RAM: netdata dimensions (free/used/cached/buffers), then node override
    # -----------------------------------------------------------------------
    ram_dims: dict[str, dict[str, float]] = {}
    for item in net_ram_r:
        m = item["metric"]
        h = _HOSTS.get(m.get("job", ""))
        if not h:
            continue
        dim = m.get("dimension", "")
        v = _val(item)
        if not math.isnan(v):
            if h not in ram_dims:
                ram_dims[h] = {}
            ram_dims[h][dim] = v

    for h, dims in ram_dims.items():
        if h not in host_map:
            continue
        total = (
            dims.get("free", 0.0)
            + dims.get("used", 0.0)
            + dims.get("cached", 0.0)
            + dims.get("buffers", 0.0)
        )
        mem_pct = (100.0 * dims.get("used", 0.0) / total) if total else None
        host_map[h] = {**host_map[h], "mem": mem_pct}

    # node memory override: 100*(1 - avail/total)
    mem_tot_map: dict[str, float] = {_metric_key(x["metric"]): _val(x) for x in node_mem_tot_r}
    for item in node_mem_avail_r:
        m = item["metric"]
        h = _HOSTS.get(m.get("job", ""))
        if not h or h not in host_map:
            continue
        node_total = mem_tot_map.get(_metric_key(m))
        avail_v = _val(item)
        if node_total and not math.isnan(avail_v) and node_total > 0:
            mem_pct = 100.0 * (1.0 - avail_v / node_total)
            host_map[h] = {**host_map[h], "mem": mem_pct}

    # QNAP CPU + memory (direct metrics override netdata/node)
    for item in qnap_cpu_r:
        v = _val(item)
        if not math.isnan(v):
            host_map["iw-nas-02"] = {**host_map["iw-nas-02"], "cpu": v}

    for item in qnap_mem_r:
        v = _val(item)
        if not math.isnan(v):
            host_map["iw-nas-02"] = {**host_map["iw-nas-02"], "mem": v}

    # -----------------------------------------------------------------------
    # Compute final host state and mem_reserved_pct for Proxmox
    # -----------------------------------------------------------------------
    proxmox_mem_reserved: float | None = None

    hosts_list: list[dict[str, Any]] = []
    for h in _EXPECTED:
        obj = host_map[h]
        cpu = obj["cpu"]
        mem = obj["mem"]
        state = _host_state(obj["up"], cpu, mem, h)

        if h == "iw-home-01" and mem is not None:
            proxmox_mem_reserved = mem

        hosts_list.append(
            {
                "name": h,
                "role": _HOST_ROLES[h],
                "up": obj["up"],
                "cpu": _safe_float(cpu),
                "mem": _safe_float(mem),
                "cpu_state": _pressure_state(cpu),
                "mem_state": _mem_state_for_host(h, mem),
                "state": state,
                "detail": obj.get("detail", ""),
            }
        )

    # -----------------------------------------------------------------------
    # Filesystems — netdata (GiB) and node_exporter (bytes)
    # -----------------------------------------------------------------------
    fs_map: dict[str, dict[str, Any]] = {}

    # Netdata netdata_disk_space_GiB_average
    for item in net_fs_r:
        m = item["metric"]
        if not _include_fs(m):
            continue
        mount = m.get("mount_point", "")
        fstype = m.get("filesystem", "")
        key = f"{m.get('job', '')}|{m.get('instance', '')}|{mount}|{fstype}"
        rec = fs_map.get(key) or {
            "host": _source_host(m),
            "mount": mount,
            "fs": fstype,
            "device": m.get("device", ""),
            "used": 0.0,
            "avail": 0.0,
            "total": 0.0,
        }
        v = _val(item)
        dim = m.get("dimension", "")
        if dim == "used":
            rec["used"] = v
        elif dim == "avail":
            rec["avail"] = v
        fs_map[key] = rec

    # node_exporter node_filesystem_size_bytes + avail_bytes (bytes → GiB)
    def _node_fs_key(m: dict[str, str]) -> str:
        """Build a compound key from node_filesystem label set."""
        return (
            f"{m.get('instance', '')}|{m.get('mountpoint', '')}"
            f"|{m.get('device', '')}|{m.get('fstype', '')}"
        )

    node_sizes: dict[str, dict[str, Any]] = {}
    for item in node_size_r:
        m = item["metric"]
        if not _include_fs(m):
            continue
        node_sizes[_node_fs_key(m)] = item

    for item in node_avail_r:
        m = item["metric"]
        if not _include_fs(m):
            continue
        k = _node_fs_key(m)
        size_item = node_sizes.get(k)
        if not size_item:
            continue
        size_gib = _val(size_item) / (1024**3)
        avail_gib = _val(item) / (1024**3)
        used_gib = size_gib - avail_gib
        fs_map[f"node|{k}"] = {
            "host": _source_host(m),
            "mount": m.get("mountpoint", ""),
            "fs": m.get("fstype", ""),
            "device": m.get("device", ""),
            "used": used_gib,
            "avail": avail_gib,
            "total": size_gib,
        }

    # Finalise filesystems: compute totals, usedPct, state, filter, sort
    _state_rank = {"critical": 3, "warning": 2, "unknown": 1, "ok": 0}

    filesystems: list[dict[str, Any]] = []
    for rec in fs_map.values():
        total = rec["total"] or (rec["used"] + rec["avail"])
        if total <= 0.05:  # filter sub-50MiB entries
            continue
        used_pct = (100.0 * rec["used"] / total) if total else math.nan
        avail_gib = rec["avail"]
        state = _fs_state(used_pct if not math.isnan(used_pct) else None, avail_gib)

        # Exclude iw-nas-02 mounts whose path contains "backup"
        host = rec["host"]
        mount = rec["mount"] or ""
        if host == "iw-nas-02" and "backup" in mount.lower():
            continue

        filesystems.append(
            {
                "host": host,
                "mount": mount,
                "device": rec.get("device", ""),
                "total_gib": round(total, 3),
                "used_gib": round(rec["used"], 3),
                "avail_gib": round(avail_gib, 3),
                "used_pct": round(used_pct, 2) if not math.isnan(used_pct) else None,
                "state": state,
            }
        )

    # Sort: critical first, then by used_pct descending
    filesystems.sort(key=lambda f: (-_state_rank.get(f["state"], 0), -(f["used_pct"] or 0.0)))

    worst_fs: dict[str, Any] | None = filesystems[0] if filesystems else None
    worst_fs_out: dict[str, Any] | None = None
    if worst_fs:
        worst_fs_out = {
            "host": worst_fs["host"],
            "mount": worst_fs["mount"],
            "used_pct": worst_fs["used_pct"],
            "avail_gib": worst_fs["avail_gib"],
            "state": worst_fs["state"],
        }

    # -----------------------------------------------------------------------
    # QNAP detail section
    # -----------------------------------------------------------------------
    nas = host_map["iw-nas-02"]
    nas_cpu = nas["cpu"]
    nas_mem = nas["mem"]

    # cpu_temp
    qnap_cpu_temp: float | None = None
    if qnap_cpu_temp_r:
        v = _val(qnap_cpu_temp_r[0])
        qnap_cpu_temp = None if math.isnan(v) else round(v, 1)

    # system_temp
    qnap_sys_temp: float | None = None
    if qnap_sys_temp_r:
        v = _val(qnap_sys_temp_r[0])
        qnap_sys_temp = None if math.isnan(v) else round(v, 1)

    # disk temperatures
    disk_temps: list[dict[str, Any]] = []
    disk_alert_map: dict[str, int] = {}
    for item in qnap_disk_alert_r:
        disk_id = item["metric"].get("disk", item["metric"].get("instance", "?"))
        disk_alert_map[disk_id] = int(_val(item))

    for item in qnap_disk_temp_r:
        disk_id = item["metric"].get("disk", item["metric"].get("instance", "?"))
        temp_v = _val(item)
        disk_temps.append(
            {
                "id": disk_id,
                "temp_c": round(temp_v, 1) if not math.isnan(temp_v) else None,
                "alert": disk_alert_map.get(disk_id, 0),
            }
        )

    # Alert only when a disk actually reports a non-zero alert flag.
    # (A populated disk_alert_map of all-zeros is normal and must NOT trip the alert.)
    disk_temp_alert = any(int(v) != 0 for v in disk_alert_map.values())

    # network
    network: list[dict[str, Any]] = []
    for item in qnap_net_r:
        m = item["metric"]
        nic = m.get("nic", m.get("interface", "?"))
        v = _val(item)
        network.append(
            {
                "nic": nic,
                "status": "up" if v == 1 else "down",
            }
        )

    # uptime
    qnap_uptime: int | None = None
    if qnap_uptime_r:
        v = _val(qnap_uptime_r[0])
        qnap_uptime = int(v) if not math.isnan(v) else None

    nas_obj = host_map["iw-nas-02"]
    qnap_section: dict[str, Any] = {
        "up": nas_obj["up"],
        "cpu": _safe_float(nas_cpu),
        "mem": _safe_float(nas_mem),
        "uptime_seconds": qnap_uptime,
        "cpu_temp_c": qnap_cpu_temp,
        "system_temp_c": qnap_sys_temp,
        "disk_temps": disk_temps,
        "disk_temp_alert": disk_temp_alert,
        "network": network,
    }

    # -----------------------------------------------------------------------
    # Proxmox section
    # -----------------------------------------------------------------------
    proxmox_host = host_map["iw-home-01"]
    proxmox_cpu = proxmox_host["cpu"]
    proxmox_fs = [f for f in filesystems if f["host"] == "iw-home-01"]
    proxmox_section: dict[str, Any] = {
        "up": proxmox_host["up"],
        "cpu": _safe_float(proxmox_cpu),
        "mem_reserved_pct": _safe_float(proxmox_mem_reserved),
        "filesystems": [
            {
                "mount": f["mount"],
                "total_gib": f["total_gib"],
                "used_pct": f["used_pct"],
                "avail_gib": f["avail_gib"],
                "state": f["state"],
            }
            for f in proxmox_fs
        ],
    }

    # -----------------------------------------------------------------------
    # Temperatures — attach a per-host `temps` list (+ cpu/gpu summary) to each
    # host object. Sources: netdata hw sensors (home-srv, iw-dev-01), node_hwmon
    # (home-srv, iw-home-01), NVMe, netdata nvidia-smi (iw-dev-01 GPU); the QNAP
    # temps come from the qnap section computed above.
    # -----------------------------------------------------------------------
    temps_by_host: dict[str, list[dict[str, Any]]] = {h: [] for h in _EXPECTED}

    def _add_temp(host: str | None, label: str, raw: float) -> None:
        if host and host in temps_by_host and not math.isnan(raw):
            temps_by_host[host].append({"label": label, "c": round(raw, 1)})

    # (job, chip, sensor) -> friendly hwmon label (e.g. Tctl, Composite)
    hwmon_label: dict[tuple[str, str, str], str] = {}
    for item in node_hwmon_label_r:
        m = item["metric"]
        lbl = m.get("label")
        if lbl:
            hwmon_label[(m.get("job", ""), m.get("chip", ""), m.get("sensor", ""))] = lbl

    def _pretty_hwmon(m: dict[str, str]) -> str | None:
        """Human label for a node_hwmon reading. Returns None for NVMe (handled separately)."""
        chip = m.get("chip", "") or ""
        sensor = m.get("sensor", "") or ""
        friendly = hwmon_label.get((m.get("job", ""), chip, sensor)) or m.get("label")
        if chip.startswith("nvme"):
            return None  # NVMe temps come from nvme_temperature_celsius (avoid duplicates)
        if friendly and friendly.lower() in ("tctl", "tdie", "package id 0"):
            return friendly
        if chip.startswith(("coretemp", "k10temp", "zenpower")):
            return friendly or "CPU"
        if chip.startswith(("ieee80211", "iwlwifi")):
            return "WiFi"
        return friendly or sensor or "temp"

    for item in net_temp_r:
        m = item["metric"]
        _add_temp(_HOSTS.get(m.get("job", "")), m.get("label", "sensor"), _val(item))
    for item in node_hwmon_r:
        m = item["metric"]
        label = _pretty_hwmon(m)
        if label is not None:
            _add_temp(_HOSTS.get(m.get("job", "")), label, _val(item))
    for item in nvme_temp_r:
        m = item["metric"]
        dev = m.get("device") or m.get("instance", "")
        _add_temp(_HOSTS.get(m.get("job", "")), ("NVMe " + dev).strip(), _val(item))

    gpu_temp_c: float | None = None
    for item in gpu_temp_r:
        m = item["metric"]
        if _HOSTS.get(m.get("job", "")) == "iw-dev-01":
            v = _val(item)
            if not math.isnan(v):
                gpu_temp_c = round(v, 1)

    # QNAP host temps come from the qnap section (cpu/system/per-disk)
    nas_temps: list[dict[str, Any]] = []
    if qnap_cpu_temp is not None:
        nas_temps.append({"label": "CPU", "c": qnap_cpu_temp})
    if qnap_sys_temp is not None:
        nas_temps.append({"label": "Sistema", "c": qnap_sys_temp})
    for d in disk_temps:
        if d.get("temp_c") is not None:
            nas_temps.append({"label": f"Disco {d['id']}", "c": d["temp_c"]})
    temps_by_host["iw-nas-02"] = nas_temps

    #: labels (lowercased) that best represent a CPU package/core temperature
    cpu_temp_prefs = ("tctl", "tdie", "package id 0", "cpu", "core 0", "temp1", "composite")

    for h in hosts_list:
        ts_raw = temps_by_host.get(h["name"], [])
        seen: set[str] = set()  # dedup by label (netdata + node_hwmon can read the same chip)
        ts: list[dict[str, Any]] = []
        for t in ts_raw:
            if t["label"] not in seen:
                seen.add(t["label"])
                ts.append(t)
        h["temps"] = ts
        h["max_temp_c"] = max((t["c"] for t in ts), default=None)
        # CPU temp only when a CPU-like sensor is actually present (home-srv is a VM: no CPU sensor)
        cpu_t: float | None = None
        for pref in cpu_temp_prefs:
            for t in ts:
                if t["label"].lower() == pref:
                    cpu_t = t["c"]
                    break
            if cpu_t is not None:
                break
        h["cpu_temp_c"] = cpu_t
        if h["name"] == "iw-dev-01":
            h["gpu_temp_c"] = gpu_temp_c

    # -----------------------------------------------------------------------
    # Overall state
    # -----------------------------------------------------------------------
    alert_count = len(alerts_r)
    alert_state = "critical" if alert_count > 0 else "ok"

    worst_fs_state = worst_fs["state"] if worst_fs else "ok"
    worst_host_state = _worst([h["state"] for h in hosts_list])
    overall = _worst([worst_fs_state, worst_host_state, alert_state])

    hosts_ok = sum(1 for h in hosts_list if h["state"] == "ok")
    stale = any(h["up"] == "unknown" for h in hosts_list)

    now = time.time()
    import datetime as _dt

    generated_at = _dt.datetime.fromtimestamp(now, tz=_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "generated_at": generated_at,
        "generated_ts": int(now),
        "overall": overall,
        "alerts": {"firing": alert_count, "state": alert_state},
        "hosts_ok": hosts_ok,
        "hosts_total": len(_EXPECTED),
        "hosts": hosts_list,
        "filesystems": filesystems,
        "worst_filesystem": worst_fs_out,
        "qnap": qnap_section,
        "proxmox": proxmox_section,
        "stale": stale,
        "errors": [],
    }


# ---------------------------------------------------------------------------
# Cache wrapper
# ---------------------------------------------------------------------------


def _get_cached() -> dict[str, Any] | None:
    """Return the cached payload if it is still within TTL.

    Returns:
        Cached payload dict or None if expired/absent.
    """
    entry: dict[str, Any] | None = _cache.get("payload")
    ts = _cache.get("ts", 0.0)
    if entry is not None and (time.monotonic() - ts) < _CACHE_TTL_SECS:
        return entry
    return None


def _set_cached(payload: dict[str, Any]) -> None:
    """Store payload in cache with the current monotonic timestamp.

    Args:
        payload: Computed homelab health payload.
    """
    _cache["payload"] = payload
    _cache["ts"] = time.monotonic()


# ---------------------------------------------------------------------------
# Failure response builder
# ---------------------------------------------------------------------------


def _failure_response(error: Exception) -> dict[str, Any]:
    """Build a safe 'unknown' response when Prometheus is unreachable.

    On total Prometheus failure the contract requires HTTP 200 with
    overall='unknown', stale=True, and errors populated — never HTTP 500.

    Args:
        error: The exception that caused the failure.

    Returns:
        Minimal valid payload matching the strict contract.
    """
    import datetime as _dt

    now = time.time()
    generated_at = _dt.datetime.fromtimestamp(now, tz=_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "generated_at": generated_at,
        "generated_ts": int(now),
        "overall": "unknown",
        "alerts": {"firing": 0, "state": "ok"},
        "hosts_ok": 0,
        "hosts_total": len(_EXPECTED),
        "hosts": [
            {
                "name": host_name,
                "role": _HOST_ROLES[host_name],
                "up": "unknown",
                "cpu": None,
                "mem": None,
                "cpu_state": "unknown",
                "mem_state": "unknown",
                "state": "unknown",
                "detail": "Prometheus unavailable",
            }
            for host_name in _EXPECTED
        ],
        "filesystems": [],
        "worst_filesystem": None,
        "qnap": {
            "up": "unknown",
            "cpu": None,
            "mem": None,
            "uptime_seconds": None,
            "cpu_temp_c": None,
            "system_temp_c": None,
            "disk_temps": [],
            "disk_temp_alert": False,
            "network": [],
        },
        "proxmox": {
            "up": "unknown",
            "cpu": None,
            "mem_reserved_pct": None,
            "filesystems": [],
        },
        "stale": True,
        "errors": [f"Prometheus unavailable: {error}"],
    }


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get("/health")
async def homelab_health() -> JSONResponse:
    """Return homelab health as JSON, computed from live Prometheus data.

    Queries the configured Prometheus for host/CPU/RAM/filesystem
    and QNAP metrics, then applies the same thresholds and rules as the
    client-side homepage_homelab_health_embed.html.

    A 30-second server-side cache prevents hammering Prometheus. Home Assistant
    polls this endpoint every ~120 seconds so the cache only avoids burst-duplicate
    requests without masking fresh data.

    On total Prometheus failure, returns HTTP 200 with overall='unknown', stale=True,
    and errors populated — never HTTP 500. The calling dashboard must handle the
    UNKNOWN state visually.

    Returns:
        JSONResponse matching the strict downstream contract shape.
    """
    cached = _get_cached()
    if cached is not None:
        return JSONResponse(cached)

    try:
        raw = await _fetch_all()
        payload = _compute(raw)
        _set_cached(payload)
        return JSONResponse(payload)
    except Exception as exc:
        logger.warning("homelab health: Prometheus query failed: %s", exc)
        return JSONResponse(_failure_response(exc))
