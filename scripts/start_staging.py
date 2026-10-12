"""Compatibility entrypoint restricted to staging."""
import os
from start_service import main

if __name__ == "__main__":
    if os.getenv("APP_ENV") != "staging":
        raise SystemExit("This entrypoint is staging-only")
    main()
