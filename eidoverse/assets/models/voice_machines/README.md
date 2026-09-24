# Historical voice machines, 1939–2001

[Props and sets guide](../../../../tools-guides/props-and-sets.md) · [Sources and licences](SOURCES.md) · [Rebuild scripts](../voice_machines_src/README.md) · [Tool inventory](../../../../docs/TOOLS.md)

Eight machines that spoke or sang, built for the DAISY music video's museum of
voices. This folder holds their runtime files. The modules in
[`eidoverse/props/voice_machines/`](../../../props/voice_machines/) read them
from here, build node materials, and animate the moving parts, lamps and
screens. Load a machine through its module, not as a bare GLB. The era-1 GLBs
have role slots and a mask atlas but no textures, and every screen and label is
drawn at runtime. `fetch_model.py` only scans the top level of
`eidoverse/assets/models/`, so these files are not in its catalogue.

| Machine | Year | Module | Files in this folder | Built size W × H × D (m) |
| --- | --- | --- | --- | --- |
| Bell Labs Voder, New York World's Fair | 1939 | `voder.js` | `voder.glb`, `voder_mask.png`, `voder_layout.json` | 1.28 × 1.70 × 1.32 |
| IBM 7090-era computer room (tape drives, cabinets, console) | 1961 | `mainframe.js` | `mainframe.glb`, `mainframe_mask.png`, `mainframe_layout.json` | 4.58 × 1.87 × 2.81 |
| Teletype ASR-33 on its pedestal | 1966 | `teletype.js` | `teletype.glb`, `teletype_mask.png`, `teletype_layout.json` | 0.60 × 1.07 × 0.76 |
| Texas Instruments Speak & Spell on a wire stand | 1978 | `speakspell.js` | `speakspell.glb` | 0.18 × 0.26 × 0.10 |
| Commodore 64 and its colour monitor | 1982 | `c64.js` | `c64.glb` | 0.41 × 0.34 × 0.69 |
| Macintosh 128K with keyboard and mouse | 1984 | `mac1984.js` | `mac1984.glb` | 0.45 × 0.34 × 0.50 |
| DECtalk DTC01 speech synthesizer | 1984 | `dectalk.js` | `dectalk.glb` | 0.46 × 0.10 × 0.31 |
| Early-2000s desktop PC (CRT, tower, speakers, keyboard, mouse) | 2001 | `desktop2001.js` | `desktop2001.glb` | 1.15 × 0.45 × 0.91 |

Sizes are the measured bounding boxes of the built groups. The mainframe
row's floor cables dip about 6 cm below `y = 0`, into the floor grommet.
`index.js` records each footprint with its XZ centre offset, so a machine can
be centred on a pedestal.

## Files

- **Era-1 machines (Voder, mainframe, Teletype):**
  - The GLB holds the modelled geometry, with role slots named `era1_<role>`
    and a second UV set for the mask atlas.
  - `<name>_mask.png` is a 2048² bake on that second UV set. R is ambient
    occlusion over 0.30 m, G is edge intensity and B is occlusion over 4 cm
    (the tight crevices).
  - `<name>_layout.json` holds the positions the module needs for its moving
    parts, lamps and labels.
  - The module layers each role from a tiling AmbientCG set on the first UV
    set, the masks, curvature wear and fingerprint or smear breakup. Labels
    and logos are canvas decals drawn when the machine is built.
- **`tex/<ID>/`:** the 14 AmbientCG sets the era-1 modules tile, all at
  1024². Each has `_Color`, `_NormalGL` and `_Roughness` maps, except the
  `Fingerprints002_1k` and `Smear004_1k` imperfection sets, which only use
  `_Color`. Only the maps the modules read are included.
- **Era-2 machines (Speak & Spell to the 2001 desktop):**
  - Everything is baked into the GLB: colour at 2048², normal and packed
    AO/roughness at 1024² (512² for small parts).
  - Objects are named for their runtime roles: `screen_*` is display glass
    that the module drives with `makeScreen`, `led_*` are indicator lenses,
    `glow_*` are surfaces lit by the machine's voice, and `metal_*` get
    runtime metal.

The folder is 89.3 MB: 41.6 MB of era-2 GLBs, 22.0 MB of era-1 GLBs, masks
and layouts, and 25.6 MB of AmbientCG maps.

## Use

```js
// In setup(): scene scripts are eval'd, so import dynamically
const VM = await import(new URL('props/voice_machines/index.js', EIDOVERSE_DIR).href);
const tty = await VM.buildMachine('teletype', THREE);
scene.add(tty.group);
// per frame, deterministic in t:
tty.update(t, { text: 'MEN ARE ALL ALIKE.\nIN WHAT WAY\n', nChars: 12 + t * 8, voice: 0.5, power: 1 });
```

See the [props and sets guide](../../../../tools-guides/props-and-sets.md)
for each machine's controls, its screen or text API, its costs and its
limitations. Everything is in metres, with +Y up, the base on `y = 0` and the
front toward +Z.

## Provenance

Modelled, baked and coded by Claude (Opus 5.5) with Skye for the DAISY music
video (2026-09). The period marks on the machines are hand-drawn homages. The
[sources](SOURCES.md) list which machine carries which, the CC0 texture
sources and the reference photos used. The Blender scripts that built the
GLBs and masks are in [`../voice_machines_src/`](../voice_machines_src/README.md).
