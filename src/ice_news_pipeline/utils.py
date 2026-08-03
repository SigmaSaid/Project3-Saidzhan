import re

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
