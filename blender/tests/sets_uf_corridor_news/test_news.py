"""The evening news (UNKNOWN FORCE verse 5) in Blender: build it, check the parts, the pickets (the JS's own rng, so
the same 79 people with the same roles), the keyed update and the Geometry Nodes poses numerically, and (--render)
render the film's five cameras plus the states (the tag half sprayed, floods off, the chyron in its overlay).

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sets_uf_corridor_news/test_news.py
    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/sets_uf_corridor_news/test_news.py --render [fence,crowd,...] [--states] [--samples 16]
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _fixture as F  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.sets.unknown_force import news as NEWS, cn_lib as CL  # noqa: E402

A = F.args()
RENDER = '--render' in A
STATES = '--states' in A
cams_arg = next((a for a in A if not a.startswith('--') and (',' in a or a in NEWS.CAMS)), None)
CAMS = cams_arg.split(',') if cams_arg else list(NEWS.CAMS)
SAMPLES = int(A[A.index('--samples') + 1]) if '--samples' in A else 16
W, H = (int(v) for v in (A[A.index('--size') + 1] if '--size' in A else '960x540').split('x'))
OUT = F.OUT / 'news'
OUT.mkdir(parents=True, exist_ok=True)

sc = F.clean_scene()
F.render_settings(W, H, SAMPLES)
sc.frame_start, sc.frame_end = 1, 72
clock = F.timer()
N = NEWS.build(sc)
print(f'[news] built in {clock():.1f}s', flush=True)
N.apply_look(sc)

# ------------------------------------------------------------------------------------------------- structure
objs = [o for o in N.collection.all_objects]
meshes = [o for o in objs if o.type == 'MESH']
F.check('built: meshes (57 in the WebGPU edition, which instanced more)', 40 <= len(meshes) <= 90, f'{len(meshes)} meshes')
for k in ('ground', 'fence', 'poles', 'beams', 'monolith', 'yard', 'street', 'crowd', 'van', 'sky', 'steam', 'graffiti',
          'chyron', 'lights', 'uniforms', 'materials'):
    F.check(f'parts.{k}', k in N.parts and N.parts[k] is not None)
F.check('cams: fence crowd wall wide pov', set(N.cams) == {'fence', 'crowd', 'wall', 'wide', 'pov'})
F.check('focal: the flood behind her at three (-3.9, 7.4, -6.5) = Blender (-3.9, 6.5, 7.4)',
        tuple(N.focal_three) == (-3.9, 7.4, -6.5) and tuple(N.focal) == (-3.9, 6.5, 7.4))
F.check('cams: Blender axes (the crowd camera at three (-4.6, 2.75, 17.6) -> (-4.6, -17.6, 2.75)), the WebGPU numbers '
        'in cams_three', N.cams['crowd']['pos'] == [-4.6, -17.6, 2.75] and N.cams_three['crowd']['pos'] == [-4.6, 2.75, 17.6])
F.check('look: argue, fog FogExp2(0x0b1018, 0.011)', N.look['fog'] == {'color': 0x0b1018, 'density': 0.011})
people = N.parts['people']
roles = {r: sum(1 for p in people if p['role'] == r) for r in ('sign', 'phone', 'torch', 'fist', 'down', 'crew')}
F.check('pickets: 79 people as CORRIDOR_NEWS.md counts them (29 signs, 12 phones, 5 torches, 7 fists, 1 crew)',
        len(people) == 79 and roles['sign'] == 29 and roles['phone'] == 12 and roles['torch'] == 5 and roles['fist'] == 7
        and roles['crew'] == 1, str(roles))
F.check('pickets: the fence camera lane in front of her is clear',
        not any(abs(p['x'] - 0.3) < 2.1 and p['z'] < NEWS.FZ + 3.2 for p in people if p['role'] != 'crew'))
fl = N.parts['lights']['floods']
F.check('floods: 4 real lamps at 850 cd', len(fl) == 4 and all(abs(l.data.energy - 850 * 4 * math.pi / 683) < 1e-3 for l in fl))
rec = N.parts['flood_receivers']
F.check('floods leave the painted-flood surfaces out (light linking)',
        all(l.light_linking.receiver_collection == rec for l in fl)
        and all(co.light_linking.link_state == 'EXCLUDE' for co in rec.collection_objects)
        and len(rec.objects) >= 5, f'{len(rec.objects)} excluded')

# ---------------------------------------------------------------------- the keyed update, the GN poses
N.animate(lambda t: {'spray': min(1.0, t / 2.5), 'chant': 1.0, 'pulse': 0.0, 'floods': 0.0 if t > 2.6 else 1.0},
          frames=(1, 72), scene=sc)
sc.frame_set(31)                                   # t = 1.25 s: half sprayed
F.check('spray: keyed 0 -> 1 over 2.5 s (0.5 at 1.25 s)', abs(N.group['spray'] - 0.5) < 1e-6, f"{N.group['spray']:.3f}")
sc.frame_set(1)
F.check('blink: aviation lights on for 0.8 s of 1.6', N.group['blink'] == 1.0)
sc.frame_set(21)                                   # t = 0.833: off
F.check('blink: off at 0.83 s', abs(N.group['blink'] - 0.05) < 1e-6)
sc.frame_set(72)
F.check('floods off: lamps at 0, beams hidden', all(l.data.energy == 0 for l in fl)
        and all(b.hide_render for b in N.parts['beams'].children))
dg = bpy.context.evaluated_depsgraph_get()


def eval_positions(ob):
    e = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = e.to_mesh()
    P = np.zeros(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', P)
    e.to_mesh_clear()
    return P.reshape(-1, 3)


signs = N.parts.get('signs')
sc.frame_set(1)
s1 = eval_positions(signs)
sc.frame_set(13)                                   # t = 0.5 s: the chant's beat has moved the boards
s2 = eval_positions(signs)
mv = np.linalg.norm(s2 - s1, axis=1)
F.check('signs: pumped by the chant (GN, keyed t)', 0.01 < mv.max() < 0.6, f'max move {mv.max():.3f} m')


def attr(ob, name):
    a = ob.data.attributes[name]
    n = len(a.data)
    if a.data_type == 'FLOAT':
        v = np.empty(n, np.float32)
        a.data.foreach_get('value', v)
        return v.astype(np.float64)
    v = np.empty(n * 3, np.float32)
    a.data.foreach_get('vector', v)
    return v.reshape(-1, 3).astype(np.float64)


def js_pose(ob, t, chant=1.0, pulse=0.0, figures=False):
    """news.js's vertex stage on the CPU (its positionNode and the instance matrix), from the rest data the Geometry
    Nodes read: the same numbers in three's axes, returned in Blender's."""
    lp = attr(ob, 'lp')
    P0 = np.stack([lp[:, 0], lp[:, 2], -lp[:, 1]], 1)                     # three axes
    th, seed, role, sc_ = attr(ob, 'theta'), attr(ob, 'seed'), attr(ob, 'role'), attr(ob, 'pscale')
    is_sign = ((role >= 0.5) & (role <= 1.5)).astype(float)
    is_fist = ((role >= 3.5) & (role <= 4.5)).astype(float)
    beat = np.sin(t * math.pi * 2 * 0.95 + seed * 6.0)
    theta = th + (is_sign + is_fist) * (beat * 0.09 + pulse * 0.12) * chant + np.sin(t * 1.3 + seed * 40) * 0.04

    def rot_x(v, ang):
        c, s = np.cos(ang), np.sin(ang)
        return np.stack([v[:, 0], v[:, 1] * c - v[:, 2] * s, v[:, 1] * s + v[:, 2] * c], 1)
    SHv, NKv = np.array(N.parts['rig']['shoulder']), np.array(N.parts['rig']['neck'])
    arm = SHv + rot_x(P0 - SHv, -theta)
    if figures:
        wc = attr(ob, 'wc')
        P1 = P0 + (arm - P0) * wc[:, 0:1]
        nod = np.sin(t * math.pi * 2 * 0.95 + seed * 6.0) * 0.06 * chant
        head = NKv + rot_x(P1 - NKv, nod)
        Pf = P1 + (head - P1) * (wc[:, 2] * (1 - wc[:, 0]))[:, None]
    else:
        Pf = arm
    yaw = attr(ob, 'yaw')
    c, s = np.cos(yaw), np.sin(yaw)
    x = (c * Pf[:, 0] + s * Pf[:, 2]) * sc_ + attr(ob, 'px')
    z = (-s * Pf[:, 0] + c * Pf[:, 2]) * sc_ + attr(ob, 'pz')
    y = Pf[:, 1] * sc_
    return np.stack([x, -z, y], 1)


sc.frame_set(13)
d = np.abs(eval_positions(signs) - js_pose(signs, 0.5)).max()
F.check("signs: the Geometry Nodes pose = news.js's positionNode at t = 0.5 s (arm angle, pump, sway, instance)",
        d < 1e-4, f'max |d| {d:.2e} m')
fig0 = next(o for o in N.parts['crowd'].children if o.name.startswith('news_pickets_'))
d = np.abs(eval_positions(fig0) - js_pose(fig0, 0.5, figures=True)).max()
F.check("pickets: the Geometry Nodes pose = news.js's positionNode (arms by vertex colour R, the head's nod by B)",
        d < 1e-4, f'max |d| {d:.2e} m')
F.check('signs: held overhead (the boards reach 2.6-3.6 m)', 2.6 < s1[:, 2].max() < 3.6, f'top {s1[:, 2].max():.2f} m')
steam = N.parts['steam']
sc.frame_set(1)
p1 = eval_positions(steam)
sc.frame_set(25)
p2 = eval_positions(steam)
F.check('steam: 110 puffs as camera-facing quads (440 vertices)', len(p1) == 440, f'{len(p1)} verts')
F.check('steam: the puffs rise with t', np.median(p2[:, 2] - p1[:, 2]) > 0.05 or np.mean(np.abs(p2 - p1)) > 0.05,
        f'mean move {np.mean(np.abs(p2 - p1)):.3f}')
hl = N.parts.get('handlights')
ph = eval_positions(hl)
F.check('hand lights: 18 quads at the raised hands (12 phones, 5 torches, the crew)', len(ph) == 72, f'{len(ph)} verts')
F.check('hand lights: held 1.0-2.4 m up', 0.9 < np.median(ph[:, 2]) < 2.5, f'median z {np.median(ph[:, 2]):.2f}')
figs = [o for o in N.parts['crowd'].children if o.name.startswith('news_pickets_')]
fp = np.concatenate([eval_positions(o) for o in figs])
F.check('pickets: figures stand on the ground (feet at 0, heads ~1.6-1.9 m)', fp[:, 2].min() > -0.05 and 1.5 < fp[:, 2].max() < 2.6,
        f'z {fp[:, 2].min():.2f}..{fp[:, 2].max():.2f}')

# ------------------------------------------------------------------------------------- the film's use of the set
s0, s1 = NEWS.film_state(200.0), NEWS.film_state(212.85)
F.check("film_state: the tag unpainted before 211.5 s, half sprayed at 212.85 s (smoothstep to 214.2), the chant at full",
        s0['spray'] == 0.0 and abs(s1['spray'] - 0.5) < 1e-9 and s0['chant'] == 1.0
        and abs(s0['pulse'] - (0.5 + 0.5 * math.sin(600.0))) < 1e-12)
F.check('film_state: the chyron with the first cue only (201.2-204.8 s)', NEWS.film_state(202.0)['chyron']
        and not NEWS.film_state(205.0)['chyron'])
F.check('film_singer_mark: her mark, then the fence from 215.4 s (z 3.2 - 0.372)', NEWS.film_singer_mark(215.0) == (0, 0, 0)
        and abs(NEWS.film_singer_mark(216.0)[2] - 2.828) < 1e-9)
c = NEWS.film_cut(213.0)
F.check("film_cut: 213 s is the film's wall shot (push 0.6, reading), her hidden", c['cam'] == 'wall'
        and c['move'] == {'push': 0.6, 'read': True} and not c['singer'])
sc.frame_start, sc.frame_end = 1, 24 * 6
cams = N.make_cameras(frames=(1, 24 * 6), t0=200.0)          # 200-206 s: wide, crowd, pov
F.check("make_cameras: the film's shots 200-206 s are wide, crowd, pov", [n for (_f, n) in sorted(cams)]
        == ['wide', 'crowd', 'pov'], str(sorted(cams)))

# --------------------------------------------------------------------------------------------------- renders
if RENDER:
    sc.frame_set(1)
    for name in CAMS:
        N.camera(name, sc)
        N.set_u('pix', CL.pix_of(sc))
        F.render_still(OUT / f'news_{name}_f1.png', sc)
    if STATES:
        sc.frame_set(31)
        N.camera('wall', sc)
        F.render_still(OUT / 'news_wall_spray_half_f31.png', sc)
        sc.frame_set(72)
        N.camera('fence', sc)
        F.render_still(OUT / 'news_fence_floods_off_f72.png', sc)
        # the chyron in a display-space overlay (media.overlay), composited over the crowd shot
        from eidoblend.media import overlay
        sc.frame_set(1)
        cam = N.camera('crowd', sc)
        ov = overlay.make_overlay_layer(sc, camera=cam)
        N.parts['chyron'].place(ov, fov=N.cams['crowd']['fov'], aspect=W / H)
        ov.scene.frame_set(1)
        ov.scene.render.filepath = str(OUT / 'news_chyron_overlay_f1.png')
        ov.scene.render.image_settings.color_mode = 'RGBA'
        bpy.ops.render.render(write_still=True, scene=ov.scene.name)
        F.check('chyron overlay rendered', (OUT / 'news_chyron_overlay_f1.png').is_file())
        from PIL import Image
        base = Image.open(OUT / 'news_crowd_f1.png').convert('RGBA')
        top = Image.open(OUT / 'news_chyron_overlay_f1.png').convert('RGBA')
        Image.alpha_composite(base, top).convert('RGB').save(OUT / 'news_crowd_with_chyron_f1.png')
F.summary()
