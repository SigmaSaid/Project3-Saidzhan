from __future__ import annotations

from collections import defaultdict
from typing import Final

import pandas as pd

from ice_news_pipeline.models import EventCandidate, PersonCandidate

AUDIT_SAMPLE_COLUMNS: Final[tuple[str, ...]] = (
    "document_id",
    "url",
    "selection_reason",
)

EVENT_AUDIT_COLUMNS: Final[tuple[str, ...]] = (
    "document_id",
    "url",
    "event_id",
    "predicted_action_type",
    "predicted_legal_stage",
    "count_min",
    "count_max",
    "count_qualifier",
    "evidence_start",
    "evidence_end",
    "evidence_text",
    "confidence",
    "selection_reason",
    "is_true_positive_gold",
    "corrected_action_type_gold",
    "corrected_legal_stage_gold",
    "corrected_count_min_gold",
    "corrected_count_max_gold",
    "corrected_count_qualifier_gold",
    "reviewer",
    "reviewer_notes",
)

PERSON_AUDIT_COLUMNS: Final[tuple[str, ...]] = (
    "document_id",
    "url",
    "mention_id",
    "name_raw",
    "age",
    "residence_raw",
    "origin_country_raw",
    "evidence_start",
    "evidence_end",
    "evidence_text",
    "confidence",
    "selection_reason",
    "is_true_positive_gold",
    "role_gold",
    "corrected_name_raw_gold",
    "corrected_age_gold",
    "corrected_residence_raw_gold",
    "corrected_origin_country_raw_gold",
    "related_event_id_gold",
    "related_action_type_gold",
    "related_legal_stage_gold",
    "reviewer",
    "reviewer_notes",
)


def _sample_lookup(audit_sample: pd.DataFrame) -> tuple[list[str], dict[str, tuple[str, str]]]:
    missing = sorted(set(AUDIT_SAMPLE_COLUMNS).difference(audit_sample.columns))
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"audit_sample is missing required columns: {joined}")
    if bool(audit_sample["document_id"].isna().any()):
        raise ValueError("audit_sample document_id values cannot be null")

    document_ids = [str(value) for value in audit_sample["document_id"].tolist()]
    duplicate_ids = sorted(
        {
            document_id
            for document_id, duplicate in zip(
                document_ids,
                pd.Series(document_ids).duplicated(keep=False).tolist(),
                strict=True,
            )
            if duplicate
        }
    )
    if duplicate_ids:
        joined = ", ".join(duplicate_ids)
        raise ValueError(f"audit_sample document_id values must be unique: {joined}")

    metadata: dict[str, tuple[str, str]] = {}
    for document_id, url, selection_reason in zip(
        document_ids,
        audit_sample["url"].tolist(),
        audit_sample["selection_reason"].tolist(),
        strict=True,
    ):
        metadata[document_id] = (
            "" if pd.isna(url) else str(url),
            "" if pd.isna(selection_reason) else str(selection_reason),
        )
    return document_ids, metadata


def build_candidate_audit_tables(
    audit_sample: pd.DataFrame,
    events: list[EventCandidate],
    people: list[PersonCandidate],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    document_ids, metadata = _sample_lookup(audit_sample)
    selected_ids = set(document_ids)

    events_by_document: defaultdict[str, list[EventCandidate]] = defaultdict(list)
    for event in events:
        if event.document_id in selected_ids:
            events_by_document[event.document_id].append(event)

    people_by_document: defaultdict[str, list[PersonCandidate]] = defaultdict(list)
    for person in people:
        if person.document_id in selected_ids:
            people_by_document[person.document_id].append(person)

    event_rows: list[dict[str, object]] = []
    person_rows: list[dict[str, object]] = []
    for document_id in document_ids:
        url, selection_reason = metadata[document_id]
        for event in events_by_document[document_id]:
            event_rows.append(
                {
                    "document_id": document_id,
                    "url": url,
                    "event_id": event.event_id,
                    "predicted_action_type": event.action_type,
                    "predicted_legal_stage": event.legal_stage,
                    "count_min": event.count_min,
                    "count_max": event.count_max,
                    "count_qualifier": event.count_qualifier,
                    "evidence_start": event.evidence_start,
                    "evidence_end": event.evidence_end,
                    "evidence_text": event.evidence_text,
                    "confidence": event.confidence,
                    "selection_reason": selection_reason,
                    "is_true_positive_gold": "",
                    "corrected_action_type_gold": "",
                    "corrected_legal_stage_gold": "",
                    "corrected_count_min_gold": "",
                    "corrected_count_max_gold": "",
                    "corrected_count_qualifier_gold": "",
                    "reviewer": "",
                    "reviewer_notes": "",
                }
            )

        for person in people_by_document[document_id]:
            person_rows.append(
                {
                    "document_id": document_id,
                    "url": url,
                    "mention_id": person.mention_id,
                    "name_raw": person.name_raw,
                    "age": person.age,
                    "residence_raw": person.residence_raw,
                    "origin_country_raw": person.origin_country_raw,
                    "evidence_start": person.evidence_start,
                    "evidence_end": person.evidence_end,
                    "evidence_text": person.evidence_text,
                    "confidence": person.confidence,
                    "selection_reason": selection_reason,
                    "is_true_positive_gold": "",
                    "role_gold": "",
                    "corrected_name_raw_gold": "",
                    "corrected_age_gold": "",
                    "corrected_residence_raw_gold": "",
                    "corrected_origin_country_raw_gold": "",
                    "related_event_id_gold": "",
                    "related_action_type_gold": "",
                    "related_legal_stage_gold": "",
                    "reviewer": "",
                    "reviewer_notes": "",
                }
            )

    return (
        pd.DataFrame(event_rows, columns=EVENT_AUDIT_COLUMNS),
        pd.DataFrame(person_rows, columns=PERSON_AUDIT_COLUMNS),
    )
