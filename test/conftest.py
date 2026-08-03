from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ice_news_pipeline.constants import REQUIRED_REFERENCE_FIELDS
from ice_news_pipeline.models import DocumentRecord

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def release_html() -> str:
    return (FIXTURES / "release.html").read_text(encoding="utf-8")


@pytest.fixture
def fallback_html() -> str:
    return (FIXTURES / "fallback.html").read_text(encoding="utf-8")


@pytest.fixture
def social_html() -> str:
    return (FIXTURES / "social.html").read_text(encoding="utf-8")


def reference_from_document(document: DocumentRecord) -> dict[str, Any]:
    row: dict[str, Any] = dict.fromkeys(REQUIRED_REFERENCE_FIELDS, "not found")
    row.update(
        {
            "url": document.input_url,
            "title": document.title or "not found",
            "subtitle": document.subtitle or "not found",
            "topics": ", ".join(document.topics) or "not found",
            "date_raw": document.date_raw or "not found",
            "date_normalized": (
                f"{document.published_date[5:7]}/{document.published_date[8:10]}/"
                f"{document.published_date[:4]}"
                if document.published_date
                else "not found"
            ),
            "date_last_updated": (
                f"{document.modified_date[5:7]}/{document.modified_date[8:10]}/"
                f"{document.modified_date[:4]}"
                if document.modified_date
                else "not found"
            ),
            "location_full_text": document.dateline_raw or "not found",
            "city": document.dateline_city or "not found",
            "state": document.dateline_region or "not found",
            "full_text": document.body_text or "not found",
            "image_urls": "; ".join(document.image_urls) or "not found",
            "scraped_at": "2026-05-22T22:05:20Z",
        }
    )
    return row
