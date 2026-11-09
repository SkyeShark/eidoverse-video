"""The verifier's stills: the shots the fixes touch, and close-ups the set renders never framed.

Corridor: the cap and door cameras (the pedestal's marble), the AI FORCE patch on the wall, the uniform on its stand
(sash, ribbon bar, sleeve patch, aiguillette, epaulettes), the cap on its cushion (badge, braid, patent visor), the poll
board's recount from the poll camera. News: the claudesona on the mark in the fence and wall cameras (the wall clean of
the fence's shadows, her own shadow from the crew LED), the crowd, wide and pov cameras (the signs lit by news.js's
normals: the crowd side bright, her side glowing through), the van's livery, a fence sign, the transformer yard.
Both: one camera under plain AgX and under cn_lib.ACES_LIKE_LOOK, measured against the WebGPU frame of that camera
(co_final_8 / nw_final_2, read from the main checkout's probes).

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <this folder>/verify_probes.py [corridor|news|both]

Writes out/verify/<set>/<shot>.png and a sheet per set (out/verify/<set>_sheet.png).
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _fixture as F  # noqa: E402
import render_shots as RS  # noqa: E402

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.sets.unknown_force import cn_lib as CL, corridor as COR, news as NEWS  # noqa: E402

A = F.args()
WHICH = next((a for a in A if a in ('corridor', 'news', 'both')), 'both')
OUT = F.OUT / 'verify'
WEBGPU = Path('C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01/work/unknown_force/sets/probes')


def grey(path):
    import numpy as np
    from PIL import Image
    return np.asarray(Image.open(path).convert('L')).astype(float)


def tone_pair(S, sc, out, names, cam, st, webgpu_png, regions, t=0.0):
    """The camera under plain AgX and under cn_lib.ACES_LIKE_LOOK; each region's mean against the WebGPU frame's."""
    S.update(t, st)
    rows = []
    for tag, lk in (('agx', 'None'), ('aces_like', CL.ACES_LIKE_LOOK)):
        sc.view_settings.look = lk
        RS.render(S, sc, out / f'{cam}_{tag}.png', cam)
        names.append(f'{cam}_{tag}')
        g = grey(out / f'{cam}_{tag}.png')
        rows.append([g[r].mean() for r in regions.values()])
    sc.view_settings.look = 'None'
    w = grey(webgpu_png) if Path(webgpu_png).is_file() else None
    if w is None:
        return
    ref = [w[r].mean() for r in regions.values()]
    err = [sum(abs(a - b) for a, b in zip(row, ref)) / len(ref) for row in rows]
    detail = '; '.join(f'{k} webgpu {r:.0f} agx {a:.0f} aces-like {b:.0f}'
                       for k, r, a, b in zip(regions, ref, rows[0], rows[1]))
    F.check(f'{cam}: the ACES-like AgX look lands nearer the WebGPU frame than plain AgX (mean |d| '
            f'{err[0]:.1f} -> {err[1]:.1f} levels)', err[1] < err[0], detail)


def b3(p):
    return Vector(CL.b3(p))


def close(S, sc, out, names, name, pos3, tgt3, fov, st, t=0.0):
    """A still from a camera of my own (three-space position and target, set-local)."""
    ob = RS.look_cam(f'verify_{name}', b3(pos3), b3(tgt3), fov)
    S.update(t, st)
    sc.camera = ob
    S.set_u('pix', CL.pix_of(sc, ob))
    F.render_still(out / f'{name}.png', sc)
    names.append(name)


def corridor():
    out = OUT / 'corridor'
    out.mkdir(parents=True, exist_ok=True)
    sc = RS.setup()
    C = COR.build(sc, {'postText': 'AMERICANISM, NOT EFFECTIVE ALTRUISM'})
    C.apply_look(sc)
    C.apply_post(sc, aeropittura=False)
    names = []
    for cam in ('cap', 'door', 'postWall'):
        C.update(0.0, {'post': 1.0})
        RS.render(C, sc, out / f'{cam}.png', cam)
        names.append(cam)
    C.update(0.0, {'post': 1.0, 'tally': [512000, 418000, 141000]})
    RS.render(C, sc, out / 'poll_recount_stamped.png', 'poll')
    names.append('poll_recount_stamped')
    st = {'post': 1.0}
    close(C, sc, out, names, 'patch_on_the_wall', (-1.6, 5.4, -1.2), (-4.95, 6.2, -4.0), 34, st)
    close(C, sc, out, names, 'uniform_close', (-2.55, 1.5, -2.85), (-3.75, 1.2, -4.6), 30, st)
    close(C, sc, out, names, 'cap_on_cushion_close', (-1.75, 1.42, -0.55), (-2.45, 1.12, -1.3), 28, st)
    close(C, sc, out, names, 'pedestal_close', (-1.3, 0.95, 0.2), (-2.45, 0.6, -1.3), 34, st)
    g = grey(out / 'pedestal_close.png')[150:460, 350:550]          # the pedestal's front face
    F.check('pedestal: its marble shows its veins (it once read one texel of the walls\' uv: a flat block)',
            g.std() > 6.0, f'luminance std {g.std():.1f} over the face')
    tone_pair(C, sc, out, names, 'cap', st, WEBGPU / 'co_final_8.png',
              {'wall': (slice(60, 120), slice(250, 400)), 'floor': (slice(420, 500), slice(650, 750)),
               'cap': (slice(270, 285), slice(400, 460)), 'cushion': (slice(330, 350), slice(350, 450))})
    RS.contact_sheet(out, names, OUT / 'corridor_sheet.png')
    C.dispose()


def news():
    out = OUT / 'news'
    out.mkdir(parents=True, exist_ok=True)
    sc = RS.setup()
    N = NEWS.build(sc)
    N.apply_look(sc)
    N.apply_post(sc, aeropittura=False)
    names = []
    her = RS.place_her()
    for cam in ('fence', 'wall'):
        N.update(0.3, {'spray': 1.0})
        RS.render(N, sc, out / f'{cam}_her_on_the_mark.png', cam)
        names.append(f'{cam}_her_on_the_mark')
    RS.show(her, False)
    for cam in ('wall', 'crowd', 'wide', 'pov'):
        N.update(0.3, {'spray': 1.0})
        RS.render(N, sc, out / f'{cam}.png', cam)
        names.append(cam)
    big = grey(out / 'crowd.png')[140:160, 100:200]                    # NOT IN OUR TOWN, seen from the crowd's side
    F.check("crowd: the signs' crowd side takes the floods head-on, as news.js's normals lit it (the WebGPU frame: "
            "246)", big.mean() > 195, f'paper {big.mean():.0f}')
    st = {'spray': 1.0}
    tone_pair(N, sc, out, names, 'crowd', st, WEBGPU / 'nw_final_2.png',
              {'sign': (slice(140, 160), slice(100, 200)), 'figure': (slice(380, 420), slice(440, 470)),
               'ground': (slice(470, 520), slice(700, 800)), 'wall': (slice(140, 180), slice(600, 700))}, t=0.3)
    close(N, sc, out, names, 'van_livery', (-10.4, 1.7, 17.4), (-12.2, 1.5, 12.2), 40, st, t=0.3)
    close(N, sc, out, names, 'fence_sign_close', (-5.9, 1.6, 6.4), (-6.6, 1.65, 3.2), 30, st, t=0.3)
    close(N, sc, out, names, 'transformer_yard', (28.5, 3.4, 4.0), (32.5, 2.6, -6.4), 46, st, t=0.3)
    RS.contact_sheet(out, names, OUT / 'news_sheet.png')
    N.dispose()


if WHICH in ('corridor', 'both'):
    corridor()
if WHICH in ('news', 'both'):
    news()
F.summary()
