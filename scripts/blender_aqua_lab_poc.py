"""Build and render the fixed-camera Aqua Lab 3D proof of concept.

Run with Blender, not the regular Python interpreter:

    blender --background --factory-startup --python scripts/blender_aqua_lab_poc.py

The scene is generated from scratch so the visual source remains reproducible.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "assets" / "poc"
SOURCE_DIR = ROOT / "assets" / "source" / "blender"
RUNTIME_DIR = ROOT / "assets" / "runtime" / "fixed"


PALETTE = {
    "background": "#9DB4BC",
    "floor_a": "#D8ECEB",
    "floor_b": "#CBE3E2",
    "floor_edge": "#527A80",
    "floor_dark": "#294B52",
    "shell": "#EAF3F2",
    "shell_shadow": "#AFC8C8",
    "mechanics": "#18343B",
    "metal": "#66858A",
    "aqua": "#18C8C2",
    "aqua_glow": "#72FFF3",
    "copper": "#C7825A",
    "warning": "#FFC95C",
}


def rgba(hex_color: str, alpha: float = 1.0) -> tuple[float, float, float, float]:
    value = hex_color.lstrip("#")
    return tuple(int(value[index:index + 2], 16) / 255 for index in (0, 2, 4)) + (alpha,)


def material(
    name: str,
    color: str,
    *,
    metallic: float = 0.0,
    roughness: float = 0.42,
    emission: str | None = None,
    emission_strength: float = 0.0,
) -> bpy.types.Material:
    result = bpy.data.materials.new(name)
    result.diffuse_color = rgba(color)
    result.use_nodes = True
    shader = result.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = rgba(color)
    shader.inputs["Metallic"].default_value = metallic
    shader.inputs["Roughness"].default_value = roughness
    if emission and "Emission Color" in shader.inputs:
        shader.inputs["Emission Color"].default_value = rgba(emission)
        shader.inputs["Emission Strength"].default_value = emission_strength
    return result


def assign(obj: bpy.types.Object, mat: bpy.types.Material) -> bpy.types.Object:
    obj.data.materials.append(mat)
    return obj


def smooth(obj: bpy.types.Object) -> None:
    if hasattr(obj.data, "polygons"):
        for polygon in obj.data.polygons:
            polygon.use_smooth = True


def box(
    name: str,
    location: tuple[float, float, float],
    dimensions: tuple[float, float, float],
    mat: bpy.types.Material,
    bevel: float = 0.08,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    assign(obj, mat)
    if bevel:
        modifier = obj.modifiers.new("Soft industrial edges", "BEVEL")
        modifier.width = bevel
        modifier.segments = 3
    return obj


def cylinder(
    name: str,
    location: tuple[float, float, float],
    radius: float,
    depth: float,
    mat: bpy.types.Material,
    *,
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
    vertices: int = 48,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices, radius=radius, depth=depth, location=location, rotation=rotation
    )
    obj = bpy.context.object
    obj.name = name
    assign(obj, mat)
    modifier = obj.modifiers.new("Rounded rims", "BEVEL")
    modifier.width = min(radius * 0.12, depth * 0.12)
    modifier.segments = 3
    smooth(obj)
    return obj


def cone(
    name: str,
    location: tuple[float, float, float],
    radius_top: float,
    radius_bottom: float,
    depth: float,
    mat: bpy.types.Material,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cone_add(
        vertices=48, radius1=radius_bottom, radius2=radius_top, depth=depth, location=location
    )
    obj = bpy.context.object
    obj.name = name
    assign(obj, mat)
    modifier = obj.modifiers.new("Rounded cone rims", "BEVEL")
    modifier.width = 0.06
    modifier.segments = 3
    smooth(obj)
    return obj


def uv_sphere(
    name: str,
    location: tuple[float, float, float],
    scale: tuple[float, float, float],
    mat: bpy.types.Material,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    assign(obj, mat)
    smooth(obj)
    return obj


def torus(
    name: str,
    location: tuple[float, float, float],
    major_radius: float,
    minor_radius: float,
    mat: bpy.types.Material,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_torus_add(
        major_radius=major_radius,
        minor_radius=minor_radius,
        major_segments=64,
        minor_segments=16,
        location=location,
    )
    obj = bpy.context.object
    obj.name = name
    assign(obj, mat)
    smooth(obj)
    return obj


def rod_between(
    name: str,
    start: tuple[float, float, float],
    end: tuple[float, float, float],
    radius: float,
    mat: bpy.types.Material,
) -> bpy.types.Object:
    start_v, end_v = Vector(start), Vector(end)
    direction = end_v - start_v
    obj = cylinder(name, tuple((start_v + end_v) / 2), radius, direction.length, mat)
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = direction.to_track_quat("Z", "Y")
    return obj


def look_at(obj: bpy.types.Object, target: tuple[float, float, float]) -> None:
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def create_materials() -> dict[str, bpy.types.Material]:
    return {
        "floor_a": material("Floor porcelain A", PALETTE["floor_a"], roughness=0.62),
        "floor_b": material("Floor porcelain B", PALETTE["floor_b"], roughness=0.62),
        "floor_edge": material("Floor edge", PALETTE["floor_edge"], metallic=0.15, roughness=0.5),
        "floor_dark": material("Floor underside", PALETTE["floor_dark"], roughness=0.58),
        "shell": material("Ceramic shell", PALETTE["shell"], roughness=0.27),
        "shell_shadow": material("Shell secondary", PALETTE["shell_shadow"], roughness=0.36),
        "mechanics": material("Dark mechanics", PALETTE["mechanics"], metallic=0.7, roughness=0.29),
        "metal": material("Brushed metal", PALETTE["metal"], metallic=0.82, roughness=0.25),
        "aqua": material("Aqua trim", PALETTE["aqua"], metallic=0.18, roughness=0.24),
        "glow": material(
            "Aqua light", PALETTE["aqua_glow"], roughness=0.2,
            emission=PALETTE["aqua_glow"], emission_strength=5.0,
        ),
        "copper": material("Copper detail", PALETTE["copper"], metallic=0.68, roughness=0.26),
        "warning": material("Safety yellow", PALETTE["warning"], roughness=0.34),
    }


def build_platform(mats: dict[str, bpy.types.Material], size: int = 5) -> None:
    width = size * 2.02
    box("Hall slab", (0, 0, -0.32), (width + 0.6, width + 0.6, 0.58), mats["floor_dark"], bevel=0.28)
    box("Hall rim", (0, 0, -0.04), (width + 0.25, width + 0.25, 0.36), mats["floor_edge"], bevel=0.2)
    tile_size = 1.94
    midpoint = (size - 1) / 2
    for y in range(size):
        for x in range(size):
            # Logical y grows towards the viewer, matching the screen grid.
            px, py = (x - midpoint) * 2.02, (midpoint - y) * 2.02
            tile = box(
                f"Floor {x},{y}", (px, py, 0.16), (tile_size, tile_size, 0.32),
                mats["floor_a" if (x + y) % 2 == 0 else "floor_b"], bevel=0.08,
            )
            tile["grid_x"], tile["grid_y"] = x, y
    for index in range(size):
        x = (index - midpoint) * 2.02
        cylinder("Front coordinate lamp", (x, -width / 2 - 0.21, -0.05), 0.075, 0.12, mats["glow"])


def build_press(mats: dict[str, bpy.types.Material], center: tuple[float, float] = (-2.02, 0.0)) -> None:
    x, y = center
    box("Press base", (x, y, 0.48), (1.58, 1.48, 0.42), mats["mechanics"], bevel=0.16)
    box("Press lower shell", (x, y + 0.05, 0.77), (1.42, 1.30, 0.30), mats["shell_shadow"], bevel=0.14)
    box("Press work bed", (x, y - 0.03, 1.02), (1.18, 1.04, 0.20), mats["metal"], bevel=0.08)
    for side in (-0.56, 0.56):
        box("Press column", (x + side, y + 0.17, 1.84), (0.24, 0.34, 1.88), mats["mechanics"], bevel=0.08)
        box("Press column cover", (x + side, y + 0.12, 1.82), (0.34, 0.48, 1.28), mats["shell"], bevel=0.13)
    box("Press crown", (x, y + 0.13, 2.78), (1.52, 1.06, 0.58), mats["shell"], bevel=0.2)
    box("Press crown inset", (x, y - 0.43, 2.76), (0.76, 0.08, 0.22), mats["aqua"], bevel=0.03)
    cylinder("Press ram", (x, y + 0.03, 2.05), 0.28, 1.02, mats["metal"])
    cylinder("Press tool", (x, y + 0.03, 1.50), 0.43, 0.18, mats["warning"])
    box("Press hologram", (x, y - 0.72, 1.62), (0.66, 0.06, 0.34), mats["glow"], bevel=0.06)
    for side in (-0.48, 0.48):
        cylinder("Press foot", (x + side, y - 0.47, 0.27), 0.11, 0.24, mats["copper"])


def build_mill(mats: dict[str, bpy.types.Material], center: tuple[float, float] = (0.0, 0.0)) -> None:
    x, y = center
    box("Mill base", (x, y, 0.50), (1.58, 1.48, 0.48), mats["mechanics"], bevel=0.16)
    box("Mill shell", (x, y + 0.10, 0.82), (1.42, 1.28, 0.34), mats["shell_shadow"], bevel=0.15)
    cylinder("Mill rotary bed", (x, y - 0.10, 1.05), 0.53, 0.20, mats["metal"])
    cylinder("Mill bed light", (x, y - 0.10, 1.17), 0.38, 0.05, mats["glow"])
    box("Mill rear tower", (x, y + 0.48, 1.86), (0.74, 0.48, 1.88), mats["shell"], bevel=0.18)
    box("Mill head arm", (x, y + 0.04, 2.56), (0.88, 1.10, 0.48), mats["shell"], bevel=0.18)
    cylinder("Mill spindle", (x, y - 0.34, 1.92), 0.20, 1.06, mats["metal"])
    cone("Mill cutter", (x, y - 0.34, 1.35), 0.10, 0.24, 0.30, mats["copper"])
    box("Mill display", (x, y - 0.53, 2.53), (0.52, 0.06, 0.20), mats["glow"], bevel=0.04)


def build_wire_drawer(mats: dict[str, bpy.types.Material], center: tuple[float, float] = (0.0, 0.0)) -> None:
    x, y = center
    box("Wire base", (x, y, 0.48), (1.64, 1.48, 0.44), mats["mechanics"], bevel=0.16)
    box("Wire shell", (x, y + 0.16, 0.79), (1.50, 1.18, 0.34), mats["shell_shadow"], bevel=0.14)
    for dx in (-0.43, 0.43):
        cylinder("Wire reel", (x + dx, y, 1.52), 0.43, 0.34, mats["metal"], rotation=(0, math.pi / 2, 0))
        cylinder("Wire hub", (x + dx, y - 0.19, 1.52), 0.16, 0.08, mats["copper"], rotation=(math.pi / 2, 0, 0))
        box("Wire upright", (x + dx, y + 0.38, 1.40), (0.18, 0.20, 1.36), mats["shell"], bevel=0.07)
    rod_between("Drawn copper wire", (x - 0.43, y - 0.26, 1.52), (x + 0.43, y - 0.26, 1.52), 0.045, mats["copper"])
    box("Wire top bridge", (x, y + 0.38, 2.12), (1.36, 0.32, 0.28), mats["shell"], bevel=0.12)
    box("Wire display", (x, y - 0.58, 0.84), (0.58, 0.06, 0.20), mats["glow"], bevel=0.04)


def build_injection(mats: dict[str, bpy.types.Material], center: tuple[float, float] = (0.0, 0.0)) -> None:
    x, y = center
    box("Injection base", (x, y, 0.48), (1.64, 1.48, 0.44), mats["mechanics"], bevel=0.16)
    box("Injection body", (x, y + 0.12, 1.12), (1.46, 1.22, 0.94), mats["shell"], bevel=0.20)
    box("Injection mold", (x, y - 0.55, 1.10), (0.82, 0.18, 0.60), mats["aqua"], bevel=0.08)
    cone("Polymer hopper", (x + 0.36, y + 0.16, 2.18), 0.28, 0.56, 0.84, mats["shell_shadow"])
    cylinder("Hopper rim", (x + 0.36, y + 0.16, 2.62), 0.57, 0.13, mats["metal"])
    cylinder("Injection barrel", (x - 0.24, y - 0.24, 1.64), 0.24, 1.10, mats["metal"], rotation=(math.pi / 2, 0, 0))
    box("Injection display", (x - 0.36, y - 0.65, 1.72), (0.48, 0.06, 0.22), mats["glow"], bevel=0.04)


def build_assembly(mats: dict[str, bpy.types.Material], center: tuple[float, float] = (0.0, 0.0)) -> None:
    x, y = center
    box("Assembly base", (x, y, 0.48), (1.68, 1.52, 0.46), mats["mechanics"], bevel=0.17)
    cylinder("Assembly table", (x, y - 0.04, 0.91), 0.66, 0.34, mats["metal"])
    cylinder("Assembly table light", (x, y - 0.04, 1.10), 0.49, 0.06, mats["glow"])
    cylinder("Assembly mast", (x, y + 0.40, 1.75), 0.20, 1.62, mats["shell_shadow"])
    cylinder("Assembly crown", (x, y + 0.40, 2.60), 0.38, 0.26, mats["shell"])
    for index, angle in enumerate((-55, 0, 55)):
        radians = math.radians(angle)
        start = (x, y + 0.28, 2.46)
        end = (x + math.sin(radians) * 0.72, y - 0.18 + math.cos(radians) * 0.28, 1.50)
        rod_between(f"Assembly arm {index}", start, end, 0.09, mats["mechanics"])
        cylinder(f"Assembly tool {index}", end, 0.14, 0.24, mats["copper"])
    box("Assembly display", (x, y - 0.68, 0.72), (0.62, 0.06, 0.24), mats["glow"], bevel=0.04)


def build_drone(mats: dict[str, bpy.types.Material], center: tuple[float, float] = (2.02, -2.02)) -> None:
    x, y = center
    z = 2.35
    cylinder("Drone shadow", (x, y, 0.38), 0.64, 0.025, mats["floor_dark"], vertices=64)
    uv_sphere("Drone body", (x, y, z), (0.78, 0.68, 0.42), mats["shell"])
    uv_sphere("Drone lower body", (x, y, z - 0.18), (0.62, 0.54, 0.30), mats["shell_shadow"])
    torus("Drone aqua ring", (x, y, z + 0.02), 0.58, 0.075, mats["aqua"])
    cylinder("Drone lens", (x, y - 0.58, z - 0.06), 0.16, 0.12, mats["glow"], rotation=(math.pi / 2, 0, 0))
    cylinder("Drone top cap", (x, y, z + 0.38), 0.29, 0.16, mats["copper"])
    rotor_points = [(-1.12, -0.78), (1.12, -0.78), (-1.12, 0.78), (1.12, 0.78)]
    for index, (dx, dy) in enumerate(rotor_points):
        endpoint = (x + dx, y + dy, z + 0.08)
        rod_between(f"Drone arm {index}", (x + dx * 0.42, y + dy * 0.42, z + 0.02), endpoint, 0.075, mats["mechanics"])
        cylinder(f"Rotor motor {index}", endpoint, 0.18, 0.18, mats["metal"])
        cylinder(f"Rotor glow {index}", (endpoint[0], endpoint[1], endpoint[2] + 0.11), 0.10, 0.04, mats["glow"])
        box(f"Rotor blade {index}", (endpoint[0], endpoint[1], endpoint[2] + 0.17), (0.92, 0.10, 0.035), mats["mechanics"], bevel=0.045).rotation_euler[2] = (index % 2) * math.pi / 2 + 0.24


def build_shipping_beacon(mats: dict[str, bpy.types.Material], center: tuple[float, float] = (4.04, 4.04)) -> None:
    x, y = center
    cylinder("Shipping base", (x, y, 0.45), 0.66, 0.30, mats["mechanics"])
    cylinder("Shipping ring", (x, y, 0.64), 0.54, 0.12, mats["aqua"])
    cylinder("Shipping light", (x, y, 0.78), 0.35, 0.18, mats["glow"])
    for angle in range(0, 360, 90):
        radians = math.radians(angle)
        rod_between(
            "Shipping guard",
            (x + math.cos(radians) * 0.48, y + math.sin(radians) * 0.48, 0.70),
            (x + math.cos(radians) * 0.48, y + math.sin(radians) * 0.48, 1.28),
            0.045,
            mats["copper"],
        )


def build_warehouse(mats: dict[str, bpy.types.Material], center: tuple[float, float] = (0.0, 0.0)) -> None:
    x, y = center
    box("Warehouse base", (x, y, 0.46), (1.62, 1.48, 0.42), mats["mechanics"], bevel=0.16)
    box("Warehouse cabinet", (x, y + 0.28, 1.34), (1.48, 0.74, 1.42), mats["shell"], bevel=0.20)
    box("Warehouse opening", (x, y - 0.14, 1.28), (1.04, 0.14, 0.82), mats["floor_dark"], bevel=0.10)
    box("Warehouse shelf", (x, y - 0.25, 0.92), (0.92, 0.34, 0.12), mats["metal"], bevel=0.04)
    box("Warehouse header", (x, y - 0.16, 2.02), (0.78, 0.12, 0.22), mats["glow"], bevel=0.04)
    for dx in (-0.50, 0.50):
        cylinder("Warehouse status", (x + dx, y - 0.18, 1.91), 0.07, 0.08, mats["copper"], rotation=(math.pi / 2, 0, 0))


def add_area_light(name: str, location: tuple[float, float, float], energy: float, size: float, color: str) -> None:
    data = bpy.data.lights.new(name, "AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    data.color = rgba(color)[:3]
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    look_at(obj, (0, 0, 0))


def render_transparent_asset(
    objects: list[bpy.types.Object],
    center: tuple[float, float],
    target_z: float,
    output_path: Path,
) -> None:
    """Render one fixed-view object group for use as a Tkinter sprite."""
    scene = bpy.context.scene
    camera = scene.camera
    hidden = {obj: obj.hide_render for obj in scene.objects}
    original_location = camera.location.copy()
    original_rotation = camera.rotation_euler.copy()
    original_lens = camera.data.lens
    original_resolution = (scene.render.resolution_x, scene.render.resolution_y)
    original_transparency = scene.render.film_transparent
    original_path = scene.render.filepath
    try:
        for obj in scene.objects:
            obj.hide_render = True
        for obj in objects:
            obj.hide_render = False
        camera.hide_render = False
        x, y = center
        camera.location = (x, y - 6.9, target_z + 6.6)
        camera.data.lens = 58
        look_at(camera, (x, y, target_z))
        scene.render.resolution_x = 512
        scene.render.resolution_y = 512
        scene.render.film_transparent = True
        output_path.parent.mkdir(parents=True, exist_ok=True)
        scene.render.filepath = str(output_path)
        bpy.ops.render.render(write_still=True)
    finally:
        for obj, was_hidden in hidden.items():
            obj.hide_render = was_hidden
        camera.location = original_location
        camera.rotation_euler = original_rotation
        camera.data.lens = original_lens
        scene.render.resolution_x, scene.render.resolution_y = original_resolution
        scene.render.film_transparent = original_transparency
        scene.render.filepath = original_path


def configure_scene() -> None:
    # The scene is generated from code; Blender's rotating .blend1 backups would
    # only create untracked duplicates on subsequent exports.
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for datablock in list(datablocks):
            datablocks.remove(datablock)

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 760
    scene.render.resolution_y = 680
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False
    scene.render.image_settings.color_depth = "8"
    scene.render.resolution_percentage = 100
    scene.world.color = rgba(PALETTE["background"])[:3]
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = rgba(PALETTE["background"])
    background.inputs["Strength"].default_value = 0.72
    scene.view_settings.look = "AgX - Medium High Contrast"

    camera_data = bpy.data.cameras.new("Fixed Aqua Lab Camera")
    camera_data.type = "PERSP"
    camera_data.lens = 58
    camera = bpy.data.objects.new("Fixed Aqua Lab Camera", camera_data)
    bpy.context.collection.objects.link(camera)
    camera.location = (0.0, -14.8, 14.2)
    look_at(camera, (0.0, 0.25, 0.35))
    scene.camera = camera

    add_area_light("Key light", (-6.0, -8.0, 14.0), 1050, 7.0, "#FFF4DF")
    add_area_light("Aqua fill", (8.0, -2.0, 8.0), 520, 6.0, "#B9FFFF")
    add_area_light("Rear rim", (-3.0, 8.0, 10.0), 720, 5.0, "#D7F7FF")


def render_runtime_assets() -> None:
    configure_scene()
    mats = create_materials()
    builders = {
        "machines/machine_press.png": build_press,
        "machines/machine_mill.png": build_mill,
        "machines/machine_wire_drawer.png": build_wire_drawer,
        "machines/machine_injection.png": build_injection,
        "machines/machine_assembly.png": build_assembly,
        "stations/station_warehouse.png": build_warehouse,
        "stations/station_shipping.png": build_shipping_beacon,
        "drone/drone_service.png": build_drone,
    }
    targets = {
        "machines/machine_press.png": 1.5,
        "machines/machine_mill.png": 1.5,
        "machines/machine_wire_drawer.png": 1.35,
        "machines/machine_injection.png": 1.45,
        "machines/machine_assembly.png": 1.45,
        "stations/station_warehouse.png": 1.25,
        "stations/station_shipping.png": 0.75,
        "drone/drone_service.png": 2.35,
    }
    for relative_path, builder in builders.items():
        before = set(bpy.data.objects)
        builder(mats, (0.0, 0.0))
        created = [
            obj for obj in set(bpy.data.objects) - before
            if obj.name != "Drone shadow"
        ]
        render_transparent_asset(
            created, (0.0, 0.0), targets[relative_path], RUNTIME_DIR / relative_path
        )


def project_to_normalized(point: tuple[float, float, float]) -> list[float]:
    scene = bpy.context.scene
    projected = world_to_camera_view(scene, scene.camera, Vector(point))
    return [round(float(projected.x), 7), round(float(1.0 - projected.y), 7)]


def render_factory_background(size: int) -> dict[str, object]:
    configure_scene()
    mats = create_materials()
    build_platform(mats, size)
    scene = bpy.context.scene
    camera = scene.camera
    camera.location = (0.0, -size * 2.96, size * 2.84)
    look_at(camera, (0.0, 0.0, 0.18))
    scene.render.resolution_x = 1400
    scene.render.resolution_y = 1100
    scene.render.film_transparent = True
    output_path = RUNTIME_DIR / "world" / f"factory_{size}.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(output_path)
    bpy.ops.render.render(write_still=True)

    spacing = 2.02
    midpoint = (size - 1) / 2
    tiles = {}
    for y in range(size):
        for x in range(size):
            cx = (x - midpoint) * spacing
            cy = (midpoint - y) * spacing
            half = spacing / 2
            tiles[f"{x},{y}"] = {
                "center": project_to_normalized((cx, cy, 0.34)),
                "polygon": [
                    project_to_normalized((cx - half, cy + half, 0.34)),
                    project_to_normalized((cx + half, cy + half, 0.34)),
                    project_to_normalized((cx + half, cy - half, 0.34)),
                    project_to_normalized((cx - half, cy - half, 0.34)),
                ],
            }
    return {
        "image": output_path.relative_to(ROOT).as_posix(),
        "render_size": [scene.render.resolution_x, scene.render.resolution_y],
        "tiles": tiles,
    }


def render_runtime_worlds() -> None:
    layouts = {str(size): render_factory_background(size) for size in (8, 10, 12)}
    layout_path = RUNTIME_DIR / "world" / "layouts.json"
    layout_path.write_text(json.dumps({"version": 1, "layouts": layouts}, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    configure_scene()
    mats = create_materials()
    build_platform(mats)
    before_press = set(bpy.data.objects)
    build_press(mats)
    press_objects = list(set(bpy.data.objects) - before_press)
    before_drone = set(bpy.data.objects)
    build_drone(mats)
    drone_objects = [
        obj for obj in set(bpy.data.objects) - before_drone
        if obj.name != "Drone shadow"
    ]
    build_shipping_beacon(mats)

    scene = bpy.context.scene
    scene.render.filepath = str(OUTPUT_DIR / "aqua_lab_fixed_view_poc.png")
    bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE_DIR / "aqua_lab_fixed_view_poc.blend"))
    bpy.ops.render.render(write_still=True)
    render_transparent_asset(press_objects, (-2.02, 0.0), 1.5, OUTPUT_DIR / "machine_press_poc.png")
    render_transparent_asset(drone_objects, (2.02, -2.02), 2.35, OUTPUT_DIR / "drone_service_poc.png")
    render_runtime_assets()
    render_runtime_worlds()
    print(f"CODEWERK_POC_RENDER={scene.render.filepath}")


if __name__ == "__main__":
    main()
