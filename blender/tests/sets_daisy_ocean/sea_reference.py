"""An independent reference for the sea's fragment stage: sea.js's colorNode evaluated in numpy, written from sea.js
line by line (not from the port's _sea_nodes.py), for the cameras and uniforms test_sea_reference.py dumped beside its
renders, and compared with them (linear light, flat water: calm 0, relief 0). PASS when, on every view, the mean
radiance agrees within 4 %, the mean |difference| stays under 0.02 and the faces' warm lines overlap at IoU > 0.55
(what is left is the filtering: EEVEE's isotropic LOD and sample accumulation against a GPU's 8x anisotropic taps).

What is shared with the port: three's PCG hash (sea.pcg_hash, the formula checked against three r184 Hash.js), the
face atlas (faces_atlas.draw_face_atlas, checked against the canvas original by parity_atlas.py), util.build_mips
(byte parity with util.js) and the coast's signed distance (Coast.sdist_3, parity with land.js). Everything else is
this file's own: the camera rays, the plane hit, cellOf, the crest / reveal / wave terms, the Fresnel sky and moon,
the faces' light, the deep layer with its parallax, the haze, and the atlas sampled the way a GPU samples
texture().grad(): screen derivatives of the continuous cell coordinates (taken by finite differences across the
pixel, inside the pixel's own cell), anisotropic footprint (up to 8 taps along the major axis, LOD from the
major axis / taps), trilinear across the mip chain. The waterline foam (MaterialX noise) is masked out.

    python <worktree>/blender/tests/sets_daisy_ocean/sea_reference.py      (test_sea_reference.py runs it after its renders)
"""
import glob
import json
import math
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER_DIR = os.path.normpath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, BLENDER_DIR)
from eidoblend.sets.daisy.ocean.sea import pcg_hash  # noqa: E402
from eidoblend.sets.daisy.ocean.faces_atlas import draw_face_atlas  # noqa: E402
from eidoblend.sets.daisy.ocean.util import build_mips  # noqa: E402
from eidoblend.sets.daisy.ocean.land import make_coast  # noqa: E402

SRC = os.path.join(HERE, 'out', 'sea_reference')
G = 9.81
MAIN_T = 3.75
SWELLS = [[-0.40, 1.0, None, 0.30, 0.55, 0.0], [-0.05, 1.0, 9.2, 0.10, 0.45, 1.7],
          [-0.80, 1.0, 5.49, 0.055, 0.40, 4.2], [0.35, 1.0, 3.3, 0.030, 0.35, 2.9]]
RIPPLES = [[0.9, 1.0, 1.55, 0.012], [-0.6, 1.0, 1.02, 0.009], [0.2, -1.0, 0.71, 0.006],
           [-1.0, 0.3, 0.53, 0.005], [0.7, 0.4, 0.38, 0.0035], [-0.3, 0.9, 0.29, 0.0025]]
W0, HV, R0F = 1.7, 3.0, 3.0
N = 8
RADIUS = 1500.0
WAVES = []
for dx, dz, L, A, Q, ph in SWELLS:
    n = math.hypot(dx, dz)
    om = 2 * math.pi / MAIN_T if L is None else math.sqrt(G * 2 * math.pi / L)
    k = om * om / G if L is None else 2 * math.pi / L
    WAVES.append((dx / n, dz / n, k, om, ph))


def ss(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def step(edge, x):
    return (x >= edge).astype(np.float64)


def cell_coords(px, pz, Wl):
    DL = Wl / HV
    r2 = np.maximum(px * px + pz * pz, 0.25)
    r = np.sqrt(r2)
    vR = (np.log(r) - math.log(R0F)) / DL
    th = np.arctan2(px, -pz)
    return r, vR, th, DL


def cell_of(px, pz, Wl=W0, so=0):
    r, vR, th, DL = cell_coords(px, pz, Wl)
    row = np.floor(vR)
    rRow = np.exp((row + 0.5) * DL + math.log(R0F))
    off = pcg_hash(((row + (64 + so)) * 37.0).astype(np.float32)) * 9.0
    sC = th * rRow / Wl + off
    col = np.floor(sC)
    seed = ((col + (4096 + so)) * 131.0 + (row + 64) * 7919.0).astype(np.float32)
    h1, h2, h3, h4 = (pcg_hash(seed + np.float32(d)) for d in (0.0, 17.0, 41.0, 73.0))
    present = step(0.16, pcg_hash(seed + np.float32(97.0)))
    scl = h2 * 0.26 + 0.74
    tilt = (h3 - 0.5) * 0.4
    ct, st = np.cos(tilt), np.sin(tilt)
    lu = sC - np.floor(sC) - 0.5
    lv = vR - row - 0.5 - (h4 - 0.5) * (1 - scl) * 0.9
    x = (lu * ct - lv * st) / scl
    y = (lu * st + lv * ct) / scl
    thC = (col + 0.5 - off) * Wl / rRow
    pc = (np.sin(thC) * rRow, -np.cos(thC) * rRow)
    return dict(r=r, vR=vR, row=row, rRow=rRow, off=off, sC=sC, col=col, h1=h1, h2=h2, h3=h3, h4=h4, scl=scl, ct=ct,
                st=st, x=x, y=y, pc=pc, present=present, Wl=Wl)


def sc_in_cell(px, pz, c):
    """the continuous lateral / row coordinates at another point, inside cell c (its row's rRow and offset)"""
    r, vR, th, _DL = cell_coords(px, pz, c['Wl'])
    return th * c['rRow'] / c['Wl'] + c['off'], vR


class Atlas:
    def __init__(self):
        data = draw_face_atlas(n=N, cell=256, seed=11)               # row 0 = v 0 (bottom), as the JS packs it
        self.levels = [m['data'].astype(np.float32) / 255.0 for m in build_mips(data)]

    def bilinear(self, li, u, v):
        img = self.levels[li]
        h, w = img.shape[:2]
        x, y = u * w - 0.5, v * h - 0.5
        x0, y0 = np.floor(x), np.floor(y)
        fx, fy = (x - x0)[..., None], (y - y0)[..., None]
        x0, y0 = x0.astype(np.int64), y0.astype(np.int64)
        xa, xb = np.clip(x0, 0, w - 1), np.clip(x0 + 1, 0, w - 1)
        ya, yb = np.clip(y0, 0, h - 1), np.clip(y0 + 1, 0, h - 1)
        return ((img[ya, xa] * (1 - fx) + img[ya, xb] * fx) * (1 - fy) + (img[yb, xa] * (1 - fx) + img[yb, xb] * fx) * fy)

    def grad(self, u, v, gx, gy, max_aniso=8):
        """texture(atlas, uv).grad(gx, gy): anisotropic (EXT_texture_filter_anisotropic's rule), trilinear, clamp"""
        S = self.levels[0].shape[0]
        px, py = np.hypot(gx[0], gx[1]) * S, np.hypot(gy[0], gy[1]) * S
        pmax, pmin = np.maximum(px, py), np.maximum(np.minimum(px, py), 1e-12)
        taps = np.minimum(np.ceil(pmax / pmin), max_aniso)
        lod = np.clip(np.log2(np.maximum(pmax / taps, 1e-12)), 0.0, len(self.levels) - 1)
        mu = np.where(px >= py, gx[0], gy[0])
        mv = np.where(px >= py, gx[1], gy[1])
        l0 = np.floor(lod).astype(np.int64)
        f = (lod - l0)[..., None]
        out = np.zeros(u.shape + (4,))
        for k in range(max_aniso):
            wk = (k < taps).astype(np.float64)[..., None]
            o = (k + 0.5) / taps - 0.5
            uu, vv = u + mu * o, v + mv * o
            acc = np.zeros(u.shape + (4,))
            for li in range(len(self.levels)):
                m0, m1 = l0 == li, (l0 + 1) == li
                if not (m0.any() or m1.any()):
                    continue
                s = self.bilinear(li, uu, vv)
                acc += s * (m0[..., None] * (1 - f) + m1[..., None] * f)
            out += acc * wk
        return out / taps[..., None], lod


def tint_of(hue):
    gold, amber, rose, aqua = (np.array(c) for c in ((1.0, 0.62, 0.26), (1.0, 0.5, 0.2), (1.0, 0.46, 0.4), (0.3, 0.72, 0.95)))
    m = lambda a, b, t: a + (b - a) * t[..., None]  # noqa: E731
    return m(m(m(np.broadcast_to(gold, hue.shape + (3,)), amber, ss(0.35, 0.55, hue)), rose, ss(0.78, 0.86, hue)), aqua,
             ss(0.91, 0.96, hue))


def render_ref(meta, atlas, coast, sub=2):
    Wp, Hp = meta['res']
    M = np.array(meta['cam_matrix'])
    Lm = np.array(meta['layout_matrix'])
    Linv = np.linalg.inv(Lm)
    U = meta['uniforms']
    t, reveal, glow = U['t'], U['reveal'], U['glow']
    moonW, moonCol, moonI = np.array(U['moonW']), np.array(U['moonCol']), U['moonI']
    zen, hor, fog = np.array(U['zen']), np.array(U['hor']), U['fog']
    cam = M[:3, 3]
    th_y = math.tan(meta['angle_y'] / 2)

    def rays(ox, oy):
        jj, ii = np.meshgrid(np.arange(Wp) + ox, np.arange(Hp) + oy)
        d = np.stack([((jj / Wp) * 2 - 1) * th_y * Wp / Hp, (1 - (ii / Hp) * 2) * th_y, -np.ones_like(jj)], -1)
        d = d @ M[:3, :3].T
        return d / np.linalg.norm(d, axis=-1, keepdims=True)

    def hit(d):
        tt = -cam[2] / np.where(np.abs(d[..., 2]) > 1e-9, d[..., 2], -1e-9)
        P = cam + d * tt[..., None]
        loc = P @ Linv[:3, :3].T + Linv[:3, 3]                      # layout-local, Blender design axes
        return P, tt, loc[..., 0], -loc[..., 1]                     # three design (x, z)

    acc = np.zeros((Hp, Wp, 3))
    valid = np.ones((Hp, Wp), bool)
    lods = []
    for oy in [(k + 0.5) / sub for k in range(sub)]:
        for ox in [(k + 0.5) / sub for k in range(sub)]:
            d = rays(ox, oy)
            P, tt, px, pz = hit(d)
            _P1, _t1, px1, pz1 = hit(rays(ox + 1, oy))
            _P2, _t2, px2, pz2 = hit(rays(ox, oy + 1))
            shore = coast.sdist_3(px, pz)
            ok = (tt > 0) & (np.hypot(px, pz) < RADIUS * 0.98) & (shore >= 2.2)
            valid &= ok
            fdamp = ss(0.5, 6.0, shore)
            th = [(px * dx + pz * dz) * k - t * om + ph for dx, dz, k, om, ph in WAVES]
            s0, c0, s1 = np.sin(th[0]), np.cos(th[0]), np.sin(th[1])
            c = cell_of(px, pz)
            dist = np.linalg.norm(P - cam, axis=-1)
            ripK = ss(260.0, 25.0, dist)
            rx = np.zeros_like(px)
            rz = np.zeros_like(px)
            for dx, dz, lam, a in RIPPLES:
                n = math.hypot(dx, dz)
                k = 2 * math.pi / lam
                om = math.sqrt(G * k)
                cc = np.cos((px * dx / n + pz * dz / n) * k - t * om) * (a * k)
                rx, rz = rx + cc * dx / n, rz + cc * dz / n
            nL3 = np.stack([-rx * ripK, np.ones_like(px), -rz * ripK], -1)       # three local (swells flat: calm 0)
            nLb = np.stack([nL3[..., 0], -nL3[..., 2], nL3[..., 1]], -1)       # Blender local
            nW = nLb @ Lm[:3, :3].T
            nW /= np.linalg.norm(nW, axis=-1, keepdims=True)
            Vd = -d
            cosV = np.maximum((nW * Vd).sum(-1), 0.0)
            F = 0.02 + (1 - cosV) ** 5 * 0.98
            Rr = -Vd + 2 * (Vd * nW).sum(-1)[..., None] * nW
            ry = np.maximum(Rr[..., 2], 0.0)
            sky = hor + (zen - hor) * np.sqrt(ry)[..., None]
            md = np.maximum(Rr @ moonW, 0.0)
            moonGl = md ** 2600 * 2.4 + md ** 220 * 0.05 + md ** 16 * 0.012
            col = sky * F[..., None] + moonCol * (moonGl * moonI * (F * 0.6 + 0.4))[..., None]
            body = np.array((0.0016, 0.0048, 0.0085))                          # + moonCol max(disp.y, 0) 0.02: flat
            col = col + body * (1 - F)[..., None]
            # ---- the faces' light
            inside = step(np.maximum(np.abs(c['x']), np.abs(c['y'])), 0.5)
            inside = (np.maximum(np.abs(c['x']), np.abs(c['y'])) <= 0.5).astype(np.float64)
            kk = np.floor(c['h1'] * (N * N * 0.999))
            ay = np.floor(kk / N)
            ax = kk - ay * N
            cxr = np.clip(c['x'] + rx * ripK * 0.05 / c['scl'], -0.5, 0.5)
            cyr = np.clip(c['y'] + rz * ripK * 0.05 / c['scl'], -0.5, 0.5)
            u_, v_ = (ax + cxr + 0.5) / N, (ay + cyr + 0.5) / N
            sx1, vx1 = sc_in_cell(px1, pz1, c)
            sy1, vy1 = sc_in_cell(px2, pz2, c)
            dsx, dvx, dsy, dvy = sx1 - c['sC'], vx1 - c['vR'], sy1 - c['sC'], vy1 - c['vR']
            k_ = 1.0 / (c['scl'] * N)
            gx = ((dsx * c['ct'] - dvx * c['st']) * k_, (dsx * c['st'] + dvx * c['ct']) * k_)
            gy = ((dsy * c['ct'] - dvy * c['st']) * k_, (dsy * c['st'] + dvy * c['ct']) * k_)
            Atex, lod = atlas.grad(u_, v_, gx, gy)
            lods.append(lod[ok])
            rf = (RADIUS / R0F) ** reveal * R0F
            on = 1.0 if reveal >= 0.001 else 0.0
            revealK = lambda r: ss(rf, rf * 0.82, r) * on  # noqa: E731
            xw = (c['r'] - rf * 0.9) / (rf * 0.13 + 0.6)
            wave = np.exp(-xw * xw) * on * (1 - ss(0.93, 1.0, reveal))
            w0 = WAVES[0]
            emerge = ss(-0.15, 0.85, np.sin((c['pc'][0] * w0[0] + c['pc'][1] * w0[1]) * w0[2] - t * w0[3] + w0[4]
                                           + c['h4'] * 1.4 - 0.7))
            pix = ss(-0.35, 0.8, s0 * math.cos(0.35) - c0 * math.sin(0.35))
            near = pix * (s1 * 0.25 + 0.75)
            crest = (near + (emerge - near) * ss(45.0, 160.0, c['r'])) * c['present']
            em = crest * revealK(c['r']) * fdamp * inside
            lines = Atex[..., 0] + Atex[..., 1] * 0.45 + Atex[..., 2] * 0.05
            far = np.exp(c['r'] / -520.0) * 0.7 + 0.3
            kf = lines * em * glow * far * (1 - F * 0.6) * (wave * 1.6 + 1.0) * 0.62
            col = col + tint_of(c['h2']) * kf[..., None]
            col = col + np.array((1.0, 0.7, 0.36)) * (wave * fdamp * 0.035 * (1 - F * 0.5))[..., None]
            # ---- the deep
            VdLb = Vd @ Linv[:3, :3].T
            VdLb /= np.linalg.norm(VdLb, axis=-1, keepdims=True)
            vx, vy, vz = VdLb[..., 0], VdLb[..., 2], -VdLb[..., 1]              # three local

            def shift(px_, pz_, d_):
                vb = -d_ @ Linv[:3, :3].T
                vb /= np.linalg.norm(vb, axis=-1, keepdims=True)
                kk_ = 1.7 / np.maximum(vb[..., 2], 0.12)
                return px_ - vb[..., 0] * kk_, pz_ + vb[..., 1] * kk_
            pdx, pdz = shift(px, pz, d)
            cd = cell_of(pdx, pdz, W0 * 2.4, 509)
            q1 = shift(px1, pz1, rays(ox + 1, oy))
            q2 = shift(px2, pz2, rays(ox, oy + 1))
            sxd, vxd = sc_in_cell(q1[0], q1[1], cd)
            syd, vyd = sc_in_cell(q2[0], q2[1], cd)
            dsx, dvx, dsy, dvy = sxd - cd['sC'], vxd - cd['vR'], syd - cd['sC'], vyd - cd['vR']
            kd_ = 1.0 / (cd['scl'] * (N / 3.5))
            gxd = ((dsx * cd['ct'] - dvx * cd['st']) * kd_, (dsx * cd['st'] + dvx * cd['ct']) * kd_)
            gyd = ((dsy * cd['ct'] - dvy * cd['st']) * kd_, (dsy * cd['st'] + dvy * cd['ct']) * kd_)
            kkd = np.floor(cd['h1'] * (N * N * 0.999))
            ayd = np.floor(kkd / N)
            axd = kkd - ayd * N
            ud = (axd + np.clip(cd['x'], -0.5, 0.5) + 0.5) / N
            vdd = (ayd + np.clip(cd['y'], -0.5, 0.5) + 0.5) / N
            Dp, _lodd = atlas.grad(ud, vdd, gxd, gyd)
            insideD = (np.maximum(np.abs(cd['x']), np.abs(cd['y'])) <= 0.5) * cd['present']
            breathe = np.sin(t * 0.45 + cd['h4'] * 6.28) * 0.35 + 0.65
            deepI = (Dp[..., 1] * 0.8 + Dp[..., 2] * 0.3) * insideD * breathe * revealK(cd['r']) * fdamp * (1 - F) \
                * np.exp(cd['r'] / -160.0)
            col = col + np.array((0.16, 0.46, 0.6)) * (deepI * glow * 0.2)[..., None]
            _ = (vx, vy, vz)
            # ---- haze (porch / window: 0 at these u)
            fk = (1 - np.exp(-dist * fog)) * 0.92
            col = col + (hor * 1.05 - col) * fk[..., None]
            acc += col
    lod_all = np.concatenate(lods) if lods else np.zeros(1)
    return acc / (sub * sub), valid, lod_all


def srgb_to_linear(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def main():
    atlas = Atlas()
    coast = make_coast()
    rows = []
    for jp in sorted(glob.glob(os.path.join(SRC, 'blender_*.json'))):
        meta = json.load(open(jp))
        name = meta['name']
        png = jp[:-5] + '.png'
        if not os.path.exists(png):
            print(f'[sea_ref] {name}: no render')
            continue
        b = np.asarray(Image.open(png), np.float64)
        b = srgb_to_linear(b[..., :3] / (65535.0 if b.max() > 255 else 255.0))
        ref, valid, lods = render_ref(meta, atlas, coast)
        refc = np.clip(ref, 0, 1)
        m = valid & (b.max(-1) < 0.999) & (refc.max(-1) < 0.999)
        d = np.abs(refc - b)[m]
        lum_r, lum_b = refc[m].mean(), b[m].mean()
        # the faces' light alone: pixels where the reference is warm (faces) vs where it is water
        warm = m & (refc[..., 0] > refc[..., 2] * 1.25) & (refc[..., 0] > 0.02)
        wb = m & (b[..., 0] > b[..., 2] * 1.25) & (b[..., 0] > 0.02)
        iou = (warm & wb).sum() / max(1, (warm | wb).sum())
        row = {'name': name, 'u': meta['u'], 'pixels': int(m.sum()), 'mean_ref': float(lum_r), 'mean_blender': float(lum_b),
               'mean_abs_diff': float(d.mean()), 'p95_abs_diff': float(np.percentile(d, 95)),
               'warm_px_ref': int(warm.sum()), 'warm_px_blender': int(wb.sum()), 'warm_iou': float(iou),
               'ref_lod_median': float(np.median(lods)), 'ref_lod_p90': float(np.percentile(lods, 90))}
        rows.append(row)
        print(f'[sea_ref] {name}: ' + ', '.join(f'{k} {v:.4f}' if isinstance(v, float) else f'{k} {v}' for k, v in row.items()),
              flush=True)
        # side by side: reference | Blender | |diff| x 8, all at +2 stops for the eye
        vis = lambda x: (linear_to_srgb(np.clip(x * 4.0, 0, 1)) * 255).astype(np.uint8)  # noqa: E731
        dv = (np.clip(np.abs(refc - b).max(-1) * 8.0 * 4.0, 0, 1) * 255).astype(np.uint8)
        dv[~valid] = 40
        side = np.concatenate([vis(refc), vis(b), np.repeat(dv[..., None], 3, -1)], axis=1)
        Image.fromarray(side).save(os.path.join(SRC, f'compare_{name}_ref_blender_diff.png'))
    checks = []
    for r in rows:
        ok = (abs(r['mean_blender'] - r['mean_ref']) <= 0.04 * r['mean_ref'] and r['mean_abs_diff'] < 0.02
              and r['warm_iou'] > 0.55)
        checks.append({'check': f"{r['name']}: the Blender sea = sea.js's fragment stage in numpy", 'pass': bool(ok),
                       'detail': f"mean {r['mean_blender']:.4f} vs {r['mean_ref']:.4f}, |diff| {r['mean_abs_diff']:.4f}, "
                                 f"faces' lines IoU {r['warm_iou']:.2f}"})
        print(f"[sea_ref] {'PASS' if ok else 'FAIL'} {checks[-1]['check']} {checks[-1]['detail']}", flush=True)
    n = sum(c['pass'] for c in checks)
    print(f'[sea_ref] {n}/{len(checks)} checks pass', flush=True)
    with open(os.path.join(SRC, 'compare_sea_ref.json'), 'w') as fh:
        json.dump({'rows': rows, 'checks': checks}, fh, indent=1)
    return n == len(checks) and len(checks) > 0


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
