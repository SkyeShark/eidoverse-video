"""The EEVEE world that shows the baked sky and lights the scene with it.

Camera rays see the camera layer (our sky for the bake camera's exact rays, sun disc included), found
by projecting the ray direction into the bake camera of that frame; outside that frustum they fall back
to the environment. Every other ray sees the environment equirect, which has no sun disc (the sun lamp is
the sun): glossy rays at the sky's own radiance (a mirror reflects the sky it stands under), diffuse light
scaled by the keyed fill (ambient x hemiDim, the weather's dimming of the sky fill).

Verified in probe_world_api.py: Light Path 'Is Camera Ray' works in an EEVEE world (P1), Texture Coordinate
'Generated' is the world-space view direction there (P2), an image sequence drives world lighting per frame
(P4), EEVEE's world lighting tells 'Is Diffuse Ray' from 'Is Glossy Ray' (P5), and an image sequence shows
floor(time) at sub-frames and file (first - 1) at any time before its range (P6). So every per-frame key is
held over [f, f+1), the span in which the sequence shows frame f, and the file before the first is a copy of
the first: a motion-blur sub-frame always reads a layer through that same layer's camera.
"""
import shutil

import bpy

GROUP = 'eido_sky_camera_projection'


def _projection_group():
    ng = bpy.data.node_groups.get(GROUP)
    if ng:
        return ng
    ng = bpy.data.node_groups.new(GROUP, 'ShaderNodeTree')
    io = ng.interface
    io.new_socket('Direction', in_out='INPUT', socket_type='NodeSocketVector')
    io.new_socket('Right', in_out='INPUT', socket_type='NodeSocketVector')
    io.new_socket('Up', in_out='INPUT', socket_type='NodeSocketVector')
    io.new_socket('Forward', in_out='INPUT', socket_type='NodeSocketVector')
    io.new_socket('TanX', in_out='INPUT', socket_type='NodeSocketFloat')
    io.new_socket('TanY', in_out='INPUT', socket_type='NodeSocketFloat')
    io.new_socket('UV', in_out='OUTPUT', socket_type='NodeSocketVector')
    io.new_socket('Valid', in_out='OUTPUT', socket_type='NodeSocketFloat')
    N, L = ng.nodes, ng.links
    gi = N.new('NodeGroupInput')
    go = N.new('NodeGroupOutput')

    def vdot(a, b):
        n = N.new('ShaderNodeVectorMath')
        n.operation = 'DOT_PRODUCT'
        L.new(a, n.inputs[0])
        L.new(b, n.inputs[1])
        return n.outputs['Value']

    def math(op, a, b=None, clamp=False):
        n = N.new('ShaderNodeMath')
        n.operation = op
        n.use_clamp = clamp
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                L.new(v, n.inputs[i])
        return n.outputs[0]

    x = vdot(gi.outputs['Direction'], gi.outputs['Right'])
    y = vdot(gi.outputs['Direction'], gi.outputs['Up'])
    z = vdot(gi.outputs['Direction'], gi.outputs['Forward'])
    zs = math('MAXIMUM', z, 1e-6)
    u = math('ADD', math('MULTIPLY', math('DIVIDE', math('DIVIDE', x, zs), gi.outputs['TanX']), 0.5), 0.5)
    v = math('ADD', math('MULTIPLY', math('DIVIDE', math('DIVIDE', y, zs), gi.outputs['TanY']), 0.5), 0.5)
    comb = N.new('ShaderNodeCombineXYZ')
    L.new(u, comb.inputs['X'])
    L.new(v, comb.inputs['Y'])
    L.new(comb.outputs['Vector'], go.inputs['UV'])
    # valid = z > 0 and 0 <= u, v <= 1
    in_front = math('GREATER_THAN', z, 1e-4)
    u_ok = math('MULTIPLY', math('GREATER_THAN', u, 0.0), math('LESS_THAN', u, 1.0))
    v_ok = math('MULTIPLY', math('GREATER_THAN', v, 0.0), math('LESS_THAN', v, 1.0))
    L.new(math('MULTIPLY', in_front, math('MULTIPLY', u_ok, v_ok)), go.inputs['Valid'])
    return ng


def _seq_image(path_first, frame_start, n_frames, name):
    img = bpy.data.images.get(name)
    if img is None:
        img = bpy.data.images.load(path_first, check_existing=False)
        img.name = name
    else:
        img.filepath = path_first
    img.source = 'SEQUENCE' if n_frames > 1 else 'FILE'
    img.alpha_mode = 'CHANNEL_PACKED'
    img.colorspace_settings.name = 'Linear Rec.709'
    if bpy.data.filepath:
        try:                                   # a saved film .blend travels with its sky_cache folder
            img.filepath = bpy.path.relpath(path_first)
        except ValueError:                     # another drive: keep it absolute
            pass
    img.reload()
    return img


def _set_user(node, frame_start, n_frames):
    iu = node.image_user
    iu.frame_start = frame_start
    iu.frame_duration = n_frames
    iu.frame_offset = frame_start - 1
    iu.use_auto_refresh = True
    iu.use_cyclic = False


def hold_before_first(pattern, frame_start):
    """Before its range a sequence shows file frame_start - 1 (P6: a missing file renders magenta), and the keys
    hold their first value there: make that file the first frame's, so the two agree (motion-blur sub-frames
    of the first frame, handles). After the range Blender already holds the last file."""
    if frame_start - 1 >= 0:            # (a negative frame number has no file name Blender would look for)
        shutil.copyfile(pattern % frame_start, pattern % (frame_start - 1))


def build_world(world, cam_first, env_first, frame_start, n_frames):
    """Rebuild `world`'s nodes for the baked sky. Returns the nodes whose inputs are keyed per frame.

    The bake camera's basis lives in the shared eido_sky_view group (sky_view.py), so the materials that read a
    camera layer (the sky elements, the cloud dome) project through the same keys. Diffuse rays also get a keyed
    tint and an added ambient radiance (the shieldworld's night ambients; neutral otherwise)."""
    from .sky_view import view_group, view_handles
    world.use_nodes = True
    world.sun_threshold = 0.0          # our sun is the lamp: never extract a second one from the world
    nt = world.node_tree
    nt.nodes.clear()
    N, L = nt.nodes, nt.links
    out = N.new('ShaderNodeOutputWorld')
    out.location = (1300, 0)
    bg = N.new('ShaderNodeBackground')
    bg.location = (700, 0)

    tc = N.new('ShaderNodeTexCoord')
    tc.location = (-900, 200)
    vg = view_group()
    basis, tans = view_handles()
    view = N.new('ShaderNodeGroup')
    view.node_tree = vg
    view.location = (-900, -200)
    grp = N.new('ShaderNodeGroup')
    grp.node_tree = _projection_group()
    grp.location = (-600, 0)
    L.new(tc.outputs['Generated'], grp.inputs['Direction'])
    for key in ('Right', 'Up', 'Forward', 'TanX', 'TanY'):
        L.new(view.outputs[key], grp.inputs[key])

    cam_tex = N.new('ShaderNodeTexImage')
    cam_tex.name = cam_tex.label = 'eido_sky_camera_layer'
    cam_tex.location = (-300, 150)
    cam_tex.image = _seq_image(cam_first, frame_start, n_frames, 'eido_sky_camera_layer')
    cam_tex.extension = 'EXTEND'
    cam_tex.interpolation = 'Linear'
    _set_user(cam_tex, frame_start, n_frames)
    L.new(grp.outputs['UV'], cam_tex.inputs['Vector'])

    env_tex = N.new('ShaderNodeTexEnvironment')
    env_tex.name = env_tex.label = 'eido_sky_environment'
    env_tex.location = (-300, -200)
    env_tex.image = _seq_image(env_first, frame_start, n_frames, 'eido_sky_environment')
    env_tex.interpolation = 'Linear'
    _set_user(env_tex, frame_start, n_frames)

    lp = N.new('ShaderNodeLightPath')
    lp.location = (-300, 420)
    use_cam = N.new('ShaderNodeMath')
    use_cam.operation = 'MULTIPLY'
    use_cam.location = (100, 300)
    L.new(lp.outputs['Is Camera Ray'], use_cam.inputs[0])
    L.new(grp.outputs['Valid'], use_cam.inputs[1])
    mix = N.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.location = (350, 100)
    L.new(use_cam.outputs[0], mix.inputs['Factor'])
    L.new(env_tex.outputs['Color'], mix.inputs['A'])
    L.new(cam_tex.outputs['Color'], mix.inputs['B'])
    # diffuse rays: the environment times a keyed tint (white unless a world asks), plus a keyed ambient radiance
    diffuse = N.new('ShaderNodeMath')
    diffuse.operation = 'MULTIPLY'
    diffuse.location = (100, 500)
    inv_cam = N.new('ShaderNodeMath')
    inv_cam.operation = 'SUBTRACT'
    inv_cam.inputs[0].default_value = 1.0
    L.new(lp.outputs['Is Camera Ray'], inv_cam.inputs[1])
    inv_gl = N.new('ShaderNodeMath')
    inv_gl.operation = 'SUBTRACT'
    inv_gl.inputs[0].default_value = 1.0
    L.new(lp.outputs['Is Glossy Ray'], inv_gl.inputs[1])
    L.new(inv_cam.outputs[0], diffuse.inputs[0])
    L.new(inv_gl.outputs[0], diffuse.inputs[1])
    tint = N.new('ShaderNodeCombineXYZ')
    tint.name = tint.label = 'eido_sky_diffuse_tint'
    tint.location = (100, 700)
    for ax in 'XYZ':
        tint.inputs[ax].default_value = 1.0
    tint_eff = N.new('ShaderNodeMix')
    tint_eff.data_type = 'RGBA'
    tint_eff.location = (350, 600)
    tint_eff.inputs['A'].default_value = (1.0, 1.0, 1.0, 1.0)
    L.new(diffuse.outputs[0], tint_eff.inputs['Factor'])
    L.new(tint.outputs['Vector'], tint_eff.inputs['B'])
    tinted = N.new('ShaderNodeMix')
    tinted.data_type = 'RGBA'
    tinted.blend_type = 'MULTIPLY'
    tinted.location = (550, 200)
    tinted.inputs['Factor'].default_value = 1.0
    L.new(mix.outputs['Result'], tinted.inputs['A'])
    L.new(tint_eff.outputs['Result'], tinted.inputs['B'])
    L.new(tinted.outputs['Result'], bg.inputs['Color'])
    add = N.new('ShaderNodeCombineXYZ')
    add.name = add.label = 'eido_sky_ambient_add'
    add.location = (100, 900)
    bg2 = N.new('ShaderNodeBackground')
    bg2.location = (900, 300)
    L.new(add.outputs['Vector'], bg2.inputs['Color'])
    L.new(diffuse.outputs[0], bg2.inputs['Strength'])
    sh_add = N.new('ShaderNodeAddShader')
    sh_add.location = (1100, 0)
    L.new(bg.outputs['Background'], sh_add.inputs[0])
    L.new(bg2.outputs['Background'], sh_add.inputs[1])
    L.new(sh_add.outputs['Shader'], out.inputs['Surface'])

    # strength: the keyed fill (ambient x hemiDim) for diffuse light and anything else; 1 for glossy rays and
    # camera rays, which see the sky at the radiance it has (P5: the world's lighting tells the two apart)
    ambient = N.new('ShaderNodeValue')
    ambient.name = ambient.label = 'eido_sky_ambient'
    ambient.location = (100, -300)
    glossy = N.new('ShaderNodeMix')
    glossy.data_type = 'FLOAT'
    glossy.name = glossy.label = 'eido_sky_glossy_full'
    glossy.location = (300, -300)
    L.new(lp.outputs['Is Glossy Ray'], glossy.inputs['Factor'])
    L.new(ambient.outputs['Value'], glossy.inputs['A'])
    glossy.inputs['B'].default_value = 1.0
    strength = N.new('ShaderNodeMix')
    strength.data_type = 'FLOAT'
    strength.location = (500, -250)
    L.new(lp.outputs['Is Camera Ray'], strength.inputs['Factor'])
    L.new(glossy.outputs['Result'], strength.inputs['A'])
    strength.inputs['B'].default_value = 1.0
    L.new(strength.outputs['Result'], bg.inputs['Strength'])
    return dict(basis=basis, tans=tans, ambient=ambient, cam_tex=cam_tex, env_tex=env_tex, tint=tint, add=add,
                view=vg)


def key_world(handles, frame, cam_basis_b, tan_half, fill, tint=None, ambient_add=None):
    """Key one frame's bake-camera projection and diffuse fill, CONSTANT and held over [f, f+1): the span in
    which the image sequences show frame f (P6), so every motion-blur sub-frame reads a layer through its own
    camera. tint / ambient_add (diffuse rays only) are keyed when given."""
    kf = frame
    for key, vec in zip(('Right', 'Up', 'Forward'), cam_basis_b):
        n = handles['basis'][key]
        for i, axis in enumerate('XYZ'):
            n.inputs[axis].default_value = vec[i]
            n.inputs[axis].keyframe_insert('default_value', frame=kf)
    for key, val in zip(('TanX', 'TanY'), tan_half):
        n = handles['tans'][key]
        n.outputs[0].default_value = val
        n.outputs[0].keyframe_insert('default_value', frame=kf)
    a = handles['ambient']
    a.outputs[0].default_value = fill
    a.outputs[0].keyframe_insert('default_value', frame=kf)
    for name, val in (('tint', tint), ('add', ambient_add)):
        if val is None:
            continue
        n = handles[name]
        for i, axis in enumerate('XYZ'):
            n.inputs[axis].default_value = val[i]
            n.inputs[axis].keyframe_insert('default_value', frame=kf)


def constant_interpolation(id_data, prefix=''):
    """CONSTANT keys on id_data's F-curves whose data path starts with `prefix` (all of them by default)."""
    ad = id_data.animation_data
    if not ad or not ad.action:
        return
    for fc in _fcurves(ad):
        if fc.data_path.startswith(prefix):
            for kp in fc.keyframe_points:
                kp.interpolation = 'CONSTANT'


def remove_fcurves(id_data, prefix):
    """Drop id_data's F-curves whose data path starts with `prefix`, leaving everyone else's animation alone."""
    ad = id_data.animation_data
    if not ad or not ad.action:
        return
    act = ad.action
    bags = []
    if hasattr(act, 'fcurves'):
        bags.append(act.fcurves)
    try:
        for layer in act.layers:
            for strip in layer.strips:
                cb = strip.channelbag(ad.action_slot)
                if cb:
                    bags.append(cb.fcurves)
    except Exception:
        pass
    for coll in bags:
        for fc in [fc for fc in coll if fc.data_path.startswith(prefix)]:
            coll.remove(fc)


def _fcurves(ad):
    act = ad.action
    if hasattr(act, 'fcurves') and len(getattr(act, 'fcurves', [])):
        return list(act.fcurves)
    # layered actions (Blender 4.4+): the channelbag of this slot
    out = []
    try:
        for layer in act.layers:
            for strip in layer.strips:
                cb = strip.channelbag(ad.action_slot)
                if cb:
                    out.extend(cb.fcurves)
    except Exception:
        pass
    return out
