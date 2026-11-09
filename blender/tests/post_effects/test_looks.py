"""tests/post_effects/test_looks.py: every compositor effect of the registry over the still life, through AgX, at its
WebGPU defaults and with options turned, in sheets to look at; the time-driven ones as strips over time; the
registry's own multi-effect example; opacity 0 is the plain frame; time moves the animated ones.

  --stage sheets   the catalogue: defaults and options of each effect (sheets_*.jpg)
  --stage time     the animated effects at frames 6, 18, 30, 42 (time_*.jpg), and their 'moves' checks
Run from the main checkout (the GPU slot), after test_parity.py --stage sources:
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh <worktree>/blender/tests/post_effects/test_looks.py --stage sheets
"""
import os
import sys
import traceback

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import still_life as SL                                          # noqa: E402

from eidoblend.look import frame_stats as FS                     # noqa: E402

A = SL.args()
STAGE = SL.arg(A, '--stage', 'sheets')
CHK = SL.Checks('looks')
OUT = os.path.join(SL.OUT, 'looks')
os.makedirs(OUT, exist_ok=True)
FRAME = 30
CASES = [
    # the effects this step ported or finished
    ('wavy', {}, {'amplitude': 18, 'frequency': 0.05, 'phase': 1.0}),
    ('kaleidoscope', {}, {'segments': 9, 'rotate': 0.4}),
    ('jitter', {}, {'speed': 3.0, 'amplitude': 0.35}),
    ('melt', {}, {'speed': 1.5, 'swirl': 0.6}),
    ('dithering', {}, {'levels': 3}),
    ('chromatic_aberration_alpha', {}, {'amount': 0.012, 'angle': 0.6}),
    ('bw_halftone', {}, {'dot_size': 3.0, 'angle': 15, 'ink_color': (0.05, 0.02, 0.12), 'paper_color': (0.9, 0.85, 0.7)}),
    ('bleach_bypass', {}, {'amount': 0.6}),
    ('hash_blur', {}, {'amount': 0.02, 'repeats': 24}),
    ('crt', {}, {'opacity': 0.85}),
    ('vhs_tape', {}, {'intensity': 2.0}),
    ('rain_on_camera', {}, {'amount': 1.5, 'drop_size': 0.3, 'speed': 2.0}),
    ('full_toon', {}, {'near_levels': 5, 'hue_shift': 0.8, 'outline_threshold': 0.3, 'saturation': 1.1}),
    ('blueprint', {}, {'cell_px': 30, 'paper_color': (0.03, 0.08, 0.2), 'rim_weight': 0.5}),
    ('cross_hatch', {}, {'hatch_strength': 1.0, 'wiggle': 0.6, 'outline_strength': 1.8}),
    ('underwater', {'bubble_count': 0}, {'bubble_count': 0, 'fog_density': 0.12, 'caustic_scale': 1.0}),
    # round one's, ported again from their nodes (three's LensflareNode / AnamorphicNode) or given their WebGPU mode
    ('lensflare', {}, {'threshold': 1.5, 'ghost_spacing': 0.3, 'ghost_tint': (1.0, 0.8, 0.6), 'ghost_samples': 6,
                       'ghost_attenuation': 12.0, 'strength': 0.8}),
    ('anamorphic_flare', {}, {'threshold': 1.5, 'scale': 3.0, 'samples': 48, 'color': (1.0, 0.5, 0.1)}),
    ('depth_fog', {'mode': 'screen'}, {'mode': 'screen', 'density': 0.08, 'noise_amount': 0.8, 'noise_scale': 3.0,
                                       'color': (0.75, 0.62, 0.5)}),
    # three's DepthOfFieldNode (focus_blur mode 'screen'): WebGPU's defaults (focus 5 m, bokeh 1: a pixel or two of
    # blur), then a strong setting focused on the near objects
    ('focus_blur', {'mode': 'screen'}, {'mode': 'screen', 'focus_distance': 6.5, 'focal_length': 4.0,
                                        'bokeh_scale': 8.0}),
    # round one's groups, for the catalogue
    ('glitch_bars', {}, {'bar_freq': 40, 'shift': 0.05}),
    ('rgb_shift', {}, {'amount': 0.012, 'angle': 0.8}),
    ('radial_blur', {}, {'center_x': 0.3, 'center_y': 0.35, 'exposure': 3.0}),
    ('box_blur', {}, {'size': 3, 'separation': 2}),
    ('sepia', {}, {'amount': 0.6}),
    ('old_bw_film', {}, {'opacity': 0.7}),
    ('neon_edges', {}, {'glow_color': (0.2, 1.0, 0.6), 'threshold': 0.02, 'strength': 2.0}),
]
TIMED = [('wavy', {'animate': True, 'anim_speed': 3.0}), ('jitter', {}), ('melt', {}), ('crt', {}), ('vhs_tape', {}),
         ('rain_on_camera', {}), ('underwater', {'bubble_count': 0}), ('cross_hatch', {}), ('glitch_bars', {}),
         ('old_bw_film', {})]


def sheets():
    from eidoblend.look.post import custom_effects as CFX
    m = SL.meta('opaque')
    paths, labels = [m['plain']], ['still life, plain (AgX)']
    for eff, o_def, o_alt in CASES:
        for tag, o in (('defaults', o_def), ('options', o_alt)):
            try:
                bpy.ops.wm.read_factory_settings(use_empty=True)
                sc = SL.post_scene(m, name=f'look_{eff}')
                CFX.apply_to(sc, eff, {eff: dict(o)})
                p = SL.render_png(sc, os.path.join(OUT, f'{eff}_{tag}.png'), FRAME)
                paths.append(p)
                shown = {k: v for k, v in o.items() if k not in ('bubble_count',)}
                labels.append(f"{eff} {shown if shown and tag == 'options' else '(WebGPU defaults)'}"
                              + (" mode 'screen'" if eff in ('depth_fog', 'focus_blur') and tag == 'defaults' else ''))
                im = FS.read_rgb(p).astype(float)
                CHK(np.isfinite(im).all() and im.std() > 3.0, f'{eff} {tag}: renders a picture (std {im.std():.1f})')
            except Exception as ex:                              # noqa: BLE001
                traceback.print_exc()
                CHK(False, f'{eff} {tag}: {ex!r}')
    for k in range(0, len(paths), 12):
        FS.sheet(paths[k:k + 12], os.path.join(OUT, f'sheet_{k // 12 + 1}.jpg'), cols=3, tile=560,
                 labels=labels[k:k + 12])
    # the registry's own example (custom_effects_deno.js's header): ['underwater', 'vhs_tape'] in one call
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = SL.post_scene(m, name='look_example')
    e = CFX.apply_to(sc, ['underwater', 'vhs_tape'], {'underwater': {'bubble_count': 0, 'fog_density': 0.1},
                                                       'vhs_tape': {'intensity': 1.0}})
    from eidoblend.look.post import chain
    st = [(s, n) for s, n, _x in chain.stages(sc)]
    CHK(st == [('under', 'underwater'), ('over', 'vhs_tape')], f"['underwater', 'vhs_tape']: world under, signal over "
                                                               f"({st})")
    p = SL.render_png(sc, os.path.join(OUT, 'example_underwater_vhs_tape.png'), FRAME)
    # the pre-bloom flares sit before the bloom whatever the order they are applied in
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = SL.post_scene(m, name='look_flares')
    CFX.apply_to(sc, 'bloom', {'bloom': {'strength': 0.25, 'radius': 0.4, 'threshold': 0.85}})
    CFX.apply_to(sc, 'anamorphic_flare,lensflare,sepia', {'sepia': {'amount': 0.3}})
    st = [(s, n) for s, n, _x in chain.stages(sc)]
    CHK([n for _s, n in st] == ['anamorphic_flare', 'lensflare', 'bloom', 'sepia'],
        f'the flares run before the bloom (WebGPU pre-bloom hook), whatever the order applied: {st}')
    p2 = SL.render_png(sc, os.path.join(OUT, 'flares_bloom_sepia.png'), FRAME)
    FS.sheet([m['plain'], p, p2], os.path.join(OUT, 'sheet_examples.jpg'), cols=3, tile=560,
             labels=['plain', "['underwater', 'vhs_tape'] (the registry's example)",
                     'bloom, then anamorphic_flare + lensflare (pre-bloom) + sepia'])


def timed():
    from eidoblend.look.post import custom_effects as CFX
    m = SL.meta('opaque')
    frames = (6, 18, 30, 42)
    rows, labels = [], []
    for eff, o in TIMED:
        try:
            bpy.ops.wm.read_factory_settings(use_empty=True)
            sc = SL.post_scene(m, name=f'time_{eff}')
            CFX.apply_to(sc, eff, {eff: dict(o)})
            ps = [SL.render_png(sc, os.path.join(OUT, f'time_{eff}_f{f:02d}.png'), f) for f in frames]
            ims = [FS.read_rgb(p).astype(float) for p in ps]
            moved = [float((np.abs(ims[i + 1] - ims[i]).max(axis=2) > 6).mean()) for i in range(len(ims) - 1)]
            CHK(max(moved) > 0.005, f'{eff}: time drives it over a still source (frames {frames}: '
                                    f'{", ".join(f"{x * 100:.1f}%" for x in moved)} of pixels change)')
            rows += ps
            labels += [f'{eff} t = {f / m["fps"]:.2f} s' for f in frames]
        except Exception as ex:                                  # noqa: BLE001
            traceback.print_exc()
            CHK(False, f'{eff} over time: {ex!r}')
    for k in range(0, len(rows), 16):
        FS.sheet(rows[k:k + 16], os.path.join(OUT, f'time_{k // 16 + 1}.jpg'), cols=4, tile=420,
                 labels=labels[k:k + 16])


try:
    {'sheets': sheets, 'time': timed}[STAGE]()
except Exception:                                                # noqa: BLE001
    traceback.print_exc()
    CHK.fail.append('exception: ' + traceback.format_exc().splitlines()[-1])
CHK.save('looks_' + STAGE)
