"""blender_gpu_check.py: does Blender in this container render EEVEE on the GPU?

    xvfb-run -a blender -b --factory-startup --python docker/blender_gpu_check.py -- [out.png]

Prints the OpenGL vendor/renderer Blender got and times one EEVEE frame. The fallback to software is silent
(Mesa llvmpipe renders the same picture 30-60x slower), so the renderer string and the frame time are the check:
a 'D3D12 (NVIDIA ...)' or 'NVIDIA' renderer and a sub-second 960x540 frame mean the GPU path works; 'llvmpipe'
means the container is missing /dev/dxg, the WSL libraries or GALLIUM_DRIVER=d3d12. Exit code 0 = GPU, 2 = software.
"""
import sys
import time

import bpy
import gpu

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
out = argv[0] if argv else '/tmp/blender_gpu_check.png'

if bpy.app.background:
    gpu.init()  # headless Blender 5.2 creates its GPU context on demand; queries need it first
vendor, renderer, version = gpu.platform.vendor_get(), gpu.platform.renderer_get(), gpu.platform.version_get()
backend = gpu.platform.backend_type_get()
print(f'[gpu] backend {backend} | vendor {vendor} | renderer {renderer} | version {version}')
software = any(s in renderer.lower() for s in ('llvmpipe', 'softpipe', 'swrast'))

sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 960, 540, 100
sc.eevee.taa_render_samples = 16
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob)
bpy.ops.mesh.primitive_plane_add(size=20)
bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=(0, 0, 1), segments=64, ring_count=32)
bpy.ops.object.shade_smooth()
mat = bpy.data.materials.new('chrome')
mat.use_nodes = True
bsdf = mat.node_tree.nodes['Principled BSDF']
bsdf.inputs['Metallic'].default_value = 1.0
bsdf.inputs['Roughness'].default_value = 0.15
bpy.context.object.data.materials.append(mat)
bpy.ops.object.light_add(type='SUN', rotation=(0.7, 0.2, 0.6))
bpy.context.object.data.energy = 4.0
bpy.ops.object.camera_add(location=(5, -5, 3), rotation=(1.2, 0, 0.785))
sc.camera = bpy.context.object
world = bpy.data.worlds.new('w')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.4, 0.55, 0.8, 1)
sc.world = world
sc.render.filepath = out
sc.render.image_settings.file_format = 'PNG'

times = []
for i in range(2):  # the first frame compiles shaders; the second is the real cost
    t0 = time.time()
    bpy.ops.render.render(write_still=(i == 1))
    times.append(time.time() - t0)
print(f'[gpu] EEVEE 960x540 x16 samples: first {times[0]:.2f} s (shader compile), second {times[1]:.2f} s -> {out}')
print('[gpu] RESULT', 'SOFTWARE (llvmpipe): check /dev/dxg, /usr/lib/wsl and GALLIUM_DRIVER=d3d12' if software else 'GPU')
sys.exit(2 if software else 0)
