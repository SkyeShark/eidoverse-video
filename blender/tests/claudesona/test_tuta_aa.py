"""The TuTa's screen-space anti-aliasing (claudesona/tuta.py, TSL.fw): every seam, stitch and pipe, the knee panels'
rip-stop grid, the badges' ghosts and the catchlights' scanline take the pixel's footprint as the JS's fwidth bands
did: a band thinner than a pixel widens to it and dims, its energy kept, so it holds still in motion.

Checks (always, no render), on claude_suit_wardrobe.vrm at the films' 0.87 in the TuTa:
    the tuta, boot, webbing, face-paint and catchlight materials carry the footprint (the voice-machine kit's
        pixel_footprint, its nodes named cs.* with its drivers on the render size); a rebuild leaves one set each
    the webbing's UV density (v per rest metre) is measured from its mesh, for its ribs' band
Render (unless --no-render): the full figure in a 960 x 540 frame (about 3 mm of suit a pixel, the stitches and the
1.1 mm rip-stop lines under a pixel), the image moved 0.37 px a frame by the lens shift (a pure sub-pixel translation:
the same frame, pose, lights and EEVEE samples every time), 8 positions, twice: with every edge at the fixed 0.2 mm the
edition drew before (patched in here, test scaffolding) and with the footprint. The shimmer is each pixel's second
difference in time, |f(t-1) - 2 f(t) + f(t+1)|, over the band pixels (where the two renders differ: the footprint
changes nothing else): a steady sub-pixel translation leaves only a moving edge's own small curvature term, aliasing
leaves much more.
    out/tuta_aa_sheet.png: the legs (pockets, piping, stitches) and the chest in both, and the legs' shimmer
    out/closeup_fixed.png, closeup_footprint.png: the chest at 0.9 m, where the stitches span pixels (as crisp in both)
    out/tuta_aa.json: the numbers

    bash run_blender.sh blender/tests/claudesona/test_tuta_aa.py [--no-render]
    # a GPU job; on a shared machine queue it with EIDO_GPU_WRAP (blender/tests/_where.py)
"""

import json
import math
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stage as S  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.characters import load_vrm, play_vrma_default  # noqa: E402
from eidoblend.characters.claudesona import tuta as TU  # noqa: E402
from eidoblend.characters.claudesona.wardrobe import make_wardrobe  # noqa: E402

ARGS = S.argv()
RENDER = '--no-render' not in ARGS
FPS, FRAME, SCALE = 30, 40, 0.87
W, H = 960, 540
STEP = 0.37                     # px of image translation per position
N = 8
MATS = ('tuta', 'boot_upper', 'boot_sole', 'webbing', 'face', 'Material')     # the buckle draws no band (nor did the JS)
OUT = os.path.join(S.OUT, 'tuta_aa')
os.makedirs(OUT, exist_ok=True)


def footprint_nodes(m):
    return [n for n in m.node_tree.nodes if n.name.startswith('cs.footprint.')]


def resolution_drivers(m):
    ad = m.node_tree.animation_data
    return [fc for fc in (ad.drivers if ad else []) if fc.data_path.startswith('nodes["cs.footprint.')
            and any(v.targets[0].data_path.startswith('render.resolution') for v in fc.driver.variables)]


def build():
    sc = S.clean_scene(FPS)
    h = load_vrm('claude_suit_wardrobe', name='tuta_aa')
    h.arm.scale = (SCALE,) * 3
    sc.frame_start, sc.frame_end = 1, 60
    play_vrma_default(h, 'idle', t=0.0, loop=True, until=2.0)
    wd = make_wardrobe(h, wear='tuta')
    wd.face_paint(True)
    for k in ('mod_red', 'mod_gold', 'mod_chrome'):
        wd.pin(k)
    return sc, h, wd


def wiring(C, R, wd):
    counts = {}
    for name in MATS:
        for m in wd.mats.get(name, []):
            counts[m.name] = (len(footprint_nodes(m)), len(resolution_drivers(m)))
    R['footprint_nodes'] = counts
    ok = bool(counts) and all(n > 0 and d == 3 for n, d in counts.values())
    C.check('every TuTa material carries the footprint, its three drivers on the render size', ok,
            ', '.join(f'{k}: {n} nodes, {d} drivers' for k, (n, d) in sorted(counts.items())))
    wd._surfaces()                          # a rebuild (what a second make_wardrobe on the same model does)
    again = {m.name: (len(footprint_nodes(m)), len(resolution_drivers(m))) for name in MATS
             for m in wd.mats.get(name, [])}
    C.check('a rebuild leaves one footprint per material (clear_cs removes the old, drivers included)',
            again == counts, f'{sum(n for n, _d in again.values())} footprint nodes after, '
                             f'{sum(n for n, _d in counts.values())} before')
    v = float(getattr(wd, 'webbing_v_per_m', 0.0))
    R['webbing_v_per_m'] = v
    C.check("the webbing's UV density is measured from its mesh", 5.0 < v < 5000.0, f'{v:.1f} v per rest metre')


def frames(sc, cam, tag):
    paths = []
    sh0 = cam.data.shift_x
    for i in range(N):
        cam.data.shift_x = sh0 + i * STEP / max(W, H)        # shift is in units of the frame's larger side
        p = os.path.join(OUT, f'{tag}_{i}.png')
        S.still(sc, cam, FRAME, p)
        paths.append(p)
    cam.data.shift_x = sh0
    return paths


def load(paths):
    import OpenImageIO as oiio
    return np.stack([np.asarray(oiio.ImageBuf(p).get_pixels(oiio.FLOAT), np.float64)[..., :3] for p in paths])


def shimmer(stack, box):
    y0, y1, x0, x1 = box
    a = stack[:, y0:y1, x0:x1].mean(axis=3)
    d2 = np.abs(a[:-2] - 2.0 * a[1:-1] + a[2:])                  # (N - 2, h, w)
    return d2, float(d2.mean()), float(np.percentile(d2, 99))


def crop(img, cx, cy, w, h):
    y0, x0 = max(0, int(cy - h // 2)), max(0, int(cx - w // 2))
    return img[y0:y0 + h, x0:x0 + w]


def save(path, img):
    import OpenImageIO as oiio
    a = np.ascontiguousarray((np.clip(img, 0.0, 1.0) * 255 + 0.5).astype(np.uint8))
    out = oiio.ImageOutput.create(path)
    out.open(path, oiio.ImageSpec(a.shape[1], a.shape[0], 3, 'uint8'))
    out.write_image(a)
    out.close()


def to_px(sc, cam, p):
    from bpy_extras.object_utils import world_to_camera_view
    v = world_to_camera_view(sc, cam, Vector(p))
    return v.x * W, (1.0 - v.y) * H


def render(C, R, sc, h, wd):
    S.probe_render(sc, res=(W, H), samples=16)
    S.turntable_studio(sc, light=0.45, background=0x14161c)
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_depth = '16'
    sc.render.use_motion_blur = False
    hb = h.arm.matrix_world @ h.arm.data.bones[h.humanoid['head']].head_local
    body_c = Vector((hb.x, hb.y, hb.z * 0.55))
    cam = S.camera('aa_cam', lens=40)
    a = math.radians(20)
    S.aim(cam, (body_c.x + 3.2 * math.sin(a), body_c.y - 3.2 * math.cos(a), body_c.z + 0.15), body_c)
    sc.camera = cam
    sc.frame_set(FRAME)
    bones = [h.arm.matrix_world @ pb.head for pb in h.arm.pose.bones]
    pts = np.array([to_px(sc, cam, p) for p in bones])
    pad = 40
    box = (max(0, int(pts[:, 1].min()) - pad), min(H, int(pts[:, 1].max()) + pad),
           max(0, int(pts[:, 0].min()) - pad), min(W, int(pts[:, 0].max()) + pad))
    knee = to_px(sc, cam, h.arm.matrix_world @ h.arm.pose.bones[h.humanoid['leftLowerLeg']].head)
    chest = to_px(sc, cam, h.arm.matrix_world @ h.arm.pose.bones[h.humanoid['chest']].head)
    # a close-up of the chest (0.9 m, the stitches several pixels wide): the footprint must leave it as crisp
    chest_w = h.arm.matrix_world @ h.arm.pose.bones[h.humanoid['chest']].head
    close = S.camera('aa_close', lens=50)
    S.aim(close, (chest_w.x + 0.9 * math.sin(math.radians(15)), chest_w.y - 0.9 * math.cos(math.radians(15)),
                  chest_w.z + 0.02), chest_w)

    def closeup(tag):
        S.still(sc, close, FRAME, os.path.join(OUT, f'closeup_{tag}.png'))
        sc.camera = cam
    # the edges at a fixed 0.2 mm: the edition before the footprint (patched over the property, rebuilt)
    real = TU.TSL.fw
    TU.TSL.fw = property(lambda self: 0.0002)
    try:
        wd._surfaces()
        fixed = load(frames(sc, cam, 'fixed'))
        closeup('fixed')
    finally:
        TU.TSL.fw = real
    wd._surfaces()
    foot = load(frames(sc, cam, 'footprint'))
    closeup('footprint')
    d_fix, m_fix, p_fix = shimmer(fixed, box)
    d_ft, m_ft, p_ft = shimmer(foot, box)
    mean_fix, mean_ft = float(fixed[:, box[0]:box[1], box[2]:box[3]].mean()), float(foot[:, box[0]:box[1],
                                                                                          box[2]:box[3]].mean())
    # the band pixels: where the two differ at all (the footprint changes nothing else: silhouettes, wide edges and
    # the weave move with the image in both, and a moving edge's own second difference is the floor here, about
    # 0.137 x the image's curvature at 0.37 px a frame)
    lum_fix, lum_ft = (s[:, box[0]:box[1], box[2]:box[3]].mean(axis=3) for s in (fixed, foot))
    bands = np.abs(lum_fix.mean(0) - lum_ft.mean(0)) > 0.004
    b_fix, b_ft = (np.abs(a[:-2] - 2.0 * a[1:-1] + a[2:])[:, bands] for a in (lum_fix, lum_ft))
    bm_fix, bm_ft = float(b_fix.mean()), float(b_ft.mean())
    bp_fix, bp_ft = float(np.percentile(b_fix, 99)), float(np.percentile(b_ft, 99))
    R.update({'box': box, 'shimmer_fixed': {'mean': m_fix, 'p99': p_fix}, 'shimmer_footprint': {'mean': m_ft,
                                                                                                  'p99': p_ft},
              'band_pixels': int(bands.sum()), 'band_shimmer_fixed': {'mean': bm_fix, 'p99': bp_fix},
              'band_shimmer_footprint': {'mean': bm_ft, 'p99': bp_ft},
              'mean_level_fixed': mean_fix, 'mean_level_footprint': mean_ft})
    C.check('the footprint holds the seams and stitches still: less shimmer on them than with the fixed 0.2 mm edges',
            bm_ft < 0.8 * bm_fix and bp_ft < 0.85 * bp_fix,
            f'{int(bands.sum())} band pixels: mean |second difference in time| {bm_ft:.4f} vs {bm_fix:.4f} '
            f'({100 * (1 - bm_ft / bm_fix):.0f} % less), 99th percentile {bp_ft:.4f} vs {bp_fix:.4f}; over the whole '
            f'figure (silhouettes and wide edges alike in both) {m_ft:.5f} vs {m_fix:.5f}')
    C.check("the bands keep their energy: the figure's mean level within 2 % of the fixed edges'",
            abs(mean_ft - mean_fix) < 0.02 * max(mean_fix, 1e-6), f'{mean_ft:.4f} vs {mean_fix:.4f}')
    # the sheet: legs and chest in both (x3, nearest), and the shimmer of each (the max over time, x8 gain)
    tiles = []
    for nm, c, (cw, ch) in (('knee', knee, (160, 100)), ('chest', chest, (160, 100))):
        for stack in (fixed, foot):
            tiles.append(np.repeat(np.repeat(crop(stack[N // 2], c[0], c[1], cw, ch), 3, 0), 3, 1))
    for d in (d_fix, d_ft):
        g = np.clip(d.max(axis=0) * 8.0, 0.0, 1.0)
        full = np.zeros((H, W))
        full[box[0]:box[1], box[2]:box[3]] = g
        c2 = crop(full, knee[0], knee[1], 160, 100)
        tiles.append(np.repeat(np.repeat(np.stack([c2] * 3, -1), 3, 0), 3, 1))
    th, tw = max(t.shape[0] for t in tiles), max(t.shape[1] for t in tiles)
    rows = [tiles[0:2], tiles[2:4], tiles[4:6]]
    sheet = np.zeros((th * 3, tw * 2, 3))
    for r, row in enumerate(rows):
        for c, t in enumerate(row):
            sheet[r * th:r * th + t.shape[0], c * tw:c * tw + t.shape[1]] = t
    save(os.path.join(OUT, 'tuta_aa_sheet.png'), sheet)
    R['sheet'] = os.path.join(OUT, 'tuta_aa_sheet.png')


def main():
    R, C = {}, S.Checks('tuta_aa')
    sc, h, wd = build()
    wiring(C, R, wd)
    if RENDER:
        render(C, R, sc, h, wd)
    with open(os.path.join(OUT, 'tuta_aa.json'), 'w', encoding='utf-8') as f:
        json.dump(R, f, indent=1, default=str)
    print(f"[tuta_aa] {'PASS' if C.all_pass else 'FAIL'}: {sum(not r['pass'] for r in C.rows)} failed check(s)")


main()
