"""Tests for per-host temperature aggregation in the homelab health payload."""

from __future__ import annotations

from typing import Any

from dashboard.routers.homelab import _QUERIES, _compute

_NET_TEMP = 18
_GPU_TEMP = 20


def _sample(job: str, label: str, value: float) -> dict[str, Any]:
    """Build one Prometheus instant-query result.

    Args:
        job: Prometheus job label, which selects the host.
        label: Sensor label.
        value: Sample value.

    Returns:
        A result item in the shape returned by the Prometheus API.
    """
    return {"metric": {"job": job, "label": label}, "value": [0, str(value)]}


def _hosts(samples: dict[int, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    """Run ``_compute`` with the given query results and index hosts by name.

    Args:
        samples: Query results keyed by position in ``_QUERIES``.

    Returns:
        The payload's host entries keyed by host name.
    """
    results = [samples.get(i, []) for i in range(len(_QUERIES))]
    return {host["name"]: host for host in _compute(results)["hosts"]}


class TestHostTemperatures:
    """Covers sensor deduplication, CPU sensor selection and GPU attribution."""

    def test_duplicate_sensor_labels_keep_only_the_first_reading(self) -> None:
        """Verifies that a sensor reported twice appears once in the host's temps."""
        samples = {
            _NET_TEMP: [_sample("netdata-home", "Tctl", 50), _sample("netdata-home", "Tctl", 60)]
        }

        host = _hosts(samples)["home-srv"]

        assert host["temps"] == [{"label": "Tctl", "c": 50.0}]
        assert host["max_temp_c"] == 50.0

    def test_cpu_temp_follows_sensor_preference_not_hottest_reading(self) -> None:
        """Verifies that a CPU-like sensor wins over a hotter non-CPU sensor."""
        samples = {
            _NET_TEMP: [_sample("netdata-home", "Disk", 70), _sample("netdata-home", "Tctl", 45)]
        }

        host = _hosts(samples)["home-srv"]

        assert host["cpu_temp_c"] == 45.0
        assert host["max_temp_c"] == 70.0

    def test_cpu_temp_is_none_without_a_cpu_like_sensor(self) -> None:
        """Verifies that a host with only non-CPU sensors reports no CPU temperature."""
        samples = {_NET_TEMP: [_sample("netdata-home", "Disk", 70)]}

        assert _hosts(samples)["home-srv"]["cpu_temp_c"] is None

    def test_gpu_temp_is_attached_only_to_the_gpu_host(self) -> None:
        """Verifies that the GPU reading is reported on iw-dev-01 and no other host."""
        hosts = _hosts({_GPU_TEMP: [_sample("netdata-dev", "gpu", 61.26)]})

        assert hosts["iw-dev-01"]["gpu_temp_c"] == 61.3
        assert hosts["home-srv"].get("gpu_temp_c") is None
