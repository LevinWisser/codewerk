from __future__ import annotations

import queue
import time
import tkinter as tk
from tkinter import messagebox, ttk

from factory_game.content import HELP, ITEM_NAMES, MISSIONS
from factory_game.editor import ProjectEditor
from factory_game.persistence import SaveStore
from factory_game.runtime import PythonRuntime
from factory_game.simulation import GameError, Simulation


BG = "#11161d"
PANEL = "#19212b"
PANEL_2 = "#202b36"
GRID_A = "#27343f"
GRID_B = "#2b3944"
TEXT = "#e8edf2"
MUTED = "#94a3b1"
ACCENT = "#efb341"
GREEN = "#52b788"
RED = "#e76f51"
BLUE = "#4ea8de"


class FactoryGameApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("CODEWERK // Programmierbare Fabrik")
        self.root.geometry("1440x880")
        self.root.minsize(1080, 700)
        self.root.configure(bg=BG)
        self.store = SaveStore()
        self.progress = self.store.load()
        self.mission_index = min(int(self.progress["mission"]), len(MISSIONS) - 1)
        self.progress["unlocked"] = max(int(self.progress["unlocked"]), self.mission_index)
        self.simulation = Simulation(MISSIONS[self.mission_index])
        self.runtime = PythonRuntime()
        self.pending_calls: list[dict] = []
        self.paused = False
        self.step_requested = False
        self.next_action_at = 0.0
        self.completed_this_run = False
        self._configure_style()
        self._build_ui()
        self._load_mission(self.mission_index, save_current=False)
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.root.after(20, self._poll_runtime)

    def _configure_style(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("Title.TLabel", foreground=TEXT, font=("Segoe UI Semibold", 13))
        style.configure("Accent.TButton", background=ACCENT, foreground="#15191d", font=("Segoe UI Semibold", 10), padding=(13, 8), borderwidth=0)
        style.map("Accent.TButton", background=[("active", "#ffc857"), ("disabled", "#5b5549")])
        style.configure("Tool.TButton", background=PANEL_2, foreground=TEXT, padding=(10, 7), borderwidth=0)
        style.map("Tool.TButton", background=[("active", "#344454")])
        style.configure("TCombobox", fieldbackground=PANEL_2, background=PANEL_2, foreground=TEXT)

    def _build_ui(self):
        top = tk.Frame(self.root, bg="#0c1117", height=58)
        top.pack(fill="x")
        top.pack_propagate(False)
        tk.Label(top, text="CODEWERK", bg="#0c1117", fg=ACCENT, font=("Segoe UI Semibold", 17)).pack(side="left", padx=(18, 8))
        tk.Label(top, text="AUTOMATION LAB", bg="#0c1117", fg=MUTED, font=("Consolas", 9)).pack(side="left", pady=(6, 0))
        self.credit_label = tk.Label(top, bg="#0c1117", fg=TEXT, font=("Consolas", 11))
        self.credit_label.pack(side="right", padx=18)
        ttk.Button(top, text="HILFE", style="Tool.TButton", command=self._open_help).pack(side="right", padx=5, pady=10)

        body = tk.PanedWindow(self.root, orient="horizontal", bg=BG, sashwidth=5, sashrelief="flat")
        body.pack(fill="both", expand=True)

        left = tk.Frame(body, bg=PANEL, width=250)
        body.add(left, minsize=220, width=250)
        tk.Label(left, text="AUFTRAEGE", bg=PANEL, fg=MUTED, font=("Segoe UI Semibold", 9)).pack(anchor="w", padx=16, pady=(18, 9))
        self.mission_list = tk.Listbox(left, bg=PANEL, fg=TEXT, selectbackground="#344454", selectforeground=TEXT, activestyle="none", borderwidth=0, highlightthickness=0, font=("Segoe UI", 10), exportselection=False)
        self.mission_list.pack(fill="x", padx=8)
        self.mission_list.bind("<<ListboxSelect>>", self._on_mission_select)
        tk.Frame(left, bg="#33404c", height=1).pack(fill="x", padx=14, pady=16)
        self.brief_title = tk.Label(left, bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 12), justify="left", wraplength=210)
        self.brief_title.pack(anchor="w", padx=16)
        self.brief_text = tk.Label(left, bg=PANEL, fg=MUTED, font=("Segoe UI", 10), justify="left", wraplength=210)
        self.brief_text.pack(anchor="w", padx=16, pady=(7, 12))
        self.goal_label = tk.Label(left, bg="#24322f", fg="#a8e6c5", font=("Segoe UI Semibold", 10), justify="left", wraplength=198, padx=10, pady=10)
        self.goal_label.pack(fill="x", padx=12)
        self.stats_label = tk.Label(left, bg=PANEL, fg=MUTED, font=("Consolas", 9), justify="left")
        self.stats_label.pack(anchor="w", padx=16, pady=15)

        center = tk.Frame(body, bg=BG)
        body.add(center, minsize=450)
        world_head = tk.Frame(center, bg=BG)
        world_head.pack(fill="x", padx=14, pady=(12, 8))
        tk.Label(world_head, text="FABRIKHALLE A", bg=BG, fg=TEXT, font=("Segoe UI Semibold", 11)).pack(side="left")
        self.status_label = tk.Label(world_head, text="BEREIT", bg="#27343f", fg=MUTED, font=("Consolas", 9), padx=9, pady=3)
        self.status_label.pack(side="right")
        self.canvas = tk.Canvas(center, bg="#0f151b", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self.canvas.bind("<Configure>", lambda _event: self._draw_world())

        right = tk.Frame(body, bg=PANEL, width=470)
        body.add(right, minsize=380, width=470)
        editor_head = tk.Frame(right, bg=PANEL)
        editor_head.pack(fill="x", padx=12, pady=(12, 8))
        tk.Label(editor_head, text="STEUERUNG.PY", bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 10)).pack(side="left")
        self.run_button = ttk.Button(editor_head, text="▶  START", style="Accent.TButton", command=self._run_code)
        self.run_button.pack(side="right")
        self.pause_button = ttk.Button(editor_head, text="Ⅱ", style="Tool.TButton", command=self._toggle_pause, width=3)
        self.pause_button.pack(side="right", padx=5)
        self.step_button = ttk.Button(editor_head, text="›|", style="Tool.TButton", command=self._step, width=3)
        self.step_button.pack(side="right")
        self.speed = tk.StringVar(value="1×")
        speed_box = ttk.Combobox(editor_head, textvariable=self.speed, values=("0.5×", "1×", "2×", "4×"), state="readonly", width=5)
        speed_box.pack(side="right", padx=6)

        self.code_editor = ProjectEditor(right)
        self.code_editor.pack(fill="both", expand=True, padx=12)

        console_head = tk.Frame(right, bg=PANEL)
        console_head.pack(fill="x", padx=12, pady=(9, 4))
        tk.Label(console_head, text="KONSOLE", bg=PANEL, fg=MUTED, font=("Segoe UI Semibold", 9)).pack(side="left")
        ttk.Button(console_head, text="LEEREN", style="Tool.TButton", command=lambda: self.console.delete("1.0", "end")).pack(side="right")
        self.console = tk.Text(right, height=7, bg="#0d1218", fg=MUTED, relief="flat", state="disabled", font=("Consolas", 9), padx=10, pady=8)
        self.console.pack(fill="x", padx=12, pady=(0, 12))

    def _populate_missions(self):
        self.mission_list.delete(0, "end")
        unlocked = int(self.progress["unlocked"])
        for index, mission in enumerate(MISSIONS):
            prefix = "✓" if index < unlocked else ("◆" if index == self.mission_index else "·")
            title = mission.title if index <= unlocked else f"{index + 1:02d}  Gesperrt"
            self.mission_list.insert("end", f" {prefix}  {title}")
            if index > unlocked:
                self.mission_list.itemconfig(index, fg="#596673")
        self.mission_list.selection_set(self.mission_index)

    def _load_mission(self, index: int, save_current=True):
        if save_current and hasattr(self, "code_editor"):
            self._store_current_project()
        self.runtime.stop()
        self.pending_calls.clear()
        self.mission_index = index
        mission = MISSIONS[index]
        self.simulation = Simulation(mission)
        self.completed_this_run = False
        files = self.progress["projects"].get(mission.id, {"main.py": mission.starter_code})
        self.code_editor.set_files(files)
        self.brief_title.configure(text=mission.title)
        self.brief_text.configure(text=f"{mission.brief}\n\n{mission.concept}")
        self.goal_label.configure(text="ZIEL\n" + mission.goal_text)
        self._set_status("BEREIT", MUTED)
        self._populate_missions()
        self._refresh()

    def _on_mission_select(self, _event):
        selection = self.mission_list.curselection()
        if not selection:
            return
        index = selection[0]
        if index <= int(self.progress["unlocked"]) and index != self.mission_index:
            self._load_mission(index)
        elif index > int(self.progress["unlocked"]):
            self.mission_list.selection_clear(0, "end")
            self.mission_list.selection_set(self.mission_index)

    def _run_code(self):
        self.simulation.reset()
        self.pending_calls.clear()
        self.completed_this_run = False
        self.paused = False
        self.code_editor.clear_highlights()
        self._console("\n--- Programm gestartet ---\n", TEXT)
        self.runtime.start(self.code_editor.get_files())
        self.run_button.configure(text="■  STOP", command=self._stop_code)
        self._set_status("LAEUFT", GREEN)
        self._refresh()

    def _stop_code(self):
        self.runtime.stop()
        self.pending_calls.clear()
        self.run_button.configure(text="▶  START", command=self._run_code)
        self._set_status("GESTOPPT", MUTED)

    def _toggle_pause(self):
        if not self.runtime.active:
            return
        self.paused = not self.paused
        self.pause_button.configure(text="▶" if self.paused else "Ⅱ")
        self._set_status("PAUSE" if self.paused else "LAEUFT", ACCENT if self.paused else GREEN)

    def _step(self):
        if self.runtime.active:
            self.paused = True
            self.step_requested = True
            self.pause_button.configure(text="▶")
            self._set_status("EINZELSCHRITT", ACCENT)

    def _poll_runtime(self):
        try:
            while True:
                message = self.runtime.messages.get_nowait()
                kind = message.get("type")
                if kind == "call":
                    self.pending_calls.append(message)
                elif kind == "line":
                    self._highlight_line(message.get("file", "main.py"), int(message.get("line", 1)), "active")
                elif kind == "log":
                    self._console(message.get("text", ""), TEXT)
                elif kind == "error":
                    self._runtime_error(message)
                elif kind == "finished":
                    self._program_finished()
        except queue.Empty:
            pass
        now = time.monotonic()
        if self.pending_calls and (not self.paused or self.step_requested) and now >= self.next_action_at:
            self.step_requested = False
            self._execute_call(self.pending_calls.pop(0))
            delay = {"0.5×": 0.65, "1×": 0.32, "2×": 0.14, "4×": 0.04}.get(self.speed.get(), 0.32)
            self.next_action_at = now + delay
        self.root.after(20, self._poll_runtime)

    def _execute_call(self, message):
        try:
            value = self.simulation.execute(message["command"], message.get("args", []))
            self.runtime.send({"type": "result", "id": message["id"], "ok": True, "value": value})
            self._refresh()
            if self.simulation.mission_complete() and not self.completed_this_run:
                self._complete_mission()
        except (GameError, TypeError) as error:
            self.runtime.send({"type": "result", "id": message["id"], "ok": False, "error": str(error)})

    def _runtime_error(self, message):
        line = int(message.get("line", 1))
        filename = message.get("file", "main.py")
        self._highlight_line(filename, line, "error")
        self._console(f"FEHLER in {filename}, Zeile {line}: {message.get('message')}\n", RED)
        self._stop_code()
        self._set_status("FEHLER", RED)

    def _program_finished(self):
        if not self.completed_this_run:
            self._console("Programm beendet. Das Auftragsziel ist noch nicht erreicht.\n", MUTED)
            self._stop_code()

    def _complete_mission(self):
        self.completed_this_run = True
        self.runtime.stop()
        self.pending_calls.clear()
        self.run_button.configure(text="▶  START", command=self._run_code)
        mission = MISSIONS[self.mission_index]
        previous_unlocked = int(self.progress["unlocked"])
        if self.mission_index >= previous_unlocked:
            self.progress["credits"] = int(self.progress["credits"]) + mission.reward
            self.progress["unlocked"] = min(self.mission_index + 1, len(MISSIONS) - 1)
        self.progress["mission"] = min(self.mission_index + 1, len(MISSIONS) - 1)
        self._store_current_project()
        self.store.save(self.progress)
        self._console(f"AUFTRAG ERFUELLT  +{mission.reward} CREDITS\n", GREEN)
        self._set_status("ERFUELLT", GREEN)
        self._populate_missions()
        self.root.after(350, lambda: messagebox.showinfo("Auftrag erfuellt", f"{mission.title} abgeschlossen.\n\nBelohnung: {mission.reward} Credits"))

    def _highlight_line(self, filename, line, tag):
        self.code_editor.highlight(filename, line, tag)

    def _store_current_project(self):
        self.progress["projects"][MISSIONS[self.mission_index].id] = self.code_editor.get_files()

    def _console(self, text, color=MUTED):
        self.console.configure(state="normal")
        tag = f"color_{color}"
        self.console.tag_configure(tag, foreground=color)
        self.console.insert("end", text, tag)
        self.console.see("end")
        self.console.configure(state="disabled")

    def _set_status(self, text, color):
        self.status_label.configure(text=text, fg=color)

    def _refresh(self):
        state = self.simulation.state
        inventory = ITEM_NAMES.get(state.inventory, "leer")
        delivered = sum(state.delivered.values())
        self.stats_label.configure(text=f"POSITION   {state.drone_x}, {state.drone_y}\nLADUNG     {inventory}\nTICKS      {state.ticks}\nVERSAND    {delivered}")
        self.credit_label.configure(text=f"{int(self.progress['credits']):05d}  CR")
        self._draw_world()

    def _draw_world(self):
        if not self.canvas.winfo_exists():
            return
        self.canvas.delete("all")
        state = self.simulation.state
        width, height = max(self.canvas.winfo_width(), 200), max(self.canvas.winfo_height(), 200)
        cell = min((width - 60) / state.size, (height - 60) / state.size)
        ox = (width - cell * state.size) / 2
        oy = (height - cell * state.size) / 2
        for y in range(state.size):
            for x in range(state.size):
                x1, y1 = ox + x * cell, oy + y * cell
                self.canvas.create_rectangle(x1, y1, x1 + cell, y1 + cell, fill=GRID_A if (x + y) % 2 == 0 else GRID_B, outline="#3b4b57")
                self.canvas.create_text(x1 + 5, y1 + 5, text=f"{x},{y}", fill="#647481", anchor="nw", font=("Consolas", max(7, int(cell / 10))))
        self._draw_station(*self.simulation.WAREHOUSE, "MAT", BLUE, cell, ox, oy)
        self._draw_station(*self.simulation.SHIPPING, "OUT", GREEN, cell, ox, oy)
        for machine in state.machines:
            color = ACCENT if machine.running else (GREEN if machine.output else "#8996a3")
            label = {"press": "PRS", "mill": "FRS", "assembly": "ASM"}[machine.kind]
            self._draw_station(machine.x, machine.y, label, color, cell, ox, oy)
            if machine.running:
                ratio = 1 - machine.remaining / machine.duration
                x1 = ox + machine.x * cell + cell * .14
                y1 = oy + (machine.y + 1) * cell - cell * .15
                self.canvas.create_rectangle(x1, y1, x1 + cell * .72, y1 + 4, fill="#111820", outline="")
                self.canvas.create_rectangle(x1, y1, x1 + cell * .72 * ratio, y1 + 4, fill=ACCENT, outline="")
        cx = ox + (state.drone_x + .5) * cell
        cy = oy + (state.drone_y + .5) * cell
        radius = cell * .23
        self.canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, fill="#f4f7fa", outline="#17212a", width=3)
        self.canvas.create_line(cx - radius * 1.5, cy, cx + radius * 1.5, cy, fill="#f4f7fa", width=max(3, int(cell / 13)))
        self.canvas.create_oval(cx - 3, cy - 3, cx + 3, cy + 3, fill=ACCENT, outline="")
        if state.inventory:
            self.canvas.create_oval(cx + radius * .55, cy - radius * .9, cx + radius * 1.25, cy - radius * .2, fill=ACCENT, outline="#111")

    def _draw_station(self, x, y, label, color, cell, ox, oy):
        margin = cell * .12
        x1, y1 = ox + x * cell + margin, oy + y * cell + margin
        self.canvas.create_rectangle(x1, y1, x1 + cell - margin * 2, y1 + cell - margin * 2, fill="#182129", outline=color, width=max(2, int(cell / 24)))
        self.canvas.create_text(x1 + (cell - margin * 2) / 2, y1 + (cell - margin * 2) / 2, text=label, fill=color, font=("Consolas", max(9, int(cell / 7)), "bold"))

    def _open_help(self):
        window = tk.Toplevel(self.root)
        window.title("CODEWERK // Hilfe")
        window.geometry("850x620")
        window.configure(bg=BG)
        left = tk.Frame(window, bg=PANEL, width=250)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        tk.Label(left, text="API & PYTHON", bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 13)).pack(anchor="w", padx=16, pady=(18, 10))
        search_var = tk.StringVar()
        search = tk.Entry(left, textvariable=search_var, bg="#0d1218", fg=TEXT, insertbackground=TEXT, relief="flat", font=("Segoe UI", 10))
        search.pack(fill="x", padx=12, ipady=7)
        entries = tk.Listbox(left, bg=PANEL, fg=TEXT, selectbackground="#344454", borderwidth=0, highlightthickness=0, font=("Segoe UI", 10), exportselection=False)
        entries.pack(fill="both", expand=True, padx=8, pady=10)
        content = tk.Text(window, bg=BG, fg=TEXT, relief="flat", wrap="word", font=("Segoe UI", 11), padx=28, pady=24)
        content.pack(side="left", fill="both", expand=True)
        content.tag_configure("title", font=("Consolas", 17, "bold"), foreground=ACCENT, spacing3=15)
        content.tag_configure("body", font=("Segoe UI", 11), foreground=TEXT, spacing3=18)
        content.tag_configure("code", font=("Consolas", 11), foreground="#b9e6ff", background="#17212a", lmargin1=12, lmargin2=12, spacing1=10, spacing3=10)

        allowed = set()
        for i in range(self.mission_index + 1):
            allowed.update(MISSIONS[i].unlocked_docs)
        allowed.add("files")
        if "all" in allowed:
            allowed = set(HELP)

        def fill(*_):
            query = search_var.get().lower()
            entries.delete(0, "end")
            for key in HELP:
                if key in allowed and (query in key.lower() or query in HELP[key][0].lower()):
                    entries.insert("end", key)

        def show(_event=None):
            selection = entries.curselection()
            if not selection:
                return
            key = entries.get(selection[0])
            title, description, code = HELP[key]
            content.configure(state="normal")
            content.delete("1.0", "end")
            content.insert("end", title + "\n", "title")
            content.insert("end", description + "\n", "body")
            content.insert("end", code + "\n", "code")
            content.configure(state="disabled")

        search_var.trace_add("write", fill)
        entries.bind("<<ListboxSelect>>", show)
        fill()
        if entries.size():
            entries.selection_set(0)
            show()
        search.focus_set()

    def _close(self):
        self.progress["mission"] = self.mission_index
        self._store_current_project()
        self.store.save(self.progress)
        self.runtime.stop()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
