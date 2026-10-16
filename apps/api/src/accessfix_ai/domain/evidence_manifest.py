"""Strict runtime validation for the synthetic evidence-export contract."""
from __future__ import annotations

from datetime import datetime
import re
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator


def _valid_uuid(value: str) -> str:
    try:
        parsed = UUID(value)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("must be a UUID string") from exc
    if str(parsed) != value.lower():
        raise ValueError("must use the canonical UUID format")
    return value


def _valid_datetime(value: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})", value):
        raise ValueError("must use RFC 3339 date-time format")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("must be an ISO-8601 date-time") from exc
    if parsed.tzinfo is None:
        raise ValueError("date-time must include a timezone")
    return value


def _exact_false(value: bool) -> bool:
    if type(value) is not bool or value is not False:
        raise ValueError("must be the boolean false")
    return value


def _exact_true(value: bool) -> bool:
    if type(value) is not bool or value is not True:
        raise ValueError("must be the boolean true")
    return value


def _exact_one(value: int) -> int:
    if type(value) is not int or value != 1:
        raise ValueError("must be the integer 1")
    return value


UUIDString = Annotated[str, AfterValidator(_valid_uuid)]
DateTimeString = Annotated[str, AfterValidator(_valid_datetime)]
SHA256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$", strict=True)]
CommitSHA = Annotated[str, StringConstraints(pattern=r"^([0-9a-fA-F]{40}|[0-9a-fA-F]{64})$", strict=True)]
ExactFalse = Annotated[bool, AfterValidator(_exact_false)]
ExactTrue = Annotated[bool, AfterValidator(_exact_true)]
ExactOne = Annotated[int, Field(strict=True), AfterValidator(_exact_one)]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class _Scan(_StrictModel):
    id: UUIDString
    status: Literal["SUCCEEDED"]
    site_id: UUIDString
    repo_commit_sha: CommitSHA
    revision_verified: ExactFalse
    network_policy_sha256: SHA256
    created_at: DateTimeString
    attempt_count: int = Field(ge=1, strict=True)


class _Source(_StrictModel):
    kind: Literal["LOCAL_FIXTURE"]
    digest_sha256: SHA256
    byte_length: int = Field(ge=0, strict=True)
    content_included: ExactFalse
    revision_verified: ExactFalse


class _Coverage(_StrictModel):
    scan_mode: Literal["STATIC_LOCAL_HTML_FIXTURE"]
    paths: list[str]
    pages_evaluated: ExactOne
    rule_ids_evaluated: list[str]
    browser_rendered: ExactFalse
    wcag_conformance_claim: ExactFalse

    @model_validator(mode="after")
    def fixed_fixture_scope(self):
        if self.paths != ["/"] or self.rule_ids_evaluated != ["image-alt"]:
            raise ValueError("coverage must describe exactly the supported local fixture scan")
        return self


class _FindingEvidence(_StrictModel):
    kind: Literal["DOM_SNIPPET"]
    digest_sha256: SHA256


class _SourceMapping(_StrictModel):
    id: UUIDString
    verified: bool
    source_revision: CommitSHA
    revision_verified: ExactFalse
    source_kind: Literal["LOCAL_FIXTURE"]


class _Finding(_StrictModel):
    id: UUIDString
    scan_id: UUIDString
    rule_id: str
    severity: str
    selector: str
    fingerprint: SHA256
    manual_check_required: bool
    evidence: _FindingEvidence
    source_mapping: _SourceMapping


class _Review(_StrictModel):
    id: UUIDString
    actor_id: UUIDString
    decision: Literal["approve", "reject"]
    manual_check_status: Literal["passed", "failed", "not_applicable"]
    proposal_version: int = Field(ge=1, strict=True)


class _Proposal(_StrictModel):
    id: UUIDString
    finding_id: UUIDString
    base_sha: CommitSHA
    patch_sha256: SHA256
    source_sha256: SHA256
    patched_source_sha256: SHA256
    content_integrity_verified: ExactTrue
    status: str
    retest_status: str
    version: int = Field(ge=1, strict=True)
    reviews: list[_Review]


Limitation = Literal[
    "SOURCE_REVISION_NOT_VERIFIED",
    "RAW_SOURCE_AND_PATCH_CONTENT_OMITTED",
    "NOT_SIGNED_OR_IMMUTABLE",
    "NOT_A_WCAG_CONFORMANCE_CLAIM",
]


class EvidenceExport(_StrictModel):
    schema_version: Literal["forgeworks.accessfix.evidence/v1"]
    product: Literal["accessfix-ai"]
    scope: Literal["SYNTHETIC_LOCAL_FIXTURE_ONLY"]
    exported_at: DateTimeString
    scan: _Scan
    source: _Source
    coverage: _Coverage
    findings: list[_Finding]
    proposals: list[_Proposal]
    limitations: list[Limitation]
    bundle_sha256: SHA256

    @field_validator("limitations")
    @classmethod
    def limitations_must_be_unique(cls, value):
        required = {
            "SOURCE_REVISION_NOT_VERIFIED",
            "RAW_SOURCE_AND_PATCH_CONTENT_OMITTED",
            "NOT_SIGNED_OR_IMMUTABLE",
            "NOT_A_WCAG_CONFORMANCE_CLAIM",
        }
        if len(set(value)) != len(value):
            raise ValueError("limitations must be unique")
        if set(value) != required:
            raise ValueError("synthetic evidence must disclose every scope and trust limitation")
        return value

    @model_validator(mode="after")
    def references_must_be_consistent(self):
        finding_ids = {finding.id for finding in self.findings}
        for finding in self.findings:
            if finding.scan_id != self.scan.id:
                raise ValueError("finding scan_id must match the exported scan")
            if finding.source_mapping.id != finding.id:
                raise ValueError("source mapping id must match its finding")
            if finding.source_mapping.source_revision != self.scan.repo_commit_sha:
                raise ValueError("source mapping revision must match the exported scan")
        for proposal in self.proposals:
            if proposal.finding_id not in finding_ids:
                raise ValueError("proposal must refer to an exported finding")
        return self


def validate_evidence_export(payload: dict) -> None:
    """Raise ValueError unless a Python payload satisfies the manifest contract."""
    EvidenceExport.model_validate(payload)
