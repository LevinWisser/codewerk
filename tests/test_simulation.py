import tempfile
import unittest
from pathlib import Path

from factory_game.content import MISSIONS
from factory_game.persistence import SaveStore
from factory_game.projects import load_mission_project, migrate_shared_files, store_mission_project
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
        simulation.execute("drop", [])
    simulation.execute("start_machine", [])
    while not simulation.execute("machine_is_done", []):
        simulation.execute("wait", [])
    simulation.execute("pick_up", [])


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

    def test_drop_loads_machine_and_pick_up_collects_after_exact_duration(self):
        simulation = Simulation(MISSIONS[3])
        move_to(simulation, *simulation.WAREHOUSE)
        simulation.execute("pick_up", [])
        move_to(simulation, 3, 2)
        simulation.execute("drop", [])
        simulation.execute("start_machine", [])
        self.assertFalse(simulation.execute("machine_is_done", []))
        simulation.execute("wait", [2])
        self.assertFalse(simulation.execute("machine_is_done", []))
        simulation.execute("wait", [1])
        self.assertTrue(simulation.execute("machine_is_done", []))
        simulation.execute("pick_up", [])
        self.assertEqual(simulation.state.inventory, "plate")

    def test_full_module_chain(self):
        simulation = Simulation(MISSIONS[7])
        make_product(simulation, (3, 2), ["steel"])
        move_to(simulation, 4, 4)
        simulation.execute("drop", [])
        make_product(simulation, (3, 2), ["steel"])
        move_to(simulation, 5, 2)
        simulation.execute("drop", [])
        simulation.execute("start_machine", [])
        while not simulation.execute("machine_is_done", []):
            simulation.execute("wait", [])
        simulation.execute("pick_up", [])
        move_to(simulation, 4, 4)
        simulation.execute("drop", [])
        simulation.execute("start_machine", [])
        while not simulation.execute("machine_is_done", []):
            simulation.execute("wait", [])
        simulation.execute("pick_up", [])
        move_to(simulation, *simulation.SHIPPING)
        simulation.execute("drop", [])
        self.assertTrue(simulation.mission_complete())


class SaveTests(unittest.TestCase):
    def test_save_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SaveStore(Path(directory) / "save.json")
            state = store.load()
            state["credits"] = 420
            state["projects"]["boot"] = {"main.py": "from paths import go\ngo()"}
            state["shared_files"]["paths.py"] = "def go():\n    move(East)"
            store.save(state)
            self.assertEqual(store.load()["credits"], 420)
            self.assertIn("paths.py", store.load()["shared_files"])

    def test_version_one_save_is_migrated(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "save.json"
            path.write_text('{"version": 1, "mission": 2, "unlocked": 2, "credits": 50, "codes": {"boot": "move(East)"}}', encoding="utf-8")
            state = SaveStore(path).load()
            self.assertEqual(state["version"], 3)
            self.assertEqual(state["projects"]["boot"]["main.py"], "move(East)")

    def test_version_two_completed_tutorial_enters_factory(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "save.json"
            path.write_text('{"version": 2, "mission": 7, "unlocked": 7, "credits": 3220, "projects": {}, "shared_files": {"functions.py": "pass"}}', encoding="utf-8")
            state = SaveStore(path).load()
            self.assertTrue(state["tutorial_complete"])
            self.assertEqual(state["mode"], "factory")
            self.assertIn("functions.py", state["shared_files"])


class ProjectTests(unittest.TestCase):
    def test_helpers_survive_mission_change(self):
        progress = {"projects": {}, "shared_files": {}}
        store_mission_project(progress, "boot", {"main.py": "move(East)", "functions.py": "def go():\n    move(East)"})
        next_project = load_mission_project(progress, "delivery", "pick_up()")
        self.assertEqual(next_project["main.py"], "pick_up()")
        self.assertIn("functions.py", next_project)

    def test_legacy_helpers_from_current_mission_take_precedence(self):
        progress = {
            "projects": {
                "old": {"main.py": "pass", "functions.py": "old = True"},
                "current": {"main.py": "pass", "functions.py": "new = True"},
            }
        }
        migrate_shared_files(progress, "current")
        self.assertEqual(progress["shared_files"]["functions.py"], "new = True")
        self.assertEqual(set(progress["projects"]["current"]), {"main.py"})


if __name__ == "__main__":
    unittest.main()
