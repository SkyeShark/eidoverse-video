"""export_cli.py: a built .blend -> an XR bundle, headless (eidoblend.xr.export.export_xr). Run inside Blender:

    bash run_blender.sh blender/eidoblend/xr/export_cli.py <scene.blend> <out_dir> [options]
    bash run_blender.sh blender/eidoblend/xr/export_cli.py <scene.blend> --survey      # what it would do, nothing written

    --street M          metres per unit when you stand in it (default: the scene's XR settings, else 1.0)
    --table M           metres per unit on the table (default: the settings, else the scene's extent fits 0.6 m)
    --start X,Y         the ground point you start at, Blender axes (default: the settings, else the camera's)
    --facing X,Y        the direction you face there (default: the settings, else where the camera looks, levelled)
    --name N            the bundle's name in the page's title and reports (default: the settings, else the .blend's)
    --shadows           the page casts sun and spot shadows (a desktop cost; off by default)
    --texel-density N   texels a metre for baked materials (default 24); --max-texture N (default 2048)
    --max-image N       scale the film's own image textures down to N px on the long side (default: as they are);
                        the headset uploads textures uncompressed (the manifest's quest grade counts them)
    --no-bake           export materials as the exporter writes them (procedural channels become defaults)
    --no-motion         do not turn instances and deformation into glTF animation (they go out still, at the first
                        frame; keys, constraints, armatures and shape keys still play)
    --no-world          no world.hdr (the page uses the world's flat colour)
    --world-frame F     the frame the world is captured at (default: the first); --world-width W (default 2048)
    --compress meshopt|draco    mesh compression (the page decodes both)
    --images AUTO|JPEG|WEBP     image format inside the GLB (default AUTO: PNG stays PNG, JPEG stays JPEG)
    --choreo a,b,c      objects whose world tracks go into choreo.json (the guide's recipe)
    --survey            print export.survey_xr (objects, what cannot be carried, bakes, motion, animated values)
                        as JSON and stop: the .blend is only read

The .blend is opened, changed to fit glTF (see export.py) and NOT saved. Exit status 1 when the export failed.
"""
import json
import os
import sys
import traceback

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')))

import bpy  # noqa: E402

from eidoblend.common import script_args  # noqa: E402


def opt(a, k, d=None):
    return a[a.index(k) + 1] if k in a else d


def main():
    a = script_args()
    if len(a) < 1 or (len(a) < 2 and '--survey' not in a):
        print(__doc__)
        sys.exit(2)
    blend = os.path.abspath(a[0])
    bpy.ops.wm.open_mainfile(filepath=blend, load_ui=False)
    from eidoblend.xr import export as X
    sc = bpy.context.scene
    if '--survey' in a:
        s = X.survey_xr(sc)
        print('[xr] survey ' + json.dumps(s, default=str))
        return
    out_dir = os.path.abspath(a[1])
    xr = X.get_xr(sc) if sc.get('eido_xr') else {}
    if any(k in a for k in ('--street', '--table', '--start', '--facing', '--name', '--shadows')) or not sc.get('eido_xr'):
        st = opt(a, '--start')
        fa = opt(a, '--facing')
        X.set_xr(sc, street=float(opt(a, '--street', xr.get('street', 1.0))),
                 table=float(opt(a, '--table')) if opt(a, '--table') else xr.get('table'),
                 start=tuple(float(v) for v in st.split(',')) + (0.0,) if st else xr.get('start'),
                 facing=tuple(float(v) for v in fa.split(',')) + (0.0,) if fa else xr.get('facing'),
                 eye_height=xr.get('eye_height', 1.6), name=opt(a, '--name', xr.get('name')),
                 table_centre=xr.get('table_centre'), shadows='--shadows' in a or xr.get('shadows', False),
                 landmarks=False)
    names = [n for n in (opt(a, '--choreo') or '').split(',') if n]
    man = X.export_xr(out_dir, sc, bake_materials='--no-bake' not in a, bake_motion='--no-motion' not in a,
                      world='--no-world' not in a,
                      world_frame=int(opt(a, '--world-frame')) if opt(a, '--world-frame') else None,
                      world_width=int(opt(a, '--world-width', 2048)),
                      texel_density=float(opt(a, '--texel-density', 24)),
                      max_texture=int(opt(a, '--max-texture', 2048)),
                      max_image=int(opt(a, '--max-image')) if opt(a, '--max-image') else None,
                      compress=opt(a, '--compress'),
                      image_format=opt(a, '--images', 'AUTO'), choreo_names=names)
    print(f"[xr] wrote {out_dir}: {man['glb']}, {man['counts']['triangles']} triangles, {man['counts']['draws']} draws, "
          f"Quest {man['quest']}, {len(man['warnings'])} warning(s)")


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except BaseException:
        traceback.print_exc()
        sys.exit(1)
