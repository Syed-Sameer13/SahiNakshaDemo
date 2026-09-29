from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class AnalysisStore:
    """Small disk-backed store for prototype persistence across API restarts."""

    def __init__(self, directory: Path):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def save(self, analysis_id: str, payload: dict[str, Any]) -> None:
        path = self.directory / f"{analysis_id}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")

    def load(self, analysis_id: str) -> dict[str, Any] | None:
        path = self.directory / f"{analysis_id}.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
