"""eidoblend.harness.interior_window: the production engine's interior mapping for windows (interior_window.js, the
three-interior-plane technique) as an EEVEE material. A flat window quad looks into a virtual ROOM box behind it:
the view ray is carried into the quad's tangent space and marched to the room's back wall, side walls or
floor/ceiling, where one room picture is sampled. Parallax-correct interiors on a facade, with no interior geometry.

    from eidoblend.harness.interior_window import create_interior_window_material, render_room_image
    mat = create_interior_window_material(room='work/<id>/room_a.png', depth=0.5, brightness=1.0)
    window.data.materials.append(mat)          # any quad / box face with 0..1 UVs (U across, V up)

    room:        an image path or a bpy Image: ONE room picture (512 x 512 is plenty)
    depth:       the room's depth relative to the window's width (0.5: half as deep as the window is wide)
    brightness:  the room's brightness (it is self-lit, as the engine's MeshBasicNodeMaterial was)

The engine's version had to stay tiny (a node graph past about the size of this march compiled to a black shader on
its WebGPU stack), so per-window variety came from a material per room picture across geometry groups; Blender has
no such limit, but the same pattern holds: a few room pictures, one material each, assigned across the windows.
render_room_image() renders a room picture in Blender from a scene you build (or the stock one it builds).

The march, exactly the engine's (branch-free): in tangent space the ray enters at (u, v, 0) heading rd (its depth
component held at most -0.05, so grazing rays still enter), exits through x = 0 or 1, y = 0 or 1, or the back wall
z = -depth, whichever comes first; the back wall shows the picture at (x, y), a side wall at (depth fraction, y), the
floor and ceiling at (x, depth fraction), clamped to 0.02..0.98.
"""

from __future__ import annotations

import os

import bpy


def _n(nt, kind, loc, **props):
    n = nt.nodes.new(kind)
    n.location = loc
    for k, v in props.items():
        setattr(n, k, v)
    return n


def _math(nt, op, a, b=None, loc=(0, 0), clamp=False):
    n = _n(nt, 'ShaderNodeMath', loc, operation=op, use_clamp=clamp)
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            n.inputs[i].default_value = float(v)
        else:
            nt.links.new(v, n.inputs[i])
    return n.outputs[0]


def _vdot(nt, a, b, loc):
    n = _n(nt, 'ShaderNodeVectorMath', loc, operation='DOT_PRODUCT')
    nt.links.new(a, n.inputs[0])
    nt.links.new(b, n.inputs[1])
    return n.outputs['Value']


def create_interior_window_material(room=None, depth=0.5, brightness=1.0, name='interior_window', uv_map='',
                                    atlas=None, reflection=0.0, glass_roughness=0.04):
    """interior_window.js createInteriorWindowMaterial: an unlit, two-sided material that shows a room behind a
    window quad (see the module docstring). room (or atlas, the engine's alias): an image path or a bpy Image.

    reflection (Blender only; 0 = the engine's material exactly): a pane of glass over the room, weighted by its
    Fresnel (IOR 1.52) times this, a glossy layer of glass_roughness that mirrors the sky and the street. The engine's
    shader had no room for it on its WebGPU stack; a facade by daylight reads as glass with it."""
    room = room if room is not None else atlas
    if room is None:
        raise ValueError('[interior_window] room (an image) is required')
    img = room if isinstance(room, bpy.types.Image) else bpy.data.images.load(os.path.abspath(room), check_existing=True)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.use_backface_culling = False
    nt = m.node_tree
    for nd in list(nt.nodes):
        nt.nodes.remove(nd)
    geo = _n(nt, 'ShaderNodeNewGeometry', (-1800, 200))
    tan = _n(nt, 'ShaderNodeTangent', (-1800, -100), direction_type='UV_MAP', uv_map=uv_map)
    uvn = _n(nt, 'ShaderNodeUVMap', (-1800, -350), uv_map=uv_map)
    # bitangent = N x T (the +V direction for an unmirrored UV layout, as three's bitangentView)
    bt = _n(nt, 'ShaderNodeVectorMath', (-1600, -100), operation='CROSS_PRODUCT')
    nt.links.new(geo.outputs['Normal'], bt.inputs[0])
    nt.links.new(tan.outputs['Tangent'], bt.inputs[1])
    # Incoming points from the surface to the eye (three's positionViewDirection): the tangent-space ray is its
    # negative, normalised
    vx = _vdot(nt, geo.outputs['Incoming'], tan.outputs['Tangent'], (-1400, 300))
    vy = _vdot(nt, geo.outputs['Incoming'], bt.outputs['Vector'], (-1400, 150))
    vz = _vdot(nt, geo.outputs['Incoming'], geo.outputs['Normal'], (-1400, 0))
    cmb = _n(nt, 'ShaderNodeCombineXYZ', (-1200, 150))
    nt.links.new(vx, cmb.inputs[0])
    nt.links.new(vy, cmb.inputs[1])
    nt.links.new(vz, cmb.inputs[2])
    nrm = _n(nt, 'ShaderNodeVectorMath', (-1050, 150), operation='NORMALIZE')
    nt.links.new(cmb.outputs[0], nrm.inputs[0])
    sep = _n(nt, 'ShaderNodeSeparateXYZ', (-900, 150))
    nt.links.new(nrm.outputs['Vector'], sep.inputs[0])
    rdx = _math(nt, 'MULTIPLY', sep.outputs[0], -1.0, (-750, 300))
    rdy = _math(nt, 'MULTIPLY', sep.outputs[1], -1.0, (-750, 150))
    rdz = _math(nt, 'MINIMUM', _math(nt, 'MULTIPLY', sep.outputs[2], -1.0, (-750, 0)), -0.05, (-600, 0))
    uvs = _n(nt, 'ShaderNodeSeparateXYZ', (-1600, -350))
    nt.links.new(uvn.outputs['UV'], uvs.inputs[0])
    rox, roy = uvs.outputs[0], uvs.outputs[1]
    # step(0, rd) = rd >= 0: the wall the ray leaves through (Math 'GREATER_THAN' is rd > 0; rd == 0 exactly gives
    # an infinite t either way)
    tx = _math(nt, 'DIVIDE', _math(nt, 'SUBTRACT', _math(nt, 'GREATER_THAN', rdx, 0.0, (-450, 400)), rox, (-300, 400)),
               rdx, (-150, 400))
    ty = _math(nt, 'DIVIDE', _math(nt, 'SUBTRACT', _math(nt, 'GREATER_THAN', rdy, 0.0, (-450, 250)), roy, (-300, 250)),
               rdy, (-150, 250))
    tz = _math(nt, 'DIVIDE', -float(depth), rdz, (-150, 100))
    t_hit = _math(nt, 'MINIMUM', _math(nt, 'MINIMUM', tx, ty, (0, 330)), tz, (150, 250))
    hx = _math(nt, 'MULTIPLY_ADD', rdx, t_hit, (300, 400))
    nt.links.new(rox, hx.node.inputs[2])
    hy = _math(nt, 'MULTIPLY_ADD', rdy, t_hit, (300, 250))
    nt.links.new(roy, hy.node.inputs[2])
    hz = _math(nt, 'MULTIPLY', rdz, t_hit, (300, 100))
    zn = _math(nt, 'DIVIDE', hz, -float(depth), (450, 100))                 # 0 at the glass, 1 at the back wall
    w_back = _math(nt, 'GREATER_THAN', zn, 0.999 - 1e-7, (600, 100))       # step(0.999, zN)
    near0 = _math(nt, 'LESS_THAN', hx, 0.001 + 1e-7, (450, 500))           # step(hit.x, 0.001)
    near1 = _math(nt, 'GREATER_THAN', hx, 0.999 - 1e-7, (450, 450))        # step(0.999, hit.x)
    near_x = _math(nt, 'MAXIMUM', near0, near1, (600, 480))
    w_side = _math(nt, 'SUBTRACT', near_x, w_back, (750, 400), clamp=True)
    w_flat = _math(nt, 'SUBTRACT', _math(nt, 'SUBTRACT', 1.0, w_back, (750, 250)), w_side, (900, 250), clamp=True)
    # roomUV = (x, y) * back + (zN, y) * side + (x, zN) * flat
    u = _math(nt, 'ADD', _math(nt, 'ADD', _math(nt, 'MULTIPLY', hx, w_back, (1050, 500)),
                                      _math(nt, 'MULTIPLY', zn, w_side, (1050, 430)), (1200, 470)),
              _math(nt, 'MULTIPLY', hx, w_flat, (1050, 360)), (1350, 440))
    v = _math(nt, 'ADD', _math(nt, 'ADD', _math(nt, 'MULTIPLY', hy, w_back, (1050, 260)),
                                      _math(nt, 'MULTIPLY', hy, w_side, (1050, 190)), (1200, 230)),
              _math(nt, 'MULTIPLY', zn, w_flat, (1050, 120)), (1350, 200))
    uc = _math(nt, 'MINIMUM', _math(nt, 'MAXIMUM', u, 0.02, (1500, 440)), 0.98, (1650, 440))
    vc = _math(nt, 'MINIMUM', _math(nt, 'MAXIMUM', v, 0.02, (1500, 200)), 0.98, (1650, 200))
    uvv = _n(nt, 'ShaderNodeCombineXYZ', (1800, 320))
    nt.links.new(uc, uvv.inputs[0])
    nt.links.new(vc, uvv.inputs[1])
    tex = _n(nt, 'ShaderNodeTexImage', (1950, 320), image=img, interpolation='Linear', extension='EXTEND')
    nt.links.new(uvv.outputs[0], tex.inputs['Vector'])
    em = _n(nt, 'ShaderNodeEmission', (2250, 320))
    nt.links.new(tex.outputs['Color'], em.inputs['Color'])
    em.inputs['Strength'].default_value = float(brightness)
    out = _n(nt, 'ShaderNodeOutputMaterial', (2650, 320))
    surface = em.outputs[0]
    if reflection > 0:
        fr = _n(nt, 'ShaderNodeFresnel', (2250, 560))
        fr.inputs['IOR'].default_value = 1.52
        k = _math(nt, 'MULTIPLY', fr.outputs[0], float(reflection), (2400, 560), clamp=True)
        gl = _n(nt, 'ShaderNodeBsdfGlossy', (2250, 120))
        gl.inputs['Roughness'].default_value = float(glass_roughness)
        mix = _n(nt, 'ShaderNodeMixShader', (2480, 320))
        nt.links.new(k, mix.inputs['Fac'])
        nt.links.new(em.outputs[0], mix.inputs[1])
        nt.links.new(gl.outputs[0], mix.inputs[2])
        surface = mix.outputs[0]
    nt.links.new(surface, out.inputs['Surface'])
    m['eido_interior_window'] = {'depth': float(depth), 'brightness': float(brightness), 'room': img.name,
                                 'reflection': float(reflection)}
    return m


def render_room_image(path, size=512, build=None, samples=16, width=3.2, height=2.6, depth=3.0,
                      lamp=(1.0, 0.82, 0.62), wall=(0.62, 0.55, 0.47), floor=(0.30, 0.20, 0.13), fov=62.0,
                      wall_material=None, floor_material=None, ceiling_material=None, lamp_power=220.0,
                      window_light=0.0, window_colour=(0.85, 0.9, 1.0)):
    """A room picture for create_interior_window_material, rendered in Blender as the engine's 'ONE room render':
    a scene of its own (the open scene is untouched), a box room (width x height, `depth` deep along +Y, its open
    side at y = 0 is the window), photographed from that window at eye height with a `fov`-degree lens, the back
    wall and the props before it filling most of the frame. The material shows the whole picture on the room's back
    wall and stretches its edges over the sides, floor and ceiling, so the picture should be a room seen straight
    on, not a corridor: keep the lens moderate. build(scene) furnishes it (props at real scale, standing on z = 0,
    inside -width/2..width/2 x 0..depth); without build it is an empty plastered room with a wooden floor under a
    warm ceiling light. Returns the path written.

    wall_material / floor_material / ceiling_material: bpy materials for the room's faces (the walls default to
    flat `wall`, the floor to flat `floor`, the ceiling to the walls'); the room's UVs run 1 a metre on every face,
    so a PBR set (harness.assets.load_pbr) tiles at its real size. lamp, lamp_power: the ceiling light's colour and
    watts. window_light: watts of soft daylight coming in through the window behind the camera (window_colour), for
    a room seen by day (0: lamp-lit only)."""
    import math
    sc = bpy.data.scenes.new('interior_room')
    r = sc.render
    r.engine = 'BLENDER_EEVEE'
    r.resolution_x = r.resolution_y = int(size)
    r.image_settings.media_type = 'IMAGE'
    r.image_settings.file_format = 'PNG'
    r.filepath = os.path.abspath(path)
    sc.eevee.taa_render_samples = int(samples)
    sc.eevee.use_raytracing = True
    sc.view_settings.view_transform = 'AgX'
    w = bpy.data.worlds.new('interior_room')
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.0
    sc.world = w
    hw, d, h = width / 2, depth, height
    me = bpy.data.meshes.new('room')
    verts = [(-hw, 0, 0), (hw, 0, 0), (hw, d, 0), (-hw, d, 0), (-hw, 0, h), (hw, 0, h), (hw, d, h), (-hw, d, h)]
    faces = [(0, 1, 2, 3), (4, 7, 6, 5), (1, 5, 6, 2), (0, 3, 7, 4), (3, 2, 6, 7)]       # no front face: the window
    me.from_pydata(verts, [], faces)
    uv = me.uv_layers.new(name='UVMap')
    for poly in me.polygons:                                       # metres along each face's own plane
        n = poly.normal
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = (co.x, co.y) if abs(n.z) > 0.5 else ((co.y, co.z) if abs(n.x) > 0.5 else (co.x, co.z))

    def mat(name, rgb, rough):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        b = m.node_tree.nodes['Principled BSDF']
        b.inputs['Base Color'].default_value = (*rgb, 1)
        b.inputs['Roughness'].default_value = rough
        return m
    walls = wall_material or mat('room_plaster', wall, 0.85)
    me.materials.append(walls)
    me.materials.append(floor_material or mat('room_floor', floor, 0.45))
    me.materials.append(ceiling_material or walls)
    me.polygons[0].material_index = 1
    me.polygons[1].material_index = 2
    room = bpy.data.objects.new('room', me)
    sc.collection.objects.link(room)
    ld = bpy.data.lights.new('room_lamp', 'AREA')
    ld.shape, ld.size, ld.energy, ld.color = 'DISK', 0.6, float(lamp_power), lamp
    lamp_ob = bpy.data.objects.new('room_lamp', ld)
    lamp_ob.location = (0.0, d * 0.55, h - 0.05)
    sc.collection.objects.link(lamp_ob)
    if window_light > 0:                                           # daylight through the window, behind the camera
        wl = bpy.data.lights.new('room_daylight', 'AREA')
        wl.shape, wl.size, wl.size_y, wl.energy, wl.color = 'RECTANGLE', width * 0.9, h * 0.7, float(window_light), \
            window_colour
        wl_ob = bpy.data.objects.new('room_daylight', wl)
        wl_ob.location = (0.0, -0.45, h * 0.55)
        wl_ob.rotation_euler = (math.radians(90 - 12), 0.0, 0.0)   # -Z (its beam) to +Y into the room, 12 deg down
        sc.collection.objects.link(wl_ob)
    cd = bpy.data.cameras.new('room_cam')
    cd.sensor_fit = 'VERTICAL'
    cd.angle_y = math.radians(fov)
    cd.clip_start = 0.05
    cam = bpy.data.objects.new('room_cam', cd)
    from mathutils import Vector
    eye = min(1.35, h * 0.5)
    cam.location = (0.0, -0.2, eye)
    cam.rotation_euler = (Vector((0.0, d, eye * 0.85)) - Vector(cam.location)).to_track_quat('-Z', 'Y').to_euler()
    sc.collection.objects.link(cam)
    sc.camera = cam
    if build is not None:
        build(sc)
    win = bpy.context.window
    prev = bpy.context.scene
    try:
        if win is not None:
            win.scene = sc
        bpy.ops.render.render(write_still=True, scene=sc.name)
    finally:
        if win is not None:
            win.scene = prev
    return os.path.abspath(path)
