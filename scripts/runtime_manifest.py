"""Print the bounded runtime fingerprint used by hosted release proofs."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api/src"))
from accessfix_ai.presentation.operations import runtime_manifest

if __name__ == "__main__":
    print(json.dumps(runtime_manifest(ROOT), sort_keys=True))
