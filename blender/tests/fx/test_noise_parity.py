"""Parity of the fx family's noise ports, and the GPU path's plumbing. Headless, no render (a few ms of GPU).

    bash run_blender.sh blender/tests/fx/test_noise_parity.py

Checks
  1. GLSL eido_snoise / eido_snoise_vec3 (compute) == numpy _noise.snoise / snoise_vec3      (|d| < 2e-5)
  2. GLSL eido_mx_noise (compute) == numpy _noise.mx_perlin_noise_float                      (|d| < 2e-5)
  3. Blender's Noise Texture (detail 0, normalized, in Geometry Nodes) == 0.5*mx_noise(p)+0.5  (|d| < 2e-5)
     -- the claim the fire's lava and flicker shaders rest on
  4. GPU plumbing: 3D texture read layout, a numpy upload, linear filtering, mat4 push constants
  5. ImprovedNoise against three's JS (a few values, dumped once from three/addons/math/ImprovedNoise.js)
Exit code 0 = all pass.
"""

import os
import sys

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
sys.path.insert(0, os.path.dirname(HERE))
import _where                                                      # noqa: E402
from eidoblend.fx import _noise                                    # noqa: E402
from eidoblend.fx._gpu import ComputeContext, GLSL_SNOISE, GLSL_MX_NOISE   # noqa: E402

fails = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + ('  ' + detail if detail else ''))
    if not ok:
        fails.append(name)


rng = np.random.default_rng(7)
N = 4096
pts = np.concatenate([rng.uniform(-40, 40, (N - 64, 3)), rng.integers(-5, 5, (64, 3)).astype(np.float64)])

ctx = ComputeContext()
side = 64
rows = N // side
up = np.zeros((rows, side, 4), dtype=np.float32)
up.reshape(-1, 4)[:, :3] = pts
ptex = ctx.texture2d_from(up)
out = ctx.gpu.types.GPUTexture((side, rows), format='RGBA32F')
src = r"""
void main() {
  ivec2 c = ivec2(gl_GlobalInvocationID.xy);
  if (c.x >= %d || c.y >= %d) return;
  vec3 p = texelFetch(pts, c, 0).xyz;
  vec3 v = eido_snoise_vec3(p * 0.37);
  imageStore(outImg, c, vec4(eido_snoise(p), eido_mx_noise(p), v.x, v.y));
}
""" % (side, rows)
k = ctx.kernel(src, samplers=['pts'], images=['outImg'], sampler_types={'pts': 'FLOAT_2D'},
               image_type='FLOAT_2D', image_format='RGBA32F', local=(8, 8, 1), preamble=GLSL_SNOISE + GLSL_MX_NOISE)
k.run((side // 8, rows // 8, 1), samplers={'pts': ptex}, images={'outImg': out})
res = ctx.read(out).reshape(-1, 4)
ref_s = _noise.snoise(pts)
ref_m = _noise.mx_perlin_noise_float(pts)
ref_v = _noise.snoise_vec3(pts * 0.37)
# The TSL simplex (radius^2 0.6, as Ashima's) is not continuous across its simplex boundaries, so a sample
# sitting on a boundary (the integer lattice points here, by construction) may pick the other simplex under a
# different float rounding or FMA contraction. Those few jump; everything else must agree to float precision.
e1 = np.abs(res[:, 0] - ref_s)
e3 = np.abs(res[:, 2:4] - ref_v[:, :2]).max(axis=1)
d2 = np.abs(res[:, 1] - ref_m).max()
rand = slice(0, N - 64)
check('GLSL snoise == numpy snoise (random points)', (e1[rand] > 5e-5).mean() < 0.002,
      f'{int((e1[rand] > 5e-5).sum())}/{N - 64} differ; median |d| {np.median(e1):.1e}; '
      f'lattice points differing {int((e1[N - 64:] > 5e-5).sum())}/64')
check('GLSL mx_noise == numpy mx_noise', d2 < 2e-5, f'max |d| {d2:.2e}, range [{ref_m.min():.3f}, {ref_m.max():.3f}]')
check('GLSL snoise_vec3 == numpy snoise_vec3 (random points)', (e3[rand] > 5e-5).mean() < 0.002,
      f'{int((e3[rand] > 5e-5).sum())}/{N - 64} differ')

# ---- 3. Blender's Noise Texture vs MaterialX noise, evaluated in Geometry Nodes on a point cloud ---------
me = bpy.data.meshes.new('pts')
me.vertices.add(N)
me.vertices.foreach_set('co', pts.astype(np.float32).ravel())
ob = bpy.data.objects.new('pts', me)
bpy.context.scene.collection.objects.link(ob)
ng = bpy.data.node_groups.new('noise_probe', 'GeometryNodeTree')
ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
gi = ng.nodes.new('NodeGroupInput')
go = ng.nodes.new('NodeGroupOutput')
pos = ng.nodes.new('GeometryNodeInputPosition')
nz = ng.nodes.new('ShaderNodeTexNoise')
nz.noise_dimensions = '3D'
nz.normalize = True
if hasattr(nz, 'noise_type'):
    nz.noise_type = 'FBM'
nz.inputs['Scale'].default_value = 1.0
nz.inputs['Detail'].default_value = 0.0
nz.inputs['Distortion'].default_value = 0.0
st = ng.nodes.new('GeometryNodeStoreNamedAttribute')
st.data_type = 'FLOAT'
st.domain = 'POINT'
st.inputs['Name'].default_value = 'n'
ng.links.new(pos.outputs[0], nz.inputs['Vector'])
ng.links.new(gi.outputs[0], st.inputs['Geometry'])
ng.links.new(nz.outputs['Fac'], st.inputs['Value'])
ng.links.new(st.outputs[0], go.inputs[0])
mod = ob.modifiers.new('probe', 'NODES')
mod.node_group = ng
dg = bpy.context.evaluated_depsgraph_get()
ev = ob.evaluated_get(dg)
vals = np.empty(N, dtype=np.float32)
ev.data.attributes['n'].data.foreach_get('value', vals)
pf = pts.astype(np.float32).astype(np.float64)
ref = 0.5 * _noise.mx_perlin_noise_float(pf) + 0.5
d4 = np.abs(vals - ref).max()
check("Blender Noise Texture == 0.5*mx_noise+0.5", d4 < 2e-5, f'max |d| {d4:.2e}')

# ---- 3b. the node-graph port of snoise (the fire material's detail noise), built as a GN group ---------
from eidoblend.fx import _nodes                                     # noqa: E402
_nodes.snoise_group('GeometryNodeTree', 'eido.snoise.gn')
ng2 = bpy.data.node_groups.new('snoise_probe', 'GeometryNodeTree')
ng2.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
ng2.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
gi2 = ng2.nodes.new('NodeGroupInput')
go2 = ng2.nodes.new('NodeGroupOutput')
pos2 = ng2.nodes.new('GeometryNodeInputPosition')
grp = ng2.nodes.new('GeometryNodeGroup')
grp.node_tree = bpy.data.node_groups['eido.snoise.gn']
st2 = ng2.nodes.new('GeometryNodeStoreNamedAttribute')
st2.data_type = 'FLOAT'
st2.domain = 'POINT'
st2.inputs['Name'].default_value = 's'
ng2.links.new(pos2.outputs[0], grp.inputs['Vector'])
ng2.links.new(gi2.outputs[0], st2.inputs['Geometry'])
ng2.links.new(grp.outputs['Value'], st2.inputs['Value'])
ng2.links.new(st2.outputs[0], go2.inputs[0])
mod.node_group = ng2
dg = bpy.context.evaluated_depsgraph_get()
ev = ob.evaluated_get(dg)
sv = np.empty(N, dtype=np.float32)
ev.data.attributes['s'].data.foreach_get('value', sv)
es = np.abs(sv - _noise.snoise(pf))
check('snoise node group == numpy snoise (random points)', (es[rand] > 5e-5).mean() < 0.002,
      f'{int((es[rand] > 5e-5).sum())}/{N - 64} differ; median |d| {np.median(es):.1e}; '
      f'{len(bpy.data.node_groups["eido.snoise.gn"].nodes)} nodes')

# ---- 4. plumbing -------------------------------------------------------------------------------------
t3 = ctx.texture3d((5, 3, 2), fmt='RGBA32F', filt=False)
k3 = ctx.kernel("""
void main() { ivec3 c = ivec3(gl_GlobalInvocationID); if (c.x >= 5 || c.y >= 3 || c.z >= 2) return;
  imageStore(o, c, vec4(c, 1.0)); }""", images=['o'], image_format='RGBA32F', local=(1, 1, 1))
k3.run((5, 3, 2), images={'o': t3})
a = ctx.read(t3)
ok = a.shape[:3] == (2, 3, 5) and np.allclose(a[1, 2, 4, :3], (4, 2, 1))
check('3D texture reads back as [z][y][x][c]', ok, f'shape {a.shape}')
# linear filtering: sample half-way between texels 0 and 1 along x
lin = ctx.texture3d((4, 1, 1), fmt='RGBA16F')
kw = ctx.kernel("""
void main() { ivec3 c = ivec3(gl_GlobalInvocationID); if (c.x >= 4) return; imageStore(o, c, vec4(float(c.x) * 10.0)); }""",
                images=['o'], local=(1, 1, 1))
kw.run((4, 1, 1), images={'o': lin})
one = ctx.gpu.types.GPUTexture((1, 1), format='RGBA32F')
ks = ctx.kernel("""
void main() { imageStore(o, ivec2(0), vec4(textureLod(s, vec3(1.0 / 4.0, 0.5, 0.5), 0.0).x,
                                          textureLod(s, vec3(-0.3, 0.5, 0.5), 0.0).x, 0.0, 0.0)); }""",
                samplers=['s'], images=['o'], image_type='FLOAT_2D', image_format='RGBA32F', local=(1, 1, 1))
ks.run((1, 1, 1), samplers={'s': lin}, images={'o': one})
v = ctx.read(one).ravel()
check('sampler3D filters linearly and clamps to edge', abs(v[0] - 5.0) < 0.05 and abs(v[1]) < 1e-4,
      f'mid {v[0]:.3f} (want 5), below-edge {v[1]:.3f} (want 0)')
km = ctx.kernel("""
void main() { vec4 p = M * vec4(1.0, 2.0, 3.0, 1.0); imageStore(o, ivec2(0), p); }""",
                images=['o'], image_type='FLOAT_2D', image_format='RGBA32F', push=[('MAT4', 'M')], local=(1, 1, 1))
Mx = np.array([[0, -1, 0, 10], [1, 0, 0, 20], [0, 0, 2, 30], [0, 0, 0, 1]], dtype=np.float64)
km.run((1, 1, 1), images={'o': one}, M=Mx)
v = ctx.read(one).ravel()
want = Mx @ np.array([1, 2, 3, 1.0])
check('MAT4 push constant (row-major numpy in, M * v in GLSL)', np.allclose(v, want), f'got {v}, want {want}')

# ---- 5. ImprovedNoise against three (values from three/addons/math/ImprovedNoise.js under Node) -----
IN = _noise.ImprovedNoise()
js = {(0.3, 1.7, 2.9): None}
try:
    import subprocess, json, shutil
    node = shutil.which('node')
    three = None
    for root in (os.path.normpath(os.path.join(HERE, '..', '..', '..')), str(_where.main_checkout())):
        p = os.path.join(root, 'node_modules', 'three', 'examples', 'jsm', 'math', 'ImprovedNoise.js')
        if os.path.exists(p):
            three = p
            break
    if node and three:
        pts5 = [(0.3, 1.7, 2.9), (-4.2, 0.01, 7.5), (12.25, -3.5, 0.0), (0, 10.0, 0), (5.5 * 3.5, 0, 0)]
        url = 'file:///' + three.replace('\\', '/')
        code = ("import {ImprovedNoise} from '%s'; const n = new ImprovedNoise(); console.log(JSON.stringify(%s.map(p => n.noise(...p))));"
                % (url, json.dumps(pts5)))
        r = subprocess.run([node, '--input-type=module', '-e', code], capture_output=True, text=True, timeout=60)
        jv = json.loads(r.stdout.strip())
        pv = [IN.noise(*p) for p in pts5]
        d5 = max(abs(a - b) for a, b in zip(jv, pv))
        check('ImprovedNoise == three ImprovedNoise.js', d5 < 1e-12, f'max |d| {d5:.1e}')
    else:
        print('SKIP ImprovedNoise vs three (node or three not found)')
except Exception as e:  # noqa: BLE001
    check('ImprovedNoise vs three ran', False, repr(e))

print('PARITY', 'OK' if not fails else 'FAILED: ' + ', '.join(fails))
# free every GPU texture and shader before Blender tears its GPU backend down: one still alive when sys.exit
# unwinds is destroyed after the backend and crashes Blender (EXCEPTION_ACCESS_VIOLATION, exit code 11)
import gc                                                           # noqa: E402
for _name in [n for n, v in list(globals().items())
              if type(v).__module__.startswith('gpu') or n in ('k', 'k3', 'kw', 'ks', 'km', 'ptex', 'out', 't3', 'lin', 'one')]:
    del globals()[_name]
gc.collect()
sys.stdout.flush()
sys.exit(1 if fails else 0)
