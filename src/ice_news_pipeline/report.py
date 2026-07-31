"""Human-readable validation, findings, and audit artifacts."""

from __future__ import annotations

import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

from ice_news_pipeline.models import (
    DocumentRecord,
    EventCandidate,
    GateStatus,
    PersonCandidate,
    ValidationResult,
)


def _safe_pct(numerator: int | float, denominator: int | float) -> str:
    """Safe percentage formatting preventing ZeroDivisionError."""
    if not denominator:
        return "0.00%"
    return f"{(numerator / denominator):.2%}"


def _decision(validation: ValidationResult) -> str:
    if validation.status is GateStatus.FAIL:
        return "NOT READY — at least one automated release-level contract gate failed."
    if validation.status is GateStatus.WARN:
        return (
            "PASS WITH WARNINGS — prespecified automated contract thresholds passed; "
            "listed exceptions still require review."
        )
    return "PASS — all prespecified automated document-layer contract gates passed."


def write_validation_report(
    path: Path,
    validation: ValidationResult,
    documents: list[DocumentRecord],
    metadata: dict[str, Any],
) -> None:
    profile = validation.reference_profile
    document_profile = validation.document_profile
    accounting = validation.row_accounting
    quarantined = [doc for doc in documents if doc.parse_status.value == "quarantined"]
    invalid_modified = profile["invalid_modified_examples"]

    gates_df = pd.DataFrame([
        {
            "Gate": g.name,
            "Status": g.status.value.upper(),
            "Observed": g.observed,
            "Requirement": g.requirement,
            "Interpretation": g.detail,
        }
        for g in validation.gates
    ])

    metrics_df = pd.DataFrame([
        {
            "Field": m.field,
            "Reference present": m.reference_present,
            "Extracted present": m.extracted_present,
            "Paired": m.both_present,
            "Coverage": _safe_pct(m.coverage, 1.0),
            "Exact / paired": (
                f"{m.exact_matches}/{m.both_present} ({_safe_pct(m.exact_matches, m.both_present)})"
                if m.both_present else "not measurable"
            ),
            "Extra DOM values": m.false_positives,
        }
        for m in validation.field_metrics
    ])

    invalid_dates_df = pd.DataFrame([
        {
            "Source URL": item["url"],
            "Invalid populated value": str(item["value"])[:180] + ("…" if len(str(item["value"])) > 180 else ""),
        }
        for item in invalid_modified
    ])

    quarantine_df = pd.DataFrame([
        {
            "URL": doc.input_url,
            "Drupal entity type": doc.entity_bundle,
            "Quality flags": "; ".join(doc.quality_flags),
        }
        for doc in quarantined
    ])

    review_issues = [
        issue for issue in validation.issues if issue.get("type") == "silver_reference_mismatch"
    ]
    body_review = sorted(
        (issue for issue in review_issues if issue.get("field") == "body_text"),
        key=lambda issue: float(issue.get("token_f1", 1.0)),
    )[:10]

    body_review_df = pd.DataFrame([
        {
            "URL": issue["url"],
            "Token F1": f"{float(issue['token_f1']):.4f}",
            "Reference / DOM tokens": f"{issue['reference_tokens']} / {issue['extracted_tokens']}",
            "First difference": issue["difference_context"],
        }
        for issue in body_review
    ])

    
    body = validation.body_similarity
    gates_by_name = {gate.name: gate for gate in validation.gates}
    join_gate = gates_by_name["one_to_one_join"]
    
    join_summary = (
        "URL sets match one-to-one between the `html` and `default` configurations."
        if join_gate.status is GateStatus.PASS
        else f"URL-set contract did not pass: {join_gate.observed}."
    )

    body_outlier_count = int(body["below_0_90"])
    if validation.status is not GateStatus.FAIL:
        publication_decision = (
            "The accepted document records passed the project's prespecified structural and "
            "silver-agreement thresholds. This is an automated contract result, not proof of "
            "ground-truth accuracy. "
            f"{body_outlier_count} body outliers below 0.90 token F1 await human adjudication."
        )
    else:
        publication_decision = (
            "The document layer is not ready for descriptive analysis because at least one "
            "automated contract gate failed. Resolve the failed gates before using its findings."
        )

    ref_lag, ext_lag = profile["modification_lag"], document_profile["modification_lag"]

  
    content = f"""# Validation report

**Decision:** {_decision(validation)}

This report evaluates the release-level document extractor on the pinned Big Local News snapshot.
It distinguishes source completeness, value validity, extractor agreement, and publication
readiness. The companion structured configuration is treated as a **silver reference**, not
infallible ground truth.

## Reproducibility

- Dataset: `{metadata.get("dataset_id", metadata.get("source", "local"))}`
- Revision: `{metadata.get("revision", "local files")}`
- Split: `{metadata.get("split", "local")}`
- Raw fingerprint: `{metadata.get("raw_fingerprint", "not available")}`
- Reference fingerprint: `{metadata.get("reference_fingerprint", "not available")}`
- Reference SHA-256: `{profile["sha256"]}`
- Input rows: {accounting["input"]:,}

## Executive result

- {accounting["accepted"]:,}/{accounting["input"]:,} rows were accepted as press releases.
- {accounting["quarantined"]:,}/{accounting["input"]:,} rows were retained in quarantine; none were silently deleted.
- {join_summary}
- The pipeline extracted {accounting["events"]:,} event candidates and {accounting["people"]:,} explicit name-and-age candidates.

## Why “populated” is not the same as “valid”

The companion `default` configuration has a non-empty `date_last_updated` value in all {profile["rows"]:,} rows, but only {profile["valid_modified_dates"]:,} values parse as dates.
The other {profile["invalid_modified_count"]:,} values appear to be article prose mistakenly stored in that field.

{invalid_dates_df.to_markdown(index=False) if not invalid_dates_df.empty else "No invalid modified dates found."}

## Automated gates

{gates_df.to_markdown(index=False)}

## Field-level silver-reference comparison

{metrics_df.to_markdown(index=False)}

### Body-text similarity

- Compared: {int(body["compared"]):,}
- Normalized exact matches: {int(body["exact_matches"]):,} ({_safe_pct(body["exact_matches"], body["compared"])})
- Below 0.90 token F1: {int(body["below_0_90"]):,}
- Below 0.95 token F1: {int(body["below_0_95"]):,}
- Mean token F1: {float(body["mean_token_f1"]):.4f}
- Median token F1: {float(body["median_token_f1"]):.4f}

### Review queue

{body_review_df.to_markdown(index=False) if not body_review_df.empty else "No body-text mismatches found."}

## Quarantine

{quarantine_df.to_markdown(index=False) if not quarantine_df.empty else "No rows were quarantined."}

## Reference-data audit

- Unique source URLs: {profile["unique_urls"]:,}/{profile["rows"]:,}
- Valid publication dates: {profile["valid_published_dates"]:,}/{profile["rows"]:,}
- Valid modified dates: {profile["valid_modified_dates"]:,}/{profile["rows"]:,}
- Duplicate-title groups: {len(profile["duplicate_title_groups"]):,}
- Non-US region labels in `state`: {", ".join(profile["non_us_region_labels"]) or "none"}
- Companion-config median metadata lag: {ref_lag["median_days"]} days
- DOM-extracted median metadata lag: {ext_lag["median_days"]} days

## Publication-readiness decision

{publication_decision}
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_findings_report(
    path: Path,
    tables: dict[str, pd.DataFrame],
    validation: ValidationResult,
) -> None:
    if validation.status is GateStatus.FAIL:
        failed_gates = [g.name for g in validation.gates if g.status is GateStatus.FAIL]
        content = f"""# Descriptive findings withheld

No release-level findings were generated because the automated validation result is `FAIL`.
Accepted rows: {validation.row_accounting['accepted']:,}/{validation.row_accounting['input']:,}. 
Failed gates: {", ".join(f"`{name}`" for name in failed_gates)}.
"""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return

    documents = tables["documents"]
    accepted = documents[documents["parse_status"] == "accepted"]
    dated = accepted.dropna(subset=["published_date"])
    years = dated["year"].value_counts().sort_index()
    recent_count = int(years.get("2025", 0) + years.get("2026", 0))

    monthly = tables["monthly_volume"].sort_values("documents", ascending=False).head(5)
    topics = tables["topics"].head(12)
    regions = tables["dateline_regions"].head(12)

    multi_topic = int((accepted["topic_count"] > 1).sum())
    known_topic = int((accepted["topic_count"] > 0).sum())
    known_regions = int(accepted["dateline_region"].notna().sum())
    
 
    monthly_df = monthly[["month", "documents"]].rename(
        columns={"month": "Publication month", "documents": "Documents"}
    )
    
    topics_df = topics.assign(
        **{"Share of documents with topics": lambda df: df["share_of_documents_with_topics"].map(lambda x: f"{float(x):.2%}")}
    )[["topic", "documents", "Share of documents with topics"]].rename(
        columns={"topic": "Topic", "documents": "Documents"}
    )

    regions_df = regions.assign(
        **{f"Share of populated regions (n={known_regions:,})": lambda df: df["share_of_known"].map(lambda x: f"{float(x):.2%}")}
    )[["dateline_region", "documents", f"Share of populated regions (n={known_regions:,})"]].rename(
        columns={"dateline_region": "Metadata dateline region", "documents": "Documents"}
    )

    content = f"""# Descriptive findings

## Scope first

These findings describe **which ICE press releases appear in this dataset and how ICE presents them**.

## Corpus coverage

- Accepted press releases: {len(accepted):,}
- Valid publication dates: {len(dated):,}
- 2025–2026 releases: {recent_count:,}/{len(dated):,} ({_safe_pct(recent_count, len(dated))})
- Quarantined non-release pages: {validation.row_accounting['quarantined']:,}

![Monthly publication volume](figures/monthly_release_volume.png)

### Largest months represented in the corpus

{monthly_df.to_markdown(index=False)}

## Topics are multi-label

- Documents with known topics: {known_topic:,}
- Multi-topic documents: {multi_topic:,}/{known_topic:,} ({_safe_pct(multi_topic, known_topic)})

{topics_df.to_markdown(index=False)}

![Top topic labels](figures/top_topics.png)

## Datelines are communication geography

{regions_df.to_markdown(index=False)}

![Top dateline regions](figures/top_dateline_regions.png)
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_audit_sample(
    documents: list[DocumentRecord],
    events: list[EventCandidate],
    people: list[PersonCandidate],
    *,
    size: int = 30,
    seed: int = 20260729,
) -> pd.DataFrame:
    reasons: defaultdict[str, set[str]] = defaultdict(set)
    by_id = {doc.document_id: doc for doc in documents}
    accepted = [doc for doc in documents if doc.parse_status.value == "accepted"]


    for doc in documents:
        if doc.parse_status.value == "quarantined":
            reasons[doc.document_id].add("quarantine")
        if doc.tables:
            reasons[doc.document_id].add("contains_table")
            
    for doc in sorted(accepted, key=lambda d: (-len(d.topics), d.document_id))[:4]:
        if len(doc.topics) > 1:
            reasons[doc.document_id].add("multi_topic")

    for doc in sorted(accepted, key=lambda d: d.word_count)[:3]:
        reasons[doc.document_id].add("shortest")
    for doc in sorted(accepted, key=lambda d: d.word_count, reverse=True)[:3]:
        reasons[doc.document_id].add("longest")

    selected = set(reasons)
    
    pool = sorted([doc.document_id for doc in accepted if doc.document_id not in selected])
    randomizer = random.Random(seed)
    randomizer.shuffle(pool)
    
    for doc_id in pool:
        if len(selected) >= size:
            break
        selected.add(doc_id)
        reasons[doc_id].add("seeded_random")

    event_counts = Counter(c.document_id for c in events)
    people_counts = Counter(c.document_id for c in people)

    rows = [
        {
            "document_id": doc_id,
            "url": by_id[doc_id].input_url,
            "title": by_id[doc_id].title,
            "published_date": by_id[doc_id].published_date,
            "topics": " | ".join(by_id[doc_id].topics),
            "word_count": by_id[doc_id].word_count,
            "event_candidates": event_counts[doc_id],
            "person_candidates": people_counts[doc_id],
            "selection_reason": " | ".join(sorted(reasons[doc_id])),
            "is_press_release_gold": "",
            "reviewer": "",
            "reviewer_notes": "",
        }
        for doc_id in sorted(selected)
    ]

    return pd.DataFrame(rows)
