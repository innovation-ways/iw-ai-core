from __future__ import annotations

from types import SimpleNamespace

import pytest

from orch.backup.restore import RestoreSafetyError, restore


class _NoopRunner:
    def __call__(self, _argv: list[str]) -> None:
        raise AssertionError("command runner must not be called when guard rejects target")


def test_restore_refuses_live_prod_target_without_allow_prod(tmp_path) -> None:
    backup_set = tmp_path / "set"
    backup_set.mkdir()
    (backup_set / "globals.sql").write_text("-- globals")
    (backup_set / "iw_orch.dump").write_bytes(b"dump")

    config = SimpleNamespace(
        db_host="127.0.0.1",
        db_port=5433,
        db_name="iw_orch",
        db_user="iw_orch",
        db_password="secret",  # noqa: S106
    )

    with pytest.raises(RestoreSafetyError, match="Refusing restore into live production DB"):
        restore(
            config,
            backup_set=backup_set,
            target={"host": "127.0.0.1", "port": 5433, "db_name": "iw_orch", "user": "iw_orch"},
            command_runner=_NoopRunner(),
        )
