from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Union
from dataclasses import dataclass, field


@dataclass
class LoadedInputs:
    records: List[Dict[str, str]] = field(default_factory=list)

def load_local_inputs(input_path: Union[str, Path]) -> List[Dict[str, str]]:
    """Loads local HTML files or raw text documents from a given directory or file path.

    Returns:
        List of dictionaries containing:
        - 'url' / 'input_url': File path or identifier
        - 'html' / 'content': Raw file content string
    """
    path = Path(input_path)
    results: List[Dict[str, str]] = []

    if not path.exists():
        return results

    if path.is_file():
        files = [path]
    else:
        files = [p for p in path.glob("**/*") if p.suffix.lower() in (".html", ".htm", ".txt", ".json")]

    for file_path in files:
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            results.append({
                "url": str(file_path),
                "input_url": str(file_path),
                "html": content,
                "content": content,
            })
        except Exception:
            continue

    return results
