"""export_glb.py: the made carbine as a glTF and its baked maps for the three.js edition (Blender, headless).

Run it from the root of a checkout of the Blender edition (branch `blender`), where `eidoblend.props.carbine` makes the
asset:

    python blender/eidoblend/props/carbine/make.py --out work/props/carbine     # -> carbine.blend, bake/ (~15 min)
    bash run_blender.sh <this file> --blend work/props/carbine/carbine.blend --bake work/props/carbine/bake \
        --out work/props/carbine/web
    python <this folder>/compress_maps.py work/props/carbine/web           # the maps re-stored losslessly (Pillow)

It reads the look's CC0 photographs through the edition's library (EIDO_ASSET_CACHE / fetched once) to record their
means. It writes into --out:
    carbine.glb            the collection 'carbine': the low's 64 parts at identity in the carbine's space (Y up in
                           glTF: +X to the muzzle, +Y up, +Z the carbine's right), one UV set, MikkTSpace tangents, the
                           materials carbine.layered and carbine.lens_coated by name
    carbine_normal.png, carbine_masks_a.png, carbine_masks_b.png, carbine_id.png, carbine_marks.png,
    carbine_relief.png     the GPU bake's maps at their size, re-compressed losslessly
    carbine_layered.json   the look's tables (eidoblend.props.carbine.look): the substrates by baked ID, the hands'
                           soft boxes, the knocks' and stains' ramps (millimetres in the carbine's Blender axes: +X to
                           the muzzle, +Y its left, +Z up), the CC0 photographs the stack reads and their means as
                           Blender reads them
"""

import json
import os
import shutil
import sys

import bpy

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
MAPS = ('normal', 'masks_a', 'masks_b', 'id', 'marks', 'relief')


def opt(k, d=None):
    return ARGS[ARGS.index(k) + 1] if k in ARGS else d


def main():
    blend, bake, out = (os.path.abspath(opt(k)) for k in ('--blend', '--bake', '--out'))
    sys.path.insert(0, os.path.join(os.path.abspath(opt('--edition', os.getcwd())), 'blender'))
    from eidoblend.materials import layered as LY
    from eidoblend.props.carbine import look as LOOK
    os.makedirs(out, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=blend)
    col = bpy.data.collections['carbine']
    parts = [o for o in col.all_objects if o.type == 'MESH']
    for o in parts:
        for m in o.data.materials:
            if m and 'lens' in m.name:
                m.diffuse_color, m.roughness, m.metallic = (0.35, 0.08, 0.03, 1.0), 0.04, 1.0
            elif m:
                m.diffuse_color, m.roughness, m.metallic = (0.026, 0.03, 0.032, 1.0), 0.46, 0.0
    for o in bpy.context.view_layer.objects:
        o.select_set(o in parts)
    path = os.path.join(out, 'carbine.glb')
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_apply=True,
                              export_texcoords=True, export_normals=True, export_tangents=True,
                              export_materials='VIEWPORT', export_vertex_color='NONE', export_attributes=False,
                              export_extras=False, export_yup=True, export_animations=False, export_cameras=False,
                              export_lights=False, export_image_format='NONE')
    for k in MAPS:                                             # (compress_maps.py then stores them losslessly smaller)
        shutil.copyfile(os.path.join(bake, f'carbine_{k}.png'), os.path.join(out, f'carbine_{k}.png'))
    # the look's tables, and the photographs' means as layered.photos() / mean_of() read them in Blender
    ph = LY.photos()
    means = {}
    for g, (col_im, rgh_im, spec) in enumerate(ph['grain'][:3]):
        means[spec[0]] = {'colour': LY.mean_of(col_im) if col_im is not None else None, 'rough': LY.mean_of(rgh_im)}
    for k in ('fingerprints', 'chips', 'scratches'):
        means[k] = LY.mean_of(ph[k])
    rows = {}
    for i, s in LOOK.SUBSTRATES.items():
        rows[str(i)] = dict(s._asdict())
    data = {
        'about': 'the carbine\'s layered material (eidoblend.props.carbine.look on materials.layered.baked_material)',
        'axes': 'millimetres in the carbine\'s Blender space: +X to the muzzle, +Y its left, +Z up; glTF (x, y, z) is (x, -z, y)',
        'ids': {str(k): v for k, v in LOOK.IDS.items()},
        'substrates': rows,
        'hands': [[list(lo), list(hi), soft] for lo, hi, soft in LOOK.HANDS],
        'knocks': [list(k) for k in LOOK.KNOCKS],
        'stains': [[[list(r) for r in ramps], amount] for ramps, amount in LOOK.STAINS],
        'mark_color': [0.55, 0.55, 0.53], 'dust_color': [0.40, 0.34, 0.25], 'soot_color': [0.012, 0.011, 0.010],
        'lens': {'color': [0.35, 0.08, 0.03], 'roughness': 0.04, 'metalness': 1.0},
        'grain_sets': [list(s) for s in LY.GRAIN_SETS],
        'photos': {k: list(v) for k, v in LY.PHOTOS.items()},
        'blender_means': means,
        'maps': {k: f'carbine_{k}.png' for k in MAPS},
        'size': json.load(open(os.path.join(bake, 'carbine.json'), encoding='utf-8')).get('size'),
    }
    with open(os.path.join(out, 'carbine_layered.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(data, f, indent=1)
    tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in parts)
    print(json.dumps({'glb': path, 'bytes': os.path.getsize(path), 'parts': len(parts), 'triangles': tris, 'means': means}))


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
