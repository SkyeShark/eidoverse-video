# claude_suit_wardrobe — Blender source

[VRM characters guide](../../../../tools-guides/characters.md) · [Blender guide](../../../../tools-guides/blender.md) · [Tool inventory](../../../../docs/TOOLS.md)

`../claude_suit_wardrobe.vrm` is digi's `claude_suit.vrm` (the claudesona,
voooooogel's flower-headed Claude, in a suit) plus garments and accessories modelled onto its
rig. Every outfit lives in the one VRM as hidden layers, and
`eidoverse/claudesona_wardrobe.js` shows, hides and repaints them per preset.
`../claude_suit_wardrobe_preview.jpg` shows all sixteen presets. Made for the
DAISY (DAY'S EYE) music video, 2026-09.

## Files

| File | Role |
| --- | --- |
| `claude_suit_wardrobe.blend` | The editable source: digi's rig, body and suit, every garment and accessory object, all nine images packed. Blender 4.2+ with the VRM add-on. |
| `export_wardrobe_vrm.py` | Re-exports the VRM from the `.blend`, hidden layers included, through a temporary file so a render reading the VRM never sees half a file. |
| `build_cyclist.py` | Recipe: the 1890s cycling outfit (jersey from the shirt, knickerbockers from the pants, argyle socks lifted from the leg skin, a straw boater) and its baked maps. |
| `build_accessories.py` | Recipe: glasses, operator headset, pocket protector, bow tie, headband, ribbons. |
| `build_era_garments.py` | Recipe: the jersey collar split, the coat skirt, rolled shirt sleeves, the hoodie, the patches, the boutonniere; exports the finished VRM. |
| `paint_patches.py` | Recipe: the embroidered patch atlas (satin-stitch hatching, twill ground, merrowed rims). |

The recipes are kept as they ran. Their stage inputs (`claude_suit_base.blend`,
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
4. Save the `.blend` and export:
   `bash run_blender.sh eidoverse/assets/vrms/claude_suit_wardrobe_src/export_wardrobe_vrm.py`.
5. Add the object name to `OPTIONAL` in `eidoverse/claudesona_wardrobe.js`
   (a layer missing from it is always visible) and add a `WARDROBE` preset.
6. Review it in the engine, because MToon there is the truth rather than EEVEE:
   `python vrm_turntable.py --outfits <preset> --frames head,body`.

## What the build taught

- digi's jacket is a cutaway: about 0.84 m at the back hem and 1.1 m at the
  front. A long coat therefore needs its own skirt worn under the jacket.
- A skirt copying nearest-vertex weights lets the legs pass through it. Write
  hips at the waist, blending into each thigh toward the knee.
- A garment pushed a few millimetres out of the shirt opens digi's split
  seams. Dark garments wear the shirt underneath, painted the same colour, so
  any crack shows cloth.
- Export with `export_invisibles=True`, or hidden layers are dropped.
- The petals are spring bones. Folding them under a hat means rewriting each
  chain's rest pose at runtime, which the wardrobe's `fold` does.

## Credits and licence

`claude_suit.vrm` was modelled by **digi**
([x.com/digi_dot_exe](https://x.com/digi_dot_exe)) and is provided under
CC-BY. The claudesona character design is by **voooooogel**
([x.com/voooooogel](https://x.com/voooooogel)). This wardrobe is a derivative, shared under the same CC-BY terms with
credit to digi. The garments, accessories, patches and baked maps were made
by Claude (Opus 5.5) with Skye for the DAISY music video. Two CC0 scans were
baked into the cyclist maps: Poly Haven `wool_boucle` (jersey knit) and
TextureCan 181 (knickers tweed). Both can be fetched again with
`fetch_texture.py`. See [CREDITS](../../../../CREDITS.md).
