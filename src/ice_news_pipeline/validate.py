
from __future__ import annotations

import hashlib
import json
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterable
from difflib import SequenceMatcher
from typing import Any

from ice_news_pipeline.constants import REQUIRED_REFERENCE_FIELDS, US_REGION_CODES
from ice_news_pipeline.models import (
    DocumentRecord,
    EventCandidate,
    FieldMetric,
    GateStatus,
    PersonCandidate,
    ValidationGate,
    ValidationResult,
)
from ice_news_pipeline.normalize import (
    is_missing,
    iso_date,
    normalize_for_match,
    normalize_url,
    parse_date,
    token_f1,
)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _reference_sha256(reference: list[dict[str, Any]]) -> str:
    payload = "\n".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, default=str) for row in reference
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def profile_reference(reference: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(reference)
    missing: dict[str, int] = {}
    for field in REQUIRED_REFERENCE_FIELDS:
        missing[field] = sum(is_missing(row.get(field)) for row in reference)

    invalid_modified: list[dict[str, Any]] = []
    invalid_published: list[dict[str, Any]] = []
    lags: list[int] = []
    years: Counter[str] = Counter()
    for row in reference:
        published = parse_date(row.get("date_normalized"))
        modified = parse_date(row.get("date_last_updated"))
        if published is None and not is_missing(row.get("date_normalized")):
            invalid_published.append({"url": row.get("url"), "value": row.get("date_normalized")})
        if modified is None and not is_missing(row.get("date_last_updated")):
            invalid_modified.append(
                {"url": row.get("url"), "value": row.get("date_last_updated")}
            )
        if published:
            years[str(published.year)] += 1
        else:
            years["unknown"] += 1
        if published and modified:
            lags.append((modified - published).days)

    urls = [normalize_url(row.get("url")) for row in reference]
    titles: defaultdict[str, list[str]] = defaultdict(list)
    for row in reference:
        title = normalize_for_match(row.get("title"))
        if title:
            titles[title].append(str(row.get("url")))
    duplicate_titles = [
        {"title": title, "urls": urls_for_title}
        for title, urls_for_title in titles.items()
        if len(urls_for_title) > 1
    ]
    non_us_region_labels = sorted(
        {
            str(row.get("state"))
            for row in reference
            if not is_missing(row.get("state")) and str(row.get("state")) not in US_REGION_CODES
        }
    )

    lag_summary: dict[str, float | int] = {
        "valid_pairs": len(lags),
        "negative": sum(value < 0 for value in lags),
        "same_day": sum(value == 0 for value in lags),
        "median_days": statistics.median(lags) if lags else 0.0,
        "p95_days": round(_percentile([float(value) for value in lags], 0.95), 2),
        "max_days": max(lags) if lags else 0,
    }
    return {
        "rows": total,
        "sha256": _reference_sha256(reference),
        "unique_urls": len({url for url in urls if url}),
        "missing_counts": missing,
        "valid_published_dates": total - missing["date_normalized"] - len(invalid_published),
        "valid_modified_dates": total - missing["date_last_updated"] - len(invalid_modified),
        "invalid_published_count": len(invalid_published),
        "invalid_modified_count": len(invalid_modified),
        "invalid_published_examples": invalid_published[:10],
        "invalid_modified_examples": invalid_modified[:10],
        "year_counts": dict(sorted(years.items())),
        "duplicate_title_groups": duplicate_titles,
        "non_us_region_labels": non_us_region_labels,
        "modification_lag": lag_summary,
    }


def profile_documents(documents: list[DocumentRecord]) -> dict[str, Any]:
    accepted = [
        doc for doc in documents 
        if (getattr(doc.parse_status, "value", str(doc.parse_status)) == "accepted")
    ]
    published_dates = [
        parsed
        for document in accepted
        if (parsed := parse_date(document.published_date)) is not None
    ]
    modified_dates = [
        parsed
        for document in accepted
        if (parsed := parse_date(document.modified_date)) is not None
    ]
    lags: list[int] = []
    for document in accepted:
        published = parse_date(document.published_date)
        modified = parse_date(document.modified_date)
        if published and modified:
            lags.append((modified - published).days)
    lag_summary: dict[str, float | int] = {
        "valid_pairs": len(lags),
        "negative": sum(value < 0 for value in lags),
        "same_day": sum(value == 0 for value in lags),
        "median_days": statistics.median(lags) if lags else 0.0,
        "p95_days": round(_percentile([float(value) for value in lags], 0.95), 2),
        "max_days": max(lags) if lags else 0,
    }
    return {
        "accepted_rows": len(accepted),
        "valid_published_dates": len(published_dates),
        "valid_modified_dates": len(modified_dates),
        "raw_datelines_present": sum(getattr(doc, "dateline_raw", getattr(doc, "dateline", None)) is not None for doc in accepted),
        "dateline_regions_present": sum(
            getattr(doc, "dateline_region", None) is not None for doc in accepted
        ),
        "published_date_start": min(published_dates).isoformat() if published_dates else None,
        "published_date_end": max(published_dates).isoformat() if published_dates else None,
        "modification_lag": lag_summary,
    }


def _reference_value(field: str, row: dict[str, Any]) -> Any:
    if field == "published_date":
        return iso_date(row.get("date_normalized"))
    if field == "modified_date":
        return iso_date(row.get("date_last_updated"))
    return row.get(
        {
            "dateline_raw": "location_full_text",
            "dateline_city": "city",
            "dateline_region": "state",
            "body_text": "full_text",
        }.get(field, field)
    )


def _document_value(field: str, document: DocumentRecord) -> Any:
    if field == "topics":
        return ", ".join(document.topics) if document.topics else None
    if field == "image_urls":
        return "; ".join(document.image_urls) if document.image_urls else None
    if field == "dateline_raw":
        return getattr(document, "dateline_raw", getattr(document, "dateline", None))
    return getattr(document, field, None)


def _field_metric(
    field: str,
    documents_by_url: dict[str, DocumentRecord],
    reference_by_url: dict[str, dict[str, Any]],
) -> FieldMetric:
    reference_present = 0
    extracted_present = 0
    both_present = 0
    exact_matches = 0
    false_positives = 0
    for url, row in reference_by_url.items():
        document = documents_by_url.get(url)
        reference_value = _reference_value(field, row)
        document_value = _document_value(field, document) if document else None
        reference_normalized = normalize_for_match(reference_value)
        document_normalized = normalize_for_match(document_value)
        if reference_normalized is not None:
            reference_present += 1
        if document_normalized is not None:
            extracted_present += 1
        if reference_normalized is not None and document_normalized is not None:
            both_present += 1
            if reference_normalized == document_normalized:
                exact_matches += 1
        elif reference_normalized is None and document_normalized is not None:
            false_positives += 1
    coverage = both_present / reference_present if reference_present else 1.0
    agreement = exact_matches / both_present if both_present else 1.0
    return FieldMetric(
        field=field,
        reference_present=reference_present,
        extracted_present=extracted_present,
        both_present=both_present,
        exact_matches=exact_matches,
        false_positives=false_positives,
        coverage=coverage,
        agreement=agreement,
    )


def _body_similarity(
    documents_by_url: dict[str, DocumentRecord],
    reference_by_url: dict[str, dict[str, Any]],
) -> dict[str, float | int]:
    scores: list[float] = []
    exact = 0
    for url, row in reference_by_url.items():
        document = documents_by_url.get(url)
        reference_body = _reference_value("body_text", row)
        extracted_body = document.body_text if document else None
        if is_missing(reference_body) or is_missing(extracted_body):
            continue
        score = token_f1(reference_body, extracted_body)
        scores.append(score)
        if normalize_for_match(reference_body) == normalize_for_match(extracted_body):
            exact += 1
    return {
        "compared": len(scores),
        "exact_matches": exact,
        "exact_rate": exact / len(scores) if scores else 0.0,
        "below_0_90": sum(score < 0.90 for score in scores),
        "below_0_95": sum(score < 0.95 for score in scores),
        "mean_token_f1": statistics.fmean(scores) if scores else 0.0,
        "median_token_f1": statistics.median(scores) if scores else 0.0,
        "p05_token_f1": _percentile(scores, 0.05),
        "minimum_token_f1": min(scores) if scores else 0.0,
    }


def _comparison_issues(
    fields: tuple[str, ...],
    documents_by_url: dict[str, DocumentRecord],
    reference_by_url: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for url, row in reference_by_url.items():
        document = documents_by_url.get(url)
        for field in fields:
            reference_value = _reference_value(field, row)
            document_value = _document_value(field, document) if document else None
            reference_normalized = normalize_for_match(reference_value)
            document_normalized = normalize_for_match(document_value)
            if reference_normalized == document_normalized:
                continue
            issue: dict[str, Any] = {
                "type": "silver_reference_mismatch",
                "severity": "review",
                "field": field,
                "url": url,
                "reference_present": reference_normalized is not None,
                "extracted_present": document_normalized is not None,
                "reference_preview": str(reference_value)[:240],
                "extracted_preview": str(document_value)[:240],
                "review_status": "",
                "adjudication": "",
                "reviewer": "",
                "review_notes": "",
            }
            if field == "body_text":
                issue["token_f1"] = token_f1(reference_value, document_value)
                reference_text = str(reference_value)
                extracted_text = str(document_value)
                reference_tokens = reference_text.split()
                extracted_tokens = extracted_text.split()
                issue["reference_characters"] = len(reference_text)
                issue["extracted_characters"] = len(extracted_text)
                issue["reference_tokens"] = len(reference_tokens)
                issue["extracted_tokens"] = len(extracted_tokens)
                issue["difference_context"] = _difference_context(
                    reference_tokens,
                    extracted_tokens,
                )
            issues.append(issue)
    return issues


def _difference_context(reference_tokens: list[str], extracted_tokens: list[str]) -> str:
    def snippet(tokens: list[str], start: int, end: int) -> str:
        before = tokens[max(0, start - 8) : start]
        changed = tokens[start : min(end, start + 20)]
        after = tokens[end : min(len(tokens), end + 8)]
        omitted = max(0, end - start - len(changed))
        parts = [*before, *changed]
        if omitted:
            parts.append(f"[… {omitted} changed tokens omitted …]")
        parts.extend(after)
        return " ".join(parts)

    matcher = SequenceMatcher(a=reference_tokens, b=extracted_tokens, autojunk=False)
    for tag, ref_start, ref_end, ext_start, ext_end in matcher.get_opcodes():
        if tag == "equal":
            continue
        ref_context = snippet(reference_tokens, ref_start, ref_end)
        ext_context = snippet(extracted_tokens, ext_start, ext_end)
        return (
            f"{tag} at reference tokens {ref_start}:{ref_end}, "
            f"DOM tokens {ext_start}:{ext_end}; "
            f"reference context: {ref_context!r}; DOM context: {ext_context!r}"
        )
    return "values differ only after normalization"


def _candidate_offset_issues(
    documents: dict[str, DocumentRecord],
    candidates: Iterable[EventCandidate | PersonCandidate],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for candidate in candidates:
        document = documents.get(candidate.document_id)
        body = document.body_text if document else None
        valid = (
            body is not None
            and 0 <= candidate.evidence_start <= candidate.evidence_end <= len(body)
            and body[candidate.evidence_start : candidate.evidence_end] == candidate.evidence_text
        )
        if not valid:
            candidate_id = (
                candidate.event_id if isinstance(candidate, EventCandidate) else candidate.mention_id
            )
            issues.append(
                {
                    "type": "invalid_evidence_offset",
                    "candidate_id": candidate_id,
                    "document_id": candidate.document_id,
                }
            )
    return issues


def _make_gate(
    name: str,
    status: GateStatus,
    observed: str,
    requirement: str,
    detail: str,
) -> ValidationGate:
    return ValidationGate(
        name=name,
        status=status,
        observed=observed,
        requirement=requirement,
        detail=detail,
    )


def _threshold_gate(
    name: str,
    value: float,
    threshold: float,
    *,
    detail: str,
) -> ValidationGate:
    status = GateStatus.PASS if value >= threshold else GateStatus.FAIL
    return _make_gate(
        name,
        status,
        f"{value:.3%}",
        f">= {threshold:.1%}",
        detail,
    )


def validate_pipeline(
    raw_rows: list[dict[str, Any]],
    documents: list[DocumentRecord],
    reference: list[dict[str, Any]],
    events: list[EventCandidate],
    people: list[PersonCandidate],
) -> ValidationResult:
    issues: list[dict[str, Any]] = []
    gates: list[ValidationGate] = []

    raw_schema_errors = [
        index
        for index, row in enumerate(raw_rows)
        if not isinstance(row.get("url"), str)
        or not row.get("url")
        or not isinstance(row.get("html"), str)
        or not row.get("html")
    ]
    reference_schema_errors = [
        {"row": index, "missing": sorted(set(REQUIRED_REFERENCE_FIELDS) - set(row))}
        for index, row in enumerate(reference)
        if set(REQUIRED_REFERENCE_FIELDS) - set(row)
    ]
    if raw_schema_errors:
        issues.append({"type": "raw_schema", "rows": raw_schema_errors[:20]})
    if reference_schema_errors:
        issues.append({"type": "reference_schema", "rows": reference_schema_errors[:20]})
    gates.append(
        _make_gate(
            "source_schema",
            GateStatus.PASS
            if not raw_schema_errors and not reference_schema_errors
            else GateStatus.FAIL,
            f"{len(raw_schema_errors) + len(reference_schema_errors)} errors",
            "0 errors",
            "Raw rows require non-empty url/html; reference rows require all documented fields.",
        )
    )
    raw_urls = [normalize_url(row.get("url")) for row in raw_rows]
    reference_urls = [normalize_url(row.get("url")) for row in reference]
    raw_url_set = {url for url in raw_urls if url}
    reference_url_set = {url for url in reference_urls if url}
    unique_ok = len(raw_url_set) == len(raw_urls) and len(reference_url_set) == len(reference_urls)
    gates.append(
        _make_gate(
            "url_uniqueness",
            GateStatus.PASS if unique_ok else GateStatus.FAIL,
            f"raw={len(raw_url_set)}/{len(raw_urls)}, reference={len(reference_url_set)}/{len(reference_urls)}",
            "100% unique in each config",
            "Titles are not keys; the pipeline joins only on normalized source URL.",
        )
    )
    set_match = raw_url_set == reference_url_set
    gates.append(
        _make_gate(
            "one_to_one_join",
            GateStatus.PASS if set_match else GateStatus.FAIL,
            f"shared={len(raw_url_set & reference_url_set)}",
            "identical URL sets",
            "The HTML and structured configurations must describe the same source documents.",
        )
    )

    accepted = [
        doc for doc in documents 
        if (getattr(doc.parse_status, "value", str(doc.parse_status)) == "accepted")
    ]
    quarantined = [
        doc for doc in documents 
        if (getattr(doc.parse_status, "value", str(doc.parse_status)) == "quarantined")
    ]
    accounting_ok = len(raw_rows) == len(accepted) + len(quarantined) == len(documents)
    gates.append(
        _make_gate(
            "row_accounting",
            GateStatus.PASS if accounting_ok else GateStatus.FAIL,
            f"input={len(raw_rows)}, accepted={len(accepted)}, quarantined={len(quarantined)}",
            "input = accepted + quarantined",
            "No row may disappear silently.",
        )
    )
    acceptance_rate = len(accepted) / len(documents) if documents else 0.0
    acceptance_status = GateStatus.PASS if acceptance_rate >= 0.99 else GateStatus.FAIL
    gates.append(
        _make_gate(
            "release_signature",
            acceptance_status,
            f"{len(accepted)}/{len(documents)} accepted",
            ">= 99% accepted; all exceptions quarantined",
            "A page must have the release DOM, dates, canonical identity, and article body.",
        )
    )
    primary_body = sum(
        getattr(doc, "field_provenance", {}).get("body_text") == "css:.nr-body" for doc in accepted
    )
    primary_rate = primary_body / len(accepted) if accepted else 0.0
    gates.append(
        _threshold_gate(
            "primary_body_selector",
            primary_rate,
            0.99,
            detail="Fallback growth is treated as template drift, not silently accepted.",
        )
    )

    documents_by_url = {
        getattr(doc, "input_url", doc.url): doc for doc in documents
    }
    reference_by_url = {
        normalized: row
        for row in reference
        if (normalized := normalize_url(row.get("url"))) is not None
    }
    fields = (
        "title",
        "subtitle",
        "topics",
        "published_date",
        "modified_date",
        "dateline_raw",
        "dateline_city",
        "dateline_region",
        "body_text",
        "image_urls",
    )
    field_metrics = [
        _field_metric(field, documents_by_url, reference_by_url) for field in fields
    ]
    metrics_by_field = {metric.field: metric for metric in field_metrics}
    for field, threshold in (
        ("title", 0.99),
        ("topics", 0.99),
        ("published_date", 0.99),
        ("dateline_city", 0.99),
    ):
        metric = metrics_by_field[field]
        if metric.reference_present == 0:
            status = GateStatus.WARN
        else:
            verified_rate = metric.exact_matches / metric.reference_present
            status = GateStatus.PASS if verified_rate >= threshold else GateStatus.FAIL
        gates.append(
            _make_gate(
                f"{field}_reference_agreement",
                status,
                (
                    f"exact={metric.exact_matches}/{metric.reference_present}; "
                    f"paired agreement={metric.agreement:.3%}"
                ),
                f"exact/reference-present >= {threshold:.1%}",
                (
                    "Agreement is measured only where both the DOM extraction and silver "
                    "reference have a value; the gate also penalizes missing extracted values."
                ),
            )
        )

    body_similarity = _body_similarity(documents_by_url, reference_by_url)
    issues.extend(
        _comparison_issues(fields, documents_by_url, reference_by_url)
    )
    body_gate_ok = (
        float(body_similarity["median_token_f1"]) >= 0.99
        and float(body_similarity["p05_token_f1"]) >= 0.95
    )
    gates.append(
        _make_gate(
            "body_similarity",
            GateStatus.PASS if body_gate_ok else GateStatus.FAIL,
            (
                f"median={float(body_similarity['median_token_f1']):.3f}, "
                f"p05={float(body_similarity['p05_token_f1']):.3f}"
            ),
            "median >= 0.99 and p05 >= 0.95",
            "Token F1 tolerates documented block-level differences in the silver reference.",
        )
    )
    body_outliers = int(body_similarity["below_0_90"])
    gates.append(
        _make_gate(
            "body_outlier_review",
            GateStatus.WARN if body_outliers else GateStatus.PASS,
            f"{body_outliers}/{int(body_similarity['compared'])} below 0.90 token F1",
            "every outlier enters a human review queue",
            "Low similarity can mean a DOM omission or useful content missing from the silver reference.",
        )
    )

    documents_by_id = {
        getattr(doc, "document_id", getattr(doc, "url", str(idx))): doc 
        for idx, doc in enumerate(documents)
    }
    offset_issues = _candidate_offset_issues(documents_by_id, [*events, *people])
    issues.extend(offset_issues)
    gates.append(
        _make_gate(
            "evidence_offsets",
            GateStatus.PASS if not offset_issues else GateStatus.FAIL,
            f"{len(offset_issues)} invalid offsets",
            "0 invalid offsets",
            "Every candidate must link back to an exact source-text span.",
        )
    )

    reference_profile = profile_reference(reference)
    document_profile = profile_documents(documents)
    source_defects = int(reference_profile["invalid_modified_count"])
    gates.append(
        _make_gate(
            "silver_reference_validity",
            GateStatus.WARN if source_defects else GateStatus.PASS,
            f"{source_defects} populated modified-date values are not dates",
            "report completeness and validity separately",
            "The companion structured data is a comparison reference, not ground truth.",
        )
    )
    gates.append(
        _make_gate(
            "candidate_layer_publication_readiness",
            GateStatus.WARN if events or people else GateStatus.PASS,
            f"{len(events)} event and {len(people)} person candidates",
            "independent row-level adjudication before journalistic use",
            (
                "Candidate rules preserve evidence, but automated invariants do not establish "
                "action, legal-stage, count, person-role, or relation accuracy."
            ),
        )
    )

        if any(g.status == GateStatus.FAIL for g in gates):
        overall_status = GateStatus.FAIL
    elif any(g.status == GateStatus.WARN for g in gates):
        overall_status = GateStatus.WARN
    else:
        overall_status = GateStatus.PASS

    return ValidationResult(
        status=overall_status,
        gates=gates,
        field_metrics=metrics,
        reference_profile=reference_profile,
        document_profile=document_profile,
        body_similarity=body_similarity,
        row_accounting={
            "input": len(raw_rows),
            "accepted": len(accepted),
            "quarantined": len(quarantined),
            "events": len(events),
            "people": len(people),
        },
        issues=issues,
    )
