"""The port's judge frames, developed (PORT_PLAN.md 8.2 row P18): views.mjs writes each view scene-linear, at k x the
review's 960 x 540; here each is averaged k x k (EEVEE's 16 samples a pixel, as a box) and taken through Blender's own
display transform, so a board shows the ground's difference and not the tone curve's.

    python eidoverse/terrain/tests/surface_look/develop.py --state <label> [--recipes a,b] [--force]
    (system Python: numpy and Pillow; no GPU)

Per view in tests/out/surface_look/states/<label>/<recipe>/:
    <view>.f16          -> <view>.png         through the review's display transform: the table blender_display.py
                                               measured from Blender (AgX, the look 'AgX - Medium High Contrast',
                                               exposure -0.5 EV, sRGB), trilinear in log2; 8-bit sRGB, what the
                                               surfacing judge's boards and measures read
                        -> <view>_agx3.png    the same frame through this edition's tone curve (three r184's
                                               agxToneMapping at the same exposure, then sRGB), for the record of what
                                               the edition's own frames look like
    <view>_layers.f16   -> <view>_layers.png  the layer map: averaged as premultiplied colour, straight alpha, the
                                               Standard view transform (sRGB), 8-bit RGBA (review_views.layer_scene's
                                               file, which surfacing_judge/layers.decode_layer_map reads)
Writes develop.json beside them (per view: the frame's size, k, its scene-linear percentiles, the layer map's terrain
share).
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, '..', 'out', 'surface_look'))
DISPLAY = os.path.join(OUT, 'display', 'blender_display.npz')

# three r184 src/nodes/display/ToneMappingFunctions.js (mat3 takes columns: these rows are its columns)
SRGB_TO_REC2020 = np.array([[0.6274, 0.0691, 0.0164], [0.3293, 0.9195, 0.0880], [0.0433, 0.0113, 0.8956]])
REC2020_TO_SRGB = np.array([[1.6605, -0.1246, -0.0182], [-0.5876, 1.1329, -0.1006], [-0.0728, -0.0083, 1.1187]])
AGX_INSET = np.array([[0.856627153315983, 0.137318972929847, 0.11189821299995],
                      [0.0951212405381588, 0.761241990602591, 0.0767994186031903],
                      [0.0482516061458583, 0.101439036467562, 0.811302368396859]])
AGX_OUTSET = np.array([[1.1271005818144368, -0.1413297634984383, -0.14132976349843826],
                       [-0.11060664309660323, 1.157823702216272, -0.11060664309660294],
                       [-0.016493938717834573, -0.016493938717834257, 1.2519364065950405]])
AGX_MIN_EV, AGX_MAX_EV = -12.47393, 4.026069


def srgb_oetf(x):
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(x, 1.0 / 2.4) - 0.055)


def three_agx(c, exposure):
    """three's agxToneMapping (a mat3 of columns c0..c2 times v is v @ [c0; c1; c2] for row vectors), then sRGB."""
    c = c * exposure
    c = c @ SRGB_TO_REC2020
    c = c @ AGX_INSET
    c = np.log2(np.maximum(c, 1e-10))
    c = np.clip((c - AGX_MIN_EV) / (AGX_MAX_EV - AGX_MIN_EV), 0.0, 1.0)
    x2 = c * c
    x4 = x2 * x2
    c = 15.5 * x4 * x2 - 40.14 * x4 * c + 31.96 * x4 - 6.868 * x2 * c + 0.4298 * x2 + 0.1191 * c - 0.00232
    c = c @ AGX_OUTSET
    c = np.power(np.maximum(c, 0.0), 2.2)
    c = c @ REC2020_TO_SRGB
    return srgb_oetf(np.clip(c, 0.0, 1.0))


class Display:
    """Blender's display transform from blender_display.py's table: scene-linear Rec.709 -> display sRGB 0..1."""

    def __init__(self, path=DISPLAY):
        d = np.load(path)
        self.lut = d['lut'].astype(np.float64)
        self.axis = d['axis']
        self.info = json.loads(str(d['info']))
        self.n = len(self.axis)
        self.lo, self.hi = float(np.log2(self.axis[1])), float(np.log2(self.axis[-1]))

    def index(self, v):
        """Fractional table index per value: 0 at black, linear up to 2^lo, then even in log2 up to 2^hi."""
        v = np.maximum(v, 0.0)
        a1 = self.axis[1]
        lin = v / a1
        logi = 1.0 + (np.log2(np.maximum(v, a1)) - self.lo) / (self.hi - self.lo) * (self.n - 2)
        return np.clip(np.where(v < a1, lin, logi), 0.0, self.n - 1.0)

    def __call__(self, rgb):
        sh = rgb.shape
        p = rgb.reshape(-1, 3)
        f = [self.index(p[:, c]) for c in range(3)]
        i0 = [np.minimum(np.floor(x).astype(np.int64), self.n - 2) for x in f]
        t = [x - i for x, i in zip(f, i0)]
        out = np.zeros((p.shape[0], 3))
        for dr in (0, 1):
            wr = t[0] if dr else 1.0 - t[0]
            for dg in (0, 1):
                wg = t[1] if dg else 1.0 - t[1]
                for db in (0, 1):
                    wb = t[2] if db else 1.0 - t[2]
                    out += (wr * wg * wb)[:, None] * self.lut[i0[0] + dr, i0[1] + dg, i0[2] + db]
        return np.clip(out, 0.0, 1.0).reshape(sh)


def read_f16(path):
    with open(path.replace('.f16', '.json'), encoding='utf-8') as f:
        meta = json.load(f)
    raw = np.fromfile(path, dtype=np.float16)
    w, h, row = int(meta['w']), int(meta['h']), int(meta['row'])
    a = raw.reshape(h, row)[:, :4 * w].reshape(h, w, 4).astype(np.float64)
    return a, meta


def box(a, k):
    if k <= 1:
        return a
    h, w = a.shape[0] // k, a.shape[1] // k
    return a[:h * k, :w * k].reshape(h, k, w, k, -1).mean(axis=(1, 3))


def to8(x):
    return (np.clip(x, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)


def develop_view(d, view, disp, force=False):
    from PIL import Image
    src = os.path.join(d, view + '.f16')
    png = os.path.join(d, view + '.png')
    info = {}
    if os.path.exists(src) and (force or not os.path.exists(png) or os.path.getmtime(png) < os.path.getmtime(src)):
        a, meta = read_f16(src)
        k = int(meta.get('k', 1))
        lin = box(a, k)[..., :3]
        lin = np.where(np.isfinite(lin), lin, 0.0)
        Image.fromarray(to8(disp(lin))).save(png)
        Image.fromarray(to8(three_agx(lin, 2.0 ** -0.5))).save(os.path.join(d, view + '_agx3.png'))
        lum = lin @ np.array([0.2126, 0.7152, 0.0722])
        info.update(size=[lin.shape[1], lin.shape[0]], k=k, linear_luma_p=[float(np.percentile(lum, q)) for q in (1, 50, 99, 99.9)],
                    linear_max=float(lin.max()))
    csrc = os.path.join(d, view + '_clay.f16')         # views.mjs --clay: the probe's grey clay frame
    cpng = os.path.join(d, view + '_clay.png')
    if os.path.exists(csrc) and (force or not os.path.exists(cpng) or os.path.getmtime(cpng) < os.path.getmtime(csrc)):
        a, meta = read_f16(csrc)
        lin = box(a, int(meta.get('k', 1)))[..., :3]
        lin = np.where(np.isfinite(lin), lin, 0.0)
        Image.fromarray(to8(disp(lin))).save(cpng)
        np.save(os.path.join(d, view + '_clay_luma.npy'), (lin @ np.array([0.2126, 0.7152, 0.0722])).astype(np.float32))
        info.update(clay=True)
    lsrc = os.path.join(d, view + '_layers.f16')
    lpng = os.path.join(d, view + '_layers.png')
    if os.path.exists(lsrc) and (force or not os.path.exists(lpng) or os.path.getmtime(lpng) < os.path.getmtime(lsrc)):
        a, meta = read_f16(lsrc)
        k = int(meta.get('k', 1))
        a = np.where(np.isfinite(a), a, 0.0)
        b = box(a, k)
        alpha = np.clip(b[..., 3], 0.0, 1.0)
        rgb = np.where(alpha[..., None] > 1e-4, b[..., :3] / np.maximum(alpha[..., None], 1e-4), 0.0)
        rgba = np.concatenate([srgb_oetf(rgb), alpha[..., None]], -1)
        Image.fromarray(to8(rgba), 'RGBA').save(lpng)
        info.update(layers_terrain_share=float((alpha >= 0.5).mean()))
    return info


def main(argv):
    def opt(k, d=None):
        return argv[argv.index(k) + 1] if k in argv else d
    state = opt('--state', 'port')
    only = set((opt('--recipes') or '').split(',')) - {''}
    root = os.path.join(OUT, 'states', state)
    disp = Display()
    print(f"[develop] {state}: Blender's display table {disp.info.get('view_transform')} / {disp.info.get('look')} at "
          f"{disp.info.get('exposure')} EV ({disp.n}^3, Blender {disp.info.get('blender')})")
    for recipe in sorted(os.listdir(root)) if os.path.isdir(root) else []:
        d = os.path.join(root, recipe)
        if not os.path.isdir(d) or (only and recipe not in only):
            continue
        views = sorted({f[:-4] for f in os.listdir(d) if f.endswith('.f16') and not f.endswith(('_layers.f16', '_clay.f16'))})
        res = {}
        jp = os.path.join(d, 'develop.json')
        if os.path.exists(jp):
            with open(jp, encoding='utf-8') as f:
                res = json.load(f)
        for v in views:
            info = develop_view(d, v, disp, force='--force' in argv)
            if info:
                res[v] = {**res.get(v, {}), **info}
                print(f'[develop] {recipe}/{v}: {json.dumps(info)}')
        with open(jp, 'w', encoding='utf-8') as f:
            json.dump(res, f, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
