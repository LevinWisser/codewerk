from __future__ import annotations

from collections import Counter
from typing import Any

from factory_game.content import DIRECTIONS, MACHINE_DEFINITIONS
from factory_game.models import Machine, Mission, WorldState


class GameError(Exception):
    pass


class Simulation:
    WAREHOUSE = (1, 2)
    SHIPPING = (6, 6)

    def __init__(self, mission: Mission):
        self.mission = mission
        self.calls: Counter[str] = Counter()
        self.state = WorldState(machines=self._make_machines())

    @staticmethod
    def _make_machines() -> list[Machine]:
        result = []
        for kind, x, y in (("press", 3, 2), ("mill", 5, 2), ("assembly", 4, 4)):
            name, inputs, output, duration = MACHINE_DEFINITIONS[kind]
            result.append(Machine(kind, x, y, name, list(inputs), output, duration))
        return result

    def reset(self) -> None:
        self.calls.clear()
        self.state = WorldState(machines=self._make_machines())

    def snapshot(self) -> dict[str, Any]:
        data = self.state.to_dict()
        data.update({"warehouse": list(self.WAREHOUSE), "shipping": list(self.SHIPPING)})
        return data

    def execute(self, command: str, args: list[Any]) -> Any:
        handlers = {
            "move": self._move, "pick_up": self._pick_up, "drop": self._drop,
            "discard_item": self._discard_item,
            "get_position": self._get_position, "get_inventory": self._get_inventory,
            "get_item_type": self._get_inventory, "can_move": self._can_move,
            "can_pick_up": self._can_pick_up, "load_machine": self._load_machine,
            "start_machine": self._start_machine, "machine_is_done": self._machine_is_done,
            "collect_output": self._collect_output, "wait": self._wait,
        }
        if command not in handlers:
            raise GameError(f"Unknown game command: {command}")
        self.calls[command] += 1
        result = handlers[command](*args)
        if command in {"move", "pick_up", "drop", "discard_item", "load_machine", "start_machine", "collect_output", "wait"}:
            self._tick()
        return result

    def _machine_here(self) -> Machine:
        for machine in self.state.machines:
            if (machine.x, machine.y) == (self.state.drone_x, self.state.drone_y):
                return machine
        raise GameError("The drone is not standing on a machine.")

    def _move(self, direction: str) -> None:
        if direction not in DIRECTIONS:
            raise GameError("move() expects North, East, South, or West.")
        dx, dy = DIRECTIONS[direction]
        nx, ny = self.state.drone_x + dx, self.state.drone_y + dy
        if not (0 <= nx < self.state.size and 0 <= ny < self.state.size):
            raise GameError("The factory boundary blocks this path.")
        self.state.drone_x, self.state.drone_y = nx, ny

    def _can_move(self, direction: str) -> bool:
        if direction not in DIRECTIONS:
            return False
        dx, dy = DIRECTIONS[direction]
        return 0 <= self.state.drone_x + dx < self.state.size and 0 <= self.state.drone_y + dy < self.state.size

    def _pick_up(self) -> None:
        if self.state.inventory is not None:
            raise GameError("The drone is already carrying an item.")
        if (self.state.drone_x, self.state.drone_y) == self.WAREHOUSE:
            self.state.inventory = "steel"
            return
        machine = self._machine_here()
        if machine.output is None:
            raise GameError("There is no finished item ready here.")
        self.state.inventory, machine.output = machine.output, None

    def _can_pick_up(self) -> bool:
        if self.state.inventory is not None:
            return False
        if (self.state.drone_x, self.state.drone_y) == self.WAREHOUSE:
            return True
        try:
            return self._machine_here().output is not None
        except GameError:
            return False

    def _drop(self) -> None:
        if self.state.inventory is None:
            raise GameError("The drone is not carrying an item.")
        if (self.state.drone_x, self.state.drone_y) == self.SHIPPING:
            item = self.state.inventory
            self.state.delivered[item] = self.state.delivered.get(item, 0) + 1
            self.state.inventory = None
            return
        self._load_machine()

    def _discard_item(self) -> None:
        if self.state.inventory is None:
            raise GameError("The drone is not carrying an item to discard.")
        self.state.inventory = None

    def _get_position(self) -> tuple[int, int]:
        return self.state.drone_x, self.state.drone_y

    def _get_inventory(self) -> str | None:
        return self.state.inventory

    def _load_machine(self) -> None:
        machine = self._machine_here()
        item = self.state.inventory
        if item is None:
            raise GameError("The drone is not carrying an item.")
        needed = Counter(machine.recipe_inputs) - Counter(machine.inputs)
        if needed[item] <= 0:
            raise GameError(f"{machine.name} does not require this item.")
        if machine.running or machine.output is not None:
            raise GameError(f"{machine.name} is not ready to be loaded.")
        machine.inputs.append(item)
        self.state.inventory = None

    def _start_machine(self) -> None:
        machine = self._machine_here()
        if machine.running or machine.output is not None:
            raise GameError(f"{machine.name} is already busy.")
        if Counter(machine.inputs) != Counter(machine.recipe_inputs):
            raise GameError(f"{machine.name} is not fully loaded yet.")
        machine.inputs.clear()
        # The generic command tick follows this call. Add one so the documented
        # processing duration starts after start_machine() has completed.
        machine.remaining = machine.duration + 1

    def _machine_is_done(self) -> bool:
        return self._machine_here().output is not None

    def _collect_output(self) -> None:
        self._pick_up()

    def _wait(self, ticks: int = 1) -> None:
        if not isinstance(ticks, int) or not 1 <= ticks <= 100:
            raise GameError("wait() expects between 1 and 100 ticks.")
        for _ in range(ticks - 1):
            self._tick()

    def _tick(self) -> None:
        self.state.ticks += 1
        for machine in self.state.machines:
            if machine.remaining > 0:
                machine.remaining -= 1
                if machine.remaining == 0:
                    machine.output = machine.recipe_output

    def mission_complete(self) -> bool:
        target = self.mission.target
        if "position" in target and [self.state.drone_x, self.state.drone_y] != target["position"]:
            return False
        for item, amount in target.get("delivered", {}).items():
            if self.state.delivered.get(item, 0) < amount:
                return False
        required = target.get("requires_call")
        return not required or self.calls[required] > 0
