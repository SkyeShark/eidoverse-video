"""The three robotics examples (eidoverse/examples/robotics/{assembly,mantis,motion}.scene.js), built by
examples.EXAMPLES at a probe size and rendered at three times each, with the scene scripts' own look
(_no_auto_enhance: no runner stages; EEVEE's ray tracing and fast GI stay on, as the harness leaves them). The mantis
example is
also saved as a .blend, reopened, and one frame rendered again from the file alone: it must match the frame rendered
before saving (the keyed-data contract: a saved file plays and renders any frame on its own).

    out/examples/<name>_t<seconds>.png      640 x 360
    out/examples/mantis.blend               (deleted after the check unless --keep)
    out/examples_render.json

    bash run_blender.sh blender/tests/robotics/test_examples_render.py
    # a GPU job; on a shared machine queue it with EIDO_GPU_WRAP (blender/tests/_where.py)
"""

import os
import sys
import traceback

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _rk as K  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402

from eidoblend.characters.robotics.examples import EXAMPLES  # noqa: E402

OUT = os.path.join(K.OUT, 'examples')
os.makedirs(OUT, exist_ok=True)
TIMES = {'assembly': (1.0, 4.5, 9.0), 'mantis': (0.0, 6.0, 13.0), 'motion': (1.0, 5.5, 11.0)}
KEEP = '--keep' in K.argv()


def look(sc):
    K.probe_render(sc, (640, 360), 16)               # ray tracing and fast GI on: _no_auto_enhance leaves them


def png(path):
    im = bpy.data.images.load(path, check_existing=False)
    px = np.empty(im.size[0] * im.size[1] * 4, np.float32)
    im.pixels.foreach_get(px)
    bpy.data.images.remove(im)
    return px


def main():
    rec = {}
    for name, builder in EXAMPLES.items():
        try:
            sc = K.clean_scene()
            sc.frame_start = 1
            r = builder(sc, width=640, height=360)
            look(sc)
            n_keyed = sum(1 for o in sc.objects if o.animation_data and o.animation_data.action)
            K.check(f'{name}: built, {len(r["robots"])} robots, {n_keyed} keyed objects, frames '
                    f'{sc.frame_start}..{sc.frame_end} at {sc.render.fps} fps', n_keyed > 0)
            shots = []
            for t in TIMES[name]:
                f = sc.frame_start + int(round(t * sc.render.fps))
                p = os.path.join(OUT, f'{name}_t{t:g}.png')
                K.check(f'{name} t={t:g}: still', K.still(sc, sc.camera, f, p))
                shots.append(p)
            rec[name] = {'shots': shots, 'keyed_objects': n_keyed}
            if name == 'mantis':
                blend = os.path.join(OUT, 'mantis.blend')
                bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)
                bpy.ops.wm.open_mainfile(filepath=blend)
                sc = bpy.context.scene
                look(sc)
                t = TIMES[name][1]
                f = sc.frame_start + int(round(t * sc.render.fps))
                p2 = os.path.join(OUT, f'mantis_t{t:g}_reopened.png')
                K.still(sc, sc.camera, f, p2)
                if not K.NO_RENDER:
                    a, b = png(shots[1]), png(p2)
                    d = float(np.abs(a - b).mean())
                    K.check('mantis: the saved file renders the same frame on its own (mean |diff| per channel)',
                            d < 0.01, f'{d:.4f}')
                    rec[name]['reopened_mean_abs_diff'] = d
                if not KEEP:
                    os.remove(blend)
                    if os.path.exists(blend + '1'):
                        os.remove(blend + '1')
        except Exception:  # noqa: BLE001
            K.check(f'{name}', False, traceback.format_exc().splitlines()[-1])
            traceback.print_exc()
    K.save_results('examples_render', {'examples': rec})


main()
