"""tests/look/test_debug_passes.py: lighting.debug_passes writes the light passes (rt_lighting's debug views) through a
compositor File Output node into one multilayer EXR, and the picture itself still renders. On the corner room (run
test_corner_room.py --stage build first); the passes are read back with OpenImageIO and a few are saved as PNGs to
look at (diffuse light, specular light, shadow, AO, normal).
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh blender/tests/look/test_debug_passes.py
"""
import glob
import os
import sys

import bpy
import numpy as np
import OpenImageIO as oiio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixtures as FX                                       # noqa: E402

from eidoblend.look import frame_stats as FS                 # noqa: E402
from eidoblend.look import lighting as L                     # noqa: E402
from eidoblend.look import probe as P                        # noqa: E402
from eidoblend.look import render_settings as RS             # noqa: E402

OUT = os.path.join(FX.OUT, 'passes')
os.makedirs(OUT, exist_ok=True)
for f in glob.glob(os.path.join(OUT, 'passes_*')):
    os.remove(f)
bpy.ops.wm.open_mainfile(filepath=os.path.join(FX.OUT, 'corner', 'corner_room.blend'), load_ui=False)
sc = bpy.context.scene
RS.apply_auto_enhance(sc, 'probe', exposure=0.5)
L.debug_passes(sc, OUT, passes=('diffuse_light', 'specular_light', 'shadow', 'ao', 'normal', 'z'), name='passes')
P.render_still(sc, os.path.join(OUT, 'beauty.png'), 12)
exr = sorted(glob.glob(os.path.join(OUT, 'passes_*.exr')))
LAYERS = {}
for e in exr:
    buf = oiio.ImageBuf(e)
    names = list(buf.spec().channelnames)
    print(f'[passes] {os.path.basename(e)}: channels {names}', flush=True)
    px = np.asarray(buf.get_pixels(oiio.FLOAT))
    for i, n in enumerate(names):
        LAYERS.setdefault(n.split('.')[0], []).append(px[..., i])


def save(prefix, name, scale=1.0, gamma=True):
    if prefix not in LAYERS:
        print(f'[passes] no {prefix}', flush=True)
        return None
    raw = np.stack(LAYERS[prefix][:3], axis=-1)
    a = np.repeat(raw, 3, axis=2) if raw.shape[2] == 1 else raw
    if prefix == 'Normal':                      # world normals -1..1 -> 0..1 for looking at
        a = a * 0.5 + 0.5
        scale, gamma = 1.0, False
    a = np.clip(a * scale, 0, 1)
    if gamma:
        a = a ** (1 / 2.2)
    p = os.path.join(OUT, f'{name}.png')
    FS.write_rgb(p, (a * 255).astype(np.uint8))
    print(f"[passes] {prefix}: min {float(raw.min()):.4f} max {float(raw.max()):.4f} -> {p}", flush=True)
    return p


got = [save(n, n.lower().replace(' ', '_'), s) for n, s in
       (('Diffuse Direct', 2.0), ('Glossy Direct', 2.0), ('Shadow', 1.0), ('Ambient Occlusion', 1.0), ('Normal', 0.5))]
paths = [os.path.join(OUT, 'beauty.png')] + [g for g in got if g]
FS.sheet(paths, os.path.join(OUT, 'passes_sheet.jpg'), cols=4, tile=400,
         labels=['beauty'] + [os.path.basename(p)[:-4] for p in paths[1:]])
print('[passes] done', flush=True)
