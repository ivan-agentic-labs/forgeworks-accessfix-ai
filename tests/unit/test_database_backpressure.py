"""Public overload responses must not expose pool or database credentials."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg_pool import PoolTimeout, TooManyRequests
from accessfix_ai.presentation.operations import register_operations


@pytest.mark.parametrize("failure", [PoolTimeout, TooManyRequests])
def test_pool_saturation_is_retryable_and_redacted(tmp_path, failure):
    app = FastAPI()
    register_operations(app, tmp_path, "accessfix-ai")

    @app.get("/test-busy")
    def busy():
        raise failure("password=synthetic-must-never-appear host=private.invalid")

    with TestClient(app) as client:
        response = client.get("/test-busy")
    assert response.status_code == 503
    assert response.headers["retry-after"] == "1"
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "DATABASE_BUSY"
    assert "password" not in response.text and "private.invalid" not in response.text
