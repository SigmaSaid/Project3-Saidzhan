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
    rows = []

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
) -> LoadedInputs:
    from datasets import load_dataset

    dataset = load_dataset(
        dataset_id,
        revision=revision,
        split=split,
        cache_dir=cache_dir,
    )

    if limit is not None:
        dataset = dataset.select(
            range(min(limit, len(dataset)))
        )

    return LoadedInputs(
        raw=[dict(row) for row in dataset],
        reference=[],
        metadata={
            "source": dataset_id,
            "revision": revision,
            "split": split,
            "limit": limit,
        },
    )
