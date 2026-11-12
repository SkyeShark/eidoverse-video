"""Probe: load_kit on a parts-library GLB (the funeral's props: a bier, candles, a mannequin ...),
parts pulled by name, by family and as islands, placed on a terrain.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 \
        bash run_blender.sh <worktree>/blender/tests/terrain/test_kit.py [--no-render]

(The funeral GLB carries no textures: its role materials were applied at runtime in WebGPU, so the
parts render in the importer's plain materials.)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _fixture as F  # noqa: E402

import bpy  # noqa: E402
from eidoblend.placement import load_kit, place_on, tight_box, run_placement_audits  # noqa: E402

F.clean_scene()
F.render_settings(960, 540, 16)
F.test_daylight(sun_elevation=34, sun_azimuth=210)
ground, h = F.ground(size=20, seed=4, clearing_m=7, relief_m=0.6)
kit = load_kit(F.WORKTREE / 'eidoverse' / 'assets' / 'models' / 'funeral_props.glb')
print('[kit-test] %d parts: %s' % (kit.count, kit.list()))
ok = kit.count > 1
candles = kit.family('candle_pillar')
print('[kit-test] family candle_pillar: %d' % len(candles))
ok = ok and len(candles) >= 2
bier = kit.get(kit.list()[0])
for o in candles + [bier]:
    b = tight_box(o)
    c = (b[0] + b[1]) * 0.5
    centred = abs(c.x) < 1e-3 and abs(c.y) < 1e-3 and abs(b[0].z) < 1e-3
    ok = ok and centred
    print('[kit-test] %-18s %.2f x %.2f x %.2f m, recentred %s' % ((o.name,) + tuple(b[1] - b[0]) + (centred,)))
isl = kit.islands()
print('[kit-test] %d islands from %d parts' % (len(isl), kit.count))
x = -3.5                                       # each candle part is a cluster about 2 m across
for o in candles:
    b = tight_box(o)
    place_on(o, ground, xy=(x, 1.0))
    x += (b[1].x - b[0].x) + 0.3
place_on(bier, ground, xy=(0.0, -1.6))
x = -6.0                                       # the islands in a row behind
for o in isl:
    b = tight_box(o)
    w = b[1].x - b[0].x
    place_on(o, ground, xy=(x + w / 2, 4.0))
    x += w + 0.4
res = run_placement_audits()
deep = [r for r in res['clipping'] if r.get('deep')]
ok = ok and not res['floaters'] and not deep
print('[kit-test] %s (floaters %d, deep overlaps %d)' % ('PASS' if ok else 'FAIL', len(res['floaters']), len(deep)))
if '--no-render' not in F.args():
    cam = F.camera('cam_kit', (0.4, -6.5, 2.4), (0.0, 1.5, 0.5), 35)
    F.render(cam, F.OUT / 'kit.png')
