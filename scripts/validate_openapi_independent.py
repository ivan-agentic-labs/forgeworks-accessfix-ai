#!/usr/bin/env python3
"""Use a third-party OpenAPI validator; errors are fatal, never suppressed."""
from pathlib import Path
import yaml
from openapi_spec_validator import validate_spec
p=Path(__file__).resolve().parents[1]/'contracts/openapi.yaml'
spec=yaml.safe_load(p.read_text(encoding='utf-8'))
validate_spec(spec)
print(f'Independent OpenAPI validator: PASS for {p.name}. This is not an application runtime test.')
