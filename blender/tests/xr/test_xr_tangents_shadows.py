"""tests/xr/test_xr_tangents_shadows.py: three things a film set does that the other xr tests do not, through the export.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \\
        <worktree>/blender/tests/xr/test_xr_tangents_shadows.py

  1. A mesh with its OWN UV map and a procedural bump (ridges along x, a Wave texture into a Bump node), on a plane whose
     UVs are turned 90 degrees and on a UV sphere: bake_for_gltf bakes the normal onto the 'gltf_bake' UV map. Blender's
     tangent-space bake works in the frame of the mesh's ACTIVE UV map and the exporter's TANGENT attribute too, so the
     bake's map is made the active one: the normal map, the GLB's tangents and the normal texture's texCoord then share
     one frame. Checked in the GLB: the TANGENT attribute against +u on the normal texture's own texCoord, triangle by
     triangle, and the ground's baked normals read back the glTF way (TBN from TANGENT and its w) against the bump's
     own direction (the normal leans down the ridges' slopes, away from their crests).
  2. A sun left at the origin (as eidoblend's robot example and the flora tests make theirs), low from +x, shadows on: a
     pillar's shadow lies across the ground. The page's still through the camera (test_xr_pages.py) must show it where
     EEVEE does: out/tangents_shadows/probe_points.json gives the pixels of a shaded and a lit ground point (same x, so
     the ridges shade them alike).
  3. export_xr(scene=<a scene that is not the context scene>): the GLB holds THAT scene's objects.
EEVEE still and bundle into out/tangents_shadows/ (the page test photographs the bundle).
"""
import json
import math
import os
import sys
import time

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
WORKTREE = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(WORKTREE, 'blender'))
NO_RENDER = '--no-render' in sys.argv
OUT = os.path.join(HERE, 'out', 'tangents_shadows_norender' if NO_RENDER else 'tangents_shadows')
os.makedirs(OUT, exist_ok=True)

from eidoblend.xr import _bl                    # noqa: E402
from eidoblend.xr import export as X            # noqa: E402
from eidoblend.xr import glb as G               # noqa: E402
from eidoblend.xr._bl import Tree               # noqa: E402

RESULTS = []
SUN_ELEV = 25.0


def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok), detail))
    print(f"[check] {'PASS' if ok else 'FAIL'} {name}{': ' + str(detail) if detail else ''}", flush=True)


def plain(name, base, rough=0.6):
    m = _bl.new_material(name)
    T = Tree(m.node_tree)
    b = T.node('ShaderNodeBsdfPrincipled', inputs={'Base Color': tuple(base) + (1,), 'Roughness': rough})
    o = T.node('ShaderNodeOutputMaterial')
    T.link(b.outputs[0], o.inputs['Surface'])
    m.diffuse_color = tuple(base) + (1,)
    return m


def ridged(name):
    """Ridges along x: a Wave texture's bands (object x) into a Bump node; constant colour and roughness."""
    m = _bl.new_material(name)
    T = Tree(m.node_tree)
    tc = T.node('ShaderNodeTexCoord')
    wv = T.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='X', wave_profile='SIN',
                inputs={'Vector': tc.outputs['Object'], 'Scale': 0.5, 'Distortion': 0.0})
    bump = T.node('ShaderNodeBump', inputs={'Height': wv.outputs['Fac'], 'Strength': 1.0, 'Distance': 0.08})
    b = T.node('ShaderNodeBsdfPrincipled', inputs={'Base Color': (0.55, 0.5, 0.45, 1), 'Roughness': 0.6})
    T.link(bump.outputs['Normal'], b.inputs['Normal'])
    o = T.node('ShaderNodeOutputMaterial')
    T.link(b.outputs[0], o.inputs['Surface'])
    m.diffuse_color = (0.55, 0.5, 0.45, 1)
    return m


# ------------------------------------------------------------------------------------------------- the set ---
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
sc = bpy.context.scene
sc.name = 'tangents_shadows'
sc.render.fps, sc.render.fps_base = 24, 1.0
sc.frame_start, sc.frame_end = 1, 25
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 960, 540, 100
sc.render.engine = 'BLENDER_EEVEE'
sc.view_settings.view_transform = 'AgX'
sc.view_settings.look = 'None'
sc.eevee.taa_render_samples = 16
sc.eevee.use_shadows = True
w = bpy.data.worlds.new('probe_dim_sky')
w.use_nodes = True
T = Tree(w.node_tree)
bg = T.node('ShaderNodeBackground', inputs={'Color': (0.05, 0.065, 0.09, 1), 'Strength': 1.0})
T.link(bg.outputs[0], T.node('ShaderNodeOutputWorld').inputs['Surface'])
sc.world = w
col = sc.collection
mat = ridged('ridged_ground')

bpy.ops.mesh.primitive_plane_add(size=10.0, location=(0, 0, 0))
ground = bpy.context.object
ground.name = 'ground'
uv = ground.data.uv_layers.active
for d in uv.data:                                   # its own UVs, turned 90 degrees: +u runs along -y, +v along +x
    u, v = d.uv
    d.uv = (1.0 - v, u)
ground.data.materials.append(mat)
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.7, location=(-2.2, -1.6, 0.7), segments=48, ring_count=24)
ball = bpy.context.object
ball.name = 'ridged_ball'
bpy.ops.object.shade_smooth()
ball.data.materials.append(mat)
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.8, 1.0, 1.25))
pillar = bpy.context.object
pillar.name = 'pillar'
pillar.scale = (0.4, 0.4, 2.5)
pillar.data.materials.append(plain('pillar_grey', (0.6, 0.6, 0.62)))
bpy.ops.mesh.primitive_cube_add(size=0.6, location=(1.8, -1.5, 0.3))
box = bpy.context.object
box.name = 'box'
box.data.materials.append(plain('box_red', (0.6, 0.1, 0.07), 0.4))
bpy.ops.object.select_all(action='DESELECT')

toward = Vector((math.cos(math.radians(SUN_ELEV)), 0.0, math.sin(math.radians(SUN_ELEV))))
ld = bpy.data.lights.new('sun_at_origin', 'SUN')
ld.energy, ld.angle, ld.use_shadow = 4.0, math.radians(1.0), True
sun = bpy.data.objects.new('sun_at_origin', ld)
col.objects.link(sun)
sun.location = (0.0, 0.0, 0.0)                      # left at the origin, as eidoblend's robot example and flora tests do
sun.rotation_euler = (-toward).to_track_quat('-Z', 'Y').to_euler()

cd = bpy.data.cameras.new('cam_probe')
cd.lens = 30.0
cd.clip_start, cd.clip_end = 0.05, 200.0
cam = bpy.data.objects.new('cam_probe', cd)
col.objects.link(cam)
cam.location = (0.0, -8.5, 3.2)
cam.rotation_euler = _bl.look_at_rotation(cam.location, (0.0, 0.0, 0.4))
sc.camera = cam
X.set_xr(sc, street=1.0, start=(0.0, -6.0, 0.0), facing=(0.0, 1.0, 0.0), name='tangents_shadows', shadows=True,
         landmarks=False)

# the probe points: shaded by the pillar (its shadow runs toward -x) and lit, at the same x (the ridges shade both alike)
bpy.context.view_layer.update()
SHADED, LIT = Vector((-1.2, 1.0, 0.0)), Vector((-1.2, -0.6, 0.0))
hit = SHADED + toward * (0.93 / toward.z)           # the sun ray from SHADED, 0.93 m up: inside the pillar
check('the probe point lies in the pillar\'s shadow (the sun ray from it meets the pillar)',
      abs(hit.x - 0.8) < 0.21 and abs(hit.y - 1.0) < 0.21 and 0 < hit.z < 2.5, tuple(round(x, 3) for x in hit))
px = {}
for name, p in (('shaded', SHADED), ('lit', LIT)):
    v = world_to_camera_view(sc, cam, p)
    px[name] = [v.x * sc.render.resolution_x, (1.0 - v.y) * sc.render.resolution_y]
with open(os.path.join(OUT, 'probe_points.json'), 'w') as f:
    json.dump({'pixels': px, 'size': [sc.render.resolution_x, sc.render.resolution_y], 'camera': cam.name}, f, indent=1)

# ------------------------------------------------------------------------------------------------- EEVEE ---
if not NO_RENDER:
    p = os.path.join(OUT, 'eevee_cam_probe_t0.png')
    sc.render.image_settings.media_type = 'IMAGE'
    sc.render.image_settings.file_format = 'PNG'
    sc.render.use_file_extension = False
    sc.render.filepath = p
    sc.frame_set(1)
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    check('EEVEE still through cam_probe', os.path.exists(p), f'{time.time() - t0:.1f} s')
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'tangents_shadows.blend'), check_existing=False)

# ------------------------------------------------------------------- 3. a scene that is not the context scene ---
sc2 = bpy.data.scenes.new('second_scene')
sc2.render.fps, sc2.frame_start, sc2.frame_end = 24, 1, 25
me = bpy.data.meshes.new('only_in_second')
me.from_pydata([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], [], [(0, 1, 2, 3)])
sc2.collection.objects.link(bpy.data.objects.new('only_in_second', me))
man2 = X.export_xr(os.path.join(OUT, 'vr_second_scene'), sc2, bake_materials=False, world=False)
g2 = G.read(os.path.join(OUT, 'vr_second_scene', 'scene.glb'))
names2 = {n.get('name') for n in g2.json.get('nodes', [])}
check("export_xr(scene=a scene that is not the context scene) exports THAT scene's objects",
      'only_in_second' in names2 and 'pillar' not in names2 and bpy.context.scene == sc, sorted(names2)[:8])
check('... and leaves the context scene as it was', bpy.context.scene.name == 'tangents_shadows'
      and not sc.objects['pillar'].hide_render)
bpy.data.scenes.remove(sc2)

# ------------------------------------------------------------------------------------------------ the export ---
vr = os.path.join(OUT, 'vr')
man = X.export_xr(vr, sc, name='scene', world_width=512, bake_materials=not NO_RENDER, world=not NO_RENDER)
g = G.read(os.path.join(vr, 'scene.glb'))
js = g.json
if not NO_RENDER:
    for node_name in ('ground', 'ridged_ball'):
        n = js['nodes'][g.node_by_name(node_name)]
        prim = js['meshes'][n['mesh']]['primitives'][0]
        mt = js['materials'][prim['material']]
        nt = mt.get('normalTexture')
        att = prim['attributes']
        if nt is None or 'TANGENT' not in att:
            check(f'{node_name}: a baked normal map and tangents in the GLB', False, (nt, sorted(att)))
            continue
        k_nt = nt.get('texCoord', 0)
        P, TG = g.accessor(att['POSITION']), g.accessor(att['TANGENT'])
        idx = g.accessor(prim['indices']) if 'indices' in prim else list(range(len(P)))

        def plus_u(UV, a, b, c):
            """The surface direction of +u on a triangle (dP/du, in its plane), or None when degenerate."""
            e1, e2 = Vector(P[b]) - Vector(P[a]), Vector(P[c]) - Vector(P[a])
            du1, dv1 = UV[b][0] - UV[a][0], UV[b][1] - UV[a][1]
            du2, dv2 = UV[c][0] - UV[a][0], UV[c][1] - UV[a][1]
            det = du1 * dv2 - du2 * dv1
            nrm = e1.cross(e2)
            if abs(det) < 1e-12 or nrm.length < 1e-12:
                return None
            tu = (e1 * dv2 - e2 * dv1) / det          # (glTF's flipped v changes both signs: the same +u)
            tu = tu - nrm.normalized() * tu.dot(nrm.normalized())
            return tu.normalized() if tu.length > 1e-9 else None

        UVb = g.accessor(att[f'TEXCOORD_{k_nt}'])
        UV0 = g.accessor(att['TEXCOORD_0']) if k_nt != 0 and 'TEXCOORD_0' in att else None
        worst, n_, apart = 0.0, 0, []
        for t in range(0, len(idx) // 3, max(1, len(idx) // 3 // 400)):
            a, b, c = idx[3 * t: 3 * t + 3]
            tu = plus_u(UVb, a, b, c)
            if tu is None:
                continue
            worst = max(worst, math.degrees(Vector(TG[a][:3]).angle(tu)))
            n_ += 1
            if UV0 is not None:                       # the mesh's own map: where tangents on IT would have pointed
                t0_ = plus_u(UV0, a, b, c)
                if t0_ is not None:
                    apart.append(math.degrees(t0_.angle(tu)))
        apart.sort()
        check(f"{node_name}: the GLB's tangents follow the baked normal map's own UV map (TEXCOORD_{k_nt})",
              n_ > 0 and worst < 10.0, f'{n_} triangles, worst {worst:.1f} deg between TANGENT and +u'
              + (f'; the mesh\'s own UV map lies {apart[len(apart) // 2]:.0f} deg off (median)' if apart else ''))
        if node_name != 'ground':
            continue
        # the ground's normal map read the glTF way: n = T x + B y + N z, B = cross(N, T) w, texel row from the top at
        # v; Blender's bump of h = 0.5 - 0.5 cos(10 x) leans the normal along -dh/dx = -5 sin(10 x)
        src = bpy.data.images.load(os.path.join(vr, 'textures', 'ground_normal.png'), check_existing=False)
        iw, ih = src.size
        import numpy as np                                                  # noqa: E402
        px = np.empty(iw * ih * 4, np.float32)
        src.pixels.foreach_get(px)
        px = px.reshape(ih, iw, 4)                                          # Blender's rows: from the bottom
        bpy.data.images.remove(src)
        A3 = np.array([[P[i][0], P[i][2], 1.0] for i in idx[:3]])
        Muv = np.linalg.solve(A3, np.array([UVb[i] for i in idx[:3]]))     # glTF (x, z, 1) -> (u, v), a flat quad
        Tg, wg, Ng = Vector(TG[idx[0]][:3]), TG[idx[0]][3], Vector(g.accessor(att['NORMAL'])[idx[0]])
        Bg = Ng.cross(Tg) * wg
        agree = tot = 0
        for xb in [-3.0 + 0.1 * i for i in range(61)]:
            u, v = np.array([xb, -0.3, 1.0]) @ Muv                          # Blender (x, 0.3, 0): glTF (x, 0, -0.3)
            row = min(ih - 1, max(0, int(v * ih)))
            nm = px[ih - 1 - row, min(iw - 1, max(0, int(u * iw))), :3] * 2 - 1
            ng = Tg * float(nm[0]) + Bg * float(nm[1]) + Ng * float(nm[2])
            want = -5 * math.sin(10 * xb)
            if abs(want) > 2.0 and abs(ng.x) > 0.02:                        # (glTF x is Blender x)
                tot += 1
                agree += (ng.x > 0) == (want > 0)
        check("ground: its baked normal map, read the glTF way (the GLB's TANGENT and w), leans the normal down the "
              "ridges' slopes as Blender's bump does", tot > 20 and agree >= 0.9 * tot, f'{agree} of {tot} points agree')
    baked = man['report']['materials'].get('baked', {})
    check('the ridged material was baked (a normal map) for the plane and the ball', {'ground', 'ridged_ball'} <= set(baked)
          and all('normal' in baked[k]['images'] for k in ('ground', 'ridged_ball')), sorted(baked))
lights = {li['name']: li for li in man['summary']['lights']}
check('the sun at the origin is in the GLB (a directional light)', lights.get('sun_at_origin', {}).get('type') == 'directional',
      lights.get('sun_at_origin'))
with open(os.path.join(OUT, 'export_report.json'), 'w') as f:
    json.dump(man, f, indent=1, default=str)
n_fail = sum(1 for _, ok, _ in RESULTS if not ok)
print(f'[check] {len(RESULTS) - n_fail} passed, {n_fail} failed', flush=True)
sys.exit(1 if n_fail else 0)
