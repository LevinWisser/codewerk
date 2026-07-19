# Blender sources

The fixed-camera Aqua Lab proof of concept is generated with Blender 4.5 LTS.
Its scene, materials, geometry, lighting, and camera are defined in
`scripts/blender_aqua_lab_poc.py`.

Run the generator from the repository root:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 4.5\blender.exe' `
  --background --factory-startup `
  --python scripts\blender_aqua_lab_poc.py
```

The command writes the editable proof scene to this directory, creates the
composed proof outputs in `assets/poc/`, and exports the complete fixed-view
runtime family under `assets/runtime/fixed/`. Runtime exports include every
machine, both stations, the drone, 8/10/12-tile halls and normalized tile
polygons for perspective hit testing.
