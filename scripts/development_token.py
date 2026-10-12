"""Mint a short-lived token for an explicitly local synthetic fixture."""
import ast
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api/src"))


def mint_token():
    if os.getenv("APP_ENV") not in {"development", "test"} or os.getenv("AUTH_MODE") != "development":
        raise ValueError("LOCAL_DEVELOPMENT_MODE_REQUIRED")
    secret, issuer, audience = (os.getenv(key, "") for key in (
        "DEV_AUTH_SECRET", "AUTH_ISSUER", "AUTH_AUDIENCE"))
    if len(secret.encode()) < 32 or not issuer or not audience:
        raise ValueError("EXPLICIT_LOCAL_AUTH_CONFIGURATION_REQUIRED")
    import jwt
    from accessfix_ai.infrastructure.store import TENANT, USER
    tree = ast.parse((ROOT / "apps/api/src/accessfix_ai/main.py").read_text())
    scopes = sorted({
        node.args[0].value for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id in {"require_scope", "scope"} and node.args
        and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)
        and ":" in node.args[0].value
    })
    if not scopes or "*" in scopes:
        raise ValueError("LOCAL_SYNTHETIC_SCOPES_REQUIRED")
    now = int(time.time())
    return jwt.encode({"iss": issuer, "aud": audience, "sub": USER, "tenant_id": TENANT,
                       "iat": now, "exp": now + 900, "scope": " ".join(scopes)}, secret, algorithm="HS256")


if __name__ == "__main__":
    try:
        print(mint_token())
    except ValueError:
        raise SystemExit("Token minting rejected: explicit local development configuration required") from None
