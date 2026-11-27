"""The hard-surface kit, built and checked without a render; it also leaves the sample pair the bake test reads.

    bash run_blender.sh blender/tests/props_hardsurface/test_kit.py          (Blender on the CPU, ~1 min)

A sample part made the kit's way: a block (a side outline's prism x a chamfered section's), a boss forged in, a
channel machined along its top, a pin hole cut through and its pin, every edge rounded by its group (finish_forged);
the same function builds its LOW (masses.start(low=True)). Checks (PASS / FAIL):
  sections   a Body's rings: one count from end to end, the keel and the crown on y = 0, stations through `must`
  masses     the high: closed parts, its bevel and weighted-normal modifiers, the edge groups' widths; the low: no
             modifiers, fewer faces, the pin hole left to the bake, round parts at the sagitta's count
  skins      a lofted body, a Surface asked along a ray, an opening's border laid on the skin, a frame swept round it
  lowpoly    the low finished: triangles only, every island a disk, UVs inside the square, the pack's fill
  bake       bake_export's inputs (out/kit_bake/kit_high.npz, kit_low.npz, kit.json) and their shapes
Leaves out/kit_high.blend, out/kit_low.blend (the finished low) and out/kit_bake/ for test_bake.py and test_stills.py.
"""
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend.props.hardsurface import bake_export, lowpoly, masses as hs, skins as sk  # noqa: E402
from eidoblend.props.hardsurface.masses import EG_BODY, EG_CUT, EG_FEATURE, EG_MACHINED  # noqa: E402
from eidoblend.props.hardsurface.sections import Body, stations  # noqa: E402

OUT = os.path.join(HERE, 'out')
BAKE = os.path.join(OUT, 'kit_bake')
FAILS = []


def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg, flush=True)
    if not ok:
        FAILS.append(msg)


def edges(ka, kb, convex):
    """the sample's edge groups (mm): the channel crisp, cuts 0.5, the body's soft contours, a fillet at the boss"""
    if EG_MACHINED in (ka, kb):
        return 0.3
    if EG_CUT in (ka, kb):
        return 0.5
    if ka == kb == EG_BODY:
        return 1.5 if convex else 2.0
    return 1.0 if convex else 2.5


def sample(low=False):
    """the block and its pin, the high (or the low): the same tables"""
    hs.start('kit_low' if low else 'kit_high', low=low)
    clay = hs.mat('clay', (0.5, 0.5, 0.5), 0.6, 0.0)
    side = [(0, 0), (120, 0), (120, 40), (100, 60), (0, 60)]
    sec = [(-20, 0), (20, 0), (20, 50), (14, 60), (-14, 60), (-20, 50)]
    block = hs.boolean(hs.tagged(hs.prism_side('block', side, -20, 20), EG_BODY),
                       hs.tagged(hs.prism_section('block_sec', sec, -5, 125), EG_BODY), 'INTERSECT')
    block = hs.boolean(block, hs.tagged(hs.cyl('boss', (40, -18, 30), (40, -26, 30), 24.0), EG_FEATURE), 'UNION')
    block = hs.boolean(block, hs.tagged(hs.box('channel', (20, -8, 52), (90, 8, 70)), EG_MACHINED), 'DIFFERENCE')
    block = hs.detail(block, hs.tagged(hs.cyl('pin_hole', (40, -40, 30), (40, 40, 30), 8.0, seg=32), EG_CUT), 'DIFFERENCE')
    hs.finish_forged(block, edges, clay)
    hs.finish(hs.cyl('pin', (40, -27.5, 30), (40, 21, 30), 7.8, seg=32), 0.3, clay)
    hs.sweep_tmp()
    hs.apply_transforms()
    return sorted((o for o in hs.col.objects if o.type == 'MESH'), key=lambda o: o.name)


def main():
    os.makedirs(BAKE, exist_ok=True)
    # ------------------------------------------------------------------------------------------- sections
    keys = [(0.0, [(0, 0), (40, 0), (50, 30), (0, 40)], [10.0, 20.0]), (100.0, [(0, 0), (60, 0), (70, 40), (0, 50)], [10.0, 30.0])]
    body = Body(keys, [4, 4, 4], [3, 6])
    rings = [body.ring(x) for x in stations(0.0, 100.0, 20.0, [33.0])]
    check(len({len(r) for r in rings}) == 1, f'sections: every ring has one count ({len(rings[0])} points)')
    h = body.half(50.0)
    check(abs(h[0][0]) < 1e-9 and abs(h[-1][0]) < 1e-9, 'sections: the half-section starts on the keel and ends on the crown (y = 0)')
    check(33.0 in stations(0.0, 100.0, 20.0, [33.0]), 'sections: stations pass through every x in must')
    # ------------------------------------------------------------------------------------------- the high
    hs.new_file()
    high = sample()
    check([o.name for o in high] == ['block', 'pin'], f'masses: the high holds the block and its pin ({[o.name for o in high]})')
    check(all(r[1] == 0 for r in hs.REPORT), f'masses: every high part closed (open edges {[r[:2] for r in hs.REPORT]})')
    blk = high[0]
    bev = blk.modifiers.get('edge_groups')
    check(bev is not None and bev.limit_method == 'WEIGHT' and blk.modifiers.get('flat_faces_flat') is not None,
          'masses: finish_forged gives the block its weighted bevel and its flats-stay-flat modifier')
    lay = blk.data.attributes.get('bevel_weight_edge')
    w = np.zeros(len(blk.data.edges), np.float32)
    if lay is not None:
        lay.data.foreach_get('value', w)
    widths = sorted({round(float(v) * bev.width * 1000, 2) for v in w if v > 0}) if bev else []
    check(len(widths) >= 3 and max(widths) <= 2.6, f'masses: the edges rounded by group, several widths up to 2.5 mm ({widths[:4]} .. {widths[-1:]})')
    dg = bpy.context.evaluated_depsgraph_get()
    hi_tris = sum(len(o.evaluated_get(dg).data.polygons) for o in high)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'kit_high.blend'))
    bake_export.write_high(high, BAKE, 'kit')
    # ------------------------------------------------------------------------------------------- the low
    hs.new_file()
    low = sample(low=True)
    check(all(not o.modifiers for o in low), 'masses: the low has no bevel (the bake carries it)')
    pin = low[1]
    seg_low = len({round(math.atan2(v.co.z - 0.030, v.co.x - 0.040), 4) for v in pin.data.vertices})
    check(16 <= seg_low < 32, f'masses: the low pin at the count its 0.12 mm sagitta allows ({seg_low} round, the high 32)')
    lo_faces = sum(len(o.data.polygons) for o in low)
    check(lo_faces < hi_tris / 4, f'masses: the low is light ({lo_faces} faces against the high\'s {hi_tris} evaluated)')
    rep = lowpoly.prepare_low(low, cells=128)
    check(all(len(p.vertices) == 3 for o in low for p in o.data.polygons), 'lowpoly: the low is triangles only')
    uv = np.concatenate([np.array([d.uv[:] for d in o.data.uv_layers['UVMap'].data]) for o in low])
    check(uv.min() >= -1e-6 and uv.max() <= 1 + 1e-6, f'lowpoly: every UV inside the square ({uv.min():.3f} .. {uv.max():.3f})')
    check(rep['uv_fill'] > 0.35, f'lowpoly: the pack fills {rep["uv_fill"] * 100:.1f} % of the square ({rep["islands"]} islands)')
    meta = bake_export.write_low(low, BAKE, 'kit', size=1024, substrate={'block': 1, 'pin': 5},
                                 options={'ao_mm': 20.0, 'cav_mm': 2.0, 'edge_mm': 4.0, 'corner_mm': 6.0})
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'kit_low.blend'))
    H = np.load(os.path.join(BAKE, 'kit_high.npz'))
    L = np.load(os.path.join(BAKE, 'kit_low.npz'))
    check(H['p'].shape[1:] == (3, 3) and len(H['ar_p']) > 100 and len(H['cc_p']) > 10,
          f'bake: the high\'s triangles ({len(H["p"]):,}), its arris ({len(H["ar_p"]):,}) and corner samples ({len(H["cc_p"]):,})')
    check(L['t'].shape[1:] == (3, 4) and L['uv'].shape[1:] == (3, 2) and set(np.unique(L['part'])) == {0, 1},
          f'bake: the low\'s corners with their tangents, UVs and parts ({len(L["p"]):,} triangles)')
    check(meta['names'] == json.load(open(os.path.join(BAKE, 'kit_high.json')))['names'] and meta['px_per_mm'] > 1.0,
          f'bake: one name list for high and low; {meta["px_per_mm"]:.2f} px/mm at 1024')
    # ------------------------------------------------------------------------------------------- skins
    hs.new_file()
    hs.start('kit_skin')
    clay = hs.mat('clay', (0.5, 0.5, 0.5), 0.6, 0.0)
    xs = stations(0.0, 100.0, 10.0)
    loft = sk.loft_body('skin', body, xs)
    ref = sk.loft_body('skin_ref', body, xs)
    bpy.context.view_layer.update()
    surf = sk.Surface(ref)
    hit = surf.hit((50.0, 300.0, 15.0), (0.0, -1.0, 0.0))
    check(hit is not None and 40.0 < hit[0].y < 70.0 and hit[1].y > 0.5, f'skins: the Surface answers a ray (hit at y {hit[0].y if hit else None})')
    pts = [Vector((x, 80.0, z)) for x, z in sk.round_poly([(35, 8), (65, 8), (65, 22), (35, 22)], 4.0)]
    path = sk.border(surf, pts, (0.0, 1.0, 0.0))
    check(len(path) >= 8, f'skins: the opening\'s border laid on the skin ({len(path)} points)')
    fr = sk.frame('frame', path, [(-2.0, 0.0), (-2.0, 1.0), (4.0, 1.0), (4.0, 0.0)], clay)
    check(fr is not None and len(fr.data.polygons) > 0 and fr.name in hs.col.objects, 'skins: a frame swept round the opening')
    sk.finish_smooth(loft, clay)
    hs.sweep_tmp()
    print(f'[kit] {len(FAILS)} FAIL' if FAILS else '[kit] all checks passed')


if __name__ == '__main__':
    try:
        main()
    except Exception:                                           # noqa: BLE001
        import traceback
        traceback.print_exc()
        FAILS.append('exception')
    sys.stdout.flush()
    os._exit(1 if FAILS else 0)
