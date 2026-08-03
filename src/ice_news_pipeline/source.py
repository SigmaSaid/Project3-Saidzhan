from __future__ import annotations

import json
from pathlib import Path
from dataclasses import dataclass
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
            "source": "local",
            "raw_path": str(raw_path),
            "reference_path": str(reference_path)
            if reference_path
            else None,
        },
    )
