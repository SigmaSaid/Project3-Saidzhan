from __future__ import annotations

from ice_news_pipeline.extract import extract_document
from ice_news_pipeline.models import ParseStatus


def test_extracts_release_with_provenance_and_scoped_body(release_html: str) -> None:
    document = extract_document(
        {
            "url": "https://www.ice.gov/news/releases/carefully-documented-operation",
            "html": release_html,
        }
    )

    assert document.parse_status is ParseStatus.ACCEPTED
    assert document.title == "ICE announces a carefully documented operation"
    assert document.subtitle == "Evidence-preserving fixture"
    assert document.published_date == "2025-02-03"
    assert document.modified_date == "2025-02-05"
    assert document.dateline_raw == "AUSTIN, Texas"
    assert document.dateline_city == "Austin"
    assert document.dateline_region == "TX"
    assert document.dateline_country == "United States"
    assert document.topics == [
        "Firearms, Ammunition and Explosives",
        "Enforcement and Removal",
    ]
    assert "navigation" not in (document.body_text or "").casefold()
    assert "footer" not in (document.body_text or "").casefold()
    assert document.field_provenance["body_text"] == "css:.nr-body"
    assert document.field_confidence["topics"] == 1.0
    assert document.image_urls == [
        "https://www.ice.gov/sites/default/files/hero.jpg"
    ]
    assert document.tables == [
        {
            "table_index": 0,
            "headers": ["Name", "Age", "Location"],
            "rows": [["Jane Roe", "29", "Miami"]],
        }
    ]


def test_international_dateline_and_title_fallback_are_explicit(fallback_html: str) -> None:
    document = extract_document(
        {
            "url": "https://www.ice.gov/news/releases/template-drift",
            "html": fallback_html,
        }
    )

    assert document.parse_status is ParseStatus.ACCEPTED
    assert document.title == "Template drift fallback title"
    assert document.dateline_city == "Lima"
    assert document.dateline_region == "Peru"
    assert document.dateline_region_code == "PE"
    assert document.dateline_country == "Peru"
    assert "title_fallback" in document.quality_flags
    assert document.field_provenance["title"] == "meta:og:title"


def test_non_release_is_quarantined_not_dropped(social_html: str) -> None:
    document = extract_document(
        {
            "url": "https://www.ice.gov/news/releases/social",
            "html": social_html,
        }
    )

    assert document.parse_status is ParseStatus.QUARANTINED
    assert document.entity_bundle == "basic_page"
    assert "missing_published_date" in document.quality_flags
    assert "canonical_url_mismatch" in document.quality_flags
    assert "unexpected_entity_bundle:basic_page" in document.quality_flags
