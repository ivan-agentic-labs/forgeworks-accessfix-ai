"""Bounded PostgreSQL connection pool readiness and fail-closed HTTP checks."""
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from accessfix_ai.infrastructure.postgres_store import PostgresStore
from accessfix_ai.presentation import authentication


class FakePool:
    def __init__(self, result=1, failure=False):
        self.result = result
        self.failure = failure
        self.open_calls = 0
        self.timeout = None
        self.query = None

    def open(self):
        self.open_calls += 1

    @contextmanager
    def connection(self, *, timeout):
        self.timeout = timeout
        if self.failure:
            raise RuntimeError("pool unavailable")
        yield self

    def execute(self, query):
        self.query = query
        return self

    def fetchone(self):
        return {"alive": self.result}


def new_store(pool):
    store = object.__new__(PostgresStore)
    store._pool = pool
    return store


def test_ready_reuses_bounded_pool_and_checks_sql():
    pool = FakePool()
    new_store(pool).readiness_check()
    assert pool.open_calls == 1
    assert pool.timeout == 3
    assert pool.query == "SELECT 1 AS alive"


@pytest.mark.parametrize("value", [0, False, None])
def test_ready_rejects_invalid_database_response(value):
    with pytest.raises(RuntimeError, match="READINESS_DATABASE_CHECK_FAILED"):
        new_store(FakePool(result=value)).readiness_check()


def test_ready_does_not_swallow_pool_outage():
    with pytest.raises(RuntimeError, match="pool unavailable"):
        new_store(FakePool(failure=True)).readiness_check()


def test_readiness_requires_database_adapter(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setattr(authentication, "configuration",
                        lambda: ("development", None, None, None))
    with pytest.raises(HTTPException) as err:
        authentication.readiness(SimpleNamespace(dsn="postgresql://fake"))
    assert err.value.status_code == 503


def test_readiness_calls_adapter_and_preserves_failure(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setattr(authentication, "configuration",
                        lambda: ("development", None, None, None))
    called = []
    adapter = SimpleNamespace(dsn="postgresql://fake",
                              readiness_check=lambda: called.append("checked"))
    assert authentication.readiness(adapter) == {"status": "ready"}
    assert called == ["checked"]

    def fail():
        raise RuntimeError("database unavailable")
    adapter.readiness_check = fail
    with pytest.raises(HTTPException) as err:
        authentication.readiness(adapter)
    assert err.value.status_code == 503
