import hashlib
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit
from bs4 import BeautifulSoup, Tag

from ice_news_pipeline.schema import DocumentRecord, ParseStatus
from ice_news_pipeline.utils import (
    BODY_SELECTOR,
    _TITLE_SUFFIX_RE,
    _decode_data_layer,
    _extract_body,
    _extract_dateline,
    _extract_topic_fallback,
    _field,
    _header_metadata,
    _meta_content,
    extract_image_urls,
    extract_tables,
    iso_date,
    normalize_text,
    normalize_url,
    tokens,
)

def extract_document(
    example: dict[str, Any] | str, html_str: str | None = None
) -> DocumentRecord:
    """Extract structured document record from HTML text or input dict."""
    if isinstance(example, str):
        input_url = normalize_url(example) or ""
        raw_html = str(html_str or "")
    else:
        input_url = normalize_url(example.get("url") or example.get("input_url")) or ""
        raw_html = str(example.get("html") or example.get("content") or "")

    source_sha256 = hashlib.sha256(raw_html.encode("utf-8")).hexdigest()
    soup = BeautifulSoup(raw_html, "lxml")
    provenance: dict[str, str] = {}
    confidences: dict[str, float] = {}
    flags: list[str] = []

    canonical_node = soup.find("link", rel="canonical")
    canonical = (
        normalize_url(canonical_node.get("href"))
        if isinstance(canonical_node, Tag)
        else None
    )
    canonical = _field(
        canonical,
        "canonical_url",
        "link[rel=canonical]",
        1.0,
        provenance,
        confidences,
    )

    title_node = soup.select_one(".nr-title h1")
    title = (
        normalize_text(title_node.get_text(" ", strip=True))
        if isinstance(title_node, Tag)
        else None
    )
    title_method = "css:.nr-title h1"
    title_confidence = 1.0
    if title is None:
        title = _meta_content(soup, "property", "og:title")
        title_method = "meta:og:title"
        title_confidence = 0.9
        if title:
            flags.append("title_fallback")
    if title is None:
        fallback_title = soup.find("h1")
        title = (
            normalize_text(fallback_title.get_text(" ", strip=True))
            if isinstance(fallback_title, Tag)
            else None
        )
        title_method = "css:h1"
        title_confidence = 0.7
        if title:
            flags.append("title_fallback")
    if title is None and soup.title:
        title = normalize_text(
            _TITLE_SUFFIX_RE.sub("", soup.title.get_text(" ", strip=True))
        )
        title_method = "html:title"
        title_confidence = 0.5
        if title:
            flags.append("title_fallback")
    title = _field(
        title or "",
        "title",
        title_method,
        title_confidence,
        provenance,
        confidences,
    )

    subtitle_node = soup.select_one(".nr-subtitle")
    subtitle = (
        normalize_text(subtitle_node.get_text(" ", strip=True))
        if isinstance(subtitle_node, Tag)
        else None
    )
    subtitle = _field(
        subtitle,
        "subtitle",
        "css:.nr-subtitle",
        1.0,
        provenance,
        confidences,
    )
    description = _field(
        _meta_content(soup, "name", "description"),
        "description",
        "meta:description",
        0.95,
        provenance,
        confidences,
    )

    date_raw, city, region, region_code, country = _header_metadata(soup)
    published = _meta_content(soup, "property", "article:published_time")
    published_method = "meta:article:published_time"
    published_confidence = 1.0
    if iso_date(published) is None:
        published = date_raw
        published_method = "css:.nr-meta"
        published_confidence = 0.85
        if published:
            flags.append("published_date_fallback")
    published_date = _field(
        iso_date(published),
        "published_date",
        published_method,
        published_confidence,
        provenance,
        confidences,
    )
    modified_date = _field(
        iso_date(_meta_content(soup, "property", "article:modified_time")),
        "modified_date",
        "meta:article:modified_time",
        1.0,
        provenance,
        confidences,
    )
    date_raw = _field(
        date_raw,
        "date_raw",
        "css:.nr-meta",
        0.95,
        provenance,
        confidences,
    )

    for field_name, value in (
        ("dateline_city", city),
        ("dateline_region", region),
        ("dateline_region_code", region_code),
        ("dateline_country", country),
    ):
        _field(value, field_name, "css:.nr-meta", 0.95, provenance, confidences)

    data_layer = _decode_data_layer(soup)
    taxonomy = data_layer.get("entityTaxonomy", {})
    topic_mapping = (
        taxonomy.get("news_release_topics", {}) if isinstance(taxonomy, dict) else {}
    )
    topics = (
        [str(topic) for topic in topic_mapping.values()]
        if isinstance(topic_mapping, dict)
        else []
    )
    if topics:
        provenance["topics"] = "json:dataLayer.entityTaxonomy.news_release_topics"
        confidences["topics"] = 1.0
    else:
        fallback_topic = _extract_topic_fallback(soup.select_one(".nr-meta"))
        topics = [fallback_topic] if fallback_topic else []
        if topics:
            provenance["topics"] = "css:.nr-meta"
            confidences["topics"] = 0.6
            flags.append("topics_fallback_unsplit")

    body_text, paragraphs, body_method, body_confidence = _extract_body(soup)
    if body_text and body_method:
        provenance["body_text"] = body_method
        confidences["body_text"] = body_confidence
        if body_method != f"css:{BODY_SELECTOR}":
            flags.append("body_fallback")
    dateline_raw = _extract_dateline(paragraphs)
    tables = extract_tables(soup)
    _field(
        dateline_raw,
        "dateline_raw",
        "regex:first_body_block",
        0.9,
        provenance,
        confidences,
    )
    image_urls = extract_image_urls(soup, canonical or input_url)
    if image_urls:
        provenance["image_urls"] = "css:.nr-image-container img,.nr-body img"
        confidences["image_urls"] = 1.0

    entity_bundle = normalize_text(data_layer.get("entityBundle"))
    if entity_bundle:
        provenance["entity_bundle"] = "json:dataLayer.entityBundle"
        confidences["entity_bundle"] = 1.0

    if not title:
        flags.append("missing_title")
    if not published_date:
        flags.append("missing_published_date")
    if not body_text:
        flags.append("missing_body")
    elif len(body_text) < 100:
        flags.append("short_body")
    if not topics:
        flags.append("missing_topics")
    if entity_bundle and entity_bundle != "news_release":
        flags.append(f"unexpected_entity_bundle:{entity_bundle}")
    if input_url and "/news/releases/" not in urlsplit(input_url).path:
        flags.append("unexpected_url_path")
    if canonical and input_url and canonical != input_url:
        flags.append("canonical_url_mismatch")
    if (
        input_url
        and urlsplit(input_url).netloc.casefold() not in {"ice.gov", "www.ice.gov"}
    ):
        flags.append("unexpected_source_domain")

    quarantine_reasons = {
        "missing_title",
        "missing_published_date",
        "missing_body",
        "short_body",
        "unexpected_url_path",
        "canonical_url_mismatch",
        "unexpected_source_domain",
    }
    quarantined = bool(quarantine_reasons.intersection(flags)) or any(
        flag.startswith("unexpected_entity_bundle:") for flag in flags
    )
    status = ParseStatus.QUARANTINED if quarantined else ParseStatus.ACCEPTED
    identity_url = canonical or input_url

    data_dict = {
        "document_id": hashlib.sha256(identity_url.encode("utf-8")).hexdigest()[:20],
        "input_url": input_url,
        "canonical_url": canonical,
        "url": input_url,
        "title": title or "",
        "subtitle": subtitle,
        "description": description,
        "published_date": published_date,
        "modified_date": modified_date,
        "date_raw": date_raw,
        "dateline": dateline_raw,
        "dateline_raw": dateline_raw,
        "dateline_city": city,
        "dateline_region": region,
        "dateline_region_code": region_code,
        "dateline_country": country,
        "topics": topics,
        "full_text": body_text or "",
        "body_text": body_text or "",
        "paragraphs": paragraphs,
        "tables": tables,
        "image_urls": image_urls,
        "word_count": len(tokens(body_text or "")),
        "paragraph_count": len(paragraphs),
        "source_sha256": source_sha256,
        "entity_bundle": entity_bundle,
        "document_type": entity_bundle or "news_release",
        "parse_status": status,
        "is_quarantined": quarantined,
        "quarantine_reason": ", ".join(sorted(set(flags))) if quarantined else None,
        "quality_flags": sorted(set(flags)),
        "field_provenance": provenance,
        "field_confidence": confidences,
    }

    try:
        return DocumentRecord(**data_dict)
    except TypeError:
        return DocumentRecord(
            url=input_url,
            canonical_url=canonical,
            title=title or "",
            subtitle=subtitle,
            published_date=published_date,
            modified_date=modified_date,
            date_raw=date_raw,
            dateline=dateline_raw,
            topics=topics,
            body_text=body_text or "",
            word_count=len(tokens(body_text or "")),
            image_urls=image_urls,
            document_type=entity_bundle or "news_release",
            parse_status=status,
            is_quarantined=quarantined,
            quarantine_reason=", ".join(sorted(set(flags))) if quarantined else None,
            quality_flags=sorted(set(flags)),
            field_provenance=provenance,
            field_confidence=confidences,
            source_sha256=source_sha256,
            entity_bundle=entity_bundle,
        )
