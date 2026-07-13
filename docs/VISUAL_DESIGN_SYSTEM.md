# CODEWERK Visual Design System

## Direction

CODEWERK is a clean, modern and friendly automation lab. The factory is rendered
in fixed 2:1 isometric projection while simulation coordinates remain the normal
orthogonal `(x, y)` grid. The visual references are the clarity of Good Company
and Big Pharma: light modular floors, matte equipment, dark mechanics and small
semantic light accents. The code editor and console remain dark focus surfaces.

The grid and programming challenge stay authoritative. Rendering must never add
automatic routes, hidden position constants, or delays to player Python.

## World language

- A logical tile is 128 x 64 pixels at 100 percent zoom; runtime masters are 2x.
- `(0, 0)` starts at the top of the isometric diamond. X grows down-right and Y
  grows down-left.
- Machines occupy exactly one logical tile, have a fixed orientation and use
  individual silhouettes. Shared matte shells, dark mechanics, universal ports
  and an integrated status light keep the family coherent.
- The press exposes its ram, the mill its spindle, the wire drawer its rollers,
  injection molding its cylinder and die, and assembly its paired tool arms.
- The drone is a compact hovering service unit without a face. Tilt, antenna and
  status light provide restrained personality. On a machine it uses a visual
  front service dock while its shadow and cyan link retain the true coordinate.
- Items are neutral carriers with filled holographic glyphs. Color identifies
  material family; silhouette identifies processing stage. Labels appear on
  hover or through a global accessibility toggle.

## Interface language

The factory is a light canvas surrounded by dark technical work surfaces.
Resizable docks keep context left, factory center and code right. Natural title
case is used for actions; uppercase is reserved for small status labels. Segoe UI
and Consolas are the Windows reference fonts with portable system fallbacks.

The spacing unit is 8 pixels with a 4 pixel compact subdivision. Controls are 36
pixels high and compact data rows 32 pixels. UI icons use a 24 pixel grid, round
caps and a two pixel stroke. Color contrast, keyboard focus, form-plus-color,
reduced motion, coordinate labels and item labels are mandatory accessibility
features.

## Motion

Movement is precise and mechanical. At 1x the drone moves in roughly 220 ms;
service actions take 160-200 ms and output reveal takes 240 ms. Animation is
adaptively compressed at 2x and 4x and never stalls the runtime protocol. The
renderer targets 60 FPS while moving, permits a 30 FPS fallback and sleeps when
the scene is unchanged. Reduced motion removes hover, overshoot, particles and
camera easing.

## Asset and renderer contracts

Editable sources live under `assets/source`, runtime PNGs under `assets/runtime`,
and anchors, footprints and frame metadata in `assets/manifests/assets.json`.
Sources and exports are both versioned. Inkscape and Krita are the recommended
production tools; image generation may assist concepts but is not a source of
final runtime artwork.

Tkinter remains the UI framework and Pillow provides alpha-aware scaling and
sprite caching. The renderer consumes simulation snapshots, owns camera and
presentation interpolation, sorts entities by `(x + y, elevation, layer)`, and
performs inverse isometric hit testing. It must not mutate simulation state.
