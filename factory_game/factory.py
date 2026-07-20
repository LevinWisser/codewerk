from __future__ import annotations

from collections import Counter
from copy import deepcopy
import random
from typing import Any

from factory_game.content import DIRECTIONS, FACTORY_MACHINE_DEFINITIONS, RAW_MATERIAL_PRICES, contract_duration
from factory_game.models import Machine, WorldState
from factory_game.simulation import GameError


class FactorySimulation:
    WAREHOUSE = (1, 2)
    SHIPPING = (8, 8)
    REQUEST_LIMIT = 8
    REFILL_DELAY = 15
    CONTRACT_BALANCE_VERSION = 2

    def __init__(self, credits: int = 3220, seed: int = 481516):
        self.state = WorldState(size=10, machines=[])
        self.credits = credits
        self.input_inventory: dict[str, int] = {}
        self.shipping_inventory: dict[str, int] = {}
        self.requests: dict[str, dict[str, Any]] = {}
        self.orders: dict[str, dict[str, Any]] = {}
        self.completed_orders: list[dict[str, Any]] = []
        self.request_seed = seed
        self.request_sequence = 0
        self.refill_remaining = 0
        self.recovery_grants = 0
        self.contract_balance_version = self.CONTRACT_BALANCE_VERSION
        self._fill_requests(initial=True)

    @property
    def completed_count(self) -> int:
        return len(self.completed_orders)

    @property
    def technology_level(self) -> int:
        if self.completed_count >= 8:
            return 4
        if self.completed_count >= 5:
            return 3
        if self.completed_count >= 2:
            return 2
        return 1

    @property
    def unlocked_machines(self) -> list[str]:
        levels = {
            1: ["press"],
            2: ["press", "mill", "wire_drawer"],
            3: ["press", "mill", "wire_drawer", "injection"],
            4: list(FACTORY_MACHINE_DEFINITIONS),
        }
        return levels[self.technology_level]

    @property
    def chapter_complete(self) -> bool:
        return self.completed_count >= 12 and any(order["product"] == "actuator" for order in self.completed_orders)

    def snapshot(self) -> dict[str, Any]:
        data = self.state.to_dict()
        data.update({
            "warehouse": list(self.WAREHOUSE), "shipping": list(self.SHIPPING),
            "credits": self.credits, "input_inventory": dict(self.input_inventory),
            "shipping_inventory": dict(self.shipping_inventory),
            "requests": self.get_requests(), "orders": self.get_orders(),
            "technology_level": self.technology_level,
        })
        return data

    def execute(self, command: str, args: list[Any]) -> Any:
        handlers = {
            "move": self._move, "pick_up": self._pick_up, "drop": self._drop,
            "discard_item": self._discard_item,
            "get_position": self._get_position, "get_inventory": self._get_inventory,
            "get_item_type": self._get_inventory, "can_move": self._can_move,
            "can_pick_up": self._can_pick_up, "start_machine": self._start_machine,
            "machine_is_done": self._machine_is_done, "wait": self._wait,
            "buy": self._buy, "get_credits": lambda: self.credits,
            "get_input_stock": self._get_input_stock,
            "get_shipping_stock": self._get_shipping_stock,
            "get_requests": self.get_requests, "get_orders": self.get_orders,
            "accept_request": self._accept_request, "reject_request": self._reject_request,
            "cancel_order": self._cancel_order,
            "ship": self._ship, "get_tick": lambda: self.state.ticks,
            # Compatibility with tutorial-era programs.
            "load_machine": self._load_machine, "collect_output": self._pick_up,
        }
        if command not in handlers:
            raise GameError(f"Unknown game command: {command}")
        result = handlers[command](*args)
        if command in {"move", "pick_up", "drop", "discard_item", "start_machine", "wait", "buy", "accept_request", "reject_request", "cancel_order", "ship", "load_machine", "collect_output"}:
            self._tick()
        return result

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

    def _machine_here(self) -> Machine:
        for machine in self.state.machines:
            if (machine.x, machine.y) == (self.state.drone_x, self.state.drone_y):
                return machine
        raise GameError("The drone is not standing on a machine.")

    def _pick_up(self, item: str | None = None) -> None:
        if self.state.inventory is not None:
            raise GameError("The drone is already carrying an item.")
        if (self.state.drone_x, self.state.drone_y) == self.WAREHOUSE:
            if item is None:
                available = [name for name, amount in self.input_inventory.items() if amount > 0]
                if len(available) != 1:
                    raise GameError("pick_up(item) requires a material type when multiple or no materials are in stock.")
                item = available[0]
            if self.input_inventory.get(item, 0) <= 0:
                raise GameError(f"There is no '{item}' in the input warehouse.")
            self.input_inventory[item] -= 1
            self.state.inventory = item
            return
        machine = self._machine_here()
        if item is not None:
            raise GameError("Use pick_up() without an argument at machines.")
        if machine.output is None:
            raise GameError("There is no finished item ready here.")
        self.state.inventory, machine.output = machine.output, None

    def _can_pick_up(self, item: str | None = None) -> bool:
        if self.state.inventory is not None:
            return False
        if (self.state.drone_x, self.state.drone_y) == self.WAREHOUSE:
            if item is not None:
                return self.input_inventory.get(item, 0) > 0
            return sum(amount > 0 for amount in self.input_inventory.values()) == 1
        try:
            return self._machine_here().output is not None
        except GameError:
            return False

    def _drop(self) -> None:
        if self.state.inventory is None:
            raise GameError("The drone is not carrying an item.")
        if (self.state.drone_x, self.state.drone_y) == self.SHIPPING:
            item = self.state.inventory
            self.shipping_inventory[item] = self.shipping_inventory.get(item, 0) + 1
            self.state.inventory = None
            return
        self._load_machine()

    def _discard_item(self) -> None:
        if self.state.inventory is None:
            raise GameError("The drone is not carrying an item to discard.")
        self.state.inventory = None

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
        machine.remaining = machine.duration + 1

    def _machine_is_done(self) -> bool:
        return self._machine_here().output is not None

    def _wait(self, ticks: int = 1) -> None:
        if not isinstance(ticks, int) or not 1 <= ticks <= 100:
            raise GameError("wait() expects between 1 and 100 ticks.")
        for _ in range(ticks - 1):
            self._tick()

    def _get_position(self) -> tuple[int, int]:
        return self.state.drone_x, self.state.drone_y

    def _get_inventory(self) -> str | None:
        return self.state.inventory

    def _buy(self, item: str) -> None:
        if item not in RAW_MATERIAL_PRICES:
            raise GameError(f"'{item}' is not a purchasable raw material.")
        price = RAW_MATERIAL_PRICES[item]
        if self.credits < price:
            raise GameError(f"Not enough credits: {item} costs {price}.")
        self.credits -= price
        self.input_inventory[item] = self.input_inventory.get(item, 0) + 1

    def _get_input_stock(self, item: str | None = None):
        return self.input_inventory.get(item, 0) if item is not None else dict(self.input_inventory)

    def _get_shipping_stock(self, item: str | None = None):
        return self.shipping_inventory.get(item, 0) if item is not None else dict(self.shipping_inventory)

    def get_requests(self) -> dict[str, dict[str, Any]]:
        return deepcopy(self.requests)

    def get_orders(self) -> dict[str, dict[str, Any]]:
        result = deepcopy(self.orders)
        for order in result.values():
            order["ticks_left"] = max(0, order["deadline_tick"] - self.state.ticks)
        return result

    def _accept_request(self, request_id: str) -> None:
        if request_id not in self.requests:
            raise GameError(f"Request '{request_id}' does not exist.")
        request = self.requests.pop(request_id)
        order_id = request_id.replace("REQ", "ORD", 1)
        self.orders[order_id] = {
            **request, "id": order_id,
            "accepted_tick": self.state.ticks,
            "deadline_tick": self.state.ticks + request["duration"],
        }
        self.refill_remaining = self.REFILL_DELAY

    def _reject_request(self, request_id: str) -> None:
        if request_id not in self.requests:
            raise GameError(f"Request '{request_id}' does not exist.")
        del self.requests[request_id]
        self.refill_remaining = self.REFILL_DELAY

    def _cancel_order(self, order_id: str) -> None:
        if order_id not in self.orders:
            raise GameError(f"Order '{order_id}' does not exist.")
        del self.orders[order_id]
        self.refill_remaining = self.REFILL_DELAY

    def _ship(self, order_id: str) -> int:
        if (self.state.drone_x, self.state.drone_y) != self.SHIPPING:
            raise GameError("ship() can only be used on the shipping tile.")
        if order_id not in self.orders:
            raise GameError(f"Order '{order_id}' does not exist.")
        order = self.orders[order_id]
        product, quantity = order["product"], order["quantity"]
        if self.shipping_inventory.get(product, 0) < quantity:
            raise GameError(f"Shipping stock requires {quantity}x {product} for a complete delivery.")
        on_time = self.state.ticks <= order["deadline_tick"]
        payout = order["base_payout"] + (order["on_time_bonus"] if on_time else 0)
        self.shipping_inventory[product] -= quantity
        self.credits += payout
        completed = {**order, "completed_tick": self.state.ticks, "on_time": on_time, "payout": payout}
        self.completed_orders.append(completed)
        del self.orders[order_id]
        if self.chapter_complete and self.state.size < 12:
            self.state.size = 12
        return payout

    def _tick(self) -> None:
        self.state.ticks += 1
        for machine in self.state.machines:
            if machine.remaining > 0:
                machine.remaining -= 1
                if machine.remaining == 0:
                    machine.output = machine.recipe_output
        if len(self.requests) < self.REQUEST_LIMIT:
            if self.refill_remaining > 0:
                self.refill_remaining -= 1
            if self.refill_remaining == 0:
                self._fill_requests(initial=False)
                self.refill_remaining = self.REFILL_DELAY
        self._maybe_recovery_grant()

    def _request_products(self) -> list[str]:
        products = ["plate"]
        if self.technology_level >= 2:
            products += ["gear", "wire"]
        if self.technology_level >= 3:
            products.append("housing")
        if self.technology_level >= 4:
            products.append("actuator")
        return products

    def _fill_requests(self, initial: bool) -> None:
        count = self.REQUEST_LIMIT - len(self.requests) if initial else min(1, self.REQUEST_LIMIT - len(self.requests))
        unit_costs = {"plate": 10, "gear": 10, "wire": 12, "housing": 8, "actuator": 30}
        quantity_ranges = {"plate": (2, 6), "gear": (2, 5), "wire": (3, 7), "housing": (3, 7), "actuator": (1, 3)}
        for _ in range(count):
            rng = random.Random(self.request_seed + self.request_sequence)
            self.request_sequence += 1
            product = rng.choice(self._request_products())
            low, high = quantity_ranges[product]
            quantity = rng.randint(low, high)
            cost = unit_costs[product] * quantity
            base = int(cost * 1.8) + 25
            request_id = f"REQ-{self.request_sequence:04d}"
            self.requests[request_id] = {
                "id": request_id, "product": product, "quantity": quantity,
                "base_payout": base, "on_time_bonus": max(20, base // 4),
                "duration": contract_duration(product, quantity),
            }

    def _maybe_recovery_grant(self) -> None:
        assets = sum(self.input_inventory.values()) + sum(self.shipping_inventory.values())
        assets += int(self.state.inventory is not None)
        assets += sum(len(machine.inputs) + int(machine.output is not None) for machine in self.state.machines)
        if self.credits < min(RAW_MATERIAL_PRICES.values()) and assets == 0:
            self.input_inventory["steel"] = self.input_inventory.get("steel", 0) + 5
            self.recovery_grants += 1

    def place_machine(self, kind: str, x: int, y: int) -> None:
        if kind not in self.unlocked_machines:
            raise GameError("This machine has not been unlocked yet.")
        definition = FACTORY_MACHINE_DEFINITIONS[kind]
        if self.credits < definition["cost"]:
            raise GameError(f"Not enough credits: {definition['name']} costs {definition['cost']}.")
        self._validate_build_position(x, y)
        self.credits -= definition["cost"]
        self.state.machines.append(Machine(kind, x, y, definition["name"], list(definition["inputs"]), definition["output"], definition["duration"]))

    def move_machine(self, old_x: int, old_y: int, new_x: int, new_y: int) -> None:
        machine = self.machine_at(old_x, old_y)
        if machine.running or machine.inputs or machine.output is not None:
            raise GameError("Only empty, stopped machines can be moved.")
        self._validate_build_position(new_x, new_y, ignore=machine)
        machine.x, machine.y = new_x, new_y

    def sell_machine(self, x: int, y: int) -> int:
        machine = self.machine_at(x, y)
        if machine.running or machine.inputs or machine.output is not None:
            raise GameError("Only empty, stopped machines can be sold.")
        refund = FACTORY_MACHINE_DEFINITIONS[machine.kind]["cost"] * 3 // 4
        self.state.machines.remove(machine)
        self.credits += refund
        return refund

    def machine_at(self, x: int, y: int) -> Machine:
        for machine in self.state.machines:
            if (machine.x, machine.y) == (x, y):
                return machine
        raise GameError("There is no machine at this position.")

    def _validate_build_position(self, x: int, y: int, ignore: Machine | None = None) -> None:
        if not (0 <= x < self.state.size and 0 <= y < self.state.size):
            raise GameError("This position is outside the factory.")
        if (x, y) in {self.WAREHOUSE, self.SHIPPING, (self.state.drone_x, self.state.drone_y)}:
            raise GameError("This tile is reserved or occupied by the drone.")
        if any(machine is not ignore and (machine.x, machine.y) == (x, y) for machine in self.state.machines):
            raise GameError("There is already a machine on this tile.")

    def to_save_data(self) -> dict[str, Any]:
        return {
            "state": self.state.to_dict(), "credits": self.credits,
            "input_inventory": self.input_inventory, "shipping_inventory": self.shipping_inventory,
            "requests": self.requests, "orders": self.orders, "completed_orders": self.completed_orders,
            "request_seed": self.request_seed, "request_sequence": self.request_sequence,
            "refill_remaining": self.refill_remaining, "recovery_grants": self.recovery_grants,
            "contract_balance_version": self.contract_balance_version,
        }

    @classmethod
    def from_save_data(cls, data: dict[str, Any] | None, fallback_credits: int) -> "FactorySimulation":
        if not data:
            return cls(fallback_credits)
        factory = cls.__new__(cls)
        state = data["state"]
        machines = []
        for machine_data in state.get("machines", []):
            normalized = dict(machine_data)
            definition = FACTORY_MACHINE_DEFINITIONS.get(normalized.get("kind"))
            if definition:
                normalized["name"] = definition["name"]
            machines.append(Machine(**normalized))
        factory.state = WorldState(
            size=state.get("size", 10), drone_x=state["drone"]["x"], drone_y=state["drone"]["y"],
            inventory=state["drone"].get("inventory"), ticks=state.get("ticks", 0),
            delivered=state.get("delivered", {}), machines=machines,
        )
        factory.credits = data.get("credits", fallback_credits)
        factory.input_inventory = dict(data.get("input_inventory", {}))
        factory.shipping_inventory = dict(data.get("shipping_inventory", {}))
        factory.requests = deepcopy(data.get("requests", {}))
        factory.orders = deepcopy(data.get("orders", {}))
        factory.completed_orders = deepcopy(data.get("completed_orders", []))
        factory.request_seed = data.get("request_seed", 481516)
        factory.request_sequence = data.get("request_sequence", len(factory.requests))
        factory.refill_remaining = data.get("refill_remaining", 0)
        factory.recovery_grants = data.get("recovery_grants", 0)
        factory.contract_balance_version = data.get("contract_balance_version", 1)
        if factory.contract_balance_version < cls.CONTRACT_BALANCE_VERSION:
            for request in factory.requests.values():
                request["duration"] = contract_duration(request["product"], request["quantity"])
            for order in factory.orders.values():
                old_duration = order.get("duration", 0)
                new_duration = contract_duration(order["product"], order["quantity"])
                extension = max(0, new_duration - old_duration)
                order["duration"] = new_duration
                order["deadline_tick"] = order.get("deadline_tick", order.get("accepted_tick", 0) + old_duration) + extension
            factory.contract_balance_version = cls.CONTRACT_BALANCE_VERSION
        if not factory.requests:
            factory._fill_requests(initial=True)
        return factory
