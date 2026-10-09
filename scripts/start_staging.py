"""Explicit staging entrypoint. No migration/provisioning credentials are accepted."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps/api/src"))

def main():
    if os.getenv("APP_ENV") != "staging" or os.getenv("AUTH_MODE") != "supabase":
        raise SystemExit("Staging requires APP_ENV=staging and AUTH_MODE=supabase")
    if not os.getenv("ACCESSFIX_DATABASE_URL"):
        raise SystemExit("A least-privilege PostgreSQL runtime URL is required")
    if os.getenv("ACCESSFIX_SEED_FIXTURE", "0") != "0":
        raise SystemExit("Synthetic fixture provisioning is forbidden on staging")
    if os.getenv("DEV_AUTH_SECRET"):
        raise SystemExit("Development auth secrets are forbidden on staging")
    import uvicorn
    uvicorn.run("accessfix_ai.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), workers=1, proxy_headers=False, access_log=False)

if __name__ == "__main__":
    main()
