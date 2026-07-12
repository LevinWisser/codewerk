from __future__ import annotations

import json
import queue
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any


class PythonRuntime:
    def __init__(self):
        self.process: subprocess.Popen[str] | None = None
        self.messages: queue.Queue[dict[str, Any]] = queue.Queue()

    @property
    def active(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def start(self, files: dict[str, str] | str) -> None:
        self.stop()
        worker = Path(__file__).resolve().parent.parent / "python_worker" / "worker.py"
        self.process = subprocess.Popen(
            [sys.executable, "-I", "-u", str(worker)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", bufsize=1,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        threading.Thread(target=self._read, daemon=True).start()
        if isinstance(files, str):
            files = {"main.py": files}
        self.send({"type": "run", "entry": "main.py", "files": files})

    def _read(self) -> None:
        assert self.process and self.process.stdout
        for line in self.process.stdout:
            try:
                self.messages.put(json.loads(line))
            except json.JSONDecodeError:
                self.messages.put({"type": "error", "line": 1, "message": line.strip()})

    def send(self, message: dict[str, Any]) -> None:
        if not self.active or not self.process or not self.process.stdin:
            return
        try:
            self.process.stdin.write(json.dumps(message) + "\n")
            self.process.stdin.flush()
        except (BrokenPipeError, OSError):
            pass

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.process = None
        while not self.messages.empty():
            try:
                self.messages.get_nowait()
            except queue.Empty:
                break
