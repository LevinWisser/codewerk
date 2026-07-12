from __future__ import annotations

import ast
import json
import sys
import traceback


BLOCKED_NAMES = {"__import__", "eval", "exec", "compile", "open", "input", "globals", "locals", "vars", "breakpoint", "help", "dir", "getattr", "setattr", "delattr"}
API_NAMES = ["move", "pick_up", "drop", "get_position", "get_inventory", "get_item_type", "can_move", "can_pick_up", "load_machine", "start_machine", "machine_is_done", "collect_output", "wait"]
request_id = 0


def send(message):
    sys.__stdout__.write(json.dumps(message, ensure_ascii=True) + "\n")
    sys.__stdout__.flush()


class Validator(ast.NodeVisitor):
    def visit_Import(self, node):
        raise ValueError("Imports sind in der Fabriksteuerung nicht freigeschaltet.")

    visit_ImportFrom = visit_Import

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
    if event == "line" and frame.f_code.co_filename == "<factory-code>":
        send({"type": "line", "line": frame.f_lineno})
    return trace_lines


def run(code):
    tree = ast.parse(code, filename="<factory-code>")
    Validator().visit(tree)
    compiled = compile(tree, "<factory-code>", "exec")
    safe_builtins = {
        "range": range, "len": len, "min": min, "max": max, "sum": sum,
        "enumerate": enumerate, "zip": zip, "abs": abs, "round": round,
        "bool": bool, "int": int, "float": float, "str": str,
        "list": list, "tuple": tuple, "dict": dict, "set": set,
        "print": game_print, "True": True, "False": False, "None": None,
    }
    namespace = {"__builtins__": safe_builtins, "North": "North", "East": "East", "South": "South", "West": "West"}
    for name in API_NAMES:
        namespace[name] = lambda *args, _name=name: call_api(_name, *args)
    sys.settrace(trace_lines)
    try:
        exec(compiled, namespace, namespace)
    finally:
        sys.settrace(None)


if __name__ == "__main__":
    try:
        initial = receive()
        run(initial.get("code", ""))
        send({"type": "finished"})
    except SyntaxError as error:
        send({"type": "error", "line": error.lineno or 1, "message": f"Syntaxfehler: {error.msg}"})
    except Exception as error:
        line = 1
        for frame in traceback.extract_tb(error.__traceback__):
            if frame.filename == "<factory-code>":
                line = frame.lineno
        send({"type": "error", "line": line, "message": str(error)})
