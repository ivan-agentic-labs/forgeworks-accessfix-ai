# Static fixture workflow console

This is a dependency-free static UI for the synthetic MVP. It calls the local API in this order:

1. request and verify ownership for `http://fixture.local`;
2. queue the deterministic fixture scan;
3. read findings and create a source-linked fix proposal;
4. queue the proposal-base revision retest; and
5. record a human review.

Remote browser scanning is **fail-closed**. The origin field is readonly and the UI never offers a
third-party target. A `503 REMOTE_BROWSER_BLOCKED` response is rendered as a stopped error state.
The API base is restricted to `localhost`/`127.0.0.1`, and the UI also does not call the disabled
GitHub write endpoint.

## Local run

From the repository root, install the API test dependencies and start the seeded API:

```bash
python -m pip install -e 'apps/api[test]'
ACCESSFIX_SEED_FIXTURE=1 PYTHONPATH=apps/api/src uvicorn accessfix_ai.main:app --port 8000
```

In a second terminal, serve this directory (do not open the file with `file://`):

```bash
python -m http.server 8080 --bind 127.0.0.1 --directory apps/web
```

Open `http://127.0.0.1:8080`. Paste a development JWT with the required scopes as prompted by
the API flow. The API exposes the synthetic challenge response header only to the two local UI
origins; no token is persisted by the page.

Static checks:

```bash
node --check apps/web/app.js
python -m pytest tests/web
```
