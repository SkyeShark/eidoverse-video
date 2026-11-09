"""The news set's camera-facing billboards alone, on black (every other mesh hidden, the floods off so their beams
hide too): the steam from the wide and wall cameras, the hand lights from the crowd camera, each with its own
material. Checks that they draw (lit pixels), as the WebGPU's did: the steam once drew nothing at all (the quad's uv
was a 3-vector, so (uv - 0.5) * 2 put z at -1 into the puff's radius and every puff was transparent). Writes
out/steam/<name>.png.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/sets_uf_corridor_news/render_steam_alone.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _fixture as F  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from eidoblend.sets.unknown_force import cn_lib as CL, news as NEWS  # noqa: E402

OUT = F.OUT / 'steam'
OUT.mkdir(parents=True, exist_ok=True)
sc = F.clean_scene()
F.render_settings(960, 540, 16)
N = NEWS.build(sc, {'world': False})
N.apply_look(sc)
w = bpy.data.worlds.new('billboards_black')
w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Color'].default_value = (0, 0, 0, 1)
sc.world = w


def alone(keep, cam, name, t=0.3):
    for o in bpy.data.objects:
        if o.type == 'MESH':
            o.hide_render = o not in keep
    N.update(t, {'spray': 1.0, 'floods': 0.0})                 # floods off: the beams hide (the steam keeps its alpha)
    ob = N.camera(cam, sc)
    N.set_u('pix', CL.pix_of(sc, ob))
    F.render_still(OUT / f'{name}.png', sc)
    a = np.asarray(Image.open(OUT / f'{name}.png').convert('L')).astype(float)
    return int((a > 20).sum()), float(a.max())


n, mx = alone({N.parts['steam']}, 'wide', 'steam_wide')
F.check('steam (wide): the tower plumes and the vents draw on black', n > 3000, f'{n} pixels lit, max {mx:.0f}')
n, mx = alone({N.parts['steam']}, 'wall', 'steam_wall')
F.check('steam (wall): the vent beside the tag draws on black', n > 3000, f'{n} pixels lit, max {mx:.0f}')
n, mx = alone({N.parts['handlights']}, 'crowd', 'handlights_crowd')
F.check('hand lights (crowd): the phones and torches glow', n > 40, f'{n} pixels lit, max {mx:.0f}')
F.summary()
