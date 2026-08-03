from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ParseStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass
class EventCandidate:
    text: str = ""
    event_type: Optional[str] = None
    confidence: float = 0.0


@dataclass
class PersonCandidate:
    name: str = ""
    role: Optional[str] = None
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
        }


DocumentRecord = ICEDocument
