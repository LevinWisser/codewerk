# CODEWERK Visual Design System

## Direction

CODEWERK is a clean, modern and friendly automation lab. The factory is rendered
through a fixed elevated perspective camera while simulation coordinates remain
the normal orthogonal `(x, y)` grid. The camera cannot rotate; zoom, pan and
optional drone follow preserve orientation. Light modular floors, matte ceramic
equipment, dark mechanics and small semantic light accents create the Aqua Lab
language. The code editor and console remain dark focus surfaces.

The grid and programming challenge stay authoritative. Rendering must never add
automatic routes, hidden position constants, or delays to player Python.

## World language

- `(0, 0)` starts at the rear-left of the perspective platform. X grows right
  and Y grows toward the viewer, matching the normal screen-grid convention.
- Blender exports 8 x 8, 10 x 10 and 12 x 12 hall backgrounds together with
  normalized tile polygons. Runtime hit testing uses these authored polygons.
- Machines occupy exactly one logical tile, have a fixed orientation and use
  individual silhouettes. Shared matte shells, dark mechanics, universal ports
  and an integrated status light keep the family coherent.
- The press exposes its ram, the mill its spindle, the wire drawer its rollers,
  injection molding its cylinder and die, and assembly its paired tool arms.
- The drone is a compact hovering service unit without a face. Rotors, a copper
  cap and cyan status light provide restrained personality. Its shadow retains
  the true logical coordinate while the body floats above machines and tiles.
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
and anchors, footprints and frame metadata in manifests. Blender 4.5 LTS and the
checked-in Python generator are authoritative for the fixed-view world, machine,
station and drone assets. Inkscape and Krita remain appropriate for UI and item
graphics. Sources and exports are both versioned.

Tkinter remains the UI framework and Pillow provides alpha-aware scaling and
sprite caching. The renderer consumes simulation snapshots, owns camera and
presentation interpolation, sorts entities from rear to front by `(y, layer)`,
and performs polygon-based perspective hit testing. It must not mutate
simulation state.
