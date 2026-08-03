from __future__ import annotations

import re
import unicodedata
from collections import Counter
from datetime import date, datetime
from typing import Any
from urllib.parse import urlsplit, urlunsplit

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
    if value is None:
        return True

    if isinstance(value, str):
        return value.strip().casefold() in MISSING_SENTINELS

    return False


def normalize_text(value: Any, *, preserve_lines: bool = False) -> str | None:
    if is_missing(value):
        return None

    text = unicodedata.normalize(
        "NFC",
        str(value)
    ).replace("\xa0", " ")

    if preserve_lines:
        lines = [
            _SPACE_RE.sub(" ", line).strip()
            for line in text.splitlines()
        ]

        normalized = "\n".join(
            line for line in lines if line
        )

        return (
            _MULTI_NEWLINE_RE.sub("\n", normalized)
            or None
        )

    normalized = _SPACE_RE.sub(
        " ",
        text.replace("\n", " ")
    ).strip()

    return normalized or None


def normalize_url(url: str | None) -> str | None:
    if not url:
        return None

    url = url.strip()

    if not re.match(r"^https?://", url, flags=re.IGNORECASE):
        url = "https://" + url

    parts = urlsplit(url)

    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path.rstrip("/"),
            "",
            "",
        )
    )

def parse_date(value: Any) -> date | None:
    text = normalize_text(value)

    if text is None:
        return None

    iso_candidate = text.replace(
        "Z",
        "+00:00"
    )

    try:
        return datetime.fromisoformat(
            iso_candidate
        ).date()

    except ValueError:
        pass


    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(
                text,
                fmt
            ).date()

        except ValueError:
            continue

    return None



def iso_date(value: Any) -> str | None:
    parsed = parse_date(value)

    return (
        parsed.isoformat()
        if parsed
        else None
    )



def normalize_for_match(value: Any) -> str | None:
    text = normalize_text(value)

    return (
        text.casefold()
        if text
        else None
    )



def tokens(value: Any) -> list[str]:
    text = normalize_for_match(value)

    return (
        _TOKEN_RE.findall(text)
        if text
        else []
    )



def token_f1(left: Any, right: Any) -> float:

    left_tokens = Counter(tokens(left))
    right_tokens = Counter(tokens(right))

    if not left_tokens and not right_tokens:
        return 1.0

    if not left_tokens or not right_tokens:
        return 0.0

    overlap = sum(
        (left_tokens & right_tokens).values()
    )

    precision = overlap / sum(left_tokens.values())
    recall = overlap / sum(right_tokens.values())

    if precision + recall == 0:
        return 0.0

    return (
        2 * precision * recall /
        (precision + recall)
    )



def normalize_document(doc: ICEDocument) -> ICEDocument:

    body = normalize_text(
        doc.body_text,
        preserve_lines=True
    ) or ""


    topics = []

    for topic in doc.topics:
        value = normalize_text(topic)

        if value and value not in topics:
            topics.append(value)


    return ICEDocument(

        # identity
        document_id=doc.document_id,
        url=normalize_url(doc.url) or "",
        input_url=doc.input_url,
        canonical_url=normalize_url(
            doc.canonical_url
        ),
        source_sha256=doc.source_sha256,


        # metadata
        title=normalize_text(doc.title) or "",
        subtitle=normalize_text(doc.subtitle),
        description=normalize_text(doc.description),
        topics=topics,


        # dates
        published_date=iso_date(
            doc.published_date
        ),
        modified_date=iso_date(
            doc.modified_date
        ),


        # location
        dateline=normalize_text(doc.dateline),
        dateline_raw=normalize_text(
            doc.dateline_raw
        ),
        dateline_city=normalize_text(
            doc.dateline_city
        ),
        dateline_region=normalize_text(
            doc.dateline_region
        ),


        city=normalize_text(doc.city),
        state=normalize_text(doc.state),


        # content
        full_text=normalize_text(
            doc.full_text,
            preserve_lines=True
        ) or "",

        body_text=body,

        paragraphs=[
            normalize_text(p) or ""
            for p in doc.paragraphs
        ],

        word_count=len(
            body.split()
        ),


        # media
        image_urls=[
            u for u in (
                normalize_url(img)
                for img in doc.image_urls
            )
            if u
        ],


        # parsing
        document_type=(
            normalize_text(
                doc.document_type
            )
            or "news_release"
        ),

        parse_status=doc.parse_status,

        is_quarantined=doc.is_quarantined,

        quarantine_reason=
            normalize_text(
                doc.quarantine_reason
            ),


        # audit
        field_provenance=
            doc.field_provenance,

        field_confidence=
            doc.field_confidence,

        quality_flags=
            doc.quality_flags,
    )
