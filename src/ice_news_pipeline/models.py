from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ICEDocument:
    url: str = ""
    title: str = ""
    subtitle: Optional[str] = None
    topics: List[str] = field(default_factory=list)
    date_raw: Optional[str] = None
    date_normalized: Optional[str] = None
    date_last_updated: Optional[str] = None
    location_full_text: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    full_text: str = ""
    image_urls: List[str] = field(default_factory=list)
    scraped_at: Optional[str] = None
    blurb_list: List[str] = field(default_factory=list)
    updated_date: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "subtitle": self.subtitle,
            "topics": self.topics,
            "date_raw": self.date_raw,
            "date_normalized": self.date_normalized,
            "date_last_updated": self.date_last_updated,
            "location_full_text": self.location_full_text,
            "city": self.city,
            "state": self.state,
            "full_text": self.full_text,
            "image_urls": self.image_urls,
            "scraped_at": self.scraped_at,
            "blurb_list": self.blurb_list,
            "updated_date": self.updated_date,
        }
