from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ParseStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    ACCEPTED = "ACCEPTED"
    QUARANTINED = "QUARANTINED"

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
    count_min: int | None
    count_max: int | None
    count_qualifier: str | None
    evidence_text: str
    evidence_start: int
    evidence_end: int
    extraction_method: str
    confidence: float


@dataclass
class PersonCandidate:
    name: str = ""
    role: Optional[str] = None
    confidence: float = 0.0
    age: Optional[int] = None
    nationality: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


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
    location_full_text: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    full_text: str = ""
    body_text: str = ""
    word_count: int = 0
    image_urls: List[str] = field(default_factory=list)
    scraped_at: Optional[str] = None
    blurb_list: List[str] = field(default_factory=list)
    updated_date: Optional[str] = None
    document_type: str = "news_release"
    is_quarantined: bool = False
    quarantine_reason: Optional[str] = None

    document_id: Optional[str] = None
    input_url: Optional[str] = None
    description: Optional[str] = None
    dateline_raw: Optional[str] = None
    dateline_city: Optional[str] = None
    dateline_region: Optional[str] = None
    dateline_region_code: Optional[str] = None
    dateline_country: Optional[str] = None
    paragraphs: List[str] = field(default_factory=list)
    tables: List[Dict[str, Any]] = field(default_factory=list)
    paragraph_count: int = 0
    source_sha256: Optional[str] = None
    entity_bundle: Optional[str] = None
    parse_status: Optional[ParseStatus] = None
    quality_flags: List[str] = field(default_factory=list)
    field_provenance: Dict[str, str] = field(default_factory=dict)
    field_confidence: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "canonical_url": self.canonical_url,
            "title": self.title,
            "subtitle": self.subtitle,
            "topics": self.topics,
            "date_raw": self.date_raw,
            "date_normalized": self.date_normalized,
            "date_last_updated": self.date_last_updated,
            "published_date": self.published_date,
            "modified_date": self.modified_date,
            "dateline": self.dateline,
            "location_full_text": self.location_full_text,
            "city": self.city,
            "state": self.state,
            "full_text": self.full_text,
            "body_text": self.body_text,
            "word_count": self.word_count,
            "image_urls": self.image_urls,
            "scraped_at": self.scraped_at,
            "blurb_list": self.blurb_list,
            "updated_date": self.updated_date,
            "document_type": self.document_type,
            "is_quarantined": self.is_quarantined,
            "quarantine_reason": self.quarantine_reason,
            "document_id": self.document_id,
            "input_url": self.input_url,
            "description": self.description,
            "dateline_raw": self.dateline_raw,
            "dateline_city": self.dateline_city,
            "dateline_region": self.dateline_region,
            "dateline_region_code": self.dateline_region_code,
            "dateline_country": self.dateline_country,
            "paragraphs": self.paragraphs,
            "tables": self.tables,
            "paragraph_count": self.paragraph_count,
            "source_sha256": self.source_sha256,
            "entity_bundle": self.entity_bundle,
            "parse_status": self.parse_status.value if isinstance(self.parse_status, Enum) else self.parse_status,
            "quality_flags": self.quality_flags,
            "field_provenance": self.field_provenance,
            "field_confidence": self.field_confidence,
        }
        
@dataclass
class FieldMetric:
    field_name: str = ""
    total: int = 0
    matched: int = 0
    missing: int = 0
    accuracy: float = 0.0


@dataclass
class ValidationGate:
    name: str = ""
    status: GateStatus = GateStatus.SKIPPED
    message: str = ""


@dataclass
class ValidationResult:
    passed: bool = False
    gates: List[ValidationGate] = field(default_factory=list)
    field_metrics: List[FieldMetric] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)

DocumentRecord = ICEDocument
