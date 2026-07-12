from __future__ import annotations

import ast
import io
import keyword
import re
import tkinter as tk
import tokenize
from tkinter import messagebox, simpledialog, ttk

from factory_game.content import HELP


EDITOR_BG = "#0d1218"
EDITOR_FG = "#dce5ec"
PANEL = "#19212b"
ACCENT = "#efb341"
MUTED = "#94a3b1"

SYNTAX_COLORS = {
    "keyword": "#c678dd",
    "api": "#56b6c2",
    "function": "#61afef",
    "builtin": "#e5c07b",
    "constant": "#e06c75",
    "string": "#98c379",
    "number": "#d19a66",
    "comment": "#6f7f8c",
}

API_COMPLETIONS = {
    "move": "move(direction) - Drohne ein Feld bewegen",
    "pick_up": "pick_up() - Teil aufnehmen",
    "drop": "drop() - Teil im Versand ablegen",
    "get_position": "get_position() - Position als (x, y)",
    "get_inventory": "get_inventory() - getragenes Teil",
    "get_item_type": "get_item_type() - Typ des getragenen Teils",
    "can_move": "can_move(direction) - Weg pruefen",
    "can_pick_up": "can_pick_up() - Aufnahme pruefen",
    "start_machine": "start_machine() - Maschine starten",
    "machine_is_done": "machine_is_done() - Fertigstatus pruefen",
    "wait": "wait(ticks=1) - Simulation warten lassen",
    "buy": "buy(item) - einen Rohstoff bestellen",
    "get_credits": "get_credits() - aktuelle Credits",
    "get_input_stock": "get_input_stock(item=None) - Eingangslager abfragen",
    "get_shipping_stock": "get_shipping_stock(item=None) - Versandlager abfragen",
    "get_requests": "get_requests() - offene Kundenanfragen",
    "get_orders": "get_orders() - aktive Auftraege",
    "accept_request": "accept_request(request_id) - Anfrage annehmen",
    "reject_request": "reject_request(request_id) - Anfrage ablehnen",
    "ship": "ship(order_id) - Auftrag komplett ausliefern",
    "get_tick": "get_tick() - aktuellen Fabriktick abfragen",
    "North": "North - Richtung nach oben",
    "East": "East - Richtung nach rechts",
    "South": "South - Richtung nach unten",
    "West": "West - Richtung nach links",
}

BUILTIN_COMPLETIONS = {
    name: f"Python built-in: {name}"
    for name in ("range", "len", "min", "max", "sum", "enumerate", "zip", "abs", "round", "bool", "int", "float", "str", "list", "tuple", "dict", "set", "print")
}


class SymbolCollector(ast.NodeVisitor):
    def __init__(self):
        self.symbols: dict[str, str] = {}

    def visit_FunctionDef(self, node):
        args = [argument.arg for argument in node.args.args]
        self.symbols[node.name] = f"function {node.name}({', '.join(args)})"
        for argument in args:
            self.symbols[argument] = f"parameter {argument}"
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        self.symbols[node.name] = f"class {node.name}"
        self.generic_visit(node)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Store):
            self.symbols.setdefault(node.id, f"variable {node.id}")

    def visit_Import(self, node):
        for alias in node.names:
            name = alias.asname or alias.name
            self.symbols[name] = f"module {alias.name}"

    def visit_ImportFrom(self, node):
        for alias in node.names:
            if alias.name == "*":
                continue
            name = alias.asname or alias.name
            self.symbols[name] = f"import from {node.module}"


class ProjectEditor(tk.Frame):
    """Tabbed Python project editor with lightweight, local IntelliSense."""

    def __init__(self, master, on_change=None):
        super().__init__(master, bg=PANEL)
        self.on_change = on_change
        self.editors: dict[str, tk.Text] = {}
        self.popup: tk.Toplevel | None = None
        self.popup_list: tk.Listbox | None = None
        self.matches: list[str] = []
        self.completion_symbols: dict[str, str] = {}
        self.popup_detail: tk.Text | None = None
        self.completion_start = "insert"
        self.highlight_jobs: dict[tk.Text, str] = {}

        bar = tk.Frame(self, bg=PANEL)
        bar.pack(fill="x", pady=(0, 5))
        tk.Label(bar, text="DATEIEN", bg=PANEL, fg=MUTED, font=("Segoe UI Semibold", 8)).pack(side="left")
        ttk.Button(bar, text="+", style="Tool.TButton", width=3, command=self.add_file).pack(side="right")
        ttk.Button(bar, text="×", style="Tool.TButton", width=3, command=self.delete_current_file).pack(side="right", padx=(0, 4))

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)
        self.notebook.bind("<<NotebookTabChanged>>", lambda _event: self._hide_completion())

    @property
    def current_name(self) -> str:
        tab = self.notebook.select()
        return self.notebook.tab(tab, "text") if tab else "main.py"

    @property
    def current_editor(self) -> tk.Text | None:
        return self.editors.get(self.current_name)

    def set_files(self, files: dict[str, str]) -> None:
        self._hide_completion()
        for tab in self.notebook.tabs():
            self.notebook.forget(tab)
        self.editors.clear()
        normalized = dict(files) or {"main.py": ""}
        if "main.py" not in normalized:
            normalized = {"main.py": "", **normalized}
        for name, source in normalized.items():
            self._create_tab(name, source)
        self.select_file("main.py")

    def get_files(self) -> dict[str, str]:
        return {name: editor.get("1.0", "end-1c") for name, editor in self.editors.items()}

    def select_file(self, name: str) -> None:
        editor = self.editors.get(name)
        if editor:
            self.notebook.select(editor.master)
            editor.focus_set()

    def add_file(self) -> None:
        name = simpledialog.askstring("Neue Python-Datei", "Dateiname:", parent=self, initialvalue="functions.py")
        if not name:
            return
        name = name.strip()
        if not name.endswith(".py"):
            name += ".py"
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*\.py", name):
            messagebox.showerror("Ungueltiger Dateiname", "Verwende Buchstaben, Zahlen und Unterstriche; der Name muss mit einem Buchstaben oder Unterstrich beginnen.", parent=self)
            return
        if name in self.editors:
            self.select_file(name)
            return
        self._create_tab(name, "")
        self.select_file(name)
        self._changed()

    def delete_current_file(self) -> None:
        name = self.current_name
        if name == "main.py":
            messagebox.showinfo("main.py", "Die Einstiegsdatei main.py kann nicht geloescht werden.", parent=self)
            return
        if not messagebox.askyesno("Datei loeschen", f"{name} aus diesem Auftrag loeschen?", parent=self):
            return
        frame = self.editors[name].master
        self.notebook.forget(frame)
        del self.editors[name]
        self._changed()

    def _create_tab(self, name: str, source: str) -> None:
        frame = tk.Frame(self.notebook, bg=EDITOR_BG)
        editor = tk.Text(frame, bg=EDITOR_BG, fg=EDITOR_FG, insertbackground=ACCENT, selectbackground="#344b5f", relief="flat", undo=True, wrap="none", font=("Consolas", 11), padx=14, pady=12, tabs=(32,))
        scroll = ttk.Scrollbar(frame, orient="vertical", command=editor.yview)
        editor.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        editor.pack(fill="both", expand=True)
        editor.insert("1.0", source)
        editor.tag_configure("active", background="#263948")
        editor.tag_configure("error", background="#5b2928", underline=True)
        for kind, color in SYNTAX_COLORS.items():
            editor.tag_configure(f"syntax_{kind}", foreground=color)
        editor.bind("<KeyRelease>", lambda event, widget=editor: self._on_key_release(event, widget))
        editor.bind("<Control-space>", lambda event, widget=editor: self._show_completion(widget, explicit=True))
        editor.bind("<Escape>", lambda _event: self._hide_completion())
        editor.bind("<Tab>", lambda _event, widget=editor: self._completion_accept_key(widget))
        editor.bind("<Return>", lambda _event, widget=editor: self._completion_accept_key(widget))
        editor.bind("<Down>", lambda _event: self._completion_move_key(1))
        editor.bind("<Up>", lambda _event: self._completion_move_key(-1))
        self.notebook.add(frame, text=name)
        self.editors[name] = editor
        self.after_idle(lambda widget=editor: self._apply_syntax_highlighting(widget))

    def _changed(self) -> None:
        if self.on_change:
            self.on_change()

    def _on_key_release(self, event, editor):
        self._changed()
        previous = self.highlight_jobs.get(editor)
        if previous:
            self.after_cancel(previous)
        self.highlight_jobs[editor] = self.after(90, lambda widget=editor: self._apply_syntax_highlighting(widget))
        if event.keysym in {"Up", "Down", "Return", "Tab", "Escape"}:
            return
        line = editor.get("insert linestart", "insert")
        prefix = re.search(r"[A-Za-z_][A-Za-z0-9_]*$", line)
        if prefix and len(prefix.group(0)) >= 2:
            self._show_completion(editor)
        else:
            self._hide_completion()

    def _symbols(self) -> dict[str, str]:
        symbols = dict(API_COMPLETIONS)
        symbols.update(BUILTIN_COMPLETIONS)
        symbols.update({word: f"Python keyword: {word}" for word in keyword.kwlist})
        for filename in self.editors:
            if filename != "main.py":
                module = filename[:-3]
                symbols[module] = f"local module {filename}"
        for filename, source in self.get_files().items():
            collector = SymbolCollector()
            try:
                collector.visit(ast.parse(source, filename=filename))
            except SyntaxError:
                for name in re.findall(r"(?:def|class)\s+([A-Za-z_]\w*)|\b([A-Za-z_]\w*)\s*=", source):
                    symbol = name[0] or name[1]
                    collector.symbols[symbol] = f"symbol from {filename}"
            for name, description in collector.symbols.items():
                symbols[name] = f"{description}  [{filename}]"
        return symbols

    def _show_completion(self, editor, explicit=False):
        self._hide_completion()
        line = editor.get("insert linestart", "insert")
        match = re.search(r"[A-Za-z_][A-Za-z0-9_]*$", line)
        prefix = match.group(0) if match else ""
        if not explicit and len(prefix) < 2:
            self._hide_completion()
            return "break"
        symbols = self._symbols()
        self.completion_symbols = symbols
        self.matches = sorted(name for name in symbols if name.startswith(prefix) and name != prefix)
        if not self.matches:
            return "break"
        self.completion_start = f"insert-{len(prefix)}c"
        popup = tk.Toplevel(self)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        container = tk.Frame(popup, bg="#202b36", highlightbackground="#536271", highlightthickness=1)
        container.pack(fill="both", expand=True)
        listing = tk.Listbox(container, bg="#202b36", fg=EDITOR_FG, selectbackground="#3c5265", selectforeground="white", relief="flat", borderwidth=0, highlightthickness=0, font=("Consolas", 10), width=31, height=min(9, max(4, len(self.matches))), activestyle="none", exportselection=False)
        for name in self.matches:
            kind, color = self._completion_kind(name, symbols[name])
            listing.insert("end", f"{name:<20} {kind}")
            listing.itemconfig("end", fg=color)
        listing.selection_set(0)
        listing.pack(side="left", fill="both")
        separator = tk.Frame(container, bg="#536271", width=1)
        separator.pack(side="left", fill="y")
        detail_frame = tk.Frame(container, bg="#182129", padx=14, pady=11, width=330)
        detail_frame.pack(side="left", fill="both", expand=True)
        detail_frame.pack_propagate(False)
        detail_scroll = ttk.Scrollbar(detail_frame, orient="vertical")
        self.popup_detail = tk.Text(detail_frame, bg="#182129", fg=EDITOR_FG, relief="flat", borderwidth=0, highlightthickness=0, wrap="word", font=("Segoe UI", 10), cursor="arrow", yscrollcommand=detail_scroll.set, padx=0, pady=0)
        detail_scroll.configure(command=self.popup_detail.yview)
        detail_scroll.pack(side="right", fill="y")
        self.popup_detail.pack(side="left", fill="both", expand=True)
        self.popup_detail.tag_configure("kind", font=("Segoe UI Semibold", 8), spacing3=3)
        self.popup_detail.tag_configure("name", font=("Consolas", 12, "bold"), foreground=EDITOR_FG, spacing3=9)
        self.popup_detail.tag_configure("body", font=("Segoe UI", 10), foreground=EDITOR_FG, spacing3=7)
        bbox = editor.bbox("insert") or (10, 10, 0, 18)
        popup_width = 670
        popup_height = max(150, min(250, 31 * min(9, max(4, len(self.matches)))))
        x = editor.winfo_rootx() + bbox[0]
        y = editor.winfo_rooty() + bbox[1] + bbox[3] + 2
        screen_width, screen_height = editor.winfo_screenwidth(), editor.winfo_screenheight()
        x = max(8, min(x, screen_width - popup_width - 8))
        if y + popup_height > screen_height - 40:
            y = max(8, editor.winfo_rooty() + bbox[1] - popup_height - 2)
        popup.geometry(f"{popup_width}x{popup_height}+{x}+{y}")
        listing.bind("<<ListboxSelect>>", lambda _event: self._update_completion_detail())
        listing.bind("<Double-Button-1>", lambda _event: self._accept_completion(editor))
        self.popup, self.popup_list = popup, listing
        self._update_completion_detail()
        return "break"

    def _completion_kind(self, name, description):
        if name in API_COMPLETIONS:
            return "Spiel-API", SYNTAX_COLORS["api"]
        if keyword.iskeyword(name):
            return "Keyword", SYNTAX_COLORS["keyword"]
        if name in BUILTIN_COMPLETIONS:
            return "Built-in", SYNTAX_COLORS["builtin"]
        if description.startswith("function"):
            return "Funktion", SYNTAX_COLORS["function"]
        if description.startswith("class"):
            return "Klasse", SYNTAX_COLORS["constant"]
        if "module" in description:
            return "Modul", SYNTAX_COLORS["constant"]
        if description.startswith("parameter"):
            return "Parameter", EDITOR_FG
        return "Variable", EDITOR_FG

    def _update_completion_detail(self):
        if not self.popup_list or not self.popup_detail:
            return
        selection = self.popup_list.curselection()
        if not selection:
            return
        name = self.matches[selection[0]]
        description = self.completion_symbols[name]
        kind, color = self._completion_kind(name, description)
        detail = description
        if name in HELP:
            signature, explanation, example = HELP[name]
            detail = f"{signature}\n\n{explanation}\n\nBeispiel:\n{example}"
        self.popup_detail.configure(state="normal")
        self.popup_detail.delete("1.0", "end")
        self.popup_detail.tag_configure("kind", foreground=color)
        self.popup_detail.insert("end", kind.upper() + "\n", "kind")
        self.popup_detail.insert("end", name + "\n", "name")
        self.popup_detail.insert("end", detail, "body")
        self.popup_detail.configure(state="disabled")

    def _completion_accept_key(self, editor):
        if self.popup_list:
            return self._accept_completion(editor)

    def _completion_move_key(self, delta):
        if self.popup_list:
            return self._move_selection(delta)

    def _move_selection(self, delta):
        if not self.popup_list:
            return
        current = self.popup_list.curselection()
        index = (current[0] if current else 0) + delta
        index = max(0, min(index, self.popup_list.size() - 1))
        self.popup_list.selection_clear(0, "end")
        self.popup_list.selection_set(index)
        self.popup_list.see(index)
        self._update_completion_detail()
        return "break"

    def _accept_completion(self, editor):
        if not self.popup_list or not self.matches:
            return
        selection = self.popup_list.curselection()
        index = selection[0] if selection else 0
        name = self.matches[index]
        editor.delete(self.completion_start, "insert")
        editor.insert("insert", name)
        self._hide_completion()
        self._changed()
        return "break"

    def _hide_completion(self):
        if self.popup:
            try:
                self.popup.destroy()
            except tk.TclError:
                pass
        self.popup = None
        self.popup_list = None
        self.popup_detail = None
        self.matches = []
        self.completion_symbols = {}

    def _apply_syntax_highlighting(self, editor):
        self.highlight_jobs.pop(editor, None)
        for kind in SYNTAX_COLORS:
            editor.tag_remove(f"syntax_{kind}", "1.0", "end")
        source = editor.get("1.0", "end-1c")
        try:
            tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
        except (tokenize.TokenError, IndentationError):
            tokens = []
            generator = tokenize.generate_tokens(io.StringIO(source).readline)
            try:
                while True:
                    tokens.append(next(generator))
            except (StopIteration, tokenize.TokenError, IndentationError):
                pass
        ignored = {tokenize.ENCODING, tokenize.ENDMARKER, tokenize.NEWLINE, tokenize.NL, tokenize.INDENT, tokenize.DEDENT}
        meaningful = [token for token in tokens if token.type not in ignored]
        for index, token in enumerate(meaningful):
            kind = None
            if token.type == tokenize.COMMENT:
                kind = "comment"
            elif token.type == tokenize.STRING:
                kind = "string"
            elif token.type == tokenize.NUMBER:
                kind = "number"
            elif token.type == tokenize.NAME:
                previous = meaningful[index - 1].string if index else ""
                following = meaningful[index + 1].string if index + 1 < len(meaningful) else ""
                if keyword.iskeyword(token.string):
                    kind = "keyword"
                elif token.string in API_COMPLETIONS:
                    kind = "api" if token.string not in {"North", "East", "South", "West"} else "constant"
                elif token.string in BUILTIN_COMPLETIONS:
                    kind = "builtin"
                elif previous in {"def", "class"} or following == "(":
                    kind = "function"
            if kind:
                start = f"{token.start[0]}.{token.start[1]}"
                end = f"{token.end[0]}.{token.end[1]}"
                editor.tag_add(f"syntax_{kind}", start, end)

    def clear_highlights(self):
        for editor in self.editors.values():
            editor.tag_remove("active", "1.0", "end")
            editor.tag_remove("error", "1.0", "end")

    def highlight(self, filename: str, line: int, tag: str):
        self.clear_highlights()
        editor = self.editors.get(filename) or self.current_editor
        if not editor:
            return
        if filename in self.editors:
            self.select_file(filename)
        editor.tag_add(tag, f"{line}.0", f"{line}.end+1c")
        editor.see(f"{line}.0")
