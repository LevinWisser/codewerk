from __future__ import annotations

import tkinter as tk
from tkinter import ttk


BG = "#0d1218"
PANEL = "#19212b"
TEXT = "#94a3b1"
ACCENT = "#efb341"


class ConsoleWindow:
    """A modeless, resizable output window that always follows new output."""

    def __init__(self, master: tk.Tk, geometry: str | None = None):
        self.window = tk.Toplevel(master)
        self.window.title("CODEWERK // Konsole")
        self.window.configure(bg=PANEL)
        self.window.geometry(geometry or "760x300+220+620")
        self.window.minsize(420, 180)
        self.window.protocol("WM_DELETE_WINDOW", self.hide)

        header = tk.Frame(self.window, bg=PANEL, height=42)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="PROGRAMMAUSGABE", bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 9)).pack(side="left", padx=14)
        ttk.Button(header, text="LEEREN", style="Tool.TButton", command=self.clear).pack(side="right", padx=8, pady=6)

        body = tk.Frame(self.window, bg=BG)
        body.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        vertical = ttk.Scrollbar(body, orient="vertical")
        horizontal = ttk.Scrollbar(body, orient="horizontal")
        self.text = tk.Text(
            body, bg=BG, fg=TEXT, insertbackground=ACCENT, relief="flat",
            state="disabled", wrap="none", font=("Consolas", 10),
            padx=12, pady=10, yscrollcommand=vertical.set,
            xscrollcommand=horizontal.set,
        )
        vertical.configure(command=self.text.yview)
        horizontal.configure(command=self.text.xview)
        vertical.pack(side="right", fill="y")
        horizontal.pack(side="bottom", fill="x")
        self.text.pack(fill="both", expand=True)
        self.window.withdraw()

    def show(self):
        self.window.deiconify()
        self.window.lift()
        self._scroll_to_end()

    def hide(self):
        self.window.withdraw()

    def clear(self):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")

    def write(self, value: str, color: str = TEXT, reveal: bool = False):
        self.text.configure(state="normal")
        tag = f"color_{color}"
        self.text.tag_configure(tag, foreground=color)
        self.text.insert("end", value, tag)
        self.text.mark_set("insert", "end-1c")
        self.text.configure(state="disabled")
        if reveal:
            self.show()
        self.window.after_idle(self._scroll_to_end)

    def _scroll_to_end(self):
        if not self.text.winfo_exists():
            return
        self.text.see("end")
        self.text.yview_moveto(1.0)

    def geometry(self) -> str:
        return self.window.geometry()

    def destroy(self):
        self.window.destroy()
