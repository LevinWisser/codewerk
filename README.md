# CODEWERK

CODEWERK is a playable vertical slice of a 2D factory automation game. The player controls a drone with real, safely executed Python to supply a grid-based factory and fulfill production orders.

Development rules and architecture are documented in [AGENTS.md](AGENTS.md). Product direction and planned chapters are described in [docs/ROADMAP.md](docs/ROADMAP.md).

## Getting Started

CODEWERK requires Python 3.11 or newer with Tkinter and Pillow. Installing the project automatically installs Pillow:

```powershell
python -m pip install -e .
```

```powershell
python main.py
```

## Features

- eight progressive tutorial missions
- a persistent main factory after tutorial 8 with parallel orders and free machine placement
- a fixed-perspective 2.5D factory view with zoom, pan, coordinate hover, and optional drone follow
- an Aqua Lab design system with transparent machine sprites, item holograms, and adaptive movement animation
- accessible view options for reduced motion, coordinates, and item labels
- input warehouse, press, mill, assembly, and shipping
- an integrated Python editor with run, pause, single-step, and speed controls
- IntelliSense for game commands, Python keywords, variables, and custom functions (`Ctrl+Space`)
- wrapped, scrollable IntelliSense documentation and symbol-aware syntax colors
- a separate movable and resizable console window that follows the latest output
- multiple Python files per project with tabs and local `import` and `from ... import ...` support
- tutorial-wide helper files: modules such as `functions.py` survive mission changes
- a separate Python worker with restricted system access
- searchable, progressively unlocked help with code examples
- persistent credits, unlocks, and programs
- deterministic simulation and automated tests

## Tests

```powershell
python -m unittest discover -v
```

The save file is stored at `~/.codewerk/save.json`.

The fixed 3D lab view is the default and cannot be rotated. For comparison and debugging, the simple grid renderer can be enabled internally with `CODEWERK_LEGACY_RENDERER=1`. UI and item assets are generated with `python scripts/export_assets.py`; the Blender scene and fixed-view assets are generated with Blender 4.5 LTS and `scripts/blender_aqua_lab_poc.py`. Visual rules are documented in [docs/VISUAL_DESIGN_SYSTEM.md](docs/VISUAL_DESIGN_SYSTEM.md).

## Main Factory

After completing the tutorial, the player enters an empty `10 x 10` factory. Its `main.py` starts fresh while all player-created helper files remain available. Machines are purchased and freely placed in Build Mode. After twelve completed orders, including an actuator delivery, the factory expands to `12 x 12`.

Up to eight customer requests are visible at once. Requests can be accepted or rejected through the UI or Python; active orders are unlimited:

```python
requests = get_requests()

for request_id, request in requests.items():
    if request["base_payout"] >= 100:
        accept_request(request_id)
```

An accepted order can be cancelled without a penalty. Items already produced or stored remain unchanged:

```python
cancel_order("ORD-0001")
```

Raw materials are purchased exclusively through code. Each purchase buys one item and consumes one tick:

```python
while get_input_stock("steel") < 5:
    buy("steel")

pick_up("steel")  # At the input warehouse
```

`drop()` stores products in the unlimited shipping warehouse when used on the shipping tile. An order can only be shipped in full and only from that tile:

```python
orders = get_orders()

for order_id, order in orders.items():
    product = order["product"]
    if get_shipping_stock(product) >= order["quantity"]:
        ship(order_id)
```

Bonus deadlines scale with production complexity, so multi-stage products such as actuators receive substantially more time than plates. Late orders remain deliverable and pay their base payout; only the on-time bonus is lost.

## Multiple Files

`main.py` is the entry point. Use `+` to create more modules:

```python
# paths.py
def go_east():
    move(East)

# main.py
from paths import go_east
go_east()
```

Only files in the current game project may be imported. External Python packages and system modules remain blocked for security.

Local star imports such as `from positions import *` are supported and follow normal Python rules: without an explicit `__all__`, names beginning with an underscore are not imported.

`pick_up()` collects from machine outputs, while `pick_up(item)` selects a raw material at the main-factory input warehouse. `drop()` loads a machine or stores an item at shipping. Machine recipes and processing times are listed in the built-in help.

If a failed program leaves the wrong item in the drone, discard it through code or with **CLEAR CARGO**:

```python
if get_inventory() is not None:
    discard_item()
```

## Execution State

Starting a program again does not reset the factory. The next run continues with the current drone position, machine state, and deliveries. The `↻` button explicitly resets the current tutorial mission to its initial world state while preserving the source code.
