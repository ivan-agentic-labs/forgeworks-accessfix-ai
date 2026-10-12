"""Read-only proof of one fixed staging origin and reviewed runtime identity."""
import argparse
import json
import os
import re
import sys
from pathlib import Path
from secrets import token_hex
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api/src"))
from accessfix_ai.presentation.operations import runtime_manifest

PRODUCT = "accessfix-ai"
ORIGIN = "https://accessfix-ai-staging.up.railway.app"
ALLOWED_PATHS = {"/healthz", "/readyz", "/versionz", "/metricsz",
                 "/v1/jobs/00000000-0000-0000-0000-000000000001"}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def fetch(path, secret=None, max_bytes=4096):
    if path not in ALLOWED_PATHS:
        raise ValueError("RELEASE_PROBE_PATH_FORBIDDEN")
    headers = {"Accept": "application/json", "User-Agent": "ForgeWorks-Release-Proof/1.0",
               "traceparent": f"00-{token_hex(16)}-{token_hex(8)}-01"}
    if secret is not None:
        headers["Authorization"] = f"Bearer {secret}"
    request = Request(ORIGIN + path, headers=headers, method="GET")
    try:
        with build_opener(NoRedirect()).open(request, timeout=15) as response:
            status, raw = response.status, response.read(max_bytes + 1)
    except HTTPError as error:
        status, raw = error.code, error.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ValueError("RELEASE_PROBE_RESPONSE_BUDGET")
    if status != 200:
        return status, None
    return status, json.loads(raw, object_pairs_hook=unique_object)


def verify_release(expected_revision, expected_manifest, request=fetch, metrics_secret=None):
    if not isinstance(expected_revision, str) or not re.fullmatch(
            r"[0-9a-f]{40}|[0-9a-f]{64}", expected_revision):
        raise ValueError("RELEASE_REVISION_REQUIRED")
    status, health = request("/healthz")
    if status != 200 or not isinstance(health, dict) or health.get("status") != "ok":
        raise ValueError("RELEASE_HEALTH_FAILED")
    status, ready = request("/readyz")
    if status != 200 or not isinstance(ready, dict) or ready.get("status") != "ready":
        raise ValueError("RELEASE_READINESS_FAILED")
    status, identity = request("/versionz")
    if (status != 200 or not isinstance(identity, dict)
            or set(identity) != {"product", "environment", "revision_sha", "runtime_manifest"}
            or identity["product"] != PRODUCT or identity["environment"] != "staging"
            or identity["revision_sha"] != expected_revision
            or identity["runtime_manifest"] != expected_manifest):
        raise ValueError("RELEASE_IDENTITY_MISMATCH")
    if request("/v1/jobs/00000000-0000-0000-0000-000000000001")[0] != 401:
        raise ValueError("RELEASE_ANONYMOUS_BUSINESS_ACCESS")
    if request("/metricsz")[0] != 401:
        raise ValueError("RELEASE_ANONYMOUS_METRICS_ACCESS")
    private_metrics = "NOT_REQUESTED"
    if metrics_secret:
        status, metrics = request("/metricsz", secret=metrics_secret, max_bytes=192 * 1024)
        if (status != 200 or not isinstance(metrics, dict)
                or metrics.get("scope") != "single-process-since-start"
                or not isinstance(metrics.get("requests"), list)):
            raise ValueError("RELEASE_PRIVATE_METRICS_FAILED")
        private_metrics = "PASS"
    return {"result": "PASS", "product": PRODUCT, "environment": "staging",
            "revision_sha": expected_revision, "runtime_manifest": expected_manifest,
            "private_metrics": private_metrics,
            "limits": "Runtime identity and anonymous boundaries only; no authenticated business acceptance"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-revision")
    args = parser.parse_args()
    manifest = runtime_manifest(ROOT)
    revision = args.expected_revision
    if not revision:
        record = json.loads((ROOT / "ops/releases/staging.json").read_bytes(),
                            object_pairs_hook=unique_object)
        if (record["product"] != PRODUCT or record["environment"] != "staging"
                or record["runtime_manifest"] != manifest):
            raise ValueError("RELEASE_RECORD_MISMATCH")
        revision = record["revision_sha"]
    print(json.dumps(verify_release(revision, manifest, metrics_secret=os.getenv("METRICS_READ_SECRET")),
                     sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError):
        raise SystemExit("Deployed release proof failed; inspect identity, readiness and access boundaries") from None
