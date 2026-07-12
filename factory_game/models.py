from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Machine:
    kind: str
    x: int
    y: int
    name: str
    recipe_inputs: list[str]
    recipe_output: str
    duration: int
    inputs: list[str] = field(default_factory=list)
    output: str | None = None
    remaining: int = 0

    @property
    def running(self) -> bool:
        return self.remaining > 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Mission:
    id: str
    title: str
    brief: str
    concept: str
    goal_text: str
    starter_code: str
    unlocked_docs: list[str]
    target: dict[str, Any]
    reward: int


@dataclass
class WorldState:
    size: int = 8
    drone_x: int = 1
    drone_y: int = 1
    inventory: str | None = None
    ticks: int = 0
    delivered: dict[str, int] = field(default_factory=dict)
    machines: list[Machine] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "size": self.size,
            "drone": {"x": self.drone_x, "y": self.drone_y, "inventory": self.inventory},
            "ticks": self.ticks,
            "delivered": dict(self.delivered),
            "machines": [machine.to_dict() for machine in self.machines],
        }
