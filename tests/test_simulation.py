import tempfile
import unittest
from pathlib import Path

from factory_game.content import MISSIONS
from factory_game.persistence import SaveStore
from factory_game.simulation import GameError, Simulation


def move_to(simulation, target_x, target_y):
    while simulation.state.drone_x < target_x:
        simulation.execute("move", ["East"])
    while simulation.state.drone_x > target_x:
        simulation.execute("move", ["West"])
    while simulation.state.drone_y < target_y:
        simulation.execute("move", ["South"])
    while simulation.state.drone_y > target_y:
        simulation.execute("move", ["North"])


def make_product(simulation, machine_position, input_items):
    for item in input_items:
        if item == "steel":
            move_to(simulation, *simulation.WAREHOUSE)
            simulation.execute("pick_up", [])
        else:
            raise AssertionError("Test helper expects preloaded non-steel items")
        move_to(simulation, *machine_position)
        simulation.execute("load_machine", [])
    simulation.execute("start_machine", [])
    while not simulation.execute("machine_is_done", []):
        simulation.execute("wait", [])
    simulation.execute("collect_output", [])


class SimulationTests(unittest.TestCase):
    def test_move_and_bounds(self):
        simulation = Simulation(MISSIONS[0])
        simulation.execute("move", ["North"])
        self.assertEqual((simulation.state.drone_x, simulation.state.drone_y), (1, 0))
        with self.assertRaises(GameError):
            simulation.execute("move", ["North"])

    def test_first_mission_completes(self):
        simulation = Simulation(MISSIONS[0])
        simulation.execute("move", ["East"])
        simulation.execute("move", ["East"])
        self.assertTrue(simulation.mission_complete())

    def test_warehouse_delivery(self):
        simulation = Simulation(MISSIONS[1])
        move_to(simulation, *simulation.WAREHOUSE)
        simulation.execute("pick_up", [])
        move_to(simulation, *simulation.SHIPPING)
        simulation.execute("drop", [])
        self.assertEqual(simulation.state.delivered, {"steel": 1})
        self.assertTrue(simulation.mission_complete())

    def test_press_recipe(self):
        simulation = Simulation(MISSIONS[3])
        make_product(simulation, (3, 2), ["steel"])
        self.assertEqual(simulation.state.inventory, "plate")
        move_to(simulation, *simulation.SHIPPING)
        simulation.execute("drop", [])
        self.assertTrue(simulation.mission_complete())

    def test_full_module_chain(self):
        simulation = Simulation(MISSIONS[7])
        make_product(simulation, (3, 2), ["steel"])
        move_to(simulation, 4, 4)
        simulation.execute("load_machine", [])
        make_product(simulation, (3, 2), ["steel"])
        move_to(simulation, 5, 2)
        simulation.execute("load_machine", [])
        simulation.execute("start_machine", [])
        while not simulation.execute("machine_is_done", []):
            simulation.execute("wait", [])
        simulation.execute("collect_output", [])
        move_to(simulation, 4, 4)
        simulation.execute("load_machine", [])
        simulation.execute("start_machine", [])
        while not simulation.execute("machine_is_done", []):
            simulation.execute("wait", [])
        simulation.execute("collect_output", [])
        move_to(simulation, *simulation.SHIPPING)
        simulation.execute("drop", [])
        self.assertTrue(simulation.mission_complete())


class SaveTests(unittest.TestCase):
    def test_save_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SaveStore(Path(directory) / "save.json")
            state = store.load()
            state["credits"] = 420
            state["projects"]["boot"] = {"main.py": "from paths import go\ngo()", "paths.py": "def go():\n    move(East)"}
            store.save(state)
            self.assertEqual(store.load()["credits"], 420)
            self.assertIn("paths.py", store.load()["projects"]["boot"])

    def test_version_one_save_is_migrated(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "save.json"
            path.write_text('{"version": 1, "mission": 2, "unlocked": 2, "credits": 50, "codes": {"boot": "move(East)"}}', encoding="utf-8")
            state = SaveStore(path).load()
            self.assertEqual(state["version"], 2)
            self.assertEqual(state["projects"]["boot"]["main.py"], "move(East)")


if __name__ == "__main__":
    unittest.main()
