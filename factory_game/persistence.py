from __future__ import annotations

import json
from pathlib import Path


class SaveStore:
    VERSION = 2

    def __init__(self, path: Path | None = None):
        self.path = path or Path.home() / ".codewerk" / "save.json"

    def load(self) -> dict:
        defaults = {"version": self.VERSION, "mission": 0, "unlocked": 0, "credits": 0, "projects": {}, "console_geometry": None}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if data.get("version") == 1:
                projects = {mission_id: {"main.py": code} for mission_id, code in data.get("codes", {}).items()}
                return defaults | {key: data.get(key, defaults[key]) for key in ("mission", "unlocked", "credits")} | {"projects": projects}
            if data.get("version") != self.VERSION:
                return defaults
            return defaults | data
        except (OSError, ValueError):
            return defaults

    def save(self, data: dict) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_suffix(".tmp")
            temp.write_text(json.dumps(data, indent=2), encoding="utf-8")
            temp.replace(self.path)
        except OSError:
            pass
