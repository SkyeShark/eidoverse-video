"""eidoblend.sets.town.cli: the town built, saved and shot from the command line. Blender:

    bash run_blender.sh blender/eidoblend/sets/town/cli.py --out work/town/town.blend [--extent 840x300] [--seed 7]
        [--damage] [--sky sky|hdri|none] [--hdri FILE] [--trees auto|built|seedthree] [--no-things] [--signs "BAKERY,TAILOR"]
        [--renders DIR] [--only NAME,NAME] [--res 960x540] [--samples 16] [--clay]

It makes the collection 'town' (layout.build: every building, street, CC0 thing, mask and the air), the sun
'town_sun' (outside the collection), the world (the sky family's, baked per view, or the photo sky), the EEVEE
settings (world.eevee); saves the .blend when --out is given (a build output: never commit it); with --renders, every
lens of views.py into DIR as PNG (--clay: each also in clay first, the air hidden). Prints the town's stats.
"""
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..')))
import bpy  # noqa: E402

from eidoblend import common  # noqa: E402
from eidoblend.sets import town as TOWN  # noqa: E402
from eidoblend.sets.town import views as V  # noqa: E402
from eidoblend.sets.town.materials import clay  # noqa: E402


def main():
    a = common.script_args()

    def opt(k, d=None):
        return a[a.index(k) + 1] if k in a else d
    t0 = time.time()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    ex, ey = (float(v) for v in opt('--extent', '840x300').split('x'))
    signs = [s.strip() for s in opt('--signs', '').split(',') if s.strip()] or None
    T = TOWN.build(seed=int(opt('--seed', '7')), extent=(ex, ey), damage='--damage' in a, signs=signs,
                   yard_trees=opt('--trees', 'auto'), things='--no-things' not in a)
    sky_kind = opt('--sky', 'sky')
    sky_kind = None if sky_kind == 'none' else sky_kind
    W, H = (int(v) for v in opt('--res', '960x540').split('x'))
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
    cd = bpy.data.cameras.new('town_lens')
    cd.clip_start, cd.clip_end = 0.3, 4500.0
    cam = bpy.data.objects.new('town_lens', cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    views = T.views()
    V.aim(cam, views[0][1], views[0][2], views[0][3])
    out = opt('--out')
    sky = TOWN.light(sc, cam, sky=sky_kind, cache_dir=os.path.join(os.path.dirname(os.path.abspath(out)), 'town_sky_cache') if out else None,
                     hdri=opt('--hdri'))
    TOWN.eevee(sc, int(opt('--samples', '16')))
    if out:
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(out), compress=True)
        print(f'[town] saved {out}: {os.path.getsize(os.path.abspath(out)) // 1024} KB ({time.time() - t0:.1f} s)', flush=True)
    folder = opt('--renders')
    if folder:
        os.makedirs(folder, exist_ok=True)
        only = opt('--only')
        air = T.parts.get('air')
        sc.render.image_settings.file_format = 'PNG'
        for name, pos, target, lens in views:
            if only and not any(q in name for q in only.split(',')):
                continue
            V.aim(cam, pos, target, lens)
            if sky is not None:
                sky.bake(sc.frame_current, sc.frame_current, log=lambda *m: None)
            for pas in (('clay', 'look') if '--clay' in a else ('look',)):
                bpy.context.view_layer.material_override = clay() if pas == 'clay' else None
                if air is not None:
                    air.hide_render = pas == 'clay'
                sc.render.filepath = os.path.join(os.path.abspath(folder), name + ('_clay' if pas == 'clay' else '') + '.png')
                t1 = time.time()
                bpy.ops.render.render(write_still=True)
                print(f'[town] rendered {name} {pas} in {time.time() - t1:.1f} s', flush=True)
        bpy.context.view_layer.material_override = None
    print(f'[town] stats {T.stats}; done in {time.time() - t0:.1f} s', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
