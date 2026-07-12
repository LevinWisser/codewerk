import json
import subprocess
import sys
import unittest
from pathlib import Path


WORKER = Path(__file__).resolve().parent.parent / "python_worker" / "worker.py"


class WorkerTests(unittest.TestCase):
    def tearDown(self):
        process = getattr(self, "process", None)
        if process is not None:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=2)
            if process.stdin:
                process.stdin.close()
            if process.stdout:
                process.stdout.close()

    def start_worker(self, code):
        return self.start_project({"main.py": code})

    def start_project(self, files):
        process = subprocess.Popen([sys.executable, "-I", "-u", str(WORKER)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8")
        self.process = process
        process.stdin.write(json.dumps({"type": "run", "entry": "main.py", "files": files}) + "\n")
        process.stdin.flush()
        return process

    def read_until(self, process, kind):
        for _ in range(20):
            message = json.loads(process.stdout.readline())
            if message.get("type") == kind:
                return message
        self.fail(f"Worker did not emit {kind}")

    def test_api_round_trip(self):
        process = self.start_worker("move(East)\nx, y = get_position()\nprint(x, y)")
        call = self.read_until(process, "call")
        self.assertEqual(call["command"], "move")
        process.stdin.write(json.dumps({"type": "result", "id": call["id"], "ok": True, "value": None}) + "\n")
        process.stdin.flush()
        call = self.read_until(process, "call")
        self.assertEqual(call["command"], "get_position")
        process.stdin.write(json.dumps({"type": "result", "id": call["id"], "ok": True, "value": [2, 1]}) + "\n")
        process.stdin.flush()
        log = self.read_until(process, "log")
        self.assertEqual(log["text"], "2 1\n")
        self.read_until(process, "finished")
        process.wait(timeout=2)

    def test_import_is_rejected(self):
        process = self.start_worker("import os")
        error = self.read_until(process, "error")
        self.assertIn("lokale Projektdateien", error["message"])
        process.wait(timeout=2)

    def test_local_module_import(self):
        process = self.start_project({
            "main.py": "from paths import go\ngo()",
            "paths.py": "def go():\n    move(East)",
        })
        call = self.read_until(process, "call")
        self.assertEqual(call["command"], "move")
        process.stdin.write(json.dumps({"type": "result", "id": call["id"], "ok": True, "value": None}) + "\n")
        process.stdin.flush()
        self.read_until(process, "finished")
        process.wait(timeout=2)

    def test_star_import_from_local_module(self):
        process = self.start_project({
            "main.py": "from positions import *\nprint(PRESS)",
            "positions.py": "PRESS = (3, 2)",
        })
        log = self.read_until(process, "log")
        self.assertEqual(log["text"], "(3, 2)\n")
        self.read_until(process, "finished")
        process.wait(timeout=2)

    def test_module_error_reports_filename(self):
        process = self.start_project({"main.py": "import paths", "paths.py": "move(Unknown)"})
        error = self.read_until(process, "error")
        self.assertEqual(error["file"], "paths.py")
        self.assertEqual(error["line"], 1)


if __name__ == "__main__":
    unittest.main()
