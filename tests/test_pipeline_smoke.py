from __future__ import annotations

from pathlib import Path

from ice_news_pipeline.extract import extract_document
from ice_news_pipeline.pipeline import run_pipeline
from ice_news_pipeline.source import LoadedInputs
from tests.conftest import reference_from_document


def test_offline_pipeline_writes_auditable_artifacts(
    tmp_path: Path,
    release_html: str,
) -> None:
    raw = {
        "url": "https://www.ice.gov/news/releases/carefully-documented-operation",
        "html": release_html,
    }
    reference = reference_from_document(extract_document(raw))
    loaded = LoadedInputs(
        raw=[raw],
        reference=[reference],
        metadata={
            "source": "test",
            "dataset_id": "fixture",
            "revision": "fixture-revision",
            "split": "train",
        },
    )
    output_dir = tmp_path / "outputs"
    report_dir = tmp_path / "reports"
    run = run_pipeline(
        loaded,
        output_dir=output_dir,
        report_dir=report_dir,
        figures=False,
        audit_size=1,
    )

    assert run.validation.row_accounting["accepted"] == 1
    assert (output_dir / "documents.jsonl").is_file()
    assert (output_dir / "documents.parquet").is_file()
    assert (output_dir / "validation.json").is_file()
    assert (report_dir / "VALIDATION_REPORT.md").is_file()
    assert (report_dir / "FINDINGS.md").is_file()
    assert (report_dir / "audit_sample.csv").is_file()
    assert (report_dir / "event_candidate_audit.csv").is_file()
    assert (report_dir / "person_candidate_audit.csv").is_file()

    report = (report_dir / "VALIDATION_REPORT.md").read_text(encoding="utf-8")
    assert "PASS WITH WARNINGS" in report
    assert "populated" in report


def test_all_quarantined_run_writes_fail_safe_reports(
    tmp_path: Path,
    social_html: str,
) -> None:
    raw = {
        "url": "https://www.ice.gov/news/releases/social",
        "html": social_html,
    }
    reference = reference_from_document(extract_document(raw))
    run = run_pipeline(
        LoadedInputs(
            raw=[raw],
            reference=[reference],
            metadata={"source": "test", "revision": "fixture", "split": "train"},
        ),
        output_dir=tmp_path / "outputs",
        report_dir=tmp_path / "reports",
        figures=False,
        audit_size=1,
    )

    findings = (tmp_path / "reports" / "FINDINGS.md").read_text(encoding="utf-8")
    validation = (tmp_path / "reports" / "VALIDATION_REPORT.md").read_text(encoding="utf-8")
    assert run.validation.status.value == "fail"
    assert "Descriptive findings withheld" in findings
    assert "NOT READY" in validation


def test_zero_topic_run_does_not_divide_by_zero(
    tmp_path: Path,
    release_html: str,
) -> None:
    no_topic_html = release_html.replace(
        '"news_release_topics":{"1":"Firearms, Ammunition and Explosives",'
        '"2":"Enforcement and Removal"}',
        '"news_release_topics":{}',
    ).replace(
        "</span><i></i>Firearms, Ammunition and Explosives, Enforcement and Removal",
        "</span><i></i>",
    )
    raw = {
        "url": "https://www.ice.gov/news/releases/carefully-documented-operation",
        "html": no_topic_html,
    }
    reference = reference_from_document(extract_document(raw))

    run_pipeline(
        LoadedInputs(
            raw=[raw],
            reference=[reference],
            metadata={"source": "test", "revision": "fixture", "split": "train"},
        ),
        output_dir=tmp_path / "outputs",
        report_dir=tmp_path / "reports",
        figures=False,
        audit_size=1,
    )

    findings = (tmp_path / "reports" / "FINDINGS.md").read_text(encoding="utf-8")
    assert "Documents with known topics: 0" in findings
    assert "Multi-topic documents: 0/0 (0.00%)" in findings


def test_failed_gate_with_accepted_rows_withholds_findings(
    tmp_path: Path,
    release_html: str,
) -> None:
    no_topic_html = release_html.replace(
        '"news_release_topics":{"1":"Firearms, Ammunition and Explosives",'
        '"2":"Enforcement and Removal"}',
        '"news_release_topics":{}',
    ).replace(
        "</span><i></i>Firearms, Ammunition and Explosives, Enforcement and Removal",
        "</span><i></i>",
    )
    raw = {
        "url": "https://www.ice.gov/news/releases/carefully-documented-operation",
        "html": no_topic_html,
    }
    reference = reference_from_document(extract_document(raw))
    reference["topics"] = "Enforcement and Removal"

    run = run_pipeline(
        LoadedInputs(
            raw=[raw],
            reference=[reference],
            metadata={"source": "test", "revision": "fixture", "split": "train"},
        ),
        output_dir=tmp_path / "outputs",
        report_dir=tmp_path / "reports",
        figures=False,
        audit_size=1,
    )

    findings = (tmp_path / "reports" / "FINDINGS.md").read_text(encoding="utf-8")
    assert run.validation.status.value == "fail"
    assert "Descriptive findings withheld" in findings
    assert "`topics_reference_agreement`" in findings
