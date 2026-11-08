"""load_part, rendered: single physical parts taken out of their donor GLBs (index.js loadPart), each framed alone in
the kit's studio. Checks per part: exactly that part's triangles (the provenance/ ownership count), one part reported,
the part where it sits in the donor (load_part does not recentre: the extracted triangles' world box equals the box of
the same triangles in a full load of the donor), every other donor mesh hidden, and the still written.

    out/parts/<model>__<part>.png        320 x 240
    out/parts_render.json

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/robotics/test_parts_render.py
"""

import os
import re
import sys
import traceback

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _rk as K  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402

from eidoblend.characters.robotics import frame_camera, load_part, make_robot, studio  # noqa: E402
from eidoblend.characters.robotics.studio import make_camera  # noqa: E402

OUT = os.path.join(K.OUT, 'parts')
os.makedirs(OUT, exist_ok=True)
# (model, parts: names, or how many of the largest parts to take)
CASES = [('face', ['FACE swept tilt yoke']), ('air/air', ['A420 hinge rotor and boom socket 0']),
         ('hand', 2), ('mantis', 2), ('humanoid', 2), ('quadruped', 1), ('process/spindle', 2), ('scara', 1),
         ('manufacturing/fdm', 1), ('stock/common', 2)]


def face_box(robot, part):
    """the world box of `part`'s triangles in a loaded robot (every mesh holding it)"""
    lo, hi = np.full(3, np.inf), np.full(3, -np.inf)
    bpy.context.view_layer.update()
    for o in robot.meshes():
        faces = robot.part_faces(o)
        if not faces:
            continue
        sel = [i for i, p in enumerate(faces) if p == part]
        if not sel:
            continue
        me = o.data
        co = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)
        vi = sorted({v for i in sel for v in me.polygons[i].vertices})
        m = np.array(o.matrix_world)
        w = co[vi] @ m[:3, :3].T + m[:3, 3]
        lo, hi = np.minimum(lo, w.min(0)), np.maximum(hi, w.max(0))
    return lo, hi


def main():
    sc = K.clean_scene()
    K.probe_render(sc, (320, 240), 12)
    studio(sc)
    cam = make_camera(35, 'parts camera', sc)
    sc.camera = cam
    rec = {}
    for rid, parts in CASES:
        try:
            donor = make_robot(rid, scene=sc, textures=False)
            if isinstance(parts, int):
                counts = {}
                for o in donor.meshes():
                    for p in donor.part_faces(o) or ():
                        counts[p] = counts.get(p, 0) + 1
                parts = [p for p, _ in sorted(counts.items(), key=lambda kv: -kv[1])[:parts]]
            want = {p: (sum(sum(1 for q in donor.part_faces(o) or () if q == p) for o in donor.meshes()),
                        face_box(donor, p)) for p in parts}
            donor.dispose()
            for p in parts:
                r = load_part(rid, p, scene=sc)
                st = r.stats()
                n, (lo, hi) = want[p]
                plo, phi = face_box(r, p)
                drift = float(max(np.abs(plo - lo).max(), np.abs(phi - hi).max()))
                hidden = all(o.hide_render for o in r.meshes() if not r.part_faces(o) or
                             any(q != p for q in r.part_faces(o)))
                K.check(f'{rid} / {p}: {st["triangles"]} triangles (ownership {n}), one part, in place, donor hidden',
                        st['triangles'] == n and r.parts() == [p] and drift < 1e-6 and hidden,
                        f'drift {drift:.1e} m')
                frame_camera(cam, [r.group], direction=(0.9, -1.5, 0.7), margin=1.25, visible_only=True)
                path = os.path.join(OUT, K.safe(rid) + '__' + re.sub(r'[^A-Za-z0-9._-]+', '_', p) + '.png')
                K.check(f'{rid} / {p}: still', K.still(sc, cam, 1, path))
                rec[f'{rid} / {p}'] = {'triangles': st['triangles'], 'png': path}
                r.dispose()
        except Exception:  # noqa: BLE001
            K.check(f'{rid}: load_part', False, traceback.format_exc().splitlines()[-1])
            traceback.print_exc()
    K.save_results('parts_render', {'parts': rec})


main()
