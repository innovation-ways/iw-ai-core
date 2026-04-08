"""Entry point for running the daemon as a module: python -m orch.daemon"""

from __future__ import annotations

import logging
import sys

from orch.config import load_config
from orch.daemon.main import Daemon, DaemonAlreadyRunning

if __name__ == "__main__":
    try:
        config = load_config()
        log_level = getattr(logging, config.log_level.upper(), logging.INFO)
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        Daemon(config).run()
    except DaemonAlreadyRunning as exc:
        sys.exit(f"Daemon already running: {exc}")
    except RuntimeError as exc:
        sys.exit(f"Configuration error: {exc}")
