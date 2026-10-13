#!/usr/bin/env python3
"""Validate ForgeWorks baseline evidence receipts without inferring release readiness."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = ROOT / "contracts" / "evidence-receipt.schema.json"
DEFAULT_RECEIPTS = ROOT / "docs" / "verification" / "evidence-receipts"


def _pointer(path: Any) -> str:
    parts = [str(part).replace("~", "~0").replace("/", "~1") for part in path]
    return "/" + "/".join(parts) if parts else "/"


def validate_receipt_data(data: Any, schema: dict[str, Any]) -> list[str]:
    """Return schema and cross-field invariant errors for one receipt."""
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = [
        f"{_pointer(error.absolute_path)}: {error.message}"
        for error in validator.iter_errors(data)
    ]
    if errors or not isinstance(data, dict):
        return sorted(errors)

    evaluated_sha = data["evaluated_source_commit"].lower()
    evidence = data["evidence"]
    for index, item in enumerate(evidence):
        location = f"/evidence/{index}"
        workflow_sha = item["workflow_commit"].lower()
        subject_sha = item["subject_commit"]

        # Baseline receipts must contain only evidence produced by workflows
        # running from the exact source snapshot recorded at the top level.
        if workflow_sha != evaluated_sha:
            errors.append(
                f"{location}/workflow_commit: baseline evidence must match "
                "evaluated_source_commit"
            )

        if item["environment"] in {"CI", "DISPOSABLE"}:
            if item["subject_identity"] != "VERIFIED":
                errors.append(
                    f"{location}/subject_identity: CI/disposable runs must identify "
                    "the checked-out subject commit"
                )
            elif subject_sha is None or subject_sha.lower() != workflow_sha:
                errors.append(
                    f"{location}/subject_commit: CI/disposable subject must equal "
                    "workflow_commit"
                )

        if item["status"] == "PASS" and not item["limitations"]:
            errors.append(f"{location}/limitations: scoped PASS evidence must state limitations")

    gate = data["gate_assessment"]
    if gate["production_acceptance"] == "ACCEPTED":
        if gate["g1_d"] != "PASS" or gate["g1_e"] != "PASS":
            errors.append(
                "/gate_assessment: production acceptance requires both G1-D and G1-E PASS"
            )
        accepted = [
            item for item in evidence
            if item["kind"] == "acceptance"
            and item["status"] == "PASS"
            and item["environment"] == "PRODUCTION"
            and item["subject_identity"] == "VERIFIED"
            and item.get("reviewers")
        ]
        if not accepted:
            errors.append(
                "/evidence: ACCEPTED production status requires a production acceptance "
                "record with verified subject identity and reviewer references"
            )

    return sorted(errors)


def validate_file(path: Path, schema: dict[str, Any]) -> list[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{path}: cannot read valid JSON: {exc}"]
    return [f"{path}: {error}" for error in validate_receipt_data(data, schema)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--schema", type=Path, default=DEFAULT_SCHEMA,
        help=f"JSON Schema path (default: {DEFAULT_SCHEMA})",
    )
    parser.add_argument(
        "--file", action="append", type=Path, dest="files",
        help="receipt JSON to validate; repeat as needed (default: all JSON in the receipt directory)",
    )
    args = parser.parse_args(argv)

    try:
        schema = json.loads(args.schema.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
    except (OSError, json.JSONDecodeError, SchemaError, TypeError) as exc:
        print(f"ERROR: invalid/unreadable schema {args.schema}: {exc}", file=sys.stderr)
        return 2

    files = args.files if args.files is not None else sorted(DEFAULT_RECEIPTS.glob("*.json"))
    if not files:
        print(f"ERROR: no evidence receipts found in {DEFAULT_RECEIPTS}", file=sys.stderr)
        return 2

    failed = False
    for path in files:
        errors = validate_file(path, schema)
        if errors:
            failed = True
            for error in errors:
                print(f"FAIL: {error}", file=sys.stderr)
        else:
            print(f"PASS: {path}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
