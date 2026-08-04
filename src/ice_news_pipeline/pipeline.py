"""End-to-end orchestration and artifact writing."""

from __future__ import annotations

import importlib.metadata
import json
import platform
import sys
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import pandas as pd

from ice_news_pipeline import __version__
from ice_news_pipeline.analyze import build_analysis_tables, write_figures
from ice_news_pipeline.audit import build_candidate_audit_tables
from ice_news_pipeline.claims import extract_event_candidates, extract_person_candidates
from ice_news_pipeline.constants import PARSER_VERSION
from ice_news_pipeline.extract import extract_documents
from ice_news_pipeline.models import (
    DocumentRecord,
    EventCandidate,
    GateStatus,
    PersonCandidate,
    ValidationResult,
)
from ice_news_pipeline.report import (
    build_audit_sample,
    write_findings_report,
    write_validation_report,
)
from ice_news_pipeline.source import LoadedInputs
from ice_news_pipeline.validate import validate_pipeline


@dataclass(slots=True)
class PipelineRun:
    documents: list[DocumentRecord]
    events: list[EventCandidate]
    people: list[PersonCandidate]
    validation: ValidationResult
    manifest: dict[str, Any]
    output_dir: Path
    report_dir: Path


class TechnicalPipelineEncoder(json.JSONEncoder):
    """Robust JSON encoder supporting datetimes, paths, and enums."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, (datetime, Path)):
            return str(obj)
        if isinstance(obj, Enum):
            return obj.value
        return super().default(obj)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        cls=TechnicalPipelineEncoder,
    )
    path.write_text(f"{content}\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            line = json.dumps(
                row,
                ensure_ascii=False,
                sort_keys=True,
                cls=TechnicalPipelineEncoder,
            )
            handle.write(f"{line}\n")


def _flatten_document_dicts(doc_dicts: list[dict[str, Any]]) -> pd.DataFrame:
    """Flatten nested lists/dicts inside serialized DocumentRecord dictionaries."""
    rows: list[dict[str, Any]] = []
    nested_fields = {
        "topics",
        "paragraphs",
        "tables",
        "image_urls",
        "quality_flags",
        "field_provenance",
        "field_confidence",
    }
    
    for original_row in doc_dicts:
        row = original_row.copy()
        for field in nested_fields:
            if field in row:
                row[f"{field}_json"] = json.dumps(
                    row.pop(field),
                    ensure_ascii=False,
                    sort_keys=True,
                    cls=TechnicalPipelineEncoder,
                )
        rows.append(row)

    df = pd.DataFrame(rows)
    if "input_url" in df.columns:
        df = df.sort_values("input_url").reset_index(drop=True)
    return df


def _dependency_versions() -> dict[str, str]:
    packages = ("beautifulsoup4", "datasets", "lxml", "matplotlib", "pandas", "pyarrow")
    versions: dict[str, str] = {}
    for pkg in packages:
        try:
            versions[pkg] = importlib.metadata.version(pkg)
        except Exception:
            versions[pkg] = "not installed"
    return versions


def _flag_duplicate_source_html(documents: list[DocumentRecord]) -> None:
    by_hash: dict[str, list[DocumentRecord]] = {}
    for document in documents:
        if document.source_sha256 is None:
            continue
        by_hash.setdefault(document.source_sha256, []).append(document)
        
    for matching in by_hash.values():
        if len(matching) < 2:
            continue
        for document in matching:
            document.quality_flags = sorted(
                {*document.quality_flags, "duplicate_source_html"}
            )


def _write_artifacts(
    run: PipelineRun,
    analysis_tables: dict[str, pd.DataFrame],
    audit_sample: pd.DataFrame,
    *,
    figures: bool,
) -> None:
    output_dir, report_dir = run.output_dir, run.report_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    table_dir = report_dir / "tables"
    table_dir.mkdir(parents=True, exist_ok=True)

    doc_dicts = [doc.to_dict() for doc in run.documents]
    event_dicts = [event.to_dict() for event in run.events]
    person_dicts = [person.to_dict() for person in run.people]
    flat_documents = _flatten_document_dicts(doc_dicts)

    event_audit, person_audit = build_candidate_audit_tables(
        audit_sample,
        run.events,
        run.people,
    )

    with ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(_write_jsonl, output_dir / "documents.jsonl", doc_dicts),
            executor.submit(_write_jsonl, output_dir / "event_candidates.jsonl", event_dicts),
            executor.submit(_write_jsonl, output_dir / "person_candidates.jsonl", person_dicts),
            executor.submit(flat_documents.to_csv, output_dir / "documents.csv", index=False),
            executor.submit(flat_documents.to_parquet, output_dir / "documents.parquet", index=False),
            executor.submit(_write_json, output_dir / "validation.json", run.validation.to_dict()),
            executor.submit(_write_json, output_dir / "run_manifest.json", run.manifest),
            executor.submit(_write_json, report_dir / "validation.json", run.validation.to_dict()),
            executor.submit(_write_json, report_dir / "run_manifest.json", run.manifest),
            executor.submit(
                pd.DataFrame(run.validation.issues).to_csv,
                table_dir / "validation_issues.csv",
                index=False,
            ),
            executor.submit(audit_sample.to_csv, report_dir / "audit_sample.csv", index=False),
            executor.submit(event_audit.to_csv, report_dir / "event_candidate_audit.csv", index=False),
            executor.submit(person_audit.to_csv, report_dir / "person_candidate_audit.csv", index=False),
        ]

        for name, table in analysis_tables.items():
            futures.append(executor.submit(table.to_csv, table_dir / f"{name}.csv", index=False))

        for future in futures:
            future.result()

    write_validation_report(
        report_dir / "VALIDATION_REPORT.md",
        run.validation,
        run.documents,
        run.manifest["source"],
    )
    write_findings_report(report_dir / "FINDINGS.md", analysis_tables, run.validation)
    
    if figures:
        write_figures(analysis_tables, report_dir / "figures")


def run_pipeline(
    loaded: LoadedInputs,
    *,
    output_dir: Path,
    report_dir: Path,
    workers: int = 1,
    extract_candidates: bool = True,
    audit_size: int = 30,
    audit_seed: int = 20260729,
    figures: bool = True,
) -> PipelineRun:
    raw_rows = [dict(row) for row in loaded.raw]

    documents = list(extract_documents(raw_rows, workers=workers))

    _flag_duplicate_source_html(documents)
    
    accepted = [doc for doc in documents if doc.parse_status.value == "accepted"]

    events: list[EventCandidate] = []
    people: list[PersonCandidate] = []
    if extract_candidates:
        for document in accepted:
            events.extend(extract_event_candidates(document))
            people.extend(extract_person_candidates(document))

    validation = validate_pipeline(raw_rows, documents, loaded.reference, events, people)
    analysis_tables = build_analysis_tables(documents)
    audit_sample = build_audit_sample(
        documents,
        events,
        people,
        size=audit_size,
        seed=audit_seed,
    )

    manifest = {
        "pipeline_version": __version__,
        "parser_version": PARSER_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": loaded.metadata,
        "runtime": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "dependencies": _dependency_versions(),
        },
        "parameters": {
            "workers": workers,
            "extract_candidates": extract_candidates,
            "audit_size": audit_size,
            "audit_seed": audit_seed,
        },
        "result": {
            "status": validation.status.value,
            **validation.row_accounting,
        },
    }

    run = PipelineRun(
        documents=documents,
        events=events,
        people=people,
        validation=validation,
        manifest=manifest,
        output_dir=output_dir,
        report_dir=report_dir,
    )
    
    _write_artifacts(run, analysis_tables, audit_sample, figures=figures)
    return run


def exit_code(run: PipelineRun, *, fail_on_warning: bool = False) -> int:
    if run.validation.status is GateStatus.FAIL:
        return 1
    if fail_on_warning and run.validation.status is GateStatus.WARN:
        return 2
    return 0
