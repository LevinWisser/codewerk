from __future__ import annotations

import os
import queue
import time
import tkinter as tk
from tkinter import ttk

from factory_game.content import FACTORY_MACHINE_DEFINITIONS, HELP, ITEM_NAMES, MISSIONS
from factory_game.console import ConsoleWindow
from factory_game.editor import ProjectEditor
from factory_game.factory import FactorySimulation
from factory_game.iso_renderer import IsoRenderer
from factory_game.persistence import SaveStore
from factory_game.projects import load_mission_project, migrate_shared_files, store_mission_project
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


def _enable_windows_dpi_awareness() -> None:
    if os.name != "nt":
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass


class FactoryGameApp:
    def __init__(self):
        _enable_windows_dpi_awareness()
        self.root = tk.Tk()
        self.root.title("CODEWERK // Programmierbare Fabrik")
        screen_width, screen_height = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        window_width = min(1440, max(960, screen_width - 60))
        window_height = min(880, max(680, screen_height - 90))
        self.root.geometry(f"{window_width}x{window_height}")
        self.root.minsize(min(1280, screen_width - 40), min(720, screen_height - 70))
        self.root.configure(bg=BG)
        self.store = SaveStore()
        self.progress = self.store.load()
        self.ui_preferences = self.progress.setdefault("ui_preferences", {})
        self.system_tk_scaling = float(self.root.tk.call("tk", "scaling"))
        self.root.tk.call("tk", "scaling", self.system_tk_scaling * float(self.ui_preferences.get("ui_scale", 1.0)))
        self.use_iso_renderer = os.environ.get("CODEWERK_LEGACY_RENDERER") != "1"
        self.mission_index = min(int(self.progress["mission"]), len(MISSIONS) - 1)
        migrate_shared_files(self.progress, MISSIONS[self.mission_index].id)
        self.progress["unlocked"] = max(int(self.progress["unlocked"]), self.mission_index)
        self.mode = "tutorial"
        self.simulation = Simulation(MISSIONS[self.mission_index])
        self.factory_simulation: FactorySimulation | None = None
        self.build_kind: str | None = None
        self.moving_machine: tuple[int, int] | None = None
        self.selected_machine: tuple[int, int] | None = None
        self.build_window: tk.Toplevel | None = None
        self.grid_geometry = (0.0, 0.0, 1.0)
        self.iso_renderer: IsoRenderer | None = None
        self.runtime = PythonRuntime()
        self.pending_calls: list[dict] = []
        self.paused = False
        self.step_requested = False
        self.next_action_at = 0.0
        self.completed_this_run = False
        self._configure_style()
        self._build_ui()
        if self.progress.get("tutorial_complete") and self.progress.get("mode") == "factory":
            self._load_factory(save_current=False)
        else:
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
        style.configure("View.Tool.TButton", background=PANEL_2, foreground=TEXT, padding=(6, 5), font=("Segoe UI", 9), borderwidth=0)
        style.map("View.Tool.TButton", background=[("active", "#344454")])
        style.configure("Compact.Tool.TButton", background=PANEL_2, foreground=TEXT, padding=(4, 5), font=("Segoe UI", 8), borderwidth=0)
        style.map("Compact.Tool.TButton", background=[("active", "#344454")])
        style.configure("TCombobox", fieldbackground=PANEL_2, background=PANEL_2, foreground=TEXT)
        style.configure("Factory.TNotebook", background=PANEL, borderwidth=0)
        style.configure("Factory.TNotebook.Tab", background=PANEL_2, foreground=MUTED, padding=(10, 7), borderwidth=0)
        style.map("Factory.TNotebook.Tab", background=[("selected", "#2a4149")], foreground=[("selected", TEXT)])

    def _build_ui(self):
        top = tk.Frame(self.root, bg="#0c1117", height=58)
        top.pack(fill="x")
        top.pack_propagate(False)
        tk.Label(top, text="CODEWERK", bg="#0c1117", fg=ACCENT, font=("Segoe UI Semibold", 17)).pack(side="left", padx=(18, 8))
        tk.Label(top, text="AUTOMATION LAB", bg="#0c1117", fg=MUTED, font=("Consolas", 9)).pack(side="left", pady=(6, 0))
        self.credit_label = tk.Label(top, bg="#0c1117", fg=TEXT, font=("Consolas", 11))
        self.credit_label.pack(side="right", padx=18)
        ttk.Button(top, text="EINSTELLUNGEN", style="Tool.TButton", command=self._open_settings).pack(side="right", padx=5, pady=10)
        ttk.Button(top, text="HILFE", style="Tool.TButton", command=self._open_help).pack(side="right", padx=5, pady=10)
        self.build_button = ttk.Button(top, text="BAUEN", style="Tool.TButton", command=self._open_build_window)

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
        self._build_factory_panel(left)

        center = tk.Frame(body, bg=BG)
        body.add(center, minsize=450)
        world_head = tk.Frame(center, bg=BG)
        world_head.pack(fill="x", padx=14, pady=(12, 8))
        tk.Label(world_head, text="FABRIKHALLE A", bg=BG, fg=TEXT, font=("Segoe UI Semibold", 11)).pack(side="left")
        self.coordinate_button = ttk.Button(world_head, text="KOORD", style="View.Tool.TButton", command=self._toggle_coordinates)
        self.coordinate_button.pack(side="left", padx=(12, 3))
        self.item_label_button = ttk.Button(world_head, text="ITEMS", style="View.Tool.TButton", command=self._toggle_item_labels)
        self.item_label_button.pack(side="left", padx=3)
        self.follow_button = ttk.Button(world_head, text="FOLGEN", style="View.Tool.TButton", command=self._toggle_follow)
        self.follow_button.pack(side="left", padx=3)
        ttk.Button(world_head, text="⌂", width=2, style="View.Tool.TButton", command=self._fit_camera).pack(side="left", padx=(7, 2))
        ttk.Button(world_head, text="−", width=2, style="View.Tool.TButton", command=lambda: self._zoom_camera(1 / 1.15)).pack(side="left", padx=2)
        ttk.Button(world_head, text="+", width=2, style="View.Tool.TButton", command=lambda: self._zoom_camera(1.15)).pack(side="left", padx=2)
        self.status_label = tk.Label(world_head, text="BEREIT", bg="#27343f", fg=MUTED, font=("Consolas", 9), padx=9, pady=3)
        self.status_label.pack(side="right")
        self.canvas = tk.Canvas(center, bg="#dce8e7", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        if self.use_iso_renderer:
            self.iso_renderer = IsoRenderer(self.canvas, self.ui_preferences)

        right = tk.Frame(body, bg=PANEL, width=470)
        body.add(right, minsize=380, width=470)
        editor_head = tk.Frame(right, bg=PANEL)
        editor_head.pack(fill="x", padx=12, pady=(12, 5))
        tk.Label(editor_head, text="STEUERUNG.PY", bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 10)).pack(side="left")
        self.run_button = ttk.Button(editor_head, text="▶  START", style="Accent.TButton", command=self._run_code)
        self.run_button.pack(side="right")
        self.speed = tk.StringVar(value="1×")
        speed_box = ttk.Combobox(editor_head, textvariable=self.speed, values=("0.5×", "1×", "2×", "4×"), state="readonly", width=5)
        speed_box.pack(side="right", padx=6)

        editor_controls = tk.Frame(right, bg=PANEL)
        editor_controls.pack(fill="x", padx=12, pady=(0, 7))
        self.reset_button = ttk.Button(editor_controls, text="↻  RESET", style="View.Tool.TButton", command=self._reset_mission_state)
        self.reset_button.pack(side="left")
        self.pause_button = ttk.Button(editor_controls, text="Ⅱ  PAUSE", style="View.Tool.TButton", command=self._toggle_pause)
        self.pause_button.pack(side="left", padx=4)
        self.step_button = ttk.Button(editor_controls, text="›|  SCHRITT", style="View.Tool.TButton", command=self._step)
        self.step_button.pack(side="left")

        self.code_editor = ProjectEditor(right)
        self.code_editor.pack(fill="both", expand=True, padx=12)

        console_bar = tk.Frame(right, bg=PANEL)
        console_bar.pack(fill="x", padx=12, pady=(8, 10))
        tk.Label(console_bar, text="Ausgabe in separatem Fenster", bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(side="left")
        ttk.Button(console_bar, text="KONSOLE  ↗", style="Tool.TButton", command=self._show_console).pack(side="right")
        self.console_window = ConsoleWindow(self.root, self.progress.get("console_geometry"))
        self.toast_label = tk.Label(self.root, bg="#203139", fg=TEXT, font=("Segoe UI Semibold", 10), padx=16, pady=10)
        self.toast_job = None
        self._sync_view_controls()

    def _build_factory_panel(self, parent):
        self.factory_panel = tk.Frame(parent, bg=PANEL)
        tk.Label(self.factory_panel, text="HAUPTFABRIK", bg=PANEL, fg=ACCENT, font=("Segoe UI Semibold", 14)).pack(anchor="w", padx=14, pady=(16, 2))
        self.factory_progress_label = tk.Label(self.factory_panel, bg=PANEL, fg=MUTED, justify="left", font=("Segoe UI", 9))
        self.factory_progress_label.pack(anchor="w", padx=14, pady=(0, 12))

        self.contract_notebook = ttk.Notebook(self.factory_panel, style="Factory.TNotebook")
        self.contract_notebook.pack(fill="both", expand=True, padx=10)
        self.request_tab = tk.Frame(self.contract_notebook, bg=PANEL)
        self.order_tab = tk.Frame(self.contract_notebook, bg=PANEL)
        self.contract_notebook.add(self.request_tab, text="Anfragen")
        self.contract_notebook.add(self.order_tab, text="Aufträge")
        self.contract_notebook.bind("<<NotebookTabChanged>>", self._update_contract_detail)

        request_frame = tk.Frame(self.request_tab, bg="#131a22")
        request_frame.pack(fill="both", expand=True, pady=(6, 5))
        request_scroll = ttk.Scrollbar(request_frame, orient="vertical")
        self.request_list = tk.Listbox(request_frame, bg="#131a22", fg=TEXT, selectbackground="#344454", borderwidth=0, highlightthickness=0, font=("Consolas", 8), height=8, exportselection=False, yscrollcommand=request_scroll.set)
        request_scroll.configure(command=self.request_list.yview)
        request_scroll.pack(side="right", fill="y")
        self.request_list.pack(side="left", fill="both", expand=True)
        self.request_list.bind("<<ListboxSelect>>", self._update_contract_detail)
        request_actions = tk.Frame(self.request_tab, bg=PANEL)
        request_actions.pack(fill="x")
        ttk.Button(request_actions, text="ANNEHMEN", style="Compact.Tool.TButton", command=self._accept_selected_request).pack(side="left", fill="x", expand=True)
        ttk.Button(request_actions, text="ABLEHNEN", style="Compact.Tool.TButton", command=self._reject_selected_request).pack(side="left", fill="x", expand=True, padx=(5, 0))

        order_frame = tk.Frame(self.order_tab, bg="#131a22")
        order_frame.pack(fill="both", expand=True, pady=(6, 0))
        order_scroll = ttk.Scrollbar(order_frame, orient="vertical")
        self.order_list = tk.Listbox(order_frame, bg="#131a22", fg=TEXT, selectbackground="#344454", borderwidth=0, highlightthickness=0, font=("Consolas", 8), height=8, exportselection=False, yscrollcommand=order_scroll.set)
        order_scroll.configure(command=self.order_list.yview)
        order_scroll.pack(side="right", fill="y")
        self.order_list.pack(side="left", fill="both", expand=True)
        self.order_list.bind("<<ListboxSelect>>", self._update_contract_detail)

        tk.Label(self.factory_panel, text="DETAILS", bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 8)).pack(anchor="w", padx=14, pady=(12, 3))
        self.contract_detail_label = tk.Label(self.factory_panel, text="Eintrag auswählen", bg="#203139", fg=TEXT, justify="left", anchor="nw", wraplength=215, padx=10, pady=9, font=("Segoe UI", 8))
        self.contract_detail_label.pack(fill="x", padx=10)
        self.factory_stock_label = tk.Label(self.factory_panel, bg=PANEL, fg=MUTED, justify="left", wraplength=215, font=("Consolas", 8))
        self.factory_stock_label.pack(anchor="w", padx=14, pady=(10, 5))
        ttk.Button(self.factory_panel, text="TUTORIALS", style="Tool.TButton", command=lambda: self._load_mission(7)).pack(side="bottom", fill="x", padx=10, pady=10)
        self.factory_panel.place_forget()

    def _populate_missions(self):
        self.mission_list.delete(0, "end")
        unlocked = int(self.progress["unlocked"])
        completed = set(self.progress.get("completed_tutorial_missions", []))
        for index, mission in enumerate(MISSIONS):
            prefix = "✓" if index in completed or index < unlocked else ("◆" if index == self.mission_index else "·")
            title = mission.title if index <= unlocked else f"{index + 1:02d}  Gesperrt"
            self.mission_list.insert("end", f" {prefix}  {title}")
            if index > unlocked:
                self.mission_list.itemconfig(index, fg="#596673")
        if self.progress.get("tutorial_complete"):
            self.mission_list.insert("end", " ◆  09  Hauptfabrik")
        if self.mode == "tutorial":
            self.mission_list.selection_set(self.mission_index)

    def _load_mission(self, index: int, save_current=True):
        if save_current and hasattr(self, "code_editor"):
            self._save_current_context()
        self.runtime.stop()
        self.pending_calls.clear()
        self.mode = "tutorial"
        self.progress["mode"] = "tutorial"
        self.factory_panel.place_forget()
        self.build_button.pack_forget()
        self.reset_button.configure(state="normal")
        self.mission_index = index
        mission = MISSIONS[index]
        self.simulation = Simulation(mission)
        self.completed_this_run = False
        files = load_mission_project(self.progress, mission.id, mission.starter_code)
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
        if index == len(MISSIONS) and self.progress.get("tutorial_complete"):
            self._load_factory()
            return
        if index <= int(self.progress["unlocked"]) and index != self.mission_index:
            self._load_mission(index)
        elif index > int(self.progress["unlocked"]):
            self.mission_list.selection_clear(0, "end")
            self.mission_list.selection_set(self.mission_index)

    def _load_factory(self, save_current=True):
        if not self.progress.get("tutorial_complete"):
            return
        if save_current and hasattr(self, "code_editor"):
            self._save_current_context()
        self.runtime.stop()
        self.pending_calls.clear()
        self.mode = "factory"
        self.progress["mode"] = "factory"
        if self.factory_simulation is None:
            self.factory_simulation = FactorySimulation.from_save_data(self.progress.get("factory_state"), int(self.progress["credits"]))
        self.simulation = self.factory_simulation
        self.completed_this_run = False
        files = load_mission_project(self.progress, "factory", "")
        self.code_editor.set_files(files)
        self.factory_panel.place(x=0, y=0, relwidth=1, relheight=1)
        self.factory_panel.lift()
        if not self.build_button.winfo_ismapped():
            self.build_button.pack(side="right", padx=5, pady=10)
        self.reset_button.configure(state="disabled")
        self._set_status("FABRIK", ACCENT)
        self._populate_missions()
        self._refresh()

    def _run_code(self):
        self.pending_calls.clear()
        self.completed_this_run = False
        self.paused = False
        self.code_editor.clear_highlights()
        self._console("\n--- Programm gestartet ---\n", TEXT, reveal=True)
        self.runtime.start(self.code_editor.get_files())
        self.run_button.configure(text="■  STOP", command=self._stop_code)
        self._set_status("LAEUFT", GREEN)
        self._refresh()

    def _reset_mission_state(self):
        self.runtime.stop()
        self.pending_calls.clear()
        self.simulation.reset()
        self.completed_this_run = False
        self.paused = False
        self.step_requested = False
        self.pause_button.configure(text="Ⅱ")
        self.run_button.configure(text="▶  START", command=self._run_code)
        self.code_editor.clear_highlights()
        self._console("\n--- Auftrag zurueckgesetzt ---\n", MUTED)
        self._set_status("ZURUECKGESETZT", MUTED)
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
            if self.mode == "factory":
                self._save_factory_state()
            elif self.simulation.mission_complete() and not self.completed_this_run:
                self._complete_mission()
        except (GameError, TypeError) as error:
            self.runtime.send({"type": "result", "id": message["id"], "ok": False, "error": str(error)})

    def _runtime_error(self, message):
        line = int(message.get("line", 1))
        filename = message.get("file", "main.py")
        self._highlight_line(filename, line, "error")
        self._console(f"FEHLER in {filename}, Zeile {line}: {message.get('message')}\n", RED, reveal=True)
        self._show_toast(f"Fehler in {filename}, Zeile {line}", RED)
        self._stop_code()
        self._set_status("FEHLER", RED)

    def _program_finished(self):
        if self.mode == "factory":
            self._console("Programm beendet. Die Hauptfabrik behaelt ihren aktuellen Zustand.\n", MUTED)
            self._stop_code()
            self._save_factory_state()
            return
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
        completed = self.progress.setdefault("completed_tutorial_missions", [])
        if self.mission_index not in completed:
            self.progress["credits"] = int(self.progress["credits"]) + mission.reward
            self.progress["unlocked"] = min(self.mission_index + 1, len(MISSIONS) - 1)
        self.progress["mission"] = min(self.mission_index + 1, len(MISSIONS) - 1)
        if self.mission_index not in completed:
            completed.append(self.mission_index)
        if self.mission_index == len(MISSIONS) - 1:
            self.progress["tutorial_complete"] = True
        self._store_current_project()
        self.store.save(self.progress)
        self._console(f"AUFTRAG ERFUELLT  +{mission.reward} CREDITS\n", GREEN)
        self._show_toast(f"{mission.title} erfüllt · +{mission.reward} Credits", GREEN)
        self._set_status("ERFUELLT", GREEN)
        self._populate_missions()
        def show_completion():
            next_action = self._load_factory if self.mission_index == len(MISSIONS) - 1 else None
            self._show_sheet("Auftrag erfüllt", f"{mission.title} abgeschlossen.\n\nBelohnung: {mission.reward} Credits", next_action)
        self.root.after(350, show_completion)

    def _highlight_line(self, filename, line, tag):
        self.code_editor.highlight(filename, line, tag)

    def _store_current_project(self):
        project_id = "factory" if self.mode == "factory" else MISSIONS[self.mission_index].id
        store_mission_project(self.progress, project_id, self.code_editor.get_files())

    def _save_factory_state(self):
        if self.factory_simulation is None:
            return
        self.progress["factory_state"] = self.factory_simulation.to_save_data()
        self.progress["credits"] = self.factory_simulation.credits
        if self.factory_simulation.chapter_complete and not self.progress.get("chapter_1_complete"):
            self.progress["chapter_1_complete"] = True
            self.root.after(100, lambda: self._show_sheet("Kapitel abgeschlossen", "Auftragsfertigung abgeschlossen.\n\nDie Halle wurde auf 12 × 12 erweitert. Kapitel 2 wird in einer späteren Version fortgesetzt."))
        self.store.save(self.progress)

    def _save_current_context(self):
        self._store_current_project()
        if self.mode == "factory":
            self._save_factory_state()

    def _show_console(self):
        self.console_window.show()

    def _console(self, text, color=MUTED, reveal=False):
        self.console_window.write(text, color, reveal)

    def _set_status(self, text, color):
        self.status_label.configure(text=text, fg=color)

    def _on_canvas_configure(self, _event=None):
        if self.iso_renderer and not self.iso_renderer.camera.user_adjusted and self.canvas.winfo_width() > 300:
            self.iso_renderer.fit()
        self._draw_world()

    def _fit_camera(self):
        if self.iso_renderer:
            self.iso_renderer.fit()
            self._draw_world()

    def _zoom_camera(self, factor):
        if self.iso_renderer:
            self.iso_renderer.zoom_by(factor)
            self._draw_world()

    def _toggle_coordinates(self):
        if self.iso_renderer:
            self.iso_renderer.toggle_coordinates()
            self._sync_view_controls()

    def _toggle_item_labels(self):
        if self.iso_renderer:
            self.iso_renderer.toggle_item_labels()
            self._sync_view_controls()

    def _toggle_follow(self):
        if self.iso_renderer:
            self.iso_renderer.toggle_follow()
            self._sync_view_controls()

    def _sync_view_controls(self):
        renderer = self.iso_renderer
        if not renderer:
            for button in (getattr(self, "coordinate_button", None), getattr(self, "item_label_button", None), getattr(self, "follow_button", None)):
                if button:
                    button.configure(state="disabled")
            return
        self.coordinate_button.configure(text="✓ KOORD" if renderer.show_coordinates else "KOORD")
        self.item_label_button.configure(text="✓ ITEMS" if renderer.show_item_labels else "ITEMS")
        self.follow_button.configure(text="✓ FOLGEN" if renderer.follow_drone else "FOLGEN")

    def _open_settings(self):
        window = tk.Toplevel(self.root)
        window.title("CODEWERK // Einstellungen")
        window.geometry("430x390+860+170")
        window.resizable(False, False)
        window.configure(bg=PANEL)
        tk.Label(window, text="Darstellung", bg=PANEL, fg=ACCENT, font=("Segoe UI Semibold", 15)).pack(anchor="w", padx=20, pady=(20, 4))
        tk.Label(window, text="Aqua-Lab-Ansicht und barrierearme Darstellungsoptionen", bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", padx=20, pady=(0, 16))

        scale_var = tk.StringVar(value=f"{round(float(self.ui_preferences.get('ui_scale', 1.0)) * 100)} %")
        reduced_var = tk.BooleanVar(value=bool(self.ui_preferences.get("reduced_motion", False)))
        coordinate_var = tk.BooleanVar(value=bool(self.iso_renderer and self.iso_renderer.show_coordinates))
        labels_var = tk.BooleanVar(value=bool(self.iso_renderer and self.iso_renderer.show_item_labels))
        follow_var = tk.BooleanVar(value=bool(self.iso_renderer and self.iso_renderer.follow_drone))

        row = tk.Frame(window, bg=PANEL)
        row.pack(fill="x", padx=20, pady=6)
        tk.Label(row, text="UI-Skalierung", bg=PANEL, fg=TEXT, font=("Segoe UI", 10)).pack(side="left")
        ttk.Combobox(row, textvariable=scale_var, values=("90 %", "100 %", "110 %", "125 %", "150 %"), state="readonly", width=8).pack(side="right")
        for text, variable in (
            ("Reduzierte Bewegung", reduced_var),
            ("Alle Rasterkoordinaten anzeigen", coordinate_var),
            ("Itemnamen anzeigen", labels_var),
            ("Drohne mit Kamera verfolgen", follow_var),
        ):
            tk.Checkbutton(window, text=text, variable=variable, bg=PANEL, fg=TEXT, activebackground=PANEL, activeforeground=TEXT, selectcolor=PANEL_2, font=("Segoe UI", 10), anchor="w").pack(fill="x", padx=20, pady=5)

        def apply():
            scale = int(scale_var.get().split()[0]) / 100
            self.ui_preferences["ui_scale"] = scale
            self.ui_preferences["reduced_motion"] = reduced_var.get()
            self.root.tk.call("tk", "scaling", self.system_tk_scaling * scale)
            if self.iso_renderer:
                self.iso_renderer.reduced_motion = reduced_var.get()
                self.iso_renderer.show_coordinates = coordinate_var.get()
                self.iso_renderer.show_item_labels = labels_var.get()
                self.iso_renderer.follow_drone = follow_var.get()
                self.iso_renderer.invalidate_static()
            self._sync_view_controls()
            self._save_ui_preferences()
            self.store.save(self.progress)
            self._show_toast("Darstellungseinstellungen gespeichert", GREEN)
            window.destroy()

        ttk.Button(window, text="SPEICHERN", style="Accent.TButton", command=apply).pack(side="bottom", fill="x", padx=20, pady=20)

    def _save_ui_preferences(self):
        preferences = dict(self.progress.get("ui_preferences", {}))
        preferences["ui_scale"] = float(self.ui_preferences.get("ui_scale", 1.0))
        if self.iso_renderer:
            preferences.update(self.iso_renderer.preferences())
        self.ui_preferences = preferences
        self.progress["ui_preferences"] = preferences

    def _show_toast(self, text, color=ACCENT, duration=3200):
        if self.toast_job:
            self.root.after_cancel(self.toast_job)
        self.toast_label.configure(text=text, fg=color)
        self.toast_label.place(relx=.5, y=66, anchor="n")
        self.toast_label.lift()
        self.toast_job = self.root.after(duration, self.toast_label.place_forget)

    def _show_sheet(self, title, body, on_close=None):
        existing = getattr(self, "completion_sheet", None)
        if existing and existing.winfo_exists():
            existing.destroy()
        sheet = tk.Frame(self.root, bg=PANEL_2, highlightbackground=ACCENT, highlightthickness=2, padx=28, pady=24)
        self.completion_sheet = sheet
        sheet.place(relx=.5, rely=.5, anchor="center", width=470)
        sheet.lift()
        tk.Label(sheet, text=title, bg=PANEL_2, fg=ACCENT, font=("Segoe UI Semibold", 18)).pack(anchor="w")
        tk.Label(sheet, text=body, bg=PANEL_2, fg=TEXT, justify="left", wraplength=410, font=("Segoe UI", 11)).pack(anchor="w", pady=(12, 20))

        def close():
            sheet.destroy()
            if on_close:
                on_close()

        ttk.Button(sheet, text="WEITER", style="Accent.TButton", command=close).pack(fill="x")

    def _refresh(self):
        state = self.simulation.state
        inventory = ITEM_NAMES.get(state.inventory, "leer")
        if self.mode == "factory":
            delivered = sum(self.factory_simulation.shipping_inventory.values())
            self.stats_label.configure(text=f"POSITION   {state.drone_x}, {state.drone_y}\nLADUNG     {inventory}\nTICKS      {state.ticks}\nVERSAND    {delivered}")
            self.credit_label.configure(text=f"{self.factory_simulation.credits:05d}  CR")
            self._refresh_factory_panel()
        else:
            delivered = sum(state.delivered.values())
            self.stats_label.configure(text=f"POSITION   {state.drone_x}, {state.drone_y}\nLADUNG     {inventory}\nTICKS      {state.ticks}\nVERSAND    {delivered}")
            self.credit_label.configure(text=f"{int(self.progress['credits']):05d}  CR")
        self._draw_world()

    def _refresh_factory_panel(self):
        if self.factory_simulation is None:
            return
        factory = self.factory_simulation
        self.factory_progress_label.configure(text=f"Kapitel 1  ·  Technik {factory.technology_level}/4\nAuftraege {factory.completed_count}/12")
        selected_request = self._selected_request_id() if hasattr(self, "request_ids") else None
        selected_order = self._selected_order_id() if hasattr(self, "order_ids") else None
        self.request_ids = list(factory.requests)
        self.request_list.delete(0, "end")
        for request_id in self.request_ids:
            request = factory.requests[request_id]
            product = ITEM_NAMES.get(request["product"], request["product"])
            total = request["base_payout"] + request["on_time_bonus"]
            self.request_list.insert("end", f"{request_id}  {request['quantity']}x {product[:12]}  {total} CR")
        if selected_request in self.request_ids:
            self.request_list.selection_set(self.request_ids.index(selected_request))
        self.order_ids = list(factory.orders)
        self.order_list.delete(0, "end")
        orders = factory.get_orders()
        for order_id in self.order_ids:
            order = orders[order_id]
            product = ITEM_NAMES.get(order["product"], order["product"])
            deadline = f"T-{order['ticks_left']}" if order["ticks_left"] else "SPAET"
            self.order_list.insert("end", f"{order_id}  {order['quantity']}x {product[:11]}  {deadline}")
            if not order["ticks_left"]:
                self.order_list.itemconfig("end", fg=RED)
        if selected_order in self.order_ids:
            self.order_list.selection_set(self.order_ids.index(selected_order))
        self.contract_notebook.tab(self.request_tab, text=f"Anfragen  {len(self.request_ids)}")
        self.contract_notebook.tab(self.order_tab, text=f"Aufträge  {len(self.order_ids)}")
        input_text = ", ".join(f"{ITEM_NAMES.get(item, item)}:{amount}" for item, amount in factory.input_inventory.items() if amount) or "leer"
        shipping_text = ", ".join(f"{ITEM_NAMES.get(item, item)}:{amount}" for item, amount in factory.shipping_inventory.items() if amount) or "leer"
        self.factory_stock_label.configure(text=f"EINGANG  {input_text}\nVERSAND  {shipping_text}")
        self._update_contract_detail()
        self._refresh_build_window()

    def _selected_request_id(self):
        selection = self.request_list.curselection()
        return self.request_ids[selection[0]] if selection and selection[0] < len(self.request_ids) else None

    def _selected_order_id(self):
        selection = self.order_list.curselection()
        return self.order_ids[selection[0]] if selection and selection[0] < len(self.order_ids) else None

    def _update_contract_detail(self, _event=None):
        if self.factory_simulation is None or not hasattr(self, "contract_detail_label"):
            return
        if self.contract_notebook.index("current") == 0:
            request_id = self._selected_request_id()
            request = self.factory_simulation.requests.get(request_id) if request_id else None
            if request:
                product = ITEM_NAMES.get(request["product"], request["product"])
                total = request["base_payout"] + request["on_time_bonus"]
                text = f"{request_id} · {product}\n{request['quantity']} Stück · {total} CR gesamt\nBasis {request['base_payout']} · Bonus {request['on_time_bonus']}\nBonusfrist {request['duration']} Ticks"
            else:
                text = "Anfrage auswählen"
        else:
            order_id = self._selected_order_id()
            order = self.factory_simulation.get_orders().get(order_id) if order_id else None
            if order:
                product = ITEM_NAMES.get(order["product"], order["product"])
                deadline = f"noch {order['ticks_left']} Ticks" if order["ticks_left"] else "verspätet · Basis bleibt erhalten"
                text = f"{order_id} · {product}\n{order['quantity']} Stück · {deadline}\nBasis {order['base_payout']} · Bonus {order['on_time_bonus']}"
            else:
                text = "Aktiven Auftrag auswählen"
        self.contract_detail_label.configure(text=text)

    def _accept_selected_request(self):
        request_id = self._selected_request_id()
        if request_id:
            self._factory_ui_command("accept_request", [request_id])

    def _reject_selected_request(self):
        request_id = self._selected_request_id()
        if request_id:
            self._factory_ui_command("reject_request", [request_id])

    def _factory_ui_command(self, command, args):
        if self.factory_simulation is None:
            return
        try:
            result = self.factory_simulation.execute(command, args)
            self._console(f"UI: {command}({', '.join(map(str, args))})\n", MUTED)
            self._refresh()
            self._save_factory_state()
            return result
        except GameError as error:
            self._console(f"FEHLER: {error}\n", RED, reveal=True)
            self._show_toast(str(error), RED)

    def _open_build_window(self):
        if self.mode != "factory" or self.factory_simulation is None:
            return
        if self.runtime.active and not self.paused:
            self._toggle_pause()
        if self.build_window and self.build_window.winfo_exists():
            self.build_window.deiconify()
            self.build_window.lift()
            self._refresh_build_window()
            return
        window = tk.Toplevel(self.root)
        window.title("CODEWERK // Baumodus")
        window.geometry("430x500+980+160")
        window.minsize(380, 400)
        window.configure(bg=PANEL)
        window.protocol("WM_DELETE_WINDOW", window.withdraw)
        self.build_window = window
        tk.Label(window, text="MASCHINENBAU", bg=PANEL, fg=ACCENT, font=("Segoe UI Semibold", 14)).pack(anchor="w", padx=16, pady=(16, 4))
        tk.Label(window, text="Kaufen, dann ein freies Rasterfeld anklicken.", bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", padx=16, pady=(0, 10))
        self.build_machine_frame = tk.Frame(window, bg=PANEL)
        self.build_machine_frame.pack(fill="both", expand=True, padx=12)
        tk.Frame(window, bg="#33404c", height=1).pack(fill="x", padx=14, pady=8)
        self.build_selection_label = tk.Label(window, text="Keine Maschine ausgewaehlt", bg=PANEL, fg=MUTED, font=("Segoe UI", 9))
        self.build_selection_label.pack(anchor="w", padx=16)
        actions = tk.Frame(window, bg=PANEL)
        actions.pack(fill="x", padx=12, pady=(8, 14))
        self.move_machine_button = ttk.Button(actions, text="VERSCHIEBEN", style="Tool.TButton", command=self._begin_move_machine)
        self.move_machine_button.pack(side="left", fill="x", expand=True)
        self.sell_machine_button = ttk.Button(actions, text="VERKAUFEN", style="Tool.TButton", command=self._sell_selected_machine)
        self.sell_machine_button.pack(side="left", fill="x", expand=True, padx=(6, 0))
        self._refresh_build_window()

    def _refresh_build_window(self):
        if not self.build_window or not self.build_window.winfo_exists() or not hasattr(self, "build_machine_frame") or self.factory_simulation is None:
            return
        for child in self.build_machine_frame.winfo_children():
            child.destroy()
        unlocked = set(self.factory_simulation.unlocked_machines)
        for kind, definition in FACTORY_MACHINE_DEFINITIONS.items():
            row = tk.Frame(self.build_machine_frame, bg="#202b36")
            row.pack(fill="x", pady=3)
            tk.Label(row, text=f"{definition['name']}\n{definition['cost']} CR", bg="#202b36", fg=TEXT if kind in unlocked else MUTED, justify="left", font=("Segoe UI", 9)).pack(side="left", padx=10, pady=7)
            button = ttk.Button(row, text="KAUFEN", style="Tool.TButton", command=lambda selected=kind: self._select_build_kind(selected))
            button.pack(side="right", padx=7, pady=7)
            if kind not in unlocked:
                button.configure(state="disabled")
        selected = self.selected_machine
        if selected:
            try:
                machine = self.factory_simulation.machine_at(*selected)
                self.build_selection_label.configure(text=f"Ausgewaehlt: {machine.name} bei {selected}")
                self.move_machine_button.configure(state="normal")
                self.sell_machine_button.configure(state="normal")
            except GameError:
                self.selected_machine = None
        if not self.selected_machine:
            self.build_selection_label.configure(text="Keine Maschine ausgewaehlt")
            self.move_machine_button.configure(state="disabled")
            self.sell_machine_button.configure(state="disabled")

    def _select_build_kind(self, kind):
        self.build_kind = kind
        self.moving_machine = None
        definition = FACTORY_MACHINE_DEFINITIONS[kind]
        self._set_status(f"PLATZIEREN: {definition['name'].upper()}", ACCENT)
        if self.build_window:
            self.build_window.withdraw()

    def _begin_move_machine(self):
        if self.selected_machine:
            self.moving_machine = self.selected_machine
            self.build_kind = None
            self._set_status("NEUE POSITION WAEHLEN", ACCENT)
            self.build_window.withdraw()

    def _sell_selected_machine(self):
        if not self.selected_machine:
            return
        try:
            refund = self.factory_simulation.sell_machine(*self.selected_machine)
            self._console(f"Maschine verkauft: +{refund} Credits\n", GREEN)
            self.selected_machine = None
            self._refresh()
            self._save_factory_state()
        except GameError as error:
            self._console(f"FEHLER: {error}\n", RED, reveal=True)
            self._show_toast(str(error), RED)

    def _on_canvas_click(self, event):
        if self.mode != "factory" or self.factory_simulation is None:
            return
        if self.iso_renderer:
            tile = self.iso_renderer.tile_at(event.x, event.y)
            if tile is None:
                return
            x, y = tile
        else:
            ox, oy, cell = self.grid_geometry
            x, y = int((event.x - ox) // cell), int((event.y - oy) // cell)
        if not (0 <= x < self.simulation.state.size and 0 <= y < self.simulation.state.size):
            return
        try:
            if self.build_kind:
                kind = self.build_kind
                self.factory_simulation.place_machine(kind, x, y)
                self._console(f"{FACTORY_MACHINE_DEFINITIONS[kind]['name']} bei ({x}, {y}) gebaut.\n", GREEN)
                self.build_kind = None
                self._set_status("FABRIK", ACCENT)
            elif self.moving_machine:
                old = self.moving_machine
                self.factory_simulation.move_machine(*old, x, y)
                self._console(f"Maschine von {old} nach ({x}, {y}) verschoben.\n", GREEN)
                self.moving_machine = None
                self.selected_machine = (x, y)
                self._set_status("FABRIK", ACCENT)
            else:
                self.factory_simulation.machine_at(x, y)
                self.selected_machine = (x, y)
                self._open_build_window()
            self._refresh()
            self._save_factory_state()
        except GameError as error:
            if not self.build_kind and not self.moving_machine:
                self.selected_machine = None
                return
            self._console(f"FEHLER: {error}\n", RED, reveal=True)
            self._show_toast(str(error), RED)

    def _draw_world(self):
        if self.iso_renderer:
            self.iso_renderer.set_state(self.simulation.state, self.simulation.WAREHOUSE, self.simulation.SHIPPING, self.speed.get())
            return
        self._draw_world_legacy()

    def _draw_world_legacy(self):
        if not self.canvas.winfo_exists():
            return
        self.canvas.delete("all")
        state = self.simulation.state
        width, height = max(self.canvas.winfo_width(), 200), max(self.canvas.winfo_height(), 200)
        cell = min((width - 60) / state.size, (height - 60) / state.size)
        ox = (width - cell * state.size) / 2
        oy = (height - cell * state.size) / 2
        self.grid_geometry = (ox, oy, cell)
        for y in range(state.size):
            for x in range(state.size):
                x1, y1 = ox + x * cell, oy + y * cell
                self.canvas.create_rectangle(x1, y1, x1 + cell, y1 + cell, fill=GRID_A if (x + y) % 2 == 0 else GRID_B, outline="#3b4b57")
                self.canvas.create_text(x1 + 5, y1 + 5, text=f"{x},{y}", fill="#647481", anchor="nw", font=("Consolas", max(7, int(cell / 10))))
        self._draw_station(*self.simulation.WAREHOUSE, "MAT", BLUE, cell, ox, oy)
        self._draw_station(*self.simulation.SHIPPING, "OUT", GREEN, cell, ox, oy)
        for machine in state.machines:
            color = ACCENT if machine.running else (GREEN if machine.output else "#8996a3")
            label = {"press": "PRS", "mill": "FRS", "assembly": "ASM", "wire_drawer": "DRT", "injection": "SGS"}.get(machine.kind, "MCH")
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
        if self.mode == "factory" or "all" in allowed:
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
        self.progress["mode"] = self.mode
        self.progress["console_geometry"] = self.console_window.geometry()
        self._save_ui_preferences()
        self._save_current_context()
        self.store.save(self.progress)
        self.runtime.stop()
        self.console_window.destroy()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
