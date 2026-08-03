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
class ICEDocument:
    url: str = ""
    canonical_url: Optional[str] = None

    title: str = ""
    subtitle: Optional[str] = None

    topics: List[str] = field(default_factory=list)

    date_raw: Optional[str] = None
    date_normalized: Optional[str] = None
    date_last_updated: Optional[str] = None

    published_date: Optional[str] = None
    modified_date: Optional[str] = None

    dateline: Optional[str] = None
    dateline_raw: Optional[str] = None
    dateline_city: Optional[str] = None
    dateline_region: Optional[str] = None
    dateline_region_code: Optional[str] = None
    dateline_country: Optional[str] = None

    location_full_text: Optional[str] = None

    city: Optional[str] = None
    state: Optional[str] = None

    full_text: str = ""
    body_text: str = ""

    paragraphs: List[str] = field(default_factory=list)
    tables: List[Dict[str, Any]] = field(default_factory=list)

    paragraph_count: int = 0
    word_count: int = 0

    image_urls: List[str] = field(default_factory=list)

    scraped_at: Optional[str] = None

    document_id: Optional[str] = None
    input_url: Optional[str] = None

    description: Optional[str] = None

    document_type: str = "news_release"

    entity_bundle: Optional[str] = None

    parse_status: Optional[ParseStatus] = None

    is_quarantined: bool = False
    quarantine_reason: Optional[str] = None

    quality_flags: List[str] = field(default_factory=list)

    field_provenance: Dict[str, str] = field(default_factory=dict)
    field_confidence: Dict[str, float] = field(default_factory=dict)


    def to_dict(self) -> Dict[str, Any]:
        result = {}

        for key, value in self.__dict__.items():
            if isinstance(value, Enum):
                result[key] = value.value
            else:
                result[key] = value

        return result



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



@dataclass
class ValidationResult:

    gates: List[ValidationGate] = field(default_factory=list)

    field_metrics: List[FieldMetric] = field(default_factory=list)


    reference_profile: Dict[str, Any] = field(default_factory=dict)

    document_profile: Dict[str, Any] = field(default_factory=dict)

    body_similarity: Dict[str, Any] = field(default_factory=dict)


    row_accounting: Dict[str, Any] = field(default_factory=dict)

    issues: List[Dict[str, Any]] = field(default_factory=list)



    @property
    def passed(self) -> bool:
        return all(
            gate.status != GateStatus.FAIL
            for gate in self.gates
        )



DocumentRecord = ICEDocument
