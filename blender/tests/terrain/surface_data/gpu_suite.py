"""The surface-data checks that need Blender's GPU, in one Blender run (one queue slot on a shared machine):

    bash run_blender.sh blender/tests/terrain/surface_data/gpu_suite.py [--noise] [--expr] [--kernels]
        [--palette CASE ...] [--seam CASE] [--all]

--kernels   test_kernels.py (every bake kernel against its twin)
--noise     test_noise.py (the noise port against Blender's nodes)
--expr      test_expr.py (expr_glsl against palettes.evaluate)
--palette   the palette bake (P, C) of a case's cached bake (bake_cases.py made it), timed: out/surface_data/
            palette_<case>.json
--images    the same, then its atlas images made, and a cache hit with its images timed
--seam      render_seam.py on a case
Each part is reported and the next runs whatever it returned.
"""
import json
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _cases as C  # noqa: E402


def palette(name, images=False, log=print):
    """The palette bake of a case (its maps' bake cached), timed; with images, its atlas images made (files written
    and loaded), then a second bake_surface + images() from the cache (the cache hit a material build sees)."""
    from eidoblend.terrain import surface as S
    from eidoblend.terrain.surface import atlas as AT
    from eidoblend.terrain.surface import maps as MP
    t = C.terrain(name)
    folder = os.path.join(C.OUT, 'cache', name)
    pal = C.CASES[name].get('palette', 'auto')
    t0 = time.perf_counter()
    sd = S.bake_surface(t, palette=pal, cache=folder, log=log)
    t1 = time.perf_counter()
    rec = dict(case=name, palette=sd.palette.get('name') if sd.palette else None, bake_seconds=round(t1 - t0, 2),
               info_palette=sd.info.get('palette_bake'), describe=sd.describe())
    if images:
        sd.images()
        t2 = time.perf_counter()
        sd2 = S.bake_surface(t, palette=pal, cache=folder, log=log)
        imgs = sd2.images()                              # (they replace the first ones, of the same names)
        t3 = time.perf_counter()
        rec.update(images_seconds=round(t2 - t1, 2), hit_with_images_seconds=round(t3 - t2, 2),
                   image_seconds=sd.info.get('image_seconds'), hit_image_seconds=sd2.info.get('image_seconds'),
                   families=list(imgs),
                   memory_mb={f: round(AT.megabytes(sd.layouts[f], MP.FAMILIES['M' if f.startswith('M') else f]
                                                    ['format']), 1) for f in imgs})
        # the round trip: what Blender holds of each file against the atlas array (one 8-bit step; half precision)
        import numpy as np
        trip = {}
        for fam, img in imgs.items():
            if not (fam in ('D', 'E', 'C', 'P') or fam == 'M0'):
                continue
            W, H = img.size
            px = np.empty(W * H * 4, np.float32)
            img.pixels.foreach_get(px)
            want = sd.atlas(fam)
            got = px.reshape(H, W, 4)
            d = np.abs(got.astype(np.float64) - want)
            base = 'M' if fam.startswith('M') else fam
            tol = 0.5 / 255 + 1e-6 if not MP.FAMILIES[base]['is_float'] else None
            if tol is None:
                rel = d / np.maximum(np.abs(want), 1e-3)
                trip[fam] = dict(max_abs=float(d.max()), max_rel=float(rel.max()), ok=bool(rel.max() <= 1.0e-3))
            else:
                trip[fam] = dict(max_abs=float(d.max()), ok=bool(d.max() <= tol))
            log(f'[gpu_suite] image round trip {fam}: {trip[fam]}')
        rec['round_trip'] = trip
    with open(os.path.join(C.OUT, f'palette_{name}.json'), 'w', encoding='utf-8') as f:
        json.dump(rec, f, indent=1, default=str)
    log(f"[gpu_suite] palette {name}: bake {rec['bake_seconds']} s"
        + (f", images {rec['images_seconds']} s, a cache hit with its images {rec['hit_with_images_seconds']} s"
           if images else ''))
    log(sd.describe())


def main():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    parts = []
    if '--kernels' in a or '--all' in a:
        parts.append(('kernels', lambda: __import__('test_kernels').main()))
    if '--noise' in a or '--all' in a:
        parts.append(('noise', lambda: __import__('test_noise').main()))
    if '--expr' in a or '--all' in a:
        parts.append(('expr', lambda: __import__('test_expr').main()))
    for i, v in enumerate(a):
        if v in ('--palette', '--images') and i + 1 < len(a):
            nm = a[i + 1]
            parts.append((f'palette {nm}', lambda nm=nm, im=(v == '--images'): palette(nm, images=im)))
        if v == '--seam' and i + 1 < len(a):
            nm = a[i + 1]

            def seam(nm=nm):
                import render_seam
                sys.argv = [sys.argv[0], '--', '--case', nm]
                return render_seam.main()
            parts.append((f'seam {nm}', seam))
    rc = 0
    for label, fn in parts:
        t0 = time.perf_counter()
        try:
            r = fn()
            print(f'[gpu_suite] {label}: returned {r} in {time.perf_counter() - t0:.1f} s', flush=True)
            rc |= int(r or 0)
        except Exception:                                    # noqa: BLE001 - reported; the next part runs
            traceback.print_exc()
            rc = 1
        sys.stdout.flush()
    return rc


if __name__ == '__main__':
    code = main()
    sys.stdout.flush()
    os._exit(code)
