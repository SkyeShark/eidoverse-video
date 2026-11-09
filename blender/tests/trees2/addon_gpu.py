"""The SeedThree add-on's operators that render (the GPU half of SeedThree-blender's
test_addon.py): Grow with baked cards and the billboard, Bake billboard (rebake),
Export .glb baking a missing billboard first, Export PNG, and the Environment
folder's sun / haze / preview hooks on a small demo scene.

    bash run_blender.sh blender/tests/trees2/addon_gpu.py
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _scene as S  # noqa: E402
import bpy  # noqa: E402

from eidoblend.trees import raw  # noqa: E402


def main():
    raw()
    import seedthree
    from seedthree import glb as G
    scene = S.reset()
    seedthree.register()
    try:
        S.render_settings(scene, 480, 270, 8)
        st = scene.seedthree
        st.auto_regrow = False
        st.species = 'whiteOak'
        st.seed = 1737
        st.level = 'ALL'
        st.cards = True
        st.billboard = True
        st.cardRes = '256'
        st.billboardRes = '512'
        sun, _ = S.sky_and_sun(scene, sun_elev_deg=35, sun_az_deg=210, strength=0.10, sun_strength=4.0)
        st.sun = sun
        bpy.ops.seedthree.grow()
        root = bpy.data.objects.get(st.last_root)
        levels = sorted({ch.get('seedthree_lod') or ('BB' if ch.get('seedthree_billboard') else None)
                         for ch in root.children} - {None})
        S.check('Grow (cards + billboard) builds LOD0-2 and BB', levels == ['BB', 'LOD0', 'LOD1', 'LOD2'], str(levels))
        cards = [m for m in bpy.data.materials if m.get('st_card')]
        S.check('the card set is baked (256 px)', cards and all(
            n.image.size[0] == 256 for m in cards for n in m.node_tree.nodes if n.type == 'TEX_IMAGE'), '%d card materials' % len(cards))
        before = {m.name for m in bpy.data.materials if m.get('st_billboard')}
        res = bpy.ops.seedthree.bake_billboard()
        bb = [o for o in bpy.data.objects if o.get('seedthree_billboard_card') and o.parent and o.parent.parent == root]
        S.check('Bake billboard replaces the pair', 'FINISHED' in res and len(bb) == 2, '%d cards (materials before %d)' % (
            len(bb), len(before)))
        # a tree without a billboard: the export bakes one first, as the app's Download .glb does
        st.billboard = False
        st.seed = 7
        bpy.ops.seedthree.grow()
        path = os.path.join(tempfile.mkdtemp(), 'oak7.glb')
        res = bpy.ops.seedthree.export_glb(filepath=path)
        doc, _ = G.read_glb(path)
        names = [n.get('name') for n in doc['nodes']]
        S.check('Export .glb bakes the missing billboard and writes White_Oak_LOD3', 'FINISHED' in res and
                'White_Oak_LOD3' in names and 'billboard_front' in names, json.dumps([n for n in names if 'LOD' in n]))
        cam = S.camera(scene, (16.0, -22.0, 6.0), (0.0, 0.0, 6.0), lens=35)
        png = os.path.join(S.OUT, 'addon_export_png.png')
        res = bpy.ops.seedthree.export_png(filepath=png)
        S.check('Export PNG renders the camera', 'FINISHED' in res and os.path.isfile(png))
        # what renders: the MESH objects under the root (the billboard's cards hang under its
        # Empty, whose own visibility draws nothing)
        def shown():
            return sorted({('BB' if o.get('seedthree_billboard_card') else o.get('seedthree_lod'))
                           for o in bpy.data.objects.get(st.last_root).children_recursive
                           if o.type == 'MESH' and not o.hide_render})
        st.preview = 'LOD2'
        S.check('Preview level LOD2 after the export bake', shown() == ['LOD2'], str(shown()))
        st.preview = 'BB'
        S.check('Preview level BB shows the baked billboard alone', shown() == ['BB'], str(shown()))
    finally:
        seedthree.unregister()
    S.summary('addon_gpu')


main()
