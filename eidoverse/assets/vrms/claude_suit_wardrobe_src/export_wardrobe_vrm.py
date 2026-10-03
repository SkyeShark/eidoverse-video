"""Export the claudesona wardrobe VRM from its Blender source.

    bash run_blender.sh eidoverse/assets/vrms/claude_suit_wardrobe_src/export_wardrobe_vrm.py [--out <path.vrm>]

Opens claude_suit_wardrobe.blend (next to this script: digi's claude_suit rig and suit plus every DAISY garment and
accessory layer, images packed) and exports every object, visible or not, to work/claude_suit_wardrobe_base.vrm: the
wardrobe WITHOUT the TuTa. The library VRM (eidoverse/assets/vrms/claude_suit_wardrobe.vrm) is written by
build_tuta.py, which opens this same .blend, adds the TuTa and exports. The export goes to a temporary file first and
replaces the VRM only when it finished, so a render reading the live file never sees half a VRM, and re-applies the
petal ring's chest pivot (ring_pivot.py) to it. Run it through the repository's
run_blender.sh (an isolated Blender user folder; see docs/blender.md). Needs the VRM add-on
(extension `bl_ext.blender_org.vrm`), which run_blender.sh copies into its sandbox.
"""
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = HERE
while REPO != os.path.dirname(REPO) and not os.path.exists(os.path.join(REPO, 'eido.py')):
    REPO = os.path.dirname(REPO)
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = argv[argv.index('--out') + 1] if '--out' in argv else os.path.join(REPO, 'work', 'claude_suit_wardrobe_base.vrm')

bpy.ops.preferences.addon_enable(module='bl_ext.blender_org.vrm')
bpy.ops.wm.open_mainfile(filepath=os.path.join(HERE, 'claude_suit_wardrobe.blend'))
os.makedirs(os.path.dirname(OUT), exist_ok=True)
tmp = OUT.replace('.vrm', '.part.vrm')
res = bpy.ops.export_scene.vrm(filepath=tmp, export_invisibles=True, export_only_selections=False)
if 'FINISHED' in res and os.path.getsize(tmp) > 1_000_000:
    # the petal ring's chest pivot (ring_pivot.py) lives in the VRM, not the .blend: re-apply it to every export
    sys.path.insert(0, HERE)
    from ring_pivot import add_ring_pivot
    add_ring_pivot(tmp, tmp)
    os.replace(tmp, OUT)
    print(f'[wardrobe] exported {OUT} ({os.path.getsize(OUT)} bytes)')
else:
    raise SystemExit(f'[wardrobe] export failed: {res}')
