from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "apps" / "web"


def test_fixture_console_is_static_and_complete():
    index = (WEB / "index.html").read_text(encoding="utf-8")
    client = (WEB / "app.js").read_text(encoding="utf-8")
    styles = (WEB / "styles.css").read_text(encoding="utf-8")

    assert '<script src="./app.js" defer></script>' in index
    assert 'http://fixture.local' in index
    assert "const FIXTURE_ORIGIN = \"http://fixture.local\"" in client
    assert "REMOTE_BROWSER_BLOCKED" in index + client
    assert "Remote browser scanning is blocked" in index
    for endpoint in (
        "/v1/sites/verification-challenges",
        "/v1/sites/${SITE_ID}/verify",
        "/v1/sites/${SITE_ID}/scans",
        "/v1/jobs/${jobId}",
        "/v1/scans/${scanId}/findings",
        "/v1/findings/${finding.id}/fix-proposals",
        "/v1/fix-proposals/${proposal.id}/retests",
        "/v1/fix-proposals/${proposal.id}/reviews",
    ):
        assert endpoint in client
    assert "setOverall(\"STOPPED\", \"blocked\")" in client
    assert "errorState.hidden = false" in client
    assert "waitForJob(scan.job_id)" in client
    assert 'if (job.state !== "SUCCEEDED")' in client
    assert "Polling fixture job" in client
    assert "github" not in client.lower()
    assert "https://example.com" not in client.lower()
    assert ".panel" in styles


def test_fixture_console_does_not_offer_an_editable_remote_target():
    index = (WEB / "index.html").read_text(encoding="utf-8")
    origin_field = index.split('id="fixture-origin"', 1)[1].split(">", 1)[0]
    assert "readonly" in origin_field
    assert 'value="http://fixture.local"' in origin_field
