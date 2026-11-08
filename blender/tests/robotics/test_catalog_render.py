"""Every catalog entry of the modular kit, rendered in the kit's own studio (studio.py: studio.js's background, room
environment, hemisphere, sun and grid), one still each, framed by frame_camera as the inspector frames a model, with
the textures, the recolour and the shared maps. Checks per model: it loads, it has triangles and parts, its recolour
rebuilt every recolourable material, its stats match the catalog's triangle count, and the still was written.

    out/catalog/<id>.png          one still per entry (320 x 240 by default)
    out/catalog_render.json

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/robotics/test_catalog_render.py [-- ids... | --res 480x360]
Then the contact sheet (system Python): python blender/tests/robotics/contact_sheet.py out/catalog out/catalog_sheet.png
"""

import os
import sys
import traceback

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _rk as K  # noqa: E402

import bpy  # noqa: E402

from eidoblend.characters.robotics import catalog, frame_camera, make_robot, studio  # noqa: E402
from eidoblend.characters.robotics.studio import make_camera  # noqa: E402

ARGS = K.argv()
RES = (320, 240)
if '--res' in ARGS:
    w, h = ARGS[ARGS.index('--res') + 1].split('x')
    RES = (int(w), int(h))
    del ARGS[ARGS.index('--res'):ARGS.index('--res') + 2]
SAMPLES = 12
ONLY = [a for a in ARGS if not a.startswith('--')]
OUT = os.path.join(K.OUT, 'catalog')
os.makedirs(OUT, exist_ok=True)


def main():
    sc = K.clean_scene()
    K.probe_render(sc, RES, SAMPLES)
    studio(sc)
    cam = make_camera(35, 'catalog camera', sc)
    sc.camera = cam
    cat = catalog()
    rec = {}
    for rid, entry in cat['models'].items():
        if ONLY and rid not in ONLY:
            continue
        try:
            r = make_robot(rid, scene=sc)
            st = r.stats()
            recolourable = sum(1 for m in r.materials.materials if m.get('eidoverse_recolor') is not None)
            K.check(f'{rid}: loads with {st["triangles"]} triangles, {st["parts"]} parts',
                    st['triangles'] > 0 and st['parts'] > 0 and st['triangles'] == entry['triangles'],
                    f"catalog {entry['triangles']}")
            K.check(f'{rid}: recolour on every recolourable material', r.recoloured == recolourable,
                    f'{r.recoloured}/{recolourable}')
            frame_camera(cam, [r.group], margin=1.12)
            p = os.path.join(OUT, K.safe(rid) + '.png')
            ok = K.still(sc, cam, 1, p)
            K.check(f'{rid}: still written', ok)
            rec[rid] = {'stats': st, 'png': p, 'label': entry.get('label'), 'clips': r.clips}
            r.dispose()
        except Exception:  # noqa: BLE001
            K.check(f'{rid}: renders', False, traceback.format_exc().splitlines()[-1])
            traceback.print_exc()
    K.save_results('catalog_render' + ('_subset' if ONLY else ''), {'models': rec})


main()
