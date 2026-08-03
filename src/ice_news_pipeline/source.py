from __future__ import annotations

import json
import re
import hashlib
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup

from ice_news_pipeline.constants import BODY_SELECTOR, TITLE_SELECTOR, FALLBACK_BODY_SELECTOR
from ice_news_pipeline.models import ICEDocument


def extract_datalayer(soup: BeautifulSoup) -> Dict[str, Any]:
    """Extract embedded JavaScript dataLayer JSON objects if present on the page."""
    for script in soup.find_all("script"):
        if script.string and "dataLayer" in script.string:
            try:
                match = re.search(r'dataLayer\s*=\s*(\[.*?\]);', script.string, re.DOTALL)
                if match:
                    data = json.loads(match.group(1))
                    return data[0] if isinstance(data, list) and data else {}
            except Exception:
                continue
    return {}


def extract_title(soup: BeautifulSoup, datalayer: Dict[str, Any]) -> str:
    """Extract page title following the extraction hierarchy: .nr-title h1 -> og:title -> h1 -> <title>."""
    nr_title = soup.select_one(TITLE_SELECTOR)
    if nr_title and nr_title.get_text(strip=True):
        return nr_title.get_text(strip=True)

    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        return str(og_title["content"]).strip()

    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(strip=True)

    if soup.title and soup.title.string:
        return soup.title.string.strip()

    return ""


def extract_topics(soup: BeautifulSoup, datalayer: Dict[str, Any]) -> List[str]:
    """Extract topics from dataLayer entityTaxonomy or fallback meta tags."""
    topics: List[str] = []

    if "entityTaxonomy" in datalayer and "news_release_topics" in datalayer["entityTaxonomy"]:
        raw_topics = datalayer["entityTaxonomy"]["news_release_topics"]
        if isinstance(raw_topics, dict):
            topics = list(raw_topics.values())
        elif isinstance(raw_topics, list):
            topics = [str(t) for t in raw_topics]

    if not topics:
        meta_node = soup.select_one(".nr-meta")
        if meta_node:
            text = meta_node.get_text(strip=True)
            if "Topics:" in text:
                topic_str = text.split("Topics:")[-1].strip()
                topics = [t.strip() for t in topic_str.split(",") if t.strip()]

    return topics


def extract_dates(soup: BeautifulSoup) -> tuple[Optional[str], Optional[str]]:
    """Extract published and modified dates from article meta tags."""
    pub_meta = soup.find("meta", property="article:published_time")
    pub_date = str(pub_meta["content"]).strip() if pub_meta and pub_meta.get("content") else None

    mod_meta = soup.find("meta", property="article:modified_time")
    mod_date = str(mod_meta["content"]).strip() if mod_meta and mod_meta.get("content") else None

    return pub_date, mod_date


def extract_body_and_dateline(soup: BeautifulSoup) -> tuple[str, Optional[str]]:
    """Targeted body text extraction from .nr-body (excluding nav/footers/scripts)."""
    body_node = soup.select_one(BODY_SELECTOR) or soup.select_one(FALLBACK_BODY_SELECTOR)

    if not body_node:
        body_node = soup.body if soup.body else soup

    for elem in body_node(["script", "style", "nav", "footer", "header", "noscript"]):
        elem.decompose()

    dateline = None
    first_p = body_node.find("p")
    if first_p:
        match = re.match(r"^([A-Z\s.,\–\-]+)\s*[\–\-—]\s*", first_p.get_text(strip=True))
        if match:
            dateline = match.group(1).strip()

    body_text = body_node.get_text(separator=" ", strip=True)
    body_text = re.sub(r'\s+', ' ', body_text).strip()

    return body_text, dateline


def extract_image_urls(soup: BeautifulSoup) -> List[str]:
    """Extract hero image links and in-body media anchors."""
    images = []
    hero_anchors = soup.select(".nr-body img, .hero-image img")
    for img in hero_anchors:
        src = img.get("src")
        if src:
            images.append(str(src))
    return list(set(images))


def parse_ice_html(raw_url: str, html_content: str) -> ICEDocument:
    """Main parsing pipeline function converting raw HTML into a structured ICEDocument."""
    soup = BeautifulSoup(html_content, "lxml")
    datalayer = extract_datalayer(soup)

    canonical_link = soup.find("link", rel="canonical")
    canonical_url = str(canonical_link["href"]) if canonical_link and canonical_link.get("href") else raw_url

    title = extract_title(soup, datalayer)
    published_date, modified_date = extract_dates(soup)
    topics = extract_topics(soup, datalayer)
    body_text, dateline = extract_body_and_dateline(soup)
    image_urls = extract_image_urls(soup)

    entity_bundle = datalayer.get("entityBundle", "")
    document_type = entity_bundle if entity_bundle else "news_release"

    word_count = len(body_text.split())

    return ICEDocument(
        url=raw_url,
        canonical_url=canonical_url,
        title=title,
        date_raw=published_date,
        published_date=published_date,
        modified_date=modified_date,
        topics=topics,
        dateline=dateline,
        full_text=body_text,
        body_text=body_text,
        word_count=word_count,
        image_urls=image_urls,
        document_type=document_type,
        is_quarantined=False,
        quarantine_reason=None
    )


# Алиас функции для тестов
extract_document = parse_ice_html
