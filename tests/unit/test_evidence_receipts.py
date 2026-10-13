from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "verify_evidence_receipts.py"
SCHEMA_PATH = ROOT / "contracts" / "evidence-receipt.schema.json"
RECEIPT_PATH = ROOT / "docs" / "verification" / "evidence-receipts" / "BASELINE_2026-10-13.json"

spec = importlib.util.spec_from_file_location("verify_evidence_receipts", SCRIPT)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _baseline() -> dict:
    return json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))


def test_checked_in_baseline_receipt_passes_cli() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--file", str(RECEIPT_PATH)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS:" in result.stdout


def test_baseline_rejects_evidence_from_a_different_workflow_commit() -> None:
    data = _baseline()
    data["evidence"][0]["workflow_commit"] = "0" * 40
    errors = module.validate_receipt_data(data, _schema())
    assert any("baseline evidence must match evaluated_source_commit" in error for error in errors)


def test_production_acceptance_cannot_pass_without_gates_and_reviewer_receipt() -> None:
    data = _baseline()
    data["gate_assessment"] = {
        "g1_d": "CONDITIONAL_PENDING_SIGNOFF",
        "g1_e": "PARTIAL_OPEN_BLOCKED",
        "production_acceptance": "ACCEPTED",
    }
    errors = module.validate_receipt_data(data, _schema())
    assert any("production acceptance requires both G1-D and G1-E PASS" in error for error in errors)
    assert any("production acceptance record" in error for error in errors)


def test_staging_unknown_deployment_identity_is_not_misreported_as_a_commit() -> None:
    data = _baseline()
    staging = next(item for item in data["evidence"] if item["environment"] == "STAGING")
    staging["subject_commit"] = data["evaluated_source_commit"]
    errors = module.validate_receipt_data(data, _schema())
    assert any("subject_commit" in error for error in errors)


def test_schema_disallows_unbounded_or_missing_limitation_statements() -> None:
    data = copy.deepcopy(_baseline())
    data["evidence"][0]["limitations"] = []
    errors = module.validate_receipt_data(data, _schema())
    assert any("limitations" in error for error in errors)
