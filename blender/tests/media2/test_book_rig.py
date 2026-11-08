"""Probe: make_book(rig={...}), a raw makeBookRig spec (no GLB, no makeBookFromSpec arithmetic), in EEVEE.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/media2/test_book_rig.py

The spec is the janus book's measure written out by hand (boardLen, jointX, foreX, halfH, halfT, lip, round, uJoint)
with 16 leaves, a plain blue cloth and six of the janus spreads: closed at frame 1, open by 12, a leaf turned over
14..28, then shut again by 40. Checks the rig took the spec as given, the underside on the desk through the move, the
rig's frames, and renders frames 1, 12, 21 and 40 -> out/book_rig_f*.png and out/book_rig_sheet.png.
Prints PASS/FAIL lines.
"""
import sys
from pathlib import Path

import bpy
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'media'))
import _stage as S  # noqa: E402
from eidoblend.media import book  # noqa: E402

OUT = HERE / 'out'
FAILS = []
RIG = {'boardLen': 0.1504, 'jointX': 0.0727, 'foreX': 0.0777, 'halfH': 0.11095, 'halfT': 0.01322, 'lip': 0.0055853,
       'round': 0.0024147, 'uJoint': 0.4573174, 'pages': 16, 'openAt': 1, 'angle': 180, 'pageAngle': 179}


def check(ok, what):
    print(f"{'PASS' if ok else 'FAIL'} {what}", flush=True)
    if not ok:
        FAILS.append(what)


sc = S.fresh_scene(res=(640, 360), samples=16, frames=(1, 40))
sc.eevee.shadow_ray_count = 4
sc.eevee.shadow_step_count = 12
plan = book.schedule((1, 40), open=[(1, 0.0), (12, 1.0), (30, 1.0), (40, 0.0)], turns=[(14, 28)])
spreads = sorted((S.ASSETS / 'book_spreads').glob('*.jpg'))[:6]
b = book.make_book(OUT / 'book_rig_work', plan, rig=dict(RIG), spreads=spreads, cover={'color': '#1d4f8a'},
                   name='rigbook')
got = b.info['rig']
check(all(abs(got[k] - v) < 1e-9 for k, v in RIG.items() if isinstance(v, float)) and got['pages'] == 16,
      f'the rig took the spec as given: {({k: got[k] for k in ("boardLen", "halfT", "pages", "openAt")})}')
m = b.metrics
check(abs(m['BOARD_LEN'] - RIG['boardLen']) < 1e-9 and abs(m['HALF_T'] - RIG['halfT']) < 1e-9
      and m['N_LEAF'] == 16, f"metrics: BOARD_LEN {m['BOARD_LEN']}, HALF_T {m['HALF_T']}, N_LEAF {m['N_LEAF']}")
check(b.max_page == 5 and b.page_at(1) == 0 and b.page_at(30) == 1 and b.open_amount(12) == 1.0,
      f'max page {b.max_page} with 6 spreads; pages {b.page_at(1)} -> {b.page_at(30)}; open at 12: '
      f'{b.open_amount(12)}')
under = [fr['minZ'] - b.states[0]['minZ'] for fr in b.states]
check(min(under) > -0.0015, f'the underside stays on the desk through the move (lowest {min(under) * 1000:.2f} mm)')
check(set(b.frames) == {'case_frame', 'page_frame'}, f'rig.frames: {sorted(b.frames)}')
check(b.code_surfaces() is False, 'code_surfaces() gated off (no code=True)')
if '--no-render' in sys.argv:                          # the checks only (no GPU slot needed)
    print(f'[test_book_rig] checks only: {"ALL OK" if not FAILS else f"{len(FAILS)} FAILED"}', flush=True)
    raise SystemExit(0)
S.box(sc, 'desk', (1.4, 0.9, 0.04), (0.05, 0.1, -0.02),
      S.pbr_material('desk_wood', S.cached('textures', 'PaintedWood009C_2k'), scale=1.4))
b.root.rotation_euler.z = -0.2
S.area_light(sc, (-0.6, -0.4, 0.75), (0, 0, 0), 30.0, size=0.7, color=(1.0, 0.93, 0.84), name='window')
S.area_light(sc, (0.7, 0.3, 0.6), (0, 0, 0), 6.0, size=0.8, color=(0.8, 0.86, 1.0), name='fill')
S.camera(sc, (0.05, -0.40, 0.38), (0.0, 0.0, 0.0), lens=35)
stills = []
for f in (1, 12, 21, 40):
    p = S.render_still(sc, f, OUT / f'book_rig_f{f:03d}.png')
    a = np.asarray(Image.open(p).convert('RGB')).astype(float)
    check(a.std() > 12, f'{p.name}: rendered (std {a.std():.1f})')
    stills.append(p)
blue = np.asarray(Image.open(stills[0]).convert('HSV')).astype(float)
cloth_px = int((((blue[..., 0] * 360 / 255) > 195) & ((blue[..., 0] * 360 / 255) < 235)
                & (blue[..., 1] > 80) & (blue[..., 2] > 40)).sum())
check(cloth_px > 3000, f'closed at frame 1: the blue cloth cover fills {cloth_px} px')
tw, th, pad = 480, 270, 6
sheet = Image.new('RGB', (2 * (tw + pad) + pad, 2 * (th + 24 + pad) + pad), (18, 18, 22))
d = ImageDraw.Draw(sheet)
fnt = ImageFont.truetype(str(S.ASSETS / 'fonts' / 'ShareTechMono-Regular.ttf'), 15)
for i, (p, lab) in enumerate(zip(stills, ['closed, f1', 'open, f12', 'a leaf mid-turn, f21', 'shut again, f40'])):
    x, y = pad + (i % 2) * (tw + pad), pad + (i // 2) * (th + 24 + pad)
    d.text((x, y + 3), f'make_book(rig=...): {lab}', font=fnt, fill=(232, 228, 216))
    sheet.paste(Image.open(p).convert('RGB').resize((tw, th), Image.Resampling.LANCZOS), (x, y + 24))
sheet.save(OUT / 'book_rig_sheet.png')
print(f'[test_book_rig] {"ALL OK" if not FAILS else f"{len(FAILS)} FAILED"}', flush=True)
