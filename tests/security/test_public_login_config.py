"""Public console configuration must never disclose a privileged API key."""
from fastapi.testclient import TestClient
from accessfix_ai.main import create_app


def test_public_login_config_and_console(tmp_path,monkeypatch):
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY","sb_secret_misconfigured")
    app=create_app(str(tmp_path/"console.db"),seed=True)
    with TestClient(app) as client:
        value=client.get("/v1/auth/config").json()
        assert value["publishable_key"]=="" and value["enabled"] is False
        assert "sb_secret" not in str(value)
        assert client.get("/").status_code==200
        assert client.get('/ui/'+"auth-panel.js").status_code==200
        monkeypatch.setenv("AUTH_MODE","supabase")
        monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY","sb_publishable_synthetic")
        value=client.get("/v1/auth/config").json()
        assert value["enabled"] is True
        assert value["publishable_key"]=="sb_publishable_synthetic"


def test_source_snapshot_is_read_after_visible_findings(tmp_path,monkeypatch):
    from test_accessfix_hardening import verified_scan
    app=create_app(str(tmp_path/"source-order.db"),seed=True)
    original_findings=app.state.store.findings
    original_source=app.state.store.scan_source
    observed={"findings":False}
    def read_findings(*args):
        observed["findings"]=True
        return original_findings(*args)
    def read_source(*args):
        assert observed["findings"],"Source read before findings creates a worker commit race"
        observed["findings"]=False
        return original_source(*args)
    monkeypatch.setattr(app.state.store,"findings",read_findings)
    monkeypatch.setattr(app.state.store,"scan_source",read_source)
    with TestClient(app) as client:
        _,finding=verified_scan(client)
        assert finding["source_mapping"]["verified"] is True
