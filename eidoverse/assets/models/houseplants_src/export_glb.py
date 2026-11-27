"""export_glb.py: the houseplants as glTFs for the three.js edition (Blender, headless).

Run it from the root of a checkout of the Blender edition (branch `blender`), where `eidoblend.props.houseplants` grows
them:

    bash run_blender.sh <this file> --out work/props/houseplants/web [--species monstera,basil]

Each species (rubber_plant, monstera, corn_plant, basil, watering_can) is grown alone at the origin, as
houseplants.build(species, look=False) grows it (the basil with its seed, 11), and written as <species>.glb: its parts
by their builders' names (the material each takes follows from the name, as look.key_of reads it), metres, glTF's Y up
(the plant faces +Z there, its floor at y 0). The leaves keep their own data as custom vertex attributes: _LEAFDATA
(along the blade 0..1, across it 0..1 with the midrib at 0.5, which leaf, how old; the underside's age below zero) and,
on the Monstera, _LEAFQ (where the point lies across its vein's field). Each part's material slot is named for its key
(houseplant.<key>) with a plain viewport colour, so the file reads in any viewer; the three.js module makes the real
materials. pack_glb.mjs (beside the helicopter's sources) then compresses each file.
"""

import json
import os
import sys

import bpy

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
# a plain colour per material key, for viewers that read the file's own materials (linear RGB, roughness)
VIEW = {'leaf_rubber': ((0.010, 0.034, 0.010), 0.2), 'leaf_monstera': ((0.016, 0.060, 0.018), 0.35),
        'leaf_dracaena': ((0.034, 0.120, 0.020), 0.4), 'rubber_stems': ((0.06, 0.09, 0.03), 0.4),
        'monstera_petioles': ((0.05, 0.13, 0.04), 0.35), 'dracaena_shoots': ((0.10, 0.12, 0.04), 0.5),
        'dracaena_bark': ((0.40, 0.31, 0.21), 0.8), 'coir_pole': ((0.075, 0.045, 0.022), 0.95),
        'tie_wire': ((0.03, 0.18, 0.04), 0.3), 'soil': ((0.06, 0.045, 0.03), 0.9), 'leca': ((0.3, 0.12, 0.05), 0.9),
        'terracotta_pot': ((0.35, 0.13, 0.06), 0.85), 'terracotta_saucer': ((0.35, 0.13, 0.06), 0.85),
        'glazed_pot': ((0.045, 0.06, 0.08), 0.25), 'nursery_pot': ((0.025, 0.025, 0.025), 0.55),
        'fibre_clay': ((0.50, 0.49, 0.46), 0.75), 'watering_can': ((0.62, 0.40, 0.01), 0.3),
        'basil_leaf': ((0.022, 0.12, 0.014), 0.34), 'basil_stem': ((0.06, 0.14, 0.03), 0.5),
        'basil_pot': ((0.35, 0.13, 0.06), 0.8), 'compost': ((0.045, 0.03, 0.02), 0.95)}


def opt(k, d=None):
    return ARGS[ARGS.index(k) + 1] if k in ARGS else d


def underscore(me, src, dst, kind):
    a = me.attributes.get(src)
    if a is None:
        return False
    key, n = ('color', 4) if kind == 'FLOAT_COLOR' else ('value', 1)
    vals = [0.0] * (len(a.data) * n)
    a.data.foreach_get(key, vals)
    me.attributes.remove(a)
    b = me.attributes.new(dst, kind, 'POINT')
    b.data.foreach_set(key, vals)
    return True


def main():
    sys.path.insert(0, os.path.join(os.path.abspath(opt('--edition', os.getcwd())), 'blender'))
    from eidoblend.props import houseplants as HP
    from eidoblend.props.houseplants import look as LK
    out = os.path.abspath(opt('--out'))
    os.makedirs(out, exist_ok=True)
    report = {}
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for sp in (opt('--species') or ','.join(HP.SPECIES)).split(','):
        for o in list(bpy.data.objects):                       # (each species alone in the file)
            bpy.data.objects.remove(o, do_unlink=True)
        for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.collections):
            for d in list(coll):
                if d.users == 0 or coll is bpy.data.collections:
                    coll.remove(d)
        p = HP.build(sp, look=False)
        mats = {}
        for o in p.parts:
            k = LK.key_of(o.name)
            if k not in mats:
                m = bpy.data.materials.new(f'houseplant.{k}')
                c, r = VIEW[k]
                m.diffuse_color, m.roughness, m.metallic = (*c, 1.0), r, 0.0
                mats[k] = m
            o.data.materials.clear()
            o.data.materials.append(mats[k])
            underscore(o.data, 'leafdata', '_leafdata', 'FLOAT_COLOR')
            underscore(o.data, 'leafq', '_leafq', 'FLOAT')
        keep = {o.name for o in p.parts} | {p.group.name}
        bpy.context.view_layer.update()
        for o in bpy.data.objects:
            try:
                o.select_set(o.name in keep)
            except RuntimeError:                               # (not in this view layer)
                pass
        path = os.path.join(out, f'{sp}.glb')
        bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_apply=True,
                                  export_attributes=True, export_vertex_color='NONE', export_texcoords=False,
                                  export_normals=True, export_tangents=False, export_materials='VIEWPORT',
                                  export_extras=False, export_yup=True, export_animations=False, export_cameras=False,
                                  export_lights=False, export_image_format='NONE')
        tris = sum(sum(len(f.vertices) - 2 for f in o.data.polygons) for o in p.parts)
        report[sp] = {'bytes': os.path.getsize(path), 'parts': sorted(o.name for o in p.parts), 'triangles': tris}
        print(f'[houseplants export] {sp}: {len(p.parts)} parts, {tris:,} triangles, {os.path.getsize(path) / 1e6:.2f} MB')
    print(json.dumps(report))


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
