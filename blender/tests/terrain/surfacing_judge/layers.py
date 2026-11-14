"""A palette's layers on a terrain, three ways (numpy; no bpy):

    from surfacing_judge import layers as LY
    pal = LY.palette(stack)                          # the recipe's 'auto' palette (or a name, or a dict)
    E = LY.weights(pal, masks, X, Y, consts)         # (layers, n, n): each layer's weight on a level, composited
                                                     # as the material does (a layer covers what lies below it)
    t = LY.main_tile(stack)                          # E, names, h, cell, slope of the main level

    w, ground, water, info = LY.decode_layer_map(rgba, n_layers)
        # the material's own weights per pixel, from a layer-map render (review_views.py --layers: the palette's
        # debug='layers' emission in the Standard view transform, transparent film, water black)

    w, seen = LY.frame_splat(stack, pal, camera)     # the layers a camera sees, with no render: every cell of the
                                                     # context and main levels splatted into the camera

The numpy weights use palettes.evaluate, whose noise() and fbm() are a value noise standing in for the shader's: the
breakup's pattern differs from the render's, its statistics do not. They carry no height blend and no hero levels.
The decoded layer map is the shader's own result.
"""
from __future__ import annotations

import ast
import itertools
import os

import numpy as np

from . import BLENDER_DIR
from . import measures as M

WATER_COLOUR = (0.0, 0.0, 0.0)            # what review_views.py --layers paints lakes and the sea
# masks whose edges are the rock column's beds: frozen (excl_strata) when the height-line index leaves bed edges out
STRATA_MASKS = ('strata', 'strata_dz', 'src_strata', 'src_dz', 'ledge')


def _palettes():
    from eidoblend.terrain.build import palettes as P
    return P


def debug_colours():
    """The flat colour of each layer in a layer map, bottom layer first: build/surfacing.py's DEBUG_COLOURS, read
    from its source (the module itself needs bpy)."""
    path = os.path.join(BLENDER_DIR, 'eidoblend', 'terrain', 'build', 'surfacing.py')
    with open(path, encoding='utf-8') as f:
        tree = ast.parse(f.read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, 'id', None) == 'DEBUG_COLOURS' for t in node.targets):
            return [tuple(float(v) for v in c) for c in ast.literal_eval(node.value)]
    raise RuntimeError('build/surfacing.py no longer defines DEBUG_COLOURS')


def layer_colours(n):
    c = debug_colours()
    return [c[i % len(c)] for i in range(n)]


def palette(stack_or_recipe, palette='auto'):
    """The filled-in palette dict the material gets: 'auto' resolved with the recipe itself (make_terrain passes the
    Recipe, whose own defaults can name a palette of its own: tower_karst's and sea_cliffs' add layers, the layered
    recipes add their rock column; the recipe's name alone reaches only palettes.RECIPE_PALETTES), or a real place's
    when the terrain is real_place with a DEM palettes.PLACES knows."""
    P = _palettes()
    if isinstance(palette, dict):
        return P.get(palette)
    recipe = getattr(stack_or_recipe, 'recipe', stack_or_recipe)
    knobs = getattr(stack_or_recipe, 'knobs', None) or {}
    if palette == 'auto' and recipe == 'real_place' and knobs.get('dem') in P.PLACES:
        return P.for_place(knobs['dem'])[0]
    if isinstance(recipe, str):
        from eidoblend.terrain import recipes as R
        recipe = R.get(recipe)
    return P.get(palette, recipe=recipe)


def weights(pal, masks, X, Y, consts, freeze=()):
    """Every layer's weight on a level: palettes.evaluate of each layer's weight expression on the level's masks,
    composited in order. freeze: mask names read at their median instead (the height-line index without the rock
    column's bed edges: freeze=STRATA_MASKS)."""
    P = _palettes()
    mk = {k: np.asarray(v, np.float64) for k, v in masks.items()}
    for k in freeze:
        if k in mk:
            mk[k] = np.full_like(mk[k], float(np.median(mk[k])))
    cov = [np.clip(P.evaluate(L['weight'], mk, X, Y, consts), 0.0, 1.0) for L in pal['layers']]
    return M.exclusive(cov)


def reads_strata(pal):
    """The strata masks the palette's layer weights read (none of today's palettes: the column colours the layers,
    it does not place them)."""
    P = _palettes()
    out = set()
    for L in pal['layers']:
        out |= P.names_in(L['weight']) & set(STRATA_MASKS)
    return sorted(out)


def main_tile(stack, pal='auto', freeze=()):
    """The palette's layers on the main level of a saved terrain: dict(E, names, sets, h, cell, slope, pal)."""
    pal = palette(stack, pal) if not (isinstance(pal, dict) and 'options' in pal) else pal
    mk = stack.masks('main')
    X, Y = stack.xy('main')
    E = weights(pal, mk, X, Y, stack.constants(pal), freeze)
    lv = stack.levels[stack.main]
    h = np.asarray(stack.fields[stack.main]['h'], np.float64)
    return dict(E=E, names=[L['name'] for L in pal['layers']], sets=[L['set'] for L in pal['layers']], h=h,
                cell=float(lv['cell']), slope=np.asarray(mk['slope'], np.float64), pal=pal, level=lv)


# ------------------------------------------------------------------------------------ the layer-map render ---

def decode_layer_map(rgba, n_layers, water=True, tol=0.02, alpha_min=0.5):
    """A layer-map render back into the material's weights per pixel.

    rgba       (H, W, 4) float 0..1, sRGB-encoded colour, straight alpha: review_views.py --layers
    n_layers   the palette's layer count (its colours are debug_colours()[:n_layers])
    water      lakes and the sea are painted WATER_COLOUR (black): decoded as their own class
    Returns (w, ground, water_share, info):
        w            (n_layers, H, W) weights, 0 off the ground
        ground       (H, W) bool: terrain covers the pixel (alpha >= alpha_min) and under half of it is water
        water_share  (H, W) the water's share of each pixel
        info         dict(unresolved: the share of terrain pixels no mix of up to three layers explains within tol,
                     residual_p99, mixes: the shares decoded as one, two and three layers)

    Each pixel's colour is a mix of the layers' flat colours by their weights. Six colours in three channels do not
    unmix uniquely in general, but the material blends by height, so nearly every pixel is one layer or a mix of two:
    the decode takes the best-fitting pair, then the best triple where no pair fits (the colours are all corners of
    their hull, and no two of the segments between them pass within 0.03 of each other). Water is tried only where
    no mix of layers fits: a little black in a pale layer looks like a little of a darker layer."""
    rgba = np.asarray(rgba, np.float64)
    H, W = rgba.shape[:2]
    alpha = rgba[..., 3] if rgba.shape[2] > 3 else np.ones((H, W))
    terrain = alpha >= alpha_min
    cols = [np.array(c) for c in layer_colours(n_layers)]
    if water:
        cols.append(np.array(WATER_COLOUR))
    C = np.stack(cols)
    K = len(C)
    p = M.srgb_to_linear(rgba[..., :3])[terrain]
    N = len(p)
    wk = np.zeros((N, K))
    wk[:, 0] = 1.0
    best = np.linalg.norm(p - C[0], axis=1)
    order = np.ones(N, np.int8)

    def fit(sel, members):
        """The best mix of two, then of three, of the colours `members` for the pixels `sel` (indices)."""
        q = p[sel]
        bq, wq, oq = best[sel].copy(), wk[sel].copy(), order[sel].copy()
        for a, b in itertools.combinations(members, 2):
            d = C[b] - C[a]
            t = np.clip((q - C[a]) @ d / (d @ d), 0.0, 1.0)
            res = np.linalg.norm(q - (C[a] + t[:, None] * d), axis=1)
            k = res < bq
            bq[k] = res[k]
            wq[k] = 0.0
            wq[k, a] = 1.0 - t[k]
            wq[k, b] = t[k]
            oq[k] = np.where((t[k] > 0.02) & (t[k] < 0.98), 2, 1)
        todo = bq > tol
        if todo.any() and len(members) >= 3:
            q3 = q[todo]
            b3, w3, o3 = bq[todo].copy(), wq[todo].copy(), oq[todo].copy()
            for a, b, c in itertools.combinations(members, 3):
                A = np.stack([C[a] - C[c], C[b] - C[c]], 1)                # 3 x 2
                uv = np.linalg.lstsq(A, (q3 - C[c]).T, rcond=None)[0].T     # (n, 2)
                bary = np.concatenate([uv, 1.0 - uv.sum(1, keepdims=True)], 1)
                res = np.linalg.norm(q3 - (C[c] + uv @ A.T), axis=1)
                k = (bary >= -1e-3).all(1) & (res < b3)
                if k.any():
                    b3[k] = res[k]
                    w3[k] = 0.0
                    bc = np.clip(bary[k], 0.0, 1.0)
                    bc /= bc.sum(1, keepdims=True)
                    w3[k, a], w3[k, b], w3[k, c] = bc[:, 0], bc[:, 1], bc[:, 2]
                    o3[k] = 3
            bq[todo], wq[todo], oq[todo] = b3, w3, o3
        best[sel], wk[sel], order[sel] = bq, wq, oq

    if n_layers > 1:
        fit(np.arange(N), range(n_layers))
    if water:
        left = np.flatnonzero(best > tol)
        if left.size:
            fit(left, range(K))
    w = np.zeros((n_layers, H, W))
    for i in range(n_layers):
        w[i][terrain] = wk[:, i]
    water_share = np.zeros((H, W))
    if water:
        water_share[terrain] = wk[:, K - 1]
    ground = terrain & (water_share < 0.5)
    info = dict(terrain_px=int(N), unresolved=float((best > tol).mean()) if N else 0.0,
                residual_p99=float(np.percentile(best, 99)) if N else 0.0,
                mixes={str(k): float((order == k).mean()) if N else 0.0 for k in (1, 2, 3)},
                water=float(water_share[terrain].mean()) if N else 0.0)
    return w, ground, water_share, info


def encode_layer_map(w, alpha=None, water_share=None):
    """The picture a layer-map render of these weights would be: (H, W, 4) float sRGB with straight alpha (the
    decode's inverse, for tests and for drawing a splat as a layer map)."""
    w = np.asarray(w, np.float64)
    C = np.array(layer_colours(w.shape[0]))
    lin = np.tensordot(w, C, axes=(0, 0))
    if water_share is not None:
        lin = lin * (1.0 - np.asarray(water_share)[..., None]) + np.array(WATER_COLOUR) * water_share[..., None]
    a = np.ones(w.shape[1:]) if alpha is None else np.asarray(alpha, np.float64)
    return np.concatenate([M.linear_to_srgb(lin), a[..., None]], 2)


# ------------------------------------------------------------------------- the layers a camera sees (no render) ---

def frame_splat(stack, pal, cam, size=(240, 135), log=None):
    """The palette's layers as a camera sees them, without a render: every cell of the saved terrain's levels (up to
    the main one) is splatted into the camera with a depth buffer, the finer level winning where two overlap. cam: a
    views.Camera. Returns (w (layers, h, w), seen (h, w) bool). The near ground of an eye-level view is drawn by hero
    levels this does not have, and one cell covers many pixels there: the splat leaves holes near the camera (seen is
    False), so read it for aerial views and take the layer-map render for the rest."""
    Wd, Hd = size
    depth = np.full(Hd * Wd, np.inf)
    out = None
    n = stack.main + 1
    for k in range(n):
        lv = stack.levels[k]
        X, Y = stack.xy(k)
        E = weights(pal, stack.masks(k, log=log), X, Y, stack.constants(pal))
        if out is None:
            out = np.zeros((E.shape[0], Hd * Wd))
        Z = np.asarray(stack.fields[k]['h'], np.float64)
        px, py, zc = cam.project(X.ravel(), Y.ravel(), Z.ravel(), size)
        ok = (zc > 1.0) & (px >= 0) & (px < Wd) & (py >= 0) & (py < Hd)
        if k + 1 < n:                                   # the cells a finer level covers are that level's
            f = stack.levels[k + 1]
            ok &= ~((X.ravel() >= f['x0']) & (X.ravel() <= f['x0'] + f['side'])
                    & (Y.ravel() >= f['y0']) & (Y.ravel() <= f['y0'] + f['side']))
        idx = np.flatnonzero(ok)
        if not idx.size:
            continue
        pix = py[idx].astype(np.int64) * Wd + px[idx].astype(np.int64)
        zz = zc[idx]
        o = np.lexsort((zz, pix))
        pix, zz, idx = pix[o], zz[o], idx[o]
        first = np.r_[True, pix[1:] != pix[:-1]]
        pix, zz, idx = pix[first], zz[first], idx[first]
        nearer = zz < depth[pix]
        pix, zz, idx = pix[nearer], zz[nearer], idx[nearer]
        depth[pix] = zz
        out[:, pix] = E.reshape(E.shape[0], -1)[:, idx]
    return out.reshape(-1, Hd, Wd), np.isfinite(depth).reshape(Hd, Wd)
