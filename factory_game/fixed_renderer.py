from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
import time
import tkinter as tk
from typing import Any

from PIL import Image, ImageTk

from factory_game.content import ITEM_NAMES
from factory_game.design import ROOT, asset_manifest, color, design_tokens, motion


LAYOUT_PATH = ROOT / "assets" / "runtime" / "fixed" / "world" / "layouts.json"


@lru_cache(maxsize=1)
def fixed_layouts() -> dict[str, Any]:
    return json.loads(LAYOUT_PATH.read_text(encoding="utf-8"))["layouts"]


def point_in_polygon(point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
    """Return whether a point lies inside a convex or concave screen polygon."""
    px, py = point
    inside = False
    previous = polygon[-1]
    for current in polygon:
        x1, y1 = previous
        x2, y2 = current
        if (y1 > py) != (y2 > py):
            crossing = (x2 - x1) * (py - y1) / (y2 - y1) + x1
            if px < crossing:
                inside = not inside
        previous = current
    return inside


@dataclass
class FixedCamera:
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


class FixedViewRenderer:
    """Fixed-camera 2.5D presentation layer backed by Blender renders."""

    ASSET_PATHS = {
        "drone_service": "assets/runtime/fixed/drone/drone_service.png",
        "station_warehouse": "assets/runtime/fixed/stations/station_warehouse.png",
        "station_shipping": "assets/runtime/fixed/stations/station_shipping.png",
        "machine_press": "assets/runtime/fixed/machines/machine_press.png",
        "machine_mill": "assets/runtime/fixed/machines/machine_mill.png",
        "machine_wire_drawer": "assets/runtime/fixed/machines/machine_wire_drawer.png",
        "machine_injection": "assets/runtime/fixed/machines/machine_injection.png",
        "machine_assembly": "assets/runtime/fixed/machines/machine_assembly.png",
    }

    def __init__(self, canvas: tk.Canvas, preferences: dict[str, Any] | None = None):
        self.canvas = canvas
        preferences = preferences or {}
        fixed_camera_preferences = preferences.get("camera_projection") == "fixed_v1"
        self.camera = FixedCamera(
            zoom=float(preferences.get("camera_zoom", 1.0)) if fixed_camera_preferences else 1.0,
            pan_x=float(preferences.get("camera_pan_x", 0.0)) if fixed_camera_preferences else 0.0,
            pan_y=float(preferences.get("camera_pan_y", 0.0)) if fixed_camera_preferences else 0.0,
            user_adjusted=bool(preferences.get("camera_adjusted", False)) if fixed_camera_preferences else False,
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
        self._background_cache: dict[tuple[int, int, int], ImageTk.PhotoImage] = {}
        self._sprite_sources: dict[str, Image.Image] = {}
        self._sprite_cache: dict[tuple[str, int], ImageTk.PhotoImage] = {}
        self._static_signature = None
        self._configure_bindings()

    def _configure_bindings(self) -> None:
        self.canvas.bind("<MouseWheel>", self._on_mousewheel, add="+")
        self.canvas.bind("<ButtonPress-2>", self._start_pan, add="+")
        self.canvas.bind("<B2-Motion>", self._drag_pan, add="+")
        self.canvas.bind("<ButtonRelease-2>", self._stop_pan, add="+")
        self.canvas.bind("<Motion>", self._on_motion, add="+")
        self.canvas.bind("<Leave>", lambda _event: self._set_hover(None), add="+")

    def view_size(self) -> tuple[int, int]:
        return max(200, self.canvas.winfo_width()), max(200, self.canvas.winfo_height())

    def _layout(self) -> dict[str, Any]:
        layouts = fixed_layouts()
        key = str(self.world_size)
        if key not in layouts:
            key = min(layouts, key=lambda value: abs(int(value) - self.world_size))
        return layouts[key]

    def _base_scale(self) -> float:
        width, height = self.view_size()
        source_width, source_height = self._layout()["render_size"]
        return min((width - 20) / source_width, (height - 20) / source_height)

    def _scale(self) -> float:
        return self._base_scale() * self.camera.zoom

    def _image_origin(self) -> tuple[float, float]:
        width, height = self.view_size()
        source_width, source_height = self._layout()["render_size"]
        scale = self._scale()
        return (
            (width - source_width * scale) / 2 + self.camera.pan_x,
            (height - source_height * scale) / 2 + self.camera.pan_y,
        )

    def _screen_point(self, normalized: list[float] | tuple[float, float]) -> tuple[float, float]:
        source_width, source_height = self._layout()["render_size"]
        origin_x, origin_y = self._image_origin()
        scale = self._scale()
        return origin_x + normalized[0] * source_width * scale, origin_y + normalized[1] * source_height * scale

    def tile_center(self, x: float, y: float) -> tuple[float, float]:
        ix = max(0, min(self.world_size - 1, int(round(x))))
        iy = max(0, min(self.world_size - 1, int(round(y))))
        base = self._layout()["tiles"][f"{ix},{iy}"]["center"]
        cx, cy = self._screen_point(base)
        dx, dy = x - ix, y - iy
        if dx:
            neighbor_x = max(0, min(self.world_size - 1, ix + (1 if dx > 0 else -1)))
            if neighbor_x != ix:
                nx, ny = self._screen_point(self._layout()["tiles"][f"{neighbor_x},{iy}"]["center"])
                cx += (nx - cx) * abs(dx)
                cy += (ny - cy) * abs(dx)
        if dy:
            neighbor_y = max(0, min(self.world_size - 1, iy + (1 if dy > 0 else -1)))
            if neighbor_y != iy:
                nx, ny = self._screen_point(self._layout()["tiles"][f"{ix},{neighbor_y}"]["center"])
                cx += (nx - cx) * abs(dy)
                cy += (ny - cy) * abs(dy)
        return cx, cy

    def tile_polygon(self, x: int, y: int) -> list[tuple[float, float]]:
        points = self._layout()["tiles"][f"{x},{y}"]["polygon"]
        return [self._screen_point(point) for point in points]

    def tile_at(self, screen_x: float, screen_y: float) -> tuple[int, int] | None:
        for y in range(self.world_size - 1, -1, -1):
            for x in range(self.world_size):
                polygon = self.tile_polygon(x, y)
                if point_in_polygon((screen_x, screen_y), polygon):
                    return x, y
        return None

    def fit(self) -> None:
        self.camera.zoom = 1.0
        self.camera.pan_x = 0.0
        self.camera.pan_y = 0.0
        self.camera.user_adjusted = False
        self.invalidate_static()

    def zoom_by(self, factor: float, center: tuple[float, float] | None = None) -> None:
        center = center or (self.view_size()[0] / 2, self.view_size()[1] / 2)
        old_origin = self._image_origin()
        old_scale = self._scale()
        source_x = (center[0] - old_origin[0]) / old_scale
        source_y = (center[1] - old_origin[1]) / old_scale
        previous = self.camera.zoom
        self.camera.zoom = self.camera.clamp_zoom(previous * factor)
        if self.camera.zoom == previous:
            return
        new_origin = self._image_origin()
        new_scale = self._scale()
        self.camera.pan_x += center[0] - (new_origin[0] + source_x * new_scale)
        self.camera.pan_y += center[1] - (new_origin[1] + source_y * new_scale)
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
        self.canvas.delete("fixed_hover")
        if self.hover_tile is None:
            return
        x, y = self.hover_tile
        points = [coordinate for point in self.tile_polygon(x, y) for coordinate in point]
        self.canvas.create_polygon(
            *points, fill=color("accent"), stipple="gray50", outline=color("accent"),
            width=2, tags="fixed_hover",
        )
        cx, cy = self.tile_center(x, y)
        self.canvas.create_text(cx, cy, text=f"{x}, {y}", fill=color("mechanics"), font=("Consolas", 9, "bold"), tags="fixed_hover")

    def _background(self) -> ImageTk.PhotoImage:
        layout = self._layout()
        source_width, source_height = layout["render_size"]
        scale = self._scale()
        width, height = max(1, round(source_width * scale)), max(1, round(source_height * scale))
        key = self.world_size, width, height
        if key not in self._background_cache:
            with Image.open(ROOT / Path(layout["image"])) as source:
                resized = source.convert("RGBA").resize((width, height), Image.Resampling.LANCZOS)
            self._background_cache.clear()
            self._background_cache[key] = ImageTk.PhotoImage(resized, master=self.canvas)
        return self._background_cache[key]

    def _sprite_source(self, name: str) -> Image.Image:
        if name not in self._sprite_sources:
            if name in self.ASSET_PATHS:
                path = ROOT / self.ASSET_PATHS[name]
            else:
                path = ROOT / Path(asset_manifest()[name]["path"])
            with Image.open(path) as source:
                image = source.convert("RGBA")
            alpha = image.getchannel("A")
            bbox = alpha.getbbox()
            self._sprite_sources[name] = image.crop(bbox) if bbox else image
        return self._sprite_sources[name]

    def _sprite(self, name: str, target_width: float) -> ImageTk.PhotoImage:
        width = max(2, round(target_width / 2) * 2)
        key = name, width
        if key not in self._sprite_cache:
            source = self._sprite_source(name)
            height = max(1, round(source.height * width / source.width))
            resized = source.resize((width, height), Image.Resampling.LANCZOS)
            self._sprite_cache[key] = ImageTk.PhotoImage(resized, master=self.canvas)
        return self._sprite_cache[key]

    def _tile_dimensions(self, x: int, y: int) -> tuple[float, float]:
        polygon = self.tile_polygon(x, y)
        width = max(point[0] for point in polygon) - min(point[0] for point in polygon)
        height = max(point[1] for point in polygon) - min(point[1] for point in polygon)
        return width, height

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
        sx, sy = self.tile_center(*self.display_drone)
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
        signature = (
            *self.view_size(), self.world_size, round(self.camera.zoom, 3),
            round(self.camera.pan_x, 1), round(self.camera.pan_y, 1), self.show_coordinates,
        )
        if signature != self._static_signature:
            self._draw_static()
            self._static_signature = signature
        self._draw_dynamic()
        self._draw_hover()

    def _draw_static(self) -> None:
        self.canvas.delete("fixed_static")
        origin_x, origin_y = self._image_origin()
        self.canvas.create_image(origin_x, origin_y, image=self._background(), anchor="nw", tags="fixed_static")
        if self.show_coordinates:
            for y in range(self.world_size):
                for x in range(self.world_size):
                    cx, cy = self.tile_center(x, y)
                    self.canvas.create_text(
                        cx, cy, text=f"{x},{y}", fill="#58737a",
                        font=("Consolas", max(7, round(9 * self.camera.zoom))), tags="fixed_static",
                    )

    def _draw_dynamic(self) -> None:
        self.canvas.delete("fixed_dynamic")
        entities: list[tuple[float, int, str, Any]] = [
            (self.warehouse[1], 0, "station_warehouse", self.warehouse),
            (self.shipping[1], 0, "station_shipping", self.shipping),
        ]
        for machine in self.state.machines:
            entities.append((machine.y, 1, f"machine_{machine.kind}", machine))
        drone = self.display_drone or (float(self.state.drone_x), float(self.state.drone_y))
        entities.append((drone[1], 2, "drone_service", drone))
        for _depth, _priority, asset_name, entity in sorted(entities, key=lambda item: (item[0], item[1])):
            if isinstance(entity, tuple):
                x, y = entity
            else:
                x, y = entity.x, entity.y
            ix, iy = int(round(x)), int(round(y))
            cx, cy = self.tile_center(x, y)
            tile_width, tile_height = self._tile_dimensions(ix, iy)
            if asset_name == "drone_service":
                self.canvas.create_oval(
                    cx - tile_width * 0.30, cy - tile_height * 0.05,
                    cx + tile_width * 0.30, cy + tile_height * 0.18,
                    fill="#5c7e83", outline="", stipple="gray50", tags="fixed_dynamic",
                )
                image = self._sprite(asset_name, tile_width * 1.45)
                bottom_y = cy - tile_height * 0.48
            else:
                image = self._sprite(asset_name, tile_width * (0.82 if asset_name.startswith("machine_") else 0.76))
                bottom_y = cy + tile_height * 0.30
            self.canvas.create_image(cx, bottom_y, image=image, anchor="s", tags="fixed_dynamic")
            if not isinstance(entity, tuple):
                self._draw_machine_status(entity, cx, bottom_y, tile_width)
                if entity.output:
                    self._draw_item(entity.output, cx + tile_width * 0.28, bottom_y - tile_height * 0.75, tile_width)
        if self.state.inventory:
            cx, cy = self.tile_center(*drone)
            tile_width, tile_height = self._tile_dimensions(int(round(drone[0])), int(round(drone[1])))
            self._draw_item(self.state.inventory, cx + tile_width * 0.34, cy - tile_height * 1.35, tile_width)

    def _draw_machine_status(self, machine, cx: float, bottom_y: float, tile_width: float) -> None:
        width = tile_width * 0.48
        y = bottom_y - tile_width * 0.10
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
        self.canvas.create_line(cx - width / 2, y, cx + width / 2, y, fill="#263a41", width=max(2, round(tile_width * 0.05)), tags="fixed_dynamic")
        self.canvas.create_line(cx - width / 2, y, cx - width / 2 + width * ratio, y, fill=status, width=max(2, round(tile_width * 0.035)), tags="fixed_dynamic")

    def _draw_item(self, item: str, x: float, y: float, tile_width: float) -> None:
        asset_name = f"item_{item}"
        if asset_name not in asset_manifest():
            return
        image = self._sprite(asset_name, tile_width * 0.34)
        self.canvas.create_image(x, y, image=image, anchor="s", tags="fixed_dynamic")
        if self.show_item_labels:
            self.canvas.create_text(x, y + 5, text=ITEM_NAMES.get(item, item), fill=color("mechanics"), font=("Segoe UI", 8, "bold"), anchor="n", tags="fixed_dynamic")

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
            "camera_projection": "fixed_v1",
            "camera_zoom": round(self.camera.zoom, 4), "camera_pan_x": round(self.camera.pan_x, 2),
            "camera_pan_y": round(self.camera.pan_y, 2), "camera_adjusted": self.camera.user_adjusted,
            "show_coordinates": self.show_coordinates, "show_item_labels": self.show_item_labels,
            "follow_drone": self.follow_drone, "reduced_motion": self.reduced_motion,
        }
