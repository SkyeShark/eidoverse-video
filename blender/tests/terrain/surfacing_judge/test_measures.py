"""The surfacing judge's measures on inputs with known answers (plain Python: numpy, Pillow; no Blender, no GPU):

    python blender/tests/terrain/surfacing_judge/test_measures.py [-k name]      # (the test_* functions suit pytest)

    largest_region          the run-based region finder against a flood fill on random masks; a diagonal touch joins
    gaussian_blur           a constant stays, an impulse sums to 1 and has the kernel's width, borders mirror
    lab                     sRGB white, mid grey and red at their CIELAB values
    one_material            a tile split in two with a soft edge: pure share, largest region, a third layer's speckle
    contour_index           a field of the height itself scores 1, one that runs down the slope 0, noise 2/pi
    layer_contours          bands by height score 1 on a cone and ribs by azimuth 0; frozen strata masks change the
                            weights of a layer that reads them
    repetition              a tiled texture scores 1 at its period in both modes; noise and a photograph-like
                            1/f field stay low
    blocks_and_colour       a flat colour has no spread; a render compared with itself gives delta E 0 and ratio 1;
                            a hue step is found in the photograph's direction and against it
    layer_map               weights -> picture -> weights: one, two and three layers per pixel, 8 bits, with water
                            and sky, for palettes of 3 to 6 layers
    frame_splat             a flat two-layer terrain seen from above: the camera sees each layer's half
    seam                    a colour step along a line reads as its delta E; a gradient reads as its control
    plants_pattern          Poisson g = 1; a hard core empties g below it; a Thomas process clusters at sigma
    plants_format           the spots format written, read back, checked; a floating plant and a cut file are caught
    camera                  from_aim puts the aim where frame says; rays and project agree; a ray meets a plane
                            where geometry says; a wall in front of the camera fails the view check, an aim on a wall's
                            face and open ground pass; a viewpoint sees its target over a wall; the clay preview
    make_views              a view behind a ridge is moved past it to see its aim, a spot is found for a view that
                            keeps its heading, an establishing aerial is added
    records                 a render record's level windows parsed; its camera rebuilt from heading and pitch; the
                            cost read from it against section 7's budgets
    board                   a frozen state's render and layer map make a board row, its crops on the largest single
                            layer and on the layer edges; the eye view's distance bands land on the rows level ground
                            gives them
    targets                 the verdicts of section 6's table, and the audit comparison's 10 % rule
"""
import math
import os
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..')))

from surfacing_judge import layers as LY  # noqa: E402
from surfacing_judge import measures as M  # noqa: E402
from surfacing_judge import plants as PL  # noqa: E402
from surfacing_judge import views as V  # noqa: E402

RNG = np.random.default_rng(7)


def near(a, b, tol, what):
    assert a is not None and abs(a - b) <= tol, f'{what}: {a} is not within {tol} of {b}'


def _flood_largest(m):
    m = m.copy()
    H, W = m.shape
    best = count = 0
    for j in range(H):
        for i in range(W):
            if not m[j, i]:
                continue
            count += 1
            stack, area = [(j, i)], 0
            m[j, i] = False
            while stack:
                y, x = stack.pop()
                area += 1
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        yy, xx = y + dy, x + dx
                        if 0 <= yy < H and 0 <= xx < W and m[yy, xx]:
                            m[yy, xx] = False
                            stack.append((yy, xx))
            best = max(best, area)
    return best, count


def test_largest_region():
    for p in (0.2, 0.45, 0.6, 0.8):
        for _ in range(4):
            m = RNG.random((37, 53)) < p
            assert M.largest_region(m) == _flood_largest(m), f'random mask at {p}'
    m = np.zeros((6, 6), bool)
    m[0:2, 0:2] = m[2:4, 2:4] = True                   # two squares touching at a corner: one region
    assert M.largest_region(m) == (8, 1)
    m = np.zeros((40, 40), bool)                        # a spiral arm: a long thin region
    for k in range(0, 18, 2):
        m[k, k:40 - k] = m[39 - k, k:40 - k] = True
        m[k:40 - k, 39 - k] = True
        m[k + 2:40 - k, k] = True
    assert M.largest_region(m) == _flood_largest(m)
    assert M.largest_region(np.zeros((5, 5), bool)) == (0, 0)
    print(f'  random masks, a corner touch and a spiral agree with a flood fill')


def test_gaussian_blur():
    a = np.full((30, 40), 3.25)
    assert np.allclose(M.gaussian_blur(a, 6.0), 3.25)
    imp = np.zeros((101, 101))
    imp[50, 50] = 1.0
    b = M.gaussian_blur(imp, 4.0)
    near(float(b.sum()), 1.0, 1e-9, 'impulse sum')
    yy, xx = np.mgrid[-50:51, -50:51]
    near(float(np.sqrt((b * xx * xx).sum())), 4.0, 0.02, 'impulse sigma')
    row = M.gaussian_blur(imp, 4.0, 0.0)
    assert np.count_nonzero(row.sum(1)) == 1, 'sigma_y 0 leaves the rows alone'
    ramp = np.arange(40.0)[None, :].repeat(3, 0)         # mirrored about the edge sample: a ramp bends only there
    assert np.allclose(M.gaussian_blur(ramp, 2.0, 0.0)[:, 10:30], ramp[:, 10:30])
    try:
        import cv2
        x = RNG.random((60, 90))
        d = np.abs(M.gaussian_blur(x, 6.0) - cv2.GaussianBlur(x, (0, 0), 6.0)).max()
        assert d < 1e-9, f'differs from OpenCV by {d}'
        print(f'  equals OpenCV GaussianBlur to {d:.1e}')
    except ImportError:
        print('  (OpenCV is not installed: its comparison skipped)')


def test_lab():
    for rgb, lab in (((1, 1, 1), (100.0, 0.0, 0.0)), ((1, 0, 0), (53.24, 80.09, 67.20)),
                     ((0.4663, 0.4663, 0.4663), (50.0, 0.0, 0.0)), ((0, 0, 1), (32.30, 79.19, -107.86))):
        got = M.srgb_to_lab(np.array(rgb, float))
        assert np.abs(got - np.array(lab)).max() < 0.1, f'{rgb}: {got} is not {lab}'
    near(M.delta_e((50, 0, 0), (50, 3, 4)), 5.0, 1e-9, 'delta E')
    x = RNG.random((5, 3))
    assert np.allclose(M.linear_to_srgb(M.srgb_to_linear(x)), x, atol=1e-9)
    print('  white, grey, red and blue at their CIELAB values')


def test_one_material():
    n = 200
    x = np.linspace(0, 1, n)[None, :].repeat(n, 0)
    top = np.clip((x - 0.45) / 0.1, 0, 1)               # the upper layer fades in over x 0.45-0.55
    E = M.exclusive([np.ones((n, n)), top])
    assert np.allclose(E.sum(0), 1.0)
    r = M.one_material(E, names=['base', 'top'])
    near(r['pure_total'], 0.92, 0.012, 'pure share')    # everything but the middle 80 % of the fade (x 0.46-0.54)
    near(r['largest'], 0.50, 0.012, 'largest region')
    near(r['layers'][0]['share'], 0.5, 0.01, 'base share')
    speck = np.zeros((n, n))
    speck[::4, ::4] = 1.0                               # a third layer in single cells: many regions, none large
    r3 = M.one_material(M.exclusive([np.ones((n, n)), top, speck]), names=['base', 'top', 'speck'])
    assert r3['layers'][2]['largest'] < 1e-3 and r3['layers'][2]['regions'] == (n // 4) ** 2
    half = np.zeros((n, n), bool)
    half[:, : n // 2] = True
    near(M.one_material(E, valid=half)['layers'][0]['share'], 0.975, 0.01, 'share inside a mask')
    print(f"  split tile: pure {r['pure_total']:.3f}, largest {r['largest']:.3f} ({r['largest_layer']})")


def _cone(n=256, cell=10.0):
    c = (np.arange(n) + 0.5 - n / 2) * cell
    X, Y = np.meshgrid(c, c)
    R = np.hypot(X, Y)
    return X, Y, R, 2000.0 - 0.6 * R, cell


def test_contour_index():
    X, Y, R, h, cell = _cone()
    near(M.contour_index(np.sin(h / 60.0), h, cell), 1.0, 1e-4, 'bands by height')
    ring = (R > 300) & (R < 1100)
    near(M.contour_index(np.sin(8 * np.arctan2(Y, X)), h, cell, sel=ring), 0.0, 0.02, 'ribs down the slope')
    noise = M.gaussian_blur(RNG.standard_normal(h.shape), 3.0)
    near(M.contour_index(noise, h, cell, sel=ring, min_grad=0.0), M.RANDOM_CONTOUR, 0.02, 'noise')
    assert M.contour_index(np.zeros_like(h), h, cell) is None
    assert M.contour_index(noise, np.zeros_like(h), cell) is None, 'flat ground has no height lines'
    print('  bands 1.00, ribs 0.00, noise 0.64')


def test_layer_contours():
    X, Y, R, h, cell = _cone()
    bands = 0.5 + 0.5 * np.sin(h / 80.0)
    ribs = (0.5 + 0.5 * np.sin(10 * np.arctan2(Y, X))) * np.clip((R - 200.0) / 200.0, 0.0, 1.0)
    slope = np.full(h.shape, math.degrees(math.atan(0.6)))
    r = M.layer_contours(M.exclusive([np.ones_like(h), bands]), h, cell, slope, names=['base', 'bands'])
    near(r['all'], 1.0, 0.02, 'bands')
    near(r['steep'], 1.0, 0.02, 'bands on the steep ground')
    r = M.layer_contours(M.exclusive([np.ones_like(h), ribs]), h, cell, slope, names=['base', 'ribs'])
    assert r['all'] < 0.12, f"ribs score {r['all']}"
    assert M.layer_contours(M.exclusive([np.ones_like(h), bands]), h, cell, np.zeros_like(h))['steep'] is None
    # a layer placed by the rock column: its weight changes when the strata masks are frozen
    pal = dict(layers=[dict(weight='1'), dict(weight='smoothstep(0.4, 0.6, strata)')])
    masks = dict(strata=(np.sin(h / 80.0) * 0.5 + 0.5))
    E = LY.weights(pal, masks, X, Y, {})
    Ef = LY.weights(pal, masks, X, Y, {}, freeze=LY.STRATA_MASKS)
    assert E[1].std() > 0.3 and Ef[1].std() < 1e-9
    assert LY.reads_strata(pal) == ['strata']
    print('  bands 1.00, ribs under 0.12; a strata-placed layer goes flat with the strata frozen')


def _one_over_f(shape, rng):
    f = np.fft.rfft2(rng.standard_normal(shape))
    ky = np.fft.fftfreq(shape[0])[:, None]
    kx = np.fft.rfftfreq(shape[1])[None, :]
    k = np.hypot(kx, ky)
    k[0, 0] = 1.0
    return np.fft.irfft2(f / k, s=shape)


def test_repetition():
    tile = RNG.random((32, 32))
    tiled = np.tile(tile, (6, 9))                       # 192 x 288, period 32
    r = M.repetition(tiled, mode='2d', tile_px=32)
    assert r['peak'] > 0.9 and (abs(r['lag'][0]) % 32 == 0 and abs(r['lag'][1]) % 32 == 0), r
    near(r['at_tile_px'], 1.0, 0.1, 'correlation at the tile period')
    rr = M.repetition(tiled, mode='rows', tile_px=32)
    assert rr['peak'] > 0.9 and rr['lag'] % 32 == 0, rr
    for name, img in (('white noise', RNG.random((192, 288))), ('1/f ground', _one_over_f((192, 288), RNG))):
        a, b = M.repetition(img, mode='2d'), M.repetition(img, mode='rows')
        assert (a['peak'] or 0) < 0.2 and (b['peak'] or 0) < 0.2, f'{name}: {a} {b}'
    box = M.repetition(np.pad(tiled, 40), box=(40, 40, 40 + 288, 40 + 192), mode='2d')
    near(box['peak'], r['peak'], 1e-9, 'a box of the image equals the crop')
    print(f"  tiled {r['peak']:.2f} at {r['lag']}, rows {rr['peak']:.2f} at {rr['lag']} px; noise under 0.2")


def test_blocks_and_colour():
    flat = np.full((128, 192, 3), (0.5, 0.4, 0.3))
    st = M.block_stats(flat)
    assert st['n'] == 24 and st['L_std'] < 1e-9
    img = np.clip(0.45 + 0.2 * _one_over_f((128, 192), RNG)[..., None] / 3.0 * np.array([1.0, 0.8, 0.6]), 0.02, 0.98)
    ones = np.ones(img.shape[:2], bool)
    c = M.colour_compare(img, ones, img, ones)
    near(c['delta_e'], 0.0, 1e-9, 'delta E against itself')
    near(c['spread_ratio_L'], 1.0, 1e-9, 'spread ratio against itself')
    c2 = M.colour_compare(np.clip(img.mean((0, 1), keepdims=True) + 0.5 * (img - img.mean((0, 1), keepdims=True)),
                                  0, 1), ones, img, ones)
    assert 0.4 < c2['spread_ratio_L'] < 0.62, c2['spread_ratio_L']   # half the contrast: about half the spread
    grey, red = M.srgb_to_lab(np.array([0.5, 0.5, 0.5])), M.srgb_to_lab(np.array([0.6, 0.4, 0.35]))
    two = np.full((64, 128, 3), 0.5)
    two[:, 64:] = (0.6, 0.4, 0.35)
    left = np.zeros((64, 128), bool)
    left[:, :64] = True
    h = M.hue_relation(two, left, ~left, two, left, ~left)
    near(h['cosine'], 1.0, 1e-9, 'the same step')
    near(h['photo_delta_e'], M.delta_e(grey, red), 1e-6, 'the step size')
    near(M.hue_relation(two, ~left, left, two, left, ~left)['cosine'], -1.0, 1e-9, 'the step the wrong way')
    lv = M.layer_variation(two, np.stack([left, ~left]).astype(float), names=['a', 'b'],
                           photo_stats=dict(L_std=2.0), block=16)
    assert lv[0]['n'] == 16 and lv[0]['L_std'] < 1e-9 and lv[0]['ratio'] < 1e-6
    half = np.zeros(img.shape[:2], bool)
    half[:, :96] = True
    assert M.block_stats(img, half)['n'] == 12
    print(f"  self delta E 0, ratio 1; half contrast ratio {c2['spread_ratio_L']:.2f}; hue step +1 / -1")


def _mix_fields(n_layers, shape, rng, three=True):
    """Weights (n_layers, H, W) with pure areas, soft two-layer edges and a few three-layer corners."""
    H, W = shape
    lab = (M.gaussian_blur(rng.standard_normal((n_layers,) + shape).reshape(-1, W), 0.0).reshape(n_layers, H, W))
    sm = np.stack([M.gaussian_blur(a, 9.0) for a in lab])
    order = np.argsort(-sm, axis=0)
    a, b, c = order[0], order[1], order[2 if n_layers > 2 else 1]
    va = np.take_along_axis(sm, a[None], 0)[0]
    vb = np.take_along_axis(sm, b[None], 0)[0]
    vc = np.take_along_axis(sm, c[None], 0)[0]
    t = np.clip(0.5 - (va - vb) / 0.02, 0.0, 0.5)       # 0 away from an edge, 0.5 on it
    u = np.clip(0.33 - (va - vc) / 0.02, 0.0, 0.33) if three and n_layers > 2 else np.zeros(shape)
    w = np.zeros((n_layers,) + shape)
    np.put_along_axis(w, a[None], (1.0 - t - u)[None], 0)
    w2 = np.zeros_like(w)
    np.put_along_axis(w2, b[None], t[None], 0)
    w3 = np.zeros_like(w)
    np.put_along_axis(w3, c[None], u[None], 0)
    w = w + w2 + w3
    return w / w.sum(0, keepdims=True)


def test_layer_map():
    cols = LY.debug_colours()
    assert len(cols) >= 6 and len(set(cols)) == len(cols)
    worst = 0.0
    for n_layers in (3, 4, 5, 6):
        w = _mix_fields(n_layers, (90, 160), RNG)
        alpha = np.ones((90, 160))
        alpha[:20] = 0.0                                 # sky
        water = np.zeros((90, 160))
        water[70:, 100:] = 1.0                           # a lake
        water[69, 100:] = 0.4                            # its antialiased shore
        img = LY.encode_layer_map(w, alpha, water)
        img8 = np.round(img * 255.0) / 255.0
        got, ground, wshare, info = LY.decode_layer_map(img8, n_layers)
        assert not ground[:20].any() and not ground[70:, 100:].any() and ground[20:69].all()
        land = (alpha > 0.5) & (water == 0)
        err = np.abs(got - w)[:, land]
        mixes = ((w > 0.02).sum(0))[land]
        e12 = float(err[:, mixes <= 2].max())
        e3 = float(np.percentile(err[:, mixes == 3], 95)) if (mixes == 3).any() else 0.0
        assert e12 < 0.05, f'{n_layers} layers: a one- or two-layer pixel is off by {e12}'
        assert e3 < 0.12, f'{n_layers} layers: three-layer pixels are off by {e3} (95th percentile)'
        assert info['unresolved'] < 0.002, info
        near(float(wshare[69, 120]), 0.4, 0.03, 'the shore pixel')
        dom_true, dom_got = w.argmax(0)[land], got.argmax(0)[land]
        assert (dom_true != dom_got).mean() < 0.005
        o1, o2 = M.one_material(w, land), M.one_material(got, ground & land)
        near(o2['pure_total'], o1['pure_total'], 0.01, 'pure share through the picture')
        near(o2['largest'], o1['largest'], 0.01, 'largest region through the picture')
        worst = max(worst, e12)
    one = LY.encode_layer_map(np.ones((1, 8, 8)))
    assert LY.decode_layer_map(one, 1, water=False)[0].min() > 0.999
    print(f'  3 to 6 layers through an 8-bit picture: one- and two-layer pixels within {worst:.3f}')


class _Flat:
    """A flat two-level stack for the splat: the main level's west half is layer 0, its east half layer 1."""
    main = 1

    def __init__(self):
        self.levels = [dict(x0=-400.0, y0=-400.0, side=800.0, cell=8.0, n=100, role='context'),
                       dict(x0=-200.0, y0=-200.0, side=400.0, cell=4.0, n=100, role='main')]
        self.fields = [dict(h=np.zeros((100, 100))), dict(h=np.zeros((100, 100)))]

    def xy(self, level='main'):
        lv = self.levels[self.main if level == 'main' else int(level)]
        c = (np.arange(lv['n']) + 0.5) * lv['cell']
        return np.meshgrid(lv['x0'] + c, lv['y0'] + c)

    def masks(self, level='main', log=None):
        X, _Y = self.xy(level)
        return dict(height=(X > 0).astype(np.float32))

    def constants(self, pal):
        return {}

    def height_at(self, x, y):
        return np.zeros(np.broadcast(x, y).shape)


def test_frame_splat():
    st = _Flat()
    pal = dict(layers=[dict(weight='1'), dict(weight='smoothstep(0.4, 0.6, height)')])
    cam = V.Camera.from_aim((0.0, -1.0, 300.0), (0.0, 0.0, 0.0), lens=20.0)      # straight down, north up
    w, seen = LY.frame_splat(st, pal, cam, size=(48, 27))       # 11 m a pixel: every pixel gets a cell
    assert seen.mean() > 0.97, seen.mean()
    left, right = w[:, :, :22], w[:, :, 26:]
    assert left[0][seen[:, :22]].mean() > 0.97 and right[1][seen[:, 26:]].mean() > 0.97
    near(float(w[1][seen].mean()), 0.5, 0.04, 'the east layer\'s share of the frame')
    fine = LY.frame_splat(st, pal, cam, size=(192, 108))[1]    # 2.8 m a pixel over 8 m cells: holes, and it says so
    assert 0.3 < fine.mean() < 0.9
    print(f'  straight down over a split tile: {100 * seen.mean():.0f} % seen, east layer {w[1][seen].mean():.2f}')


def test_seam():
    H, W = 200, 300
    a, b = np.array([0.42, 0.36, 0.30]), np.array([0.46, 0.38, 0.30])
    img = np.empty((H, W, 3))
    img[:] = a
    yy, xx = np.mgrid[0:H, 0:W]
    side = (yy - 100) - 0.3 * (xx - 150) > 0            # a line through the middle, slope 0.3
    img[side] = b
    pts = np.stack([np.linspace(20, 280, 60), 100 + 0.3 * (np.linspace(20, 280, 60) - 150)], 1)
    P, N, vis = M.line_samples(pts)
    assert len(P) > 100 and vis.all() and np.allclose(np.hypot(N[:, 0], N[:, 1]), 1.0)
    s = M.seam_delta(img, P, N, vis)
    step = M.delta_e(M.srgb_to_lab(a), M.srgb_to_lab(b))
    near(s['delta_e'], step, 0.05, 'the step across the line')
    assert s['control'] < 0.05, s
    grad = np.empty((H, W, 3))
    grad[:] = (0.3 + 0.002 * yy)[..., None]             # a smooth gradient: no seam
    g = M.seam_delta(grad, P, N, vis)
    near(g['delta_e'], g['control'], 0.15 * g['control'], 'a gradient reads as its control')
    near(s['excess'], s['delta_e'] - s['control'], 1e-9, 'the excess over the control')
    # a point projected far outside the picture (just in front of the camera's plane) and hidden adds nothing
    far = np.array([[20.0, 50.0], [120.0, 50.0], [1e12, 7.0], [140.0, 60.0], [240.0, 60.0]])
    Pf, _Nf, vf = M.line_samples(far, np.array([True, True, False, True, True]))
    assert len(Pf) == 100 and vf.all(), len(Pf)                 # 200 px of visible line at 2 px
    hidden = vis.copy()
    hidden[:] = False
    assert M.seam_delta(img, P, N, hidden) is None
    sky = np.ones((H, W), bool)
    sky[:, 150:] = False                                 # the right half is sky: its samples are left out
    half = M.seam_delta(img, P, N, vis, ground=sky)
    assert half['n'] < 0.55 * s['n'] and abs(half['delta_e'] - step) < 0.1, (half, s['n'])
    # the step is a change of layer (a landform's edge the window edge runs along): not a seam
    two = np.stack([(~side).astype(float), side.astype(float)])
    assert M.seam_delta(img, P, N, vis, weights=two) is None
    one = np.stack([np.ones((H, W)), np.zeros((H, W))])     # one layer on both sides: the step is a seam
    near(M.seam_delta(img, P, N, vis, weights=one)['delta_e'], step, 0.05, 'a step within one layer')
    print(f"  a step of {step:.2f} reads {s['delta_e']:.2f} (control {s['control']:.2f}); a gradient "
          f"{g['delta_e']:.2f} against control {g['control']:.2f}")


def _poisson(n, size, rng):
    return rng.random(n) * size, rng.random(n) * size


def _hard_core(n, size, core, rng):
    cell = core
    grid = {}
    xs, ys = [], []
    while len(xs) < n:
        x, y = rng.random() * size, rng.random() * size
        gi, gj = int(x / cell), int(y / cell)
        ok = True
        for dj in (-1, 0, 1):
            for di in (-1, 0, 1):
                for (px, py) in grid.get((gi + di, gj + dj), ()):
                    if (px - x) ** 2 + (py - y) ** 2 < core * core:
                        ok = False
        if ok:
            grid.setdefault((gi, gj), []).append((x, y))
            xs.append(x)
            ys.append(y)
    return np.array(xs), np.array(ys)


def _thomas(parents, mu, sigma, size, rng):
    px, py = rng.random(parents) * size, rng.random(parents) * size
    k = rng.poisson(mu, parents)
    x = np.repeat(px, k) + rng.normal(0, sigma, k.sum())
    y = np.repeat(py, k) + rng.normal(0, sigma, k.sum())
    ok = (x > 0) & (x < size) & (y > 0) & (y < size)
    return x[ok], y[ok]


def test_plants_pattern():
    size = 1000.0
    win = (0, 0, size, size)
    edges = np.linspace(0, 40, 21)
    x, y = _poisson(6000, size, RNG)
    g = np.array(M.pair_correlation(x, y, win, edges)['g'])
    assert np.abs(g[2:] - 1.0).max() < 0.12, g
    near(M.stems_per_ha(len(x), size * size), 60.0, 1e-9, 'stems per hectare')
    x, y = _hard_core(4000, size, 6.0, RNG)
    p = M.plant_pattern(x, y, win, core_m=6.0)
    assert p['inhibited'] and p['g_core'] < 0.01 and abs(p['g_far'] - 1.0) < 0.15, p
    x, y = _thomas(300, 20, 8.0, size, RNG)
    p = M.plant_pattern(x, y, win, core_m=1.0, sigma_m=8.0)
    assert p['clustered'] and p['g_cluster'] > 2.0 and not p['inhibited'], p
    assert abs(M.plant_pattern(x, y, win, core_m=1.0, sigma_m=8.0, r_max=120.0)['g_far'] - 1.0) < 0.2
    print(f"  Poisson g within 0.12 of 1; hard core g {0.0:.2f} below it; Thomas g {p['g_cluster']:.1f} at sigma")


def test_plants_format():
    rng = np.random.default_rng(11)                    # its own draws: the same plants whichever tests ran before
    with tempfile.TemporaryDirectory() as d:
        base = os.path.join(d, 'canyon')
        x, y = _hard_core(500, 300.0, 4.0, rng)
        n = len(x)
        tab = dict(x=x, y=y, z=0.01 * x, yaw=rng.random(n) * 6.28, scale=np.ones(n), age=rng.random(n),
                   tint=rng.random(n), nx=np.zeros(n), ny=np.zeros(n), nz=np.ones(n), variant=np.zeros(n),
                   level=np.ones(n))
        header = dict(frame=dict(axes='x east, y north, z up, metres (Blender)'), terrain=dict(recipe='canyon'),
                      seed=7, species=[dict(name='juniper', kind='tree', size_m=[2, 6], core_m=4.0,
                                            cluster=dict(sigma_m=20.0))])
        PL.save(base, header, dict(juniper=tab))
        sp = PL.load(base)
        assert sp.names() == ['juniper'] and sp.count() == n
        assert np.allclose(sp.table('juniper')['x'], x.astype('<f4'))
        assert PL.check(sp, height_at=lambda a, b: 0.01 * a) == [], PL.check(sp)
        near(PL.density(sp, 'juniper', (0, 0, 300, 300)), n / 9.0, 1e-6, 'stems per hectare')
        v = PL.core_violations(sp, 'juniper')
        assert v['pairs'] == 0 and v['nearest_m'] is None, v          # no two plants within the core at all
        rp = PL.report(sp, height_at=lambda a, b: 0.01 * a)
        assert rp['problems'] == [] and rp['species']['juniper']['count'] == n, rp
        assert rp['species']['juniper']['pattern']['inhibited'], rp['species']['juniper']
        # the gate at a window edge: an even stand passes, a stand thinned inside the window does not
        even = PL.edge_density(sp, 'juniper', windows=[(100.0, 100.0, 100.0)], strip_m=30.0, min_count=5)
        assert even and all(e['verdict'] == 'pass' or abs(e['ratio'] - 1) < 0.35 for e in even), even
        keep = ~((tab['x'] > 100) & (tab['x'] < 130) & (tab['y'] > 100) & (tab['y'] < 200) & (rng.random(n) < 0.5))
        thin = PL.Spots(base, sp.header, dict(juniper={k: (v[keep] if k != '_bytes' else v)
                                                         for k, v in sp.table('juniper').items()}))
        west = [e for e in PL.edge_density(thin, 'juniper', windows=[(100.0, 100.0, 100.0)], strip_m=30.0,
                                            min_count=5) if e['edge'] == 'west']
        assert west and west[0]['ratio'] < 0.75 and west[0]['verdict'] == 'fail', west
        # a floating plant, a pair inside the core and a cut file are caught
        tab2 = {k: np.r_[a, a[:1]] for k, a in tab.items()}
        tab2['x'][-1] += 1.0
        tab2['z'][-1] += 2.0
        PL.save(base, header, dict(juniper=tab2))
        sp = PL.load(base)
        assert any('off the ground' in s for s in PL.check(sp, height_at=lambda a, b: 0.01 * a))
        assert PL.core_violations(sp, 'juniper')['pairs'] >= 1      # the copy 1 m from its original, and any
        #                                                              neighbour it lands near
        path = base + '.plants.juniper.f32'
        with open(path, 'rb') as f:
            raw = f.read()
        with open(path, 'wb') as f:
            f.write(raw[:-6])
        msgs = PL.check(PL.load(base))
        assert any('whole number' in s for s in msgs) and any('header counts' in s for s in msgs), msgs
    print('  written, read back and checked; a floating plant, a crowded pair and a cut file are caught')


def test_camera():
    eye, tgt = (100.0, -50.0, 30.0), (400.0, 700.0, -20.0)
    for frame in ((0.5, 0.5), (0.25, 0.62), (0.66, 0.07)):
        cam = V.Camera.from_aim(eye, tgt, frame, 35.0)
        px, py, zc = cam.project(*tgt)
        # the review's rule turns the camera by the two offsets one after the other: exact at the centre, within
        # a few pixels off it
        tol = 0.01 if frame == (0.5, 0.5) else 6.0
        near(float(px), frame[0] * 960, tol, 'aim x')
        near(float(py), frame[1] * 540, tol, 'aim y')
        assert zc > 0 and abs(cam.u[0] * cam.r[0] + cam.u[1] * cam.r[1] + cam.u[2] * cam.r[2]) < 1e-12
        assert abs(cam.r[2]) < 1e-12, 'a level horizon'
    cam = V.Camera.from_aim((0.0, 0.0, 10.0), (0.0, 100.0, 10.0), lens=36.0)
    near(cam.heading_deg, 0.0, 1e-9, 'heading north')
    d = cam.rays(48, 27)
    px, py, _z = cam.project(d[5, 7, 0] * 50, d[5, 7, 1] * 50, 10.0 + d[5, 7, 2] * 50)
    near(float(px), (7 + 0.5) / 48 * 960, 1e-6, 'a ray back through its pixel')
    near(float(py), (5 + 0.5) / 27 * 540, 1e-6, 'a ray back through its pixel')
    flat = lambda x, y: np.zeros(np.broadcast(x, y).shape)       # noqa: E731
    hit = V.raycast(flat, cam.eye, d, far=5000.0)
    j, i = 20, 24
    near(float(hit[j, i]), 10.0 / -d[j, i, 2], 0.02 * 10.0 / -d[j, i, 2], 'a ray onto flat ground')
    assert np.isinf(hit[:13]).all(), 'rays over the horizon are sky'

    class Wall(_Flat):
        def __init__(self, wall):
            super().__init__()
            self.wall = wall

        def height_at(self, x, y):
            y = np.asarray(y, float) + 0.0 * np.asarray(x, float)
            return np.where((y > 8.0) & (y < 30.0), 40.0, 0.0) if self.wall else np.zeros(y.shape)
    v = dict(name='eye', cam=[0.0, 0.0], cam_z=['ground', 1.7], aim=[0.0, 150.0, 1.0], lens=35.0, frame=[0.5, 0.5],
             focus=True)
    ok, blocked = V.check(Wall(False), v), V.check(Wall(True), v)
    assert ok['fails'] == [] and ok['stands'] == 'main' and ok['aim_clear_m'] > 0 and ok['aim_seen'] == 1.0
    assert blocked['aim_clear_m'] < 0 and blocked['blocked'] > 0.9 and len(blocked['fails']) == 2, blocked['fails']
    near(blocked['aim_seen'], 8.0 / 150.0, 0.02, 'the ray at the aim stops at the wall')
    # an aim on the face of a wall the camera looks at: the line to it ends inside the wall, and the view is right
    face = V.check(Wall(True), dict(v, cam=[0.0, -150.0], aim=[0.0, 25.0, 20.0]))
    assert face['aim_clear_m'] < 0 and face['fails'] == [], face['fails']
    out = V.check(Wall(False), dict(v, cam=[0.0, -300.0], focus=False))
    assert out['stands'] == 'context' and any('context level' in s for s in out['warns']) and not out['fails']
    vp = V.viewpoint(Wall(False), (0.0, 150.0, 10.0), 120.0, heading=0.0)
    assert abs(vp['eye'][0]) < 1e-6 and abs(vp['eye'][1] - 30.0) < 1e-6 and abs(vp['heading_deg']) < 1e-6, vp
    walled = Wall(True)
    vp = V.viewpoint(walled, (0.0, 150.0, 10.0), 140.0, heading=0.0)
    ex, ey, ez = vp['eye']
    tt = np.linspace(0.03, 0.97, 200)
    lz = ez + (10.0 - ez) * tt
    gz = walled.height_at(ex + (0.0 - ex) * tt, ey + (150.0 - ey) * tt)
    assert (lz - gz).min() >= 1.0, 'the chosen eye sees the target over the wall'
    clay = V.preview(Wall(False), v, size=(48, 27))
    assert clay.shape == (27, 48, 3) and clay[20, 24, 2] < clay[2, 24, 2], 'ground below, sky above'
    walls = V.preview(Wall(True), v, size=(48, 27))
    assert walls[2, 10, 2] < 170 and clay[2, 10, 2] > 170, 'the wall fills the sky the open view shows'
    print('  the aim lands where frame says; a wall 8 m ahead fails the view, an aim on a wall face and open '
          'ground pass; a viewpoint clears the wall')


def test_make_views():
    from surfacing_judge import make_views as MV

    class Ridge(_Flat):
        """Flat ground with a ridge 40 m high across y 20-60."""
        def height_at(self, x, y):
            y = np.asarray(y, float) + 0.0 * np.asarray(x, float)
            return np.where((y > 20.0) & (y < 60.0), 40.0, 0.0)
    st = Ridge()
    v = dict(name='eye', kind='eye', cam=[0.0, 0.0], cam_z=['ground', 1.7], aim=[0.0, 150.0, 5.0], lens=35.0,
             frame=[0.5, 0.5], focus=True, photo=None, caption='')
    assert V.check(st, v)['fails'], 'the ridge stands between the camera and its aim'
    w, c, how = MV.fix_see(st, v, dict(target='aim', prefer='low'))
    assert w is not None and not c['fails'] and w['cam'][1] > 60.0, (w, how)     # past the ridge, facing the aim
    w2, c2, how2 = MV.fix_spot(st, dict(v, aim=[0.0, 150.0, 0.0]), dict(radius=150.0, prefer='low'))
    assert w2 is not None and not c2['fails'], how2
    est = MV.added(st, 'meadow', 'high', 400.0)
    assert est['name'] == 'establishing' and not V.check(st, est)['fails']
    assert MV.level_kind(dict(height_m=1.7), 400.0) == 'eye' and MV.level_kind(dict(height_m=60.0), 400.0) == 'high'
    print(f"  a view behind a ridge moved past it ({how}); a spot found; an establishing aerial added")


def test_records():
    from surfacing_judge import cost as C
    from surfacing_judge import states as S
    rec = dict(camera=[441.4, 2472.7, 898.9], heading_deg=180.0, pitch_deg=2.98, lens=35.0,
               levels=['Level(0 context 16000 m @ 15.62 m x1024, x0 -8000 y0 -8000, prepass [256, 512])',
                       'Level(1 main 8000 m @ 7.812 m x1024, x0 -4000 y0 -4000)',
                       'Level(5 hero 500 m @ 0.4883 m x1024, x0 191.406 y0 2222.66)'],
               build_s=23.0, first_render_s=27.3, second_render_s=2.41, nodes=1002, timing={'material_s': 0.9})
    lv = S.levels(rec)
    assert [L['role'] for L in lv] == ['context', 'main', 'hero'] and lv[2]['x0'] == 191.406 and lv[2]['side'] == 500
    cam = V.Camera.from_record(rec)
    near(cam.heading_deg, 180.0, 1e-9, 'heading')
    near(cam.pitch_deg, 2.98, 1e-9, 'pitch')
    px, py, _z = cam.project(441.4, 2472.7 - 1000.0, 898.9 + 1000.0 * math.tan(math.radians(2.98)))
    near(float(px), 480.0, 1e-6, 'a point straight ahead lands mid-picture')
    near(float(py), 270.0, 1e-6, 'a point straight ahead lands mid-picture')
    c = C.render_cost(rec, 'aerial')
    assert c['compile_s'] == 24.9 and c['material_s'] == 0.9 and c['verdict'] == 'pass', c
    assert C.render_cost(dict(rec, second_render_s=9.0), 'eye')['verdict'] == 'fail'
    assert C.render_cost({}) == {}
    print('  levels parsed, the camera rebuilt, the cost read against the budgets')


def test_far_edges():
    """Where the far material begins (baseline.far_edges): rings lying beyond 1.5 far_m of every camera built with
    the view take it (surfacing.far_rings' rule); the edge is the window of the first near ring inside a far one. A
    record that lists its own far_edges (review_views.py since 11-20) is read as it is."""
    from surfacing_judge import baseline as B
    lv = ['Level(0 context 224000 m @ 218.8 m x1024, x0 -112000 y0 -112000, prepass [256, 512])',
          'Level(1 context 112000 m @ 109.4 m x1024, x0 -56000 y0 -56000)',
          'Level(2 context 56000 m @ 54.69 m x1024, x0 -28000 y0 -28000)',
          'Level(3 context 28000 m @ 27.34 m x1024, x0 -14000 y0 -14000)',
          'Level(4 main 14000 m @ 13.67 m x1024, x0 -7000 y0 -7000)']
    # the caldera's aerial_far and low_oblique of 11-20, built together: D0 5469 m, so 8203 m
    rec = dict(levels=lv, far_material=True, far_m=5468.75, camera=[-25700.0, -11600.0, 10391.4])
    two = dict(rec, views_built_together=['other'])
    other = {'camera': [1562.4, -5095.8, 1405.5]}
    import surfacing_judge.states as S
    keep = S.record
    S.record = lambda recipe, view, state: other if view == 'other' else {}
    try:
        e = B.far_edges(two, 'caldera', 'x')
    finally:
        S.record = keep
    assert e == [(-56000.0, -56000.0, 56000.0, 56000.0)], e          # ring 0 far, rings 1-4 near
    # the aerial alone, 28 km out: rings 1 and 2 hold it, so ring 0 and rings 3-4 (11.7 km and more away) are far
    assert B.far_edges(rec) == [(-56000.0, -56000.0, 56000.0, 56000.0), (-14000.0, -14000.0, 14000.0, 14000.0)]
    # a camera at the centre: rings 0-2 far (14 km and more), rings 3-4 near: the edge is ring 3's window
    assert B.far_edges(dict(rec, camera=[0.0, 0.0, 600.0])) == [(-14000.0, -14000.0, 14000.0, 14000.0)]
    assert B.far_edges(dict(rec, far_material=False)) == []
    assert B.far_edges(dict(rec, far_edges=[[-1, -2, 3, 4]])) == [(-1.0, -2.0, 3.0, 4.0)]
    print('  the far material begins at the 112 km window for the caldera aerial built with its low oblique, also at '
          'the 28 km one for the aerial alone, at the 28 km one for a camera at the centre; a record\'s own list is '
          'read as it is')


def test_board():
    from surfacing_judge import baseline as B
    from surfacing_judge import board as BD
    from surfacing_judge import states as S
    from PIL import Image
    H, W = 540, 960
    w = np.zeros((3, H, W))
    w[0, :, :600] = 1.0                                    # a large single layer on the left
    w[1, :, 600:] = 1.0
    w[2, 300:, 600:] = 1.0                                 # an edge-rich corner on the right
    w[1, 300:, 600:] = 0.0
    alpha = np.ones((H, W))
    alpha[:100] = 0.0                                      # sky
    lay = LY.encode_layer_map(w, alpha)
    render = (RNG.random((H, W, 3)) * 255).astype(np.uint8)
    old = S.STATES
    with tempfile.TemporaryDirectory() as d:
        S.STATES = d
        try:
            folder = os.path.join(d, 'probe', 'canyon')
            os.makedirs(folder)
            Image.fromarray(render).save(os.path.join(folder, 'approach_walk.png'))
            Image.fromarray((lay * 255).round().astype(np.uint8), 'RGBA').save(
                os.path.join(folder, 'approach_walk_layers.png'))
            v = dict(name='approach_walk', kind='eye', cam=[0.0, 0.0], cam_z=['ground', 1.7], aim=[0.0, 100.0, 0.0],
                     lens=35.0, frame=[0.5, 0.5], focus=True, photo=None, caption='a probe')
            got, ground, _ws, _info = LY.decode_layer_map(M.load_rgba(os.path.join(folder, 'approach_walk_layers.png')),
                                                          3)
            crops = BD.pick_crops(v, got, ground)
            (ax0, ay0, ax1, ay1), (bx0, by0, bx1, by1) = crops
            assert ax1 <= 640 and ay0 >= 90, crops                      # inside the large left layer
            assert bx0 >= 450 and abs((by0 + by1) / 2 - 300) < 90, crops  # on the edges at the right corner
            row = BD.view_row('canyon', v, 'probe', 'probe')
            assert row.size == (4 * BD.TW, 46 + BD.TH + 40 + 2 * BD.CH), row.size
        finally:
            S.STATES = old
    cam = V.Camera.from_heading((0.0, 0.0, 1.7), 0.0, -5.0, 35.0)
    r0, r1 = B.rows_for_band(cam, 25, 50)
    for d, row in ((50.0, r0), (25.0, r1)):                 # level ground 1.7 m under the eye, d metres out
        _px, py, _z = cam.project(0.0, math.sqrt(d * d - 1.7 * 1.7), 0.0)
        near(float(py), row, 1.0, f'the row of level ground {d:.0f} m out')
    assert B._cmp(0.105, 0.1)['within'] and not B._cmp(0.12, 0.1)['within'] and B._cmp(0.004, 0.0)['within']
    print(f'  a board row from a frozen state; crops {crops}; distance bands on their rows')


def test_targets():
    assert M.verdict('seam_delta_e', 2.0) == 'pass' and M.verdict('seam_delta_e', 2.1) == 'fail'
    assert M.verdict('plants_edge_ratio', 1.05) == 'pass' and M.verdict('plants_edge_ratio', 0.85) == 'fail'
    assert M.verdict('largest_region', 0.9) is None, 'a diagnostic is not a gate'
    assert M.flag('largest_region', 0.55, 0.40) and not M.flag('largest_region', 0.45, 0.40)
    assert M.flag('largest_region', 0.9, None) is False, 'no reference, no flag'
    assert M.flag('variation_ratio', 0.4) and not M.flag('variation_ratio', 0.6)
    assert M.flag('repetition', 0.2) and M.flag('repetition_energy', 0.7) and not M.flag('repetition_energy', 0.9)
    assert M.flag('height_line_index', 0.9) is None and M.flag('largest_region', None) is None
    assert abs(M.RANDOM_CONTOUR - 0.6366) < 1e-4
    print('  section 6\'s gates and the diagnostics\' flags')


def test_reference():
    H, W = 180, 320
    yy, xx = np.mgrid[0:H, 0:W]
    photo = np.zeros((H, W, 3))
    photo[...] = (0.55, 0.45, 0.35)                                  # a sandy left half
    photo[:, W // 2:] = (0.25, 0.35, 0.18)                           # a green right half, its own grain
    photo += 0.04 * RNG.standard_normal((H, W, 1))
    photo = np.clip(photo, 0, 1)
    ground = np.ones((H, W), bool)
    ground[:30] = False                                              # sky
    r = M.reference_one_material(photo, ground, 2)
    near(r['largest'], 0.5, 0.03, 'two halves: the larger class region')
    quad = photo.copy()
    quad[H // 2:, :W // 2] = (0.6, 0.6, 0.62)
    quad[H // 2:, W // 2:] = (0.15, 0.12, 0.10)
    r4 = M.reference_one_material(quad, ground, 4)
    assert r4['largest'] < 0.33, r4
    # repetition's energy: a blurred texture loses its fine detail, and the energy says so
    tex = _one_over_f((160, 300), RNG)
    tex = (tex - tex.min()) / np.ptp(tex)
    e_sharp = M.repetition(tex, mode='2d')['energy']
    e_soft = M.repetition(M.gaussian_blur(tex, 3.0), mode='2d')['energy']
    assert e_soft < 0.5 * e_sharp, (e_soft, e_sharp)
    # colour after exposure matching: the same ground half as bright reads the same
    dim = M.linear_to_srgb(M.srgb_to_linear(photo) * 0.5)
    c = M.colour_compare(dim, ground, photo, ground)
    assert c['delta_e'] < 0.5 and c['delta_e_raw'] > 10.0 and abs(c['exposure_scale'] - 2.0) < 0.05, c
    print(f"  the photograph's own largest region {r['largest']:.2f} (halves), {r4['largest']:.2f} (quarters); "
          f"blur halves the energy; exposure matched dE {c['delta_e']:.2f} (raw {c['delta_e_raw']:.1f})")


def main(argv):
    only = argv[argv.index('-k') + 1] if '-k' in argv else ''
    tests = [(k, v) for k, v in globals().items() if k.startswith('test_') and callable(v) and only in k]
    failed = 0
    for name, fn in tests:
        try:
            print(f'{name[5:]}:')
            fn()
            print(f'[PASS] {name[5:]}')
        except Exception as e:                           # noqa: BLE001 - every test reports
            import traceback
            traceback.print_exc()
            failed += 1
            print(f'[FAIL] {name[5:]}: {type(e).__name__}: {e}')
    print(f'{len(tests) - failed} of {len(tests)} passed')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
