from __future__ import annotations


from tests.conftest import reference_from_document

from ice_news_pipeline.claims import extract_event_candidates, extract_person_candidates
from ice_news_pipeline.extract import extract_document
from ice_news_pipeline.models import GateStatus
from ice_news_pipeline.validate import profile_reference, validate_pipeline


def test_validation_separates_completeness_from_validity(release_html: str) -> None:
    document = extract_document(
        {
            "url": "https://www.ice.gov/news/releases/carefully-documented-operation",
            "html": release_html,
        }
    )
    reference = reference_from_document(document)
    reference["date_last_updated"] = "Roberts updated his address with USCIS."
    profile = profile_reference([reference])

    assert profile["missing_counts"]["date_last_updated"] == 0
    assert profile["valid_modified_dates"] == 0
    assert len(profile["invalid_modified_examples"]) == 1


def test_validation_passes_contracts_and_warns_on_unlabeled_candidates(
    release_html: str,
) -> None:
    raw = {
        "url": "https://www.ice.gov/news/releases/carefully-documented-operation",
        "html": release_html,
    }
    document = extract_document(raw)
    events = extract_event_candidates(document)
    people = extract_person_candidates(document)
    result = validate_pipeline(
        [raw],
        [document],
        [reference_from_document(document)],
        events,
        people,
    )

    assert result.status is GateStatus.WARN
    assert all(gate.status is not GateStatus.FAIL for gate in result.gates)
    assert result.row_accounting == {
        "input": 1,
        "accepted": 1,
        "quarantined": 0,
        "events": len(events),
        "people": len(people),
    }
    assert result.document_profile["valid_published_dates"] == 1
    assert not result.issues


def test_core_gate_cannot_pass_when_extraction_coverage_is_zero(
    release_html: str,
) -> None:
    raw = {
        "url": "https://www.ice.gov/news/releases/carefully-documented-operation",
        "html": release_html,
    }
    document = extract_document(raw)
    reference = reference_from_document(document)
    document.topics = []

    result = validate_pipeline([raw], [document], [reference], [], [])
    topic_gate = next(
        gate for gate in result.gates if gate.name == "topics_reference_agreement"
    )

    assert topic_gate.status is GateStatus.FAIL
    assert "exact=0/1" in topic_gate.observed
    assert result.status is GateStatus.FAIL
