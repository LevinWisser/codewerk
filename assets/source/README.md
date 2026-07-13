# CODEWERK asset sources

Runtime assets use the Aqua Lab design tokens in `../design_tokens.json` and are
exported at 2x scale. New production artwork should be authored as SVG in the
matching `world/`, `machines/`, `drone/`, `items/`, `ui_icons/`, or `effects/`
folder. Krita sources belong beside the relevant SVG.

The initial vertical slice is intentionally reproducible without a locally
installed design application: `scripts/export_assets.py` draws the approved
vector-like primitives with Pillow and writes the runtime PNGs plus manifest.
Later hand-authored SVGs may replace an individual generated asset without
changing its runtime filename, anchor, or manifest contract.

Naming uses `snake_case`. State and layer suffixes follow the base name, for
example `machine_press_body.png`, `machine_press_tool.png`, and
`machine_press_output.png`.
