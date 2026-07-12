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
        process = subprocess.Popen([sys.executable, "-I", "-u", str(WORKER)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8")
        self.process = process
        process.stdin.write(json.dumps({"type": "run", "code": code}) + "\n")
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
        self.assertIn("Imports", error["message"])
        process.wait(timeout=2)


if __name__ == "__main__":
    unittest.main()
