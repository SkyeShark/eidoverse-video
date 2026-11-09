"""The studio (studio.py, the port of studio.js): its unlit colours, its one-pixel grid, rendered from the WebGPU
examples' own cameras with the robots hidden, and compared with the WebGPU frames:

    out/studio/studio_grid_<example>.png           the empty studio from the example's camera (960 x 540, 16 samples):
                                                   motion at 5.5 s (its fixed camera), mantis at 6 s (the camera
                                                   carried with the body), assembly (framed on the backbone)
    out/studio/studio_vs_webgpu_<example>.png      the WebGPU frame | this render | the floor blocks compared (green:
                                                   lines land on the same pixels, red: not)

The WebGPU frames are render_scene.mjs's (960 x 540) of the three examples at those times, read from
out/verify/webgpu/webgpu_<example>_at<t>s.png when present (the comparison SKIPs without them).

Checks: the background and the grid's two line colours display as three's ACES of studio.js's colours (what the WebGPU
film shows) for the probe look, and again after an exposure change (match_display); the grid's pixel-scale drivers
equal the camera's pixels per unit (vertical, horizontal and auto sensor fit, 50 % resolution, orthographic); in the
renders the background reads (204, 208, 209) within a level; in each floor-only block of the WebGPU frame (every pixel
on the grid's colour ramp, with lines in it), the Blender grid lines land on the same pixels (normalised
cross-correlation of the two blocks' luminance) and darken the floor about as much (the median darkening within 0.6 to
1.6 times WebGPU's: round one's world-space strips darkened it a twelfth as much).

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/robotics/test_studio_render.py [-- --no-render]
    (-- --compare-existing: no slot needed, compares the renders already in out/studio with the WebGPU frames)
"""

import math
import os
import sys
import traceback

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _rk as K  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402

from eidoblend.characters.robotics._display import shown, three_aces, to_255  # noqa: E402
from eidoblend.characters.robotics.examples import EXAMPLES  # noqa: E402
from eidoblend.characters.robotics.studio import (BACKGROUND, GRID_CENTRE, GRID_LINE, make_camera,  # noqa: E402
                                                  match_display, studio)

OUT = os.path.join(K.OUT, 'studio')
os.makedirs(OUT, exist_ok=True)
WEBGPU = os.path.join(K.OUT, 'verify', 'webgpu')
SHOTS = (('motion', 5.5), ('mantis', 6.0), ('assembly', 4.5))
COMPARE_EXISTING = '--compare-existing' in K.argv()      # compare the renders already in out/studio (no GPU)


def colours():
    sc = K.clean_scene()
    studio(sc)
    K.probe_render(sc, (960, 540), 16)                    # the probe look (AgX - Base Contrast); it re-solves
    for exposure in (0.0, 1.0):
        sc.view_settings.exposure = exposure
        got = match_display(sc)
        for name, want_hex in (('background', BACKGROUND), ('grid line colour', GRID_LINE),
                               ('grid centre colour', GRID_CENTRE)):
            rad, target = got[name]
            show = shown(sc, [rad])[0]
            err = max(abs(a - b) for a, b in zip(show, three_aces(want_hex))) * 255
            K.check(f'exposure {exposure:+.0f}: {name} {want_hex} shows as three ACES shows it {to_255(target)}: '
                    f'{to_255(show)}', err < 0.6, f'radiance {tuple(round(v, 4) for v in rad)}, {err:.2f} levels')
    sc.view_settings.exposure = 0.0
    match_display(sc)


def drivers():
    sc = K.clean_scene()
    st = studio(sc)
    nodes = st['grid'].data.materials[0].node_tree.nodes
    cam = make_camera(35, 'driver probe', sc)
    sc.camera = cam
    r = sc.render

    def value(name):
        sc.frame_set(sc.frame_current)
        bpy.context.view_layer.update()
        return nodes[name].outputs[0].default_value
    cases = []
    r.resolution_x, r.resolution_y, r.resolution_percentage = 960, 540, 100
    cases.append(('vertical fit, 960 x 540', value('grid focal px'), 540 / (2 * math.tan(math.radians(17.5)))))
    r.resolution_percentage = 50
    cases.append(('vertical fit at 50 %', value('grid focal px'), 270 / (2 * math.tan(math.radians(17.5)))))
    r.resolution_percentage = 100
    cam.data.sensor_fit = 'HORIZONTAL'
    cases.append(('horizontal fit', value('grid focal px'), 960 * cam.data.lens / cam.data.sensor_width))
    cam.data.sensor_fit = 'AUTO'
    r.resolution_x, r.resolution_y = 540, 960
    cases.append(('auto fit, portrait', value('grid focal px'), 960 * cam.data.lens / cam.data.sensor_width))
    r.resolution_x, r.resolution_y = 960, 540
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = 4.0
    cases.append(('orthographic, auto fit', value('grid ortho px'), 960 / 4.0))
    cases.append(('orthographic: perspective flag 0', value('grid perspective'), 0.0))
    for name, got, want in cases:
        K.check(f'grid pixel-scale driver, {name}: {got:.3f} (camera: {want:.3f})', abs(got - want) < 1e-3 * max(1, want))


def _camera(sc, name, t):
    """the example built by the port (its camera matches the WebGPU one to the millimetre), robots hidden, at t"""
    rec = EXAMPLES[name](sc, width=960, height=540)
    for r in rec['robots']:
        for o in [r.group] + list(r.group.children_recursive):
            o.hide_render = True
    f = sc.frame_start + int(round(t * sc.render.fps))
    sc.frame_set(f)
    return rec, f


def _read(path):
    """a PNG's encoded values, 0..255 (Non-Color: no colour transform on load)"""
    im = bpy.data.images.load(path)
    im.colorspace_settings.name = 'Non-Color'
    w, h = im.size
    px = np.empty(w * h * 4, np.float32)
    im.pixels.foreach_get(px)
    bpy.data.images.remove(im)
    return (px.reshape(h, w, 4)[::-1, :, :3] * 255.0).astype(np.float64)


def _ramp_distance(a, bg, ends):
    """each pixel's distance (levels) to the nearest of the segments bg -> end (the grid's colour ramps)"""
    best = np.full(a.shape[:2], np.inf)
    for e in ends:
        d = e - bg
        t = np.clip(((a - bg) @ d) / (d @ d), 0, 1)
        best = np.minimum(best, np.linalg.norm(a - (bg + t[..., None] * d), axis=-1))
    return best


def compare(name, t, mine):
    ref = os.path.join(WEBGPU, f'webgpu_{name}_at{t:.2f}s.png')
    if not os.path.exists(ref):
        print(f'SKIP {name}: no WebGPU frame at {ref}', flush=True)
        return
    W, B = _read(ref), _read(mine)
    if W.shape != B.shape:
        K.check(f'{name}: the WebGPU frame and the render are the same size', False, f'{W.shape} vs {B.shape}')
        return
    bg = np.array([v * 255 for v in three_aces(BACKGROUND)])
    ends = [np.array([v * 255 for v in three_aces(c)]) for c in (GRID_LINE, GRID_CENTRE)]
    top = B[:6].reshape(-1, 3).mean(axis=0)
    K.check(f'{name}: the background renders as three ACES shows #c6cfd1 {tuple(int(round(v)) for v in bg)}: '
            f'{tuple(int(round(v)) for v in top)}', np.abs(top - bg).max() < 1.5)
    lw, lb = W.mean(axis=2), B.mean(axis=2)
    # each frame's lines darken the floor below ITS OWN background (the top rows): the WebGPU frame's background is
    # (203, 207, 209), a level under three's ACES of #c6cfd1, and that offset is not line weight
    own_w, own_b = lw[:6].mean(), lb[:6].mean()
    on_ramp = _ramp_distance(W, bg, ends) < 8
    n = 24
    nccs, dark = [], []
    vis = np.zeros(W.shape[:2] + (3,), np.uint8)
    for y in range(0, W.shape[0] - n + 1, n):
        for x in range(0, W.shape[1] - n + 1, n):
            if not on_ramp[y:y + n, x:x + n].all():
                continue                                        # a robot (or anything not the grid) in the block
            a, b = lw[y:y + n, x:x + n], lb[y:y + n, x:x + n]
            if a.std() < 2.0:
                continue                                        # no lines here (above the horizon, between lines)
            ncc = float(((a - a.mean()) * (b - b.mean())).mean() / (a.std() * max(b.std(), 1e-6)))
            nccs.append(ncc)
            dark.append((own_w - a.mean(), own_b - b.mean()))
            vis[y:y + n, x:x + n] = (40, 200, 90) if ncc > 0.5 else (220, 60, 60)
    if not nccs:
        K.check(f'{name}: floor blocks to compare', False, 'none found')
        return
    dark = np.array(dark)
    med = float(np.median(nccs))
    good = float(np.mean(np.array(nccs) > 0.5))
    dw, db = float(np.median(dark[:, 0])), float(np.median(dark[:, 1]))
    # alignment alone does not show a visible grid (round one's 1.2 mm strips correlated at 0.66 on mantis while
    # darkening the floor 0.2 levels against WebGPU's 1.4): the line weight is checked as a ratio of the darkening
    K.check(f'{name}: in {len(nccs)} floor blocks the grid lines land on the WebGPU pixels (median normalised '
            f'cross-correlation {med:.2f}, {good * 100:.0f} % of blocks above 0.5)', med > 0.5 and good > 0.6)
    K.check(f'{name}: the grid darkens the floor as the WebGPU lines do (median darkening WebGPU {dw:.1f}, '
            f'Blender {db:.1f} levels: ratio {db / max(dw, 1e-6):.2f}, within 0.6 .. 1.6)',
            0.6 <= db / max(dw, 1e-6) <= 1.6)
    sheet = np.concatenate([W, B, vis.astype(np.float64)], axis=1)
    out = bpy.data.images.new('studio comparison', sheet.shape[1], sheet.shape[0], alpha=False)
    px = np.ones(sheet.shape[:2] + (4,), np.float32)
    px[..., :3] = sheet[::-1] / 255.0
    out.pixels.foreach_set(px.ravel())
    out.filepath_raw = os.path.join(OUT, f'studio_vs_webgpu_{name}.png')
    out.file_format = 'PNG'
    out.save()
    bpy.data.images.remove(out)


def renders():
    for name, t in SHOTS:
        p = os.path.join(OUT, f'studio_grid_{name}.png')
        if COMPARE_EXISTING:
            if os.path.exists(p):
                compare(name, t, p)
            else:
                print(f'SKIP {name}: no earlier render at {p} to compare', flush=True)
            continue
        sc = K.clean_scene()
        sc.frame_start = 1
        _rec, f = _camera(sc, name, t)
        K.probe_render(sc, (960, 540), 16)
        K.check(f'{name}: the empty studio from its camera at {t} s: still', K.still(sc, sc.camera, f, p))
        if not K.NO_RENDER:
            compare(name, t, p)


def main():
    for fn in (colours, drivers, renders):
        try:
            fn()
        except Exception:  # noqa: BLE001
            K.check(fn.__name__, False, traceback.format_exc().splitlines()[-1])
            traceback.print_exc()
    K.save_results('studio_render')


main()
