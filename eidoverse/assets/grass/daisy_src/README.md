# The `daisy` flora sheet — source

[Vegetation guide](../../../../AGENTS.md) · [Blender guide](../../../../docs/blender.md)

`createFlora({ species: 'daisy' })` draws oxeye/Shasta daisy clumps
(`eidoverse/vegetation_daisy_gen.js`) from one trim sheet in
`eidoverse/assets/grass/`: `daisy_albedo.png`, `daisy_normal.png`,
`daisy_roughness.png`, `daisy_translucency.png` and `daisy_fit.json`. This
folder rebuilds that sheet. Every region of it is a real high-poly model of
*Leucanthemum vulgare*, built in Blender in millimetres and rendered
orthographically as exact emission passes. The cards the gen builds are then
fitted to the measured alpha of that art. The materials come first and the
geometry follows them.

| File | Role |
| --- | --- |
| `daisy_art.py` | Blender: models and renders each region: the disc (~520 florets in a Vogel spiral), 16 ray-floret variants, basal and stem leaves, the involucre and the ribbed stalk. Writes albedo, roughness/translucency, normal and AO passes per region as float `.npy`. |
| `assemble_sheet.py` | Python (numpy, Pillow, SciPy): un-premultiplies the passes, bakes AO into albedo, converts the normals to tangent space, calibrates translucency, downsamples 2×, pads colour under empty alpha, and measures every card's alpha envelope into `daisy_fit.json`. |
| `preview.py` | A contact strip of one region's passes (albedo, normal, AO, raking-light relief, alpha) for checking a region before assembly. |
| `fetch_refs.py` | Optional: botanical reference photos from Wikimedia Commons, with their licences recorded, into `work/refs/daisy/` (not committed). |

## Rebuild

From the repository root:

```bash
bash run_blender.sh eidoverse/assets/grass/daisy_src/daisy_art.py work/daisy_sheet/renders
python eidoverse/assets/grass/daisy_src/preview.py work/daisy_sheet/renders petals work/daisy_sheet/petals.png
python eidoverse/assets/grass/daisy_src/assemble_sheet.py work/daisy_sheet/renders work/daisy_sheet/sheet --install eidoverse/assets/grass
```

`daisy_art.py` takes an optional comma list of regions as its second argument
(`disc,petals,basalA,basalB,stemA,stemB,invol,stalk`), so one region can be
re-rendered without the rest. The sheet layout (pixel rectangles per region)
is owned by `LAYOUT` in `daisy_art.py`, and `vegetation_daisy_gen.js` reads
the same windows. Change both together, then reinstall and render a field to
check it (see the vegetation guide).

## Credits

Modelled, rendered and assembled by Claude (Opus 5.5) for the DAISY music
video (2026-09). No photograph is part of the sheet; the reference photos only
guided the modelling.
