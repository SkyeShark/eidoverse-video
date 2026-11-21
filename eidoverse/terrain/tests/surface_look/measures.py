"""The surfacing judge's measures on the port's renders, beside the same measures on Blender's (PORT_PLAN.md 8.2 row
P18; SURFACING_DESIGN.md 5.4 package 3 item 3 and section 6: diagnostics beside the boards, each read against the
place's photograph; the eye decides).

    python -B eidoverse/terrain/tests/surface_look/measures.py --state <label> [--ref final2] [--recipes a,b]
           [--views a,b] [--no-seams]
    (system Python: numpy and Pillow, as the judge runs; -B, so nothing is written into the Blender edition, which is
    found at $EIDO_BLENDER_EDITION and only read)

The measures are the judge's own code, used as it is: surfacing_judge/baseline.frame_measures (one-material share
against the photograph's, within-layer variation, the ground's colour after exposure matching against the
photograph's, repetition in ground windows with its energy against the --ref render of the same camera, the colour
step across each level window's edge), on the port's state (tests/out/surface_look/states/<label>/<recipe>/: a frozen
state, states.py's layout, read through states.STATES pointed there), each view on its own saved terrain (the plan's,
terrain_data.load with its hero levels: the render's own ground) and the palette of the code as it is now. Blender's
numbers are its own baseline of the --ref state (out/surfacing_judge/baseline_<ref>.json), made by the same code on the
same terrains and cameras.

Three readings of this package's own sit beside them, port against Blender on the same camera (both frames through
Blender's display transform, develop.py):
    frame     CIELAB means of the whole ground (both layer maps' ground) and the dE of the two; the dE per 32 px block,
              its median and 90th percentile, and the eight worst blocks (where a difference shows: the crops)
    layers    the two layer maps decoded (layers.decode_layer_map): each layer's share in each, and the share of
              ground pixels whose dominant layer is the same
    light     the port's scene-linear luminance over Blender's on the ground (Blender's frame taken back through the
              display table), its median over the ground and over Blender's brightest and darkest quarters; then the
              frame and block dE again with the port's frame brought to Blender's light (divided by that median); and
              where the clay probe exists (views.mjs --clay, blender_clay.py), the same ratio between the two clay
              frames, the renderers' light alone

Writes tests/out/surface_look/baseline_<label>.json (the shape of baseline.py's, so the judge's board reads it) and
compare_<label>.json (per view: Blender's numbers, the port's, the two readings).
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, '..', 'out', 'surface_look'))


def edition():
    root = os.environ.get('EIDO_BLENDER_EDITION', '')
    tn = os.path.join(root, 'blender', 'tests', 'terrain')
    if not root or not os.path.isdir(os.path.join(tn, 'surfacing_judge')):
        sys.exit('[measures] set EIDO_BLENDER_EDITION to the root of a checkout of the blender branch')
    if tn not in sys.path:
        sys.path.insert(0, tn)
    return root, tn


def judge(state_root):
    """The judge's modules, with states.STATES pointed at this package's states (a label there is a frozen state;
    any other state name is the Blender review's tag, as before)."""
    from surfacing_judge import baseline as BL, layers as LY, measures as M, states as S, views as V
    S.STATES = state_root
    return BL, LY, M, S, V


def block_lab(img, mask, block=32, cover=0.9):
    """(rows, cols, 3) CIELAB of each block where mask covers at least `cover` of it (NaN elsewhere)."""
    from surfacing_judge import measures as M
    H, W = img.shape[:2]
    h, w = H // block, W // block
    lab = M.srgb_to_lab(img[:h * block, :w * block]).reshape(h, block, w, block, 3)
    m = mask[:h * block, :w * block].reshape(h, block, w, block)
    cov = m.mean(axis=(1, 3))
    s = (lab * m[..., None]).sum(axis=(1, 3)) / np.maximum(m.sum(axis=(1, 3)), 1)[..., None]
    s[cov < cover] = np.nan
    return s


def compare_frames(M, LY, n_layers, port_png, port_layers, blender_png, blender_layers):
    """This package's readings of the port's frame against Blender's frame of the same camera."""
    a, b = M.load_rgb(port_png), M.load_rgb(blender_png)
    out = {}
    wa = wb = None
    ga = gb = None
    if port_layers and os.path.exists(port_layers):
        wa, ga, _wsa, ia = LY.decode_layer_map(M.load_rgba(port_layers), n_layers)
        out['port_layers_unresolved'] = ia.get('unresolved')
    if blender_layers and os.path.exists(blender_layers):
        wb, gb, _wsb, _ib = LY.decode_layer_map(M.load_rgba(blender_layers), n_layers)
    if ga is not None and gb is not None:
        ground = ga & gb
        out['ground_share'] = dict(port=float(ga.mean()), blender=float(gb.mean()), both=float(ground.mean()))
        da, db = wa.argmax(0), wb.argmax(0)
        out['dominant_layer_agreement'] = float((da[ground] == db[ground]).mean()) if ground.any() else None
        out['layer_shares'] = dict(port=[float(wa[i][ga].mean()) if ga.any() else 0.0 for i in range(n_layers)],
                                   blender=[float(wb[i][gb].mean()) if gb.any() else 0.0 for i in range(n_layers)])
    else:
        ground = np.ones(a.shape[:2], bool)
    if ground.any():
        la, lb = M.mean_lab(a, ground), M.mean_lab(b, ground)
        out['ground_lab'] = dict(port=[float(x) for x in la], blender=[float(x) for x in lb],
                                 delta_e=float(M.delta_e(np.asarray(la), np.asarray(lb))))
    ba, bb = block_lab(a, ground), block_lab(b, ground)
    de = np.linalg.norm(ba - bb, axis=-1)
    ok = np.isfinite(de)
    if ok.any():
        out['block_delta_e'] = dict(median=float(np.median(de[ok])), p90=float(np.percentile(de[ok], 90)),
                                    blocks=int(ok.sum()))
        order = np.argsort(np.where(ok, de, -1).ravel())[::-1][:8]
        worst = []
        for idx in order:
            j, i = np.unravel_index(idx, de.shape)
            if not ok[j, i]:
                continue
            worst.append(dict(box=[int(i * 32), int(j * 32), int(i * 32 + 32), int(j * 32 + 32)], delta_e=float(de[j, i]),
                              port_lab=[round(float(x), 1) for x in ba[j, i]],
                              blender_lab=[round(float(x), 1) for x in bb[j, i]]))
        out['worst_blocks'] = worst
    # L* of the whole frame and of the sky (off the ground in both layer maps), so a tone or light difference over the
    # whole picture reads apart from the ground's own
    out['frame_L'] = dict(port=float(M.srgb_to_lab(a)[..., 0].mean()), blender=float(M.srgb_to_lab(b)[..., 0].mean()))
    if ga is not None and gb is not None and (~ga & ~gb).any():
        sky = ~ga & ~gb
        out['sky_lab'] = dict(port=[float(x) for x in M.mean_lab(a, sky)], blender=[float(x) for x in M.mean_lab(b, sky)])
    # the light: the port's scene-linear frame (views.mjs' .f16) over Blender's frame taken back through the display
    # table (blender_display.py; each channel by the grey diagonal, close off grey), the median ratio of luminance on
    # the ground both draw, and on Blender's brightest and darkest quarter of it (sunlit, shaded)
    f16 = os.path.splitext(port_png)[0] + '.f16'
    if os.path.exists(f16) and ground.any():
        import develop as DV
        disp = DV.Display()
        g = 2.0 ** np.linspace(-14, 10, 6000)
        curve = disp(np.stack([g] * 3, -1))
        lb = np.stack([np.interp(b[..., c], np.maximum.accumulate(curve[:, c]), g) for c in range(3)], -1)
        raw, meta = DV.read_f16(f16)
        lp = DV.box(raw, int(meta.get('k', 1)))[..., :3]
        Y = np.array([0.2126, 0.7152, 0.0722])
        yb, yp = lb @ Y, lp @ Y
        ok = ground & (b.max(-1) < 0.995) & np.isfinite(yp)
        if ok.sum() > 1000:
            q0, q1 = np.percentile(yb[ok], [25, 75])
            med = lambda m: float(np.median(yp[m]) / max(np.median(yb[m]), 1e-9))   # noqa: E731
            out['linear_ratio'] = dict(ground=med(ok), brightest_quarter=med(ok & (yb >= q1)),
                                       darkest_quarter=med(ok & (yb <= q0)))
            # the same frame at Blender's light: the port's scene-linear frame over the ground's median ratio, through
            # the display table, against Blender's frame block by block (what is left is the ground's, not the light's)
            am = disp(lp / out['linear_ratio']['ground'])
            dm = np.linalg.norm(block_lab(am, ground) - block_lab(b, ground), axis=-1)
            okm = np.isfinite(dm)
            if okm.any():
                lam, lbm = M.mean_lab(am, ground), M.mean_lab(b, ground)
                out['light_matched'] = dict(ground_delta_e=float(M.delta_e(np.asarray(lam), np.asarray(lbm))),
                                            port_lab=[float(x) for x in lam], block_median=float(np.median(dm[okm])),
                                            block_p90=float(np.percentile(dm[okm], 90)))
        # the clay probe (views.mjs --clay beside blender_clay.py's render of the same view): the same light ratio on
        # grey clay, where the surfacing plays no part
        name = os.path.splitext(os.path.basename(port_png))[0]
        recipe = os.path.basename(os.path.dirname(port_png))
        bclay = os.path.join(OUT, 'clay', f'{recipe}_{name}_blender.png')
        pclay = os.path.splitext(port_png)[0] + '_clay.f16'
        if os.path.exists(bclay) and os.path.exists(pclay):
            cb = M.load_rgb(bclay)
            lcb = np.stack([np.interp(cb[..., c], np.maximum.accumulate(curve[:, c]), g) for c in range(3)], -1)
            raw, meta = DV.read_f16(pclay)
            lcp = DV.box(raw, int(meta.get('k', 1)))[..., :3]
            ycb, ycp = lcb @ Y, lcp @ Y
            okc = ground & (cb.max(-1) < 0.995) & np.isfinite(ycp)
            if okc.sum() > 1000:
                q0, q1 = np.percentile(ycb[okc], [25, 75])
                medc = lambda m: float(np.median(ycp[m]) / max(np.median(ycb[m]), 1e-9))   # noqa: E731
                out['clay_linear_ratio'] = dict(ground=medc(okc), brightest_quarter=medc(okc & (ycb >= q1)),
                                                darkest_quarter=medc(okc & (ycb <= q0)))
    return out


def main(argv):
    def opt(k, d=None):
        return argv[argv.index(k) + 1] if k in argv else d
    label = opt('--state', 'port')
    ref = opt('--ref', 'final2')
    only = set((opt('--recipes') or '').split(',')) - {''}
    only_views = set((opt('--views') or '').split(',')) - {''}
    root, tn = edition()
    state_root = os.path.join(OUT, 'states')
    BL, LY, M, S, V = judge(state_root)
    from surfacing_judge import terrain_data as TD
    plan_path = os.path.join(state_root, label, 'plan.json')
    with open(plan_path, encoding='utf-8') as f:
        plan = json.load(f)
    terrain_of = {tuple(k.split('/', 1)): v['terrain'] for k, v in (plan.get('views') or {}).items()}
    with open(os.path.join(tn, 'out', 'surfacing_judge', f'baseline_{ref}.json'), encoding='utf-8') as f:
        blender = json.load(f)
    out_json = os.path.join(OUT, f'baseline_{label}.json')
    res = dict(state=label, when=time.strftime('%Y-%m-%d %H:%M'), terrains='the views\' own (plan.json)', tile={},
               frames={}, energy_reference=ref)
    cmp_json = os.path.join(OUT, f'compare_{label}.json')
    cmp = {}
    for p, d in ((out_json, res['frames']), (cmp_json, cmp)):
        if os.path.exists(p):
            with open(p, encoding='utf-8') as f:
                old = json.load(f)
            d.update(old.get('frames', {}) if p == out_json else old)
    views = V.load()
    by_terrain = {}
    for (recipe, name), tpath in terrain_of.items():
        if (only and recipe not in only) or (only_views and name not in only_views):
            continue
        by_terrain.setdefault((recipe, tpath), []).append(name)
    for (recipe, tpath), names in sorted(by_terrain.items()):
        st = None
        if '--no-seams' not in argv:
            t0 = time.time()
            try:
                st = TD.load(tpath, recipe=recipe, heroes=True)
                print(f'[measures] {recipe}: {os.path.basename(tpath)} loaded in {time.time() - t0:.0f} s', flush=True)
            except Exception as e:                       # noqa: BLE001 - reported, the run goes on
                print(f'[measures] {recipe}: {tpath} does not load ({type(e).__name__}: {e}): no seams', flush=True)
        pal = LY.palette(st if st is not None else recipe)
        n_layers = len(pal['layers'])
        for name in names:
            v = next((x for x in views[recipe]['views'] if x['name'] == name), None)
            key = f'{recipe}/{name}'
            if v is None or not S.render(recipe, name, label):
                continue
            print(f'[measures] {key}', flush=True)
            try:
                fr = BL.frame_measures(recipe, v, label, st, pal, ref_state=ref, splat=False)
            except Exception as e:                       # noqa: BLE001
                import traceback
                traceback.print_exc()
                fr = dict(error=f'{type(e).__name__}: {e}')
            res['frames'][key] = fr
            try:
                c = compare_frames(M, LY, n_layers, S.render(recipe, name, label), S.layers(recipe, name, label),
                                   S.render(recipe, name, ref), S.layers(recipe, name, ref))
            except Exception as e:                       # noqa: BLE001
                import traceback
                traceback.print_exc()
                c = dict(error=f'{type(e).__name__}: {e}')
            c['layer_names'] = [L['name'] for L in pal['layers']]
            cmp[key] = dict(blender=(blender.get('frames') or {}).get(key), port=fr, compare=c)
            with open(out_json, 'w', encoding='utf-8') as f:
                json.dump(res, f, indent=1, default=float)
            with open(cmp_json, 'w', encoding='utf-8') as f:
                json.dump(cmp, f, indent=1, default=float)
        del st
    print('[measures] wrote', out_json.replace('\\', '/'), 'and', cmp_json.replace('\\', '/'))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
