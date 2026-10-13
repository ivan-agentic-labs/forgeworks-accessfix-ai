"""Application shutdown must release database pool resources even after errors."""
import pytest
from fastapi.testclient import TestClient
from accessfix_ai.main import create_app


@pytest.mark.parametrize("fail_inside", [False, True])
def test_store_pool_lifecycle_is_closed_on_exit(tmp_path, fail_inside):
    app = create_app(db_path=str(tmp_path / "lifecycle.db"), seed=False)
    events = []
    app.state.store.start_pool = lambda: events.append("open")
    app.state.store.close = lambda: events.append("close")
    try:
        with TestClient(app):
            assert events == ["open"]
            if fail_inside:
                raise RuntimeError("synthetic lifespan interruption")
    except RuntimeError:
        assert fail_inside
    assert events == ["open", "close"]
