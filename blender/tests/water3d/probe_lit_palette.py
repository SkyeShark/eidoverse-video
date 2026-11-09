"""The lit water's palette on a baked scene: re-shade a saved water .blend with other look values and render.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/water3d/probe_lit_palette.py -- blend=out/w3d_pour.blend frames=60,144 \
        variants=as_baked,defaults [samples=64]

Each variant rebuilds the water material with create_water_sim's look options over the same baked PLY sequence
(the player's Set Material node takes the new material) and renders the frames to
out/verify/palette_<variant>_f####.png, then tiles them into out/verify/palette_sheet.png (rows = variants).
Variants (VARIANTS below; add more there): as_baked (the file's own material), defaults (the engine's palette:
DEFAULTS' look values), defaults_foam (that palette with the pour's foam). world3= and center3= give the baked
domain in three axes (the sparkle's uvw); the defaults are the pour's.
"""

import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
sys.path.insert(0, HERE)
a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
A = dict(x.split('=', 1) for x in a if '=' in x)
BLEND = A['blend'] if os.path.isabs(A['blend']) else os.path.join(HERE, A['blend'])
FRAMES = [int(x) for x in A.get('frames', '60').split(',')]
OUT = os.path.join(HERE, 'out', 'verify')
os.makedirs(OUT, exist_ok=True)

# look values per variant (DEFAULTS' names); 'as_baked' keeps the file's material
VARIANTS = {
    'as_baked': None,
    'defaults': dict(),
    'defaults_foam': dict(foam_strength=0.35, foam_churn=0.35, churn_speed=2.6),
}
names = [v for v in A.get('variants', 'as_baked,defaults').split(',')]

bpy.ops.wm.open_mainfile(filepath=BLEND)
import _scene as S  # noqa: E402,F401  (after the open: the module's helpers only)
from eidoblend.fx.water3d.water import DEFAULTS  # noqa: E402
from eidoblend.fx.water3d.material import build_water_material  # noqa: E402

sc = bpy.context.scene
if 'samples' in A:
    sc.eevee.taa_render_samples = int(A['samples'])
player = [ob for ob in sc.objects if 'water3d_player' in ob.modifiers][0]
tree = player.modifiers['water3d_player'].node_group
setm = [n for n in tree.nodes if n.bl_idname == 'GeometryNodeSetMaterial'][0]
baked = setm.inputs['Material'].default_value
world3 = None
shots = []
for nm in names:
    if VARIANTS[nm] is None:
        mat = baked
    else:
        o = dict(DEFAULTS)
        o.update(VARIANTS[nm])
        o['shading'] = 'lit'
        # the domain the attributes were baked in: read back from the file's sparkle uvw (the material's own nodes)
        gs = [float(x) for x in A.get('world3', '1.4,1.4,1.4').split(',')]
        c3 = [float(x) for x in A.get('center3', '0,0.7,0').split(',')]
        mat = build_water_material('palette_' + nm, o, gs, c3, sc.render.fps, sc.frame_start, scene=sc)
    setm.inputs['Material'].default_value = mat
    for f in FRAMES:
        p = os.path.join(OUT, f'palette_{nm}_f{f:04d}.png')
        S.render(sc, f, p)
        shots.append(p)
S.contact_sheet(shots, os.path.join(OUT, 'palette_sheet.png'), cols=len(FRAMES), half=False)
