"""The PBR look (claudesona/look.py) on the TuTa (claudesona/tuta.py): everything the TuTa animates or builds on MToon's
inputs must reach the Principled BSDF too, in either order (the look set after the wardrobe, or before it, as
blender/tools/vrm_turntable.py does with --look pbr).

Checks, both orders:
    every badge material's Principled Emission Strength is DRIVEN as MToon's is, and on a snap's flash frame, a
        flight frame and at rest it equals MToon's driven value (the glow the render reads)
    the TuTa's bump (weave, seams, piping cord) feeds the Principled's Normal
    the face paint feeds the face's PBR base colour, the catchlights its emission, the sun disc its front/back
    neon(0) keyed on a frame dims the badges' PBR glow to 0 there
Stills: out/pbr_tuta_sheet.png: MToon and PBR side by side at the snap's flash, at rest, and the painted face in PBR.

    bash run_blender.sh blender/tests/claudesona/test_pbr_tuta.py [--no-render]
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

from mathutils import Vector  # noqa: E402

from eidoblend.characters import load_vrm, play_vrma_default  # noqa: E402
from eidoblend.characters.claudesona import look as LK  # noqa: E402
from eidoblend.characters.claudesona import tuta as TU  # noqa: E402
from eidoblend.characters.claudesona.wardrobe import make_wardrobe  # noqa: E402

ARGS = S.argv()
RENDER = '--no-render' not in ARGS
FPS, F1, SCALE = 30, 60, 0.87
SNAP_T, EJECT_T, DARK_F = 0.5, 1.0, 58          # mod_gold snaps on at 0.5 s; mod_red pops off at 1.0 s; neon 0 at f58
OUT = os.path.join(S.OUT, 'pbr_tuta')
os.makedirs(OUT, exist_ok=True)


def build(order):
    sc = S.clean_scene(FPS)
    sc.frame_start, sc.frame_end = 1, F1
    h = load_vrm('claude_suit_wardrobe', name=f'pbr_{order}')
    h.arm.scale = (SCALE,) * 3
    play_vrma_default(h, 'idle', t=0.0, loop=True, until=F1 / FPS)
    if order == 'before':
        LK.set_look(h, 'pbr')
    wd = make_wardrobe(h, wear='tuta')
    wd.face_paint(True)
    wd.sun_disc(True)
    for k in ('mod_red', 'mod_chrome', 'mod_warning', 'mod_spray'):
        wd.pin(k)
    wd.schedule([{'at': SNAP_T, 'pin': 'mod_gold'}, {'at': EJECT_T, 'unpin': 'mod_red', 'eject': True}])
    wd.bake(1, F1 - 4)
    wd.neon(1.0, frame=1)
    wd.neon(0.0, frame=DARK_F)
    if order == 'after':
        LK.set_look(h, 'pbr')
    return sc, h, wd


def _bsdf(m):
    return m.node_tree.nodes.get(LK.PBR + 'bsdf')


def _mo(m):
    return m.node_tree.nodes.get('Mtoon1Material.Mtoon1Output')


def _from_cs(sock):
    """the socket is fed (through any chain) by a node of this package ('cs.*')"""
    seen, todo = set(), [sock]
    while todo:
        s = todo.pop()
        for l in s.links:
            n = l.from_node
            if n.name.startswith('cs.'):
                return True
            if n.name not in seen:
                seen.add(n.name)
                todo.extend(i for i in n.inputs if i.is_linked)
    return False


def checks(order, sc, h, wd, C, R):
    rr = R[order] = {}
    snap_f = 1 + int(round(SNAP_T * FPS))           # the flash's first frame
    fly_f = 1 + int(round(EJECT_T * FPS)) + 4
    frames = (snap_f, snap_f + 2, fly_f, 40, DARK_F + 1)
    bad, vals = [], {}
    for k in TU.BADGES:
        for m in wd.mats.get(k, []):
            b, mo = _bsdf(m), _mo(m)
            drv = LK._drivers_of(m.node_tree, b.inputs['Emission Strength'])
            if not drv:
                bad.append((k, 'no driver on the Principled emission strength'))
                continue
            for f in frames:
                sc.frame_set(f)
                a, p = mo.inputs['Emissive Strength'].default_value, b.inputs['Emission Strength'].default_value
                vals.setdefault(k, []).append((f, round(a, 4), round(p, 4)))
                if abs(a - p) > 1e-5:
                    bad.append((k, f, a, p))
    rr['glow'] = vals
    C.check(f'{order}: every badge\'s PBR emission strength is driven as MToon\'s, equal on the flash, flight and rest '
            'frames', not bad and len(vals) == len(TU.BADGES), f"{bad[:4]}; mod_gold {vals.get('mod_gold')}")
    g = {f: p for f, _a, p in vals.get('mod_gold', [])}
    C.check(f'{order}: the snap flashes in PBR (mod_gold brighter on its flash than at rest) and neon 0 darkens it',
            g.get(snap_f, 0) > 1.5 * g.get(40, 1e9) and g.get(DARK_F + 1, 1.0) < 1e-6, f'{g}')
    tm = wd.mats['tuta'][0]
    C.check(f'{order}: the TuTa\'s bump (weave, seams, piping) feeds the Principled normal',
            _from_cs(_bsdf(tm).inputs['Normal']), _bsdf(tm).inputs['Normal'].links[0].from_node.name
            if _bsdf(tm).inputs['Normal'].is_linked else 'unlinked')
    fm = wd.mats['face'][0]
    base = fm.node_tree.nodes[LK.PBR + 'base']
    em = fm.node_tree.nodes[LK.PBR + 'emission']
    pm = wd.mats['Material'][0]
    pem = pm.node_tree.nodes[LK.PBR + 'emission']
    dm = wd.mats.get('sundisc', [None])[0]
    ok_disc = dm is None or _from_cs(next(s for s in dm.node_tree.nodes[LK.PBR + 'base'].inputs if s.identifier == 'A_Color'))
    rr['feeds'] = {'face_paint_base': _from_cs(next(s for s in base.inputs if s.identifier == 'A_Color')),
                   'face_paint_emission': _from_cs(next(s for s in em.inputs if s.identifier == 'A_Color')),
                   'catchlights_emission': _from_cs(next(s for s in pem.inputs if s.identifier == 'A_Color')),
                   'sun_disc_base': ok_disc}
    C.check(f'{order}: the face paint, the catchlights and the sun disc feed the PBR path', all(rr['feeds'].values()),
            f"{rr['feeds']}")


def render(R):
    sc, h, wd = build('after')
    S.probe_render(sc, res=(480, 640), samples=16)
    S.turntable_studio(sc, light=0.45, background=0x14161c)
    hb = h.arm.matrix_world @ h.arm.data.bones[h.humanoid['head']].head_local
    cam = S.camera('chest', lens=50)
    tgt = Vector((hb.x, hb.y, hb.z - 0.32))
    S.aim(cam, (tgt.x + 0.95 * math.sin(math.radians(15)), tgt.y - 0.95 * math.cos(math.radians(15)), tgt.z + 0.05), tgt)
    face = S.camera('face', lens=50)
    ft = Vector((hb.x, hb.y, hb.z + 0.08))
    S.aim(face, (ft.x + 0.75 * math.sin(math.radians(10)), ft.y - 0.75 * math.cos(math.radians(10)), ft.z), ft)
    snap_f = 1 + int(round(SNAP_T * FPS))
    paths = []
    for look in ('mtoon', 'pbr'):
        LK.set_look(h, look)
        for nm, c, f in (('flash', cam, snap_f), ('rest', cam, 40), ('face', face, 40)):
            p = os.path.join(OUT, f'pbr_tuta_{look}_{nm}.png')
            S.still(sc, c, f, p)
            paths.append(p)
    R['sheet'] = S.sheet(paths, os.path.join(S.OUT, 'pbr_tuta_sheet.png'), cols=3)


def main():
    R, C = {}, S.Checks('pbr_tuta')
    try:
        for order in ('after', 'before'):
            sc, h, wd = build(order)
            checks(order, sc, h, wd, C, R)
        if RENDER:
            render(R)
    except Exception:
        traceback.print_exc()
        R['error'] = traceback.format_exc()
        C.check('ran without an exception', False)
    R['checks'] = C.rows
    R['all_pass'] = C.all_pass and 'error' not in R
    with open(os.path.join(OUT, 'pbr_tuta.json'), 'w', encoding='utf-8') as f:
        json.dump(R, f, indent=1, default=str)
    print('[pbr_tuta] ALL PASS' if R['all_pass'] else '[pbr_tuta] SOME FAILED', flush=True)


main()
