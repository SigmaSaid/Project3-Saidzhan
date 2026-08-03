from __future__ import annotations

from typing import cast

import pandas as pd
import pytest

from ice_news_pipeline.audit import (
    EVENT_AUDIT_COLUMNS,
    PERSON_AUDIT_COLUMNS,
    build_candidate_audit_tables,
)
from ice_news_pipeline.models import EventCandidate, PersonCandidate


def _event(
    document_id: str,
    event_id: str,
    *,
    evidence: str = "Taylor was charged with fraud.",
) -> EventCandidate:
    return EventCandidate(
        event_id=event_id,
        document_id=document_id,
        action_type="charge",
        legal_stage="charged",
        count_min=1,
        count_max=1,
        count_qualifier="exact",
        evidence_text=evidence,
        evidence_start=17,
        evidence_end=17 + len(evidence),
        extraction_method="action_sentence_v1",
        confidence=0.91,
    )


def _person(document_id: str, mention_id: str) -> PersonCandidate:
    evidence = "Jordan Taylor, 32, of Reno, was charged with fraud."
    return PersonCandidate(
        mention_id=mention_id,
        document_id=document_id,
        name_raw="Jordan Taylor",
        age=32,
        residence_raw="Reno",
        origin_country_raw=None,
        evidence_text=evidence,
        evidence_start=5,
        evidence_end=5 + len(evidence),
        extraction_method="name_age_v1",
        confidence=0.84,
    )


def test_build_candidate_audit_tables_filters_and_preserves_review_context() -> None:
    audit_sample = pd.DataFrame(
        [
            {
                "document_id": "doc-b",
                "url": "https://example.test/b",
                "selection_reason": "multi_topic",
            },
            {
                "document_id": "doc-a",
                "url": "https://example.test/a",
                "selection_reason": "seeded_random",
            },
        ]
    )
    events = [
        _event("doc-a", "event-a"),
        _event("outside", "event-outside"),
        _event("doc-b", "event-b", evidence="Lee was sentenced to five years."),
    ]
    people = [_person("outside", "person-outside"), _person("doc-a", "person-a")]

    event_audit, person_audit = build_candidate_audit_tables(audit_sample, events, people)

    assert list(event_audit.columns) == list(EVENT_AUDIT_COLUMNS)
    assert event_audit["event_id"].tolist() == ["event-b", "event-a"]
    assert event_audit["url"].tolist() == [
        "https://example.test/b",
        "https://example.test/a",
    ]
    assert event_audit["selection_reason"].tolist() == ["multi_topic", "seeded_random"]
    assert event_audit.loc[0, "predicted_action_type"] == "charge"
    assert event_audit.loc[0, "predicted_legal_stage"] == "charged"
    assert event_audit.loc[0, "evidence_text"] == "Lee was sentenced to five years."
    evidence_start = cast(int, event_audit.loc[0, "evidence_start"])
    evidence_end = cast(int, event_audit.loc[0, "evidence_end"])
    evidence_text = cast(str, event_audit.loc[0, "evidence_text"])
    assert evidence_end - evidence_start == len(evidence_text)
    assert event_audit.loc[0, "is_true_positive_gold"] == ""
    assert event_audit.loc[0, "corrected_legal_stage_gold"] == ""

    assert list(person_audit.columns) == list(PERSON_AUDIT_COLUMNS)
    assert person_audit["mention_id"].tolist() == ["person-a"]
    assert person_audit.loc[0, "name_raw"] == "Jordan Taylor"
    assert person_audit.loc[0, "age"] == 32
    assert person_audit.loc[0, "role_gold"] == ""
    assert person_audit.loc[0, "related_event_id_gold"] == ""
    assert person_audit.loc[0, "reviewer"] == ""


def test_empty_candidate_audit_tables_keep_stable_headers() -> None:
    audit_sample = pd.DataFrame(columns=["document_id", "url", "selection_reason"])

    event_audit, person_audit = build_candidate_audit_tables(audit_sample, [], [])

    assert event_audit.empty
    assert person_audit.empty
    assert list(event_audit.columns) == list(EVENT_AUDIT_COLUMNS)
    assert list(person_audit.columns) == list(PERSON_AUDIT_COLUMNS)


def test_duplicate_audit_document_ids_are_rejected() -> None:
    audit_sample = pd.DataFrame(
        [
            {"document_id": "doc-a", "url": "https://example.test/a", "selection_reason": "oldest"},
            {"document_id": "doc-a", "url": "https://example.test/a", "selection_reason": "random"},
        ]
    )

    with pytest.raises(ValueError, match="document_id values must be unique: doc-a"):
        build_candidate_audit_tables(audit_sample, [], [])
