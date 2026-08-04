from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ParseStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    ACCEPTED = "accepted"
    QUARANTINED = "quarantined"


class GateStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    SKIPPED = "skipped"


@dataclass
class PersonCandidate:
    mention_id: str
    document_id: str
    name_raw: str
    age: int | None = None
    residence_raw: str | None = None
    origin_country_raw: str | None = None
    evidence_text: str = ""
    evidence_start: int = 0
    evidence_end: int = 0
    extraction_method: str = ""
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            key: (value.value if isinstance(value, Enum) else value)
            for key, value in self.__dict__.items()
        }


@dataclass
class EventCandidate:
    event_id: str
    document_id: str
    action_type: str
    legal_stage: str
    count_min: int | None = None
    count_max: int | None = None
    count_qualifier: str | None = None
    evidence_text: str = ""
    evidence_start: int = 0
    evidence_end: int = 0
    extraction_method: str = ""
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            key: (value.value if isinstance(value, Enum) else value)
            for key, value in self.__dict__.items()
        }


@dataclass
class ICEDocument:
    document_id: str = ""

    url: str = ""
    input_url: str | None = None
    canonical_url: str | None = None
    source_sha256: str | None = None

    title: str = ""
    subtitle: str | None = None
    description: str | None = None
    topics: list[str] = field(default_factory=list)

    date_raw: str | None = None
    date_normalized: str | None = None
    date_last_updated: str | None = None
    published_date: str | None = None
    modified_date: str | None = None
    updated_date: str | None = None

    dateline: str | None = None
    dateline_raw: str | None = None
    dateline_city: str | None = None
    dateline_region: str | None = None
    dateline_region_code: str | None = None
    dateline_country: str | None = None

    city: str | None = None
    state: str | None = None
    location_full_text: str | None = None

    full_text: str = ""
    body_text: str = ""

    paragraphs: list[str] = field(default_factory=list)
    tables: list[dict[str, Any]] = field(default_factory=list)

    word_count: int = 0
    paragraph_count: int = 0

    image_urls: list[str] = field(default_factory=list)

    scraped_at: str | None = None

    document_type: str = "news_release"

    parse_status: ParseStatus = ParseStatus.QUARANTINED

    is_quarantined: bool = False
    quarantine_reason: str | None = None

    entity_bundle: str | None = None

    quality_flags: list[str] = field(default_factory=list)

    field_provenance: dict[str, str] = field(default_factory=dict)
    field_confidence: dict[str, float] = field(default_factory=dict)

    blurb_list: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            key: (value.value if isinstance(value, Enum) else value)
            for key, value in self.__dict__.items()
        }


@dataclass
class FieldMetric:
    field: str = ""
    reference_present: int = 0
    extracted_present: int = 0
    both_present: int = 0
    exact_matches: int = 0
    false_positives: int = 0
    coverage: float = 0.0
    agreement: float = 0.0


@dataclass
class ValidationGate:
    name: str = ""
    status: GateStatus = GateStatus.SKIPPED
    observed: str = ""
    requirement: str = ""
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "observed": self.observed,
            "requirement": self.requirement,
            "detail": self.detail,
        }


@dataclass
class ValidationResult:
    status: GateStatus = GateStatus.SKIPPED

    gates: list[ValidationGate] = field(default_factory=list)
    field_metrics: list[FieldMetric] = field(default_factory=list)

    reference_profile: dict[str, Any] = field(default_factory=dict)
    document_profile: dict[str, Any] = field(default_factory=dict)
    body_similarity: dict[str, Any] = field(default_factory=dict)

    row_accounting: dict[str, Any] = field(default_factory=dict)

    issues: list[dict[str, Any]] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.status != GateStatus.FAIL

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "gates": [gate.to_dict() if hasattr(gate, "to_dict") else gate for gate in self.gates],
            "field_metrics": [metric.__dict__ for metric in self.field_metrics],
            "reference_profile": self.reference_profile,
            "document_profile": self.document_profile,
            "body_similarity": self.body_similarity,
            "row_accounting": self.row_accounting,
            "issues": self.issues,
        }


DocumentRecord = ICEDocument
