"""The TuTa (claudesona/tuta.py) on claude_suit_wardrobe.vrm at the films' 0.87, measured frame by frame against
claudesona_wardrobe.js ITSELF (tuta_parity.mjs: the module run in deno on the same VRM, CPU, no renderer), then
probed in renders.

Parity (the character at rest, 30 fps, frames 1-100, the same calls on both sides):
    now:       neon(0.8), facePaint(1), sunDisc(true), eyeLights(0.6, true), pin mod_red, pin + unpin mod_chrome
    schedule:  mod_gold snaps on at 0.10 s and is EJECTED at 1.00 s; mod_warning snaps on at 0.30 s and unsnaps at
               0.80 s (its ghost fades in); mod_spray snaps on at 0.50 s and is ejected at 1.40 s to LINGER on the floor
Checks:
    every TuTa layer is found; wear('tuta') shows the tuta, the boots and the straps and hides digi's shoes, as the JS
    the surfaces are built (tuta, boot_upper, boot_sole, webbing, buckle, the face paint, the catchlights, the disc)
    every badge on every frame: visible exactly when the JS's is; where visible, its world centroid within 1 mm of the
        JS's and its spread (the vertex covariance: orientation and size) within 2 % (attached, snapping, unsnapping,
        flying, lingering); its glow and its ghost equal the JS's
    the pop's sparks: shown on the same frames, the flare and the eight embers where the JS puts them (1 mm), sized alike
    pinned / ghosts / badgeWorld / the uniforms (neon, paint, eyes, eyeNeon) equal the JS's after the run
    the keys play back cold: a frame re-evaluated after jumping elsewhere gives the same badge state
    the cyclist (the garment wardrobe under the TuTa, at rest): the auto folds, the brim lift, each folded petal's
        direction and the boater's centroid equal the JS's
Stills (the TuTa at play, idle clip, night-studio light): out/tuta_sheet.png (front and back, three-quarter, the five
badges pinned, face paint, the disc), out/tuta_details_sheet.png (the chest: zip, piping, stitches, badges; the back:
yoke, grommet, a ghost; the legs: knee panels, cargo pocket, lightning inlay, boots; the face: paint + catchlights),
out/tuta_eject_sheet.png (mod_gold popped off and tumbling, its sparks), out/tuta_neon_sheet.png (neon 0, 0.4, 1).

    bash run_blender.sh blender/tests/claudesona/test_tuta.py [--no-render]
    # a GPU job; on a shared machine queue it with EIDO_GPU_WRAP (blender/tests/_where.py)
"""

import json
import math
import os
import subprocess
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
from eidoblend.characters.claudesona.wardrobe import make_wardrobe  # noqa: E402

ARGS = S.argv()
RENDER = '--no-render' not in ARGS
FPS, F0, F1 = 30, 1, 100
SCALE = 0.87
NOW = [['neon', 0.8], ['facePaint', 1], ['sunDisc', True], ['eyeLights', 0.6, True], ['pin', 'mod_red'],
       ['pin', 'mod_chrome'], ['unpin', 'mod_chrome']]
SCHEDULE = [{'at': 0.10, 'pin': 'mod_gold'}, {'at': 1.00, 'unpin': 'mod_gold', 'eject': True},
            {'at': 0.30, 'pin': 'mod_warning'}, {'at': 0.80, 'unpin': 'mod_warning'},
            {'at': 0.50, 'pin': 'mod_spray'}, {'at': 1.40, 'unpin': 'mod_spray', 'eject': True, 'linger': True}]
PETALS = ['12_L', '11_R', '1_L', '10_R', '2_L']
# a hand-placed hat ({offset, scale}: model metres, +z the face's side), worn after the cyclist on both sides
HAT_OFFSET = {'cs_hat_offset': {'show': ['jersey', 'shirt', 'knickers', 'socks', 'boater'],
                                'hat': {'offset': [0.0, 0.06, 0.02], 'scale': 1.1}}}
PY = {'facePaint': 'face_paint', 'sunDisc': 'sun_disc', 'eyeLights': 'eye_lights', 'clearGhost': 'clear_ghost'}
R3 = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]])        # three -> Blender


def reference():
    nm = os.path.join(S.MAIN, 'node_modules').replace('\\', '/')
    u = 'file:///' + nm
    imap = {'imports': {'three': f'{u}/three/build/three.webgpu.js', 'three/webgpu': f'{u}/three/build/three.webgpu.js',
                        'three/tsl': f'{u}/three/build/three.tsl.js', 'three/addons/': f'{u}/three/examples/jsm/',
                        '@pixiv/three-vrm': f'{u}/@pixiv/three-vrm/lib/three-vrm.module.js',
                        '@pixiv/three-vrm-materials-mtoon': f'{u}/@pixiv/three-vrm-materials-mtoon/lib/three-vrm-materials-mtoon.module.js',
                        '@pixiv/three-vrm-materials-mtoon/nodes': f'{u}/@pixiv/three-vrm-materials-mtoon/lib/nodes/index.module.js'}}
    mp = os.path.join(S.OUT, 'tuta_import_map.json')
    with open(mp, 'w', encoding='utf-8') as f:
        json.dump(imap, f)
    tex = None
    for root in (S.REPO, S.MAIN):
        d = os.path.join(root, 'eidoverse', 'assets', 'cache', 'textures')
        if os.path.isdir(os.path.join(d, 'Fabric039_1k')):
            tex = d.replace('\\', '/')
    job = {'module': 'file:///' + os.path.join(S.REPO, 'eidoverse', 'claudesona_wardrobe.js').replace('\\', '/'),
           'vrm': os.path.join(S.VRMS, 'claude_suit_wardrobe.vrm').replace('\\', '/'), 'scale': SCALE, 'fps': FPS,
           'frames': [F0, F1], 'texroot': tex, 'now': NOW, 'schedule': SCHEDULE, 'wear_after': 'cyclist_1892',
           'petal_keys': PETALS, 'presets': HAT_OFFSET, 'wears': list(HAT_OFFSET)}
    jp = os.path.join(S.OUT, 'tuta_job.json')
    with open(jp, 'w', encoding='utf-8') as f:
        json.dump(job, f)
    r = subprocess.run(['deno', 'run', '--no-config', '--no-lock', '-A', f'--import-map={mp}',
                        os.path.join(S.HERE, 'tuta_parity.mjs'), jp], capture_output=True, text=True, encoding='utf-8')
    if r.returncode != 0:
        raise RuntimeError(f'deno tuta_parity.mjs failed ({r.returncode}): {r.stderr[-2000:]}')
    line = [ln for ln in r.stdout.splitlines() if ln.startswith('{')][-1]
    with open(os.path.join(S.OUT, 'tuta_ref.json'), 'w', encoding='utf-8') as f:
        f.write(line)
    return json.loads(line)


def cloud(o):
    """world vertices of an object (evaluated): centroid + covariance, Blender axes"""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    P = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', P)
    ev.to_mesh_clear()
    P = P.reshape(-1, 3)
    M = np.array([list(r) for r in o.matrix_world])
    W = P @ M[:3, :3].T + M[:3, 3]
    c = W.mean(0)
    D = W - c
    return c, D.T @ D / len(W)


def call(wd, m, *args):
    getattr(wd, PY.get(m, m))(*args)


def badge_state(wd, k):
    """the badge as it renders now: its flight copy while that shows, else the badge itself"""
    fl = wd._flyers.get(k)
    o = fl if (fl is not None and not fl.hide_render) else wd.uf[k]
    vis = not o.hide_render
    c, cov = cloud(o)
    return {'vis': vis, 'c': c, 'cov': cov, 'glow': float(wd.arm[f'cs_tuta.glow.{k}']),
            'ghost': float(wd.arm[f'cs_tuta.ghost.{k}'])}


def parity(C, R):
    ref = reference()
    R['ref_frames'] = len(ref['frames'])
    sc = S.clean_scene(FPS)
    sc.frame_start, sc.frame_end = F0, F1
    h = load_vrm('claude_suit_wardrobe')
    h.arm.scale = (SCALE,) * 3
    bpy.context.view_layer.update()
    wd = make_wardrobe(h, wear='tuta')
    C.check('every TuTa layer found (tuta, uf_boots, uf_straps, five badges, the sun disc)', not wd.missing,
            f'missing {wd.missing}' if wd.missing else f'{len(TU.UF_LAYERS)} layers')
    lay = {n: (not wd.uf[n].hide_render) if n in wd.uf else None for n in ('tuta', 'uf_boots', 'uf_straps')}
    shoes = [not o.hide_render for o in wd._base_shoes]
    C.check("wear('tuta'): the tuta, boots and straps shown, digi's shoes hidden, as the JS",
            all(lay[n] == ref['layers'][n] for n in lay) and shoes == ref['layers']['shoes'], f'{lay}, shoes {shoes}')
    built = {n: any(wd.installed.get(m.name) for m in wd.mats.get(n, []))
             for n in ('tuta', 'boot_upper', 'boot_sole', 'webbing', 'buckle')}
    face_ok = any(m.node_tree.nodes.get('cs.u.paint') is not None for m in wd.mats.get('face', []))
    eyes_ok = any(m.node_tree.nodes.get('cs.u.eyes') is not None for m in wd.mats.get('Material', []))
    disc_ok = any(any(n.name.startswith('cs.') for n in m.node_tree.nodes) for m in wd.mats.get('sundisc', []))
    R['surfaces'] = dict(built, face_paint=face_ok, catchlights=eyes_ok, disc=disc_ok)
    C.check('the TuTa surfaces are built (tuta, boots, sole, webbing, buckle, face paint, catchlights, disc)',
            all(R['surfaces'].values()), str(R['surfaces']))
    for m, *args in NOW:
        call(wd, m, *args)
    wd.schedule(SCHEDULE)
    rep = wd.bake(F0, F1)
    R['bake'] = rep
    # frame by frame against the JS
    worst = {'c_mm': 0.0, 'cov_rel': 0.0, 'glow': 0.0, 'ghost': 0.0}
    vis_bad, spark_bad, spark_mm = [], [], 0.0
    states = {}
    for fr in ref['frames']:
        f = fr['f']
        sc.frame_set(f)
        for k, js in fr['badges'].items():
            st = badge_state(wd, k)
            states[(f, k)] = st
            if st['vis'] != js['vis']:
                vis_bad.append((f, k, st['vis'], js['vis']))
                continue
            worst['glow'] = max(worst['glow'], abs(st['glow'] - js['glow']))
            worst['ghost'] = max(worst['ghost'], abs(st['ghost'] - js['ghost']))
            if not js['vis']:
                continue
            cj = R3 @ np.array(js['c'])
            covj = R3 @ np.array(js['cov']) @ R3.T
            worst['c_mm'] = max(worst['c_mm'], 1000 * float(np.linalg.norm(st['c'] - cj)))
            worst['cov_rel'] = max(worst['cov_rel'], float(np.linalg.norm(st['cov'] - covj) / np.linalg.norm(covj)))
        # every frame, every badge with sparks on either side: before the JS makes a badge's sparks (its first pop)
        # they do not exist there, so they must be hidden here (each card: the flare and the eight embers)
        for k in sorted(set(fr['sparks']) | set(wd._sparks)):
            js = fr['sparks'].get(k, {'vis': False})
            sp = wd._sparks.get(k)
            if sp is None:
                if js['vis']:
                    spark_bad.append((f, k, 'no sparks'))
                continue
            cards_vis = {not o.hide_render for o in [sp['flare']] + sp['embers']}
            vis = not sp['flare'].hide_render
            if len(cards_vis) > 1 or vis != js['vis']:
                spark_bad.append((f, k, sorted(cards_vis), js['vis']))
                continue
            if not vis:
                continue
            pairs = [(sp['flare'], js['flare'])] + list(zip(sp['embers'], js['embers']))
            for o, (p, s) in pairs:
                spark_mm = max(spark_mm, 1000 * float(np.linalg.norm(np.array(o.matrix_world.translation) - R3 @ np.array(p))))
                if abs(o.matrix_world.to_scale()[0] - s) > 1e-4:
                    spark_bad.append((f, k, 'scale', round(o.matrix_world.to_scale()[0], 5), round(s, 5)))
    R['worst'] = {k: round(v, 5) for k, v in worst.items()}
    C.check('every badge visible on exactly the JS frames (attached, snapping, unsnapping, flying, lingering)',
            not vis_bad, f'{len(ref["frames"])} frames x 5 badges' + ('' if not vis_bad else f'; {vis_bad[:5]}'))
    C.check("every shown badge within 1 mm of the JS's (its world centroid) and its spread within 2 %",
            worst['c_mm'] < 1.0 and worst['cov_rel'] < 0.02, f"{worst['c_mm']:.4f} mm, {100 * worst['cov_rel']:.3f} %")
    C.check("every badge's glow and ghost equal the JS's (emissive / ufEmissive, U.ghost)",
            worst['glow'] < 1e-4 and worst['ghost'] < 1e-4, f"glow {worst['glow']:.2e}, ghost {worst['ghost']:.2e}")
    R['spark_mm'] = round(spark_mm, 4)
    C.check("the pop's sparks: the same frames (every frame, hidden before the first pop as the JS has none yet), the "
            "flare and eight embers within 1 mm, sized as the JS's",
            not spark_bad and spark_mm < 1.0, f'{spark_mm:.4f} mm' + ('' if not spark_bad else f'; {spark_bad[:5]}'))
    # after the run
    sc.frame_set(F1)
    u = {'neon': wd.arm['cs_tuta.neon'], 'paint': wd.arm['cs_tuta.paint'], 'eyes': wd.arm['cs_tuta.eyes'],
         'eyeNeon': wd.arm['cs_tuta.eye_neon']}
    ok_u = all(abs(float(u[k]) - float(ref['uniforms'][k])) < 1e-6 for k in u)
    C.check('the uniforms after the run (neon, paint, eyes, eyeNeon) equal the JS\'s', ok_u, f'{u} / {ref["uniforms"]}')
    C.check('pinned / ghosts equal the JS\'s', sorted(wd.pinned) == sorted(ref['pinned']) and sorted(wd.ghosts) == sorted(ref['ghosts']),
            f'pinned {sorted(wd.pinned)}, ghosts {sorted(wd.ghosts)}')
    bw = {k: wd.badge_world(k, frame=F1) for k in TU.BADGES}
    d_bw = {k: 1000 * (bw[k]['position'] - Vector(R3 @ np.array(ref['world'][k]['p']))).length for k in TU.BADGES}
    bad_bw = [k for k in TU.BADGES if bw[k]['visible'] != ref['world'][k]['visible'] or
              (bw[k]['visible'] and d_bw[k] > 1.0)]
    R['badge_world'] = {k: [round(x, 4) for x in v['position']] + [v['visible'], v['flying']] for k, v in bw.items()}
    C.check("badge_world: where each badge is at the end (a lingering one on the floor) as the JS's badgeWorld",
            not bad_bw, f'{bad_bw}' if bad_bw else
            f"visible ones within {max(d_bw[k] for k in TU.BADGES if bw[k]['visible']):.4f} mm")
    # cold playback
    f_mid = 40
    sc.frame_set(F1)
    sc.frame_set(f_mid)
    cold = {k: badge_state(wd, k) for k in TU.BADGES}
    same = all(cold[k]['vis'] == states[(f_mid, k)]['vis'] and float(np.linalg.norm(cold[k]['c'] - states[(f_mid, k)]['c'])) < 1e-6
               and abs(cold[k]['glow'] - states[(f_mid, k)]['glow']) < 1e-6 for k in TU.BADGES)
    C.check('keyed: a frame jumped to cold gives the same badges (no state carried from the bake)', same, f'frame {f_mid}')
    # the cyclist under the TuTa
    wd.wear('cyclist_1892')
    cy = ref['cyclist']
    folds = {k: list(v) for k, v in wd.folds.items()}
    dirs = {k: wd.petal_dir(k) for k in PETALS}
    dmax = max(max(abs(dirs[k][a] - cy['petal_dirs'][k][a]) for a in ('up', 'fwd', 'side')) for k in PETALS)
    hc, _hcov = cloud(wd.layers['boater'])
    hat_mm = 1000 * float(np.linalg.norm(hc - R3 @ np.array(cy['hat']['c'])))
    R['cyclist'] = {'folds': folds, 'js_folds': cy['folds'], 'lift_mm': round(1000 * wd.lift, 2),
                    'js_lift_mm': round(1000 * cy['lift'], 2), 'petal_dir_max_diff': dmax, 'hat_mm': round(hat_mm, 3)}
    C.check("the cyclist's auto folds and brim lift equal the JS's (at rest)",
            folds == {k: list(v) for k, v in cy['folds'].items()} and abs(wd.lift - cy['lift']) < 0.0005,
            f"{folds}; lift {1000 * wd.lift:.2f} / {1000 * cy['lift']:.2f} mm")
    C.check("the cyclist's folded petal directions (head frame) and the boater's centroid equal the JS's",
            dmax <= 0.011 and hat_mm < 2.0, f'direction max diff {dmax:.3f}; hat {hat_mm:.2f} mm')
    # a hand-placed hat: offset in model metres and a scale
    from eidoblend.characters.claudesona.wardrobe import WARDROBE
    WARDROBE.update(HAT_OFFSET)
    for key in HAT_OFFSET:
        wd.wear(key)
        js = ref['wears'][key]
        c, cov = cloud(wd.layers['boater'])
        d = 1000 * float(np.linalg.norm(c - R3 @ np.array(js['hat']['c'])))
        covj = R3 @ np.array(js['hat']['cov']) @ R3.T
        rel = float(np.linalg.norm(cov - covj) / np.linalg.norm(covj))
        shown = {n: not o.hide_render for n, o in wd.layers.items()}
        same_layers = all(shown[n] == js['layers'][n] for n in shown if n in js['layers'])
        R['hat_offset'] = {'mm': round(d, 4), 'cov_rel': round(rel, 5), 'layers_same': same_layers}
        C.check("a hand-placed hat ({offset, scale}) lands where the JS puts it, at its size; the preset's layers as the JS",
                d < 1.0 and rel < 0.01 and same_layers, f'{d:.4f} mm, spread {100 * rel:.3f} %')
    return h, wd


# ------------------------------------------------------------------------------------------------ renders
def night_studio(sc):
    """the turntable's studio, dimmed (the TuTa is black techwear made for a night film: its neon reads in the dark)"""
    S.turntable_studio(sc, light=0.45, background=0x14161c)


def cam_at(name, target, yaw, dist, dz=0.0, lens=50):
    a = math.radians(yaw)
    cam = S.camera(name, lens=lens)
    t = Vector(target)
    S.aim(cam, (t.x + dist * math.sin(a), t.y - dist * math.cos(a), t.z + dz), t)
    return cam


def render(R):
    sc = S.clean_scene(FPS)
    S.probe_render(sc, res=(480, 640), samples=16)
    night_studio(sc)
    h = load_vrm('claude_suit_wardrobe', name='tuta_film')
    h.arm.scale = (SCALE,) * 3
    sc.frame_start, sc.frame_end = 1, 120
    play_vrma_default(h, 'idle', t=0.0, loop=True, until=5.0)
    wd = make_wardrobe(h, wear='tuta')
    wd.face_paint(True)
    wd.sun_disc(True)
    for k in TU.BADGES:
        wd.pin(k)
    # the second half: mod_gold ejected at 2.0 s (frame 61), mod_chrome unpinned at once (its ghost on the arm)
    wd.schedule([{'at': 2.0, 'unpin': 'mod_gold', 'eject': True}, {'at': 1.5, 'unpin': 'mod_chrome'}])
    wd.bake(1, 120)
    from eidoblend.characters.springs import bake_springs
    bake_springs(h, 1, 120)
    hb = h.arm.matrix_world @ h.arm.data.bones[h.humanoid['head']].head_local
    body_c = Vector((hb.x, hb.y, hb.z * 0.55))
    paths = []
    for yaw in (20, 160):
        cam = cam_at(f'body{yaw}', body_c, yaw, 3.2, dz=0.15, lens=40)
        p = os.path.join(S.OUT, f'tuta_body_y{yaw:03d}.png')
        S.still(sc, cam, 40, p)
        paths.append(p)
    R['tuta_sheet'] = S.sheet(paths, os.path.join(S.OUT, 'tuta_sheet.png'), cols=2)
    det = []
    chest = Vector((hb.x, hb.y, hb.z - 0.30))
    for nm, tgt, yaw, dist, dz, fr in (('chest', chest, 15, 0.95, 0.02, 100), ('back', Vector((hb.x, hb.y, hb.z - 0.45)), 180, 1.05, 0.0, 100),
                                       ('legs', Vector((hb.x, hb.y, hb.z * 0.32)), 25, 1.2, 0.05, 100),
                                       ('face', Vector((hb.x, hb.y, hb.z + 0.08)), 10, 0.75, 0.0, 30)):
        cam = cam_at(f'det_{nm}', tgt, yaw, dist, dz=dz, lens=50)
        p = os.path.join(S.OUT, f'tuta_detail_{nm}.png')
        S.still(sc, cam, fr, p)
        det.append(p)
    R['tuta_details_sheet'] = S.sheet(det, os.path.join(S.OUT, 'tuta_details_sheet.png'), cols=4)
    ej = []
    cam = cam_at('eject', Vector((hb.x, hb.y, hb.z - 0.35)), 30, 2.4, dz=0.1, lens=40)
    for f in (61, 63, 67, 75, 90):
        p = os.path.join(S.OUT, f'tuta_eject_f{f:03d}.png')
        S.still(sc, cam, f, p)
        ej.append(p)
    R['tuta_eject_sheet'] = S.sheet(ej, os.path.join(S.OUT, 'tuta_eject_sheet.png'), cols=5)
    ne = []
    cam = cam_at('neon', body_c, 20, 3.2, dz=0.15, lens=40)
    for lv in (0.0, 0.4, 1.0):
        wd.neon(lv, frame=40)
        p = os.path.join(S.OUT, f'tuta_neon_{int(lv * 10):02d}.png')
        S.still(sc, cam, 40, p)
        ne.append(p)
    R['tuta_neon_sheet'] = S.sheet(ne, os.path.join(S.OUT, 'tuta_neon_sheet.png'), cols=3)


def main():
    R, C = {}, S.Checks('tuta')
    try:
        parity(C, R)
        if RENDER:
            render(R)
    except Exception:
        traceback.print_exc()
        R['error'] = traceback.format_exc()
        C.check('ran without an exception', False)
    R['checks'] = C.rows
    R['all_pass'] = C.all_pass and 'error' not in R
    with open(os.path.join(S.OUT, 'tuta.json'), 'w', encoding='utf-8') as f:
        json.dump(R, f, indent=1, default=str)
    print('[tuta] ALL PASS' if R['all_pass'] else '[tuta] SOME FAILED', flush=True)


main()
