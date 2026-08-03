import re
import json
from bs4 import BeautifulSoup, Tag

from ice_news_pipeline.constants import BODY_SELECTOR
from ice_news_pipeline.normalize import (
    iso_date,
    normalize_text,
    normalize_url,
    tokens,
)

_TITLE_SUFFIX_RE = re.compile(
    r"\s*\|\s*U\.S\. Immigration and Customs Enforcement$"
)


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


def _extract_dateline(paragraphs):
    if paragraphs:
        return paragraphs[0]
    return None


def _extract_topic_fallback(node):
    if isinstance(node, Tag):
        return normalize_text(node.get_text(" ", strip=True))
    return None


def _header_metadata(soup):
    return None, None, None, None, None


def extract_image_urls(soup, base_url=None):
    urls = []
    for img in soup.find_all("img"):
        src = img.get("src")
        if src:
            urls.append(src)
    return urls


def extract_tables(soup):
    tables = []
    for table in soup.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            rows.append(
                [
                    normalize_text(td.get_text(" ", strip=True))
                    for td in tr.find_all(["td", "th"])
                ]
            )
        tables.append({"rows": rows})
    return tables
