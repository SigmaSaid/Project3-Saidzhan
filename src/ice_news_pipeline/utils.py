from __future__ import annotations

import json
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup, PageElement, Tag

from ice_news_pipeline.constants import BODY_SELECTOR
from ice_news_pipeline.normalize import normalize_text

_TITLE_SUFFIX_RE = re.compile(r"\s*\|\s*U\.S\. Immigration and Customs Enforcement$")


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


def _meta_content(soup: BeautifulSoup, attr: str, key: str) -> str | None:
    node = soup.find("meta", attrs={attr: key})
    if isinstance(node, Tag):
        content = node.get("content")
        return content if isinstance(content, str) else None
    return None


def _decode_data_layer(soup: BeautifulSoup) -> dict[str, Any]:
    for script in soup.find_all("script"):
        text = script.string or ""
        if "entityTaxonomy" in text or "entityBundle" in text:
            try:
                start = text.find("{")
                end = text.rfind("}") + 1
                result: dict[str, Any] = json.loads(text[start:end])
                return result
            except Exception:
                pass
    return {}


def _extract_body(soup: BeautifulSoup) -> tuple[str, list[str], str | None, float]:
    body = soup.select_one(BODY_SELECTOR)

    if isinstance(body, Tag):
        paragraphs = [
            text
            for p in body.find_all("p")
            if p.get_text(strip=True)
            and (text := normalize_text(p.get_text(" ", strip=True))) is not None
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
            text
            for p in article.find_all("p")
            if p.get_text(strip=True)
            and (text := normalize_text(p.get_text(" ", strip=True))) is not None
        ]
        return (
            "\n".join(paragraphs),
            paragraphs,
            "css:article",
            0.7,
        )

    return "", [], None, 0.0


_DASH_SPLIT_RE = re.compile(r"\s*[—–]\s*|\s+-\s+")


def _extract_dateline(paragraphs: list[str]) -> str | None:
    if not paragraphs:
        return None
    first = paragraphs[0]
    parts = _DASH_SPLIT_RE.split(first, maxsplit=1)
    if len(parts) > 1:
        return normalize_text(parts[0])
    return None


def _extract_topic_fallback(node: PageElement | None) -> str | None:
    if not isinstance(node, Tag):
        return None
    separators = node.find_all("i")
    if len(separators) < 2:
        return None
    tail_parts = []
    for sibling in separators[1].next_siblings:
        tail_parts.append(sibling.get_text() if isinstance(sibling, Tag) else str(sibling))
    return normalize_text("".join(tail_parts))


def _header_metadata(
    soup: BeautifulSoup,
) -> tuple[str | None, str | None, str | None, str | None, str | None]:
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


def extract_image_urls(soup: BeautifulSoup, base_url: str | None = None) -> list[str]:
    urls: list[str] = []

    for anchor in soup.select(".colorbox-image-grid a.colorbox"):
        href = anchor.get("href")
        if isinstance(href, str):
            resolved = urljoin(base_url or "", href) if base_url else href
            if resolved not in urls:
                urls.append(resolved)

    for img in soup.select(".nr-body img"):
        src = img.get("src")
        if isinstance(src, str):
            resolved = urljoin(base_url or "", src) if base_url else src
            if resolved not in urls:
                urls.append(resolved)

    return urls


def extract_tables(soup: BeautifulSoup) -> list[dict[str, Any]]:
    tables = []
    for index, table in enumerate(soup.find_all("table")):
        headers = [
            text
            for th in table.select("thead th")
            if (text := normalize_text(th.get_text(" ", strip=True))) is not None
        ]
        body = table.find("tbody") or table
        rows = []
        for tr in body.find_all("tr"):
            cells = [
                text
                for td in tr.find_all("td")
                if (text := normalize_text(td.get_text(" ", strip=True))) is not None
            ]
            if cells:
                rows.append(cells)
        tables.append({"table_index": index, "headers": headers, "rows": rows})
    return tables
