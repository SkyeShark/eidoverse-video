"""export_glb.py: the made helicopter as a glTF for the three.js edition (Blender, headless).

Run it in a checkout of the Blender edition (branch `blender`), where `eidoblend.props.helicopter` makes the asset:

    python blender/eidoblend/props/helicopter/make.py --out work/props/helicopter        # -> helicopter.blend, decals/
    bash run_blender.sh <this file> --blend work/props/helicopter/helicopter.blend \
        --decals work/props/helicopter/decals --out work/props/helicopter/web [--mask-caps 0.05,0.035,0.014]

It writes into --out:
    helicopter_raw.glb   the collection 'helicopter' as it renders there: its 290 parts (the high, with each part's
                         modifiers applied), the Empties that turn the rotors (main_rotor under mast_tilt, tail_rotor
                         under tail_rotor_cant) and the seats' marks; per vertex `_masks` (R the nearness of an exposed
                         arris, G of an inside corner, B the openness near, A the openness far) and, on the blades,
                         `_blade` (R across the chord from the leading edge, G along the span); every material by its
                         role (helicopter.paint, helicopter.glass ...) with its base colour, roughness and metalness
    skin_side.png, marks_left.png, marks_right.png, decals.json   the pictures the paint lays through the hull
pack_glb.mjs then compresses the raw file into the library's helicopter.glb.

--mask-caps re-cuts the parts before the masks are measured (hull, big panels, small parts: the longest edge in metres,
as look.apply cuts them): larger caps give fewer faces and coarser wear, the same parts and silhouette. It opens the
made high (helicopter_high.blend beside --blend) and runs the look again with those caps, importing the edition's
package from --edition (default: the working directory, the edition's root).
"""

import json
import os
import shutil
import sys

import bpy

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def opt(k, d=None):
    return ARGS[ARGS.index(k) + 1] if k in ARGS else d


def relook(blend, decals, caps):
    """the made high looked again with other cut caps (eidoblend.props.helicopter.look.apply with its maxe changed)"""
    here = os.path.dirname(os.path.abspath(blend))
    sys.path.insert(0, os.path.join(os.path.abspath(opt('--edition', os.getcwd())), 'blender'))   # the edition's package
    from eidoblend.props.helicopter import look as LOOK
    hull, big, small = (float(v) for v in caps.split(','))
    bpy.ops.wm.open_mainfile(filepath=os.path.join(here, 'helicopter_high.blend'))
    col = bpy.data.collections['helicopter_high']
    orig = LOOK.bake_edges

    def bake_edges(parts, maxe):
        return orig(parts, lambda o: hull if o.name == 'hull' else big if o.name.startswith(LOOK.BIG) else small)
    LOOK.bake_edges = bake_edges
    try:
        LOOK.apply(col, decals)
    finally:
        LOOK.bake_edges = orig
    col.name = 'helicopter'


def viewport_colours(mat):
    """the material's group inputs (or its Principled BSDF) as the viewport colour, roughness and metalness glTF takes"""
    if not mat or not mat.use_nodes:
        return
    for n in mat.node_tree.nodes:
        if n.type == 'GROUP' and 'Base Color' in n.inputs:
            mat.diffuse_color = tuple(n.inputs['Base Color'].default_value)
            mat.roughness = float(n.inputs['Base Rough'].default_value)
            mat.metallic = float(n.inputs['Base Metal'].default_value)
            return
        if n.type == 'BSDF_PRINCIPLED':
            c = n.inputs['Base Color']
            if not c.is_linked:
                mat.diffuse_color = tuple(c.default_value)
            r, m = n.inputs['Roughness'], n.inputs['Metallic']
            mat.roughness = 0.5 if r.is_linked else float(r.default_value)
            mat.metallic = 0.0 if m.is_linked else float(m.default_value)
            return


def underscore(me, src, dst):
    """a point colour attribute copied under a name the exporter writes as a custom attribute, the original removed"""
    a = me.attributes.get(src)
    if a is None:
        return False
    vals = [0.0] * (len(a.data) * 4)
    a.data.foreach_get('color', vals)
    me.attributes.remove(a)
    b = me.attributes.new(dst, 'FLOAT_COLOR', 'POINT')
    b.data.foreach_set('color', vals)
    return True


def main():
    blend, decals, out = (os.path.abspath(opt(k)) for k in ('--blend', '--decals', '--out'))
    os.makedirs(out, exist_ok=True)
    if opt('--mask-caps'):
        relook(blend, decals, opt('--mask-caps'))
    else:
        bpy.ops.wm.open_mainfile(filepath=blend)
    col = bpy.data.collections['helicopter']
    objs = list(col.all_objects)
    meshes = [o for o in objs if o.type == 'MESH']
    n_blade = 0
    for o in meshes:
        me = o.data
        underscore(me, 'masks', '_masks')
        n_blade += underscore(me, 'blade', '_blade')
        for m in me.materials:
            viewport_colours(m)
    for o in bpy.context.view_layer.objects:
        o.select_set(o in objs)
    path = os.path.join(out, 'helicopter_raw.glb')
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_apply=True,
                              export_attributes=True, export_vertex_color='NONE', export_texcoords=False,
                              export_normals=True, export_tangents=False, export_materials='VIEWPORT',
                              export_extras=True, export_yup=True, export_animations=False, export_cameras=False,
                              export_lights=False, export_image_format='NONE')
    for n in ('skin_side.png', 'marks_left.png', 'marks_right.png', 'decals.json'):
        shutil.copyfile(os.path.join(decals, n), os.path.join(out, n))
    faces = sum(len(o.data.polygons) for o in meshes)
    print(json.dumps({'glb': path, 'bytes': os.path.getsize(path), 'parts': len(meshes), 'faces': faces, 'blades': n_blade}))
    sys.stdout.flush()


if __name__ == '__main__':
    try:
        main()
        sys.stdout.flush()
        os._exit(0)
    except BaseException:                                       # noqa: BLE001
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        os._exit(1)
