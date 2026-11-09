"""Every volumetric example in motion: its life over the loop and a run of consecutive frames, in EEVEE beside the
engine's own march of the same sample(), on a dusk stage with the fire's keyed lamps lighting the floor.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/sdf_volumes/test_volume_sequences.py [-- examples=bonfire,fire lit=1 w=480 h=270]

Per example:
  out/seq_<name>_life.png     four times through its life: EEVEE (top row) over the reference march (bottom row)
  out/seq_<name>_motion.png   six consecutive frames at 24 fps (baked as a sequence, lamps keyed), EEVEE
  lit=1: out/seq_<name>_lit.png   look='engine' beside look='lit' (its smoke scattering the moon and the fire's lamps)
PASS lines: every frame rendered, the volume is visible (its pixels differ from the empty stage), consecutive frames
change (it moves), and EEVEE and the reference march show the medium in the same pixels (IoU of the pixels each
changes against the same empty stage; the march is composited over EEVEE's render of that stage).
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _vcommon as V  # noqa: E402

import bpy  # noqa: E402

from eidoblend.sdf import EXAMPLES  # noqa: E402
from eidoblend.sdf.examples_volumes import build_still, fit_volume_range, light_from_emission  # noqa: E402

A = V.args()
W, H = int(A.get('w', 480)), int(A.get('h', 270))
SAMPLES = int(A.get('samples', 16))
CACHE = os.path.join(V.OUT, 'cache_seq')
LIT = A.get('lit', '0') == '1'

# per example: cells, Blender location, camera, target, lens, life times (s), the motion run's start (s), floor z
SHOTS = {
    'explosion_ring': dict(cells=256, loc=(0, 0, 0.2), cam=(0.0, -2.3, 1.25), target=(0.0, 0.0, 0.22), lens=40,
                           life=(0.5, 1.4, 2.6, 4.0), run=1.0),
    'flame': dict(cells=200, loc=(0, 0, 0), cam=(0.0, -3.3, 0.85), target=(0.0, 0.0, 0.62), lens=40,
                  life=(0.4, 1.0, 1.7, 2.5), run=1.0),
    'smoke': dict(cells=180, loc=(0, 0, 0), cam=(0.0, -6.6, 1.5), target=(0.0, 0.0, 1.3), lens=40,
                  life=(0.5, 2.0, 4.0, 6.0), run=2.0),
    'gyroid_fireball': dict(cells=192, loc=(0, 0, 0.85), cam=(0.0, -2.9, 1.05), target=(0.0, 0.0, 0.8), lens=40,
                            life=(0.12, 0.5, 1.2, 2.3), run=0.3),
    'bonfire': dict(cells=200, loc=(0, 0, 0), cam=(0.0, -5.4, 1.5), target=(0.0, 0.0, 1.1), lens=40,
                    life=(0.5, 1.1, 1.7, 2.4), run=1.0),
    'candle_flame': dict(cells=256, loc=(0, 0, 0), cam=(0.0, -1.35, 0.36), target=(0.0, 0.0, 0.3), lens=40,
                         life=(0.5, 1.5, 3.0, 5.0), run=1.0),
    'fire': dict(cells=220, loc=(0, 0, 0), cam=(0.0, -12.0, 2.7), target=(0.0, 0.0, 2.55), lens=35,
                 life=(0.5, 1.2, 1.9, 2.7), run=1.0),
    'nuclear_blast': dict(cells=220, loc=(0, 0, 0), cam=(0.0, -46.0, 7.0), target=(0.0, 0.0, 8.5), lens=35,
                          life=(1.0, 4.0, 9.0, 16.0), run=5.0, lit_t=17.5),
}
NAMES = A.get('examples', ','.join(SHOTS)).split(',')
WORLD = 0.03


def stage_for(name):
    S = SHOTS[name]
    V.stage(W, H, SAMPLES, world=WORLD, sun=0.15, floor=True, floor_color=(0.32, 0.31, 0.29),
            floor_size=max(400.0, 40.0 * abs(S['cam'][1])), sun_rot=(62.0, 0.0, -30.0))
    sc = bpy.context.scene
    sc.render.fps = 24
    cam = V.camera(S['cam'], S['target'], lens=S['lens'])
    cam.data.clip_start = 0.02
    return sc, cam


def lum(img):
    return img[..., :3] @ np.array([0.2126, 0.7152, 0.0722])


def render_png(path, text):
    ok = V.render(path)
    if ok:
        V.label(path, text)
    return ok


for name in NAMES:
    S = SHOTS[name]
    # ---- the empty stage (for the visibility check) --------------------------------------------------------------
    sc, cam = stage_for(name)
    empty = os.path.join(V.OUT, f'seq_{name}_empty.png')
    V.render(empty)
    base = V.read_png(empty)
    empty_exr = os.path.join(V.OUT, f'seq_{name}_empty.exr')
    V.render_linear(empty_exr)
    # ---- life: four stills through the loop, EEVEE + reference -------------------------------------------------
    vol = EXAMPLES[name].make(cells=S['cells'], cache_dir=CACHE, location=S['loc'], name=f'seq_{name}', build=False)
    fit_volume_range(sc, cam, [vol], frames=[sc.frame_current], tile_size='2', samples=96)
    life_e, life_r = [], []
    ious = []
    for i, t in enumerate(S['life']):
        build_still(vol, t)                # a file per time: Blender keeps the grids it loaded from a path
        # like for like with the march: the volume alone (its lamps light the floor in the motion run below)
        pe = os.path.join(V.OUT, f'seq_{name}_life{i}.png')
        V.check(f'{name}: life frame t={t} rendered', render_png(pe, f'{name} EEVEE t={t:g}s'), pe)
        img = V.read_png(pe)
        diff = np.abs(lum(img) - lum(base))
        diff[:30, :] = 0.0                  # the label's corner
        V.check(f'{name}: visible at t={t}', float((diff > 0.03).mean()) > 0.002,
                f'{(diff > 0.03).mean() * 100:.2f}% of the frame changed')
        # the engine's march of the same sample(), composited over the same empty stage (the floor and sky EEVEE
        # rendered without the volume), so the two differ only by the volume
        refi = vol.raymarch_reference(cam, W, H, samples=2, t=t)
        stage_lin = V.read_exr(empty_exr)[::-1, :, :3]
        ref = refi[..., :3] + stage_lin * (1.0 - refi[..., 3:4])
        pr = V.save_linear_png(os.path.join(V.OUT, f'seq_{name}_life{i}_ref.png'), ref)
        V.label(pr, f'{name} engine march t={t:g}s')
        # where each shows the medium, measured alike: the pixels each image changes against the same empty stage
        # (the label's corner left out)
        refa = np.abs(lum(V.read_png(pr)) - lum(base)) > 0.03
        eev = diff > 0.03
        refa[:30, :] = False
        eev[:30, :] = False
        inter, union = float((refa & eev).sum()), float((refa | eev).sum())
        ious.append(inter / max(1.0, union))
        life_e.append(pe)
        life_r.append(pr)
    V.sheet(life_e + life_r, os.path.join(V.OUT, f'seq_{name}_life.png'), cols=4)
    V.check(f'{name}: EEVEE shows the medium where the engine march does', min(ious) > 0.5,
            'IoU ' + ', '.join(f'{x:.2f}' for x in ious))
    # ---- motion: six consecutive frames, baked + keyed lamps ---------------------------------------------------
    sc.frame_start, sc.frame_end = 1, 6
    vol.bake(1, 6, time_offset=S['run'], log=None)
    light_from_emission(vol, log=None)
    fit_volume_range(sc, cam, [vol], frames=range(1, 7), tile_size='2', samples=96)
    run = []
    for f in range(1, 7):
        sc.frame_set(f)
        p = os.path.join(V.OUT, f'seq_{name}_f{f:02d}.png')
        render_png(p, f'{name} frame {f} (t={S["run"] + (f - 1) / 24:.3f}s)')
        run.append(p)
    V.sheet(run, os.path.join(V.OUT, f'seq_{name}_motion.png'), cols=3)
    imgs = [lum(V.read_png(p)) for p in run]
    moves = [float(np.abs(imgs[k + 1] - imgs[k]).mean()) for k in range(5)]
    V.check(f'{name}: moves frame to frame', min(moves) > 1e-4, 'mean |dL| ' + ', '.join(f'{m:.4f}' for m in moves))
    # ---- lit: look='engine' beside look='lit' ----------------------------------------------------------------
    if LIT and name in ('bonfire', 'candle_flame', 'fire', 'nuclear_blast'):
        # one still of each look at a time with smoke in it (the blast's smoke comes as it cools), under a moon
        # strong enough to light smoke, with each look's own lamps
        t = S.get('lit_t', S['run'])
        for ob in [vol.object] + list(vol.emission_lights.lights):
            ob.hide_render = True
        sun = bpy.data.objects.get('sun')
        if sun is not None:
            sun.data.energy = 1.5
        shots = []
        for look in ('engine', 'lit'):
            v = EXAMPLES[name].make(look=look, cells=S['cells'], cache_dir=CACHE, location=S['loc'],
                                    name=f'seq_{name}_{look}', build=False)
            build_still(v, t)
            rig = light_from_emission(v, log=None)
            p = os.path.join(V.OUT, f'seq_{name}_look_{look}.png')
            render_png(p, f"{name} look='{look}' t={t:g}s, moon 1.5")
            shots.append(p)
            for ob in [v.object] + list(rig.lights):
                ob.hide_render = True
        V.sheet(shots, os.path.join(V.OUT, f'seq_{name}_lit.png'), cols=2)
    vol.program.free()
V.summary()
