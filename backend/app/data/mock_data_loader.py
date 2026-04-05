from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


def _resolve_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    repo_root = Path(__file__).resolve().parents[3]
    return (repo_root / path).resolve()


@lru_cache(maxsize=8)
def load_mock_data(raw_path: str) -> dict:
    path = _resolve_path(raw_path)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def clear_mock_data_cache() -> None:
    load_mock_data.cache_clear()
