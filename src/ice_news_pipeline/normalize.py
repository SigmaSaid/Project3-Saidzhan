from __future__ import annotations

import re
import unicodedata
from collections import Counter
from datetime import date, datetime
from typing import Any, Optional

from ice_news_pipeline.constants import MISSING_SENTINELS
from ice_news_pipeline.models import ICEDocument

_SPACE_RE = re.compile(r"[^\S\n]+")
_MULTI_NEWLINE_RE = re.compile(r"\n{2,}")
_TOKEN_RE = re.compile(r"\b[\w’'-]+\b", re.UNICODE)

DATE_FORMATS = (
    "%m/%d/%Y",
    "%B %d, %Y",
    "%b %d, %Y",
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d %B %Y",
    "%d %b %Y",
)


def is_missing(value: Any) -> bool:
    """Check if a value is None, empty, or a recognized missing sentinel string."""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().casefold() in MISSING_SENTINELS
    return False


def normalize_text(value: Any, *, preserve_lines: bool = False) -> str | None:
    """
    Normalizes text using Unicode NFC, replaces non-breaking spaces,
    and collapses whitespace while preserving or flattening line breaks.
    """
    if is_missing(value):
        return None
    text = unicodedata.normalize("NFC", str(value)).replace("\xa0", " ")
    
    if preserve_lines:
        lines = [_SPACE_RE.sub(" ", line).strip() for line in text.splitlines()]
        normalized = "\n".join(line for line in lines if line)
        return _MULTI_NEWLINE_RE.sub("\n", normalized) or None
        
    normalized = _SPACE_RE.sub(" ", text.replace("\n", " ")).strip()
    return normalized or None


def normalize_url(value: Any) -> str | None:
    """Standardizes scheme, domain, path, and query parameters for URL comparison."""
    text = normalize_text(value)
    if text is None:
        return None
    
    # Strip protocol prefix for standard comparison
    text_clean = re.sub(r"^https?://", "", text, flags=re.IGNORECASE)
    return text_clean.rstrip("/")


def parse_date(value: Any) -> date | None:
    """Parses various date string formats into a python datetime.date object."""
    text = normalize_text(value)
    if text is None:
        return None
        
    # Attempt ISO format resolution (e.g. 2026-07-31T12:00:00Z)
    iso_candidate = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(iso_candidate).date()
    except ValueError:
        pass
        
    # Fallback to standard human-readable formats
    for date_format in DATE_FORMATS:
        try:
            return datetime.strptime(text, date_format).date()
        except ValueError:
            continue
            
    return None


def iso_date(value: Any) -> str | None:
    """Returns YYYY-MM-DD formatted date string or None if unparseable."""
    parsed = parse_date(value)
    return parsed.isoformat() if parsed else None


def normalize_for_match(value: Any) -> str | None:
    """Case-folds and flattens text for fuzzier token and exact matching."""
    text = normalize_text(value, preserve_lines=False)
    return text.casefold() if text else None


def tokens(value: Any) -> list[str]:
    """Extracts alphanumeric word tokens for precision/recall evaluation."""
    text = normalize_for_match(value)
    return _TOKEN_RE.findall(text) if text else []


def token_f1(left: Any, right: Any) -> float:
    """Computes symmetric Token F1 similarity score between two values."""
    left_tokens = Counter(tokens(left))
    right_tokens = Counter(tokens(right))
    
    if not left_tokens and not right_tokens:
        return 1.0
    if not left_tokens or not right_tokens:
        return 0.0
        
    overlap = sum((left_tokens & right_tokens).values())
    precision = overlap / sum(left_tokens.values())
    recall = overlap / sum(right_tokens.values())
    
    return (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0


def normalize_document(doc: ICEDocument) -> ICEDocument:
    """
    Applies pipeline-wide normalization directly to an ICEDocument instance,
    ensuring consistent text formats, standardized dates, and clean topic lists.
    """
    clean_title = normalize_text(doc.title) or ""
    clean_body = normalize_text(doc.body_text, preserve_lines=True) or ""
    
    clean_topics = []
    if doc.topics:
        for t in doc.topics:
            norm_t = normalize_text(t)
            if norm_t and norm_t not in clean_topics:
                clean_topics.append(norm_t)

    return ICEDocument(
        url=normalize_url(doc.url) or doc.url,
        canonical_url=normalize_url(doc.canonical_url),
        title=clean_title,
        published_date=iso_date(doc.published_date),
        modified_date=iso_date(doc.modified_date),
        topics=clean_topics,
        dateline=normalize_text(doc.dateline),
        body_text=clean_body,
        word_count=len(clean_body.split()),
        image_urls=[url for url in (normalize_url(img) for img in doc.image_urls) if url],
        document_type=normalize_text(doc.document_type) or "news_release",
        is_quarantined=doc.is_quarantined,
        quarantine_reason=normalize_text(doc.quarantine_reason),
    )
