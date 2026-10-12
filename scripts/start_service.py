"""Hosted entrypoint: staging or independently reviewed production only."""
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api/src"))
from accessfix_ai.presentation.operations import runtime_identity
from accessfix_ai.presentation.release_gate import MAX_RECEIPT_BYTES, validate_receipt

PRODUCT = "accessfix-ai"
STAGING_PROJECT = "1b35f35d-ad5b-4b93-ad20-ed68251b4589"
STAGING_ENVIRONMENT = "0395e7ac-10f8-4004-8bb7-ddee901343c7"
STAGING_SUPABASE = "fljekuwplgkrpdoajyhn"


def platform_uuid(name):
    value = os.environ[name]
    if str(UUID(value)) != value:
        raise ValueError("PRODUCTION_PLATFORM_ID_INVALID")
    return value


def validate_configuration():
    environment = os.getenv("APP_ENV")
    if environment not in {"staging", "production"} or os.getenv("AUTH_MODE") != "supabase":
        raise ValueError("HOSTED_SUPABASE_CONFIGURATION_REQUIRED")
    if not os.getenv("ACCESSFIX_DATABASE_URL"):
        raise ValueError("LEAST_PRIVILEGE_DATABASE_URL_REQUIRED")
    if os.getenv("ACCESSFIX_SEED_FIXTURE", "0") != "0" or os.getenv("DEV_AUTH_SECRET"):
        raise ValueError("HOSTED_DEVELOPMENT_CONFIGURATION_FORBIDDEN")
    if environment == "staging":
        return {"environment": environment, "acceptance": "NOT_APPLICABLE"}
    identity = runtime_identity(ROOT, PRODUCT)
    project = platform_uuid("RAILWAY_PROJECT_ID")
    railway_environment = platform_uuid("RAILWAY_ENVIRONMENT_ID")
    url = urlsplit(os.environ["SUPABASE_URL"])
    if (url.scheme != "https" or not url.hostname
            or not re.fullmatch(r"[a-z0-9]{20}\.supabase\.co", url.hostname)
            or url.path or url.query or url.fragment or "@" in url.netloc or url.port is not None):
        raise ValueError("PRODUCTION_SUPABASE_URL_INVALID")
    supabase = url.hostname.split(".")[0]
    if project == STAGING_PROJECT or railway_environment == STAGING_ENVIRONMENT or supabase == STAGING_SUPABASE:
        raise ValueError("SEPARATE_PRODUCTION_INFRASTRUCTURE_REQUIRED")
    expected = {"product": PRODUCT, "environment": "production", "revision_sha": identity["revision_sha"],
                "runtime_manifest_sha256": identity["runtime_manifest"]["sha256"],
                "infrastructure": {"railway_project_id": project,
                                   "railway_environment_id": railway_environment,
                                   "supabase_project_ref": supabase}}
    path = Path(os.environ["PRODUCTION_ACCEPTANCE_FILE"])
    if path.is_symlink() or not path.is_file():
        raise ValueError("PRODUCTION_ACCEPTANCE_FILE_INVALID")
    with path.open("rb") as handle:
        raw = handle.read(MAX_RECEIPT_BYTES + 1)
    return validate_receipt(raw, os.environ["PRODUCTION_ACCEPTANCE_PUBLIC_KEY_PEM"].encode(), expected)


def main():
    try:
        validate_configuration()
    except (OSError, KeyError, ValueError):
        raise SystemExit("Hosted startup rejected: configuration or signed production acceptance is invalid") from None
    import uvicorn
    uvicorn.run("accessfix_ai.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")),
                workers=1, proxy_headers=False, access_log=False)


if __name__ == "__main__":
    main()
