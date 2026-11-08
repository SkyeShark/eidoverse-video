"""Parity of eidoblend.fx.stable_fluids against three-fluid-fx itself (the package eidoverse/fluid_sim.js wraps).

engine_run_stable_fluids.mjs runs the package's own WGSLFluidSimulation on WebGPU (deno) with a scripted splat
sequence and dumps its textures; this runs the port on the same script and compares. No Blender needed:

    cd blender/tests/water3d
    for c in motion colour novort; do deno run --no-config --no-lock -A --import-map=importmap_engine.json \
        engine_run_stable_fluids.mjs out=out case=$c; done
    python test_stable_fluids_parity.py

Cases: 'motion' (vorticity, BFECC, reflective walls, the default (dx, dy, 1) splat colour, dye), 'colour' (a
16:9 resize and fluid_sim.js's coloured splat, whose colour also drives the velocity), 'novort' (vorticity,
BFECC and wall reflection off). PASS when the relative RMS difference of velocity, density and dye is under 3 %:
the GPU's bilinear filter weights carry ~8 bits of sub-texel precision and its half-float rounding order differs
from numpy's, so 60 frames of a chaotic flow agree closely, not bit for bit.
"""

import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend.fx.stable_fluids import FluidSimulation  # noqa: E402

OUT = os.path.join(HERE, 'out')


def run_port(case, n):
    opts = dict(profile='performance', enable_vorticity=case != 'novort', enable_dye=True, curl_strength=0.55)
    if case == 'novort':
        opts.update(bfecc=False, reflect_walls=False)
    s = FluidSimulation(**opts)
    if case == 'colour':
        s.resize(1920, 1080)
    for k in range(n):
        a = k / n * 2 * math.pi
        script = [(0.5 + 0.3 * math.cos(a), 0.5 + 0.3 * math.sin(a), -40 * math.sin(a), 40 * math.cos(a))]
        if k % 3 == 0:
            script.append((0.2, 0.25, 30, 12))
        if k % 4 == 1:
            script.append((0.8, 0.7, -25, -18))
        for x, y, dx, dy in script:
            col = (0.5 + 0.5 * math.sin(k * 0.3), 0.4, 0.5 + 0.5 * math.cos(k * 0.2))
            if case == 'colour':
                s.add_splat(x, y, dx, dy, color=col, dye_color=col)
            else:
                s.add_splat(x, y, dx, dy, dye_color=col)
        s.step(1 / 60)
    return s


def rel_rms(a, b):
    return float(np.sqrt(np.mean((a - b) ** 2)) / max(np.sqrt(np.mean(b ** 2)), 1e-9))


ok = True
for case in ('motion', 'colour', 'novort'):
    meta_p = os.path.join(OUT, f'engine_fluid2d_{case}.json')
    if not os.path.exists(meta_p):
        print(f'FAIL {case}: no engine dump (run engine_run_stable_fluids.mjs first)')
        ok = False
        continue
    meta = json.load(open(meta_p))
    s = run_port(case, meta['frames'])
    for name, mine, chans in (('velocity', s.velocity, (0, 1)), ('density', s.density, (0, 1, 2)),
                              ('dye', s.dye, (0, 1, 2))):
        shp = meta['shapes'][name]
        eng = np.fromfile(os.path.join(OUT, f'engine_fluid2d_{case}_{name}.f32'), dtype='<f4').reshape(shp)
        if eng.shape != mine.shape:
            print(f'FAIL {case} {name}: shape {mine.shape} vs engine {eng.shape}')
            ok = False
            continue
        e = rel_rms(mine[..., list(chans)], eng[..., list(chans)])
        good = e < 0.03
        ok &= good
        print(('PASS' if good else 'FAIL') + f' {case} {name}: relative RMS difference {e * 100:.2f} %  '
              f'(max |engine| {np.abs(eng[..., list(chans)]).max():.3f}, max |port| '
              f'{np.abs(mine[..., list(chans)]).max():.3f})')
print('ALL PASS' if ok else 'SOME FAIL')
