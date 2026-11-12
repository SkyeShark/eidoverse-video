"""Every solid EXAMPLE's GLSL compiles in Blender's GPU module and evaluates: dist, grad, surface and the engine's
raymarch with its shade() (engine_march), plus the four make_sdf_texture recipes. No render, no mesh.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sdf/test_examples_compile.py

PASS lines: the kernel compiled, the field changes sign inside the bounds (there is a surface to mesh), the surface
channels are finite and in range, the help text lists every example.
"""

import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402
import engine_march as EM  # noqa: E402
from eidoblend import sdf  # noqa: E402
from eidoblend.sdf.gpu_eval import SdfProgram  # noqa: E402

rng = np.random.default_rng(5)
for name in sdf.EXAMPLES.solids():
    ex = sdf.EXAMPLES[name]
    t0 = time.perf_counter()
    try:
        prog = SdfProgram(map=ex['map'], surface=ex.get('surface'), shade=ex.get('shade'), extra=ex.get('extra', ''),
                          uniforms=ex.get('uniforms'), label=name)
        lo = np.asarray(ex['bounds']['min'], np.float32)
        hi = np.asarray(ex['bounds']['max'], np.float32)
        pts = (lo + rng.random((40000, 3), dtype=np.float32) * (hi - lo)).astype(np.float32)
        d, m = prog.dist(pts)
        iso = float(ex.get('iso', 0.0))
        inside = float(np.mean(d < iso))
        C.check(f'{name}: dist kernel', np.isfinite(d).mean() > 0.999 and 0.0005 < inside < 0.9,
                f'{inside * 100:.2f}% of the bounds inside, materials {sorted(set(np.rint(m[d < 0.01]).astype(int).tolist()))[:12]}')
        g = prog.grad(pts[:2000], 0.001)[2]
        C.check(f'{name}: grad kernel', np.isfinite(g).all(), f'|grad| median {np.median(np.linalg.norm(g, axis=1)):.3f}')
        near = pts[np.abs(d - iso) < 0.02][:4000]
        ch = prog.surface_eval(near, project=2, grad_h=0.0005, normal_h=0.0005)
        alb = ch['albedo']
        ok = np.isfinite(alb).all() and alb.min() >= -1e-4 and alb.max() <= 1.5 and np.isfinite(ch['roughness']).all()
        C.check(f'{name}: surface kernel', ok,
                f'{len(near)} pts, albedo mean {alb.mean(axis=0).round(3).tolist()}, roughness {ch["roughness"].mean():.2f}')
        march = EM.MarchProgram(prog)
        march.values.update({'sdfCameraUniform': (0.0, 0.5, 4.0), 'sdfCamFwd': (0.0, 0.0, -1.0), 'sdfImageSize': (64.0, 36.0),
                             'sdfClipMin': tuple(float(x) for x in lo), 'sdfClipMax': tuple(float(x) for x in hi),
                             'uMaxSteps': 128.0, 'uSurfEps': 0.001, 'uStepScale': 0.8, 'uMaxDist': 100.0})
        img = march.eval('raymarch', np.zeros((64 * 36, 3), np.float32), width=64)[0]
        C.check(f'{name}: raymarch kernel', np.isfinite(img).all() and img[:, 3].max() > 0,
                f'coverage {img[:, 3].mean() * 100:.1f}%')
    except Exception as e:  # a compile error prints the numbered source
        C.check(f'{name}: compiles', False, str(e)[:3000])
    print(f'[compile] {name} {time.perf_counter() - t0:.2f} s', flush=True)

for recipe in sdf.SDF_TEX_RECIPES:
    try:
        tex = sdf.make_sdf_texture(recipe=recipe, width=64, height=32, name=f'probe_{recipe}',
                                   cache_dir=os.path.join(C.OUT, 'cache'))
        img = tex.render(1.0)
        C.check(f'texture {recipe}', np.isfinite(img).all() and img[..., :3].std() > 0.01,
                f'mean {img[..., :3].mean():.3f} std {img[..., :3].std():.3f}')
    except Exception as e:
        C.check(f'texture {recipe}: compiles', False, str(e)[:3000])

msg = sdf.help()
C.check('help lists every example', all(n in msg for n in sdf.EXAMPLES), f'{len(sdf.EXAMPLES)} examples')
C.summary()
