from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from typing import Any


def _integer(row: dict[str, str], field: str, row_number: int) -> int:
    raw = row.get(field, "").strip()
    if not raw:
        raise ValueError(f"row {row_number}: {field} is blank")
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"row {row_number}: {field} must be an integer") from exc
    if value < 0:
        raise ValueError(f"row {row_number}: {field} cannot be negative")
    return value


def _layer_metrics(
    rows: list[dict[str, str]],
    *,
    candidate_field: str,
    false_positive_field: str,
    false_negative_field: str,
) -> dict[str, Any]:
    predicted = sum(int(row[candidate_field]) for row in rows)
    false_positives = sum(int(row[false_positive_field]) for row in rows)
    false_negatives = sum(int(row[false_negative_field]) for row in rows)
    if false_positives > predicted:
        raise ValueError(
            f"{false_positive_field} total ({false_positives}) exceeds candidate total ({predicted})"
        )
    true_positives = predicted - false_positives
    gold_total = true_positives + false_negatives
    precision = true_positives / predicted if predicted else 0.0
    recall = true_positives / gold_total if gold_total else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "predicted": predicted,
        "gold_total": gold_total,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def evaluate_audit(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("audit file has no labeled rows")

    integer_fields = (
        "event_candidates",
        "person_candidates",
        "event_false_positives",
        "event_false_negatives",
        "person_false_positives",
        "person_false_negatives",
    )
    normalized: list[dict[str, str]] = []
    seen_document_ids: set[str] = set()
    for row_number, row in enumerate(rows, start=2):
        document_id = row.get("document_id", "").strip()
        if not document_id:
            raise ValueError(f"row {row_number}: document_id is blank")
        if document_id in seen_document_ids:
            raise ValueError(f"row {row_number}: duplicate document_id {document_id}")
        seen_document_ids.add(document_id)
        reviewer = row.get("reviewer", "").strip()
        if not reviewer:
            raise ValueError(f"row {row_number}: reviewer is blank")
        release_label = row.get("is_press_release_gold", "").strip().casefold()
        if release_label not in {"yes", "no", "uncertain"}:
            raise ValueError(
                f"row {row_number}: is_press_release_gold must be yes, no, or uncertain"
            )
        clean = dict(row)
        for field in integer_fields:
            clean[field] = str(_integer(row, field, row_number))
        for candidate_field, false_positive_field in (
            ("event_candidates", "event_false_positives"),
            ("person_candidates", "person_false_positives"),
        ):
            if int(clean[false_positive_field]) > int(clean[candidate_field]):
                raise ValueError(
                    f"row {row_number}: {false_positive_field} exceeds "
                    f"{candidate_field}"
                )
        normalized.append(clean)

    release_counts: dict[str, int] = {"yes": 0, "no": 0, "uncertain": 0}
    selection_reasons: Counter[str] = Counter()
    for row in normalized:
        release_counts[row["is_press_release_gold"].strip().casefold()] += 1
        for reason in row.get("selection_reason", "").split(" | "):
            if reason:
                selection_reasons[reason] += 1
    return {
        "documents_reviewed": len(normalized),
        "reviewers": sorted({row["reviewer"].strip() for row in normalized}),
        "release_labels": release_counts,
        "selection_reason_counts": dict(sorted(selection_reasons.items())),
        "metric_scope": (
            "Unweighted, sample-descriptive micro metrics for this fixed purposive QA sample; "
            "not corpus estimates. No inferential confidence interval is reported because the "
            "sample includes certainty-selected challenge cases and candidates are clustered "
            "within documents."
        ),
        "events": _layer_metrics(
            normalized,
            candidate_field="event_candidates",
            false_positive_field="event_false_positives",
            false_negative_field="event_false_negatives",
        ),
        "people": _layer_metrics(
            normalized,
            candidate_field="person_candidates",
            false_positive_field="person_false_positives",
            false_negative_field="person_false_negatives",
        ),
    }
