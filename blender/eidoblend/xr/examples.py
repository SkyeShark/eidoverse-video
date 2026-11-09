"""eidoblend.xr.examples: the kit's example (eidoverse/xr/example.html) as a Blender scene. EXAMPLES['city'].

    from eidoblend.xr.examples import EXAMPLES
    city = EXAMPLES['city'](scene)          # -> {'towers', 'ground', 'walkers', 'cameras', 'world', 'fps', 'frames'}

The page's small city, built from the page's own numbers, one Blender metre per stage unit:
  - the sky: the dome's gradient by height (#2a0c34 at the horizon, #130822, #05030b overhead) as the world;
  - the ground: 120 x 120 units, an antialiased grid with one line a unit fading out by 60 units. The page draws its
    lines a constant 1.2 px wide with fwidth(); Blender's shader nodes have no screen derivatives, so the port builds
    the same footprint from the camera: view distance x the pixel's angle, stretched by the grazing angle along the
    view (grid_pixel_angle). The object carries xr_material = 'grid', so an XR page draws it with the page's own TSL
    grid (eidoblend/xr/page/xr_page.html), which a texture cannot reproduce at every distance;
  - the towers: 36 boxes from the page's Park-Miller generator (seed 11) in ONE mesh (the page's one instanced draw),
    each face carrying the unit box position 'g0' and 'tower' = (width, height, index), so the material computes the
    page's windows (one a unit at 0.8, 40 % lit) and the neon roof from the same numbers. The page's hash is PCG on
    integers; Blender's shader nodes hash with White Noise: the same density, a different draw;
  - the walkers: 24 boxes going round the square, moved by a Geometry Nodes tree from the scene time with the page's
    formula (angle = 2 pi i / 24 + t 0.9 / r, r = 5 + 2 (i mod 4), a hop |sin(6 t + 9 a0)| x 0.25), instanced;
  - every material unlit, as the page's MeshBasic materials, under the Standard view (no tone curve, as the page);
  - the kit's views: cam_street (stand at stage (0, 0, 10), eyes 1.6 m at 0.25 m a unit, facing the square) and
    cam_table (the desktop table view: 1 cm a unit, the orbit camera at pitch 0.6, 1.4 m from the table), plus the
    scene's XR settings (eidoblend.xr.export.set_xr) the export and the page read.
"""
from __future__ import annotations

import math

import bpy

from . import _bl
from ._bl import Tree, hex_rgb

# the page's numbers
N_TOWERS, N_WALKERS = 36, 24
STREET, TABLE, EYE = 0.25, 0.01, 1.6
START_THREE, TOWARD_THREE = (0.0, 0.0, 10.0), (0.0, 0.0, -1.0)
PAGE_FOV = 70.0


def park_miller(seed=11):
    s = seed

    def rnd():
        nonlocal s
        s = (s * 16807) % 2147483647
        return s / 2147483647
    return rnd


def tower_layout(seed=11):
    """[(x, z, width, height)] in the page's stage units (three axes), exactly as example.html draws them."""
    rnd = park_miller(seed)
    out = []
    for i in range(N_TOWERS):
        a = (i / N_TOWERS) * math.pi * 2 + rnd() * 0.15
        r = 14 + rnd() * 18
        out.append((math.cos(a) * r, math.sin(a) * r, 3 + rnd() * 3, 6 + rnd() * 22))
    return out


def walker_position(i, t):
    """The page's walker i at t seconds, in three axes (x, y, z) of the box's base."""
    a0 = (i / N_WALKERS) * math.pi * 2
    r = 5 + (i % 4) * 2
    ang = a0 + t * (0.9 / r)
    return (math.cos(ang) * r, abs(math.sin(t * 6 + a0 * 9)) * 0.25, math.sin(ang) * r)


# ------------------------------------------------------------------------------------------------- the world ---

def sky_world(name='xr_city_sky'):
    w = bpy.data.worlds.get(name) or bpy.data.worlds.new(name)
    w.use_nodes = True
    T = Tree(w.node_tree)
    tc = T.node('ShaderNodeTexCoord')
    sep = T.node('ShaderNodeSeparateXYZ', inputs={0: tc.outputs['Generated']})
    h = T.math('MAXIMUM', sep.outputs['Z'], 0.0)
    h = T.math('MINIMUM', h, 1.0)
    k1 = T.math('MULTIPLY', h, 4.0, clamp=True)
    c1 = T.mix_rgb(k1, hex_rgb('#2a0c34') + (1,), hex_rgb('#130822') + (1,))
    k2 = T.math('MULTIPLY', T.math('SUBTRACT', h, 0.15), 2.0, clamp=True)
    c = T.mix_rgb(k2, c1, hex_rgb('#05030b') + (1,))
    bg = T.node('ShaderNodeBackground', inputs={'Color': c, 'Strength': 1.0})
    out = T.node('ShaderNodeOutputWorld')
    T.link(bg.outputs[0], out.inputs['Surface'])
    return w


# ------------------------------------------------------------------------------------------------ the ground ---

def grid_material(name='xr_city_grid'):
    """The page's antialiased grid, ported: lines at whole units, about 1.2 px wide at any distance, fading by 60."""
    m = _bl.new_material(name)
    T = Tree(m.node_tree)
    geo = T.node('ShaderNodeNewGeometry')
    cam = T.node('ShaderNodeCameraData')
    px = T.value(0.0013, label='px_angle')                 # radians a pixel (grid_pixel_angle sets it)
    pos = T.node('ShaderNodeSeparateXYZ', inputs={0: geo.outputs['Position']})
    gx, gy = pos.outputs['X'], pos.outputs['Y']
    inc = T.node('ShaderNodeSeparateXYZ', inputs={0: geo.outputs['Incoming']})
    ndv = T.math('MAXIMUM', T.math('ABSOLUTE', inc.outputs['Z']), 0.06)
    hl = T.math('SQRT', T.math('ADD', T.math('MULTIPLY', inc.outputs['X'], inc.outputs['X']),
                               T.math('MULTIPLY', inc.outputs['Y'], inc.outputs['Y'])))
    hl = T.math('MAXIMUM', hl, 1e-4)
    ax = T.math('ABSOLUTE', T.math('DIVIDE', inc.outputs['X'], hl))
    ay = T.math('ABSOLUTE', T.math('DIVIDE', inc.outputs['Y'], hl))
    foot = T.math('MULTIPLY', cam.outputs['View Distance'], px)
    # fwidth along x: across-view part |a.y| + along-view part |a.x| / cos(incidence) (and the same for y)
    fwx = T.math('MULTIPLY', foot, T.math('ADD', ay, T.math('DIVIDE', ax, ndv)))
    fwy = T.math('MULTIPLY', foot, T.math('ADD', ax, T.math('DIVIDE', ay, ndv)))

    def axis(g, fw):
        d = T.math('ABSOLUTE', T.math('SUBTRACT', T.math('FRACT', T.math('SUBTRACT', g, 0.5)), 0.5))
        d = T.math('DIVIDE', d, T.math('MAXIMUM', fw, 1e-4))
        mr = T.node('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP',
                    inputs={'Value': d, 'From Min': 0.0, 'From Max': 1.2, 'To Min': 0.0, 'To Max': 1.0})
        return mr.outputs['Result']
    line = T.math('SUBTRACT', 1.0, T.math('MINIMUM', axis(gx, fwx), axis(gy, fwy)))
    r = T.math('SQRT', T.math('ADD', T.math('MULTIPLY', gx, gx), T.math('MULTIPLY', gy, gy)))
    fade = T.math('SUBTRACT', 1.0, T.math('DIVIDE', r, 60.0), clamp=True)
    c = T.mix_rgb(T.math('MULTIPLY', line, fade), hex_rgb('#0b0812') + (1,), hex_rgb('#35e8ff', 0.35) + (1,))
    _bl.unlit_output(T, c)
    m.diffuse_color = hex_rgb('#0b0812') + (1.0,)
    return m


def grid_pixel_angle(scene, material_name='xr_city_grid', camera=None):
    """The grid's pixel footprint for a camera at the scene's resolution: 2 tan(fov_v / 2) / height in pixels."""
    cam = camera or scene.camera
    m = bpy.data.materials.get(material_name)
    if cam is None or m is None:
        return None
    r = scene.render
    w = r.resolution_x * r.resolution_percentage / 100.0
    h = r.resolution_y * r.resolution_percentage / 100.0
    d = cam.data
    if d.sensor_fit == 'VERTICAL' or (d.sensor_fit == 'AUTO' and h > w):
        sensor = d.sensor_height if d.sensor_fit == 'VERTICAL' else d.sensor_width
        tan_v = sensor / 2 / d.lens
    else:
        sensor = d.sensor_width
        tan_v = sensor / 2 / d.lens * (h / w)
    a = 2 * tan_v / h
    m.node_tree.nodes['px_angle'].outputs[0].default_value = a
    return a


def make_ground(collection, name='xr_city_ground'):
    me = bpy.data.meshes.new(name)
    s = 60.0
    me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name='UVMap')
    for li, (u, v) in zip(range(4), ((0, 0), (1, 0), (1, 1), (0, 1))):
        uv.data[li].uv = (u, v)
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    me.materials.append(grid_material())
    ob['xr_material'] = 'grid'
    ob['xr_params'] = '{"dark": "#0b0812", "line": "#35e8ff", "line_scale": 0.35, "fade": 60}'
    return ob


# ------------------------------------------------------------------------------------------------ the towers ---

def towers_material(name='xr_city_towers'):
    """example.html's tower shader, ported: windows from the unit box position and the tower's size, a neon roof."""
    m = _bl.new_material(name)
    T = Tree(m.node_tree)
    g0 = T.node('ShaderNodeAttribute', attribute_name='g0', attribute_type='GEOMETRY')
    tw = T.node('ShaderNodeAttribute', attribute_name='tower', attribute_type='GEOMETRY')
    g = T.node('ShaderNodeSeparateXYZ', inputs={0: g0.outputs['Vector']})       # three's axes: y up
    s = T.node('ShaderNodeSeparateXYZ', inputs={0: tw.outputs['Vector']})       # (width, height, index)
    cx = T.math('MULTIPLY', T.math('MULTIPLY', T.math('ADD', g.outputs['X'], g.outputs['Z']), s.outputs['X']), 0.8)
    cy = T.math('MULTIPLY', T.math('MULTIPLY', g.outputs['Y'], s.outputs['Y']), 0.8)
    wx = T.math('GREATER_THAN', T.math('FRACT', cx), 0.35)
    wy = T.math('GREATER_THAN', T.math('FRACT', cy), 0.4)
    # the index is a per-vertex float the rasteriser interpolates (7.0 arrives as 6.9999995 on some pixels) and White
    # Noise hashes exact bits: round it, as the page's instanceIndex is an exact integer
    seed = T.node('ShaderNodeCombineXYZ', inputs={0: T.math('ROUND', s.outputs['Z']), 1: T.math('FLOOR', cx),
                                                 2: T.math('FLOOR', cy)})
    hn = T.node('ShaderNodeTexWhiteNoise', noise_dimensions='3D', inputs={'Vector': seed.outputs[0]})
    lit = T.math('GREATER_THAN', hn.outputs['Value'], 0.6)
    win = T.math('MULTIPLY', T.math('MULTIPLY', wx, wy), lit)
    geo = T.node('ShaderNodeNewGeometry')
    nz = T.node('ShaderNodeSeparateXYZ', inputs={0: geo.outputs['Normal']}).outputs['Z']
    side = T.math('LESS_THAN', T.math('ABSOLUTE', nz), 0.5)
    roof = T.math('GREATER_THAN', nz, 0.5)
    c = T.mix_rgb(T.math('MULTIPLY', win, side), hex_rgb('#1a1626') + (1,), hex_rgb('#ffd28a', 1.6) + (1,))
    neon = T.mix_rgb(T.math('MULTIPLY', roof, 0.8), (0, 0, 0, 1), hex_rgb('#ff3fd0') + (1,))
    c = T.mix_rgb(1.0, c, neon, blend='ADD')
    _bl.unlit_output(T, c)
    m.diffuse_color = hex_rgb('#1a1626') + (1.0,)
    return m


def make_towers(collection, name='xr_city_towers', seed=11):
    """One mesh, 36 boxes (sides and roof), per-vertex 'g0' (the unit box, three axes) and 'tower' (w, h, i)."""
    verts, faces, g0s, tws = [], [], [], []
    # unit box faces in three's axes (x, y, z), y in [0, 1]; each face's corners counter-clockwise from outside
    F = [((0.5, 0, 0.5), (0.5, 0, -0.5), (0.5, 1, -0.5), (0.5, 1, 0.5)),      # +x
         ((-0.5, 0, -0.5), (-0.5, 0, 0.5), (-0.5, 1, 0.5), (-0.5, 1, -0.5)),  # -x
         ((-0.5, 0, 0.5), (0.5, 0, 0.5), (0.5, 1, 0.5), (-0.5, 1, 0.5)),      # +z
         ((0.5, 0, -0.5), (-0.5, 0, -0.5), (-0.5, 1, -0.5), (0.5, 1, -0.5)),  # -z
         ((-0.5, 1, 0.5), (0.5, 1, 0.5), (0.5, 1, -0.5), (-0.5, 1, -0.5))]    # +y (the roof)
    for i, (x, z, w, h) in enumerate(tower_layout(seed)):
        for face in F:
            base = len(verts)
            for (ux, uy, uz) in face:
                tx, ty, tz = x + ux * w, uy * h, z + uz * w
                verts.append((tx, -tz, ty))                                      # three -> Blender
                g0s.append((ux, uy, uz))
                tws.append((w, h, float(i)))
            faces.append((base, base + 1, base + 2, base + 3))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.validate()
    a = me.attributes.new('g0', 'FLOAT_VECTOR', 'POINT')
    a.data.foreach_set('vector', [c for v in g0s for c in v])
    a = me.attributes.new('tower', 'FLOAT_VECTOR', 'POINT')
    a.data.foreach_set('vector', [c for v in tws for c in v])
    me.materials.append(towers_material())
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    return ob


# ------------------------------------------------------------------------------------------------ the walkers ---

def walker_material(name='xr_city_walker'):
    m = _bl.new_material(name)
    T = Tree(m.node_tree)
    geo = T.node('ShaderNodeNewGeometry')
    nz = T.node('ShaderNodeSeparateXYZ', inputs={0: geo.outputs['Normal']}).outputs['Z']
    k = T.math('ADD', T.math('MULTIPLY', nz, 0.3), 0.8)
    kc = T.node('ShaderNodeCombineColor', inputs={0: k, 1: k, 2: k})
    c = T.mix_rgb(1.0, hex_rgb('#d77757') + (1,), kc.outputs[0], blend='MULTIPLY')
    _bl.unlit_output(T, c)
    m.diffuse_color = hex_rgb('#d77757') + (1.0,)
    return m


def walkers_tree(frame_start, fps, name='xr_city_walkers'):
    """Geometry Nodes: 24 points placed by the page's formula at the scene time, a 0.8 box instanced on each."""
    ng = bpy.data.node_groups.get(name)
    if ng is not None:
        bpy.data.node_groups.remove(ng)
    ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    T = Tree(ng)
    T.node('NodeGroupInput')
    out = T.node('NodeGroupOutput')
    st = T.node('GeometryNodeInputSceneTime')
    t = T.math('DIVIDE', T.math('SUBTRACT', st.outputs['Frame'], float(frame_start)), float(fps))
    idx = T.node('GeometryNodeInputIndex').outputs[0]
    a0 = T.math('MULTIPLY', T.math('DIVIDE', idx, float(N_WALKERS)), math.pi * 2)
    r = T.math('ADD', T.math('MULTIPLY', T.math('FLOORED_MODULO', idx, 4.0), 2.0), 5.0)
    ang = T.math('ADD', a0, T.math('MULTIPLY', t, T.math('DIVIDE', 0.9, r)))
    x = T.math('MULTIPLY', T.math('COSINE', ang), r)
    y = T.math('MULTIPLY', T.math('MULTIPLY', T.math('SINE', ang), r), -1.0)            # three z -> Blender -y
    hop = T.math('MULTIPLY', T.math('ABSOLUTE', T.math('SINE', T.math('ADD', T.math('MULTIPLY', t, 6.0),
                                                                          T.math('MULTIPLY', a0, 9.0)))), 0.25)
    pos = T.node('ShaderNodeCombineXYZ', inputs={0: x, 1: y, 2: hop})
    pts = T.node('GeometryNodePoints', inputs={'Count': N_WALKERS, 'Position': pos.outputs[0]})
    cube = T.node('GeometryNodeMeshCube', inputs={'Size': (0.8, 0.8, 0.8)})
    lift = T.node('GeometryNodeTransform', inputs={'Geometry': cube.outputs['Mesh'], 'Translation': (0, 0, 0.4)})
    mat = T.node('GeometryNodeSetMaterial', inputs={'Geometry': lift.outputs[0]})
    mat.inputs['Material'].default_value = walker_material()
    inst = T.node('GeometryNodeInstanceOnPoints', inputs={'Points': pts.outputs[0], 'Instance': mat.outputs[0]})
    T.link(inst.outputs['Instances'], out.inputs[0])
    return ng


def make_walkers(collection, frame_start, fps, name='xr_city_walkers'):
    me = bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    mod = ob.modifiers.new('walkers', 'NODES')
    mod.node_group = walkers_tree(frame_start, fps)
    return ob


# ------------------------------------------------------------------------------------------------- the views ---

def _camera(collection, name, eye, target=None, rotation=None, fov=PAGE_FOV, aspect=16 / 9):
    cd = bpy.data.cameras.new(name)
    _bl.vertical_fov_lens(cd, fov, aspect)
    cd.clip_start, cd.clip_end = 0.05, 2000.0
    ob = bpy.data.objects.new(name, cd)
    collection.objects.link(ob)
    ob.location = eye
    ob.rotation_euler = rotation if rotation is not None else _bl.look_at_rotation(eye, target)
    return ob


def street_eye(start_three=START_THREE, street=STREET, eye=EYE):
    """Where the page's street view puts your eyes, in stage units, Blender axes."""
    x, _, z = start_three
    return (x, -z, eye / street)


def table_eye(table=TABLE, orbit_pitch=0.6, orbit_dist=1.4):
    """The page's desktop table view (Desktop orbit: yaw 0, pitch 0.6, 1.4 m from the table centre), stage units."""
    up = orbit_dist * math.sin(orbit_pitch) / table
    back = orbit_dist * math.cos(orbit_pitch) / table
    return (0.0, -back, up)


def build_city(scene=None, *, collection='xr_city', fps=24, seconds=30.0, seed=11, resolution=(960, 540)):
    """The kit example's city in `scene` (default: the context scene). Returns its parts."""
    from . import export as X
    sc = scene or bpy.context.scene
    col = bpy.data.collections.get(collection) or bpy.data.collections.new(collection)
    if col.name not in sc.collection.children:
        sc.collection.children.link(col)
    sc.render.fps, sc.render.fps_base = int(fps), 1.0
    sc.frame_start = 1
    sc.frame_end = 1 + int(round(seconds * fps))
    sc.render.resolution_x, sc.render.resolution_y = resolution
    sc.render.resolution_percentage = 100
    sc.render.engine = 'BLENDER_EEVEE'
    sc.view_settings.view_transform = 'Standard'
    sc.view_settings.look = 'None'
    sc.view_settings.exposure = 0.0
    sc.world = sky_world()
    ground = make_ground(col)
    towers = make_towers(col, seed=seed)
    walkers = make_walkers(col, sc.frame_start, fps)
    aspect = resolution[0] / resolution[1]
    eye = street_eye()
    cam_street = _camera(col, 'cam_street', eye, rotation=(math.pi / 2, 0.0, 0.0), aspect=aspect)
    cam_table = _camera(col, 'cam_table', table_eye(), target=(0, 0, 0), aspect=aspect)
    cam_table.data.clip_start = 2.0
    cam_table.data.clip_end = 40000.0
    sc.camera = cam_street
    grid_pixel_angle(sc)
    X.set_xr(sc, street=STREET, table=TABLE, start=(START_THREE[0], -START_THREE[2], 0.0),
             facing=(TOWARD_THREE[0], -TOWARD_THREE[2], 0.0), eye_height=EYE, name='city', table_centre=(0, 0, 0))
    return {'towers': towers, 'ground': ground, 'walkers': walkers, 'cameras': [cam_street, cam_table],
            'world': sc.world, 'fps': fps, 'frames': (sc.frame_start, sc.frame_end), 'collection': col}


EXAMPLES = {'city': build_city}
