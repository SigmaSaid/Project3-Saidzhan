from __future__ import annotations

from dataclasses import replace

from ice_news_pipeline.claims import extract_event_candidates, extract_person_candidates
from ice_news_pipeline.extract import extract_document


def test_event_candidates_preserve_stage_qualifier_and_offsets(release_html: str) -> None:
    document = extract_document(
        {
            "url": "https://www.ice.gov/news/releases/carefully-documented-operation",
            "html": release_html,
        }
    )
    candidates = extract_event_candidates(document)

    arrest = next(candidate for candidate in candidates if candidate.action_type == "arrest")
    assert arrest.count_min == 12
    assert arrest.count_max is None
    assert arrest.count_qualifier == "more_than"
    assert document.body_text is not None
    assert document.body_text[arrest.evidence_start : arrest.evidence_end] == arrest.evidence_text

    charge = next(candidate for candidate in candidates if candidate.action_type == "charge")
    sentence = next(candidate for candidate in candidates if candidate.action_type == "sentence")
    conviction = next(
        candidate for candidate in candidates if candidate.action_type == "conviction"
    )
    assert charge.legal_stage == "charged"
    assert sentence.legal_stage == "sentenced"
    assert conviction.legal_stage == "convicted"


def test_event_counts_are_bound_to_concrete_action_mentions(release_html: str) -> None:
    document = extract_document(
        {
            "url": "https://www.ice.gov/news/releases/carefully-documented-operation",
            "html": release_html,
        }
    )
    body = (
        "ICE arrested 10 people and removed 5 people. "
        "Later, ICE arrested 3 people and arrested 2 people."
    )
    document = replace(document, body_text=body, paragraphs=[body])

    candidates = extract_event_candidates(document)
    arrests = [candidate for candidate in candidates if candidate.action_type == "arrest"]
    removals = [candidate for candidate in candidates if candidate.action_type == "removal"]

    assert [candidate.count_min for candidate in arrests] == [10, 3, 2]
    assert [candidate.count_min for candidate in removals] == [5]
    assert all(candidate.count_min == candidate.count_max for candidate in candidates)
    assert all(candidate.extraction_method == "rule:action_mention_v2" for candidate in candidates)
    assert document.body_text is not None
    for candidate in candidates:
        assert (
            document.body_text[candidate.evidence_start : candidate.evidence_end]
            == candidate.evidence_text
        )


def test_ambiguous_action_does_not_borrow_another_actions_count(release_html: str) -> None:
    document = extract_document(
        {
            "url": "https://www.ice.gov/news/releases/carefully-documented-operation",
            "html": release_html,
        }
    )
    body = "ICE arrested and removed 5 people."
    document = replace(document, body_text=body, paragraphs=[body])

    candidates = {
        candidate.action_type: candidate for candidate in extract_event_candidates(document)
    }

    assert candidates["arrest"].count_min is None
    assert candidates["arrest"].count_max is None
    assert candidates["arrest"].confidence == 0.72
    assert candidates["removal"].count_min == 5
    assert candidates["removal"].count_max == 5
    assert candidates["removal"].confidence == 0.86


def test_count_before_action_preserves_explicit_range(release_html: str) -> None:
    document = extract_document(
        {
            "url": "https://www.ice.gov/news/releases/carefully-documented-operation",
            "html": release_html,
        }
    )
    body = "Between 10 and 12 people were arrested."
    document = replace(document, body_text=body, paragraphs=[body])

    arrest = extract_event_candidates(document)[0]

    assert arrest.action_type == "arrest"
    assert arrest.count_min == 10
    assert arrest.count_max == 12
    assert arrest.count_qualifier == "range"


def test_person_candidates_only_use_explicit_name_and_age(release_html: str) -> None:
    document = extract_document(
        {
            "url": "https://www.ice.gov/news/releases/carefully-documented-operation",
            "html": release_html,
        }
    )
    candidates = extract_person_candidates(document)
    by_name = {candidate.name_raw: candidate for candidate in candidates}

    assert by_name["Maria Elena Lopez"].age == 34
    assert by_name["Maria Elena Lopez"].origin_country_raw == "Mexico"
    assert by_name["John Doe"].age == 41
    assert by_name["John Doe"].residence_raw == "Dallas"
    for candidate in candidates:
        assert document.body_text is not None
        assert (
            document.body_text[candidate.evidence_start : candidate.evidence_end]
            == candidate.evidence_text
        )
