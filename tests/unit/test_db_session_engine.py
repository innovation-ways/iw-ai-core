from __future__ import annotations

from unittest.mock import MagicMock

from orch.daemon.main import create_session_factory


def test_create_session_factory_reuses_shared_session_for_default_db_url(monkeypatch) -> None:
    create_engine_mock = MagicMock()
    monkeypatch.setattr("orch.daemon.main.safe_create_engine", create_engine_mock)
    monkeypatch.setattr(
        "orch.config.get_db_url", lambda: "postgresql+psycopg://test:test@localhost/test"
    )

    factory = create_session_factory("postgresql+psycopg://test:test@localhost/test")

    assert factory.__module__ == "orch.db.session"
    assert factory.__name__ == "get_session"
    create_engine_mock.assert_not_called()


def test_create_session_factory_sets_explicit_pool_kwargs_for_non_default_url(monkeypatch) -> None:
    mock_engine = object()
    create_engine_mock = MagicMock(return_value=mock_engine)
    monkeypatch.setattr("orch.daemon.main.safe_create_engine", create_engine_mock)
    monkeypatch.setattr(
        "orch.config.get_db_url", lambda: "postgresql+psycopg://default:default@localhost/default"
    )
    monkeypatch.setattr("orch.config.get_db_pool_size", lambda: 20)
    monkeypatch.setattr("orch.config.get_db_max_overflow", lambda: 20)

    create_session_factory("postgresql+psycopg://test:test@localhost/test")

    kwargs = create_engine_mock.call_args.kwargs
    assert kwargs["pool_pre_ping"] is True
    assert kwargs.get("pool_size", 20) == 20
    assert kwargs.get("max_overflow", 20) == 20
    assert kwargs.get("pool_recycle", 1800) == 1800
    assert kwargs.get("pool_timeout", 10) == 10
