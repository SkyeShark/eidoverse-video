"""The look package's checks (SURFACING_DESIGN.md 3.1, 3.2, 3.6, 5.3): plain Python, no Blender, no GPU.

    python blender/tests/terrain/surface_look/test_look.py [--skip-keys]

1. Cache keys (test_cache_keys.py, which runs on its own too): every recipe's terrain cache key, and real_place's
   under each place, built with the palettes.py of the last commit and with this checkout's, must be the same: a
   look edit never regenerates a cached terrain.
2. Every palette, every recipe's 'auto' palette and every real place's palette resolves and passes check().
3. Ramps: ramp_rows has one row per ramp, each the ramp's colour at its texels; the patches get() writes for a ramp
   multiply out to the ramp; the satmap's row is the multiplier it draws.
4. known_mask accepts the surface data bake's map names; the material's masks fit the mesh attribute budget (more
   than ATTRS_DIRECT masks are read packed three to an attribute; 14 attributes compile).
5. The looks' noise share (design 3.2, rule 1): in the weights a look writes, the world-noise terms inside a
   smoothstep move its argument by at most a quarter of its window, unless the line says why not.
6. The photograph colour sampler: sample_photo.retint keeps an albedo whose render already matches the photograph,
   and gives the same albedo whatever the photograph's exposure.
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
BLENDER_DIR = os.path.normpath(os.path.join(TN, '..', '..'))
for _p in (BLENDER_DIR, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def check_cache_keys(log=print):
    import test_cache_keys
    return test_cache_keys.check(log)


def check_palettes(P, log=print):
    from eidoblend.terrain import recipes as R
    bad = []
    for nm in P.names():
        try:
            P.get(nm)
        except Exception as e:                           # noqa: BLE001
            bad.append(f'{nm}: {e}')
    for rn in R.names():
        try:
            P.get('auto', recipe=R.resolve(rn))
        except Exception as e:                           # noqa: BLE001
            bad.append(f'auto/{rn}: {e}')
    for place in P.PLACES:
        try:
            P.for_place(place)
        except Exception as e:                           # noqa: BLE001
            bad.append(f'place {place}: {e}')
    log(f'[palettes] {len(P.names())} palettes, {len(R.names())} recipes, {len(P.PLACES)} places: '
        + ('all resolve and check' if not bad else f'{len(bad)} problems: {bad}'))
    return bad


def _all_palettes(P):
    from eidoblend.terrain import recipes as R
    out = {nm: P.get(nm) for nm in P.names()}
    for rn in R.names():
        out['auto/' + rn] = P.get('auto', recipe=R.resolve(rn))
    for place in P.PLACES:
        out['place/' + place] = P.for_place(place)[0]
    return out


def check_ramps(P, log=print):
    bad = []
    pals = _all_palettes(P)
    n_ramps = 0
    for key, pal in pals.items():
        rows, index = P.ramp_rows(pal)
        want = [L['name'] for L in pal['layers'] if L.get('ramp')] + (['satmap'] if pal['options'].get('satmap')
                                                                       else [])
        if sorted(index) != sorted(want) or rows.shape[0] != len(want) or (rows.size and rows.shape[1:] != (256, 4)):
            bad.append(f'{key}: rows {rows.shape} for {want}')
            continue
        tt = np.linspace(0.0, 1.0, 256)
        for L in pal['layers']:
            r = L.get('ramp')
            if not r:
                continue
            n_ramps += 1
            ent = index[L['name']]
            lin = P.srgb_to_linear(rows[ent['row'], :, :3]) * ent['gain']
            ref = P.ramp_value(r, tt)
            if np.abs(lin - ref).max() > 0.01 * max(1.0, ref.max()):
                bad.append(f"{key} {L['name']}: row off the ramp by {np.abs(lin - ref).max():.4f}")
            # the patches get() wrote multiply out to the ramp (the material's attribute path draws it this way)
            centre = (np.array(P.hex_linear(L['colour'])) if ent['kind'] == 'colour' else np.ones(3))
            rp = [pt for pt in P._patches(L) if pt.get('from_ramp') == 'ramp']
            for t in (0.0, 0.17, 0.5, 0.83, 1.0):
                col = centre.copy()
                for pt in rp:
                    w = float(P.evaluate(_where_at(pt['where'], r['t'], t), {})) if pt.get('where') else 1.0
                    col = col + w * float(pt.get('amount', 1.0)) * (col * np.array(pt['tint']) - col)
                if np.abs(col - P.ramp_value(r, t)).max() > 1e-6 * max(1.0, float(col.max())) + 1e-9:
                    bad.append(f"{key} {L['name']}: patches give {col} at t={t}, the ramp {P.ramp_value(r, t)}")
                    break
    log(f'[ramps] {n_ramps} layer ramps over {len(pals)} resolved palettes: '
        + ('rows and patches reproduce every ramp' if not bad else f'{len(bad)} problems: {bad[:6]}'))
    return bad


def _where_at(where, t_expr, t):
    """A ramp patch's `where` with its terrain term replaced by the number t (the patch reads t through it)."""
    return where.replace(f'({t_expr})', repr(float(t))).replace(str(t_expr), repr(float(t)))


def check_names_and_budget(P, log=print):
    from eidoblend.terrain import masks as M
    bad = []
    for nm in P.SURFACE_MAPS:
        if P.known_mask(nm):
            bad.append(f'known_mask rejects {nm!r}')
    try:
        from eidoblend.terrain.surface import maps as SM
        reg = getattr(SM, 'MAPS', None) or {}
        for nm in (reg.keys() if isinstance(reg, dict) else []):
            if isinstance(nm, str) and P.known_mask(nm):
                bad.append(f'known_mask rejects the registry map {nm!r}')
    except Exception:                                    # noqa: BLE001 - the bake needs Blender or is not there
        pass
    attrs_direct = 10                                    # surfacing.ATTRS_DIRECT (no bpy here)
    surface = set(P.surface_maps())
    n_surface = 0
    for key, pal in _all_palettes(P).items():
        used = P.material_masks(pal)
        # a material without baked data reads every name as a mesh attribute, the surface data's maps too (packed
        # with the masks, written as 0 by pack_masks: the looks are written so that 0 is their neutral value, or a
        # layer's fallback stands in), so all of them count toward the attribute budget
        n_attr = len(used) if len(used) <= attrs_direct else (len(used) + 2) // 3
        if n_attr > 14:
            bad.append(f'{key}: {len(used)} masks need {n_attr} attributes (14 compile)')
        missing = sorted(m for m in used if m not in M.DEFAULT_NAMES and m not in ('strata',) and m not in surface)
        if missing:
            bad.append(f'{key}: reads {missing}, neither a mask the ring mesh carries nor a surface data map')
        n_surface += bool(used & surface)
        for L in pal['layers']:
            # a weight whose cover comes from a map only the bake makes (the plant layer's rasters, the snowpack) needs
            # a fallback, the weight a material without them takes (SURFACING_DESIGN.md 5.3); a term on another map is
            # written to be neutral at 0 (palettes._has)
            only = P.names_in(L['weight']) & {'canopy_expected', 'canopy_far', 'canopy', 'shrubs', 'shrubs_far',
                                              'snowpack'}
            if only and L.get('fallback') is None:
                bad.append(f"{key}/{L['name']}: its weight reads {sorted(only)} and it has no fallback")
    log('[names] ' + (f'known_mask takes the bake\'s maps; every material fits the attribute budget; {n_surface} '
                      f'palettes read the surface data, and every weight on a map only the bake makes has a fallback'
                      if not bad else f'{len(bad)} problems: {bad}'))
    return bad


def _noise_span(t):
    """How far the world-noise terms of an expression tree can move it: the sum over its additive terms of
    |factor| x the noise's span (1 for noise/fbm/cells), with masks taken at most 1 in a product; 0 without noise."""
    k = t[0]
    if k in ('num', 'const', 'mask'):
        return 0.0
    if k == 'neg':
        return _noise_span(t[1])
    if k == 'call':
        if t[1] in ('noise', 'fbm', 'cells'):
            return 1.0
        if t[1] in ('smoothstep',):
            return 0.0                                   # bounded inside its own window: checked on its own
        return max((_noise_span(a) for a in t[2]), default=0.0)
    if k == 'op':
        a, b = t[2], t[3]
        if t[1] in '+-':
            return _noise_span(a) + _noise_span(b)
        if t[1] == '*':
            if a[0] == 'num':
                return abs(a[1]) * _noise_span(b)
            if b[0] == 'num':
                return abs(b[1]) * _noise_span(a)
            return max(_noise_span(a), _noise_span(b))
        if t[1] == '/':
            return _noise_span(a) / abs(b[1]) if b[0] == 'num' and b[1] else _noise_span(a)
    return 0.0


def noise_shares(P, expr):
    """[(e0, e1, span, share)] for every smoothstep(e0, e1, x) in expr: the span its noise terms move x by, and that
    over the window |e1 - e0|."""
    out = []

    def walk(n):
        if n[0] == 'call':
            if n[1] == 'smoothstep' and n[2][0][0] == 'num' and n[2][1][0] == 'num':
                e0, e1 = n[2][0][1], n[2][1][1]
                sp = _noise_span(n[2][2])
                if sp > 0:
                    out.append((e0, e1, sp, sp / max(abs(e1 - e0), 1e-9)))
            for a in n[2]:
                walk(a)
        elif n[0] == 'op':
            walk(n[2])
            walk(n[3])
        elif n[0] == 'neg':
            walk(n[1])
    walk(P.parse(expr))
    return out


def check_noise_share(P, log=print, limit=0.25):
    """The looks' own weights (PALETTE_LOOKS, RECIPE_LOOKS entries that set a weight): every smoothstep's noise span
    at most `limit` of its window. Tiny tufts and speckle layers whose pattern IS a noise (a 1-2 m noise drawing
    shrubs or grass tufts) are named in NOISE_PATTERN_LAYERS and skipped."""
    bad = []
    n = 0
    looks = [('palette ' + k, v) for k, v in getattr(P, 'PALETTE_LOOKS', {}).items()] + \
            [('recipe ' + k, v) for k, v in P.RECIPE_LOOKS.items() if k in LOOKS_UNDER_RULE]
    for tag, look in looks:
        for lname, d in (look.get('layers') or {}).items():
            if 'weight' not in d or (tag, lname) in NOISE_PATTERN_LAYERS:
                continue
            for e0, e1, sp, share in noise_shares(P, d['weight']):
                n += 1
                if share > limit + 1e-9:
                    bad.append(f'{tag} {lname}: smoothstep({e0:g}, {e1:g}) moved {sp:g} by noise ({share:.2f} of it)')
    log(f'[noise] {n} thresholds in the looks\' weights: ' + ('every noise share within a quarter of its window'
                                                            if not bad else f'{len(bad)} over: {bad}'))
    return bad


# the recipe looks written under the 3.2 rule (the others are from before it, and keep their own noise until they are
# rewritten); and the layers whose pattern is a random partition by design: farmland's fields are whole cells of a
# Voronoi partition (cells()), each field one crop, so their edge is the partition's and not a threshold broken by noise
LOOKS_UNDER_RULE = set()
NOISE_PATTERN_LAYERS = {('palette farmland', 'soil'), ('palette farmland', 'crop')}


def check_sampler(log=print):
    """sample_photo.retint: the old albedo back when the render already has the photograph's colour, and the same
    albedo whatever the photograph's exposure (its colour scaled by 0.5 or 2 in linear light). Skipped without the
    light chart (surfacing/calibrate_light.py renders it into out/surfacing/calibration/)."""
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    import sample_photo as SPH
    if not os.path.exists(SPH.CHART):
        log('[skip] sampler: no light chart (run blender/tests/terrain/surfacing/calibrate_light.py)')
        return None
    chart = SPH.Chart(SPH.CHART, 'flat')
    bad = []
    old = np.array([0.33, 0.16, 0.08])
    lab = np.array([45.0, 8.0, 12.0])
    same = SPH.retint(old, lab, lab, chart)
    if np.abs(same - old).max() > 1e-6:
        bad.append(f'retint changes an albedo whose render matches the photograph: {same}')
    outs = []
    for k in (0.5, 1.0, 2.0):
        p = SPH.srgb_to_lab(SPH.linear_to_srgb(np.array([0.30, 0.18, 0.09]) * k))
        outs.append(SPH.retint(old, lab, p, chart))
    spread = max(np.abs(o - outs[1]).max() for o in outs)
    if spread > 0.02 * float(np.max(outs[1])):
        bad.append(f'retint moves with the photograph\'s exposure by {spread:.4f}')
    log('[sampler] retint ' + ('keeps a matching albedo and ignores the photograph\'s exposure (within '
                              f'{100 * spread / float(np.max(outs[1])):.1f} %)' if not bad else f'FAILS: {bad}'))
    return bad


def main():
    from eidoblend.terrain.build import palettes as P
    skip_keys = '--skip-keys' in sys.argv
    fails = 0
    if not skip_keys:
        bad = check_cache_keys()
        fails += bool(bad)
    fails += bool(check_palettes(P))
    fails += bool(check_ramps(P))
    fails += bool(check_names_and_budget(P))
    fails += bool(check_noise_share(P))
    fails += bool(check_sampler())
    print('[test_look] ' + ('all checks pass' if not fails else f'{fails} checks FAIL'))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
