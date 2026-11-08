"""Every animated solid EXAMPLE baked over a few frames and rendered at the first and last: the red shoggoth (tentacles,
pulse, blinking darting eyes), the explosion (the radius pulse, the rising noise), the stylized blob (its domain warp)
on the per-frame atlas sequence, and the gyroid recipe (its palette drifts with uTime).

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/sdf/test_animated_examples.py [-- frames=3 time_scale=20]

out/anim_examples_f0001.png, _f0003.png and anim_examples_sheet.png. PASS lines: each bake wrote its frames, the
player shows different geometry (or colour) at the first and last frame, the atlas sequence's mesh carries its UV
map, every example renders.
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

import bpy  # noqa: E402

from eidoblend import sdf  # noqa: E402

A = C.args()
FRAMES = int(A.get('frames', '3'))
TS = float(A.get('time_scale', '20'))
CACHE = os.path.join(C.OUT, 'cache_anim_ex')

sc = C.stage(1280, 540, 16, world_color=(0.2, 0.2, 0.22), world_strength=1.0, sun=False, floor_color=(0.18, 0.18, 0.18))
import math  # noqa: E402
from mathutils import Vector  # noqa: E402
for i, (d3, col, k) in enumerate([((5.0, 8.0, 5.0), (1.0, 0.94, 0.85), 1.1), ((-4.0, 3.0, -6.0), (0.35, 0.5, 0.85), 0.32)]):
    ld = bpy.data.lights.new(f'key{i}', 'SUN')
    ld.energy, ld.color, ld.angle = math.pi * k, col, math.radians(1.5)
    ob = bpy.data.objects.new(f'key{i}', ld)
    sc.collection.objects.link(ob)
    ob.rotation_euler = Vector((d3[0], -d3[2], d3[1])).normalized().to_track_quat('Z', 'Y').to_euler()
sc.frame_start, sc.frame_end = 1, FRAMES

# (example, overrides, location, scale)
LINEUP = [
    ('red_shoggoth', {'cells': 300}, (-2.7, 0.4, 0.0), 0.62),
    ('explosion', {'cells': 200}, (-0.6, 0.0, 0.0), 0.5),
    ('stylized_blob', {'cells': 128, 'carrier': 'atlas_sequence'}, (1.1, 0.0, 0.0), 0.55),
    ('gyroid', {'cells': 160}, (2.7, 0.0, 0.0), 0.45),
]
objs = {}
for name, over, loc, s in LINEUP:
    o = sdf.EXAMPLES[name].make(name=f'anim_{name}', cache_dir=CACHE, location=loc, scale=s, log=None, **over)
    o.place_on_ground(0.0)
    o.bake(1, FRAMES, time_scale=TS, log=None)
    objs[name] = o
    files = [os.path.join(CACHE, f'anim_{name}_{f:04d}.ply') for f in range(1, FRAMES + 1)]
    C.check(f'{name}: one PLY per frame', all(os.path.exists(p) for p in files),
            f'{FRAMES} frames, carrier {o.stats.get("carrier")}')


def evaluated(obj, frame):
    sc.frame_set(frame)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', co)
    uv = None
    if 'UVMap' in me.uv_layers:
        uv = np.empty(len(me.loops) * 2, np.float32)
        me.uv_layers['UVMap'].data.foreach_get('uv', uv)
        uv = uv.reshape(-1, 2)
    ev.to_mesh_clear()
    return co.reshape(-1, 3), uv


for name, o in objs.items():
    a, uva = evaluated(o.object, 1)
    b, uvb = evaluated(o.object, FRAMES)
    moved = len(a) != len(b) or float(np.abs(a - b).max()) > 0.005
    if name == 'gyroid':
        # the gyroid's shape does not move: its palette does (uTime in sdfTexPalette), carried per vertex
        def colour(frame):
            sc.frame_set(frame)
            dg = bpy.context.evaluated_depsgraph_get()
            ev = o.object.evaluated_get(dg)
            me = ev.to_mesh()
            at = me.attributes.get('sdf_albedo')
            c = np.empty(len(at.data) * 4, np.float32)
            at.data.foreach_get('color', c)
            ev.to_mesh_clear()
            return c.reshape(-1, 4)[:, :3]
        ca, cb = colour(1), colour(FRAMES)
        C.check('gyroid: the palette drifts per frame', len(ca) == len(cb) and float(np.abs(ca - cb).mean()) > 0.01,
                f'mean albedo change {np.abs(ca - cb).mean():.3f}')
    else:
        C.check(f'{name}: the player shows each frame', len(a) > 1000 and moved,
                f'{len(a)} -> {len(b)} vertices')
    if name == 'stylized_blob':
        ok = uva is not None and uvb is not None and float(uva.std()) > 0.01 and 0.0 <= float(uva.min()) and \
            float(uva.max()) <= 1.0
        C.check('blob atlas sequence: the frame mesh carries its UV map', ok,
                'UVMap ' + ('missing' if uva is None else f'{uva.min():.3f}..{uva.max():.3f}'))
        # the packs the first frame left out are its constants on the BSDF (the Principled default emission
        # colour is white: left there, the blob glowed white)
        bsdf = next(n for n in o.material.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        em = bsdf.inputs['Emission Color']
        sheen = bsdf.inputs['Sheen Weight']
        C.check('blob atlas sequence: constant channels on the BSDF', (em.is_linked or max(em.default_value[:3]) == 0.0)
                and abs(sheen.default_value - 0.5) < 1e-6,
                f'emission {"linked" if em.is_linked else tuple(round(x, 3) for x in em.default_value[:3])}, '
                f'sheen {sheen.default_value:.2f}')

if A.get('render', '1') == '1':
    cam = C.camera((0.0, -6.0, 1.5), (0.0, 0.0, 0.62), lens=35)
    shots = []
    for f in (1, FRAMES):
        sc.frame_set(f)
        p = os.path.join(C.OUT, f'anim_examples_f{f:04d}.png')
        C.check(f'render frame {f}', C.render(p), p)
        shots.append(p)
    C.sheet(shots, os.path.join(C.OUT, 'anim_examples_sheet.png'), cols=1)
C.summary()
