"""Report whether GitHub source matches a reviewed staging release record.

This is deliberately NOT proof of live hosting, tenant isolation, or production.
"""
import argparse
import json
import re
from pathlib import Path

PRODUCT = "accessfix-ai"
RECORD = Path(__file__).resolve().parents[1] / "ops/releases/staging.json"


def inspect(record, main_sha):
    if not isinstance(record, dict) or record.get("schema") != "forgeworks-staging-release-v1":
        raise ValueError("INVALID_RELEASE_RECORD")
    if record.get("product") != PRODUCT or record.get("environment") != "staging":
        raise ValueError("WRONG_RELEASE_TARGET")
    deployed = record.get("revision_sha")
    manifest = record.get("runtime_manifest")
    if not isinstance(deployed, str) or not re.fullmatch(r"[0-9a-f]{40}", deployed):
        raise ValueError("INVALID_STAGING_REVISION")
    if not isinstance(main_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", main_sha):
        raise ValueError("INVALID_MAIN_REVISION")
    if not isinstance(manifest, dict) or not re.fullmatch(
            r"[0-9a-f]{64}", str(manifest.get("sha256", ""))):
        raise ValueError("INVALID_STAGING_MANIFEST")
    if record.get("deployment_status") != "SUCCESS":
        raise ValueError("STAGING_RELEASE_NOT_SUCCESSFUL")
    return {
        "product": PRODUCT,
        "recorded_deployment_sha": deployed,
        "github_main_sha": main_sha,
        "record_is_current": deployed == main_sha,
        "status": "RECORD_MATCHES_MAIN" if deployed == main_sha else "STAGING_RELEASE_STALE",
        "scope": "Source SHA versus reviewed record only; current hosted deployment not verified",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--main-sha", required=True)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    result = inspect(json.loads(RECORD.read_text()), args.main_sha)
    print(json.dumps(result, sort_keys=True))
    if args.strict and not result["record_is_current"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
