from __future__ import annotations

from pathlib import Path

import pytest

from ice_news_pipeline.evaluation import evaluate_audit


def test_evaluate_completed_audit(tmp_path: Path) -> None:
    audit = tmp_path / "audit.csv"
    audit.write_text(
        "document_id,is_press_release_gold,event_candidates,person_candidates,"
        "event_false_positives,event_false_negatives,"
        "person_false_positives,person_false_negatives,reviewer\n"
        "doc-a,yes,10,4,2,1,1,2,AB\n"
        "doc-b,yes,5,1,1,2,0,0,CD\n",
        encoding="utf-8",
    )
    result = evaluate_audit(audit)

    assert result["documents_reviewed"] == 2
    assert result["events"]["true_positives"] == 12
    assert result["events"]["precision"] == pytest.approx(0.8)
    assert result["events"]["recall"] == pytest.approx(0.8)
    assert result["events"]["f1"] == pytest.approx(0.8)
    assert result["people"]["true_positives"] == 4
    assert "not corpus estimates" in result["metric_scope"]
    assert "precision_wilson_95" not in result["events"]


def test_incomplete_audit_is_rejected(tmp_path: Path) -> None:
    audit = tmp_path / "audit.csv"
    audit.write_text(
        "document_id,is_press_release_gold,event_candidates,person_candidates,"
        "event_false_positives,event_false_negatives,"
        "person_false_positives,person_false_negatives,reviewer\n"
        "doc-a,yes,1,0,,0,0,0,AB\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="event_false_positives is blank"):
        evaluate_audit(audit)


def test_row_level_false_positive_invariant_is_enforced(tmp_path: Path) -> None:
    audit = tmp_path / "audit.csv"
    audit.write_text(
        "document_id,is_press_release_gold,event_candidates,person_candidates,"
        "event_false_positives,event_false_negatives,"
        "person_false_positives,person_false_negatives,reviewer\n"
        "doc-a,yes,0,0,2,0,0,0,AB\n"
        "doc-b,yes,3,0,0,0,0,0,CD\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="event_false_positives exceeds event_candidates"):
        evaluate_audit(audit)
