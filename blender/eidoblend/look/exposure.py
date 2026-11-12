"""look/exposure.py: exposure chosen by measurement. Render once, judge every exposure from that one render, then
confirm the choice with real renders.

A render's Render Result holds scene-linear light; Image.save_render writes it through the scene's colour management
(AgX, its look, the exposure) at save time. So one render gives a whole sweep of exposures: set the exposure, save the
result as an 8-bit display-referred still, measure it with frame_stats. The sweep is exact on flat areas and
APPROXIMATE along high-contrast edges: EEVEE's film accumulation sees the view exposure, so a frame rendered at +E
differs from the exposure-0 render saved at +E along silhouettes, shadow edges and the horizon (measured on the meadow:
up to 42-61 levels at single pixels, 6-9 % of pixels over 2 levels at +2.25 and +3.25; the clipped shares moved by a
few thousandths of a percent and no verdict changed). auto_expose therefore confirms its pick and its ceiling with
real renders and walks them a step when a real render disagrees. The highlight rule (frame_stats.py): the share of
pixels with any channel >= 250 stays near zero, and no grid cell holds a clipped region.

    from eidoblend.look import exposure
    rows = exposure.exposure_sweep(scene, out_dir, stops=(-2, -1.5, -1, -0.5, 0, 0.5, 1))   # one render, 7 stills
    best = exposure.pick_exposure(rows)               # metered to 18 % grey, the highlight check as the ceiling
    exposure.auto_expose(scene, out_dir)              # both, confirmed by renders; sets the scene's exposure

Where AgX puts things (Blender 5.2's OCIO config, AgX Base Contrast, exposure 0): scene-linear 0.18 -> 117.6 of 255,
1.0 -> 196.6, 4 -> 233, 8 -> 245, 16 -> 254.6. A grey channel reaches 250 about 6 stops above 18 % grey, a saturated
one sooner. So the clip check is a ceiling: metering puts the frame's median at the view's 18 % grey, and the check
says how far the shot's brighter frames may go above that (the 'headroom').

Expose for the frames that matter: run it at a shot's brightest moment (the subject in full sun, the sun in frame),
and check a few frames of every shot with probe.render_stills, which measures each still it writes.
"""
import os
import time

import bpy

from . import frame_stats as fs

DEFAULT_STOPS = tuple(x * 0.25 for x in range(-12, 17))    # -3 .. +4 stops around the current exposure, 1/4 stop apart


def _png_settings(scene):
    """Switch the output format to 8-bit PNG, uncompressed (sweep stills are measured, not kept); returns a restore fn."""
    im = scene.render.image_settings
    saved = {k: getattr(im, k) for k in ('media_type', 'file_format', 'color_mode', 'color_depth', 'compression')
             if hasattr(im, k)}
    if hasattr(im, 'media_type'):
        im.media_type = 'IMAGE'
    im.file_format = 'PNG'
    im.color_mode = 'RGB'
    im.color_depth = '8'
    im.compression = 0

    def restore():
        for k in ('media_type', 'file_format', 'color_mode', 'color_depth', 'compression'):
            if k in saved:
                try:
                    setattr(im, k, saved[k])
                except (TypeError, ValueError):
                    pass
    return restore


def render_result():
    """The last render's Render Result image (bpy.ops.render.render fills it)."""
    img = bpy.data.images.get('Render Result')
    if img is None:
        raise RuntimeError('no Render Result: render first (bpy.ops.render.render())')
    return img


def save_display(scene, path, exposure=None):
    """Save the last render through the scene's view transform at `exposure` (absolute stops; None = the scene's)."""
    vs = scene.view_settings
    keep = vs.exposure
    restore = _png_settings(scene)
    try:
        if exposure is not None:
            vs.exposure = float(exposure)
        render_result().save_render(filepath=path, scene=scene)
    finally:
        vs.exposure = keep
        restore()
    return path


def exposure_sweep(scene, out_dir, stops=DEFAULT_STOPS, name='sweep', render=True, keep=False, region=None,
                   clip=fs.CLIP):
    """Render the current frame once (unless render=False: then the last render is used) and measure it at the scene's
    exposure + each of `stops`. Returns one row per exposure: {'exposure', 'stops', **frame_stats}. The stills are
    deleted unless keep=True (then <out_dir>/<name>_<exposure>.png)."""
    os.makedirs(out_dir, exist_ok=True)
    base = scene.view_settings.exposure
    if render:
        t = time.perf_counter()
        bpy.ops.render.render()
        print(f'[exposure] rendered frame {scene.frame_current} for the sweep in {time.perf_counter() - t:.1f} s', flush=True)
    rows = []
    for s in stops:
        e = base + s
        p = os.path.join(out_dir, f'{name}_{e:+.2f}.png')
        save_display(scene, p, exposure=e)
        st = fs.frame_stats(fs.read_rgb(p), clip=clip, region=region)
        rows.append({'exposure': round(e, 4), 'stops': round(s, 4), 'path': p if keep else None, **st})
        if not keep:
            try:
                os.remove(p)
            except OSError:
                pass
    return rows


def mid_grey_luma(scene=None, grey=0.18):
    """The display value (0..255) the scene's view transform and look give scene-linear `grey` at exposure 0: AgX Base
    Contrast puts 18 % grey at 117.6, Punchy at 88.3 (measured through Blender's own OCIO config). Falls back to
    117.6 when PyOpenColorIO is not there."""
    try:
        import PyOpenColorIO as ocio
        cfg_path = os.path.join(os.path.dirname(bpy.app.binary_path), '%d.%d' % bpy.app.version[:2], 'datafiles',
                                'colormanagement', 'config.ocio')
        cfg = ocio.Config.CreateFromFile(cfg_path)
        vs = scene.view_settings if scene else None
        dv = ocio.DisplayViewTransform()
        dv.setSrc(ocio.ROLE_SCENE_LINEAR)
        dv.setDisplay(scene.display_settings.display_device if scene else 'sRGB')
        dv.setView(vs.view_transform if vs else 'AgX')
        pipe = ocio.LegacyViewingPipeline()
        pipe.setDisplayViewTransform(dv)
        if vs and vs.look not in ('None', 'NONE', ''):
            pipe.setLooksOverrideEnabled(True)
            pipe.setLooksOverride(vs.look)
        r = pipe.getProcessor(cfg).getDefaultCPUProcessor().applyRGB([grey, grey, grey])
        return float(r[0]) * 255.0
    except Exception:
        return 117.6


def pick_exposure(rows, max_share=fs.MAX_SHARE, max_cell=fs.MAX_CELL, target_median=117.6, mode='meter', key='frame'):
    """Choose an exposure from a sweep.

    mode 'meter' (default): the exposure that puts the median luma at target_median (the view's 18 % grey:
        mid_grey_luma(scene)), metering the whole frame (key='frame') or the subject's box (key='region'); if that
        exposure fails the highlight check, the brightest one below it that passes.
    mode 'brightest': the brightest exposure that passes the highlight check (high key; it pushes everything into
        AgX's shoulder, washed and flat: a ceiling, rarely the right exposure).
    The highlight check is the ceiling either way: the frame's share of pixels with any channel >= 250, and its worst
    grid cell. Returns the row with 'reason', 'ceiling' (the brightest passing exposure in the sweep, or None) and
    'headroom' (stops between the pick and that ceiling; the shot's brighter frames spend it)."""
    rows = sorted(rows, key=lambda r: r['exposure'])
    passes = lambda r: r['clipped'] <= max_share and r['worst_cell'][2] <= max_cell
    ok = [r for r in rows if passes(r)]
    ceiling = max((r['exposure'] for r in ok), default=None)
    top = rows[-1]['exposure']
    if not ok:
        r = min(rows, key=lambda r: (r['worst_cell'][2], r['clipped']))
        return {**r, 'ceiling': None, 'headroom': None,
                'reason': 'no exposure in the sweep passes: the darkest-clipping one (widen the sweep downward, or the '
                          'clipping is a light or material fault, not exposure)'}
    metered = None
    if mode == 'brightest':
        r = max(ok, key=lambda r: r['exposure'])
        why = 'the brightest exposure that passes the highlight check'
    else:
        med = (lambda r: r['region']['luma_median']) if key == 'region' and 'region' in rows[0] else (lambda r: r['luma_median'])
        m = min(rows, key=lambda r: abs(med(r) - target_median))
        metered = m['exposure']
        if passes(m):
            r, why = m, f'metered: {key} median {med(m):.0f} nearest {target_median:.0f} (18 % grey)'
        else:
            below = [x for x in ok if x['exposure'] <= m['exposure']]
            r = max(below, key=lambda x: x['exposure']) if below else min(ok, key=lambda x: x['exposure'])
            why = (f"metered {m['exposure']:+.2f} clips; the brightest passing exposure below it")
    head = (ceiling - r['exposure']) if ceiling is not None else None
    if ceiling == top:
        why += f' (no clipping up to the top of the sweep, {top:+.2f}: headroom at least {head:.2f} stops)'
    return {**r, 'ceiling': ceiling, 'headroom': head, 'reason': why, 'metered': metered, 'mode': mode}


def render_at(scene, out_dir, exposure, region=None, clip=fs.CLIP, name='confirm'):
    """Render the current frame AT `exposure` (absolute stops) and measure the still: the exact numbers a sweep's save
    approximates. Leaves the scene's exposure as it was. Returns {'exposure', 'path', **frame_stats}."""
    os.makedirs(out_dir, exist_ok=True)
    vs = scene.view_settings
    keep = vs.exposure
    p = os.path.join(out_dir, f'{name}_{exposure:+.2f}.png')
    try:
        vs.exposure = float(exposure)
        bpy.ops.render.render()
        save_display(scene, p)
    finally:
        vs.exposure = keep
    return {'exposure': round(float(exposure), 4), 'path': p, **fs.frame_stats(fs.read_rgb(p), clip=clip, region=region)}


def _confirm(scene, out_dir, start, step, lo, hi, ok, region, role, log):
    """Walk from `start` (a sweep's answer) with real renders: down while it fails; for the ceiling, up while the next
    step still passes. Returns (exposure, row, renders)."""
    renders = []
    e = start
    row = render_at(scene, out_dir, e, region, name=f'confirm_{role}')
    renders.append(e)
    while not ok(row) and e - step >= lo - 1e-9 and len(renders) < 12:
        e -= step
        row = render_at(scene, out_dir, e, region, name=f'confirm_{role}')
        renders.append(e)
    if role == 'ceiling' and ok(row):
        while e + step <= hi + 1e-9 and len(renders) < 12:
            up = render_at(scene, out_dir, e + step, region, name=f'confirm_{role}')
            renders.append(e + step)
            if not ok(up):
                break
            e, row = e + step, up
    if log:
        print(f"[exposure] confirmed {role}: from {start:+.2f} -> rendered {e:+.2f} (renders at "
              f"{', '.join(f'{x:+.2f}' for x in renders)}; clipped {row['clipped'] * 100:.3f} %, worst cell "
              f"{row['worst_cell'][2] * 100:.1f} %, median {row['luma_median']:.1f})", flush=True)
    return e, row, renders


def auto_expose(scene, out_dir, stops=DEFAULT_STOPS, max_share=fs.MAX_SHARE, max_cell=fs.MAX_CELL, target_median=None,
                mode='meter', key='frame', headroom=0.0, apply=True, render=True, region=None, confirm=True, log=True):
    """exposure_sweep + pick_exposure (metered to the view's own 18 % grey unless target_median is given); sets the
    scene's exposure to the pick minus `headroom` stops. confirm=True (default) renders at the sweep's ceiling and
    pick (the pick last, so the Render Result is the chosen exposure's) and walks either a step down while a real
    render fails the highlight check (the ceiling also a step up while one passes). Returns {'exposure', 'pick',
    'rows', 'target', 'confirmed': [{role, sweep, rendered, changed, renders, clipped, worst_cell, luma_median}]}."""
    target = target_median if target_median is not None else mid_grey_luma(scene)
    rows = exposure_sweep(scene, out_dir, stops=stops, render=render, region=region)
    pick = pick_exposure(rows, max_share=max_share, max_cell=max_cell, target_median=target, mode=mode, key=key)
    confirmed = []
    if confirm:
        ex = sorted(r['exposure'] for r in rows)
        step = min((b - a for a, b in zip(ex, ex[1:]) if b - a > 1e-6), default=0.25)
        ok = lambda r: r['clipped'] <= max_share and r['worst_cell'][2] <= max_cell
        for role in ('ceiling', 'pick'):
            start = pick['ceiling'] if role == 'ceiling' else pick['exposure']
            if role == 'pick' and pick['ceiling'] is not None and pick['exposure'] < pick['ceiling']:
                # the pick was capped by the sweep's ceiling (the brightest passing exposure, or the metered one
                # clipped): a higher confirmed ceiling lifts it, never past what metering asked for
                cap = pick['metered'] if pick.get('metered') is not None else pick['ceiling']
                if pick.get('mode') == 'brightest' or pick['exposure'] == pick.get('sweep_ceiling'):
                    start = min(pick['ceiling'], cap)
            if start is None:
                continue
            e, row, renders = _confirm(scene, out_dir, start, step, ex[0], ex[-1], ok, region, role, log)
            sweep_value = pick['ceiling'] if role == 'ceiling' else pick['exposure']
            confirmed.append({'role': role, 'sweep': sweep_value, 'rendered': round(e, 4),
                              'changed': abs(e - sweep_value) > 1e-6, 'renders': [round(x, 4) for x in renders],
                              'clipped': row['clipped'], 'worst_cell': row['worst_cell'],
                              'luma_median': row['luma_median']})
            if role == 'ceiling':
                pick = {**pick, 'sweep_ceiling': pick['ceiling'], 'ceiling': round(e, 4)}
            else:
                pick = {**pick, 'exposure': round(e, 4)}
        if pick['ceiling'] is not None and pick['exposure'] > pick['ceiling']:
            pick['exposure'] = pick['ceiling']
        if pick['ceiling'] is not None:
            pick['headroom'] = pick['ceiling'] - pick['exposure']
        if confirmed and confirmed[-1]['rendered'] != pick['exposure']:
            render_at(scene, out_dir, pick['exposure'], region, name='confirm_pick')   # the Render Result = the pick
        moved = [f"{c['role']} {c['sweep']:+.2f} -> {c['rendered']:+.2f}" for c in confirmed if c['changed']]
        pick['reason'] += ('; confirmed by renders' + (f" ({', '.join(moved)})" if moved else ''))
    e = pick['exposure'] - headroom
    if log:
        for r in rows:
            mark = '<- pick' if r['exposure'] == pick['exposure'] else ('   ceiling' if r['exposure'] == pick['ceiling'] else '')
            reg = f", subject median {r['region']['luma_median']:.0f} p99 {r['region']['luma_p99']:.0f}" if 'region' in r else ''
            print(f"[exposure] {r['exposure']:+.2f}: clipped {r['clipped'] * 100:6.3f} %  worst cell "
                  f"{r['worst_cell'][2] * 100:5.1f} %  median {r['luma_median']:5.1f}  p99 {r['luma_p99']:5.1f}{reg} {mark}",
                  flush=True)
        print(f"[exposure] pick {pick['exposure']:+.2f}: {pick['reason']}; set {e:+.2f}", flush=True)
    if apply:
        scene.view_settings.exposure = e
    return {'exposure': e, 'pick': pick, 'rows': rows, 'target': target, 'confirmed': confirmed}
