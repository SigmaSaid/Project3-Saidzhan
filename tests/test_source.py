from __future__ import annotations

import json
from pathlib import Path

from ice_news_pipeline.source import load_local_inputs


def _write_jsonl(path: Path, rows: list[dict[str, str]]) -> None:
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_local_source_adapter_supports_offline_reproduction(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw.jsonl"
    reference_path = tmp_path / "reference.jsonl"
    _write_jsonl(
        raw_path,
        [
            {"url": "https://example.test/1", "html": "<html>one</html>"},
            {"url": "https://example.test/2", "html": "<html>two</html>"},
        ],
    )
    _write_jsonl(
        reference_path,
        [{"url": "https://example.test/1"}, {"url": "https://example.test/2"}],
    )

    loaded = load_local_inputs(raw_path, reference_path, limit=1)
    assert len(list(loaded.raw)) == 1
    assert len(loaded.reference) == 1
    assert loaded.metadata["source"] == "local_jsonl"
