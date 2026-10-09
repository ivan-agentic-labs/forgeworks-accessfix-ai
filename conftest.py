# Explicit synthetic credentials used only by automated tests.
import os
from pathlib import Path
import sys
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("AUTH_MODE", "development")
os.environ.setdefault("DEV_AUTH_SECRET", "forgeworks-development-secret-32-plus")
os.environ.setdefault("AUTH_ISSUER", "https://issuer.synthetic.invalid")
os.environ.setdefault("AUTH_AUDIENCE", "forgeworks-api")
os.environ.setdefault("ARTIFACT_SIGNING_SECRET", "synthetic-artifact-signing-secret-for-tests-only")
ROOT = Path(__file__).resolve().parent
for path in (ROOT / "apps/worker/src", ROOT / "apps/api/src"):
    sys.path.insert(0, str(path))
