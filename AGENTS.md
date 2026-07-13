# CODEWERK Agent Guide

This file is the authoritative handoff for coding agents working in this repository. Read it before editing. The user-facing product documentation lives in `README.md`; product direction lives in `docs/ROADMAP.md`.

## Project State

- Product: CODEWERK, a German-language 2D factory automation game controlled with standard Python syntax.
- Current version: `0.3.0`.
- Runtime: Python 3.11+, Tkinter, Pillow.
- Entry point: `main.py`.
- Tests: `python -m unittest discover -v`.
- Save file: `~/.codewerk/save.json`, currently schema version 3.
- GitHub: `https://github.com/LevinWisser/codewerk`, default branch `main`.
- `handy_functions/` is user-owned, intentionally untracked content. Never delete, modify, move, ignore, or commit it unless the user explicitly requests that exact action.

## Product Invariants

- The drone and player-authored Python remain the center of the game. UI automation must not replace the programming challenge.
- Player Python should behave like normal Python wherever feasible. Local project imports and local star imports are supported; external imports, filesystem, network, process access, and dynamic code execution remain blocked.
- Do not inject predefined machine-position constants. Discovering and storing useful coordinates is part of the player's learning and progression.
- Tutorial `main.py` files are mission-specific. Player-created helper modules are shared across tutorials and the main factory. The main factory has its own persistent `main.py`.
- Starting code never resets the world. Tutorial reset is explicit through the reset button. The persistent main factory must not be silently reset.
- `pick_up(item)` selects raw material at the main-factory input warehouse; `pick_up()` collects machine output. `drop()` loads a machine or stores finished goods at shipping.
- Shipping inventory has unlimited capacity. `ship(order_id)` works only at shipping, fulfills an order atomically, and never performs partial delivery.
- Late orders remain deliverable for base payout; only the on-time bonus is lost.
- Requests stay until accepted or rejected. At most eight are open; active orders are unlimited.
- Economy must remain recoverable. Do not introduce irreversible bankruptcy or mandatory hard failure without an explicit design decision.
- Keep the German UI and help text, but keep Python API names in English.

## Architecture

- `factory_game/app.py`: Tkinter composition, mode switching, editor/runtime orchestration, tutorial UI, contract UI, build mode, and persistence triggers.
- `factory_game/simulation.py`: deterministic tutorial simulation and tutorial command semantics.
- `factory_game/factory.py`: persistent main-factory simulation, economy, requests/orders, inventories, building, technology progression, and serialization.
- `factory_game/content.py`: tutorial missions, item and machine definitions, API help, and data-driven gameplay content.
- `factory_game/editor.py`: multi-file editor, local IntelliSense, completion documentation, and token-based syntax colors.
- `factory_game/iso_renderer.py`: isometric projection, camera, hit testing, sprite caching, presentation animation, and world drawing.
- `factory_game/design.py`: shared visual tokens and runtime asset-manifest access.
- `factory_game/runtime.py`: lifecycle and JSON-lines transport for the isolated Python subprocess.
- `python_worker/worker.py`: AST validation, local module loader, restricted built-ins, tracing, and Python-to-game API bridge.
- `factory_game/projects.py`: mission-specific `main.py` plus tutorial-wide shared helper-file persistence.
- `factory_game/persistence.py`: atomic versioned save loading, migration, and writing.
- `factory_game/console.py`: detachable, resizable, auto-scrolling output window.

Keep simulation and economy rules out of Tkinter callbacks. UI and player Python must call the same validated simulation operations. Content that can be represented as data belongs in `content.py`, not branch-heavy UI code.

Visual sources and runtime exports live under `assets/`; `scripts/export_assets.py` reproducibly rebuilds the initial Aqua Lab asset set and manifest. Rendering may interpolate presentation state but must never mutate or delay simulation state.

## Main Factory Progression

- Tutorial completion migrates the player to a new persistent `10 x 10` factory while retaining credits and helper modules.
- Technology level is derived from completed orders.
- Initial machine: press. Later unlocks: mill and wire drawer, injection molding, then assembly.
- Raw materials: `steel`, `copper`, and `polymer` purchased only through `buy(item)`.
- Products: `plate`, `gear`, `wire`, `housing`, and `actuator`.
- Chapter 1 completes after at least 12 orders and an actuator delivery; the hall expands to `12 x 12`.
- Later chapters are specified in `docs/ROADMAP.md`; do not implement them by guessing beyond that document.

## Public Factory API

The currently supported post-tutorial API includes:

```python
get_requests()
get_orders()
accept_request(request_id)
reject_request(request_id)
buy(item)
get_credits()
get_input_stock(item=None)
get_shipping_stock(item=None)
ship(order_id)
get_tick()
```

Existing movement, inventory, machine, sensor, wait, and direction APIs remain available. `load_machine()` and `collect_output()` exist only for compatibility with old saved code; do not teach or promote them in new content.

When adding or changing a public API, update all of these in the same change:

1. Simulation command handler.
2. `python_worker/worker.py` API allowlist.
3. IntelliSense metadata in `factory_game/editor.py`.
4. In-game help in `factory_game/content.py`.
5. README examples when player-visible.
6. Worker, simulation, and integration tests.

## Save Compatibility

- Never discard a valid older save because its schema is old. Add an explicit migration.
- Preserve credits, tutorial completion, per-mission `main.py`, shared helper files, main-factory `main.py`, placed machines, inventories, requests, orders, ticks, and deterministic request sequence.
- Writes must remain atomic through a temporary file replacement.
- Request generation must remain deterministic across save/load; reloading must not reroll offers.
- Before changing completion or reward logic, test replay behavior so tutorial rewards cannot be farmed repeatedly.

## UI Rules

- Preserve the restrained industrial visual language and current color semantics.
- Keep the factory grid readable at supported window sizes; dynamic content must not overlap.
- Long help and completion documentation must wrap and scroll instead of being clipped.
- The console remains a separate movable and resizable window and must follow new output automatically.
- Build mode pauses running code. Only empty, stopped machines can move or sell; sale returns 75 percent of purchase price.
- Use clear symbols for familiar controls and provide text where the command would otherwise be ambiguous.

## Verification and Git Hygiene

Before completing code changes, run:

```powershell
python -m compileall -q main.py factory_game python_worker tests
python -m unittest discover -v
git diff --check
git status --short --branch
```

For UI, editor, persistence, worker, or mode-transition changes, also run an isolated GUI smoke test using a temporary save. Do not overwrite the user's real `~/.codewerk/save.json` during tests.

Do not commit caches, local saves, shortcuts, generated files, or `handy_functions/`. Do not revert unrelated user changes. Commit only task files, use a focused message, and push `main` when the user asks for a published implementation or the active workflow already publishes completed game changes.

## Current Priorities

1. Stabilize and balance the post-tutorial Chapter 1 loop through player feedback.
2. Improve contract inspection, production statistics, and code-facing prioritization tools without automating decisions for the player.
3. Add Chapter 2 only after Chapter 1 economy and pacing are validated.
4. Keep multi-drone support for Chapter 3 rather than introducing it early.
