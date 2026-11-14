"""The facades' fwidth (citykit.pixel_footprint: the windows' box filter, their frames and panes, the far average)
against the truth, at two of the film's dive cameras:

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sets_uf_city/test_window_footprint.py
    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sets_uf_city/test_window_footprint.py --render
    (--render: a GPU job; on a shared machine queue it with EIDO_GPU_WRAP: blender/tests/_where.py)

The truth is what the GPU's fwidth measured on a plane: rays through a pixel and its right and lower neighbours hit the
same facade quad (its UVs, in metres, are affine there), so |du_x| + |du_y| over the cell size is the window grid's
fwidth. Checked against it:
  - the formula pixel_footprint writes as nodes, here in numpy from the same inputs (the camera's axes, the depth, the
    pixel angle, the face's normal and UV tangent): no GPU;
  - --render: the material itself, which writes its footprint and its panes' resolve to the AOV 'uf_window_fw' (the
    kit's aovs option); one 960 x 540 render per camera, read back from an EXR.
At dive t = 40.8 s the near rim tower's windows must resolve their frames and mullions, as in the film's still.
Prints PASS / FAIL.
"""
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402
from eidoblend.common import script_args  # noqa: E402
from eidoblend.sets.unknown_force import citykit as KIT  # noqa: E402
from eidoblend.sets.unknown_force import city as C  # noqa: E402

OUT = HERE / 'out'
OUT.mkdir(exist_ok=True)
args = script_args()
RENDER = '--render' in args
W, H = 960, 540
STEP = 4
results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print('[uf-footprint] %s %s %s' % ('PASS' if ok else 'FAIL', name, detail), flush=True)


for c in (bpy.data.objects, bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras,
          bpy.data.node_groups, bpy.data.images, bpy.data.worlds):
    for x in list(c):
        c.remove(x)
scene = bpy.context.scene
scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = W, H, 100
city = C.build(scene=scene, rain_count=100, aovs=RENDER)
city.parts.apply_atmosphere(scene)
M = dict(city.parts.meshes)
M.update(city.parts.hole.parts.meshes)
cd = bpy.data.cameras.new('fp_cam')
cd.clip_start, cd.clip_end = 0.25, 6000.0
cam = bpy.data.objects.new('fp_cam', cd)
scene.collection.objects.link(cam)
scene.camera = cam

occ = ['uf_towers_concrete', 'uf_towers_metal', 'uf_frames', 'uf_far', 'uf_street', 'uf_blocks', 'uf_hole_concrete',
       'uf_hole_metal', 'uf_hole_frames', 'uf_hole_marble']
facades = ('uf_towers_concrete', 'uf_towers_metal', 'uf_hole_concrete', 'uf_hole_metal')
verts, polys, owner, data = [], [], [], {}
base = 0
for nm in occ:
    me = M[nm].data
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    for p in me.polygons:
        polys.append([base + i for i in p.vertices])
        owner.append((nm, p.index))
    verts.extend(co.tolist())
    base += len(co)
    if nm in facades:
        uv = np.empty(len(me.loops) * 2, np.float32)
        me.uv_layers['UVMap'].data.foreach_get('uv', uv)
        aM = np.empty(len(me.vertices) * 4, np.float32)
        me.attributes['aM'].data.foreach_get('color', aM)
        aW = np.empty(len(me.vertices) * 4, np.float32)
        me.attributes['aW'].data.foreach_get('color', aW)
        data[nm] = (me, co, uv.reshape(-1, 2), aM.reshape(-1, 4), aW.reshape(-1, 4))
tree = BVHTree.FromPolygons(verts, polys)


def uv_affine(nm, pi):
    """The gradients of u and v on a facade quad (world units), its normal, cell sizes, kind and window rect."""
    me, co, uv, aM, aW = data[nm]
    p = me.polygons[pi]
    li, vi = list(p.loop_indices), list(p.vertices)
    P = co[vi[:3]].astype(np.float64)
    Uv = uv[li[:3]].astype(np.float64)
    e1, e2 = P[1] - P[0], P[2] - P[0]
    G = np.array([[e1 @ e1, e1 @ e2], [e1 @ e2, e2 @ e2]])
    out = []
    for k in (0, 1):
        rhs = np.array([Uv[1, k] - Uv[0, k], Uv[2, k] - Uv[0, k]])
        try:
            a, b = np.linalg.solve(G, rhs)
        except np.linalg.LinAlgError:
            return None
        out.append(a * e1 + b * e2)
    n = np.cross(e1, e2)
    n /= np.linalg.norm(n) + 1e-12
    am, aw = aM[vi[0]], aW[vi[0]]
    return out[0], out[1], n, max(am[2], 0.5), max(am[1], 0.5), am[0], aw


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def resolve_of(fu, fv, aw):
    pxW = fu / max(1 - 2 * aw[0], 0.05)
    pxH = fv / max(aw[2] - aw[1], 0.05)
    return 1 - smoothstep(0.035, 0.09, max(pxW, pxH))


def measure(t):
    """Facade samples at dive time t: [(px, py, truth fu, fv, formula fu, fv, resolve truth, formula, distance)]."""
    KIT.apply_cam(cam, C.dive_cam(t))
    bpy.context.view_layer.update()
    pix = 2 * math.tan(cd.angle_y / 2) / H
    mw = cam.matrix_world
    R3 = mw.to_3x3()
    origin = np.array(mw.translation)
    ex, ey, fwd = (np.array(R3 @ Vector(v)) for v in ((1, 0, 0), (0, 1, 0), (0, 0, -1)))
    tr, br, bl, tl = [Vector(v) for v in cd.view_frame(scene=scene)]

    def ray(px, py):
        u, v = (px + 0.5) / W, (py + 0.5) / H
        p = tl.lerp(tr, u).lerp(bl.lerp(br, u), v)
        return (R3 @ p).normalized()
    rows = []
    for py in range(1, H - 1, STEP):
        for px in range(1, W - 1, STEP):
            h0 = tree.ray_cast(Vector(origin), ray(px, py))
            if h0[0] is None or owner[h0[2]][0] not in data:
                continue
            hs = [tree.ray_cast(Vector(origin), ray(px + dx, py + dy)) for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1))]
            if any(h[0] is None or h[2] != h0[2] for h in hs):
                continue
            nm, pi = owner[h0[2]]
            A = uv_affine(nm, pi)
            if A is None:
                continue
            gu, gv, n, cu, cv, kind, aw = A
            if kind > 0.5:
                continue
            p0, p1, p2 = (np.array(h[0], np.float64) for h in (h0, hs[0], hs[1]))
            fu_t = (abs(gu @ (p1 - p0)) + abs(gu @ (p2 - p0))) / cu
            fv_t = (abs(gv @ (p1 - p0)) + abs(gv @ (p2 - p0))) / cv
            # the formula (pixel_steps + pixel_footprint), from the inputs the shader has
            d = p0 - origin
            s = float(d @ fwd)
            w = d / np.linalg.norm(d)
            nw = float(n @ w)
            nw = math.copysign(max(abs(nw), 0.02), nw)
            steps = [s * pix * (e - w * (float(n @ e) / nw)) for e in (ex, ey)]
            T = gu / (np.linalg.norm(gu) + 1e-12)
            B = np.cross(n, T)
            fu_f = (abs(T @ steps[0]) + abs(T @ steps[1])) / cu
            fv_f = (abs(B @ steps[0]) + abs(B @ steps[1])) / cv
            rows.append((px, py, fu_t, fv_t, fu_f, fv_f, resolve_of(fu_t, fv_t, aw), resolve_of(fu_f, fv_f, aw),
                         float(np.linalg.norm(d))))
    return np.array(rows)


def report(tag, a, est_cols, res_col):
    tru = np.maximum(a[:, 2], a[:, 3])
    est = np.maximum(a[:, est_cols[0]], a[:, est_cols[1]])
    ratio = est / np.maximum(tru, 1e-9)
    pr = np.percentile(ratio, [5, 50, 95])
    rt, re_ = (a[:, 6] > 0.5).mean() * 100, (a[:, res_col] > 0.5).mean() * 100
    far_t = (smoothstep(0.25, 0.85, tru) > 0.5).mean() * 100
    far_e = (smoothstep(0.25, 0.85, est) > 0.5).mean() * 100
    print(f'[uf-footprint] {tag}: {len(a)} samples; estimate / truth p5 {pr[0]:.3f} median {pr[1]:.3f} p95 {pr[2]:.3f}; '
          f'panes resolved truth {rt:.1f} %, estimate {re_:.1f} %; far regime truth {far_t:.1f} %, estimate {far_e:.1f} %',
          flush=True)
    return pr, rt, re_, far_t, far_e


TIMES = (16.0, 40.8)
meas = {}
for t in TIMES:
    a = measure(t)
    meas[t] = a
    pr, rt, re_, far_t, far_e = report(f'formula, dive t {t}', a, (4, 5), 7)
    check(f'formula = the truth at dive t {t} (median within 1 %, 90 % of samples within 5 %)',
          abs(pr[1] - 1) < 0.01 and np.mean(np.abs(np.maximum(a[:, 4], a[:, 5]) / np.maximum(np.maximum(a[:, 2], a[:, 3]), 1e-9) - 1) < 0.05) > 0.9,
          f'p5 {pr[0]:.3f} p95 {pr[2]:.3f}')
    check(f'formula: panes resolve where the truth resolves them (t {t})', abs(rt - re_) < 2.0, f'{re_:.1f} vs {rt:.1f} %')
    near = a[:, 8] < 60
    if near.any():
        rn_t, rn_e = (a[near, 6] > 0.5).mean() * 100, (a[near, 7] > 0.5).mean() * 100
        print(f'[uf-footprint] t {t}: within 60 m {near.sum()} samples, panes resolved truth {rn_t:.1f} %, formula {rn_e:.1f} %',
              flush=True)

if RENDER:
    vl = scene.view_layers[0]
    if 'uf_window_fw' not in [x.name for x in vl.aovs]:
        aov = vl.aovs.add()
        aov.name = 'uf_window_fw'
        aov.type = 'COLOR'
    KIT.eevee_settings(scene, samples=1)
    scene.render.filter_size = 0.5
    ctree = bpy.data.node_groups.new('uf_fp_comp', 'CompositorNodeTree')
    scene.compositing_node_group = ctree
    rl = ctree.nodes.new('CompositorNodeRLayers')
    fo = ctree.nodes.new('CompositorNodeOutputFile')
    fo.directory = str(OUT / 'footprint_aov') + '/'
    fo.file_name = 'fw_####_'
    fo.save_as_render = False
    fo.format.media_type = 'IMAGE'
    fo.format.file_format = 'OPEN_EXR'
    fo.format.color_depth = '32'
    fo.file_output_items.new('RGBA', 'fw')
    ctree.links.new(rl.outputs['uf_window_fw'], fo.inputs['fw'])
    scene.render.filepath = str(OUT / 'footprint_aov' / 'beauty_')
    scene.render.image_settings.media_type = 'IMAGE'
    scene.render.image_settings.file_format = 'PNG'
    for i, t in enumerate(TIMES):
        KIT.apply_cam(cam, C.dive_cam(t))
        scene.frame_set(10 + i)
        U = city.parts.uniforms
        U['time'] = t
        bpy.ops.render.render(write_still=False)
        exr = sorted((OUT / 'footprint_aov').glob(f'fw_{10 + i:04d}_*.exr'))
        if not exr:
            check(f'AOV written at t {t}', False, str(list((OUT / 'footprint_aov').glob('*'))))
            continue
        img = bpy.data.images.load(str(exr[0]))
        px = np.empty(W * H * 4, np.float32)
        img.pixels.foreach_get(px)
        bpy.data.images.remove(img)
        px = px.reshape(H, W, 4)[::-1]                 # rows from the top, as the rays above
        a = meas[t]
        sh = px[a[:, 1].astype(int), a[:, 0].astype(int)]
        ok = np.isfinite(sh).all(1) & (sh[:, 0] > 0)
        b = np.concatenate([a[ok], sh[ok, :3]], 1)     # columns 9, 10, 11: the shader's fu, fv, resolve
        pr, rt, re_, far_t, far_e = report(f'shader (AOV), dive t {t}', b, (9, 10), 11)
        check(f'the shader\'s footprint = the truth at dive t {t} (median within 3 %)', abs(pr[1] - 1) < 0.03 and ok.mean() > 0.9,
              f'{ok.mean() * 100:.1f} % of samples on a facade in the AOV, p5 {pr[0]:.3f} p95 {pr[2]:.3f}')
        check(f'the shader: panes resolve where the truth resolves them (t {t})', abs(rt - re_) < 3.0,
              f'{re_:.1f} vs {rt:.1f} %')
fails = [n for n, ok in results if not ok]
print(f'[uf-footprint] {len(results) - len(fails)}/{len(results)} passed' + (f'; FAILED: {fails}' if fails else ''))
