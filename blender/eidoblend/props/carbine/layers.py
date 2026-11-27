"""eidoblend.props.carbine.layers: the carbine's own data laid into its bake (plain Python: numpy and Pillow).

    python blender/tools/gpu_bake.py --bake DIR --name carbine --layers blender/eidoblend/props/carbine/layers.py \
        --layers-dir work/carbine/decals

gpu_bake.py calls layers(bake) once its maps are computed. From each texel's point and normal on the high (in the
carbine's millimetres) it writes:
    <name>_marks.png    the markings (decals.py's pictures) laid square through their rectangles, each on the faces
                        that look its way (the rail's four sides, the receiver's top, the lower's two sides)
    <name>_relief.png   where the grip's moulded relief cuts in (the chequered panels on both sides, the backstrap's
                        ribs 1.6 mm apart): the material puts what a texel averages away into roughness
and turns that relief's height (mm) into the normal map, blended over the baked normal (Reoriented Normal Mapping).
"""

from __future__ import annotations

import json
import math
import os

import numpy as np

MARK = {'rail_fore_end': [('rail_right', 1, -1), ('rail_left', 1, 1), ('rail_top', 2, 1), ('rail_bottom', 2, -1)],
        'upper_receiver': [('upper_top', 2, 1)], 'lower_receiver': [('lower_left', 1, 1), ('lower_right', 1, -1)]}
G_O, RK = np.array((61.9, -47.0)), math.radians(34.0)          # the grip's frame (grip.py: G_O, G_RAKE)
G_D, G_N = np.array((-math.sin(RK), -math.cos(RK))), np.array((math.cos(RK), -math.sin(RK)))


def sample(img, u, v):
    """bilinear sample of an image (rows from the top) at u, v in 0..1 (v up); outside: 0"""
    h_, w_ = img.shape
    x = u * w_ - 0.5
    y = (1.0 - v) * h_ - 0.5
    inside = (u >= 0) & (u <= 1) & (v >= 0) & (v <= 1)
    x0 = np.clip(np.floor(x).astype(int), 0, w_ - 2)
    y0 = np.clip(np.floor(y).astype(int), 0, h_ - 2)
    fx = np.clip(x - x0, 0, 1)
    fy = np.clip(y - y0, 0, 1)
    val = (img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x0 + 1] * fx * (1 - fy) + img[y0 + 1, x0] * (1 - fx) * fy + img[y0 + 1, x0 + 1] * fx * fy)
    return np.where(inside, val, 0.0)


def layers(bake):
    from PIL import Image
    d = bake.layers_dir
    if not d or not os.path.isfile(os.path.join(d, 'decals.json')):
        raise FileNotFoundError(f'carbine layers: no decals.json in {d!r} (draw them first: decals.py --out DIR)')
    DEC = json.load(open(os.path.join(d, 'decals.json'), encoding='utf-8'))

    def load_l(name):
        im = np.asarray(Image.open(os.path.join(d, name)))
        return im.astype(np.float32) / (255.0 if im.dtype == np.uint8 else 65535.0)

    N = bake.size * bake.size
    okh, tp, pos_mm, nos = bake.okh, bake.tp, bake.pos_mm, bake.nos
    mark = np.zeros(N, np.float32)
    for pname, decs in MARK.items():
        if pname not in bake.names:
            continue
        st = okh & (tp == bake.names.index(pname))
        P_ = pos_mm[st]
        for key, axn, sgn in decs:
            dd = DEC[key]
            img = load_l(dd['file'])
            u = (P_[:, 'xyz'.index(dd['u'][0])] - dd['u'][1]) / (dd['u'][2] - dd['u'][1])
            v = (P_[:, 'xyz'.index(dd['v'][0])] - dd['v'][1]) / (dd['v'][2] - dd['v'][1])
            g = np.clip((nos[st][:, axn] * sgn - 0.6) / 0.25, 0, 1)
            mark[st] = np.maximum(mark[st], sample(img, u, v) * g * g * (3 - 2 * g))
    relief = np.zeros(N, np.float32)
    if 'pistol_grip' in bake.names:
        gst = okh & (tp == bake.names.index('pistol_grip'))
        gp = DEC['grip_panel']
        pan_h, pan_m = load_l(gp['file']), load_l(gp['mask'])

        def grip_height(P_, n_):
            """the relief's height (mm, 0 = the surface, negative = cut): the chequering on both panels, the
            backstrap's ribs 1.6 mm apart (0.3 deep)"""
            u = (P_[:, 0] - gp['u'][1]) / (gp['u'][2] - gp['u'][1])
            v = (P_[:, 2] - gp['v'][1]) / (gp['v'][2] - gp['v'][1])
            side = np.clip((np.abs(n_[:, 1]) - 0.72) / 0.18, 0, 1)
            h = (sample(pan_h, u, v) - 1.0) * sample(pan_m, u, v) * side * gp['depth_mm']
            s = (P_[:, 0] - G_O[0]) * G_D[0] + (P_[:, 2] - G_O[1]) * G_D[1]
            backf = np.clip((-(n_[:, 0] * G_N[0] + n_[:, 2] * G_N[1]) - 0.55) / 0.25, 0, 1)
            run = np.clip((s - 34.0) / 6.0, 0, 1) * np.clip((104.0 - s) / 6.0, 0, 1)
            fr = np.mod(P_[:, 1] / 1.6, 1.0)
            tri_ = 1.0 - np.abs(2.0 * fr - 1.0)
            rib = (np.clip((tri_ - 0.15) / 0.45, 0, 1) - 1.0) * backf * run * 0.3
            return h + rib

        if gst.any():
            P_, n_, T_, B_ = pos_mm[gst], nos[gst], bake.tan[gst], bake.bit[gst]
            eps = 0.03
            h0 = grip_height(P_, n_)
            dh_t = (grip_height(P_ + T_ * eps, n_) - grip_height(P_ - T_ * eps, n_)) / (2 * eps)
            dh_b = (grip_height(P_ + B_ * eps, n_) - grip_height(P_ - B_ * eps, n_)) / (2 * eps)
            det = np.stack([-dh_t, -dh_b, np.ones_like(dh_t)], 1)
            det /= np.linalg.norm(det, axis=1, keepdims=True)
            base = bake.nts[gst]
            t_ = base + np.array((0.0, 0.0, 1.0))                  # Reoriented Normal Mapping
            u_ = det * np.array((-1.0, -1.0, 1.0))
            r_ = t_ * (np.sum(t_ * u_, 1) / t_[:, 2])[:, None] - u_
            nts = bake.nts.copy()
            nts[gst] = r_ / np.linalg.norm(r_, axis=1, keepdims=True)
            bake.nts = nts
            relief[gst] = np.clip(-h0 / 0.4, 0, 1)
            bake.log(f'grip relief: {gst.sum():,} texels, cut share {(h0 < -0.05).mean() * 100:.1f} %')
    bake.save(f'{bake.name}_marks.png', bake.pad(mark, 0.0))
    bake.save(f'{bake.name}_relief.png', bake.pad(relief, 0.0))
