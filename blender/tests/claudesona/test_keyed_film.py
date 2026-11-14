"""A short keyed film with every claudesona system in it, saved, reopened and rendered again: the contract that a saved
.blend plays and renders any frame on its own, for outfits switched on frames (wardrobe.wear(key, frame)), the TuTa's
pins, face paint and sun disc keyed where it goes on, a scheduled ejection baked (tuta.bake), the springs baked last
(springs.bake_springs) and the body turning (the face's catchlights and paint must ride the head).

    frames 1-30 lab_coat_1961, 31-60 cyclist_1892 (folds + boater), 61-100 tuta (paint, disc, five badges; mod_gold
    ejected at frame 80); the armature turns 0 -> 30 -> -20 deg over the film; idle plays throughout

Checks:
    each block wears its outfit: its layers, the boater only on the cyclist, the TuTa's layers only on the TuTa
    the badges (pinned, and the scheduled mod_gold) are hidden on every frame before the TuTa goes on, as the JS's
        update(t) hides them off the TuTa (onTuta() at that frame), and shown on it
    the ejected badge's flying copy is out at frame 84
    the bake reads the neon keyed at each frame (keyed before it, after the clip: the case the session's depsgraph
        missed until the armature was tagged): a snap at frame 92 flashes at that frame's neon
    the boater stays where its wear seated it, in the head's frame, through the cyclist's whole block
    the cyclist's folded petals are folded on its block and back at rest on the TuTa's
    reopened: frames 20, 45, 75 and 84 render as before saving (mean difference under 0.002)
Stills: out/keyed_film_sheet.png (the four frames; then the face at two head turns on the TuTa: the catchlights and
the paint stay on the face).

    bash run_blender.sh blender/tests/claudesona/test_keyed_film.py [--no-render]
    # a GPU job; on a shared machine queue it with EIDO_GPU_WRAP (blender/tests/_where.py)
"""

import json
import math
import os
import sys
import traceback

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stage as S  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.characters import load_vrm, play_vrma_default  # noqa: E402
from eidoblend.characters.claudesona import tuta as TU  # noqa: E402
from eidoblend.characters.claudesona.wardrobe import WARDROBE, make_wardrobe  # noqa: E402
from eidoblend.characters.springs import bake_springs  # noqa: E402

ARGS = S.argv()
RENDER = '--no-render' not in ARGS
FPS, F1, SCALE = 30, 100, 0.87
BLOCKS = [(1, 'lab_coat_1961'), (31, 'cyclist_1892'), (61, 'tuta')]
EJECT_F = 80
NEON_F, SNAP_F = 90, 92                  # neon keyed down to 0.5 at frame 90; mod_spray snaps (re-pinned) at 92
FRAMES = (20, 45, 75, 84)
OUT = os.path.join(S.OUT, 'keyed_film')
os.makedirs(OUT, exist_ok=True)
BLEND = os.path.join(OUT, 'keyed_film.blend')


def build():
    sc = S.clean_scene(FPS)
    sc.frame_start, sc.frame_end = 1, F1
    h = load_vrm('claude_suit_wardrobe', name='film')
    h.arm.scale = (SCALE,) * 3
    play_vrma_default(h, 'idle', t=0.0, loop=True, until=F1 / FPS)
    arm = h.arm
    arm.rotation_mode = 'XYZ'
    for f, deg in ((1, 0.0), (45, 30.0), (100, -20.0)):
        arm.rotation_euler = (0.0, 0.0, math.radians(deg))
        arm.keyframe_insert('rotation_euler', index=2, frame=f)
    wd = make_wardrobe(h)
    for f, key in BLOCKS:
        wd.wear(key, frame=f)
    wd.face_paint(False, frame=1)
    wd.face_paint(True, frame=61)
    wd.sun_disc(False, frame=1)
    wd.sun_disc(True, frame=61)
    for k in TU.BADGES:
        wd.pin(k, frame=61)
    wd.neon(1.0, frame=1)
    wd.neon(0.5, frame=NEON_F)               # keyed before the bake: the bake reads each frame's neon
    wd.schedule([{'at': (EJECT_F - 1) / FPS, 'unpin': 'mod_gold', 'eject': True},
                 {'at': (SNAP_F - 1) / FPS, 'pin': 'mod_spray'}])
    rep_b = wd.bake(1, F1)
    rep_s = bake_springs(h, 1, F1)
    return sc, h, wd, rep_b, rep_s


def check(sc, h, wd, C, R):
    bad = []
    for f in range(1, F1 + 1):
        sc.frame_set(f)
        key = [k for f0, k in BLOCKS if f0 <= f][-1]
        p = WARDROBE[key]
        shown = {n for n, o in wd.layers.items() if not o.hide_render}
        if shown != set(p.get('show', [])) & set(wd.layers):
            bad.append((f, 'layers', sorted(shown ^ (set(p.get('show', [])) & set(wd.layers)))))
        on_tuta = key == 'tuta'
        for n in ('tuta', 'uf_boots', 'uf_straps'):
            if n in wd.uf and wd.uf[n].hide_render == on_tuta:
                bad.append((f, n))
        for k in TU.BADGES:
            o = wd.uf.get(k)
            fl = wd._flyers.get(k)
            vis = (o is not None and not o.hide_render) or (fl is not None and not fl.hide_render)
            want = on_tuta and not (k == 'mod_gold' and f >= EJECT_F + int(round((TU.POP + TU.FLY) * FPS)) + 1)
            if vis != want:
                bad.append((f, k, vis))
    R['frame_mismatches'] = bad[:40]
    C.check('every frame wears its block\'s outfit, and the badges show only on the TuTa (none floating on the lab coat '
            'or the cyclist)', not bad, f'{len(bad)} mismatches' + ('' if not bad else f': {bad[:6]}'))
    sc.frame_set(EJECT_F + 4)
    fl = wd._flyers.get('mod_gold')
    C.check('the ejected badge\'s flying copy is out at frame 84, the badge itself hidden',
            fl is not None and not fl.hide_render and wd.uf['mod_gold'].hide_render, '')
    sp = wd._sparks.get('mod_gold')
    cards = [sp['flare']] + sp['embers'] if sp else []
    shown = {}
    for f in (1, 40, EJECT_F - 1, EJECT_F, EJECT_F + 3, EJECT_F + 12):
        sc.frame_set(f)
        shown[f] = sum(1 for o in cards if not o.hide_render)
    R['spark_cards_shown'] = shown
    C.check('the pop\'s flare and embers show only for the 0.22 s after the pop (none before it: no flare beside the '
            'badge from the film\'s start)', bool(cards) and shown[1] == shown[40] == shown[EJECT_F - 1] == 0
            and shown[EJECT_F] == shown[EJECT_F + 3] == 9 and shown[EJECT_F + 12] == 0, f'{shown}')
    g = {}
    for f in (70, SNAP_F):
        sc.frame_set(f)
        g[f] = round(float(h.arm['cs_tuta.glow.mod_spray']), 4)
    R['mod_spray_glow'] = g
    C.check('the bake reads the neon keyed at each frame: mod_spray glows 1.0 at frame 70 (neon 1), and its snap at '
            'frame 92 flashes at neon 0.5 (0.5 x 4 = 2.0)', abs(g[70] - 1.0) < 1e-3 and abs(g[SNAP_F] - 2.0) < 1e-3, f'{g}')
    hat = wd.layers['boater']
    hb = h.humanoid['head']
    rel = {}
    for f in (31, 38, 45, 52, 60):
        sc.frame_set(f)
        rel[f] = (h.arm.matrix_world @ h.arm.pose.bones[hb].matrix).inverted() @ hat.matrix_world
    d_mm = max((rel[f].translation - rel[31].translation).length for f in rel) * 1000
    d_deg = max(math.degrees(rel[f].to_quaternion().rotation_difference(rel[31].to_quaternion()).angle) for f in rel)
    d_sc = max(abs(s - rel[31].to_scale()[0]) for f in rel for s in rel[f].to_scale())
    R['boater_drift'] = {'mm': round(d_mm, 4), 'deg': round(d_deg, 4), 'scale': round(d_sc, 5)}
    C.check('the boater stays seated on the head through the cyclist\'s block (its keys CONSTANT on every axis, no '
            'easing toward the next outfit\'s hat)', d_mm < 0.1 and d_deg < 0.01 and d_sc < 1e-4, f"{R['boater_drift']}")
    folds = {}
    for f in (45, 75):
        sc.frame_set(f)
        folds[f] = {}
        for key in ('12_L', '11_R'):
            root = wd.petal_root(key)
            q = h.arm.pose.bones[root].rotation_quaternion
            folds[f][key] = round(math.degrees(q.angle), 1)
    R['fold_angles_deg'] = folds
    C.check('the cyclist\'s petals folded on its block (> 90 deg) and back near rest on the TuTa\'s (< 45 deg: springs only)',
            all(v > 90 for v in folds[45].values()) and all(v < 45 for v in folds[75].values()), f'{folds}')


def stills(sc, h, tag):
    hb = h.arm.matrix_world @ h.arm.data.bones[h.humanoid['head']].head_local
    cam = bpy.data.objects.get('film_cam') or S.camera('film_cam', lens=40)
    c = Vector((hb.x, hb.y, hb.z * 0.55))
    S.aim(cam, (c.x + 3.2 * math.sin(math.radians(15)), c.y - 3.2 * math.cos(math.radians(15)), c.z + 0.15), c)
    paths = []
    for f in FRAMES:
        p = os.path.join(OUT, f'keyed_film_{tag}_f{f:03d}.png')
        S.still(sc, cam, f, p)
        paths.append(p)
    return paths


def face_stills(sc, h):
    hb = h.arm.matrix_world @ h.arm.data.bones[h.humanoid['head']].head_local
    cam = S.camera('film_face', lens=60)
    ft = Vector((hb.x, hb.y, hb.z + 0.08))
    S.aim(cam, (ft.x, ft.y - 0.85, ft.z), ft)
    paths = []
    for f in (70, 98):                     # the body turned about +10 deg, then about -18 deg
        p = os.path.join(OUT, f'keyed_film_face_f{f:03d}.png')
        S.still(sc, cam, f, p)
        paths.append(p)
    return paths


def mad(a, b):
    def load(p):
        im = bpy.data.images.load(p, check_existing=False)
        w, hh = im.size
        x = np.array(im.pixels[:], dtype=np.float32).reshape(hh, w, 4)[..., :3]
        bpy.data.images.remove(im)
        return x
    return float(np.abs(load(a) - load(b)).mean())


def main():
    R, C = {}, S.Checks('keyed_film')
    try:
        sc, h, wd, rep_b, rep_s = build()
        R['bake'], R['springs'] = rep_b, {k: rep_s[k] for k in ('springs', 'joints', 'keys', 'nan', 'override_frames')}
        check(sc, h, wd, C, R)
        if RENDER:
            S.probe_render(sc, res=(480, 640), samples=16)
            S.turntable_studio(sc, light=0.7)
            before = stills(sc, h, 'live')
            faces = face_stills(sc, h)
            bpy.ops.wm.save_as_mainfile(filepath=BLEND, copy=True)
            bpy.ops.wm.open_mainfile(filepath=BLEND)
            sc = bpy.context.scene
            cam = bpy.data.objects['film_cam']
            after = []
            for f, pb in zip(FRAMES, before):
                p = pb.replace('_live_', '_reopened_')
                S.still(sc, cam, f, p)
                after.append(p)
            d = {f: round(mad(a, b), 5) for f, a, b in zip(FRAMES, before, after)}
            R['reopened_mad'] = d
            C.check('the saved .blend, reopened, renders frames 20, 45, 75 and 84 as before (keys, drivers, NLA only)',
                    max(d.values()) < 0.002, f'{d}')
            R['sheet'] = S.sheet(before + after[:2] + faces, os.path.join(S.OUT, 'keyed_film_sheet.png'), cols=4)
            os.remove(BLEND)
            for x in os.listdir(OUT):
                if x.endswith('.blend1'):
                    os.remove(os.path.join(OUT, x))
    except Exception:
        traceback.print_exc()
        R['error'] = traceback.format_exc()
        C.check('ran without an exception', False)
    R['checks'] = C.rows
    R['all_pass'] = C.all_pass and 'error' not in R
    with open(os.path.join(OUT, 'keyed_film.json'), 'w', encoding='utf-8') as f:
        json.dump(R, f, indent=1, default=str)
    print('[keyed_film] ALL PASS' if R['all_pass'] else '[keyed_film] SOME FAILED', flush=True)


main()
