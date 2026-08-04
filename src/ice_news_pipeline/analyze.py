from __future__ import annotations
from matplotlib.axes import Axes

import os
import tempfile
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

os.environ.setdefault(
    "MPLCONFIGDIR",
    str(Path(tempfile.gettempdir()) / "ice-news-pipeline-matplotlib"),
)

import matplotlib
import pandas as pd

from ice_news_pipeline.models import DocumentRecord, ParseStatus

matplotlib.use("Agg")
import matplotlib.pyplot as plt

CARDINAL = "#8C1515"
DARK = "#2E2D29"
TEAL = "#007C92"
GOLD = "#B26F16"
LIGHT = "#DAD7CB"


def documents_frame(documents: list[DocumentRecord]) -> pd.DataFrame:
    if not documents:
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    for document in documents:
        published = (
            date.fromisoformat(document.published_date) if document.published_date else None
        )
        modified = date.fromisoformat(document.modified_date) if document.modified_date else None
        
        rows.append(
            {
                "document_id": document.document_id,
                "url": document.input_url,
                "title": document.title,
                "published_date": document.published_date,
                "modified_date": document.modified_date,
                "year": str(published.year) if published else "Unknown",
                "month": published.strftime("%Y-%m") if published else None,
                "modification_lag_days": (
                    int((modified - published).days) if published and modified else None
                ),
                "dateline_city": document.dateline_city,
                "dateline_region": document.dateline_region,
                "dateline_country": document.dateline_country,
                "topics": document.topics,
                "topic_count": len(document.topics),
                "has_subtitle": document.subtitle is not None,
                "has_images": bool(document.image_urls),
                "has_dateline": document.dateline_raw is not None,
                "word_count": document.word_count,
                "paragraph_count": document.paragraph_count,
                "table_count": len(document.tables),
                "parse_status": document.parse_status.value,
                "quality_flags": document.quality_flags,
            }
        )
    return pd.DataFrame(rows)


def _count_table(series: pd.Series, name: str, denominator: int) -> pd.DataFrame:
    counts = series.dropna().value_counts().rename_axis(name).reset_index(name="documents")
    counts["share_of_known"] = counts["documents"] / denominator if denominator else 0.0
    return counts


def _lag_bucket(value: float | int | None) -> str | None:
    if value is None or pd.isna(value):
        return None
    days = int(value)
    if days < 0:
        return "Negative (review)"
    if days == 0:
        return "Same day"
    if days <= 7:
        return "1–7 days"
    if days <= 30:
        return "8–30 days"
    if days <= 365:
        return "31–365 days"
    return "More than 365 days"


def build_analysis_tables(documents: list[DocumentRecord]) -> dict[str, pd.DataFrame]:
    frame = documents_frame(documents)
    if frame.empty:
        return {
            "documents": frame,
            "monthly_volume": pd.DataFrame(columns=["month", "documents"]),
            "dateline_regions": pd.DataFrame(columns=["dateline_region", "documents", "share_of_known"]),
            "topics": pd.DataFrame(columns=["topic", "documents", "share_of_documents_with_topics"]),
            "missingness_by_year": pd.DataFrame(),
            "modification_lag_buckets": pd.DataFrame(columns=["lag_bucket", "documents", "share"]),
            "field_provenance": pd.DataFrame(),
            "quarantined": pd.DataFrame(),
        }

    accepted = frame[frame["parse_status"] == ParseStatus.ACCEPTED.value].copy()

    monthly = (
        accepted.dropna(subset=["month"])
        .groupby("month", as_index=False)
        .size()
        .rename(columns={"size": "documents"})
        .sort_values("month")
    )

    known_regions = int(accepted["dateline_region"].notna().sum())
    regions = _count_table(accepted["dateline_region"], "dateline_region", known_regions)

    topic_frame = (
        accepted[["document_id", "topics"]]
        .explode("topics")
        .dropna(subset=["topics"])
        .rename(columns={"topics": "topic"})
    )
    known_topic_documents = int(accepted["topics"].map(bool).sum())
    
    if not topic_frame.empty:
        topics = (
            topic_frame.groupby("topic")["document_id"]
            .nunique()
            .reset_index(name="documents")
            .sort_values(["documents", "topic"], ascending=[False, True])
        )
    else:
        topics = pd.DataFrame(columns=["topic", "documents"])

    topics["share_of_documents_with_topics"] = (
        topics["documents"] / known_topic_documents if known_topic_documents else 0.0
    )

    missingness_rows: list[dict[str, Any]] = []
    for year, group in frame.groupby("year", sort=True):
        total = len(group)
        missingness_rows.append(
            {
                "year": year,
                "documents": total,
                "subtitle_missing": int((~group["has_subtitle"]).sum()),
                "subtitle_missing_share": float((~group["has_subtitle"]).mean()),
                "dateline_missing": int((~group["has_dateline"]).sum()),
                "dateline_missing_share": float((~group["has_dateline"]).mean()),
                "image_missing": int((~group["has_images"]).sum()),
                "image_missing_share": float((~group["has_images"]).mean()),
                "quarantined": int((group["parse_status"] == ParseStatus.QUARANTINED.value).sum()),
            }
        )
    missingness = pd.DataFrame(missingness_rows)

    lags = accepted["modification_lag_days"].dropna()
    lag_buckets = (
        lags.map(_lag_bucket)
        .value_counts()
        .reindex(
            [
                "Negative (review)",
                "Same day",
                "1–7 days",
                "8–30 days",
                "31–365 days",
                "More than 365 days",
            ],
            fill_value=0,
        )
        .rename_axis("lag_bucket")
        .reset_index(name="documents")
    )
    lag_buckets["share"] = lag_buckets["documents"] / len(lags) if len(lags) else 0.0

    provenance_rows: list[dict[str, str]] = []
    for document in documents:
        for field, method in document.field_provenance.items():
            provenance_rows.append({"field": field, "method": method})

    if provenance_rows:
        provenance = (
            pd.DataFrame(provenance_rows)
            .value_counts(["field", "method"])
            .rename("documents")
            .reset_index()
            .sort_values(["field", "documents"], ascending=[True, False])
        )
        field_denominators = Counter(row["field"] for row in provenance_rows)
        provenance["share_within_field"] = (
            provenance["documents"] / provenance["field"].map(field_denominators)
        )
    else:
        provenance = pd.DataFrame(columns=["field", "method", "documents", "share_within_field"])

    quarantined = frame[frame["parse_status"] == ParseStatus.QUARANTINED.value][
        ["document_id", "url", "title", "quality_flags"]
    ].copy()
    quarantined["quality_flags"] = quarantined["quality_flags"].map(
        lambda values: "; ".join(values) if isinstance(values, (list, tuple)) else ""
    )

    return {
        "documents": frame,
        "monthly_volume": monthly,
        "dateline_regions": regions,
        "topics": topics,
        "missingness_by_year": missingness,
        "modification_lag_buckets": lag_buckets,
        "field_provenance": provenance,
        "quarantined": quarantined,
    }


def _style_axis(axis: Axes) -> None:
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.spines["left"].set_color(LIGHT)
    axis.spines["bottom"].set_color(LIGHT)
    axis.tick_params(colors=DARK)
    axis.grid(axis="y", color=LIGHT, alpha=0.55, linewidth=0.8)
    axis.set_axisbelow(True)


def _plot_monthly_volume(monthly: pd.DataFrame, figure_dir: Path) -> Path:
    recent = monthly[monthly["month"].str.startswith(("2025-", "2026-"))].copy()
    if recent.empty:
        recent = monthly.tail(24).copy()

    figure, axis = plt.subplots(figsize=(12, 5.8))
    colors = [GOLD if index in {0, len(recent) - 1} else CARDINAL for index in range(len(recent))]
    bars = axis.bar(recent["month"], recent["documents"], color=colors, width=0.78)
    
    axis.bar_label(bars, padding=3, fontsize=9, color=DARK)
    axis.set_title("ICE press releases in the dataset by publication month")
    axis.set_ylabel("Documents")
    axis.set_xlabel("Publication month (edge months are incomplete)")
    axis.tick_params(axis="x", rotation=55)
    _style_axis(axis)
    
    figure.tight_layout()
    path = figure_dir / "monthly_release_volume.png"
    figure.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(figure)
    return path


def _plot_horizontal_bars(
    df: pd.DataFrame,
    category_col: str,
    value_col: str,
    title: str,
    xlabel: str,
    color: str,
    filename: str,
    figure_dir: Path,
) -> Path:
    data = df.head(12).sort_values(value_col)
    figure, axis = plt.subplots(figsize=(10, 6.4))
    bars = axis.barh(data[category_col], data[value_col], color=color)
    
    axis.bar_label(bars, padding=4, fontsize=9, color=DARK)
    axis.set_title(title)
    axis.set_xlabel(xlabel)
    axis.set_ylabel("")
    _style_axis(axis)
    axis.grid(axis="x", color=LIGHT, alpha=0.55, linewidth=0.8)
    axis.grid(axis="y", visible=False)
    
    figure.tight_layout()
    path = figure_dir / filename
    figure.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(figure)
    return path


def write_figures(tables: dict[str, pd.DataFrame], figure_dir: Path) -> list[Path]:
    figure_dir.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "axes.titleweight": "bold",
            "axes.titlesize": 14,
            "figure.facecolor": "white",
        }
    )
    written: list[Path] = []

    if not tables["monthly_volume"].empty:
        written.append(_plot_monthly_volume(tables["monthly_volume"], figure_dir))

    if not tables["topics"].empty:
        written.append(
            _plot_horizontal_bars(
                df=tables["topics"],
                category_col="topic",
                value_col="documents",
                title="Most frequent topic labels (multi-label documents counted once per topic)",
                xlabel="Documents",
                color=TEAL,
                filename="top_topics.png",
                figure_dir=figure_dir,
            )
        )

    if not tables["dateline_regions"].empty:
        written.append(
            _plot_horizontal_bars(
                df=tables["dateline_regions"],
                category_col="dateline_region",
                value_col="documents",
                title="Most frequent press-release datelines",
                xlabel="Documents (not enforcement-event locations)",
                color=DARK,
                filename="top_dateline_regions.png",
                figure_dir=figure_dir,
            )
        )

    return written
