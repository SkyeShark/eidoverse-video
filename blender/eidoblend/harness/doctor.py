"""doctor.py: the in-Blender half of `eido_blender.py doctor`. Renders one 64 x 64 EEVEE frame at 1 sample (a lit
cube, so the GPU path really runs), times it, then runs the port of the engine's gpu_check.mjs (harness.gpu_check):
the GPU Blender chose, classified hardware / software / unknown (a software fallback warns: everything runs on the
CPU), and a compute dispatch whose readback must hold exactly i * 3 + 7. Exit 1 if the frame is not written or the
readback is wrong.

    bash run_blender.sh blender/eidoblend/harness/doctor.py <out.png>
"""
import os
import sys
import time

sys.dont_write_bytecode = True
import bpy  # noqa: E402

out = sys.argv[sys.argv.index('--') + 1] if '--' in sys.argv else os.path.join(os.environ.get('TMP', '.'), 'eido_doctor.png')
print(f'[doctor] blender {bpy.app.version_string}', flush=True)
prefs = bpy.context.preferences
print(f"[doctor] gpu backend {getattr(prefs.system, 'gpu_backend', '?')}, preferred device "
      f"{getattr(prefs.system, 'gpu_preferred_device', '?') or 'auto'}", flush=True)
try:
    import addon_utils
    vrm = any(m.__name__.endswith('.vrm') for m in addon_utils.modules())
except Exception:                                                     # noqa: BLE001
    vrm = False
print(f"[doctor] VRM extension {'available in the sandbox' if vrm else 'NOT available'}", flush=True)
bpy.ops.wm.read_homefile(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'
sc.render.resolution_x = sc.render.resolution_y = 64
sc.eevee.taa_render_samples = 1
bpy.ops.mesh.primitive_cube_add(size=1)
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
sc.collection.objects.link(cam)
cam.location = (3, -3, 2.4)
cam.rotation_euler = (1.1, 0, 0.785)
sc.camera = cam
light = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
sc.collection.objects.link(light)
light.rotation_euler = (0.6, 0.2, 0.4)
sc.render.image_settings.media_type = 'IMAGE'
sc.render.image_settings.file_format = 'PNG'
sc.render.filepath = out
t = time.perf_counter()
bpy.ops.render.render(write_still=True)
dt = time.perf_counter() - t
ok = os.path.exists(out) and os.path.getsize(out) > 0
print(f"[doctor] EEVEE 64x64 frame: {dt:.2f} s ({'written' if ok else 'NOT written'}: {out})", flush=True)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
try:
    from eidoblend.harness import gpu_check
    g = gpu_check.check_gpu(warn=lambda m: print(m, flush=True))
    print(f"[doctor] GPU {g['description']} ({g['vendor']}, {g['architecture']}): {g['backend']}, compute readback "
          f"{g['compute_readback']}", flush=True)
except RuntimeError as e:
    print(f'[doctor] {e}', flush=True)
    ok = False
except Exception as e:                                                # noqa: BLE001 - the check could not run
    print(f'[doctor] GPU check SKIPPED ({type(e).__name__}: {e})', flush=True)
sys.exit(0 if ok else 1)
