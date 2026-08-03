from __future__ import annotations

from ice_news_pipeline.normalize import (
    is_missing,
    iso_date,
    normalize_text,
    normalize_url,
    token_f1,
)


def test_missing_sentinel_is_not_a_real_value() -> None:
    assert is_missing("not found")
    assert is_missing(" NOT FOUND ")
    assert normalize_text("not found") is None
    assert not is_missing("A real finding")


def test_text_and_url_normalization_are_deterministic() -> None:
    assert normalize_text("  one\xa0  two \n three  ") == "one two three"
    assert normalize_text(" one \n\n two ", preserve_lines=True) == "one\ntwo"
    assert (
        normalize_url("HTTPS://WWW.ICE.GOV/news/releases/example/#fragment")
        == "https://www.ice.gov/news/releases/example"
    )


def test_date_normalization_accepts_source_formats() -> None:
    assert iso_date("02/03/2025") == "2025-02-03"
    assert iso_date("February 3, 2025") == "2025-02-03"
    assert iso_date("2025-02-03T10:30:00-05:00") == "2025-02-03"
    assert iso_date("Roberts updated his address.") is None


def test_token_f1_quantifies_near_matches() -> None:
    assert token_f1("one two three", "one two three") == 1.0
    assert 0.0 < token_f1("one two three", "one two") < 1.0
    assert token_f1("", "one") == 0.0
