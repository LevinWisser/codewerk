from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
TOKEN_PATH = ROOT / "assets" / "design_tokens.json"
MANIFEST_PATH = ROOT / "assets" / "manifests" / "assets.json"


@lru_cache(maxsize=1)
def design_tokens() -> dict[str, Any]:
    return json.loads(TOKEN_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def asset_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["assets"]


def color(name: str) -> str:
    return design_tokens()["color"][name]


def geometry(name: str) -> int | float:
    return design_tokens()["geometry"][name]


def motion(name: str) -> int | float:
    return design_tokens()["motion"][name]
