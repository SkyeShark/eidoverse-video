# Eidoverse modular robotics assets

The kit includes 85 GLB files, 67 shared PNGs and portable joint,
assembly and motion metadata. Files can contain many named components or a
complete sample robot. Enumerate component IDs with `robot.parts()` and extract
them with `loadPart(modelId, partId)`, retaining their shared textures and frames.
The catalog also defines detachable humanoid module views of an existing GLB.
Use the [shared runtime](../../robotics/index.js) for recoloring, animation,
authored tangent normals and reflected instances.

Keep `models/`, `textures/`, `metadata/` and `provenance/` together. GLBs reference
external shared maps. Repeated fitting/clamp instances share mesh and material
resources within the manufacturing exports. Provenance identifies selectable
parts independently of their packaging.

The 200 mm filament dispenser uses a 2K reel/stand atlas and the common feed
fitting. The runtime adds a 1.75 mm strand and a translucent 4/2 mm PTFE tube
around an independently colored filament core. Reel motion follows actual
extruded volume; body and filament colors have separate controls.

The FDM uses a rail-mounted carrier with that same finished reel and hardware.
An exposed feed span joins short seated PTFE entries and a carrier liner,
totaling 174 mm. The print-head fan and reel follow the print job's physical clock.
The carrier has one shared 512-square material set; the reel keeps its existing
maps. `spool_mount` is available separately for assembly and part extraction.

The FDM keeps its 450 x 520 mm bed, with a 458 x 528 x 0.65 mm removable PEI
sheet and overhanging pull tabs. The CNC has eight aluminum deck extrusions,
seven undercut T-slots and four removable toe clamps. `cnc` uses a flat end mill;
`cnc_relief` fits a ball-nose cutter for coordinated roughing and finishing.

`cnc_rotary` uses that gantry, table and ball-nose head with a fourth-axis drive,
four independently captured stepped jaws and a quill-supported tailstock. Its
saddle and tailstock have fasteners aligned with the table's T-slots. It removes
volumetric stock around an original asymmetric sculpture; wood and metal
examples share this assembly. The blank includes a prepared live-centre seat.

The reusable `rotary_fixture` shares the kit's rotary drive. Its four jaws,
sliding dovetail carriage and fed quill fit 80–180 mm stock lengths and
18–50 mm widths/heights. Independent locks, a feed handwheel and captured
guideways explain the adjustment. Inspect the `stock-setup` motion sample or
choose a stock preset in the CNC inspector.

New workholding and the ground two-flute ball cutter share five 2048-square
maps for recolorable coatings, fixed finish, normal and ORM. Repeated jaws,
table fasteners, braces and lock levers share primary UVs. Standalone parts
and their CNC consumers reference the same texture files. Use catalog entries
for current per-assembly triangle and part counts.

The sheet, table, clamp, frame guide and push fitting share
one 512 x 1024 material set: base color,
tangent normal and packed AO/roughness/metalness. The PEI finish uses CC0
[ambientCG Plastic004](https://ambientcg.com/a/Plastic004) PBR. Matching unprinted
coating patches, deck extrusions and opposite matching surfaces reuse UVs;
lettering remains unique.

| Module | Named parts | Static triangles |
| --- | ---: | ---: |
| `fdm_plate` | 1 | 260 |
| `cnc_plate` | 8 | 292 |
| `cnc_clamp` | 3 | 70 |
| `tube_support` | 2 | 390 |
| `push_fitting` | 2 | 576 |
| `ball_tool` | 1 | 1280 |
| `spool_mount` | 1 | 424 |

See the [robotics guide](../../../tools-guides/robotics.md), the
[offline inspector](../../robotics/inspector/) and
[examples](../../examples/robotics/). Runtime code is MIT; original geometry
and material bakes are CC0. See [LICENSE](LICENSE) and [THIRD_PARTY](THIRD_PARTY.md).
