"""Cloud shadows: our transmittance field, carried by EEVEE's own sun shadows.

Eanpa integrates transmittance toward the cloud key through the SAME density field the camera sees
(tslCloudTransmittance) into a light-column map and multiplies only the sun's direct light by it.
Here the baker writes that transmittance for the ground points of a square around the camera, and a
hidden caster plane high above the set shows it as transparency to the sun lamp. A receiver anywhere
under the plane reads the value of its own light ray (the ray meets the ground reference further along,
above or below it, and nothing below the cloud deck changes transmittance), so the shadow is exact for
every height under the caster, terrain relief included. The plane therefore sits just under the lowest
cloud base of the bake (where the transmittance integral starts), so everything below the clouds receives;
make_sky(shadow_height=) puts it elsewhere. Only the sun lamp is affected: the plane is invisible to the
camera and to indirect rays.

make_sky(cloud_shadow_strength=s) (wrapCloudShadows' strength, 1 - (1 - T) s) splits the sun: the sun lamp keeps s of
the light and takes the clouds' shadow, and a twin with the rest, 1 - s (CLEAR_SHARE_SUN), passes them (its blockers
leave the caster out). So a partial strength draws the transmittance map as it is, and adds no transparent-shadow
grain over the whole shade (key_clear_share).

An object marked eido_noCloudShadow (WebGPU's userData.noCloudShadow) keeps the sun as if no cloud were overhead:
EEVEE's light linking lights it with a twin of the sun lamp whose blockers leave the caster out, and the sun lamp's
receivers leave it out (link_opt_outs). Its ordinary shadows stay.

Both twins keep the sun lamp's own light linking (the ringworld's, or one a scene set): their blockers and the clear
share's receivers are copies of the lamp's, rebuilt each bake.
"""
import math
import os

import numpy as np

from . import palette as P
from .bake.baker import write_exr

EXTENT = 6144.0          # metres, the WebGPU cloudShadowExtent
STORM_BASE_DROP = 280.0  # the darkstorm layer's base sits this far under cloudStart (sky.glsl stormLayerBottom)
CASTER_UNDER_BASE = 0.9  # the caster at 0.9 of the lowest cloud base: a margin under where shadowing starts
CASTER_MIN = 20.0        # metres above the ground reference, at least
CASTER = 'eido_sky_cloud_shadow_caster'
OPT_OUT = 'eido_noCloudShadow'            # the object property (WebGPU userData.noCloudShadow)
CLEAR_SUN = 'eido_sky_sun_no_cloud_shadow'  # the twin of the sun lamp that lights the opted-out objects
CLEAR_SHARE_SUN = 'eido_sky_sun_clear_share'  # the share of the sun no cloud takes: 1 - cloud_shadow_strength
CASTER_EXCLUDED = 'eido_sky_cloud_caster_excluded'   # the twins' blockers: the sun lamp's, the caster left out


def caster_height_for(frames, ground_z=0.0):
    """Metres above ground_z for the caster: just under the lowest base the transmittance integral starts
    from over the baked frames (cloudTransmittance's shadowBottom: cloudStart, lowered under a storm canopy)."""
    # the ringworld's deck sits on its own profile: ringDeckBase (450 m over the local scene) instead of cloudStart
    base = min(fr['U'].get('ringDeckBase', fr['U']['cloudStart'])
               - STORM_BASE_DROP * min(max(fr['U'].get('stormCanopy', 0.0), 0.0), 1.0) for fr in frames)
    return max(CASTER_MIN, CASTER_UNDER_BASE * base - ground_z)


def deck_top_for(frames, ground_z=0.0):
    """Metres above ground_z of the highest cloud-deck top over the baked frames: the ringworld's deck (ringDeckBase
    + ringDeckThick, 450 + 280 m by default) or cloudStart + cloudHeight, and a storm canopy's own layer (its base 280 m under
    cloudStart, clamp(cloudHeight * 2.85, 1100, 1450) deep, sky.glsl stormLayerDepth)."""
    top = 0.0
    for fr in frames:
        U = fr['U']
        if 'ringDeckBase' in U:
            t = U['ringDeckBase'] + U.get('ringDeckThick', 280.0)
        else:
            t = U['cloudStart'] + U['cloudHeight']
        if min(max(U.get('stormCanopy', 0.0), 0.0), 1.0) > 0.0:
            t = max(t, U['cloudStart'] - STORM_BASE_DROP + min(max(U['cloudHeight'] * 2.85, 1100.0), 1450.0))
        top = max(top, t)
    return max(CASTER_MIN, top - ground_z)


def _smoothstep(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def _caster_material(name):
    import bpy
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    if hasattr(mat, 'use_transparent_shadow'):
        mat.use_transparent_shadow = True
    if hasattr(mat, 'surface_render_method'):
        mat.surface_render_method = 'DITHERED'
    nt = mat.node_tree
    nt.nodes.clear()
    N, L = nt.nodes, nt.links

    def node(kind, loc, **kw):
        n = N.new(kind)
        n.location = loc
        for k, v in kw.items():
            setattr(n, k, v)
        return n

    def vm(op, a, b=None, loc=(0, 0)):
        n = node('ShaderNodeVectorMath', loc, operation=op)
        L.new(a, n.inputs[0])
        if b is not None:
            if isinstance(b, (int, float)):
                n.inputs[3 if op == 'SCALE' else 1].default_value = b
            else:
                L.new(b, n.inputs[3 if op == 'SCALE' else 1])
        return n.outputs[1 if op in ('DOT_PRODUCT', 'LENGTH', 'DISTANCE') else 0]

    def m(op, a, b=None, loc=(0, 0)):
        n = node('ShaderNodeMath', loc, operation=op)
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                L.new(v, n.inputs[i])
        return n.outputs[0]

    geo = node('ShaderNodeNewGeometry', (-1400, 0))
    light = node('ShaderNodeCombineXYZ', (-1400, -250))
    light.name = light.label = 'eido_shadow_light'
    centre = node('ShaderNodeCombineXYZ', (-1400, -450))
    centre.name = centre.label = 'eido_shadow_centre'
    extent = node('ShaderNodeValue', (-1400, -650))
    extent.name = extent.label = 'eido_shadow_extent'
    sep_p = node('ShaderNodeSeparateXYZ', (-1150, 0))
    L.new(geo.outputs['Position'], sep_p.inputs[0])
    sep_l = node('ShaderNodeSeparateXYZ', (-1150, -250))
    L.new(light.outputs[0], sep_l.inputs[0])
    sep_c = node('ShaderNodeSeparateXYZ', (-1150, -450))
    L.new(centre.outputs[0], sep_c.inputs[0])
    # ground = P - L * (P.z - ground_z) / L.z ;  uv = (ground.xy - centre.xy) / E + 0.5
    k = m('DIVIDE', m('SUBTRACT', sep_p.outputs['Z'], sep_c.outputs['Z']), m('MAXIMUM', sep_l.outputs['Z'], 0.02))
    gx = m('SUBTRACT', sep_p.outputs['X'], m('MULTIPLY', sep_l.outputs['X'], k))
    gy = m('SUBTRACT', sep_p.outputs['Y'], m('MULTIPLY', sep_l.outputs['Y'], k))
    u = m('ADD', m('DIVIDE', m('SUBTRACT', gx, sep_c.outputs['X']), extent.outputs[0]), 0.5)
    v = m('ADD', m('DIVIDE', m('SUBTRACT', gy, sep_c.outputs['Y']), extent.outputs[0]), 0.5)
    uv = node('ShaderNodeCombineXYZ', (-400, 0))
    L.new(u, uv.inputs['X'])
    L.new(v, uv.inputs['Y'])
    tex = node('ShaderNodeTexImage', (-200, 0), interpolation='Linear', extension='EXTEND')
    tex.name = tex.label = 'eido_shadow_map'
    L.new(uv.outputs[0], tex.inputs['Vector'])
    # edge fade of the WebGPU sampler: 1 - smoothstep(0.46, 0.5, max |uv - 0.5|)
    edge = m('MAXIMUM', m('ABSOLUTE', m('SUBTRACT', u, 0.5)), m('ABSOLUTE', m('SUBTRACT', v, 0.5)))
    ramp = node('ShaderNodeMapRange', (-200, -300), interpolation_type='SMOOTHSTEP')
    ramp.inputs['From Min'].default_value = 0.46
    ramp.inputs['From Max'].default_value = 0.5
    ramp.inputs['To Min'].default_value = 1.0
    ramp.inputs['To Max'].default_value = 0.0
    L.new(edge, ramp.inputs['Value'])
    trans = node('ShaderNodeMix', (100, 0))
    trans.data_type = 'FLOAT'
    trans.inputs['A'].default_value = 1.0
    L.new(ramp.outputs['Result'], trans.inputs['Factor'])
    L.new(tex.outputs['Color'], trans.inputs['B'])
    opaque = node('ShaderNodeBsdfDiffuse', (300, 150))
    opaque.inputs['Color'].default_value = (0, 0, 0, 1)
    clear = node('ShaderNodeBsdfTransparent', (300, -50))
    mix = node('ShaderNodeMixShader', (500, 0))
    L.new(trans.outputs['Result'], mix.inputs['Fac'])
    L.new(opaque.outputs[0], mix.inputs[1])
    L.new(clear.outputs[0], mix.inputs[2])
    out = node('ShaderNodeOutputMaterial', (700, 0))
    L.new(mix.outputs[0], out.inputs['Surface'])
    return mat


def _caster_object(scene, extent):
    import bpy
    name = CASTER
    ob = bpy.data.objects.get(name)
    if ob:
        return ob
    me = bpy.data.meshes.new(name)
    h = extent * 0.5
    me.from_pydata([(-h, -h, 0), (h, -h, 0), (h, h, 0), (-h, h, 0)], [], [(0, 1, 2, 3)])
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    for attr in ('visible_camera', 'visible_diffuse', 'visible_glossy', 'visible_transmission',
                 'visible_volume_scatter'):
        if hasattr(ob, attr):
            setattr(ob, attr, False)
    if hasattr(ob, 'visible_shadow'):
        ob.visible_shadow = True
    if hasattr(ob, 'hide_probe_volume'):
        ob.hide_probe_volume = True
        ob.hide_probe_sphere = True
        ob.hide_probe_plane = True
    me.materials.append(_caster_material('eido_sky_cloud_shadow'))
    return ob


def bake_and_key(sky, frames, ground_z=0.0, caster_height=None, extent=EXTENT, log=print):
    import bpy
    from .world_nodes import _seq_image, _set_user, constant_interpolation, hold_before_first
    bk = sky.baker()
    size = sky.q['shadow']
    if caster_height is None:
        caster_height = caster_height_for(frames, ground_z)
    pat = os.path.join(sky.cache_dir, 'sky_shadow_%04d.exr')
    for fr in frames:
        U = fr['U']
        org = fr['shadow_org']
        img = bk.shadow_map(U, size, (org[0], ground_z, org[2]), extent, ground_y=ground_z)
        # tslCloudShadow: 1 - (1 - T) * cloudShadowStrength * daylight (belowDeck is 1 for receivers under the
        # caster); the scene's strength splits the sun instead (key_clear_share)
        daylight = _smoothstep(-0.005, 0.012, U['cloudLightDir'][1])
        tr = 1.0 - (1.0 - img[..., 0]) * U.get('cloudShadowStrength', 1.0) * daylight
        out = np.repeat(tr[..., None], 3, axis=2).astype(np.float32)
        write_exr(pat % fr['frame'], out, channels='RGB')
    fs, n = frames[0]['frame'], len(frames)
    hold_before_first(pat, fs)
    ob = _caster_object(sky.scene, extent)
    mat = ob.data.materials[0]
    nt = mat.node_tree
    tex = nt.nodes['eido_shadow_map']
    tex.image = _seq_image(pat % fs, fs, n, 'eido_sky_cloud_shadow_map')
    tex.image.colorspace_settings.name = 'Non-Color'
    _set_user(tex, fs, n)
    light, centre, ext = nt.nodes['eido_shadow_light'], nt.nodes['eido_shadow_centre'], nt.nodes['eido_shadow_extent']
    ext.outputs[0].default_value = extent
    if nt.animation_data:
        nt.animation_data_clear()
    if ob.animation_data:
        ob.animation_data_clear()
    for fr in frames:
        kf = fr['frame']                    # held over [f, f+1), with the map sequence (world_nodes, P6)
        Lb = P.three_to_blender(fr['U']['cloudLightDir'])
        org = fr['shadow_org']
        cb = P.three_to_blender(org)
        lz = max(Lb[2], 0.02)
        for i, a in enumerate('XYZ'):
            light.inputs[a].default_value = Lb[i]
            light.inputs[a].keyframe_insert('default_value', frame=kf)
        for i, val in enumerate((cb[0], cb[1], ground_z)):
            centre.inputs['XYZ'[i]].default_value = val
            centre.inputs['XYZ'[i]].keyframe_insert('default_value', frame=kf)
        ob.location = (cb[0] + Lb[0] * caster_height / lz, cb[1] + Lb[1] * caster_height / lz,
                       ground_z + caster_height)
        ob.keyframe_insert('location', frame=kf)
    constant_interpolation(nt)
    constant_interpolation(ob)
    log('[sky] cloud shadows: %d maps %dx%d over %.0f m, caster %.0f m up' % (n, size, size, extent, caster_height))
    if getattr(sky, 'ring', None) is not None and sky.ring.band_sun is not None:
        top = deck_top_for(frames, ground_z)
        tlocs = []
        for fr in frames:
            Lb = P.three_to_blender(fr['U']['cloudLightDir'])
            cb = P.three_to_blender(fr['shadow_org'])
            lz = max(Lb[2], 0.02)
            tlocs.append((cb[0] + Lb[0] * top / lz, cb[1] + Lb[1] * top / lz, ground_z + top))
        _band_caster(sky, ob, frames, tlocs)
        log('[sky] the band sun\'s cloud-shadow twin sits at the deck top, %.0f m up' % top)
    return ob


def _band_caster(sky, caster, frames, locs):
    """The ringworld's near band under the local deck (Eanpa's band light model weights the local clouds' shadow
    in within 2.5-5 km): a twin of the caster, sharing its mesh and its map, that only the band sun sees. It sits at
    the deck's TOP (locs, deck_top_for): every receiver below it reads its own light ray's transmittance through the
    whole deck, so the band rising through and beneath the clouds takes their shadow (a point inside the deck gets the
    whole deck's, a little dark). The map is projected along the cloud key, which is the true sun by day only, so the
    twin is keyed off while the moon is the key (the near band faces away from a sun below the horizon then)."""
    import bpy
    from .world_nodes import constant_interpolation
    name = 'eido_sky_cloud_shadow_caster_band'
    tw = bpy.data.objects.get(name)
    if tw is None:
        tw = bpy.data.objects.new(name, caster.data)
        sky.scene.collection.objects.link(tw)
        for attr in ('visible_camera', 'visible_diffuse', 'visible_glossy', 'visible_transmission',
                     'visible_volume_scatter'):
            if hasattr(tw, attr):
                setattr(tw, attr, False)
        tw.visible_shadow = True
        for attr in ('hide_probe_volume', 'hide_probe_sphere', 'hide_probe_plane'):
            if hasattr(tw, attr):
                setattr(tw, attr, True)
    # the band renders in the ring's plate scene (Ringworld.make_plate): the twin, which only its sun sees, lives there
    pc = getattr(sky.ring, 'plate_collection', None)
    if pc is not None:
        if tw.name not in pc.objects:
            pc.objects.link(tw)
        main = {sky.scene.collection} | set(sky.scene.collection.children_recursive)   # not the light-linking ones
        for c in list(tw.users_collection):
            if c in main:
                c.objects.unlink(tw)
    # the twin's material: a fresh copy of the caster's, made after this bake keyed it (so it carries this bake's
    # projection keys), with the shadow faded out by the twin object's keyed 'eido_band_caster_on' property
    old = bpy.data.materials.get('eido_sky_cloud_shadow_band')
    if old is not None:
        bpy.data.materials.remove(old)
    mat = caster.data.materials[0].copy()
    mat.name = 'eido_sky_cloud_shadow_band'
    nt = mat.node_tree
    mix = next(n for n in nt.nodes if n.bl_idname == 'ShaderNodeMixShader')
    src = mix.inputs['Fac'].links[0].from_socket
    on = nt.nodes.new('ShaderNodeAttribute')
    on.attribute_type = 'OBJECT'
    on.attribute_name = 'eido_band_caster_on'
    on.location = (300, -300)
    dark = nt.nodes.new('ShaderNodeMath')              # fac = 1 - (1 - T) * on: clear when off
    dark.operation = 'SUBTRACT'
    dark.inputs[0].default_value = 1.0
    nt.links.new(src, dark.inputs[1])
    scaled = nt.nodes.new('ShaderNodeMath')
    scaled.operation = 'MULTIPLY'
    nt.links.new(dark.outputs[0], scaled.inputs[0])
    nt.links.new(on.outputs['Fac'], scaled.inputs[1])
    fac = nt.nodes.new('ShaderNodeMath')
    fac.operation = 'SUBTRACT'
    fac.inputs[0].default_value = 1.0
    nt.links.new(scaled.outputs[0], fac.inputs[1])
    nt.links.new(fac.outputs[0], mix.inputs['Fac'])
    # the twin shares the caster's mesh (one material slot): its own material through the object's slot
    tw.material_slots[0].link = 'OBJECT'
    tw.material_slots[0].material = mat
    if tw.animation_data:
        tw.animation_data_clear()
    for fr, loc in zip(frames, locs):
        tw.location = loc
        tw.keyframe_insert('location', frame=fr['frame'])
        tw['eido_band_caster_on'] = 1.0 if fr['lights']['night_k'] <= 0.5 else 0.0
        tw.keyframe_insert('["eido_band_caster_on"]', frame=fr['frame'])
    constant_interpolation(tw)
    # only the band sun sees it; the scene sun already has the caster itself
    r = sky.ring
    blk = r.band_sun.light_linking.blocker_collection
    if blk is not None and tw.name not in blk.objects:
        blk.objects.link(tw)
        for o, co in zip(blk.objects, blk.collection_objects):
            if o == tw:
                co.light_linking.link_state = 'INCLUDE'
    sb = sky.sun.light_linking.blocker_collection
    if sb is None:
        sb = bpy.data.collections.new('eido_scene_sun_blockers')
        sky.sun.light_linking.blocker_collection = sb
    if tw.name not in sb.objects:
        sb.objects.link(tw)
    for o, co in zip(sb.objects, sb.collection_objects):
        if o == tw:
            co.light_linking.link_state = 'EXCLUDE'
    return tw


SURFACE_TYPES = {'MESH', 'CURVE', 'SURFACE', 'META', 'FONT', 'CURVES', 'POINTCLOUD', 'VOLUME'}


def _set_states(coll, objects, state):
    names = {o.name for o in objects}
    # collection_objects runs in the order of collection.objects (one light-linking entry per object)
    for o, co in zip(coll.objects, coll.collection_objects):
        if o.name in names:
            co.light_linking.link_state = state


def _mirror_links(src, name, leave_out=frozenset(), add=()):
    """The light-linking collection `name`, rebuilt as a copy of src's entries (its objects and child collections,
    each with its own state), less the objects named in leave_out, plus the (object, state) entries of add. Returns
    it, or None (and no collection) when it would hold nothing."""
    import bpy
    objs, colls = {}, {}
    if src is not None:
        # collection_objects / collection_children run in the order of objects / children (one entry each)
        for o, co in zip(src.objects, src.collection_objects):
            if o.name not in leave_out:
                objs[o.name] = (o, co.light_linking.link_state)
        for c, cc in zip(src.children, src.collection_children):
            colls[c.name] = (c, cc.light_linking.link_state)
    for o, state in add:
        objs[o.name] = (o, state)
    dst = bpy.data.collections.get(name)
    if not objs and not colls:
        if dst is not None:
            bpy.data.collections.remove(dst)
        return None
    dst = dst or bpy.data.collections.new(name)
    for o in list(dst.objects):
        dst.objects.unlink(o)
    for c in list(dst.children):
        dst.children.unlink(c)
    for o, _state in objs.values():
        dst.objects.link(o)
    for c, _state in colls.values():
        dst.children.link(c)
    for o, co in zip(dst.objects, dst.collection_objects):
        co.light_linking.link_state = objs[o.name][1]
    for c, cc in zip(dst.children, dst.collection_children):
        cc.light_linking.link_state = colls[c.name][1]
    return dst


def _remove_twin(name):
    """Remove a twin of the sun lamp, its own light data (never the lamp's) and its receiver collection; with the
    last twin, the twins' blocker collection."""
    import bpy
    twin = bpy.data.objects.get(name)
    if twin is not None:
        data = twin.data
        bpy.data.objects.remove(twin, do_unlink=True)
        if data is not None and data.name == name and data.users == 0:
            bpy.data.lights.remove(data)
    c = bpy.data.collections.get(name + '_receivers')
    if c is not None:
        bpy.data.collections.remove(c)
    blk = bpy.data.collections.get(CASTER_EXCLUDED)
    if blk is not None and not any(n in bpy.data.objects for n in (CLEAR_SUN, CLEAR_SHARE_SUN)):
        bpy.data.collections.remove(blk)


def _sun_twin(sky, name, data, caster):
    """A twin of the sky's sun lamp: `data` for its light, parented to the lamp with no offset (so it turns with every
    key the bake gives the lamp), shadowed as the lamp is but for the cloud-shadow caster. Its blockers
    (CASTER_EXCLUDED) are a copy of the lamp's own shadow linking (the ringworld's, or the scene's) with the caster
    left out."""
    import bpy
    twin = bpy.data.objects.get(name)
    if twin is None:
        twin = bpy.data.objects.new(name, data)
        sky.scene.collection.objects.link(twin)
    twin.data = data
    if twin.animation_data:
        twin.animation_data_clear()
    twin.parent = sky.sun
    twin.matrix_parent_inverse.identity()
    twin.location = (0.0, 0.0, 0.0)
    twin.rotation_mode = 'QUATERNION'
    twin.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
    twin.scale = (1.0, 1.0, 1.0)
    twin.light_linking.blocker_collection = _mirror_links(sky.sun.light_linking.blocker_collection, CASTER_EXCLUDED,
                                                          add=[(caster, 'EXCLUDE')])
    return twin


def sun_share(sky):
    """The share of the sun lamp the clouds shadow: make_sky(cloud_shadow_strength), 1 without cloud shadows."""
    return float(getattr(sky, 'cloud_shadow_strength', 1.0)) if sky.use_shadows else 1.0


def key_clear_share(sky, frames, log=print):
    """make_sky(cloud_shadow_strength=s < 1): the share of the sun no cloud takes. The bake keys the sun lamp at s of
    the palette's strength (Sky._key_sun), and this keys a twin with the rest, 1 - s (CLEAR_SHARE_SUN: its own light
    data, the lamp's colour, the same turn), whose blockers leave the caster out. Every receiver then gets
    s * T + (1 - s) = 1 - (1 - T) s of the sun, wrapCloudShadows' strength, with the transmittance map drawn as it is
    (no transparent-shadow grain over the whole shade); objects marked eido_noCloudShadow get the rest from their own
    twin (link_opt_outs, which runs first). The twin lights what the lamp lights: its receivers copy the lamp's, less
    the entries link_opt_outs made. At s = 1, or without cloud shadows, the twin is removed. Returns it, or None."""
    import bpy
    from .world_nodes import _fcurves
    caster = bpy.data.objects.get(CASTER)
    s = sun_share(sky)
    if s >= 1.0 or caster is None or sky.sun is None:
        _remove_twin(CLEAR_SHARE_SUN)
        return None
    data = bpy.data.lights.get(CLEAR_SHARE_SUN)
    if data is None or data.type != 'SUN':
        data = sky.sun.data.copy()
        data.name = CLEAR_SHARE_SUN
    for attr in ('angle', 'use_shadow', 'shadow_jitter', 'shadow_jitter_overblur', 'shadow_filter_radius',
                 'shadow_maximum_resolution', 'diffuse_factor', 'specular_factor', 'volume_factor'):
        if hasattr(data, attr) and hasattr(sky.sun.data, attr):
            setattr(data, attr, getattr(sky.sun.data, attr))
    if data.animation_data:
        data.animation_data_clear()
    for fr in frames:
        L = fr['lights']
        data.energy = L['sun_intensity'] * (1.0 - s)
        data.color = L['sun_color']
        data.keyframe_insert('energy', frame=fr['frame'])
        data.keyframe_insert('color', frame=fr['frame'])
    if data.animation_data and data.animation_data.action:
        for fc in _fcurves(data.animation_data):
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'
    twin = _sun_twin(sky, CLEAR_SHARE_SUN, data, caster)
    opted = bpy.data.collections.get(CLEAR_SUN + '_receivers')
    twin.light_linking.receiver_collection = _mirror_links(
        sky.sun.light_linking.receiver_collection, CLEAR_SHARE_SUN + '_receivers',
        leave_out={o.name for o in opted.objects} if opted is not None else frozenset())
    log('[sky] cloud shadows at strength %.2f: %s carries the other %.2f of the sun' % (s, CLEAR_SHARE_SUN, 1.0 - s))
    return twin


def link_opt_outs(sky, log=print):
    """Objects marked eido_noCloudShadow (WebGPU's userData.noCloudShadow, which wrapCloudShadows skips) are lit as if
    no cloud were overhead. A twin of the sky's sun lamp (CLEAR_SUN: the lamp's own light data, parented to it with no
    offset, so it carries every key the bake gives the lamp) lights them alone, and its blockers are the lamp's own
    with the cloud-shadow caster left out; the sun lamp's receiver collection leaves them out. Every other object
    still blocks both lamps, so their ordinary shadows stay. Without marked objects, or without cloud shadows, the
    twin and its entries are removed. Returns the twin, or None."""
    import bpy
    sun = sky.sun
    caster = bpy.data.objects.get(CASTER)
    on = sky.use_shadows and caster is not None and sun is not None
    marked = [o for o in sky.scene.objects if on and o.type in SURFACE_TYPES and o.get(OPT_OUT) and o is not caster]
    recv_name = CLEAR_SUN + '_receivers'
    twin_recv = bpy.data.collections.get(recv_name)
    before = {o.name for o in twin_recv.objects} if twin_recv is not None else set()
    recv = sun.light_linking.receiver_collection if sun is not None else None
    if recv is not None:                       # the sun lamp takes back objects no longer marked
        for name in before - {o.name for o in marked}:
            if name in recv.objects:
                recv.objects.unlink(recv.objects[name])
    if not marked:
        _remove_twin(CLEAR_SUN)
        return None
    if recv is None:
        recv = bpy.data.collections.new('eido_scene_sun_receivers')
        sun.light_linking.receiver_collection = recv
    for ob in marked:
        if ob.name not in recv.objects:
            recv.objects.link(ob)
    _set_states(recv, marked, 'EXCLUDE')
    twin = _sun_twin(sky, CLEAR_SUN, sun.data, caster)
    twin_recv = twin_recv or bpy.data.collections.new(recv_name)
    for o in list(twin_recv.objects):
        if o not in marked:
            twin_recv.objects.unlink(o)
    for ob in marked:
        if ob.name not in twin_recv.objects:
            twin_recv.objects.link(ob)
    _set_states(twin_recv, marked, 'INCLUDE')
    twin.light_linking.receiver_collection = twin_recv
    log('[sky] cloud shadows: %d object%s marked %s, lit by %s' % (len(marked), '' if len(marked) == 1 else 's', OPT_OUT,
                                                                 CLEAR_SUN))
    return twin
