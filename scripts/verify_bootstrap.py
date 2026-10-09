#!/usr/bin/env python3
"""Bootstrap structure and heuristic sensitive-content check; not a security certification."""
from pathlib import Path
import json, re, sys
import yaml
root = Path(__file__).resolve().parents[1]
required = [
    "README.md", ".gitignore", ".env.example", ".github/CODEOWNERS",
    "contracts/openapi.yaml", "contracts/events.schema.json",
    "scripts/requirements-verification.txt", "scripts/verify_contracts.py",
    "scripts/validate_openapi_independent.py",
    "docs/architecture/DESIGN_HANDOFF.md", "docs/product/PRODUCT_SCOPE.md",
    "docs/verification/G2_BOOTSTRAP_STATUS.md",
    ".github/workflows/g1-contracts.yml", ".github/workflows/g1-disposable-postgres.yml",
    "apps/api/README.md", "apps/web/README.md", "apps/worker/README.md",
]
errors = [f"missing: {p}" for p in required if not (root / p).is_file()]
for p in root.glob(".github/workflows/*.yml"):
    data = yaml.load(p.read_text(), Loader=yaml.BaseLoader)
    if not isinstance(data.get("on"), dict) or not data.get("jobs"):
        errors.append(f"workflow shape: {p.relative_to(root)}")
    if data.get("permissions") != {"contents": "read"}:
        errors.append(f"workflow permissions: {p.relative_to(root)}")
for p in root.glob("migrations/versions/*.sql"):
    errors.append(f"unapproved bootstrap migration: {p.relative_to(root)}")
patterns = {
    "private key": r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    "GitHub token": r"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,})",
    "AWS access key": r"AKIA[A-Z0-9]{16}",
    "personal email": r"[A-Za-z0-9._%+-]+@(?!example\.(?:com|org)\b)[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    "local path": r"/(?:workspace/scratch|root)/",
}
scanned = 0
for p in root.rglob("*"):
    rel = p.relative_to(root)
    if not p.is_file() or any(x in {".git", "__pycache__", ".venv", "node_modules"} for x in rel.parts):
        continue
    if p.name == ".env" or (p.name.startswith(".env.") and p.name != ".env.example"):
        errors.append(f"environment file: {rel}")
    if p.suffix in {".pem", ".key", ".p12", ".pfx"}:
        errors.append(f"credential file: {rel}")
    text = p.read_text(encoding="utf-8")
    scanned += 1
    # The scanner's own regex literals are definitions, not leaked credentials.
    if p == Path(__file__).resolve():
        continue
    for name, pattern in patterns.items():
        if re.search(pattern, text):
            errors.append(f"{name}: {rel}")
print(json.dumps({"check": "bootstrap structure and heuristic sensitive-content scan",
                  "files_scanned": scanned, "errors": errors,
                  "limit": "Pattern checks cannot guarantee absence of all secrets or personal data."}, indent=2))
sys.exit(bool(errors))
