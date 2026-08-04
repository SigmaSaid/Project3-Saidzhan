from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class LoadedInputs:
    raw: list[dict[str, Any]]
    reference: list[dict[str, Any]]
    metadata: dict[str, Any]


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    path = Path(path)

    if not path.exists():
        return rows

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    return rows


def load_local_inputs(
    raw_path: str | Path,
    reference_path: str | Path | None = None,
    limit: int | None = None,
) -> LoadedInputs:
    raw = _read_jsonl(raw_path)

    reference = []
    if reference_path:
        reference = _read_jsonl(reference_path)

    if limit is not None:
        raw = raw[:limit]
        reference = reference[:limit]

    return LoadedInputs(
        raw=raw,
        reference=reference,
        metadata={
            "source": "local_jsonl",
            "raw_path": str(raw_path),
            "reference_path": str(reference_path) if reference_path else None,
        },
    )


def load_huggingface_inputs(
    dataset_id: str,
    revision: str | None = None,
    split: str = "train",
    limit: int | None = None,
    cache_dir: str | Path | None = None,
    html_config: str = "html",
    reference_config: str = "default",
) -> LoadedInputs:
    from datasets import load_dataset

    raw_dataset = load_dataset(
        dataset_id,
        name=html_config,
        revision=revision,
        split=split,
        cache_dir=cache_dir,
    )
    reference_dataset = load_dataset(
        dataset_id,
        name=reference_config,
        revision=revision,
        split=split,
        cache_dir=cache_dir,
    )

    if limit is not None:
        raw_dataset = raw_dataset.select(range(min(limit, len(raw_dataset))))
        reference_dataset = reference_dataset.select(range(min(limit, len(reference_dataset))))

    return LoadedInputs(
        raw=[dict(row) for row in raw_dataset],
        reference=[dict(row) for row in reference_dataset],
        metadata={
            "source": dataset_id,
            "dataset_id": dataset_id,
            "revision": revision,
            "split": split,
            "limit": limit,
            "html_config": html_config,
            "reference_config": reference_config,
        },
    )
