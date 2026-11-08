"""Probe: a hardcover book in Blender 5.2 EEVEE (eidoblend.media.book: book_core.js posed in Deno, PC2 caches).

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/media/test_book.py

The template's covers (front, back, spine composed into the wrap by the rig's own composer) and lining, with the
16 Simulacra spreads, on a wooden desk: closed (f1), half open (f13), open on the title spread (f28), a leaf mid-turn
(f40), landed on the next spread (f56). Checks printed: the Mesh Cache reads the exported pose at a frame (a vertex
read back from the evaluated mesh against the PC2 sample), and the book's underside against the desk per frame.
"""
import struct
import sys
from pathlib import Path

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _stage as S  # noqa: E402
from eidoblend.media import book  # noqa: E402

OUT = S.OUT
T = S.ASSETS / 'book_template'
sc = S.fresh_scene(frames=(1, 60))
# a large soft light over thin paper: at 16 samples EEVEE's one shadow ray per sample stippled the turning leaf's
# penumbra on the page beneath (11-07: translucency off kept it; 4 rays x 12 steps reduce it a lot, but a faint grain
# stays at 16 samples, and 16 steps, filter radius 3, raytracing or fast GI off do not change that)
sc.eevee.shadow_ray_count = 4
sc.eevee.shadow_step_count = 12
plan = book.schedule((1, 60), open=[(1, 0.0), (24, 1.0)], turns=[(31, 50)])
b = book.make_book(OUT / 'book_work', plan, size=(0.15, 0.222, 0.026),
                   cover={'front': T / 'front.png', 'back': T / 'back.png', 'spine': T / 'spine.png', 'color': '#1e4d2b'},
                   spreads=sorted((S.ASSETS / 'book_spreads').glob('*.jpg')), lining=T / 'lining.png', wrap_res=2048)
print('[book] metrics', {k: (round(v, 4) if isinstance(v, float) else v) for k, v in b.metrics.items()})
print('[book] parts', {k: len(o.data.vertices) for k, o in b.parts.items()})

# the desk under it, a window light, a lamp
desk = S.box(sc, 'desk', (1.4, 0.9, 0.04), (0.05, 0.1, -0.02),
             S.pbr_material('desk_wood', S.cached('textures', 'PaintedWood009C_2k'), scale=1.4))
b.root.rotation_euler.z = 0.12
S.area_light(sc, (-0.6, -0.4, 0.75), (0, 0, 0), 30.0, size=0.7, color=(1.0, 0.93, 0.84), name='window')
S.area_light(sc, (0.7, 0.3, 0.6), (0, 0, 0), 6.0, size=0.8, color=(0.8, 0.86, 1.0), name='fill')
S.camera(sc, (0.05, -0.38, 0.36), (0.0, 0.0, 0.0), lens=35)

# the cache reads the exported pose: frame 40's case vertex 100 from the evaluated mesh against the PC2 sample
case = b.parts['case']
f = 40
sc.frame_set(f)
dg = bpy.context.evaluated_depsgraph_get()
ev = case.evaluated_get(dg)
me = ev.to_mesh()
got = np.array(me.vertices[100].co)
ev.to_mesh_clear()
with open(b.out / 'case.pc2', 'rb') as fh:
    hd = fh.read(32)
    n = struct.unpack('<i', hd[16:20])[0]
    fh.seek(32 + (f - 1) * n * 12 + 100 * 12)
    want = np.frombuffer(fh.read(12), dtype='<f4')
print(f'[book] cache read-back at frame {f}: evaluated {np.round(got, 6)} vs PC2 {np.round(want, 6)} -> '
      f'{"OK" if np.abs(got - want).max() < 1e-6 else "MISMATCH"}')
print('[book] underside per frame (m, below 0 = into the desk):',
      [(fr['f'], round(fr['minZ'] - b.info['frames'][0]['minZ'], 5)) for fr in b.info['frames'][::6]])
print('[book] page turn sound events', b.page_turn_events())
for fr in (1, 13, 28, 40, 56):
    st = b.frame_state(fr)
    print(f'[book] frame {fr}: page {st["page"]} open {st["open"]:.2f} turn {st["turn"]} slots',
          [(s['recto'], s['verso']) for s in st['slots']])
    S.render_still(sc, fr, OUT / f'book_f{fr:03d}.png')
print('[test_book] done')
