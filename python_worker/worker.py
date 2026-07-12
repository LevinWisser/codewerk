from __future__ import annotations

import ast
import json
import sys
import traceback
import types


BLOCKED_NAMES = {"__import__", "eval", "exec", "compile", "open", "input", "globals", "locals", "vars", "breakpoint", "help", "dir", "getattr", "setattr", "delattr"}
API_NAMES = [
    "move", "pick_up", "drop", "get_position", "get_inventory", "get_item_type",
    "can_move", "can_pick_up", "load_machine", "start_machine", "machine_is_done",
    "collect_output", "wait", "buy", "get_credits", "get_input_stock",
    "get_shipping_stock", "get_requests", "get_orders", "accept_request",
    "reject_request", "ship", "get_tick",
]
request_id = 0
project_filenames = set()


def send(message):
    sys.__stdout__.write(json.dumps(message, ensure_ascii=True) + "\n")
    sys.__stdout__.flush()


class Validator(ast.NodeVisitor):
    def __init__(self, allowed_modules=None):
        self.allowed_modules = set(allowed_modules or ())

    def visit_Import(self, node):
        for alias in node.names:
            if alias.name not in self.allowed_modules:
                raise ValueError(f"Nur lokale Projektdateien duerfen importiert werden: '{alias.name}' wurde nicht gefunden.")

    def visit_ImportFrom(self, node):
        if node.level or not node.module or node.module not in self.allowed_modules:
            raise ValueError("Nur absolute Imports aus lokalen Projektdateien sind erlaubt.")

    def visit_Name(self, node):
        if node.id in BLOCKED_NAMES or node.id.startswith("__"):
            raise ValueError(f"'{node.id}' ist in der Fabriksteuerung nicht verfuegbar.")
        self.generic_visit(node)

    def visit_Attribute(self, node):
        if node.attr.startswith("_"):
            raise ValueError("Interne Attribute sind nicht verfuegbar.")
        self.generic_visit(node)


def receive():
    line = sys.stdin.readline()
    if not line:
        raise SystemExit
    return json.loads(line)


def call_api(name, *args):
    global request_id
    request_id += 1
    send({"type": "call", "id": request_id, "command": name, "args": list(args)})
    response = receive()
    if response.get("type") != "result" or response.get("id") != request_id:
        raise RuntimeError("Die Verbindung zur Simulation wurde unterbrochen.")
    if not response.get("ok"):
        raise RuntimeError(response.get("error", "Spielbefehl fehlgeschlagen."))
    value = response.get("value")
    if name == "get_position" and isinstance(value, list):
        return tuple(value)
    return value


def game_print(*values, sep=" ", end="\n"):
    send({"type": "log", "text": sep.join(str(value) for value in values) + end})


def trace_lines(frame, event, arg):
    if event == "line" and frame.f_code.co_filename in project_filenames:
        send({"type": "line", "file": frame.f_code.co_filename, "line": frame.f_lineno})
    return trace_lines


def run(files, entry="main.py"):
    global project_filenames
    if entry not in files:
        raise ValueError("Das Projekt benoetigt eine main.py als Einstiegspunkt.")
    modules = {filename[:-3]: source for filename, source in files.items() if filename.endswith(".py") and filename != entry}
    project_filenames = set(files)
    trees = {}
    for filename, source in files.items():
        if not filename.endswith(".py"):
            raise ValueError(f"Ungueltige Projektdatei: {filename}")
        tree = ast.parse(source, filename=filename)
        Validator(modules).visit(tree)
        trees[filename] = tree

    safe_builtins = {
        "range": range, "len": len, "min": min, "max": max, "sum": sum,
        "enumerate": enumerate, "zip": zip, "abs": abs, "round": round,
        "bool": bool, "int": int, "float": float, "str": str,
        "list": list, "tuple": tuple, "dict": dict, "set": set,
        "print": game_print, "True": True, "False": False, "None": None,
    }
    common = {"North": "North", "East": "East", "South": "South", "West": "West"}
    for api_name in API_NAMES:
        common[api_name] = lambda *args, _name=api_name: call_api(_name, *args)

    module_cache = {}

    def execute_module(name):
        if name in module_cache:
            return module_cache[name]
        if name not in modules:
            raise ImportError(f"Lokale Datei {name}.py wurde nicht gefunden.")
        module = types.ModuleType(name)
        module_cache[name] = module
        namespace = module.__dict__
        namespace.update(common)
        namespace.update({"__builtins__": safe_builtins, "__name__": name})
        try:
            exec(compile(trees[f"{name}.py"], f"{name}.py", "exec"), namespace, namespace)
        except Exception:
            module_cache.pop(name, None)
            raise
        return module

    def local_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level or name not in modules:
            raise ImportError(f"Nur lokale Projektdateien koennen importiert werden: {name}")
        return execute_module(name)

    safe_builtins["__import__"] = local_import
    namespace = dict(common)
    namespace.update({"__builtins__": safe_builtins, "__name__": "__main__"})
    sys.settrace(trace_lines)
    try:
        exec(compile(trees[entry], entry, "exec"), namespace, namespace)
    finally:
        sys.settrace(None)


if __name__ == "__main__":
    try:
        initial = receive()
        files = initial.get("files") or {"main.py": initial.get("code", "")}
        run(files, initial.get("entry", "main.py"))
        send({"type": "finished"})
    except SyntaxError as error:
        send({"type": "error", "file": error.filename or "main.py", "line": error.lineno or 1, "message": f"Syntaxfehler: {error.msg}"})
    except Exception as error:
        line = 1
        filename = "main.py"
        for frame in traceback.extract_tb(error.__traceback__):
            if frame.filename.endswith(".py") and frame.filename in files:
                filename = frame.filename
                line = frame.lineno
        send({"type": "error", "file": filename, "line": line, "message": str(error)})
