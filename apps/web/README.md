# AccessFix UI: offline HTML analysis and fixture workflow

The UI has two separate workflows. The **offline HTML analysis** accepts a supplied UTF-8 .html/.htm file (or pasted HTML) and calls `POST /v1/offline/html-findings`. It needs a scoped `scan:start` token and returns static missing-image-alt findings with a source checksum. It does not fetch remote sites, execute scripts, store HTML, or certify WCAG compliance.

The **fixture-only remediation workflow** calls the local API in this order:

1. request and verify ownership for `http://fixture.local`;
2. queue the deterministic fixture scan;
3. read findings and create a source-linked fix proposal;
4. queue the proposal-base revision retest; and
5. record a human review.

Remote browser scanning is **fail-closed**. The origin field is readonly and the UI never offers a
third-party target. A `503 REMOTE_BROWSER_BLOCKED` response is rendered as a stopped error state.
The fixture workflow API base is restricted to `localhost`/`127.0.0.1`. The offline form can also call the API at the page's same origin and does not call the disabled
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
node --check apps/web/offline-html-panel.js
python -m pytest tests/web
```
