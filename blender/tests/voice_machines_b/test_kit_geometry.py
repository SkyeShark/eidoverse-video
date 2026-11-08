"""The era-1 kit's geometry builders and tandem.js's teapot against three r184's own (geometry_parity_dump.mjs):
positions, normals, UVs and indices of the runtime parts the machines build (the teletype's buttons and keys, the
mainframe's lamp bulbs, lens boxes, vacuum-column runs and bends, the paper roll) and the Utah teapot stoker.

    deno run --no-config --no-lock -A blender/tests/voice_machines_b/geometry_parity_dump.mjs \\
        <main checkout>/node_modules/three/build blender/tests/voice_machines_b/out/geometry_js.json
    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/voice_machines_b/test_kit_geometry.py
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _stage as S  # noqa: E402

import numpy as np  # noqa: E402


def compare(tag, geo, J, tol=2e-6):
    """PASS when the port's vertices (same order) and triangles equal three's: positions, normals, UVs to float32"""
    pos = np.array(J['position']).reshape(-1, 3)
    nrm = np.array(J['normal']).reshape(-1, 3)
    uv = np.array(J['uv']).reshape(-1, 2)
    if J['index'] is None:            # three made it non-indexed (RoundedBoxGeometry): compare corner by corner
        c = geo.tris.ravel()
        geo = type(geo)(geo.pos[c], geo.nrm[c], geo.uv[c], np.arange(len(c)).reshape(-1, 3))
    idx = np.array(J['index'] if J['index'] is not None else np.arange(len(pos))).reshape(-1, 3)
    if len(geo.pos) != len(pos) or len(geo.tris) != len(idx):
        return S.check(f'kit geometry: {tag} equals three', False,
                       f'{len(geo.pos)} vertices / {len(geo.tris)} triangles vs three {len(pos)} / {len(idx)}')
    scale = max(1.0, float(np.abs(pos).max()))
    e_pos = float(np.abs(geo.pos - pos).max()) / scale
    e_nrm = float(np.abs(geo.nrm - nrm).max())
    e_uv = float(np.abs(geo.uv - uv).max())
    same_tris = bool(np.array_equal(geo.tris, idx))
    return S.check(f'kit geometry: {tag} equals three (positions, normals, UVs, triangles)',
                   e_pos < tol and e_nrm < 1e-5 and e_uv < tol and same_tris,
                   f'pos {e_pos:.1e}, normal {e_nrm:.1e}, uv {e_uv:.1e}, triangles {"same" if same_tris else "differ"}')


def run(render=False):
    S.fresh_scene()
    dump = S.OUT / 'geometry_js.json'
    if not dump.exists():
        S.check('kit geometry: the dump (geometry_parity_dump.mjs) is present', False, str(dump))
        return S.summary('kit geometry')
    J = json.loads(dump.read_text())
    from eidoblend.props.voice_machines import voder as K, mainframe as MF
    from eidoblend.props import tandem as TD
    compare('rbox (the teletype call-control button)', K.rbox(0.0145, 0.010, 0.0145, 0.0025), J['rbox_button'])
    compare('rbox (a 729 lens box, its atlas cell UVs)', K.rbox(0.066, 0.028, 0.006, 0.002), J['rbox_lens'])
    compare('the lamp bulb (a half sphere turned to face +Z)', MF.bulb_geo(), J['bulb'])
    compare('a key (CylinderGeometry, 24 sides)', K.cylinder_geo(0.0072, 0.0077, 0.017, 24, 1), J['key'])
    compare('a vacuum-column bend (TorusGeometry, half)', K.torus_geo(0.031, 0.0008, 6, 24, math.pi), J['loop_bend'])
    compare('the paper roll (LatheGeometry, 64)',
            K.lathe_geo([(0.012, -0.108), (0.035, -0.108), (0.035, 0.108), (0.012, 0.108)], 64), J['roll'])
    compare('a vacuum-column run (BoxGeometry 1 x 8 x 1)', K.box_geo(0.0016, 0.9, 0.0127, 1, 8, 1), J['loop_run'])
    compare('the teapot body (TeapotGeometry, 20 segments)', TD.teapot_geometry(1, 20, True, False, True, True, False),
            J['teapot_body'], tol=5e-6)
    compare('the teapot lid', TD.teapot_geometry(1, 20, False, True, False, True, False), J['teapot_lid'], tol=5e-6)
    if 'paper_curl' in J:
        from eidoblend.props.voice_machines import teletype as TT
        path, i_print = TT.paper_path(K.json_load('teletype_layout.json')['paper'])
        n_back_below = 4 + 9                              # the strip from the roll and round the platen, then the curl
        got = np.array(path[n_back_below:])
        want = np.array(J['paper_curl'][1:])
        err = float(np.abs(got - want).max()) if got.shape == want.shape else float('inf')
        S.check("kit geometry: the teletype paper's curl equals three's CatmullRomCurve3 (centripetal, 72 spaced)",
                err < 1e-6, f'{err * 1000:.4f} mm over {len(want)} points')
    return S.summary('kit geometry')


if __name__ == '__main__':
    sys.exit(1 if run(render='--render' in sys.argv) else 0)
