from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ParseStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    ACCEPTED = "accepted"
    QUARANTINED = "quarantined"


class GateStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    SKIPPED = "SKIPPED"


@dataclass
class PersonCandidate:
    mention_id: str
    document_id: str
    name_raw: str
    age: Optional[int] = None
    residence_raw: Optional[str] = None
    origin_country_raw: Optional[str] = None
    evidence_text: str = ""
    evidence_start: int = 0
    evidence_end: int = 0
    extraction_method: str = ""
    confidence: float = 0.0


@dataclass
class EventCandidate:
    event_id: str
    document_id: str
    action_type: str
    legal_stage: str
    count_min: Optional[int] = None
    count_max: Optional[int] = None
    count_qualifier: Optional[str] = None
    evidence_text: str = ""
    evidence_start: int = 0
    evidence_end: int = 0
    extraction_method: str = ""
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            key: (
                value.value
                if isinstance(value, Enum)
                else value
            )
            for key, value in self.__dict__.items()
        }

@dataclass
class ICEDocument:

    document_id: Optional[str] = None

    url: str = ""
    input_url: Optional[str] = None
    canonical_url: Optional[str] = None
    source_sha256: Optional[str] = None

    title: str = ""
    subtitle: Optional[str] = None
    description: Optional[str] = None
    topics: List[str] = field(default_factory=list)

    date_raw: Optional[str] = None
    date_normalized: Optional[str] = None
    date_last_updated: Optional[str] = None
    published_date: Optional[str] = None
    modified_date: Optional[str] = None
    updated_date: Optional[str] = None

    dateline: Optional[str] = None
    dateline_raw: Optional[str] = None
    dateline_city: Optional[str] = None
    dateline_region: Optional[str] = None
    dateline_region_code: Optional[str] = None
    dateline_country: Optional[str] = None

    city: Optional[str] = None
    state: Optional[str] = None
    location_full_text: Optional[str] = None

    full_text: str = ""
    body_text: str = ""

    paragraphs: List[str] = field(default_factory=list)
    tables: List[Dict[str, Any]] = field(default_factory=list)

    word_count: int = 0
    paragraph_count: int = 0

    image_urls: List[str] = field(default_factory=list)

    scraped_at: Optional[str] = None

    document_type: str = "news_release"

    parse_status: Optional[ParseStatus] = None

    is_quarantined: bool = False
    quarantine_reason: Optional[str] = None

    entity_bundle: Optional[str] = None

    quality_flags: List[str] = field(default_factory=list)

    field_provenance: Dict[str, str] = field(default_factory=dict)
    field_confidence: Dict[str, float] = field(default_factory=dict)

    blurb_list: List[str] = field(default_factory=list)


    def to_dict(self) -> Dict[str, Any]:
        return {
            key: (
                value.value
                if isinstance(value, Enum)
                else value
            )
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

    def to_dict(self) -> Dict[str, Any]:
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

    gates: List[ValidationGate] = field(default_factory=list)
    field_metrics: List[FieldMetric] = field(default_factory=list)

    reference_profile: Dict[str, Any] = field(default_factory=dict)
    document_profile: Dict[str, Any] = field(default_factory=dict)
    body_similarity: Dict[str, Any] = field(default_factory=dict)

    row_accounting: Dict[str, Any] = field(default_factory=dict)

    issues: List[Dict[str, Any]] = field(default_factory=list)


    @property
    def passed(self) -> bool:
        return self.status != GateStatus.FAIL


    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "gates": [
                gate.to_dict()
                for gate in self.gates
            ],
            "field_metrics": [
                metric.__dict__
                for metric in self.field_metrics
            ],
            "reference_profile": self.reference_profile,
            "document_profile": self.document_profile,
            "body_similarity": self.body_similarity,
            "row_accounting": self.row_accounting,
            "issues": self.issues,
        }


DocumentRecord = ICEDocument
