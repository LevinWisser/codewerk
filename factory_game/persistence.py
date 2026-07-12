from __future__ import annotations

import json
from pathlib import Path


class SaveStore:
    VERSION = 3

    def __init__(self, path: Path | None = None):
        self.path = path or Path.home() / ".codewerk" / "save.json"

    def load(self) -> dict:
        defaults = {
            "version": self.VERSION, "mission": 0, "unlocked": 0, "credits": 0,
            "projects": {}, "shared_files": {}, "console_geometry": None,
            "tutorial_complete": False, "completed_tutorial_missions": [],
            "mode": "tutorial", "factory_state": None,
        }
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if data.get("version") == 1:
                projects = {mission_id: {"main.py": code} for mission_id, code in data.get("codes", {}).items()}
                data = defaults | {key: data.get(key, defaults[key]) for key in ("mission", "unlocked", "credits")} | {"projects": projects, "version": 2}
            if data.get("version") == 2:
                tutorial_complete = int(data.get("unlocked", 0)) >= 7 and int(data.get("credits", 0)) >= 3220
                completed_count = 8 if tutorial_complete else min(7, int(data.get("unlocked", 0)))
                return defaults | data | {
                    "version": self.VERSION,
                    "tutorial_complete": tutorial_complete,
                    "completed_tutorial_missions": list(range(completed_count)),
                    "mode": "factory" if tutorial_complete else "tutorial",
                }
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
