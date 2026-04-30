#!/usr/bin/env uv run python
"""E2E health check — curls /health for each service in docker-compose.e2e.yml."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml


def main() -> int:
    compose_path = Path("docker-compose.e2e.yml")
    if not compose_path.exists():
        print("FAIL  docker-compose.e2e.yml not found", file=sys.stderr)
        return 1

    with compose_path.open() as f:
        compose = yaml.safe_load(f)

    services = compose.get("services", {})
    failures = 0

    for name, svc in services.items():
        ports_mappings = svc.get("ports", [])
        host_port = None

        for mapping in ports_mappings:
            if isinstance(mapping, str):
                parts = mapping.split(":")
                if len(parts) >= 2:
                    host_port = parts[-1]
                    break
            elif isinstance(mapping, list) and len(mapping) >= 2:
                host_port = str(mapping[-1])
                break

        if host_port is None:
            print(f"WARN  {name}  no port mapping found")
            continue

        url = f"http://localhost:{host_port}/health"
        try:
            import urllib.request

            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as resp:
                code = resp.status
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL  {name}  {exc}")
            failures += 1
            continue

        print(f"PASS  {name}  HTTP {code}")

    if failures:
        print(f"\n{failures} service(s) failed health check", file=sys.stderr)
        return 1
    print("\nAll services passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
