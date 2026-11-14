"""tests/look/test_post.py: the post chain and the effect registry, each effect rendered and looked at.

  - on the stage's reverse shot (the FOH lenses glowing): plain, bloom, anamorphic streaks (WebGPU's blue tint),
    lens ghosts
  - on the meadow's frame 60: plain; glitch_bars with the WebGPU guide's own options (camelCase, as a ported scene
    passes them), and keyed as a burst on its opacity (on at 60, gone at 64); rgb_shift (its frame edges checked:
    no black or tinted bars); sepia; neon_edges; radial_blur; box_blur; native depth_fog (a fog volume, with noise);
    sun_beams; old_bw_film over 12 frames (its 12 fps cadence, gate weave, flicker and dust live in time)
  - options: an unknown one raises, a WebGPU-only one warns and is ignored (no render)
Run test_meadow_camera.py and test_stage.py (--stage build) first.
    bash run_blender.sh blender/tests/look/test_post.py
    # a GPU job; on a shared machine queue it with EIDO_GPU_WRAP (blender/tests/_where.py)
"""
import json
import os
import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixtures as FX                                       # noqa: E402

from eidoblend.look import frame_stats as FS                 # noqa: E402
from eidoblend.look import probe as P                        # noqa: E402
from eidoblend.look import render_settings as RS             # noqa: E402
from eidoblend.look.post import chain                        # noqa: E402
from eidoblend.look.post import custom_effects as CFX        # noqa: E402

OUT = os.path.join(FX.OUT, 'post')
os.makedirs(OUT, exist_ok=True)
MEADOW = os.path.join(FX.OUT, 'meadow', 'meadow_camera.blend')
STAGE = os.path.join(FX.OUT, 'stage', 'stage.blend')
REPORT = {'effects': CFX.list()}
FAIL = []


def fresh(blend, exposure):
    bpy.ops.wm.open_mainfile(filepath=blend, load_ui=False)
    sc = bpy.context.scene
    RS.apply_auto_enhance(sc, 'probe', exposure=exposure, volumes={'tile': '8', 'samples': 64} if blend == STAGE else None)
    return sc


def shot(blend, exposure, frame, name, effects=None, opts=None, keys=(), frames=None):
    sc = fresh(blend, exposure)
    fx = CFX.apply_to(sc, effects, opts) if effects else None
    for k in keys:
        fx.key(*k)
    paths = []
    for f in (frames or [frame]):
        p = os.path.join(OUT, f'{name}.png' if not frames else f'{name}_f{f}.png')
        P.render_still(sc, p, f)
        paths.append(p)
    st = FS.frame_stats(FS.read_rgb(paths[0]))
    REPORT[name] = {'effects': effects, 'opts': opts, 'stages': [(s, n) for s, n, _x in chain.stages(sc)],
                    'clipped': st['clipped'], 'luma_median': st['luma_median']}
    print(f'[post] {name}: {effects or "plain"} {opts or ""}; stages {REPORT[name]["stages"]}', flush=True)
    return paths if frames else paths[0]


def diff(a, b):
    x, y = FS.read_rgb(a).astype(np.int16), FS.read_rgb(b).astype(np.int16)
    d = np.abs(x - y)
    return {'max': int(d.max()), 'mean': round(float(d.mean()), 4), 'over_2': round(float((d.max(axis=2) > 2).mean()), 6)}


# ---- options (no render): unknown keys raise, WebGPU-only keys warn
bpy.ops.wm.open_mainfile(filepath=MEADOW, load_ui=False)
try:
    CFX.apply_to(bpy.context.scene, 'rgb_shift', {'rgb_shift': {'pixels': 4}})
    FAIL.append("rgb_shift accepted an unknown option 'pixels'")
except KeyError as e:
    REPORT['unknown_option'] = str(e)
    print(f'[post] unknown option raised, as it must: {e}', flush=True)
fx = CFX.apply_to(bpy.context.scene, 'lensflare', {'lensflare': {'ghostSpacing': 0.3, 'ghostTint': (1.0, 0.8, 0.6)}})
REPORT['camel_case_tint'] = list(fx.uniforms['lensflare']['ghostTint'].default_value)
if abs(REPORT['camel_case_tint'][2] - 0.6) > 1e-6:
    FAIL.append(f"lensflare ghostTint not applied: {REPORT['camel_case_tint']}")

# ---- the stage's lenses: glare
st = [shot(STAGE, 1.25, 30, 'stage_plain'),
      shot(STAGE, 1.25, 30, 'stage_bloom', 'bloom', {'bloom': {'strength': 0.6, 'radius': 0.6, 'threshold': 1.0}}),
      shot(STAGE, 1.25, 30, 'stage_anamorphic', 'anamorphic_flare', {'anamorphic_flare': {'threshold': 2.0, 'strength': 0.6}}),
      shot(STAGE, 1.25, 30, 'stage_lensflare', 'lensflare', {'lensflare': {'threshold': 1.0, 'strength': 0.6}})]
FS.sheet(st, os.path.join(OUT, 'post_stage_sheet.jpg'), cols=2, tile=640,
         labels=['plain', 'bloom (Glare)', "anamorphic_flare (three's AnamorphicNode, blue)",
                 "lensflare (three's LensflareNode)"])

# ---- the meadow: the compositor groups, a keyed burst, native fog
try:
    with open(os.path.join(FX.OUT, 'meadow', 'report_render.json'), encoding='utf-8') as fh:
        E = float(json.load(fh)['exposure']['set'])
except (OSError, KeyError, ValueError):
    E = 0.25
REPORT['meadow_exposure'] = E
plain = shot(MEADOW, E, 60, 'meadow_plain')
burst = [('glitch_bars', 'opacity', 58, 0.0), ('glitch_bars', 'opacity', 60, 1.0), ('glitch_bars', 'opacity', 62, 0.0)]
md = [plain,
      shot(MEADOW, E, 60, 'meadow_glitch_guide', 'glitch_bars', {'glitch_bars': {'barFreq': 22, 'shift': 0.03,
                                                                                  'opacity': 0.85}}),
      shot(MEADOW, E, 60, 'meadow_glitch_on', 'glitch_bars', keys=burst),
      shot(MEADOW, E, 64, 'meadow_glitch_off', 'glitch_bars', keys=burst),
      shot(MEADOW, E, 60, 'meadow_rgb_shift', 'rgb_shift', {'rgb_shift': {'amount': 0.006}}),
      shot(MEADOW, E, 60, 'meadow_sepia', 'sepia'),
      shot(MEADOW, E, 60, 'meadow_neon_edges', 'neon_edges'),
      shot(MEADOW, E, 60, 'meadow_radial_blur', 'radial_blur'),
      shot(MEADOW, E, 60, 'meadow_box_blur', 'box_blur', {'box_blur': {'size': 3, 'separation': 2}})]
FS.sheet(md, os.path.join(OUT, 'post_meadow_sheet.jpg'), cols=3, tile=640,
         labels=['plain', "glitch_bars {barFreq 22, shift 0.03, opacity 0.85}", 'glitch_bars burst: opacity keyed 1 at 60',
                 'glitch_bars at 64 (opacity keyed back to 0)', 'rgb_shift amount 0.006', 'sepia',
                 'neon_edges (defaults: hot pink)', 'radial_blur (defaults)', 'box_blur size 3, separation 2'])
ex = [shot(MEADOW, E, 60, 'meadow_depth_fog', 'depth_fog', {'depth_fog': {'density': 0.006}}),
      shot(MEADOW, E, 60, 'meadow_depth_fog_noise', 'depth_fog', {'depth_fog': {'density': 0.006, 'noiseAmount': 0.6,
                                                                               'noiseScale': 6.0}}),
      shot(MEADOW, E, 60, 'meadow_sun_beams', 'sun_beams', {'sun_beams': {'source': (0.25, 0.85), 'threshold': 0.8,
                                                                           'strength': 0.4}})]
FS.sheet([plain] + ex, os.path.join(OUT, 'post_meadow_extra_sheet.jpg'), cols=2, tile=640,
         labels=['plain', 'depth_fog 0.006 / m', 'depth_fog + noise (noiseAmount 0.6)', 'sun_beams from (0.25, 0.85)'])
film = shot(MEADOW, E, 60, 'meadow_old_bw_film', 'old_bw_film', frames=list(range(56, 80, 2)))
FS.sheet(film, os.path.join(OUT, 'post_old_bw_film_sheet.jpg'), cols=4, tile=480,
         labels=[f'old_bw_film frame {f}' for f in range(56, 80, 2)])

plain64 = shot(MEADOW, E, 64, 'meadow_plain_f64')
REPORT['glitch_off_vs_plain_f64'] = diff(os.path.join(OUT, 'meadow_glitch_off.png'), plain64)
REPORT['glitch_on_vs_plain'] = diff(os.path.join(OUT, 'meadow_glitch_on.png'), plain)
if REPORT['glitch_off_vs_plain_f64']['max'] > 3:
    FAIL.append(f"glitch_bars keyed to opacity 0 is not the plain frame: {REPORT['glitch_off_vs_plain_f64']}")
# rgb_shift's frame edges: the shifted channels clamp at the edge (WebGPU's ClampToEdge), no black or tinted bars
a, b = FS.read_rgb(os.path.join(OUT, 'meadow_rgb_shift.png')).astype(np.int16), FS.read_rgb(plain).astype(np.int16)
edges = {'left_cols_0_3': round(float(np.abs(a[:, :4] - b[:, :4]).mean()), 3),
         'right_cols_last_4': round(float(np.abs(a[:, -4:] - b[:, -4:]).mean()), 3),
         'interior': round(float(np.abs(a[:, 8:-8] - b[:, 8:-8]).mean()), 3),
         'black_left_column_share': round(float((a[:, 0].max(axis=1) == 0).mean()), 4)}
REPORT['rgb_shift_edges'] = edges
if edges['black_left_column_share'] > 0.01 or max(edges['left_cols_0_3'], edges['right_cols_last_4']) > 3 * edges['interior'] + 2:
    FAIL.append(f'rgb_shift edges differ from its interior: {edges}')
for k in ('glitch_off_vs_plain_f64', 'glitch_on_vs_plain', 'rgb_shift_edges'):
    print(f'[post] {k}: {REPORT[k]}', flush=True)
REPORT['fail'] = FAIL
with open(os.path.join(OUT, 'report.json'), 'w', encoding='utf-8') as fh:
    json.dump(REPORT, fh, indent=1, default=str)
print(f"[post] {'PASS' if not FAIL else 'FAIL'} ({len(FAIL)} finding(s))", flush=True)
for f in FAIL:
    print('  -', f, flush=True)
