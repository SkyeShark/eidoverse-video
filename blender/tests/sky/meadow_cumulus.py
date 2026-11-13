"""First-priority probe: cumulus late afternoon on Earth, a camera standing in a meadow looking up.

Builds a small meadow (ground + blade cards from our own eidoverse/assets/grass atlas), lighting
references (white, grey and chrome spheres, a wooden crate when the shared texture cache has one),
calls make_sky, bakes, and renders EEVEE stills into blender/tests/sky/out/:
    meadow_<name>_up.png      looking up into the cumulus
    meadow_<name>_level.png   level view: the scene lit by the sun lamp + the sky's ambient + cloud shadows
plus <name>_shadow.png (the cloud-shadow transmittance map) and the sky layers under out/<name>_cache/.

    bash run_blender.sh blender/tests/sky/meadow_cumulus.py [--name N] [--hours 16.5] [--clouds cumulus]
        [--weather fair] [--views up,level] [--samples 16] [--res 960x540] [--quality film|draft]
        [--ambient 0.4] [--exposure 0] [--frames 1] [--step 1]
"""
import argparse
import math
import os
import sys
import time

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'blender'))
from eidoblend.sky import make_sky  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument('--name', default='cumulus_1630')
ap.add_argument('--hours', type=float, default=16.5)
ap.add_argument('--clouds', default='cumulus')
ap.add_argument('--weather', default=None)
ap.add_argument('--views', default='up,level')
ap.add_argument('--samples', type=int, default=16)
ap.add_argument('--res', default='960x540')
ap.add_argument('--quality', default='film')
ap.add_argument('--ambient', type=float, default=None)
ap.add_argument('--exposure', type=float, default=0.6,
                help="AgX sits ~0.7 EV under three's ACES (which divides by 0.6) in the upper mids")
ap.add_argument('--frames', type=int, default=1)
ap.add_argument('--step', type=int, default=1, help='render every Nth frame of the baked range')
ap.add_argument('--no-shadows', action='store_true')
ap.add_argument('--yaw', type=float, default=None, help='camera heading in degrees from +Y (default: sun-relative)')
ap.add_argument('--transition', default=None, help='name:seconds:at  (weather transition during the range)')
ap.add_argument('--fps', type=int, default=24)
ap.add_argument('--spot', default='auto', help="'auto' = nearest sunlit point, or 'x,y' metres, or '' for the origin")
ap.add_argument('--fog', type=float, default=0.0004, help='FogExp2 density (0 = off)')
ap.add_argument('--shafts', type=float, default=None, help='below-cloud light shafts strength (WebGPU shafts=)')
ap.add_argument('--shadow-height', type=float, default=None, help='caster metres up (default: under the cloud base)')
args = ap.parse_args(argv)

OUT = os.path.join(HERE, 'out')
CACHE_TEX = os.path.normpath(os.path.join(REPO, '..', 'eidoverse-video-prealpha-0.01', 'eidoverse', 'assets',
                                          'cache'))
GRASS = os.path.join(REPO, 'eidoverse', 'assets', 'grass')

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
W, H = (int(v) for v in args.res.split('x'))
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
sc.render.engine = 'BLENDER_EEVEE'
sc.eevee.taa_render_samples = args.samples
sc.eevee.use_raytracing = True
sc.eevee.use_shadows = True
sc.view_settings.view_transform = 'AgX'
sc.view_settings.exposure = args.exposure
sc.render.fps = args.fps
sc.frame_start, sc.frame_end = 1, args.frames
sc.render.image_settings.media_type = 'IMAGE'
sc.render.image_settings.file_format = 'PNG'


# ---------------------------------------------------------------- materials
def image_node(nt, path, non_color=False):
    n = nt.nodes.new('ShaderNodeTexImage')
    n.image = bpy.data.images.load(path, check_existing=True)
    if non_color:
        n.image.colorspace_settings.name = 'Non-Color'
    return n


def ground_material():
    mat = bpy.data.materials.new('meadow_ground')
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes['Principled BSDF']
    d = os.path.join(CACHE_TEX, 'textures', 'Ground037_2k')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    mp = nt.nodes.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (0.45, 0.45, 0.45)       # a 2.2 m tile
    nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])
    if os.path.isdir(d):
        col = image_node(nt, os.path.join(d, 'Ground037_Color.jpg'))
        rough = image_node(nt, os.path.join(d, 'Ground037_Roughness.jpg'), True)
        nrm = image_node(nt, os.path.join(d, 'Ground037_NormalGL.jpg'), True)
        for n in (col, rough, nrm):
            nt.links.new(mp.outputs['Vector'], n.inputs['Vector'])
        # large-scale variation so the tiling never reads at distance
        noise = nt.nodes.new('ShaderNodeTexNoise')
        noise.inputs['Scale'].default_value = 0.02
        nt.links.new(tc.outputs['Object'], noise.inputs['Vector'])
        hue = nt.nodes.new('ShaderNodeMix')
        hue.data_type = 'RGBA'
        hue.blend_type = 'MULTIPLY'
        hue.inputs['B'].default_value = (0.62, 0.78, 0.42, 1)
        nt.links.new(noise.outputs['Fac'], hue.inputs['Factor'])
        nt.links.new(col.outputs['Color'], hue.inputs['A'])
        nt.links.new(hue.outputs['Result'], bsdf.inputs['Base Color'])
        nt.links.new(rough.outputs['Color'], bsdf.inputs['Roughness'])
        nm = nt.nodes.new('ShaderNodeNormalMap')
        nt.links.new(nrm.outputs['Color'], nm.inputs['Color'])
        nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
    else:
        bsdf.inputs['Base Color'].default_value = (0.09, 0.13, 0.04, 1)
        bsdf.inputs['Roughness'].default_value = 0.9
    return mat


def blade_material():
    mat = bpy.data.materials.new('meadow_blades')
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    uv = nt.nodes.new('ShaderNodeUVMap')
    alb = image_node(nt, os.path.join(GRASS, 'blades_meadow_albedo.png'))
    alb.image.alpha_mode = 'STRAIGHT'
    nt.links.new(uv.outputs['UV'], alb.inputs['Vector'])
    rnd = nt.nodes.new('ShaderNodeObjectInfo')
    tint = nt.nodes.new('ShaderNodeMix')
    tint.data_type = 'RGBA'
    tint.blend_type = 'MULTIPLY'
    tint.inputs['Factor'].default_value = 1.0
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (0.70, 0.78, 0.45, 1)
    ramp.color_ramp.elements[1].color = (1.05, 1.0, 0.80, 1)
    nt.links.new(rnd.outputs['Random'], ramp.inputs['Fac'])
    nt.links.new(alb.outputs['Color'], tint.inputs['A'])
    nt.links.new(ramp.outputs['Color'], tint.inputs['B'])
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Roughness'].default_value = 0.55
    nt.links.new(tint.outputs['Result'], bsdf.inputs['Base Color'])
    trl = nt.nodes.new('ShaderNodeBsdfTranslucent')
    nt.links.new(tint.outputs['Result'], trl.inputs['Color'])
    leaf = nt.nodes.new('ShaderNodeMixShader')
    leaf.inputs['Fac'].default_value = 0.35
    nt.links.new(bsdf.outputs[0], leaf.inputs[1])
    nt.links.new(trl.outputs[0], leaf.inputs[2])
    clear = nt.nodes.new('ShaderNodeBsdfTransparent')
    cut = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(alb.outputs['Alpha'], cut.inputs['Fac'])
    nt.links.new(clear.outputs[0], cut.inputs[1])
    nt.links.new(leaf.outputs[0], cut.inputs[2])
    nt.links.new(cut.outputs[0], out.inputs['Surface'])
    return mat


def simple_material(name, color, rough, metal=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    b = mat.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*color, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    return mat


# ---------------------------------------------------------------- the meadow
def mesh_object(name, verts, faces, mat=None, uvs=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    if uvs:
        layer = me.uv_layers.new(name='UVMap')
        for loop in me.loops:
            layer.data[loop.index].uv = uvs[loop.vertex_index]
    if mat:
        me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    sc.collection.objects.link(ob)
    return ob


ground = mesh_object('ground', [(-4000, -4000, 0), (4000, -4000, 0), (4000, 4000, 0), (-4000, 4000, 0)],
                     [(0, 1, 2, 3)], ground_material())

# blade cards: one gently curved 3-segment strip per atlas column
blades_col = bpy.data.collections.new('blades')
bmat = blade_material()
for i in range(8):
    u0, u1 = i / 8.0 + 0.004, (i + 1) / 8.0 - 0.004
    w, h = 0.055, 0.42
    verts, uvs, faces = [], [], []
    for s in range(4):
        t = s / 3.0
        y = 0.04 * t * t                       # a slight forward bend
        verts += [(-w / 2, y, h * t), (w / 2, y, h * t)]
        uvs += [(u0, t), (u1, t)]
    for s in range(3):
        a = s * 2
        faces.append((a, a + 1, a + 3, a + 2))
    me = bpy.data.meshes.new('blade_%d' % i)
    me.from_pydata(verts, [], faces)
    layer = me.uv_layers.new(name='UVMap')
    for loop in me.loops:
        layer.data[loop.index].uv = uvs[loop.vertex_index]
    me.materials.append(bmat)
    ob = bpy.data.objects.new('blade_%d' % i, me)
    blades_col.objects.link(ob)

# the blade patch: a disc round the camera, dense near, thinning out to 120 m
import bmesh
patch_me = bpy.data.meshes.new('meadow_patch')
bm = bmesh.new()
bmesh.ops.create_circle(bm, cap_ends=True, segments=96, radius=120.0)
bm.to_mesh(patch_me)
patch = bpy.data.objects.new('meadow_patch', patch_me)
patch.location.z = 0.002
sc.collection.objects.link(patch)
gn = bpy.data.node_groups.new('meadow_scatter', 'GeometryNodeTree')
gn.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
gn.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
N, L = gn.nodes, gn.links
gi, go = N.new('NodeGroupInput'), N.new('NodeGroupOutput')
pos = N.new('GeometryNodeInputPosition')
dist_len = N.new('ShaderNodeVectorMath')
dist_len.operation = 'LENGTH'
L.new(pos.outputs[0], dist_len.inputs[0])
fall = N.new('ShaderNodeMapRange')
fall.inputs['From Min'].default_value = 8.0
fall.inputs['From Max'].default_value = 120.0
fall.inputs['To Min'].default_value = 240.0
fall.inputs['To Max'].default_value = 18.0
L.new(dist_len.outputs['Value'], fall.inputs['Value'])
dist = N.new('GeometryNodeDistributePointsOnFaces')
L.new(gi.outputs[0], dist.inputs['Mesh'])
L.new(fall.outputs['Result'], dist.inputs['Density'])
ci = N.new('GeometryNodeCollectionInfo')
ci.inputs['Collection'].default_value = blades_col
ci.inputs['Separate Children'].default_value = True
ci.inputs['Reset Children'].default_value = True
inst = N.new('GeometryNodeInstanceOnPoints')
inst.inputs['Pick Instance'].default_value = True
L.new(dist.outputs['Points'], inst.inputs['Points'])
L.new(ci.outputs[0], inst.inputs['Instance'])
r_id = N.new('FunctionNodeRandomValue')
r_id.data_type = 'INT'
r_id.inputs['Min'].default_value = 0
r_id.inputs['Max'].default_value = 7
L.new(r_id.outputs['Value'], inst.inputs['Instance Index'])
r_rot = N.new('FunctionNodeRandomValue')
r_rot.data_type = 'FLOAT_VECTOR'
r_rot.inputs['Min'].default_value = (-0.35, -0.35, 0.0)
r_rot.inputs['Max'].default_value = (0.35, 0.35, 6.283)
r_rot.inputs['Seed'].default_value = 3
L.new(r_rot.outputs['Value'], inst.inputs['Rotation'])
r_sc = N.new('FunctionNodeRandomValue')
r_sc.data_type = 'FLOAT_VECTOR'
r_sc.inputs['Min'].default_value = (0.8, 0.8, 0.55)
r_sc.inputs['Max'].default_value = (1.3, 1.3, 1.45)
r_sc.inputs['Seed'].default_value = 7
L.new(r_sc.outputs['Value'], inst.inputs['Scale'])
L.new(inst.outputs['Instances'], go.inputs[0])
patch.modifiers.new('scatter', 'NODES').node_group = gn


def place_references(yaw_deg):
    """White, grey and chrome spheres on stands, plus a crate, in front of a camera heading `yaw_deg`."""
    yaw = math.radians(yaw_deg)
    fwd = (-math.sin(yaw), math.cos(yaw))
    right = (math.cos(yaw), math.sin(yaw))
    at = lambda d, lat: (SPOT[0] + fwd[0] * d + right[0] * lat, SPOT[1] + fwd[1] * d + right[1] * lat)
    refs = [('white', (0.80, 0.80, 0.80), 0.9, 0.0, at(9.0, -2.2)), ('grey', (0.18, 0.18, 0.18), 0.7, 0.0, at(10.0, 0.0)),
            ('chrome', (0.95, 0.95, 0.95), 0.03, 1.0, at(9.0, 2.2))]
    for name, col, rough, metal, (x, y) in refs:
        me = bpy.data.meshes.new(name)
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=32, radius=0.45)
        bm.to_mesh(me)
        for p in me.polygons:
            p.use_smooth = True
        me.materials.append(simple_material(name, col, rough, metal))
        ob = bpy.data.objects.new(name, me)
        ob.location = (x, y, 1.25)
        sc.collection.objects.link(ob)
        st_me = bpy.data.meshes.new(name + '_stand')
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=0.05, radius2=0.05, depth=0.8)
        bm.to_mesh(st_me)
        st_me.materials.append(simple_material(name + '_stand', (0.05, 0.05, 0.05), 0.4))
        st = bpy.data.objects.new(name + '_stand', st_me)
        st.location = (x, y, 0.4)
        sc.collection.objects.link(st)
    crate_dir = os.path.join(CACHE_TEX, 'models', 'wooden_military_crate_1k')
    if os.path.isdir(crate_dir):
        gltf = [f for f in os.listdir(crate_dir) if f.endswith(('.gltf', '.glb'))]
        if gltf:
            before = set(bpy.data.objects)
            bpy.ops.import_scene.gltf(filepath=os.path.join(crate_dir, gltf[0]))
            for ob in set(bpy.data.objects) - before:
                if ob.parent is None:
                    ob.location = (*at(6.5, -0.9), 0.0)
                    ob.rotation_euler = (0, 0, yaw + math.radians(28))


# ---------------------------------------------------------------- cameras
cam_data = bpy.data.cameras.new('cam')
cam = bpy.data.objects.new('cam', cam_data)
sc.collection.objects.link(cam)
sc.camera = cam


SPOT = [0.0, 0.0]        # where the camera stands; the patch and references follow it


def aim(yaw_deg, pitch_deg, lens, z=1.62):
    cam.location = (SPOT[0], SPOT[1], z)
    cam.rotation_euler = (math.radians(90 + pitch_deg), 0.0, math.radians(yaw_deg))
    cam_data.lens = lens


def sunlit_spot(sky, radius_px=3):
    """The nearest point to the origin standing in sunlight, from our own cloud-shadow field."""
    import numpy as np
    sky.update(0.0)
    size, extent = 192, 6144.0
    tr = sky.baker().shadow_map(sky.sky.U, size, (0.0, 0.0, 0.0), extent)[..., 0]
    best, best_d = None, 1e9
    for j in range(radius_px, size - radius_px):
        for i in range(radius_px, size - radius_px):
            if tr[j, i] > 0.97 and tr[j - radius_px:j + radius_px + 1, i - radius_px:i + radius_px + 1].min() > 0.9:
                x, y = ((i + 0.5) / size - 0.5) * extent, ((j + 0.5) / size - 0.5) * extent
                d = x * x + y * y
                if d < best_d:
                    best, best_d = (x, y), d
    return best


# ---------------------------------------------------------------- the sky
os.makedirs(OUT, exist_ok=True)
cache = os.path.join(OUT, args.name + '_cache')
kw = {}
if args.ambient is not None:
    kw['ambient'] = args.ambient
if args.shafts is not None:
    kw['shafts'] = args.shafts
if args.shadow_height is not None:
    kw['shadow_height'] = args.shadow_height
sky = make_sky(sc, camera=cam, world='earth', hours=args.hours, clouds=args.clouds, weather=args.weather,
               cache_dir=cache, quality=args.quality, shadows=not args.no_shadows, weather_fx=False, **kw)
if args.transition:
    nm, secs, at = args.transition.split(':')
    sky.transition_to(nm, 1.0, float(secs), at=float(at))
sd = sky.sun_dir
sun_yaw = math.degrees(math.atan2(-sd[0], sd[1]))         # heading of the sun, from +Y toward -X
print('[test] sun dir (Blender)', [round(c, 3) for c in sd], 'elevation %.1f deg' % math.degrees(math.asin(sd[2])))
# (pitch, lens, heading relative to the sun): looking up with the sun out of frame on the left, so the
# cumulus are side-lit; level with the sun behind-left, so the references show a lit side and a terminator
# 'high' stands 45 m up looking down across the land with the sun behind: the cloud shadows on the ground
# 'sun' looks into the sun: the HDR disc, its glow lobes and the forward-scattered cloud rims
views = {'up': (25.0, 18.0, -75.0, 1.62), 'level': (4.0, 26.0, -130.0, 1.62), 'high': (-9.0, 24.0, -165.0, 45.0),
         'sun': (20.0, 24.0, 8.0, 1.62)}
yaw = args.yaw if args.yaw is not None else sun_yaw + views['level'][2]
if args.spot == 'auto':
    s = sunlit_spot(sky)
    if s:
        SPOT[:] = s
elif args.spot:
    SPOT[:] = [float(v) for v in args.spot.split(',')]
print('[test] camera stands at', [round(v, 1) for v in SPOT])
patch.location.x, patch.location.y = SPOT
place_references(yaw)
for view in args.views.split(','):
    pitch, lens, rel, z = views[view]
    aim(args.yaw if args.yaw is not None else sun_yaw + rel, pitch, lens, z)
    t0 = time.time()
    # each view is its own bake: the camera layer belongs to its camera
    sky2 = make_sky(sc, camera=cam, world='earth', hours=args.hours, clouds=args.clouds, weather=args.weather,
                    cache_dir=os.path.join(cache, view), quality=args.quality, shadows=not args.no_shadows,
                    sun=sky.sun, weather_fx=False, **kw)
    if args.transition:
        nm, secs, at = args.transition.split(':')
        sky2.transition_to(nm, 1.0, float(secs), at=float(at))
    if args.fog > 0:
        sky2.use_fog(density=args.fog)
    frames = sky2.bake()
    print('[test] %s bake %.1fs' % (view, time.time() - t0))
    for f in range(sc.frame_start, sc.frame_end + 1, args.step):
        sc.frame_set(f)
        suffix = '' if args.frames == 1 else '_f%03d' % f
        sc.render.filepath = os.path.join(OUT, 'meadow_%s_%s%s.png' % (args.name, view, suffix))
        t1 = time.time()
        bpy.ops.render.render(write_still=True)
        print('[test] rendered %s in %.1fs' % (sc.render.filepath, time.time() - t1))
    if view == 'level' and not args.no_shadows:
        import numpy as np
        import OpenImageIO as oiio
        buf = oiio.ImageBuf(os.path.join(cache, view, 'sky_shadow_%04d.exr' % sc.frame_start))
        arr = np.asarray(buf.get_pixels(oiio.FLOAT))[..., 0]
        print('[test] shadow transmittance min %.3f mean %.3f' % (arr.min(), arr.mean()))
        o = oiio.ImageBuf(oiio.ImageSpec(arr.shape[1], arr.shape[0], 1, 'uint8'))
        o.set_pixels(oiio.ROI(), (np.clip(arr, 0, 1) ** (1 / 2.2))[..., None].astype(np.float32))
        o.write(os.path.join(OUT, '%s_shadow.png' % args.name))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(cache, 'meadow_%s.blend' % args.name))
print('[test] done')
