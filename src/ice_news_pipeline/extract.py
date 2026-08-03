from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor
from json import JSONDecodeError
from typing import Any
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from bs4.element import Comment, NavigableString, Tag

from ice_news_pipeline.constants import US_REGION_CODES
from ice_news_pipeline.models import DocumentRecord, ICEDocument, ParseStatus
from ice_news_pipeline.normalize import iso_date, normalize_text, normalize_url, tokens

_DATELINE_RE = re.compile(r"^(?P<dateline>.{2,80}?)(?:\s*[—–]\s*|\s*-\s+)")
_TITLE_SUFFIX_RE = re.compile(r"\s*[|–—-]\s*ICE\s*$", re.IGNORECASE)
_TWO_LETTER_RE = re.compile(r"^[A-Z]{2}$")
_DATA_LAYER_CALL = "window.dataLayer.push("


def _meta_content(soup: BeautifulSoup, key: str, value: str) -> str | None:
    node = soup.find("meta", attrs={key: value})
    return normalize_text(node.get("content")) if isinstance(node, Tag) else None


def _field(
    value: str | None,
    name: str,
    method: str,
    confidence: float,
    provenance: dict[str, str],
    confidences: dict[str, float],
) -> str | None:
    if value is not None:
        provenance[name] = method
        confidences[name] = confidence
    return value


def _decode_data_layer(soup: BeautifulSoup) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    for script in soup.find_all("script"):
        script_text = script.string or script.get_text()
        if _DATA_LAYER_CALL not in script_text:
            continue
        cursor = 0
        while True:
            call_at = script_text.find(_DATA_LAYER_CALL, cursor)
            if call_at < 0:
                break
            payload_at = call_at + len(_DATA_LAYER_CALL)
            try:
                payload, consumed = decoder.raw_decode(script_text[payload_at:].lstrip())
            except JSONDecodeError:
                cursor = payload_at
                continue
            if isinstance(payload, dict) and (
                "entityTaxonomy" in payload or "entityBundle" in payload
            ):
                return payload
            cursor = payload_at + consumed
    return {}


def _extract_topic_fallback(meta_node: Tag | None) -> str | None:
    if meta_node is None:
        return None
    icons = meta_node.find_all("i")
    if len(icons) < 2:
        return None
    fragments: list[str] = []
    for sibling in icons[-1].next_siblings:
        if isinstance(sibling, NavigableString):
            fragments.append(str(sibling))
        elif isinstance(sibling, Tag):
            fragments.append(sibling.get_text(" ", strip=True))
    return normalize_text(" ".join(fragments))


def _semantic_segments(root: Tag) -> list[str]:
    block_names = {"blockquote", "figcaption", "h2", "h3", "h4", "li", "p", "tr"}
    segments: list[str] = []
    fragments: list[str] = []
    current_group: int | None = None

    def flush() -> None:
        if fragments and (text := normalize_text(" ".join(fragments))):
            segments.append(text)
        fragments.clear()

    for descendant in root.descendants:
        if not isinstance(descendant, NavigableString) or isinstance(descendant, Comment):
            continue
        text = normalize_text(descendant)
        if not text:
            continue
        parent = descendant.parent
        if not isinstance(parent, Tag) or parent.name in {"script", "style", "noscript"}:
            continue

        nearest_block: Tag | None = None
        top_level: Tag = parent
        cursor: Tag | None = parent
        while cursor is not None and cursor is not root:
            if nearest_block is None and cursor.name in block_names:
                nearest_block = cursor
            top_level = cursor
            cursor = cursor.parent if isinstance(cursor.parent, Tag) else None
        group = nearest_block or top_level
        group_id = id(group)
        if current_group is not None and group_id != current_group:
            flush()
        current_group = group_id
        fragments.append(text)
    flush()
    return segments


def _extract_body(soup: BeautifulSoup) -> tuple[str | None, list[str], str | None, float]:
    strategies = (
        (".nr-body", "css:.nr-body", 1.0),
        ("[itemprop='articleBody']", "css:[itemprop=articleBody]", 0.75),
        ("article .field--name-body", "css:article .field--name-body", 0.60),
    )
    for selector, method, confidence in strategies:
        root = soup.select_one(selector)
        if not isinstance(root, Tag):
            continue
        paragraphs = _semantic_segments(root)
        if not paragraphs:
            fallback = normalize_text(root.get_text(" ", strip=True))
            paragraphs = [fallback] if fallback else []
        body = "\n".join(paragraphs) if paragraphs else None
        if body:
            return body, paragraphs, method, confidence
    return None, [], None, 0.0


def _header_metadata(
    soup: BeautifulSoup,
) -> tuple[str | None, str | None, str | None, str | None, str | None]:
    meta_node = soup.select_one(".nr-meta")
    if not isinstance(meta_node, Tag):
        return None, None, None, None, None

    first_text = next(meta_node.stripped_strings, None)
    date_raw = normalize_text(first_text)
    locality = meta_node.select_one(".locality")
    city = normalize_text(locality.get_text(" ", strip=True)) if isinstance(locality, Tag) else None

    region_label: str | None = None
    region_code: str | None = None
    country: str | None = None
    if isinstance(locality, Tag):
        region_node = locality.find_next_sibling("span")
        if isinstance(region_node, Tag):
            region_label = normalize_text(region_node.get_text(" ", strip=True).lstrip(", "))
            classes = region_node.get("class", [])
            for class_name in classes if isinstance(classes, list) else []:
                if _TWO_LETTER_RE.fullmatch(str(class_name)):
                    region_code = str(class_name)
                    break
            country_node = region_node.find_next_sibling("span")
            if isinstance(country_node, Tag):
                country = normalize_text(country_node.get_text(" ", strip=True).lstrip(", "))

    if country is None and region_code in US_REGION_CODES:
        country = "United States"
    elif country is None and region_label and region_code not in US_REGION_CODES:
        country = region_label

    return date_raw, city, region_label, region_code, country


def _extract_dateline(paragraphs: list[str]) -> str | None:
    if not paragraphs:
        return None
    match = _DATELINE_RE.match(paragraphs[0])
    candidate = normalize_text(match.group("dateline")) if match else None
    if candidate is None:
        return None
    city_fragment = candidate.split(",", maxsplit=1)[0]
    letters = "".join(character for character in city_fragment if character.isalpha())
    return candidate if letters and letters == letters.upper() else None


def _extract_tables(soup: BeautifulSoup) -> list[dict[str, Any]]:
    tables: list[dict[str, Any]] = []
    for table_index, table in enumerate(soup.select(".nr-body table")):
        rows: list[list[str]] = []
        for row in table.select("tr"):
            cells = [
                text
                for cell in row.select("th, td")
                if (text := normalize_text(cell.get_text(" ", strip=True))) is not None
            ]
            if cells:
                rows.append(cells)
        if not rows:
            continue
        header_cells = [
            text
            for cell in table.select("thead tr:first-child th, thead tr:first-child td")
            if (text := normalize_text(cell.get_text(" ", strip=True))) is not None
        ]
        if header_cells and rows and rows[0] == header_cells:
            rows = rows[1:]
        if not header_cells and table.select_one("tr th"):
            header_cells = rows[0]
            rows = rows[1:]
        tables.append(
            {
                "table_index": table_index,
                "headers": header_cells,
                "rows": rows,
            }
        )
    return tables


def _extract_images(soup: BeautifulSoup, base_url: str) -> list[str]:
    images: list[str] = []
    seen: set[str] = set()
    nodes = soup.select(
        ".colorbox-image-grid a.colorbox[href], .nr-image-container img, .nr-body img"
    )
    for image in nodes:
        attributes = ("href",) if image.name == "a" else ("src", "data-src", "data-original")
        candidate = next(
            (
                normalized
                for attribute in attributes
                if (normalized := normalize_text(image.get(attribute))) is not None
            ),
            None,
        )
        if not candidate:
            continue
        absolute = normalize_url(urljoin(base_url, candidate))
        if absolute and absolute not in seen:
            seen.add(absolute)
            images.append(absolute)
    return images


def extract_document(example: dict[str, Any] | str, html_str: str | None = None) -> DocumentRecord:
    """Извлекает документ как из словаря-обертки, так и при прямом передаче URL и HTML-строки."""
    if isinstance(example, str):
        input_url = normalize_url(example) or ""
        raw_html = str(html_str or "")
    else:
        input_url = normalize_url(example.get("url")) or ""
        raw_html = str(example.get("html") or "")

    source_sha256 = hashlib.sha256(raw_html.encode("utf-8")).hexdigest()
    soup = BeautifulSoup(raw_html, "lxml")
    provenance: dict[str, str] = {}
    confidences: dict[str, float] = {}
    flags: list[str] = []

    canonical_node = soup.find("link", rel="canonical")
    canonical = normalize_url(canonical_node.get("href")) if isinstance(canonical_node, Tag) else None
    canonical = _field(
        canonical,
        "canonical_url",
        "link[rel=canonical]",
        1.0,
        provenance,
        confidences,
    )

    title_node = soup.select_one(".nr-title h1")
    title = normalize_text(title_node.get_text(" ", strip=True)) if isinstance(title_node, Tag) else None
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
        title = normalize_text(_TITLE_SUFFIX_RE.sub("", soup.title.get_text(" ", strip=True)))
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
    topic_mapping = taxonomy.get("news_release_topics", {}) if isinstance(taxonomy, dict) else {}
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
        if body_method != "css:.nr-body":
            flags.append("body_fallback")
    dateline_raw = _extract_dateline(paragraphs)
    tables = _extract_tables(soup)
    _field(
        dateline_raw,
        "dateline_raw",
        "regex:first_body_block",
        0.9,
        provenance,
        confidences,
    )
    image_urls = _extract_images(soup, canonical or input_url)
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
    if "/news/releases/" not in urlsplit(input_url).path:
        flags.append("unexpected_url_path")
    if canonical and input_url and canonical != input_url:
        flags.append("canonical_url_mismatch")
    if urlsplit(input_url).netloc.casefold() not in {"ice.gov", "www.ice.gov"}:
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

    # Безопасное инстанцирование модели в зависимости от определенной структуры
    doc_kwargs = {
        "url": input_url,
        "canonical_url": canonical,
        "title": title or "",
        "subtitle": subtitle,
        "published_date": published_date,
        "modified_date": modified_date,
        "date_raw": date_raw,
        "dateline": dateline_raw,
        "topics": topics,
        "full_text": body_text or "",
        "body_text": body_text or "",
        "word_count": len(tokens(body_text or "")),
        "image_urls": image_urls,
        "document_type": entity_bundle or "news_release",
        "is_quarantined": quarantined,
        "quarantine_reason": ", ".join(sorted(set(flags))) if quarantined else None,
    }

    try:
        return DocumentRecord(**doc_kwargs)
    except TypeError:
        # Резервный вызов для кастомной сигнатуры DocumentRecord
        return DocumentRecord(
            document_id=hashlib.sha256(identity_url.encode("utf-8")).hexdigest()[:20],
            input_url=input_url,
            canonical_url=canonical,
            title=title or "",
            subtitle=subtitle,
            description=description,
            published_date=published_date,
            modified_date=modified_date,
            date_raw=date_raw,
            dateline_raw=dateline_raw,
            dateline_city=city,
            dateline_region=region,
            dateline_region_code=region_code,
            dateline_country=country,
            topics=topics,
            body_text=body_text or "",
            paragraphs=paragraphs,
            tables=tables,
            image_urls=image_urls,
            word_count=len(tokens(body_text or "")),
            paragraph_count=len(paragraphs),
            source_sha256=source_sha256,
            entity_bundle=entity_bundle,
            parse_status=status,
            quality_flags=sorted(set(flags)),
            field_provenance=provenance,
            field_confidence=confidences,
        )


parse_ice_html = extract_document


def extract_documents(
    examples: Iterable[dict[str, Any]], *, workers: int = 1
) -> Iterator[DocumentRecord]:
    if workers <= 1:
        for example in examples:
            yield extract_document(example)
        return
    with ThreadPoolExecutor(max_workers=workers) as executor:
        yield from executor.map(extract_document, examples)
