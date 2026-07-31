from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Sequence


class ParseStatus(str, Enum):
    ACCEPTED = "accepted"
    QUARANTINED = "quarantined"


class GateStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


@dataclass(slots=True)
class DocumentRecord:
    document_id: str
    input_url: str
    canonical_url: str | None
    title: str | None
    subtitle: str | None
    description: str | None
    published_date: str | None
    modified_date: str | None
    date_raw: str | None
    dateline_raw: str | None
    dateline_city: str | None
    dateline_region: str | None
    dateline_region_code: str | None
    dateline_country: str | None
    topics: list[str] = field(default_factory=list)
    body_text: str | None = None
    paragraphs: list[str] = field(default_factory=list)
    tables: list[dict[str, Any]] = field(default_factory=list)
    image_urls: list[str] = field(default_factory=list)
    word_count: int = 0
    paragraph_count: int = 0
    source_sha256: str = ""
    entity_bundle: str | None = None
    parse_status: ParseStatus = ParseStatus.ACCEPTED
    quality_flags: list[str] = field(default_factory=list)
    field_provenance: dict[str, str] = field(default_factory=dict)
    field_confidence: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "input_url": self.input_url,
            "canonical_url": self.canonical_url,
            "title": self.title,
            "subtitle": self.subtitle,
            "description": self.description,
            "published_date": self.published_date,
            "modified_date": self.modified_date,
            "date_raw": self.date_raw,
            "dateline_raw": self.dateline_raw,
            "dateline_city": self.dateline_city,
            "dateline_region": self.dateline_region,
            "dateline_region_code": self.dateline_region_code,
            "dateline_country": self.dateline_country,
            "topics": list(self.topics),
            "body_text": self.body_text,
            "paragraphs": list(self.paragraphs),
            "tables": [dict(tbl) for tbl in self.tables],
            "image_urls": list(self.image_urls),
            "word_count": self.word_count,
            "paragraph_count": self.paragraph_count,
            "source_sha256": self.source_sha256,
            "entity_bundle": self.entity_bundle,
            "parse_status": self.parse_status.value,
            "quality_flags": list(self.quality_flags),
            "field_provenance": dict(self.field_provenance),
            "field_confidence": dict(self.field_confidence),
        }


@dataclass(slots=True)
class EventCandidate:
    event_id: str
    document_id: str
    action_type: str
    legal_stage: str
    evidence_text: str
    evidence_start: int
    evidence_end: int
    extraction_method: str
    confidence: float
    count_min: int | None = None
    count_max: int | None = None
    count_qualifier: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "document_id": self.document_id,
            "action_type": self.action_type,
            "legal_stage": self.legal_stage,
            "count_min": self.count_min,
            "count_max": self.count_max,
            "count_qualifier": self.count_qualifier,
            "evidence_text": self.evidence_text,
            "evidence_start": self.evidence_start,
            "evidence_end": self.evidence_end,
            "extraction_method": self.extraction_method,
            "confidence": self.confidence,
        }


@dataclass(slots=True)
class PersonCandidate:
    mention_id: str
    document_id: str
    name_raw: str
    evidence_text: str
    evidence_start: int
    evidence_end: int
    extraction_method: str
    confidence: float
    age: int | None = None
    residence_raw: str | None = None
    origin_country_raw: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mention_id": self.mention_id,
            "document_id": self.document_id,
            "name_raw": self.name_raw,
            "age": self.age,
            "residence_raw": self.residence_raw,
            "origin_country_raw": self.origin_country_raw,
            "evidence_text": self.evidence_text,
            "evidence_start": self.evidence_start,
            "evidence_end": self.evidence_end,
            "extraction_method": self.extraction_method,
            "confidence": self.confidence,
        }


@dataclass(slots=True)
class FieldMetric:
    field: str
    reference_present: int
    extracted_present: int
    both_present: int
    exact_matches: int
    false_positives: int
    coverage: float
    agreement: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "reference_present": self.reference_present,
            "extracted_present": self.extracted_present,
            "both_present": self.both_present,
            "exact_matches": self.exact_matches,
            "false_positives": self.false_positives,
            "coverage": self.coverage,
            "agreement": self.agreement,
        }


@dataclass(slots=True)
class ValidationGate:
    name: str
    status: GateStatus
    observed: str
    requirement: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "status": self.status.value,
            "observed": self.observed,
            "requirement": self.requirement,
            "detail": self.detail,
        }


@dataclass(slots=True)
class ValidationResult:
    gates: Sequence[ValidationGate]
    field_metrics: Sequence[FieldMetric]
    reference_profile: dict[str, Any]
    document_profile: dict[str, Any]
    body_similarity: dict[str, float | int]
    row_accounting: dict[str, int]
    issues: list[dict[str, Any]] = field(default_factory=list)

    @property
    def status(self) -> GateStatus:
        statuses = {gate.status for gate in self.gates}
        if GateStatus.FAIL in statuses:
            return GateStatus.FAIL
        if GateStatus.WARN in statuses:
            return GateStatus.WARN
        return GateStatus.PASS

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "gates": [gate.to_dict() for gate in self.gates],
            "field_metrics": [metric.to_dict() for metric in self.field_metrics],
            "reference_profile": dict(self.reference_profile),
            "document_profile": dict(self.document_profile),
            "body_similarity": dict(self.body_similarity),
            "row_accounting": dict(self.row_accounting),
            "issues": [dict(issue) for issue in self.issues],
        }
