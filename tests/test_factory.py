import unittest

from factory_game.factory import FactorySimulation
from factory_game.simulation import GameError


def move_to(factory, target_x, target_y):
    while factory.state.drone_x < target_x:
        factory.execute("move", ["East"])
    while factory.state.drone_x > target_x:
        factory.execute("move", ["West"])
    while factory.state.drone_y < target_y:
        factory.execute("move", ["South"])
    while factory.state.drone_y > target_y:
        factory.execute("move", ["North"])


def produce_plate(factory):
    factory.execute("buy", ["steel"])
    move_to(factory, *factory.WAREHOUSE)
    factory.execute("pick_up", ["steel"])
    move_to(factory, 3, 2)
    factory.execute("drop", [])
    factory.execute("start_machine", [])
    factory.execute("wait", [3])
    factory.execute("pick_up", [])
    move_to(factory, *factory.SHIPPING)
    factory.execute("drop", [])


class FactoryEconomyTests(unittest.TestCase):
    def test_buy_costs_one_tick_and_stock_can_be_queried(self):
        factory = FactorySimulation(credits=100)
        factory.execute("buy", ["copper"])
        self.assertEqual(factory.credits, 88)
        self.assertEqual(factory.state.ticks, 1)
        self.assertEqual(factory.execute("get_input_stock", ["copper"]), 1)
        self.assertEqual(factory.execute("get_input_stock", []), {"copper": 1})

    def test_pick_up_requires_item_with_multiple_stocks(self):
        factory = FactorySimulation()
        factory.execute("buy", ["steel"])
        factory.execute("buy", ["copper"])
        move_to(factory, *factory.WAREHOUSE)
        with self.assertRaises(GameError):
            factory.execute("pick_up", [])
        factory.execute("pick_up", ["copper"])
        self.assertEqual(factory.state.inventory, "copper")

    def test_discard_item_clears_drone_inventory_and_costs_one_tick(self):
        factory = FactorySimulation()
        factory.state.inventory = "steel"
        before_tick = factory.state.ticks
        factory.execute("discard_item", [])
        self.assertIsNone(factory.state.inventory)
        self.assertEqual(factory.state.ticks, before_tick + 1)

        with self.assertRaises(GameError):
            factory.execute("discard_item", [])
        self.assertEqual(factory.state.ticks, before_tick + 1)

    def test_build_move_and_sell_machine(self):
        factory = FactorySimulation(credits=2000)
        factory.place_machine("press", 3, 2)
        self.assertEqual(factory.credits, 1500)
        factory.move_machine(3, 2, 4, 2)
        self.assertEqual((factory.state.machines[0].x, factory.state.machines[0].y), (4, 2))
        refund = factory.sell_machine(4, 2)
        self.assertEqual(refund, 375)
        self.assertEqual(factory.credits, 1875)

    def test_locked_machine_cannot_be_built(self):
        factory = FactorySimulation(credits=5000)
        with self.assertRaises(GameError):
            factory.place_machine("assembly", 4, 4)


class ContractTests(unittest.TestCase):
    def test_requests_are_deterministic_and_capped(self):
        first = FactorySimulation(seed=123)
        second = FactorySimulation(seed=123)
        self.assertEqual(first.get_requests(), second.get_requests())
        self.assertEqual(len(first.requests), 8)

    def test_accept_and_reject_refill_after_delay(self):
        factory = FactorySimulation()
        ids = list(factory.requests)
        factory.execute("accept_request", [ids[0]])
        factory.execute("reject_request", [ids[1]])
        self.assertEqual(len(factory.requests), 6)
        factory.execute("wait", [15])
        self.assertGreaterEqual(len(factory.requests), 7)
        self.assertEqual(len(factory.orders), 1)

    def test_ship_is_atomic_when_stock_is_missing(self):
        factory = FactorySimulation()
        request_id = next(iter(factory.requests))
        factory.execute("accept_request", [request_id])
        order_id = next(iter(factory.orders))
        move_to(factory, *factory.SHIPPING)
        before = factory.get_orders()
        with self.assertRaises(GameError):
            factory.execute("ship", [order_id])
        self.assertEqual(factory.get_orders(), before)
        self.assertEqual(factory.shipping_inventory, {})

    def test_accepted_order_can_be_cancelled_without_penalty(self):
        factory = FactorySimulation()
        request_id = next(iter(factory.requests))
        factory.execute("accept_request", [request_id])
        order_id = request_id.replace("REQ", "ORD", 1)
        credits = factory.credits

        factory.execute("cancel_order", [order_id])

        self.assertNotIn(order_id, factory.orders)
        self.assertEqual(factory.credits, credits)
        self.assertEqual(factory.completed_orders, [])
        self.assertEqual(factory.refill_remaining, factory.REFILL_DELAY - 1)

        with self.assertRaises(GameError):
            factory.execute("cancel_order", [order_id])

    def test_late_delivery_keeps_base_and_loses_bonus(self):
        factory = FactorySimulation(credits=0)
        request_id = next(iter(factory.requests))
        factory.execute("accept_request", [request_id])
        order_id, order = next(iter(factory.orders.items()))
        factory.shipping_inventory[order["product"]] = order["quantity"]
        factory.state.ticks = order["deadline_tick"] + 1
        move_to(factory, *factory.SHIPPING)
        payout = factory.execute("ship", [order_id])
        self.assertEqual(payout, order["base_payout"])

    def test_three_parallel_orders_through_real_production(self):
        factory = FactorySimulation(credits=5000)
        request_ids = list(factory.requests)[:3]
        for request_id in request_ids:
            factory.execute("accept_request", [request_id])
        orders = list(factory.orders.items())
        total_plates = sum(order["quantity"] for _, order in orders)
        factory.place_machine("press", 3, 2)
        for _ in range(total_plates):
            produce_plate(factory)
        for order_id, _order in orders:
            factory.execute("ship", [order_id])
        self.assertEqual(len(factory.completed_orders), 3)
        self.assertEqual(factory.shipping_inventory.get("plate"), 0)
        self.assertGreater(factory.credits, 0)

    def test_factory_round_trip(self):
        factory = FactorySimulation(credits=2000, seed=77)
        factory.place_machine("press", 3, 2)
        request_id = next(iter(factory.requests))
        factory.execute("accept_request", [request_id])
        restored = FactorySimulation.from_save_data(factory.to_save_data(), 0)
        self.assertEqual(restored.snapshot(), factory.snapshot())
        self.assertEqual(restored.get_orders(), factory.get_orders())

    def test_saved_machine_display_names_are_normalized_to_english(self):
        factory = FactorySimulation(credits=2000)
        factory.place_machine("press", 3, 2)
        saved = factory.to_save_data()
        saved["state"]["machines"][0]["name"] = "Legacy Press Name"

        restored = FactorySimulation.from_save_data(saved, 0)

        self.assertEqual(restored.state.machines[0].name, "Press")


if __name__ == "__main__":
    unittest.main()
