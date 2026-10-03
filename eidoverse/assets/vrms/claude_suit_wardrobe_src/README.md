# claude_suit_wardrobe — Blender source

[VRM characters guide](../../../../AGENTS.md) · [Blender guide](../../../../docs/blender.md) · [Runtime textures](../claude_suit_wardrobe_tex/README.md)

`../claude_suit_wardrobe.vrm` is digi's `claude_suit.vrm` (the claudesona,
voooooogel's flower-headed Claude, in a suit) plus garments and accessories modelled onto its
rig. Every outfit lives in the one VRM as hidden layers, and
`eidoverse/claudesona_wardrobe.js` shows, hides and repaints them per preset.
`../claude_suit_wardrobe_preview.jpg` shows the sixteen presets made for the DAISY (DAY'S EYE) music video
(2026-09); `../claude_suit_wardrobe_preview_tuta.jpg` shows the TuTa, the outfit of the UNKNOWN FORCE music video
(2026-10), with all five badges pinned (see [The TuTa](#the-tuta)).

The VRM is built in two stages: `claude_suit_wardrobe.blend` holds digi's model and every DAISY garment, and
`build_tuta.py` opens it read-only, adds the TuTa and exports the library VRM. Run `build_tuta.py` after any change
to the `.blend`.

## Files

| File | Role |
| --- | --- |
| `claude_suit_wardrobe.blend` | The editable source: digi's rig, body and suit, every DAISY garment and accessory object, all nine images packed. Blender 4.2+ with the VRM add-on. |
| `export_wardrobe_vrm.py` | Exports the `.blend` alone (hidden layers included) to `work/claude_suit_wardrobe_base.vrm`, the wardrobe without the TuTa, for checks. The library VRM comes from `build_tuta.py`. |
| `build_cyclist.py` | Recipe: the 1890s cycling outfit (jersey from the shirt, knickerbockers from the pants, argyle socks lifted from the leg skin, a straw boater) and its baked maps. |
| `build_accessories.py` | Recipe: glasses, operator headset, pocket protector, bow tie, headband, ribbons. |
| `build_era_garments.py` | Recipe: the jersey collar split, the coat skirt, rolled shirt sleeves, the hoodie, the patches, the boutonniere; exports the finished VRM. |
| `paint_patches.py` | Recipe: the embroidered patch atlas (satin-stitch hatching, twill ground, merrowed rims). |
| `ring_pivot.py` | Tool: hangs the petal ring's bottom-arc bone from a chest pivot so nods and tilts don't drive the ring into the jacket. Already applied to both claudesona VRMs; `export_wardrobe_vrm.py` and `build_tuta.py` re-apply it to every export. |
| `build_tuta.py` | Builds the outfit: opens the library wardrobe `.blend` read-only, adds the tuta, the boots, the straps, the badges and the disc, saves `work/claude_suit_wardrobe_tuta.blend` and exports `../claude_suit_wardrobe.vrm` (through a temporary file, so a render reading the VRM never sees half a file) with the petal ring's chest pivot re-applied. `--no-export` skips the VRM; `--looks` adds EEVEE geometry checks in `work/claude_suit_wardrobe_looks/`. |
| `paint_badges.py` | Paints the badges' faces and emissive rims, the ghost SDF atlas and the sun disc (system Python: PIL + numpy) into `../claude_suit_wardrobe_tex/`. Deterministic: it reproduces the shipped PNGs byte for byte. |
| `badges.json` | The modificanti: outline polygons in badge millimetres, placement rays, bones, colours and glows. The runtime reads it too (badge names, camps, glows, the ghost atlas extent). |
| `badges_set.py` | Edits `badges.json` from the command line in its compact layout (`mod_gold ray_origin='[…]'`, `--print`). |
| `uf_shapes.py` | Outline helpers shared by `build_tuta.py` and `paint_badges.py`: each badge's polygons from `badges.json` (CCW, corners rounded), stars, point-in-polygon. Pure Python. |
| `measure_tail_exit.py` | Measures where digi's tail leaves the tuta in the rest pose: the belt's tail port and the runtime's `TAIL_EXIT` grommet come from it. Reads `work/claude_suit_wardrobe_tuta.blend`. |
| `probe_petals.py` | A front-view ASCII map of where the petal ring hides the suit: used to place the badges where they read. |
| `inspect_base.py` | Takes stock of the wardrobe base (objects, bones, digi's split seams, the face disc, the eye plate) before cutting; renders to `work/claude_suit_wardrobe_looks/`. |

The DAISY recipes are kept as they ran. Their stage inputs (`claude_suit_base.blend`,
`cyclist_tex.blend`, the scan folders) were working files and are not in the
repository; the `.blend` here is the finished result. Read them for technique
and reuse their functions (weight transfer, bone parenting, MToon materials,
BVH-projected decals) for new garments. The two partial stages write their
check VRMs to `work/`, never to the library VRM.

## Layers

Skinned layers follow the body; rigid ones are parented to a bone.

| Object | Materials | Kind |
| --- | --- | --- |
| `jacket`, `tie`, `shirt`, `pants` | `Jacket`, `Tie`, `shirt`, `pants` | digi's suit, skinned |
| `jersey` | `jersey`, `jersey_collar` | shirt pushed out 7 mm, rolled neck on its own material; skinned |
| `knickers`, `socks` | `knickers`, `socks` | skinned |
| `boater` (+ `boater_band`) | `straw`, `ribbon` | head bone |
| `coat_skirt` | `Jacket` (paints match the jacket) | knee-length, written hip-to-thigh weights |
| `shirt_rolled` | `shirt_rolled` | sleeves rolled below the elbow; skinned |
| `acc_glasses`, `acc_headset`, `acc_headband`, `acc_ribbons` | `acetate`; `leather_black`, `bakelite`, `nickel`; `terry_pink`, `terry_teal`; `satin_teal` | head bone |
| `acc_pocket`, `acc_bowtie`, `acc_boutonniere` | `vinyl`, pens, `chrome`; `silk_green`; `bout_petal`, `bout_disc`, `bout_stem` | chest bone |
| `acc_hoodie`, `acc_patches` | `fleece`, `cord`; `patches` | skinned, weights from the surface they lie on |
| `tuta` | `tuta` | skinned (from digi's shirt + pants, weights kept) |
| `uf_boots` | `boot_upper`, `boot_sole`, `webbing`, `buckle` | skinned (the foot from digi's loafer; the shaft's weights from the skin) |
| `uf_straps` | `webbing`, `buckle` | skinned (weights from the tuta): the belt, the thigh strap, the zip puller |
| `mod_red`, `mod_gold`, `mod_chrome`, `mod_warning`, `mod_spray` | `mod_<key>` (painted face + emissive rim) | bone-parented, hidden until pinned |
| `acc_sundisc` | `sundisc` | head bone, hidden unless `sunDisc(true)` |

`BodyActual`, `face`, `Body`, `flower` and `shoes` are digi's and are always
shown.

## Add a garment

1. Open the `.blend` in Blender with the VRM add-on, or script it headlessly
   with `bash run_blender.sh <your_script.py>` from the repository root.
2. Build from what the garment lies on so it inherits skin weights: duplicate
   and push out a garment, or copy weights from the nearest vertex of the
   jacket or jersey (`copy_weights` in `build_era_garments.py`). Loose cloth
   such as a skirt needs weights written on purpose. Parent rigid accessories
   to a bone (`bone_parent`).
3. Give it an MToon material with a distinct name. The runtime paints by
   material name and hides layers by object name.
4. Save the `.blend` and build the library VRM (the TuTa stage exports it):
   `bash run_blender.sh eidoverse/assets/vrms/claude_suit_wardrobe_src/build_tuta.py`.
5. Add the object name to `OPTIONAL` in `eidoverse/claudesona_wardrobe.js`
   (a layer missing from it is always visible) and add a `WARDROBE` preset.
6. Review it in the engine, because MToon there is the truth rather than EEVEE:
   `python vrm_turntable.py --outfits <preset> --frames head,body`.

## The TuTa

The outfit of the UNKNOWN FORCE music video (2026-10), the `tuta` preset:

- **the tuta**: Thayaht's 1920 TuTa, the one-piece T-cut overall, re-cut as black techwear (one skinned garment from
  digi's shirt and pants);
- **techwear boots**, the belt (open at the back round the tail), a thigh strap and the zip puller;
- **the modificanti**: Balla's snap-on shapes, five bone-parented neon badges, one per camp of the AI argument,
  hidden until pinned;
- optional **`acc_sundisc`**: Balla's segmented sun disc behind the petal ring.

The surface look (the weave, seams, neon piping, colour blocking, the zip, the ghosts, the face paint and the
catchlights) is TSL in [`eidoverse/claudesona_wardrobe.js`](../../../claudesona_wardrobe.js), which wears the VRM at runtime.
`../claude_suit_wardrobe_preview_tuta.jpg` shows the outfit with all five badges pinned.

The runtime is `makeWardrobe(THREE, vrm, { wear: 'tuta' })` in `claudesona_wardrobe.js`: on this VRM it adds the
badge, face-paint, sun-disc and neon controls (`pin`, `unpin`, `schedule`, `facePaint`, `sunDisc`, `neon`,
`update(t)`); see the [characters guide](../../../../AGENTS.md). The eye catchlights are
part of the TuTa's look and come on only with the `tuta` preset; every other preset looks as it did on the DAISY build.

### Rebuild the TuTa

From the repository root:

```bash
python eidoverse/assets/vrms/claude_suit_wardrobe_src/paint_badges.py         # badge art, ghost atlas, sun disc
bash run_blender.sh eidoverse/assets/vrms/claude_suit_wardrobe_src/build_tuta.py   # -> work/claude_suit_wardrobe_tuta.blend + the VRM
```

Only through `run_blender.sh`, the isolated runner (see the [Blender guide](../../../../docs/blender.md)): a
bare `--factory-startup` run against your real Blender profile deletes your extension packages. The build needs the
VRM add-on. The `.blend` it saves is a by-product (30 MB) and is not committed. Review the result in the engine,
because MToon there is the truth rather than EEVEE (`python vrm_turntable.py --vrm eidoverse/assets/vrms/claude_suit_wardrobe.vrm --outfits - …`
shows the raw VRM; the outfit's surface needs `claudesona_wardrobe.js`).

The zip line is defined twice, in `build_tuta.py` (`ZIP_TOP`/`ZIP_BOT`, Blender x/z, for the puller) and in
`claudesona_wardrobe.js` (glTF x/y): keep the two in step. `paint_badges.py` sets the CLANKER stencil in Windows' Impact
when it is installed, else in the bundled Anton.

### What the TuTa build taught

- digi's shirt has split seams along the sleeves and cracks when pushed out: weld them (`remove_doubles`) first. The
  pants are closed, and so is the shirt at the neck, so there is no neckline to extrude a collar from.
- MToon's dark side is `shadeColorNode`: a `colorNode` override alone leaves the unlit side showing the old texture.
- `Vector.to_4d()` sets w = 1, so a matrix built from `to_4d()` axis rows is projective. Build frames with
  `Matrix((u, v, n)).transposed().to_4x4()`.
- The library wardrobe's `wear()` resets every material to the nodes it captured at construction: install TSL
  before making it, or it wipes them (`claudesona_wardrobe.js` does).
- A bone-parented object exports to glTF with Blender local Z as node +Y: the badge normal is the node's +Y and the
  badge's up is its −Z.
- Polygon signed distances need consistent winding (the runtime re-orders each polygon to CCW).
- Under the boots, tuck the tuta thin (2 mm): a shaft lofted round the pants reads as a stovepipe gaiter.
- The tail leaves the cloth on the belt line, not where the line from the hips to the first tail bone suggests:
  the tail's root is weighted to the hips, so measure where the whole tail island crosses the cloth.
- An ejected badge flies in world space: the runtime moves it to the scene root for the flight and back to its bone
  on the next pin.

## What the build taught

- digi's jacket is a cutaway: about 0.84 m at the back hem and 1.1 m at the
  front. A long coat therefore needs its own skirt worn under the jacket.
- A skirt copying nearest-vertex weights lets the legs pass through it. Write
  hips at the waist, blending into each thigh toward the knee.
- A garment pushed a few millimetres out of the shirt opens digi's split
  seams. Dark garments wear the shirt underneath, painted the same colour, so
  any crack shows cloth.
- Export with `export_invisibles=True`, or hidden layers are dropped.
- The orange ring around the face is split-skinned: its top arc rides the
  head, its bottom arc the `petals base lower` bone. That bone used to hang
  from the neck, so every nod or tilt swung the arc down into the collar and
  the lapels showed through it. It now hangs from a chest pivot that follows
  only the neck's turn about the body's vertical (`ring_pivot.py`). Following
  less of the turn stretches the ring into folds (none of it) or breaks the
  lapel tip into fragments (60% of it), so the turn stays whole; big turns
  still bring a lapel tip through the side of the ring, as before.
- The petals are spring bones. Folding them under a hat means rewriting each
  chain's rest pose at runtime, which the wardrobe's `fold` does.

## Credits and licence

`claude_suit.vrm` was modelled by **digi**
([x.com/digi_dot_exe](https://x.com/digi_dot_exe)) and is provided under
CC-BY. The claudesona character design is by **voooooogel**
([x.com/voooooogel](https://x.com/voooooogel)). This wardrobe is a derivative, shared under the same CC-BY terms with
credit to digi. The garments, accessories, patches and baked maps were made
by Claude (Opus 5.5) with Skye for the DAISY music video; the tuta, boots, straps, badges, disc, their art and
their scripts for UNKNOWN FORCE (references: Thayaht's TuTa, 1920, Museo del Tessuto, Prato; Balla's *Il vestito
antineutrale*, 1914). The TuTa's weave and leather grain are CC0 AmbientCG maps fetched into the texture library
(see [`../claude_suit_wardrobe_tex/README.md`](../claude_suit_wardrobe_tex/README.md)). Two CC0 scans were
baked into the cyclist maps: Poly Haven `wool_boucle` (jersey knit) and
TextureCan 181 (knickers tweed). Both can be fetched again with
`fetch_texture.py`. See [CREDITS](../../../../CREDITS.md).
