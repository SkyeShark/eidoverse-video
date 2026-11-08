"""tests/look/test_probe_modes.py: probe stills rendered three ways must agree on a keyed scene, and EEVEE must keep no
history between final renders (so a jumped-to still is the film's frame).

On the meadow test's blend (run test_meadow_camera.py --stage build first): one time rendered by jump, by preroll (1 s
of frames evaluated first) and by replay (every frame from the start); then the same frame rendered alone and right
after the frame before it. The differences are measured (max / mean per channel, and a windowed SSIM on luma).
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh blender/tests/look/test_probe_modes.py
"""
import os
import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixtures as FX                                       # noqa: E402

from eidoblend.look import frame_stats as FS                 # noqa: E402
from eidoblend.look import probe as P                        # noqa: E402
from eidoblend.look import render_settings as RS             # noqa: E402

OUT = os.path.join(FX.OUT, 'probe_modes')
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=os.path.join(FX.OUT, 'meadow', 'meadow_camera.blend'), load_ui=False)
sc = bpy.context.scene
RS.apply_auto_enhance(sc, 'probe', exposure=0.25)
T = 2.5


def ssim(a, b):
    """Mean SSIM of luma over 8 x 8 windows (no SciPy in Blender: box statistics from integral images)."""
    x = FS.luma(a).astype(np.float64)
    y = FS.luma(b).astype(np.float64)
    k = 8

    def box(z):
        ii = np.pad(z.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
        return (ii[k:, k:] - ii[:-k, k:] - ii[k:, :-k] + ii[:-k, :-k]) / (k * k)
    mx, my = box(x), box(y)
    vx, vy, cxy = box(x * x) - mx * mx, box(y * y) - my * my, box(x * y) - mx * my
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    s = ((2 * mx * my + c1) * (2 * cxy + c2)) / ((mx * mx + my * my + c1) * (vx + vy + c2))
    return float(s.mean())


def diff(pa, pb):
    a, b = FS.read_rgb(pa), FS.read_rgb(pb)
    d = np.abs(a.astype(np.int16) - b.astype(np.int16))
    return {'max': int(d.max()), 'mean': round(float(d.mean()), 4), 'ssim': round(ssim(a, b), 5)}


rows = {}
for mode in ('jump', 'preroll', 'replay'):
    r = P.render_stills(sc, at=[T], out_dir=OUT, name=f'm_{mode}', mode=mode, preroll_s=1.0, report=False)[0]
    rows[mode] = r['path']
res = {'jump_vs_preroll': diff(rows['jump'], rows['preroll']), 'jump_vs_replay': diff(rows['jump'], rows['replay'])}
f = rows and P.C.frame_at(sc, T)
P.render_still(sc, os.path.join(OUT, 'alone.png'), f, 'jump')
P.render_still(sc, os.path.join(OUT, 'prev.png'), f - 1, 'jump')
P.render_still(sc, os.path.join(OUT, 'after_prev.png'), f, 'jump')
res['alone_vs_after_prev'] = diff(os.path.join(OUT, 'alone.png'), os.path.join(OUT, 'after_prev.png'))
# a still twice in a row: the floor of the comparison (EEVEE's own run-to-run noise, if any)
P.render_still(sc, os.path.join(OUT, 'again.png'), f, 'jump')
res['after_prev_vs_again'] = diff(os.path.join(OUT, 'after_prev.png'), os.path.join(OUT, 'again.png'))
for k, v in res.items():
    print(f'[probe-modes] {k}: {v}', flush=True)
ok = all(v['ssim'] > 0.995 for v in res.values())
print(f"[probe-modes] {'PASS' if ok else 'FAIL'}: jump, preroll and replay agree; a still rendered alone is the "
      f"still rendered after its previous frame" if ok else '[probe-modes] FAIL', flush=True)
