from __future__ import annotations

from dataclasses import dataclass
import math
import time
import tkinter as tk
from pathlib import Path
from typing import Any, Callable

from PIL import Image, ImageTk

from factory_game.content import ITEM_NAMES
from factory_game.design import ROOT, asset_manifest, color, design_tokens, geometry, motion


def project_iso(x: float, y: float, origin_x: float, origin_y: float, tile_width: float, tile_height: float) -> tuple[float, float]:
    return origin_x + (x - y) * tile_width / 2, origin_y + (x + y) * tile_height / 2


def unproject_iso(screen_x: float, screen_y: float, origin_x: float, origin_y: float, tile_width: float, tile_height: float) -> tuple[float, float]:
    horizontal = (screen_x - origin_x) / (tile_width / 2)
    vertical = (screen_y - origin_y) / (tile_height / 2)
    return (vertical + horizontal) / 2, (vertical - horizontal) / 2


@dataclass
class IsoCamera:
    zoom: float = 1.0
    pan_x: float = 0.0
    pan_y: float = 0.0
    user_adjusted: bool = False

    @property
    def min_zoom(self) -> float:
        return float(design_tokens()["camera"]["min_zoom"])

    @property
    def max_zoom(self) -> float:
        return float(design_tokens()["camera"]["max_zoom"])

    def clamp_zoom(self, value: float) -> float:
        return max(self.min_zoom, min(self.max_zoom, value))


class IsoRenderer:
    """Isometric presentation layer for a simulation WorldState.

    The renderer owns camera, interpolation and hit testing only. It never calls
    simulation commands or mutates the supplied state.
    """

    def __init__(self, canvas: tk.Canvas, preferences: dict[str, Any] | None = None):
        self.canvas = canvas
        preferences = preferences or {}
        self.camera = IsoCamera(
            zoom=float(preferences.get("camera_zoom", 1.0)),
            pan_x=float(preferences.get("camera_pan_x", 0.0)),
            pan_y=float(preferences.get("camera_pan_y", 0.0)),
            user_adjusted=bool(preferences.get("camera_adjusted", False)),
        )
        self.show_coordinates = bool(preferences.get("show_coordinates", False))
        self.show_item_labels = bool(preferences.get("show_item_labels", False))
        self.follow_drone = bool(preferences.get("follow_drone", False))
        self.reduced_motion = bool(preferences.get("reduced_motion", False))
        self.state = None
        self.world_size = 10
        self.warehouse = (1, 2)
        self.shipping = (8, 8)
        self.speed = "1×"
        self.display_drone: tuple[float, float] | None = None
        self.target_drone: tuple[float, float] | None = None
        self.animation_from: tuple[float, float] | None = None
        self.animation_started = 0.0
        self.animation_duration = 0.0
        self.animation_job: str | None = None
        self.hover_tile: tuple[int, int] | None = None
        self.drag_origin: tuple[int, int] | None = None
        self._image_cache: dict[tuple[str, int], ImageTk.PhotoImage] = {}
        self._static_signature = None
        self._configure_bindings()

    @property
    def tile_width(self) -> float:
        return float(geometry("tile_width")) * self.camera.zoom

    @property
    def tile_height(self) -> float:
        return float(geometry("tile_height")) * self.camera.zoom

    def _configure_bindings(self) -> None:
        self.canvas.bind("<MouseWheel>", self._on_mousewheel, add="+")
        self.canvas.bind("<ButtonPress-2>", self._start_pan, add="+")
        self.canvas.bind("<B2-Motion>", self._drag_pan, add="+")
        self.canvas.bind("<ButtonRelease-2>", self._stop_pan, add="+")
        self.canvas.bind("<Motion>", self._on_motion, add="+")
        self.canvas.bind("<Leave>", lambda _event: self._set_hover(None), add="+")

    def view_size(self) -> tuple[int, int]:
        return max(200, self.canvas.winfo_width()), max(200, self.canvas.winfo_height())

    def origin(self) -> tuple[float, float]:
        width, height = self.view_size()
        grid_height = self.world_size * self.tile_height
        return (
            width / 2 + self.camera.pan_x,
            (height - grid_height) / 2 + 42 * self.camera.zoom + self.camera.pan_y,
        )

    def project_corner(self, x: float, y: float) -> tuple[float, float]:
        ox, oy = self.origin()
        return project_iso(x, y, ox, oy, self.tile_width, self.tile_height)

    def project_center(self, x: float, y: float) -> tuple[float, float]:
        sx, sy = self.project_corner(x, y)
        return sx, sy + self.tile_height / 2

    def world_at(self, screen_x: float, screen_y: float) -> tuple[float, float]:
        ox, oy = self.origin()
        return unproject_iso(screen_x, screen_y, ox, oy, self.tile_width, self.tile_height)

    def tile_at(self, screen_x: float, screen_y: float) -> tuple[int, int] | None:
        x, y = self.world_at(screen_x, screen_y)
        tile = math.floor(x), math.floor(y)
        if 0 <= tile[0] < self.world_size and 0 <= tile[1] < self.world_size:
            return tile
        return None

    def fit(self) -> None:
        width, height = self.view_size()
        horizontal = (width - 56) / (self.world_size * float(geometry("tile_width")))
        vertical = (height - 72) / (self.world_size * float(geometry("tile_height")) + 150)
        self.camera.zoom = self.camera.clamp_zoom(min(horizontal, vertical))
        self.camera.pan_x = 0.0
        self.camera.pan_y = 0.0
        self.camera.user_adjusted = False
        self.invalidate_static()

    def zoom_by(self, factor: float, center: tuple[float, float] | None = None) -> None:
        center = center or (self.view_size()[0] / 2, self.view_size()[1] / 2)
        world_point = self.world_at(*center)
        previous = self.camera.zoom
        self.camera.zoom = self.camera.clamp_zoom(previous * factor)
        if self.camera.zoom == previous:
            return
        projected = self.project_corner(*world_point)
        self.camera.pan_x += center[0] - projected[0]
        self.camera.pan_y += center[1] - projected[1]
        self.camera.user_adjusted = True
        self.invalidate_static()

    def pan_by(self, dx: float, dy: float) -> None:
        self.camera.pan_x += dx
        self.camera.pan_y += dy
        self.camera.user_adjusted = True
        self.invalidate_static()

    def _on_mousewheel(self, event) -> str:
        self.zoom_by(1.1 if event.delta > 0 else 1 / 1.1, (event.x, event.y))
        return "break"

    def _start_pan(self, event) -> str:
        self.drag_origin = event.x, event.y
        self.canvas.configure(cursor="fleur")
        return "break"

    def _drag_pan(self, event) -> str:
        if self.drag_origin:
            old_x, old_y = self.drag_origin
            self.pan_by(event.x - old_x, event.y - old_y)
            self.drag_origin = event.x, event.y
        return "break"

    def _stop_pan(self, _event) -> str:
        self.drag_origin = None
        self.canvas.configure(cursor="")
        return "break"

    def _on_motion(self, event) -> None:
        if not self.drag_origin:
            self._set_hover(self.tile_at(event.x, event.y))

    def _set_hover(self, tile: tuple[int, int] | None) -> None:
        if tile == self.hover_tile:
            return
        self.hover_tile = tile
        self._draw_hover()

    def _draw_hover(self) -> None:
        self.canvas.delete("iso_hover")
        if self.hover_tile is None:
            return
        x, y = self.hover_tile
        top_x, top_y = self.project_corner(x, y)
        half_w, half_h = self.tile_width / 2, self.tile_height / 2
        points = (top_x, top_y, top_x + half_w, top_y + half_h, top_x, top_y + self.tile_height, top_x - half_w, top_y + half_h)
        self.canvas.create_polygon(*points, fill=color("accent"), stipple="gray50", outline=color("accent"), width=2, tags="iso_hover")
        self.canvas.create_text(top_x, top_y + half_h, text=f"{x}, {y}", fill=color("mechanics"), font=("Consolas", 9, "bold"), tags="iso_hover")

    def _asset(self, name: str) -> ImageTk.PhotoImage:
        zoom_key = max(1, round(self.camera.zoom * 100))
        key = name, zoom_key
        if key in self._image_cache:
            return self._image_cache[key]
        entry = asset_manifest()[name]
        path = ROOT / Path(entry["path"])
        with Image.open(path) as source:
            source = source.convert("RGBA")
            factor = self.camera.zoom / float(geometry("asset_scale"))
            size = max(1, round(source.width * factor)), max(1, round(source.height * factor))
            resized = source.resize(size, Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(resized, master=self.canvas)
        self._image_cache[key] = photo
        return photo

    def invalidate_static(self) -> None:
        self._static_signature = None
        self.draw()

    def set_state(self, state, warehouse: tuple[int, int], shipping: tuple[int, int], speed: str = "1×") -> None:
        self.state = state
        self.world_size = int(state.size)
        self.warehouse = warehouse
        self.shipping = shipping
        self.speed = speed
        target = float(state.drone_x), float(state.drone_y)
        if self.display_drone is None:
            self.display_drone = target
            self.target_drone = target
        elif target != self.target_drone:
            self.animation_from = self.display_drone
            self.target_drone = target
            self.animation_started = time.monotonic()
            compression = {"0.5×": 1.5, "1×": 1.0, "2×": 0.55, "4×": 0.22}.get(speed, 1.0)
            self.animation_duration = 0.0 if self.reduced_motion else float(motion("drone_move_ms")) / 1000 * compression
            if self.animation_job:
                self.canvas.after_cancel(self.animation_job)
                self.animation_job = None
            self._animate()
            return
        self.draw()

    def _animate(self) -> None:
        if not self.animation_from or not self.target_drone:
            return
        elapsed = time.monotonic() - self.animation_started
        progress = 1.0 if self.animation_duration <= 0 else min(1.0, elapsed / self.animation_duration)
        eased = progress * progress * (3 - 2 * progress)
        self.display_drone = (
            self.animation_from[0] + (self.target_drone[0] - self.animation_from[0]) * eased,
            self.animation_from[1] + (self.target_drone[1] - self.animation_from[1]) * eased,
        )
        if self.follow_drone:
            self._soft_center_on_drone()
        self.draw(dynamic_only=True)
        if progress < 1.0:
            self.animation_job = self.canvas.after(16, self._animate)
        else:
            self.display_drone = self.target_drone
            self.animation_job = None

    def _soft_center_on_drone(self) -> None:
        if not self.display_drone:
            return
        width, height = self.view_size()
        sx, sy = self.project_center(*self.display_drone)
        margin_x, margin_y = width * 0.2, height * 0.2
        dx = max(0.0, margin_x - sx) + min(0.0, width - margin_x - sx)
        dy = max(0.0, margin_y - sy) + min(0.0, height - margin_y - sy)
        self.camera.pan_x += dx * 0.18
        self.camera.pan_y += dy * 0.18
        if dx or dy:
            self._static_signature = None

    def draw(self, dynamic_only: bool = False) -> None:
        if self.state is None or not self.canvas.winfo_exists():
            return
        width, height = self.view_size()
        signature = (width, height, self.world_size, round(self.camera.zoom, 3), round(self.camera.pan_x, 1), round(self.camera.pan_y, 1), self.show_coordinates)
        if not dynamic_only and signature != self._static_signature:
            self._draw_static()
            self._static_signature = signature
        elif dynamic_only and signature != self._static_signature:
            self._draw_static()
            self._static_signature = signature
        self._draw_dynamic()
        self._draw_hover()

    def _draw_static(self) -> None:
        self.canvas.delete("iso_static")
        for diagonal in range(self.world_size * 2 - 1):
            for x in range(self.world_size):
                y = diagonal - x
                if not 0 <= y < self.world_size:
                    continue
                cx, cy = self.project_center(x, y)
                tile = self._asset("floor_a" if (x + y) % 2 == 0 else "floor_b")
                self.canvas.create_image(cx, cy, image=tile, tags="iso_static")
                if self.show_coordinates:
                    self.canvas.create_text(cx, cy, text=f"{x},{y}", fill="#71888d", font=("Consolas", max(7, round(9 * self.camera.zoom))), tags="iso_static")
        for index in range(self.world_size):
            x_x, x_y = self.project_center(index, 0)
            y_x, y_y = self.project_center(0, index)
            self.canvas.create_text(x_x + self.tile_width * .34, x_y - self.tile_height * .3, text=f"x{index}", fill="#58737a", font=("Consolas", 8), tags="iso_static")
            self.canvas.create_text(y_x - self.tile_width * .34, y_y - self.tile_height * .3, text=f"y{index}", fill="#58737a", font=("Consolas", 8), tags="iso_static")

    def _draw_dynamic(self) -> None:
        self.canvas.delete("iso_dynamic")
        entities: list[tuple[float, int, str, Any]] = [
            (sum(self.warehouse), 0, "station_warehouse", self.warehouse),
            (sum(self.shipping), 0, "station_shipping", self.shipping),
        ]
        for machine in self.state.machines:
            entities.append((machine.x + machine.y, 1, f"machine_{machine.kind}", machine))
        drone = self.display_drone or (float(self.state.drone_x), float(self.state.drone_y))
        entities.append((drone[0] + drone[1], 2, "drone_service", drone))
        for _depth, _priority, asset_name, entity in sorted(entities, key=lambda item: (item[0], item[1])):
            if isinstance(entity, tuple):
                x, y = entity
            else:
                x, y = entity.x, entity.y
            cx, _cy = self.project_center(x, y)
            _top_x, top_y = self.project_corner(x, y)
            bottom_y = top_y + self.tile_height
            if asset_name == "drone_service" and any(machine.x == round(x) and machine.y == round(y) for machine in self.state.machines):
                cx += 28 * self.camera.zoom
                bottom_y += 12 * self.camera.zoom
                self.canvas.create_line(cx - 30 * self.camera.zoom, bottom_y - 8 * self.camera.zoom, cx, bottom_y - 18 * self.camera.zoom, fill=color("hologram"), width=max(1, round(2 * self.camera.zoom)), dash=(3, 3), tags="iso_dynamic")
            image = self._asset(asset_name)
            self.canvas.create_image(cx, bottom_y, image=image, anchor="s", tags="iso_dynamic")
            if not isinstance(entity, tuple):
                self._draw_machine_status(entity, cx, bottom_y)
                if entity.output:
                    self._draw_item(entity.output, cx + 30 * self.camera.zoom, bottom_y - 38 * self.camera.zoom)
        if self.state.inventory:
            drone_x, _ = self.project_center(*drone)
            _, drone_top = self.project_corner(*drone)
            self._draw_item(self.state.inventory, drone_x + 30 * self.camera.zoom, drone_top - 8 * self.camera.zoom)

    def _draw_machine_status(self, machine, cx: float, bottom_y: float) -> None:
        width = 50 * self.camera.zoom
        y = bottom_y - 26 * self.camera.zoom
        if machine.output:
            status, ratio = color("success"), 1.0
        elif machine.running:
            status = color("hologram")
            ratio = max(0.04, min(1.0, 1 - machine.remaining / max(1, machine.duration)))
        elif machine.inputs:
            status = color("warning")
            ratio = len(machine.inputs) / max(1, len(machine.recipe_inputs))
        else:
            status, ratio = color("mechanics"), 0.18
        self.canvas.create_line(cx - width / 2, y, cx + width / 2, y, fill="#263a41", width=max(2, round(5 * self.camera.zoom)), tags="iso_dynamic")
        self.canvas.create_line(cx - width / 2, y, cx - width / 2 + width * ratio, y, fill=status, width=max(2, round(4 * self.camera.zoom)), tags="iso_dynamic")

    def _draw_item(self, item: str, x: float, y: float) -> None:
        asset_name = f"item_{item}"
        if asset_name not in asset_manifest():
            return
        image = self._asset(asset_name)
        self.canvas.create_image(x, y, image=image, anchor="s", tags="iso_dynamic")
        if self.show_item_labels:
            self.canvas.create_text(x, y + 5, text=ITEM_NAMES.get(item, item), fill=color("mechanics"), font=("Segoe UI", 8, "bold"), anchor="n", tags="iso_dynamic")

    def toggle_coordinates(self) -> bool:
        self.show_coordinates = not self.show_coordinates
        self.invalidate_static()
        return self.show_coordinates

    def toggle_item_labels(self) -> bool:
        self.show_item_labels = not self.show_item_labels
        self.draw()
        return self.show_item_labels

    def toggle_follow(self) -> bool:
        self.follow_drone = not self.follow_drone
        return self.follow_drone

    def preferences(self) -> dict[str, Any]:
        return {
            "camera_zoom": round(self.camera.zoom, 4), "camera_pan_x": round(self.camera.pan_x, 2),
            "camera_pan_y": round(self.camera.pan_y, 2), "camera_adjusted": self.camera.user_adjusted,
            "show_coordinates": self.show_coordinates, "show_item_labels": self.show_item_labels,
            "follow_drone": self.follow_drone, "reduced_motion": self.reduced_motion,
        }
