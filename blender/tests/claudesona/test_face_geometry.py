"""The claudesona's face geometry (claudesona/face.py) measured against claudesona_face.js run in deno on the same VRM
(face_geometry_parity.mjs): install_suit_mouth and install_viseme_mouth must leave every face vertex, at rest and at
the end of every shape key, where installSuitMouth / installVisemeMouth leave three's (geometry space, three's axes).
No render: an API check.

Checks, per install:
    the re-seated rest of the plate (eyes, smile, mouth plate) and of the blush within 0.05 mm of the JS
    every expression target's end (Blink, Smile, EyeClosed*, Blush ...) within 0.05 mm of the JS
    the mouth's own keys (suit: seat, wide, round; viseme: seat and the ten visemes, the line's warp included)
    within 0.05 mm of the JS's targets at weight 1 (the openings on top of the seat, as the JS's deltas are)
    the rig's own mouth shapes (show MMD mouth, A, vis_aa ...) keep their deltas on the new rest
    the viseme face's idx names the same shapes as the JS's

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    bash run_blender.sh C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/claudesona/test_face_geometry.py
"""

import json
import os
import sys
import traceback

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stage as S  # noqa: E402

import numpy as np  # noqa: E402

from eidoblend.characters import load_vrm  # noqa: E402
from eidoblend.characters.claudesona import _mesh as M  # noqa: E402
from eidoblend.characters.claudesona import face as F  # noqa: E402

TOL_MM = 0.05
OUT = os.path.join(S.OUT, 'face_geometry')
os.makedirs(OUT, exist_ok=True)


def reference(install):
    job = {'module': 'file:///' + os.path.join(S.REPO, 'eidoverse', 'claudesona_face.js').replace('\\', '/'),
           'vrm': os.path.join(S.VRMS, 'claude_suit.vrm').replace('\\', '/'), 'install': install}
    return S.run_mjs('face_geometry_parity.mjs', job, f'face_geometry/{install}', with_three=True)


def slot_of(h, gname):
    o, k = M.find(h, gname, need_keys=True)
    return o, k


def dump(h, plate):
    """{slot glTF name: (vertex indices, {key name: (n, 3) coords in the plate's geometry space, three's axes})}"""
    tm = M.to_space(plate, plate)
    out = {}
    slots = M.gltf_slots(h)[plate.name]
    for k, gname in enumerate(slots):
        idx = M.slot_vertices(plate, k)
        keys = {}
        for kb in plate.data.shape_keys.key_blocks:
            keys[kb.name] = M.apply(tm, M.key_coords(kb)[idx])
        out[gname] = (idx, keys)
    return out


def match(A, B):
    """for each row of A the index of the nearest row of B (and the distance)"""
    from mathutils.kdtree import KDTree
    kd = KDTree(len(B))
    for i, p in enumerate(B):
        kd.insert(p, i)
    kd.balance()
    idx, dist = np.empty(len(A), int), np.empty(len(A))
    for i, p in enumerate(A):
        _co, j, d = kd.find(p)
        idx[i], dist[i] = j, d
    return idx, dist


def run(install, C, rows):
    S.clean_scene(30)
    h = load_vrm(os.path.join(S.VRMS, 'claude_suit.vrm'))
    plate, _k = slot_of(h, 'Material')
    before = dump(h, plate)
    face = F.install_suit_mouth(h) if install == 'suit' else F.install_viseme_mouth(h)
    after = dump(h, plate)
    ref = reference(install)
    by_mat = {m['mats'][0]: m for m in ref['meshes']}
    news = ({'seat': '#53', 'wide': '#54', 'round': '#55'} if install == 'suit'
            else {k: f'#{v}' for k, v in ref['idx'].items()})
    worst = {}
    for gname in ('Material', 'BLUSH', 'Material.001'):
        if gname not in after or gname not in by_mat:
            continue
        m = by_mat[gname]
        R0 = np.array(m['rest0']).reshape(-1, 3)
        R = np.array(m['rest']).reshape(-1, 3)
        T = {k: np.array(v).reshape(-1, 3) for k, v in m['targets'].items()}
        idx_b, keys_b = after[gname]
        rest0_b = before[gname][1][plate.data.shape_keys.key_blocks[0].name]
        j, d0 = match(rest0_b, R0)
        C.check(f'{install}: {gname} vertices matched to the JS by their rest position', d0.max() < 1e-6,
                f'{len(idx_b)} vertices, worst {d0.max() * 1000:.6f} mm')
        basis = keys_b[plate.data.shape_keys.key_blocks[0].name]
        e = np.linalg.norm(basis - R[j], axis=1).max() * 1000
        worst[f'{gname} rest'] = e
        C.check(f'{install}: {gname} re-seated rest = the JS', e < TOL_MM, f'max {e:.4f} mm')
        rig_e, expr_e, new_e = 0.0, 0.0, {}
        for kn, co in keys_b.items():
            if kn == plate.data.shape_keys.key_blocks[0].name:
                continue
            if kn.startswith(F.KEY_PREFIX):
                short = kn[len(F.KEY_PREFIX):].split('.', 1)[1]
                tname = news.get(short)
                if tname is None or tname not in T:
                    continue
                seat = T[news['seat']]
                want = R + T[tname] + (seat if short != 'seat' else 0.0)
                e = np.linalg.norm(co - want[j], axis=1).max() * 1000
                new_e[short] = e
                continue
            if kn not in T:
                continue
            want = R + T[kn]
            e = np.linalg.norm(co - want[j], axis=1).max() * 1000
            if kn in F.RIG_MOUTH:
                rig_e = max(rig_e, e)
            else:
                expr_e = max(expr_e, e)
        worst[f'{gname} expressions'] = expr_e
        worst[f'{gname} rig mouth'] = rig_e
        C.check(f'{install}: {gname} expression target ends = the JS', expr_e < TOL_MM, f'max {expr_e:.4f} mm')
        C.check(f'{install}: {gname} rig mouth shapes keep their deltas = the JS', rig_e < TOL_MM, f'max {rig_e:.4f} mm')
        if new_e:
            mx = max(new_e.values())
            worst[f'{gname} mouth keys'] = new_e
            C.check(f'{install}: {gname} the mouth keys = the JS targets at weight 1', mx < TOL_MM,
                    ', '.join(f'{k} {v:.4f}' for k, v in sorted(new_e.items())) + ' mm')
    if install == 'viseme':
        C.check('viseme: idx names every shape the JS\'s idx does (here: the plate\'s shape key per shape)',
                set(face.idx) == set(ref['idx']), f'{sorted(face.idx)}')
    rows[install] = {'worst_mm': worst, 'report': {k: v for k, v in face.report.items() if not isinstance(v, (list, dict))}}


def main():
    C = S.Checks('face_geometry')
    rows = {}
    for install in ('suit', 'viseme'):
        try:
            run(install, C, rows)
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            C.check(f'{install}: ran', False, 'exception')
    with open(os.path.join(OUT, 'face_geometry.json'), 'w', encoding='utf-8') as f:
        json.dump({'rows': C.rows, 'measures': rows}, f, indent=1, default=str)
    print(f'[face_geometry] {"ALL PASS" if C.all_pass else "SOME FAIL"}', flush=True)


main()
