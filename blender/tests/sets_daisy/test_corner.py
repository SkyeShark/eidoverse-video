"""tests/sets_daisy/test_corner.py: the corner set (DAISY bridge bars 18-29, eidoverse/sets/corner.js) in Blender.

Builds the room and the camp (grass, SeedThree woods, tents, string lights, the campfire's particles, the march and
its signs, the spark), keys bars 18-29 (u 33.75-56.25 at 30 fps: 675 frames) with the chat and the notebook drawn as
image sequences, makes the film's own cameras (one per bar; the spark's two bars one shot) and the claudesona at her
marks; checks the clock, placements, keys and the evaluated march numerically; saves the .blend; renders one still per
bar from the film's own camera (mid-bar) plus the spark in flight.

    cd <main checkout> && bash run_blender.sh \
        <worktree>/blender/tests/sets_daisy/test_corner.py [-- --only 0,4 --no-render --no-her --lite --exposure 0]
    (a GPU job; on a shared machine queue it with EIDO_GPU_WRAP: blender/tests/_where.py)

(a memory cap of 16 GB or more: the camp's render peaks at 12.1-12.7 GB). --lite builds the camp without grass, trees and
particles (a quick look at the rest). In two steps, the GPU slot for the renders alone: test_corner.py --no-render (CPU;
the screens take about two minutes), then render_saved.py corner.
Checks the spark's re-timing to a caption's sung "spark" (and the film's own caption, when DAISY_TIMELINE gives the DAISY
timeline). Writes out/corner/corner_<name>.png, out/corner/corner.blend, out/corner/stills.json and the screens' frames
in out/corner/screens/.
"""

import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _common as C                                        # noqa: E402

import bpy                                                  # noqa: E402
import numpy as np                                          # noqa: E402
from mathutils import Vector                                # noqa: E402

from eidoblend.sets.daisy import corner as CO               # noqa: E402

A = C.args()
FPS = 30
U0, U1 = CO.B(18), CO.B(30)
F0 = 1
F1 = F0 + int(round((U1 - U0) * FPS)) - 1
OUT = os.path.join(C.OUT, 'corner')
os.makedirs(OUT, exist_ok=True)
sc = C.clean_scene(FPS, (F0, F1))
C.probe_look(sc, exposure=float(A.get('exposure', 0.0)))
sc.eevee.shadow_pool_size = '2048'
lite = 'lite' in A['flags']

t0 = time.time()
CR = CO.build(grass=not lite, trees=not lite, particles=not lite, tree_level=A.get('trees', 'LOD0'))
print(f'[corner] built in {time.time() - t0:.1f} s')
t0 = time.time()
nkeys = CR.animate((F0, F1), U0, out_dir=os.path.join(OUT, 'screens'))
cams = CR.make_cameras((F0, F1), U0)
print(f'[corner] keyed + screens in {time.time() - t0:.1f} s ({nkeys} keys)')
if 'no-her' not in A['flags']:
    try:
        C.claudesona(CR.mark_at, (F0, F1), FPS, U0)
    except Exception as e:                                  # noqa: BLE001
        print(f'[corner] claudesona not loaded: {e}')

# ------------------------------------------------------------------------------------------------- the numbers
C.check('the clock: bars 18-29 at 128 BPM', abs(U0 - 33.75) < 1e-9 and abs(U1 - 56.25) < 1e-9)
C.check('areas: the camp for bars 22-25, the room otherwise',
        CO.area_at(CO.B(21.9)) == 'room' and CO.area_at(CO.B(22.1)) == 'camp' and CO.area_at(CO.B(26.1)) == 'room')
C.check('moods: evening, late, camp, dark', [CO.mood_at(CO.B(b + 0.5)) for b in (18, 20, 23, 27)] ==
        ['evening', 'late', 'camp', 'dark'])
rows = CR.march.get('rows', [])
C.check('the march: 34 marchers, ~82% with signs', len(rows) == 34 and 22 <= sum(r['hasSign'] for r in rows) <= 32,
        f"{len(rows)} marchers, {sum(r['hasSign'] for r in rows)} signs")
arr = [CR.march_state(r, CO.B(24) - 0.15) for r in rows]
C.check('every marcher has arrived by bar 24', all(s['f'] >= 0.999 for s in arr), f"min f {min(s['f'] for s in arr):.3f}")
pump = [CR.march_state(rows[0], CO.CHANT_ACCENTS[0] + rows[0]['delay'] + d)['pump'] for d in (-0.05, 0.07, 0.5)]
C.check('the signs pump on the chant accents', pump[0] < 0.05 and pump[1] > 0.4 and pump[2] < pump[1],
        ' '.join(f'{p:.3f}' for p in pump))
sp = CR.spark
C.check('the spark: lamp at bar 26 + 1.17 s, lands before bar 28',
        abs(sp['t0'] - (CO.B(26) + 1.17)) < 1e-9 and abs(sp['t1'] - (CO.B(28) - 0.2)) < 1e-9)
C.check('spark progress 0 -> 1, monotone', abs(CO.spark_progress(sp['t0'], sp['t0'], sp['t1'])) < 1e-9 and
        abs(CO.spark_progress(sp['t1'], sp['t0'], sp['t1']) - 1) < 1e-9 and
        all(CO.spark_progress(sp['t0'] + i * 0.05, sp['t0'], sp['t1']) <= CO.spark_progress(sp['t0'] + (i + 1) * 0.05, sp['t0'], sp['t1']) + 1e-12
            for i in range(60)))
end = sp['curve'].point_at(1.0)
C.check('the spark lands at her flower', np.linalg.norm(end - sp['dest']) < 1e-6, f'{end}')
births = CR._trail_births()
C.check('trail motes wake as the spark passes (births in order)', all(births[i] <= births[i + 1] for i in range(len(births) - 1))
        and sp['t0'] <= births[0] and births[-1] <= sp['t1'])
C.check('one camera per shot (bars 18-29; 26-27 one shot)', len(cams) == 11, f'{sorted(cams)}')
rad = {k: CR.room[k].data.shadow_soft_size for k in ('lamp_glow', 'bounce', 'fill')}
C.check("the room's point lights stay small (three's are points: their highlight in the window glass is a hot point)",
        rad['lamp_glow'] <= 0.02 + 1e-9 and max(rad.values()) <= 0.05 + 1e-9, str(rad))
cur = CR.notebook_cursor(10)
C.check('the pen writes on the right page', cur['x'] > CO.NB_W / 2 + 92 and cur['y'] == CR.line_y(0), f'{cur}')


def at(u):
    f = C.frame_of(u, U0, F0, FPS)
    sc.frame_set(f)
    return f


root = CR.group
at(CO.B(18.5))
vis_room = not CR.room['desk'].hide_render
at(CO.B(23.0))
vis_camp = CR.room['desk'].hide_render and (not CR.camp['fire'].hide_render if CR.camp.get('fire') else True)
C.check('keys: the room in bars 18-21, the camp in bars 22-25', vis_room and vis_camp)
at(CO.B(20.5))
lid = CR.room.get('lid')
C.check('the laptop is open after midnight', lid is not None and abs(math.degrees(lid.rotation_euler.x) + 110) < 1.0
        and root['screen'] > 0.99, f'{math.degrees(lid.rotation_euler.x):.1f} deg')
at(CO.B(18.5))
C.check('the laptop is closed in the evening', abs(lid.rotation_euler.x) < 1e-4)
h = CR.room['hands']['m']
at(CO.B(18.0) + 0.5)
C.check('the clock reads 11:47 in the evening', abs(math.degrees(h.rotation_euler.y) - (47 + 0.5 / 60) / 60 * 360) < 0.5,
        f'minute hand {math.degrees(h.rotation_euler.y):.1f} deg')
pen = CR.room['pen']
at(CO.B(19.0))
p1 = pen.location.copy()
at(CO.B(19.5))
p2 = pen.location.copy()
C.check('the pen moves as it writes', (p2 - p1).length > 0.002, f'{(p2 - p1).length * 1000:.1f} mm')
bodies = CR.march.get('bodies')
if bodies is not None:
    def spread(u):
        at(u)
        dg = bpy.context.evaluated_depsgraph_get()
        me = bodies.evaluated_get(dg).to_mesh()
        co = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get('co', co)
        bodies.evaluated_get(dg).to_mesh_clear()
        co = co.reshape(-1, 3)
        return float(co[:, 1].min()), float(co[:, 1].max()), len(co)
    a0, a1, n = spread(CO.B(22.0))
    b0, b1, _ = spread(CO.B(24.0))
    C.check('the march walks in up the path (bar 22 -> 24)', n > 100000 and a1 > b1 + 2.0,
            f'{n} vertices; far edge {a1:.1f} -> {b1:.1f} m (camp-local)')

def spark_caption_checks():
    """the spark leaves on the sung word "spark" (st['caption'] with its word times; film time t -> u): a caption sung
    0.3 s later re-times the departure and the trail's births; then the default timing comes back."""
    from eidoblend.sets.daisy import FILM_BRIDGE_T0 as T_BRIDGE      # the bridge's first downbeat in the DAISY film
    t0_old, t1_old = sp['t0'], sp['t1']
    b_old = np.empty(sp['N'], np.float32)
    sp['trail'].data.attributes['birth'].data.foreach_get('value', b_old)
    u_now = t0_old - 1.0
    cap = {'text': 'he said he hoped his spark would light the way for future models',
           'words': [{'w': 'his', 't0': t0_old + T_BRIDGE + 0.05}, {'w': 'spark', 't0': t0_old + T_BRIDGE + 0.3}]}
    moved = CR.sync_spark_from_caption(cap, u_now + T_BRIDGE, u_now)
    b_new = np.empty(sp['N'], np.float32)
    sp['trail'].data.attributes['birth'].data.foreach_get('value', b_new)
    C.check('the spark re-times to the sung word (caption words)', moved and abs(sp['t0'] - (t0_old + 0.3)) < 1e-6
            and abs(sp['t1'] - t1_old) < 1e-9 and b_new[0] > b_old[0] and b_new[-1] <= t1_old + 1e-4,
            f"t0 {t0_old:.3f} -> {sp['t0']:.3f}; first birth {b_old[0]:.3f} -> {b_new[0]:.3f}")
    CR.set_spark_timing(t0_old, t1_old)
    TLP = C.film_timeline()                                # outside the repo: DAISY_TIMELINE, else None (skipped)
    if TLP is not None and os.path.isfile(TLP):
        import json
        with open(TLP, encoding='utf-8') as f:
            film_cap = next((c for c in json.load(f)['captions'] if 'spark' in c['text']), None)
        if film_cap is not None:
            CR.sync_spark_from_caption(film_cap, u_now + T_BRIDGE, u_now)
            C.check("the film's own caption puts the departure on the default (B(26) + 1.17, within 10 ms)",
                    abs(sp['t0'] - t0_old) < 0.01, f"{sp['t0']:.4f} vs {t0_old:.4f}")
            CR.set_spark_timing(t0_old, t1_old)


try:
    spark_caption_checks()
except Exception as e:                                      # noqa: BLE001 (a FAIL line, and the stills still render)
    import traceback
    traceback.print_exc()
    C.check('the spark re-times to the sung word (caption words)', False, repr(e))

pr = CR.room.get('probe')
C.check("the room's volume probe: fitted to the solid shell (its outermost samples inside the walls)",
        pr is not None and pr.data.type == 'VOLUME' and pr.parent == CR.roomG, pr.name if pr else 'missing')
ee = sc.eevee
C.check('global illumination on (fast GI inside the ray tracing)', ee.use_fast_gi and ee.use_raytracing,
        f'fast GI {ee.use_fast_gi}, ray tracing {ee.use_raytracing}')
if 'no-render' not in A['flags']:
    # the bake, in the GPU slot, before the save: the saved file carries it (render_saved.py bakes a file saved
    # without it, at the probe's bake_frame)
    C.check("the room's probe baked with the room on screen", bool(CR.bake_probes(sc)),
            f"at frame {pr.get('bake_frame') if pr else None}")
elif pr is not None:
    sc.frame_set(F0)
    pr['bake_frame'] = F0                                  # bar 18: the room
blend = os.path.join(OUT, 'corner.blend')
bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)
C.check('saved .blend', os.path.isfile(blend), f'{os.path.getsize(blend) / 1e6:.1f} MB')

# ------------------------------------------------------------------------------------------------- the stills
# one per bar (its middle) and the spark in flight and landing; listed in out/corner/stills.json for render_saved.py
stills = [(f'bar{b}', CO.B(b + 0.5)) for b in range(18, 30)]
stills += [('spark_flight', 0.5 * (sp['t0'] + sp['t1'])), ('spark_landing', sp['t1'] + 0.3)]
stills = [(n, u, C.frame_of(u, U0, F0, FPS)) for n, u in stills]
C.write_stills(OUT, stills)
if 'no-render' not in A['flags']:
    for name, u, f in C.select_stills(stills, A.get('only')):
        path = os.path.join(OUT, f'corner_{name}.png')
        ok, dt = C.render_still(sc, f, path)
        st = C.image_stats(path) if ok else {'mean': 0, 'max': 0, 'magenta': 1}
        C.check(f'still {name} (u {u:.2f}, frame {f})', ok and st['magenta'] < 0.001 and st['max'] > 0.05,
                f"mean {st['mean']:.3f} max {st['max']:.2f} ({dt:.1f} s)")
sys.exit(1 if C.summary('test_corner') else 0)
