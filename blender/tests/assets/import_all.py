"""import_all.py: does every shared GLB / glTF / VRM / FBX / OBJ asset import into Blender 5.2?

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/assets/import_all.py [-- --only vrms]

Each file imports into a fresh empty file; the sweep records objects, meshes, materials, missing images and any error,
and writes out/import_report.json beside this script. PASS = every asset imported with at least one object and no
missing image. Renders nothing (no GPU slot needed).
"""
import json
import os
import sys
import time
import traceback

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
ASSETS = os.path.join(ROOT, 'eidoverse', 'assets')
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
only = argv[argv.index('--only') + 1] if '--only' in argv else None

try:
    bpy.ops.preferences.addon_enable(module='bl_ext.blender_org.vrm')
    vrm_ok = True
except Exception as e:                                                  # noqa: BLE001
    print('[assets] VRM add-on not available:', e)
    vrm_ok = False

EXT = ('.glb', '.gltf', '.vrm', '.fbx', '.obj')
files = []
for dp, dn, fn in os.walk(ASSETS):
    dn[:] = [d for d in dn if d not in ('cache', 'node_modules') and not d.startswith('.')]
    for f in fn:
        if f.lower().endswith(EXT) and (not only or only in dp.replace('\\', '/')):
            files.append(os.path.join(dp, f))
files.sort()


def import_one(p):
    ext = os.path.splitext(p)[1].lower()
    if ext in ('.glb', '.gltf'):
        return bpy.ops.import_scene.gltf(filepath=p)
    if ext == '.vrm':
        if not vrm_ok:
            raise RuntimeError('VRM add-on missing')
        return bpy.ops.import_scene.vrm(filepath=p)
    if ext == '.fbx':
        return bpy.ops.import_scene.fbx(filepath=p)
    if ext == '.obj':
        return bpy.ops.wm.obj_import(filepath=p)


rows, fails = [], 0
for i, p in enumerate(files):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if vrm_ok:
        try:
            bpy.ops.preferences.addon_enable(module='bl_ext.blender_org.vrm')
        except Exception:                                               # noqa: BLE001
            pass
    rel = os.path.relpath(p, ROOT).replace('\\', '/')
    t0 = time.time()
    row = {'file': rel, 'mb': round(os.path.getsize(p) / 2 ** 20, 2)}
    try:
        res = import_one(p)
        row['result'] = sorted(res) if res else None
        missing = [im.name for im in bpy.data.images if im.source == 'FILE' and not im.packed_file
                   and not os.path.exists(bpy.path.abspath(im.filepath))]
        row.update(objects=len(bpy.data.objects), meshes=len(bpy.data.meshes), materials=len(bpy.data.materials),
                   images=len(bpy.data.images), armatures=len(bpy.data.armatures),
                   actions=len(bpy.data.actions), missing_images=missing)
        row['ok'] = row['objects'] > 0 and not missing and 'FINISHED' in (row['result'] or [])
    except Exception as e:                                              # noqa: BLE001
        row.update(ok=False, error=f'{type(e).__name__}: {e}', trace=traceback.format_exc()[-600:])
    row['sec'] = round(time.time() - t0, 2)
    fails += not row['ok']
    rows.append(row)
    print(f"[assets] {i + 1}/{len(files)} {'ok  ' if row['ok'] else 'FAIL'} {rel} "
          f"({row.get('objects', 0)} obj, {row.get('materials', 0)} mat, {row['sec']} s)"
          + (f" {row.get('error', '')} missing={row.get('missing_images', [])}" if not row['ok'] else ''), flush=True)

os.makedirs(os.path.join(HERE, 'out'), exist_ok=True)
with open(os.path.join(HERE, 'out', 'import_report.json'), 'w', encoding='utf-8') as f:
    json.dump({'files': len(rows), 'failed': fails, 'rows': rows}, f, indent=1)
print(f"[assets] {'PASS' if not fails else 'FAIL'}: {len(rows) - fails} of {len(rows)} assets import")
