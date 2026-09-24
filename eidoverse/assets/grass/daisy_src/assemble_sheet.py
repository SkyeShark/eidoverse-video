# assemble_sheet.py — the Blender region renders -> the daisy_ map set + fit.
#
#   python eidoverse/assets/grass/daisy_src/assemble_sheet.py work/daisy_sheet/renders work/daisy_sheet/sheet [--install eidoverse/assets/grass]
#
# Per region: un-premultiply the emission passes, bake AO into albedo, convert
# world normals to TANGENT space (flat cards: identity; the domed disc and the
# involucre cup: per-pixel frame of the low-poly surface the gen builds, with
# u along s1 and v along s2 of the head frame), calibrate translucency into the
# engine's register, 2x box downsample, edge-pad colour under empty alpha (mips
# never pull background), then measure the alpha envelope of every card window
# into daisy_fit.json (the overdraw pull-in law: cards fitted to the art).
import sys, os, json, math
import numpy as np
from PIL import Image
from scipy import ndimage

R, OUT = sys.argv[1], sys.argv[2]
INSTALL = sys.argv[sys.argv.index('--install') + 1] if '--install' in sys.argv else None
os.makedirs(OUT, exist_ok=True)
SS = 2
SIZE = 1024

LAYOUT = {
    'disc':   (5, 605, 419, 1019),
    'petals': (428, 605, 1020, 1019),
    'basalA': (5, 418, 640, 596),
    'basalB': (5, 236, 640, 414),
    'stemA':  (5, 124, 640, 230),
    'stemB':  (5, 12, 640, 118),
    'invol':  (648, 216, 1016, 584),
    'stalk':  (648, 12, 1016, 108),
}
# physical calibration shared with daisy_art.py / vegetation_daisy_gen.js
RD, RF, DOME_H = 9.0, 9.0 * 1.06, 2.2
R_INV = 9.4
AO_K = {'disc': 0.7, 'petals': 0.35, 'basalA': 0.5, 'basalB': 0.5, 'stemA': 0.5, 'stemB': 0.5,
        'invol': 0.7, 'stalk': 0.45}
# translucency register (decoded LINEAR value = dat.G * k): petals glow, leaves
# half, bracts/stalk/disc barely — neutral grey (the engine reads .r only)
TR_K = {'disc': 0.15, 'petals': 0.20, 'basalA': 0.10, 'basalB': 0.10, 'stemA': 0.10, 'stemB': 0.10,
        'invol': 0.12, 'stalk': 0.12}

def dome_z(rho):
    rho = np.asarray(rho, dtype=np.float64)
    r2 = np.clip(rho, 0, 1.0) ** 2
    z = DOME_H * (1 - r2) ** 0.85 - 0.25 * np.exp(-(rho / 0.12) ** 2)
    return np.where(rho > 1.0, -3.0 * (rho - 1.0), z)

def cup_z(r):
    return -0.8 - 4.6 * np.clip(1 - (np.asarray(r) / 8.7) ** 2, 0, 1) ** 1.35

def lin2srgb(x):
    x = np.clip(x, 0, 1)
    return np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(x, 1 / 2.4) - 0.055)

def load(key, mode):
    return np.load(os.path.join(R, f'{key}_{mode}.npy')).astype(np.float64)

def down2(x):
    h, w = x.shape[:2]
    return x.reshape(h // 2, 2, w // 2, 2, -1).mean((1, 3))

def tangent_frame_surface(key, h, w):
    """per-pixel (T, B, N) of the low-poly surface for disc / invol, in the
    render's frame (x = u right, y = v up, z toward camera)"""
    ys, xs = np.mgrid[0:h, 0:w]
    if key == 'disc':
        half = RF
        px = (xs + 0.5) / w * 2 * half - half
        py = (ys + 0.5) / h * 2 * half - half
        r = np.hypot(px, py) + 1e-9
        e = 1e-3
        dzdr = (dome_z(r / RD + e) - dome_z(np.maximum(r / RD - e, 0))) / (2 * e * RD)
        dzdr = np.where(r / RD > 1.0, -0.8, dzdr)     # rim ring rolls off (LP rim ring)
    else:
        half = R_INV
        px = (xs + 0.5) / w * 2 * half - half
        py = (ys + 0.5) / h * 2 * half - half
        r = np.hypot(px, py) + 1e-9
        e = 1e-3
        # mirrored cup (outer surface toward the camera): z' = -cup_z(r)
        dzdr = -(cup_z(r + e) - cup_z(np.maximum(r - e, 0))) / (2 * e)
    dzdx, dzdy = dzdr * px / r, dzdr * py / r
    T = np.stack([np.ones_like(dzdx), np.zeros_like(dzdx), dzdx], -1)
    B = np.stack([np.zeros_like(dzdy), np.ones_like(dzdy), dzdy], -1)
    N = np.cross(T, B)
    N /= np.linalg.norm(N, axis=-1, keepdims=True)
    T -= N * (T * N).sum(-1, keepdims=True); T /= np.linalg.norm(T, axis=-1, keepdims=True)
    B = np.cross(N, T)
    return T, B, N

def region(key):
    col, dat, nrm, ao = (load(key, m) for m in ('col', 'dat', 'nrm', 'ao'))
    a = col[..., 3:4]
    un = lambda x: np.where(a > 1e-5, x[..., :3] / np.maximum(a, 1e-5), 0.0)
    alb, d, n, occ = un(col), un(dat), un(nrm) * 2 - 1, un(ao)[..., :1]
    n /= np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-6)
    h, w = a.shape[:2]
    if key in ('disc', 'invol'):
        T, B, N = tangent_frame_surface(key, h, w)
        n = np.stack([(n * T).sum(-1), (n * B).sum(-1), (n * N).sum(-1)], -1)
        n[..., 2] = np.maximum(n[..., 2], 0.05)
        n /= np.linalg.norm(n, axis=-1, keepdims=True)
    k = AO_K[key]
    albedo = alb * (1 - k * (1 - occ))
    rough = d[..., 0:1]
    transl = d[..., 1:2] * TR_K[key]
    # premultiply, downsample, un-premultiply
    pack = np.concatenate([albedo * a, n * a, rough * a, transl * a, a], -1)
    pk = down2(pack)
    A = pk[..., -1:]
    safe = np.maximum(A, 1e-5)
    out = {
        'alb': np.where(A > 1e-5, pk[..., 0:3] / safe, 0),
        'nrm': np.where(A > 1e-5, pk[..., 3:6] / safe, np.array([0, 0, 1.0])),
        'rough': np.where(A > 1e-5, pk[..., 6:7] / safe, 0.6),
        'transl': np.where(A > 1e-5, pk[..., 7:8] / safe, 0),
        'a': A,
    }
    out['nrm'] /= np.maximum(np.linalg.norm(out['nrm'], axis=-1, keepdims=True), 1e-6)
    # solid regions: the lathe / tube samples inside the circle or band only
    hh, ww = A.shape[:2]
    out['af'] = out['a'].copy()                  # the alpha that ships
    if key in ('disc', 'invol'):
        ys, xs = np.mgrid[0:hh, 0:ww]
        rr = (np.hypot(xs + 0.5 - ww / 2, ys + 0.5 - hh / 2) / (ww / 2))[..., None]
        out['af'] = np.where(rr <= 1.0, 1.0, 0.0)
    if key == 'stalk':
        out['af'] = np.ones_like(A)
    return out

sheet = {
    'alb': np.zeros((SIZE, SIZE, 3)), 'nrm': np.tile(np.array([0, 0, 1.0]), (SIZE, SIZE, 1)),
    'rough': np.full((SIZE, SIZE, 1), 0.6), 'transl': np.zeros((SIZE, SIZE, 1)), 'a': np.zeros((SIZE, SIZE, 1)),
    'af': np.zeros((SIZE, SIZE, 1)),
}
for key, (x0, y0, x1, y1) in LAYOUT.items():
    o = region(key)
    assert o['a'].shape[:2] == (y1 - y0, x1 - x0), (key, o['a'].shape)
    for ch in sheet:
        sheet[ch][y0:y1, x0:x1] = o[ch]
    print(f'[sheet] {key}: opaque {float((o["a"] > 0.5).mean()):.2f}')

# ── far-LOD impostor: the whole head seen from the front, composed from the
# sheet's OWN ray cells + disc (so near and far read as the same flower).
# Built at 4x and box-downsampled into a 72-px tile that REPLACES ray cell 7
# (row 0, col 7): far cards sample tiny mips, and in the ray block every
# neighbour is white ray art — the mips average to the flower's own colour
# (placed between green regions, the far field came out green).
IMP = (947, 739, 1019, 811)          # top of cell 7: rays above and beside, leaves far below
def compose_impostor():
    S = 288
    c = S / 2
    tipR, discR = 0.49 * S, 0.40 * 0.49 * S           # head radius, disc radius (px): disc ~0.4 of the head
    baseR = 0.8 * discR
    yy, xx = np.mgrid[0:S, 0:S]
    dx, dy = xx + 0.5 - c, yy + 0.5 - c
    out = np.zeros((S, S, 6))                         # rgb, rough, transl (straight), alpha
    rng = np.random.default_rng(5)
    px0, py0 = LAYOUT['petals'][:2]
    nP = 24
    for k in range(nP):
        th = 2 * np.pi * k / nP + rng.normal(0, 0.04)
        cell = int(rng.integers(0, 16)); cx, cy = cell % 8, cell // 8
        x0, y0 = px0 + 74 * cx, py0 + 207 * cy
        ca = sheet['a'][y0:y0 + 207, x0:x0 + 74, 0]
        rows = np.nonzero((ca > 0.5).any(axis=1))[0]
        vb, vt = rows.min(), rows.max() + 1
        L = (tipR - baseR) * rng.uniform(0.9, 1.05)
        scale = L / (vt - vb)                         # impostor px per cell px
        along = dx * np.cos(th) + dy * np.sin(th) - baseR
        across = -dx * np.sin(th) + dy * np.cos(th)
        v = vb + along / scale
        u = 37 + across / scale
        ok = (v >= 0) & (v < 206) & (u >= 0) & (u < 73)
        coords = [np.clip(v, 0, 206), np.clip(u, 0, 73)]
        a = ndimage.map_coordinates(ca, coords, order=1) * ok
        layer = [ndimage.map_coordinates(sheet['alb'][y0:y0 + 207, x0:x0 + 74, ch], coords, order=1) for ch in range(3)]
        layer.append(ndimage.map_coordinates(sheet['rough'][y0:y0 + 207, x0:x0 + 74, 0], coords, order=1))
        layer.append(ndimage.map_coordinates(sheet['transl'][y0:y0 + 207, x0:x0 + 74, 0], coords, order=1))
        for ch in range(5):
            out[..., ch] = layer[ch] * a + out[..., ch] * (1 - a)
        out[..., 5] = a + out[..., 5] * (1 - a)
    # the disc over the ray bases (the gen's planar mapping, rim at 0.965 R)
    r = np.hypot(dx, dy)
    dcx, dcy, dR = 212, 812, 207
    sx = dcx + dx / discR * dR * 0.965 - 0.5
    sy = dcy + dy / discR * dR * 0.965 - 0.5
    coords = [np.clip(sy, 0, SIZE - 1), np.clip(sx, 0, SIZE - 1)]
    a = np.clip((discR * 1.02 - r) / 1.5, 0, 1)
    for ch in range(3):
        out[..., ch] = ndimage.map_coordinates(sheet['alb'][..., ch], coords, order=1) * a + out[..., ch] * (1 - a)
    out[..., 3] = 0.45 * a + out[..., 3] * (1 - a)
    out[..., 4] = 0.02 * a + out[..., 4] * (1 - a)
    out[..., 5] = a + out[..., 5] * (1 - a)
    # 4x box downsample (premultiplied), un-premultiply
    pm = np.concatenate([out[..., :5] * out[..., 5:6], out[..., 5:6]], -1)
    d = pm.reshape(72, 4, 72, 4, 6).mean((1, 3))
    A = d[..., 5:6]
    rgb = np.where(A > 1e-5, d[..., :5] / np.maximum(A, 1e-5), 0)
    return rgb, A

imp_rgb, imp_a = compose_impostor()
# clear ray cell 7 (its art moves out of use) — padding refills it white
sheet['a'][605:812, 946:1020] = 0
sheet['af'][605:812, 946:1020] = 0
ix0, iy0, ix1, iy1 = IMP
sheet['alb'][iy0:iy1, ix0:ix1] = imp_rgb[..., :3]
sheet['rough'][iy0:iy1, ix0:ix1] = imp_rgb[..., 3:4]
sheet['transl'][iy0:iy1, ix0:ix1] = imp_rgb[..., 4:5]
sheet['nrm'][iy0:iy1, ix0:ix1] = np.array([0, 0, 1.0])
sheet['a'][iy0:iy1, ix0:ix1] = imp_a
sheet['af'][iy0:iy1, ix0:ix1] = imp_a
print(f'[sheet] impostor: opaque {float((imp_a > 0.5).mean()):.2f}')

# edge padding: every non-opaque texel takes the colour of its nearest
# opaque texel (alpha untouched) — generated sheets otherwise mip toward black
opaque = sheet['a'][..., 0] > 0.5
dist, (iy, ix) = ndimage.distance_transform_edt(~opaque, return_indices=True)
for ch in ('alb', 'nrm', 'rough', 'transl'):
    filled = sheet[ch][iy, ix]
    if ch == 'nrm':
        # padded normals relax to flat within a few texels — edge roll-offs
        # must not smear tilted normals into what the mips average in
        f = np.clip(dist / 4.0, 0, 1)[..., None]
        filled = filled * (1 - f) + np.array([0, 0, 1.0]) * f
    m = (~opaque)[..., None]
    # partially covered edge texels keep a blend of their own colour
    wgt = np.clip(sheet['a'] / 0.5, 0, 1)
    sheet[ch] = np.where(m, filled * (1 - wgt) + sheet[ch] * wgt, sheet[ch])
sheet['nrm'] /= np.maximum(np.linalg.norm(sheet['nrm'], axis=-1, keepdims=True), 1e-6)
sheet['a'] = sheet['af']

def save(name, rgb, alpha=None):
    img = np.clip(rgb, 0, 1)
    if alpha is None:
        alpha = np.ones(img.shape[:2] + (1,))
    arr = np.concatenate([img, np.clip(alpha, 0, 1)], -1)[::-1]      # rows: v-up -> PNG top-down
    Image.fromarray((arr * 255 + 0.5).astype(np.uint8), 'RGBA').save(os.path.join(OUT, name))

save('daisy_albedo.png', lin2srgb(sheet['alb']), sheet['a'])
save('daisy_normal.png', sheet['nrm'] * 0.5 + 0.5)
save('daisy_roughness.png', np.repeat(sheet['rough'], 3, -1))
save('daisy_translucency.png', np.repeat(lin2srgb(sheet['transl']), 3, -1))

# ── fit: measured alpha envelopes of every card window ─────────────────────
PAD = 1.14
A = sheet['a'][..., 0]
def envelope(mask, n_st):
    """mask rows = along the card (base->tip), cols = across. Stations at
    t = g/(n_st-1); each takes the widest art within +-half a band."""
    rows = mask.shape[0]
    cols_n = mask.shape[1]
    st = []
    for g in range(n_st):
        t = g / (n_st - 1)
        half = 0.5 / (n_st - 1)
        r0 = int(max(0, (t - half) * rows)); r1 = int(min(rows, (t + half) * rows + 1))
        sl = mask[r0:r1]
        cols = np.nonzero(sl.any(axis=0))[0]
        if len(cols) == 0:
            st.append([0.5, 0.02]); continue
        c = (cols.min() + cols.max() + 1) / 2 / cols_n
        hw = (cols.max() + 1 - cols.min()) / 2 / cols_n * PAD
        st.append([round(float(c), 4), round(float(min(hw, 0.5)), 4)])
    return st

fit = {'version': 1, 'sheet': 1024, 'petals': [], 'petalV': [], 'leaves': {}}
px0, py0 = LAYOUT['petals'][:2]
for k in range(16):
    c, row = k % 8, k // 8
    x0, y0 = px0 + 74 * c, py0 + 207 * row
    cell = A[y0:y0 + 207, x0:x0 + 74] > 0.5          # rows = v up = base -> tip
    rows = np.nonzero(cell.any(axis=1))[0]
    vb, vt = rows.min(), rows.max() + 1
    fit['petals'].append(envelope(cell[vb:vt], 5))
    fit['petalV'].append([round(vb / 207, 4), round(vt / 207, 4)])
for key in ('basalA', 'basalB', 'stemA', 'stemB'):
    x0, y0, x1, y1 = LAYOUT[key]
    win = (A[y0:y1, x0:x1] > 0.5).T                  # rows = u (base -> tip), cols = v
    rows = np.nonzero(win.any(axis=1))[0]
    ub, ut = rows.min(), rows.max() + 1
    fit['leaves'][key] = {'u': [round(ub / (x1 - x0), 4), round(ut / (x1 - x0), 4)],
                          'bands': envelope(win[ub:ut], 7)}
fit['layout'] = {k: [v / 1024 for v in LAYOUT[k]] for k in LAYOUT}
with open(os.path.join(OUT, 'daisy_fit.json'), 'w') as f:
    json.dump(fit, f)
print('[fit] petal 0:', fit['petals'][0], fit['petalV'][0])
print('[fit] basalA:', fit['leaves']['basalA'])

# preview: the albedo over grey + a lit relief view
g = 0.25
prev = lin2srgb(sheet['alb']) * sheet['a'] + g * (1 - sheet['a'])
Image.fromarray((np.clip(prev[::-1], 0, 1) * 255).astype(np.uint8)).save(os.path.join(OUT, 'preview_albedo.png'))
L = np.array([-0.5, 0.45, 0.74]); L /= np.linalg.norm(L)
lam = np.clip((sheet['nrm'] * L).sum(-1, keepdims=True), 0, 1)
litp = lin2srgb(sheet['alb'] * (0.2 + 0.9 * lam)) * sheet['a'] + 0.1 * (1 - sheet['a'])
Image.fromarray((np.clip(litp[::-1], 0, 1) * 255).astype(np.uint8)).save(os.path.join(OUT, 'preview_lit.png'))

if INSTALL:
    import shutil
    for nme in ('daisy_albedo.png', 'daisy_normal.png', 'daisy_roughness.png', 'daisy_translucency.png', 'daisy_fit.json'):
        shutil.copy(os.path.join(OUT, nme), os.path.join(INSTALL, nme))
    print('[sheet] installed ->', INSTALL)
print('[sheet] done')
