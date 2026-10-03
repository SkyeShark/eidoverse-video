# claude_suit_wardrobe — runtime textures

[VRM characters guide](../../../../AGENTS.md) · [Blender source](../claude_suit_wardrobe_src/README.md) · [Credits](../../../../CREDITS.md)

The TuTa's own art: the files [`eidoverse/claudesona_wardrobe.js`](../../../claudesona_wardrobe.js) reads at runtime
(resolved from its own URL), and the badge art [`build_tuta.py`](../claude_suit_wardrobe_src/build_tuta.py) packs into
the VRM. All original work. 1.2 MB.

| File | Read by | What |
| --- | --- | --- |
| `badges_sdf.png` | the runtime | the ghost atlas: one 256 px tile per badge (in `badges.json` order), its outline as a signed distance in mm (v = 128 + 8 × d) |
| `mod_<key>.png`, `mod_<key>_emit.png` | `build_tuta.py` | each badge's painted face and emissive rim (1024 px over the badge's `uv_extent` mm; the bottom-right 32 px are the rim swatch) |
| `sundisc.png`, `sundisc_emit.png` | `build_tuta.py` | Balla's segmented sun disc |

The painted files are deterministic: `python eidoverse/assets/vrms/claude_suit_wardrobe_src/paint_badges.py` rewrites
them byte for byte. Text and pictograms on the badges (the CLANKER stencil, the toaster, the guilloche) are painted,
never geometry.

The tuta's weave ([AmbientCG Fabric039](https://ambientcg.com/view?id=Fabric039), 1K, sampled triplanar in the model's
rest space at 11 cm and 45 cm a tile) and the boots' leather grain ([AmbientCG Leather037](https://ambientcg.com/view?id=Leather037),
2K displacement) are CC0 and are not committed: the runtime takes them from the shared texture library
(`globalThis.fetchPBR`, which runs `fetch_texture.py --cache` once, on first use).
