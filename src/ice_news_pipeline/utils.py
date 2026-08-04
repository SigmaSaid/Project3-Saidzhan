import json
import re
from urllib.parse import urljoin

from bs4 import Tag

from ice_news_pipeline.constants import BODY_SELECTOR
from ice_news_pipeline.normalize import (
    normalize_text,
)

_TITLE_SUFFIX_RE = re.compile(r"\s*\|\s*U\.S\. Immigration and Customs Enforcement$")


def _field(value, name, method, confidence, provenance, confidences):
    if value is not None:
        provenance[name] = method
        confidences[name] = confidence
    return value


def _meta_content(soup, attr, key):
    node = soup.find("meta", attrs={attr: key})
    if isinstance(node, Tag):
        return node.get("content")
    return None


def _decode_data_layer(soup):
    for script in soup.find_all("script"):
        text = script.string or ""
        if "entityTaxonomy" in text or "entityBundle" in text:
            try:
                start = text.find("{")
                end = text.rfind("}") + 1
                return json.loads(text[start:end])
            except Exception:
                pass
    return {}


def _extract_body(soup):
    body = soup.select_one(BODY_SELECTOR)

    if isinstance(body, Tag):
        paragraphs = [
            normalize_text(p.get_text(" ", strip=True))
            for p in body.find_all("p")
            if p.get_text(strip=True)
        ]
        return (
            "\n".join(paragraphs),
            paragraphs,
            f"css:{BODY_SELECTOR}",
            1.0,
        )

    article = soup.select_one("article")

    if isinstance(article, Tag):
        paragraphs = [
            normalize_text(p.get_text(" ", strip=True))
            for p in article.find_all("p")
            if p.get_text(strip=True)
        ]
        return (
            "\n".join(paragraphs),
            paragraphs,
            "css:article",
            0.7,
        )

    return "", [], None, 0.0


_DASH_SPLIT_RE = re.compile(r"\s*[—–]\s*|\s+-\s+")


def _extract_dateline(paragraphs):
    if not paragraphs:
        return None
    first = paragraphs[0]
    parts = _DASH_SPLIT_RE.split(first, maxsplit=1)
    if len(parts) > 1:
        return normalize_text(parts[0])
    return None


def _extract_topic_fallback(node):
    if not isinstance(node, Tag):
        return None
    separators = node.find_all("i")
    if len(separators) < 2:
        return None
    tail_parts = []
    for sibling in separators[1].next_siblings:
        tail_parts.append(sibling.get_text() if isinstance(sibling, Tag) else str(sibling))
    return normalize_text("".join(tail_parts))


def _header_metadata(soup):
    meta_node = soup.select_one(".nr-meta")
    if not isinstance(meta_node, Tag):
        return None, None, None, None, None

    # Date is the text before the first <i> separator tag.
    parts_before_i = []
    for child in meta_node.children:
        if isinstance(child, Tag) and child.name == "i":
            break
        parts_before_i.append(child.get_text() if isinstance(child, Tag) else str(child))
    date_raw = normalize_text("".join(parts_before_i))

    city = None
    region = None
    region_code = None
    country = None

    locality_node = meta_node.select_one("span.locality")
    if isinstance(locality_node, Tag):
        city = normalize_text(locality_node.get_text(" ", strip=True))

    other_spans = [span for span in meta_node.find_all("span") if span is not locality_node]

    def _clean(text: str | None) -> str | None:
        if text is None:
            return None
        return normalize_text(text.lstrip(", ").strip())

    if len(other_spans) == 1:
        span = other_spans[0]
        classes = span.get("class") or []
        region_code = classes[0] if classes else None
        value = _clean(span.get_text(" ", strip=True))
        region = value
        country = value
    elif len(other_spans) >= 2:
        region_span, country_span = other_spans[0], other_spans[1]
        classes = region_span.get("class") or []
        region_code = classes[0] if classes else None
        region = _clean(region_span.get_text(" ", strip=True))
        country = _clean(country_span.get_text(" ", strip=True))

    return date_raw, city, region, region_code, country


def extract_image_urls(soup, base_url=None):
    urls = []

    for anchor in soup.select(".colorbox-image-grid a.colorbox"):
        href = anchor.get("href")
        if href:
            resolved = urljoin(base_url or "", href) if base_url else href
            if resolved not in urls:
                urls.append(resolved)

    for img in soup.select(".nr-body img"):
        src = img.get("src")
        if src:
            resolved = urljoin(base_url or "", src) if base_url else src
            if resolved not in urls:
                urls.append(resolved)

    return urls


def extract_tables(soup):
    tables = []
    for index, table in enumerate(soup.find_all("table")):
        headers = [normalize_text(th.get_text(" ", strip=True)) for th in table.select("thead th")]
        body = table.find("tbody") or table
        rows = []
        for tr in body.find_all("tr"):
            cells = [normalize_text(td.get_text(" ", strip=True)) for td in tr.find_all("td")]
            if cells:
                rows.append(cells)
        tables.append({"table_index": index, "headers": headers, "rows": rows})
    return tables
