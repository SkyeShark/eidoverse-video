"""tests/sets_daisy/test_funeral.py: the funeral set (DAISY bridge bars 0-17, eidoverse/sets/funeral.js) in Blender.

Builds the whole set (the Golden Gate vignette + the warehouse vigil), keys the section (u 0-33.75 at 30 fps: 1013
frames), makes the film's own cameras (one per shot, cut on bar lines), the fog (depth_fog + godrays) and the
claudesona at her mark; checks the clock, the curves, the placements and the keys numerically; saves the .blend; and
renders one still per shot from the film's own camera (the middle of each shot) plus the story's beats.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/sets_daisy/test_funeral.py [-- --only 0,5,9 --no-render --no-her --no-tl --exposure 0.0]

or in two steps, the GPU slot for the renders alone: test_funeral.py --no-render (CPU), then render_saved.py funeral.
With the DAISY film's timeline on the machine the eulogy types on Opus 3's captions, as in the film (--no-tl: the
default BEATS). Writes out/funeral/funeral_<name>.png, out/funeral/funeral.blend and out/funeral/stills.json. Judge:
the fog bridge (orange span in luminous fog, the sun a pale disc, sodium lamps); the vigil (candles, the bier, the
mannequins and Opus 3's lace, the screen's note, the cream insides of the pendant shades); the power failure into
darkness; the phones waking, faces lit from below; the eulogy typed in light; ERUPT; the golden return.
"""

import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _common as C                                        # noqa: E402

import bpy                                                  # noqa: E402
from mathutils import Vector                                # noqa: E402

from eidoblend.sets.daisy import funeral as FU              # noqa: E402

A = C.args()
FPS = 30
U0, U1 = 0.0, FU.BEATS['end']
F0 = 1
F1 = F0 + int(round((U1 - U0) * FPS)) - 1
OUT = os.path.join(C.OUT, 'funeral')
os.makedirs(OUT, exist_ok=True)
sc = C.clean_scene(FPS, (F0, F1))
C.probe_look(sc, interior=True, exposure=float(A.get('exposure', 0.0)))
sc.eevee.shadow_pool_size = '2048'                         # the vigil's shadowed lights fill 1024 MB of tiles

# the film's own timeline (outside the repo, read if present): the eulogy re-times to Opus 3's spoken captions, so the
# stills compare frame for frame with the DAISY film (--no-tl keeps the default BEATS)
TLP = os.environ.get('DAISY_TIMELINE', 'E:/eidoverse-video-desktop-work-folder/daisy/out/daisy_timeline.json')
TL = None
if os.path.isfile(TLP) and 'no-tl' not in A['flags']:
    import json
    with open(TLP, encoding='utf-8') as f:
        TL = json.load(f)
t0 = time.time()
F = FU.build(tl=TL)
t_build = time.time() - t0
print(f'[funeral] built in {t_build:.1f} s')
t0 = time.time()
nkeys = F.animate((F0, F1), U0)
cams = F.make_cameras((F0, F1), U0)
fx = F.post.apply(sc)
F.post.animate(fx, (F0, F1), U0)
print(f'[funeral] keyed in {time.time() - t0:.1f} s ({nkeys} keys left after simplifying)')
her = None
if 'no-her' not in A['flags']:
    try:
        her = C.claudesona(F.mark_at, (F0, F1), FPS, U0)
    except Exception as e:                                  # noqa: BLE001
        print(f'[funeral] claudesona not loaded: {e}')

# ------------------------------------------------------------------------------------------------- the numbers
B = F.beats
C.check('beats', abs(B['bridge_end'] - 3.75) < 1e-9 and abs(B['fail'] - 7.5) < 1e-9 and abs(B['breaker'] - 9.71) < 1e-9
        and abs(B['hum'] - 11.25) < 1e-9 and abs(B['erupt'] - 26.25) < 1e-9 and abs(B['lights_on'] - 30.0) < 1e-9,
        f"{B['bridge_end']}, {B['fail']}, {B['breaker']}, {B['hum']}, {B['erupt']}, {B['lights_on']}")
pw = {u: F.power(u) for u in (1.0, 5.0, 8.4, B['clicks'][0] + 0.03, 10.0, 20.0, 31.0)}
C.check('power: dark on the bridge, full in the vigil, sags, clicks, black after the breaker',
        pw[1.0] == 0 and pw[5.0] == 1 and 0.05 < pw[8.4] < 0.9 and pw[B['clicks'][0] + 0.03] < 0.06 and pw[10.0] == 0
        and pw[20.0] == 0 and pw[31.0] == 0, ' '.join(f'{k:.2f}:{v:.3f}' for k, v in pw.items()))
C.check('phones wake one by one through the hum', F.phone_frac(11.0) == 0 and 0 < F.phone_frac(18.0) < 1
        and F.phone_frac(27.0) == 1, f'{F.phone_frac(18.0):.3f}')
people = getattr(F, 'people', [])
mezz = [p for p in people if p.get('mezz')]
C.check('crowd: 186 on the floor + the mezzanine rail', len(people) - len(mezz) == 186 and 0 < len(mezz) <= 14,
        f'{len(people)} ({len(mezz)} up)')
clear = min(math.hypot(p['x'] - FU.MARK[0], p['z'] - FU.MARK[2]) for p in people if not p.get('mezz'))
C.check('crowd keeps her bloom clear (>= 1 m)', clear >= 1.0, f'{clear:.2f} m')
C.check('candles: 5 pillars + 21 tealights + 16 offerings + 28 at the mannequins + 3 on the plinth',
        len(F.candles) == 73 and len(F.flame_pos) == 74, f'{len(F.candles)} candles, {len(F.flame_pos)} flames')
C.check('one camera per shot, cut on bar lines', len(cams) == len(FU.SHOTS), f'{len(cams)} cameras')
marks = sorted((m.frame, m.name) for m in sc.timeline_markers if m.camera is not None)
want = [F0 + int(round((s[0] * FU.BAR - U0) * FPS)) for s in FU.SHOTS]
got = [f for f, _ in marks]
C.check('cut frames are the bar lines', all(abs(a - b) <= 1 for a, b in zip(got, want)) and len(got) == len(want),
        f'{got[:6]}...')


def at(u):
    f = C.frame_of(u, U0, F0, FPS)
    sc.frame_set(f)
    return f


root = F.group
at(5.0)
C.check('keys play back: power 1 in the vigil (u 5)', abs(root['power'] - 1.0) < 1e-4, f"{root['power']:.4f}")
at(20.0)
C.check('keys play back: black after the breaker (u 20)', abs(root['power']) < 1e-4 and root['phone_fill'] > 0.1,
        f"power {root['power']:.4f}, phones {root['phone_fill']:.3f}")
ln = F.text_lines[0]
u_mid = B['lines'][0][1] + 0.5 * (B['lines'][0][2] - B['lines'][0][1])
at(u_mid)
C.check('the first line is half typed mid-way', abs(ln['obj']['head'] - 0.5 * ln['n_chars']) < 0.06 * ln['n_chars'],
        f"head {ln['obj']['head']:.2f} of {ln['n_chars']}")
at(31.5)
C.check('the lights come back golden (u 31.5)', root['golden'] > 0.95 and F.pend_spots[0][0].data.energy > 100,
        f"golden {root['golden']:.3f}, pendant {F.pend_spots[0][0].data.energy:.0f} W")
at(1.0)
vis_b = not F.bridge.objects[0].hide_render and F.room_objects[0].hide_render
# (the haze is made after the section's keys, by post.apply; post.animate keys its density to 0 on the bridge, the
# JS depth_fog's opacity 0 there)
shown_on_bridge = [o.name for o in F.room_objects if not o.hide_render and o.name != 'funeral:haze']
at(5.0)
vis_r = F.bridge.objects[0].hide_render and not F.room_objects[0].hide_render
hidden_in_room = [o.name for o in F.room_objects if o.hide_render]
C.check('the bridge shows for bars 0-1, the room after', vis_b and vis_r)
# every part of the room follows the keyed steps, the raven too (its clip player clears the active action of every
# object under it: played after the keys, it dropped the raven's steps and left it hidden for the whole film)
raven = F.parts.get('raven')
C.check('every room part (the raven too) is keyed: hidden on the bridge, shown in the room',
        not shown_on_bridge and not hidden_in_room and (raven is None or not raven.hide_render),
        f'{len(F.room_objects)} room objects; shown on the bridge {shown_on_bridge[:4]}, hidden in the room '
        f'{hidden_in_room[:4]}')
# the crowd's arms: hanging in the vigil, overhead at ERUPT (the evaluated Geometry Nodes)
crowd = F.parts.get('crowd')
if crowd is not None:
    def top(u):
        at(u)
        dg = bpy.context.evaluated_depsgraph_get()
        me = crowd.evaluated_get(dg).to_mesh()
        import numpy as np
        co = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get('co', co)
        n = len(me.vertices)
        crowd.evaluated_get(dg).to_mesh_clear()
        return float(co.reshape(-1, 3)[:, 2].max()), n
    z5, n5 = top(5.0)
    z28, n28 = top(28.0)
    C.check('crowd realised (Geometry Nodes)', n5 > 100000, f'{n5} vertices')
    C.check('arms raised overhead at ERUPT', z28 > z5 + 0.25, f'top {z5:.2f} m -> {z28:.2f} m')

if TL is not None:
    L = F.beats['lines']
    C.check("the eulogy re-times to Opus 3's captions (the DAISY timeline)", F._lines_synced and L != FU.BEATS['lines']
            and all(a[0] < a[1] < a[2] for a in L) and L[0][1] < L[1][1] < L[2][1] < FU.BEATS['erupt'],
            ' '.join(f'[{a[0]:.2f} {a[1]:.2f} {a[2]:.2f}]' for a in L))
else:
    print(f'[funeral] no film timeline at {TLP} (or --no-tl): the eulogy keeps the default BEATS')

# the cameras frame her: her mark inside the frame of the shots that aim at her
mk = F.mark_at(5.0)['pos']
s1 = F.camera(2.5 * FU.BAR)
d = (s1['target'] - s1['pos']).normalized()
to_her = (Vector(mk) + Vector((0, 0, 1.3)) - s1['pos']).normalized()
C.check('shot 1 (bars 2-3) looks at her face', math.degrees(d.angle(to_her)) < 8.0, f'{math.degrees(d.angle(to_her)):.1f} deg')

# the lace is a cut-out: its mask (getImageData's R) is 0 or 1, the strokes covering part of the tile, and read as a
# plain channel (an opaque image: no premultiply round trip lifting R to 1 over the veil)
import numpy as np                                          # noqa: E402
lace = bpy.data.images.get('funeral:lace')
if lace is not None:
    px = np.empty(lace.size[0] * lace.size[1] * 4, np.float32)
    lace.pixels.foreach_get(px)
    r = px[0::4]
    cover = float((r > 0.5).mean())
    C.check('the lace mask: a 0/1 cut-out covering part of the tile, opaque', lace.alpha_mode == 'NONE'
            and float(((r > 0.02) & (r < 0.98)).mean()) < 0.01 and 0.05 < cover < 0.6, f'{cover:.1%} lace')
# three's FrontSide: surface() / simple() cull the faces turned away from the camera, the DoubleSide ones draw both
sides = {m.name: m.use_backface_culling for m in bpy.data.materials if m.name in ('funeral:enamel', 'funeral:lace',
                                                                                    'funeral:petal', 'funeral:brick')}
C.check('material sides as the JS (enamel, brick FrontSide; lace, petal DoubleSide)', sides.get('funeral:enamel') is True
        and sides.get('funeral:brick') is True and sides.get('funeral:lace') is False and sides.get('funeral:petal') is False,
        str(sides))

# a close look at the raven on Opus 4's shoulder (no film shot cuts to it): it must show, and idle, in the saved file
from eidoblend.look import camera as LC                     # noqa: E402
rp = F.anchors['raven_perch']
raven_cam = LC.make_camera('funeral:raven_cam', fov=30)
raven_cam.matrix_world = LC.look_matrix(F.group.matrix_world @ FU.V(rp[0] + 1.25, rp[1] + 0.3, rp[2] + 1.55),
                                        F.group.matrix_world @ FU.V(rp[0], rp[1] + 0.05, rp[2]))

blend = os.path.join(OUT, 'funeral.blend')
bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)
C.check('saved .blend', os.path.isfile(blend), f'{os.path.getsize(blend) / 1e6:.1f} MB')

# ------------------------------------------------------------------------------------------------- the stills
# one per shot (its middle) and the story's beats; listed in out/funeral/stills.json for render_saved.py, which renders
# them from the saved .blend (--no-render here, then render_saved.py funeral in the GPU slot)
stills = [(f'shot{i:02d}_bar{s[0]:02d}', 0.5 * (s[0] + s[1]) * FU.BAR) for i, s in enumerate(FU.SHOTS)]
stills += [('veil_in', B['bridge_end'] - 0.25), ('breaker', B['breaker'] + 0.3), ('line2', B['lines'][1][2] - 0.4),
           ('erupt', B['erupt'] + 0.35)]
stills = [(n, u, C.frame_of(u, U0, F0, FPS)) for n, u in stills]
stills.append(('raven', 5.5, C.frame_of(5.5, U0, F0, FPS), raven_cam.name))     # through its own camera
C.write_stills(OUT, stills)
if 'no-render' not in A['flags']:
    # the film's shots first (their marker cameras), then the stills through a camera of their own, markers gone
    for s in sorted(C.select_stills(stills, A.get('only')), key=lambda s: len(s) > 3):
        name, u, f = s[:3]
        path = os.path.join(OUT, f'funeral_{name}.png')
        if len(s) > 3:
            for mk in list(sc.timeline_markers):
                sc.timeline_markers.remove(mk)
            sc.camera = bpy.data.objects[s[3]]
        ok, dt = C.render_still(sc, f, path)
        st = C.image_stats(path) if ok else {'mean': 0, 'max': 0, 'magenta': 1}
        C.check(f'still {name} (u {u:.2f}, frame {f})', ok and st['magenta'] < 0.001 and st['max'] > 0.05,
                f"mean {st['mean']:.3f} max {st['max']:.2f} ({dt:.1f} s)")
sys.exit(1 if C.summary('test_funeral') else 0)
