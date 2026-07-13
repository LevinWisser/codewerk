from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent.parent
TOKENS = json.loads((ROOT / "assets" / "design_tokens.json").read_text(encoding="utf-8"))
C = TOKENS["color"]
RUNTIME = ROOT / "assets" / "runtime"
MANIFEST = ROOT / "assets" / "manifests" / "assets.json"


def rgba(value: str, alpha: int = 255) -> tuple[int, int, int, int]:
    value = value.lstrip("#")
    return int(value[:2], 16), int(value[2:4], 16), int(value[4:6], 16), alpha


def canvas(size: tuple[int, int]) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    return image, ImageDraw.Draw(image)


def ensure(folder: str) -> Path:
    path = RUNTIME / folder
    path.mkdir(parents=True, exist_ok=True)
    return path


def diamond(draw: ImageDraw.ImageDraw, center: tuple[int, int], width: int, height: int, fill, outline=None, line=3):
    x, y = center
    points = [(x, y - height // 2), (x + width // 2, y), (x, y + height // 2), (x - width // 2, y)]
    draw.polygon(points, fill=fill)
    if outline:
        draw.line(points + [points[0]], fill=outline, width=line, joint="curve")
    return points


def save_tile(name: str, color: str):
    image, draw = canvas((256, 128))
    diamond(draw, (128, 64), 252, 124, rgba(color), rgba(C["grid"]), 3)
    image.save(ensure("tiles") / f"{name}.png")


def save_station(kind: str, accent: str, label: str):
    image, draw = canvas((256, 224))
    draw.ellipse((36, 172, 220, 212), fill=(44, 67, 72, 42))
    diamond(draw, (128, 176), 208, 84, rgba(C["machine_secondary"]), rgba(C["metal"]), 4)
    diamond(draw, (128, 148), 168, 66, rgba(C["machine_shell"]), rgba(accent), 5)
    draw.rounded_rectangle((76, 62, 180, 150), radius=18, fill=rgba(C["mechanics"]), outline=rgba(accent), width=5)
    draw.rounded_rectangle((90, 78, 166, 122), radius=10, fill=rgba(accent, 46), outline=rgba(accent), width=4)
    draw.text((128, 100), label, anchor="mm", fill=rgba(C["text_light"]), stroke_width=1)
    image.save(ensure("stations") / f"station_{kind}.png")


def machine_base(draw: ImageDraw.ImageDraw, accent: str):
    draw.ellipse((34, 250, 222, 302), fill=(40, 62, 68, 44))
    diamond(draw, (128, 256), 210, 86, rgba(C["machine_secondary"]), rgba(C["metal"]), 4)
    diamond(draw, (128, 235), 178, 68, rgba(C["machine_shell"]), rgba(C["mechanics"]), 4)
    draw.rounded_rectangle((69, 241, 187, 253), radius=6, fill=rgba(C["mechanics"]))
    draw.rounded_rectangle((76, 243, 180, 251), radius=4, fill=rgba(accent))


def save_machine(kind: str, accent: str):
    image, draw = canvas((256, 320))
    machine_base(draw, accent)
    shell, mechanics, metal = rgba(C["machine_shell"]), rgba(C["mechanics"]), rgba(C["metal"])
    glow = rgba(accent)
    if kind == "press":
        draw.rounded_rectangle((58, 80, 86, 232), radius=10, fill=shell, outline=mechanics, width=5)
        draw.rounded_rectangle((170, 80, 198, 232), radius=10, fill=shell, outline=mechanics, width=5)
        draw.rounded_rectangle((53, 60, 203, 102), radius=12, fill=shell, outline=mechanics, width=5)
        draw.rectangle((114, 100, 142, 174), fill=metal, outline=mechanics, width=4)
        draw.rounded_rectangle((91, 168, 165, 190), radius=7, fill=glow, outline=mechanics, width=4)
        diamond(draw, (128, 214), 98, 36, rgba(C["metal"]), mechanics, 3)
    elif kind == "mill":
        draw.rounded_rectangle((55, 96, 201, 226), radius=22, fill=shell, outline=mechanics, width=5)
        draw.rounded_rectangle((76, 116, 180, 202), radius=16, fill=rgba(accent, 45), outline=glow, width=5)
        draw.rectangle((116, 82, 140, 167), fill=metal, outline=mechanics, width=4)
        draw.ellipse((105, 156, 151, 202), fill=mechanics, outline=glow, width=4)
        diamond(draw, (128, 205), 82, 28, metal, mechanics, 3)
    elif kind == "wire_drawer":
        draw.rounded_rectangle((48, 108, 208, 226), radius=20, fill=shell, outline=mechanics, width=5)
        for x in (92, 164):
            draw.ellipse((x - 31, 126, x + 31, 188), fill=mechanics, outline=glow, width=6)
            draw.ellipse((x - 10, 147, x + 10, 167), fill=metal)
        draw.line((40, 157, 216, 157), fill=rgba(C["copper"]), width=8)
    elif kind == "injection":
        draw.rounded_rectangle((48, 132, 156, 220), radius=18, fill=shell, outline=mechanics, width=5)
        draw.rounded_rectangle((122, 92, 206, 152), radius=22, fill=metal, outline=mechanics, width=5)
        draw.polygon([(122, 108), (84, 130), (122, 150)], fill=glow, outline=mechanics)
        draw.rounded_rectangle((73, 150, 132, 201), radius=9, fill=rgba(accent, 48), outline=glow, width=4)
    else:
        draw.rounded_rectangle((74, 142, 182, 222), radius=18, fill=shell, outline=mechanics, width=5)
        for left in (48, 166):
            draw.line((left, 98, left + (42 if left == 48 else -42), 156), fill=metal, width=16)
            draw.ellipse((left - 13, 84, left + 13, 110), fill=glow, outline=mechanics, width=4)
        draw.ellipse((101, 161, 155, 215), fill=rgba(accent, 45), outline=glow, width=5)
    image.save(ensure("machines") / f"machine_{kind}.png")


def save_drone():
    image, draw = canvas((192, 168))
    draw.ellipse((41, 130, 151, 157), fill=(27, 55, 60, 46))
    draw.line((26, 90, 67, 90), fill=rgba(C["metal"]), width=12)
    draw.line((125, 90, 166, 90), fill=rgba(C["metal"]), width=12)
    draw.ellipse((18, 77, 48, 103), fill=rgba(C["mechanics"]), outline=rgba(C["hologram"]), width=4)
    draw.ellipse((144, 77, 174, 103), fill=rgba(C["mechanics"]), outline=rgba(C["hologram"]), width=4)
    draw.ellipse((48, 48, 144, 128), fill=rgba(C["machine_shell"]), outline=rgba(C["mechanics"]), width=6)
    draw.ellipse((61, 62, 131, 114), fill=rgba(C["machine_secondary"]), outline=rgba(C["metal"]), width=4)
    draw.arc((57, 58, 135, 120), 10, 170, fill=rgba(C["accent"]), width=7)
    draw.line((96, 47, 96, 25), fill=rgba(C["mechanics"]), width=5)
    draw.ellipse((90, 18, 102, 30), fill=rgba(C["hologram"]))
    image.save(ensure("drone") / "drone_service.png")


ITEMS = {
    "steel": ("steel", "ingot"), "plate": ("steel", "plate"), "gear": ("steel", "gear"),
    "module": ("steel", "module"), "copper": ("copper", "ingot"), "wire": ("copper", "wire"),
    "polymer": ("polymer", "pellet"), "housing": ("polymer", "housing"), "actuator": ("accent", "actuator"),
}


def save_item(name: str, family: str, glyph: str):
    image, draw = canvas((80, 80))
    color = rgba(C[family])
    draw.rounded_rectangle((8, 8, 72, 72), radius=18, fill=rgba(C["mechanics"], 220), outline=color, width=4)
    if glyph == "ingot":
        draw.polygon([(23, 48), (32, 27), (57, 27), (64, 48), (53, 57), (30, 57)], fill=color)
    elif glyph == "plate":
        draw.rounded_rectangle((21, 27, 59, 55), radius=5, fill=color)
    elif glyph == "gear":
        draw.ellipse((22, 22, 58, 58), fill=color)
        draw.ellipse((33, 33, 47, 47), fill=rgba(C["mechanics"]))
        for x, y in ((36, 15), (36, 57), (15, 36), (57, 36)):
            draw.rectangle((x, y, x + 9, y + 9), fill=color)
    elif glyph == "wire":
        draw.ellipse((20, 20, 60, 60), outline=color, width=8)
        draw.ellipse((33, 33, 47, 47), fill=color)
    elif glyph == "pellet":
        for box in ((22, 22, 36, 36), (43, 24, 57, 38), (31, 43, 45, 57), (49, 45, 61, 57)):
            draw.ellipse(box, fill=color)
    elif glyph == "housing":
        draw.rounded_rectangle((20, 21, 60, 59), radius=10, outline=color, width=8)
    elif glyph == "module":
        draw.rectangle((20, 26, 60, 54), fill=color)
        draw.ellipse((26, 32, 42, 48), fill=rgba(C["mechanics"]))
        draw.rectangle((54, 19, 61, 31), fill=color)
    else:
        draw.rounded_rectangle((21, 25, 59, 55), radius=7, fill=color)
        draw.line((28, 19, 28, 61), fill=rgba(C["text_light"]), width=5)
        draw.line((52, 19, 52, 61), fill=rgba(C["copper"]), width=5)
    image.save(ensure("items") / f"item_{name}.png")


def save_ui_icon(name: str):
    image, draw = canvas((48, 48))
    color = rgba(C["text_light"])
    if name in {"zoom_in", "zoom_out"}:
        draw.ellipse((8, 8, 32, 32), outline=color, width=4)
        draw.line((29, 29, 41, 41), fill=color, width=4)
        draw.line((14, 20, 26, 20), fill=color, width=4)
        if name == "zoom_in":
            draw.line((20, 14, 20, 26), fill=color, width=4)
    elif name == "center":
        draw.line((8, 17, 24, 6, 40, 17), fill=color, width=4)
        draw.rounded_rectangle((13, 17, 35, 40), radius=3, outline=color, width=4)
    elif name == "follow":
        draw.ellipse((8, 8, 40, 40), outline=color, width=4)
        draw.ellipse((19, 19, 29, 29), fill=rgba(C["accent"]))
    elif name == "grid":
        for offset in (9, 24, 39):
            draw.line((8, offset, 40, offset), fill=color, width=3)
            draw.line((offset, 8, offset, 40), fill=color, width=3)
    elif name == "labels":
        draw.rounded_rectangle((6, 10, 42, 38), radius=6, outline=color, width=4)
        draw.line((13, 19, 35, 19), fill=color, width=3)
        draw.line((13, 28, 29, 28), fill=color, width=3)
    image.save(ensure("ui") / f"icon_{name}.png")


def main():
    save_tile("floor_a", C["floor_a"])
    save_tile("floor_b", C["floor_b"])
    save_station("warehouse", C["hologram"], "MAT")
    save_station("shipping", C["success"], "OUT")
    machine_accents = {"press": "warning", "mill": "hologram", "wire_drawer": "copper", "injection": "polymer", "assembly": "accent"}
    for kind, accent in machine_accents.items():
        save_machine(kind, C[accent])
    save_drone()
    for name, (family, glyph) in ITEMS.items():
        save_item(name, family, glyph)
    for name in ("zoom_in", "zoom_out", "center", "follow", "grid", "labels"):
        save_ui_icon(name)

    entries = {}
    for file in sorted(RUNTIME.rglob("*.png")):
        with Image.open(file) as image:
            entries[file.stem] = {
                "path": file.relative_to(ROOT).as_posix(), "size": list(image.size),
                "anchor": [0.5, 1.0], "footprint": [1, 1], "frames": 1,
            }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps({"version": 1, "assets": entries}, indent=2) + "\n", encoding="utf-8")
    print(f"Exported {len(entries)} assets to {RUNTIME}")


if __name__ == "__main__":
    main()
