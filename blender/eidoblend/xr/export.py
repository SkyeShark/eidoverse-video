"""eidoblend.xr.export: a Blender scene -> an XR bundle the kit's page plays in a headset browser.

    from eidoblend.xr.export import set_xr, survey_xr, export_xr
    set_xr(scene, street=1.0, table=0.02, start=(0, -6, 0), facing=(0, 1, 0))     # saved with the .blend
    survey_xr(scene)                                                              # what it would do; nothing changes
    rep = export_xr('work/<id>/vr')                                               # the context scene

writes, in out_dir:
    scene.glb        Blender's glTF exporter: the whole timeline as ONE glTF animation sampled every frame
                     (export_animation_mode 'SCENE': keys, NLA strips, drivers, constraints, armatures, shape keys),
                     punctual lights in Blender's own watts (lighting mode COMPAT, which three's physical lights read
                     as Blender means them: a sun's W/m2 is three's lux, a point's W / 4 pi its candela), cameras, the
                     page's xr_* custom properties as extras, materials as the exporter writes them after the bake
                     below. Two faults of the 5.2 exporter are handled: its EXT_mesh_gpu_instancing pass leaves
                     animation channels on stale node indices (_GpuInstancingChannelFix re-points them while it runs;
                     check_channels reads the GLB back), and its own instance nodes (export_gn_mesh) are left off when
                     the motion bake has made every instance an object
    world.hdr        the world, equirectangular, three's convention (eidoblend.xr.world): the page's sky and its IBL
    textures/        what bake_for_gltf baked (eidoblend.xr.materials)
    choreo.json      markers and the property tracks glTF cannot carry (eidoblend.xr.motion.property_tracks)
    scene.xr.json    the manifest the page reads: XR scales and start, view transform, lights glTF has no type for
                     (area lights -> three RectAreaLight), the page-side materials, counts and Quest budgets, warnings
    index.html       the page (eidoblend/xr/page/xr_page.html), which imports eidoverse/xr/xr_kit.js

Before the export the scene is CHANGED to fit glTF (instances become objects, deformation becomes shape keys, baked
materials replace procedural ones, area lights are hidden, keyed visibility is unkeyed): export from a built .blend you
do not save afterwards (export_cli.py opens it, exports and quits), or call export_xr last in a script.
"""
from __future__ import annotations

import datetime
import json
import math
import os
import time

import bpy

from ..common import to_three
from . import glb as G

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE_TEMPLATE = os.path.join(HERE, 'page', 'xr_page.html')
TONE = {'Standard': 'None', 'AgX': 'AgX', 'Khronos PBR Neutral': 'Neutral', 'Filmic': 'ACESFilmic', 'Raw': 'None'}
DEFAULTS = {'street': 1.0, 'table': None, 'start': None, 'facing': (0.0, 1.0, 0.0), 'eye_height': 1.6, 'name': None,
            'table_centre': None, 'shadows': False}


# ------------------------------------------------------------------------------------------- the XR settings ---

def set_xr(scene, *, street=1.0, table=None, start=None, facing=(0.0, 1.0, 0.0), eye_height=1.6, name=None,
           table_centre=None, shadows=False, landmarks=True):
    """The scene's XR settings, saved with the .blend (scene['eido_xr']), in Blender axes:
    street   metres in the room per Blender unit when you stand in it (1.0: life size)
    table    metres per unit on the table (None: the scene's extent fits about 0.6 m)
    start    the ground point you start at (None: the scene camera's ground point, else the origin)
    facing   the direction you face there; table_centre: the point at the table's centre (None: the start)
    shadows  the page casts shadows from its sun (desktop cost; off by default for the headset)
    With landmarks, Blender's VR Scene Inspection gets the same two places (eidoblend.xr.landmarks), the street one
    active, and the session the kit page's view settings (landmarks.session_settings)."""
    d = {'street': float(street), 'table': None if table is None else float(table),
         'start': None if start is None else [float(x) for x in start],
         'facing': [float(x) for x in facing], 'eye_height': float(eye_height), 'name': name,
         'table_centre': None if table_centre is None else [float(x) for x in table_centre], 'shadows': bool(shadows)}
    scene['eido_xr'] = json.dumps(d)
    if landmarks:
        try:
            from . import landmarks as LM
            if LM.ensure_addon():
                xr = get_xr(scene)
                LM.stand_at(scene, xr['start'], xr['facing'], xr['street'], xr['eye_height'], name='xr_street')
                LM.to_table(scene, xr['table_centre'], xr['table'], eye_height=xr['eye_height'], facing=xr['facing'],
                            name='xr_table')
                LM.activate(scene, 'xr_street')
                LM.session_settings(scene)
        except Exception as e:                              # the add-on missing never blocks an export
            print(f'[xr] VR landmarks not written: {e}', flush=True)
    return d


def scene_extent(scene):
    """(centre, horizontal size) of the renderable meshes' world bounds."""
    from mathutils import Vector
    lo, hi = Vector((1e18, 1e18, 1e18)), Vector((-1e18, -1e18, -1e18))
    n = 0
    for ob in scene.objects:
        if ob.type != 'MESH' or ob.hide_render:
            continue
        for c in ob.bound_box:
            w = ob.matrix_world @ Vector(c)
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
            n += 1
    if not n:
        return Vector((0, 0, 0)), 10.0
    return (lo + hi) / 2, max(hi.x - lo.x, hi.y - lo.y, 1e-3)


def get_xr(scene):
    """The XR settings with every default filled in (Blender axes)."""
    raw = scene.get('eido_xr')
    d = dict(DEFAULTS)
    if raw:
        d.update({k: v for k, v in json.loads(raw).items() if v is not None or k in ('table', 'start')})
    c, size = scene_extent(scene)
    if d.get('table') is None:
        d['table'] = round(0.6 / size, 6)
    if d.get('start') is None:
        cam = scene.camera
        d['start'] = [cam.matrix_world.translation.x, cam.matrix_world.translation.y, 0.0] if cam else [0.0, 0.0, 0.0]
    if d.get('table_centre') is None:
        d['table_centre'] = [c.x, c.y, 0.0]
    if not d.get('name'):
        d['name'] = os.path.splitext(os.path.basename(bpy.data.filepath))[0] or scene.name
    return d


# --------------------------------------------------------------------------------------------- what exports ---

def export_objects(scene):
    """The objects the export writes: renderable (not hide_render), in the view layer, not instancing sources."""
    vl = bpy.context.view_layer
    vl.update()                                       # (objects removed since the last update leave empty bases)
    names = {o.name for o in vl.objects if o is not None}
    out = []
    for ob in scene.objects:
        if ob.name not in names or ob.hide_render:
            continue
        out.append(ob)
    return out


# object types Blender's glTF exporter does not write (it writes meshes, point clouds, and curves, surfaces and text as
# meshes); metaballs are converted to a mesh here, the rest are reported
NOT_IN_GLTF = {'VOLUME': 'a volume (smoke, fire, clouds): glTF has no volumes; the page shows nothing there',
               'GREASEPENCIL': 'Grease Pencil strokes: not glTF',
               'CURVES': 'hair curves: not glTF (a mesh card version would be)',
               'SPEAKER': 'a speaker: the page has no sound',
               'LIGHT_PROBE': "a light probe: the page lights with world.hdr and the GLB's lights"}


def unsupported(objects):
    """[(object name, why)] for objects the export cannot carry: NOT_IN_GLTF types, hair particle systems, point
    clouds (written, but three draws glTF points one pixel wide)."""
    out = []
    for ob in objects:
        if ob.type in NOT_IN_GLTF:
            out.append((ob.name, NOT_IN_GLTF[ob.type]))
        elif ob.type == 'POINTCLOUD':
            out.append((ob.name, 'a point cloud: written as glTF points, which three draws one pixel wide'))
        if ob.type == 'MESH':
            for ps in getattr(ob, 'particle_systems', []):
                st = ps.settings
                if st.type == 'HAIR' and st.render_type == 'PATH':
                    out.append((ob.name, f'hair particles {ps.name!r} rendered as strands: not glTF'))
    return out


def metaballs_to_meshes(scene, objects, log=print):
    """Metaballs as meshes (the exporter skips them): each family's evaluated surface at the current frame becomes a
    mesh object with its material; the metaball stops rendering. Returns the new objects' names."""
    made = []
    metas = [o for o in objects if o.type == 'META']
    if not metas:
        return made
    dg = bpy.context.evaluated_depsgraph_get()
    for ob in metas:
        ev = ob.evaluated_get(dg)
        try:
            me = bpy.data.meshes.new_from_object(ev, depsgraph=dg)
        except RuntimeError:
            continue
        if not len(me.vertices):                       # not the family's base metaball: its surface is elsewhere
            bpy.data.meshes.remove(me)
            continue
        new = bpy.data.objects.new(f'{ob.name}_mesh', me)
        (ob.users_collection[0] if ob.users_collection else scene.collection).objects.link(new)
        new.matrix_world = ob.matrix_world
        made.append(new.name)
    for ob in metas:
        ob.hide_render = True
    if log and made:
        log(f'[xr] metaballs -> meshes: {", ".join(made)}')
    return made


def survey_xr(scene=None):
    """What export_xr would do with a scene, changing nothing: objects by type, what it cannot carry, the materials it
    would bake (and why), the motion it would convert, the animated values the page plays or cannot, the lights, the
    world and the view. Cheap (no bake, no GLB): run it before an export to see a film's XR cost."""
    from . import materials as M
    from . import motion as MO
    sc = scene or bpy.context.scene
    objs = export_objects(sc)
    types = {}
    for ob in objs:
        types[ob.type] = types.get(ob.type, 0) + 1
    meshes = [o for o in objs if o.type == 'MESH' and not o.get('xr_material')]
    mats = []
    for o in meshes:
        for m in M.used_materials(o):
            if m not in mats:
                mats.append(m)
    page_mats = {o.name: o['xr_material'] for o in objs if o.type == 'MESH' and o.get('xr_material')}
    tri, per_mesh = 0, {}
    dg = bpy.context.evaluated_depsgraph_get()
    for inst in dg.object_instances:                   # what renders now: objects and every instance they make
        ob = inst.object
        if ob.type != 'MESH' or (not inst.is_instance and ob.original.hide_render):
            continue
        key = ob.data.as_pointer()
        if key not in per_mesh:
            per_mesh[key] = len(ob.data.loop_triangles)
            if inst.is_instance:                       # instanced geometry's own materials (Geometry Nodes, particles)
                for m in ob.data.materials:
                    m = m.original if m is not None else None
                    if m is not None and m not in mats:
                        mats.append(m)
        tri += per_mesh[key]
    sv = M.survey(mats)
    det = MO.detect(sc, objs)
    props = MO.animated_properties(sc)
    xr = get_xr(sc)
    return {
        'scene': sc.name, 'frames': [sc.frame_start, sc.frame_end], 'fps': sc.render.fps / sc.render.fps_base,
        'objects': types, 'unsupported': unsupported(objs),
        'materials': {'total': len(sv), 'to_bake': {k: v['lost'] for k, v in sv.items()
                                                    if v['lost'] and M.mtoon(bpy.data.materials.get(k)) is None},
                      'mtoon': [m.name for m in mats if M.mtoon(m) is not None],
                      'kinds': sorted({v['kind'] for v in sv.values()}), 'page_materials': page_mats},
        'motion': {'moving_instances': [o.name for o in det['instances']],
                   'still_instances': [o.name for o in det['still_instances']],
                   'deforming': [(o.name, why) for o, why in det['deforming']],
                   'skinned': [o.name for o in det['skinned']]},
        'animated': sorted({(k, getattr(o, 'name', '?'), p) for k, o, p in props}),
        'lights': sorted((o.name, o.data.type) for o in objs if o.type == 'LIGHT'),
        'world': sc.world.name if sc.world else None,
        'view': (sc.view_settings.view_transform, sc.view_settings.look, sc.view_settings.exposure),
        'triangles_now': tri, 'xr': xr,
    }


def _rect_lights(scene, objects):
    """Area lights as three RectAreaLight data (glTF has no area light): radiance L = P / (pi A), measured."""
    out = []
    for ob in objects:
        if ob.type != 'LIGHT' or ob.data.type != 'AREA':
            continue
        li = ob.data
        sx, sy, sz = ob.matrix_world.to_scale()
        w = li.size * abs(sx)
        h = (li.size_y if li.shape in ('RECTANGLE', 'ELLIPSE') else li.size) * abs(sy)
        if li.shape in ('DISK', 'ELLIPSE'):
            area = math.pi * w * h / 4
            w, h = w * math.sqrt(math.pi / 4), h * math.sqrt(math.pi / 4)        # a rectangle of the same area
        else:
            area = w * h
        power = li.energy * (2 ** getattr(li, 'exposure', 0.0))
        col = list(li.color)
        if getattr(li, 'use_temperature', False):
            tc = li.temperature_color
            col = [col[0] * tc[0], col[1] * tc[1], col[2] * tc[2]]
        m = ob.matrix_world
        p = m.translation
        q = m.to_quaternion()
        out.append({'name': ob.name, 'position': list(to_three(*p)), 'quaternion': [q.x, q.z, -q.y, q.w],
                    'width': w, 'height': h, 'intensity': power / (math.pi * max(area, 1e-9)), 'color': col,
                    'spread': math.degrees(getattr(li, 'spread', math.pi))})
    return out


def _fallback_background(scene):
    """The world as one linear colour (its radiance): a Background node's colour x strength when they are constants,
    else the world's viewport colour. The page's background, and its ambient light when there is no world.hdr."""
    w = scene.world
    if w is None:
        return [0.0, 0.0, 0.0]
    try:
        bg = next(n for n in w.node_tree.nodes if n.type == 'BACKGROUND')
        if not bg.inputs['Color'].is_linked:
            k = 1.0 if bg.inputs['Strength'].is_linked else float(bg.inputs['Strength'].default_value)
            return [c * k for c in list(bg.inputs['Color'].default_value)[:3]]
    except Exception:
        pass
    return list(w.color)[:3]


class _GpuInstancingChannelFix:
    """Blender 5.2's glTF exporter collapses still instances into EXT_mesh_gpu_instancing
    (GlTF2Exporter.manage_gpu_instancing_nodes) and slides the scene's nodes, children and skin joints to the shorter
    node list, but not the animation channels' target nodes: a channel on a node listed after the removed ones then
    points at another node, or past the end (found here: a spinning cube's rotation landed 40 nodes too far after 40
    rocks collapsed). While this is active, each channel is re-pointed at its own node object after the collapse."""

    def __enter__(self):
        self.cls = self.orig = None
        try:
            from io_scene_gltf2.blender.exp import exporter as EX
        except ImportError:
            return self
        cls = getattr(EX, 'GlTF2Exporter', None)
        orig = getattr(cls, 'manage_gpu_instancing_nodes', None)
        if orig is None:
            return self

        def fixed(exp, export_settings):
            gltf = getattr(exp, '_GlTF2Exporter__gltf', None)
            if gltf is None:
                return orig(exp, export_settings)
            nodes = list(gltf.nodes or [])
            held = [(ch, nodes[ch.target.node]) for a in (gltf.animations or []) for ch in a.channels
                    if isinstance(ch.target.node, int) and 0 <= ch.target.node < len(nodes)]
            orig(exp, export_settings)
            index = {id(n): i for i, n in enumerate(gltf.nodes or [])}
            for ch, n in held:
                if id(n) in index:
                    ch.target.node = index[id(n)]

        self.cls, self.orig = cls, orig
        cls.manage_gpu_instancing_nodes = fixed
        return self

    def __exit__(self, *exc):
        if self.cls is not None:
            self.cls.manage_gpu_instancing_nodes = self.orig


def check_channels(g, scene, objects):
    """[problems] of an exported GLB's animation: channels on nodes that do not exist, and objects that move in Blender
    (their world matrix differs between the first, middle and last frames) with no channel on their node (the
    exporter's own index slips show up here)."""
    js = g.json
    nodes = js.get('nodes', [])
    targeted = set()
    out = []
    for a in js.get('animations', []):
        for ch in a['channels']:
            i = ch['target'].get('node')
            if i is None or i >= len(nodes):
                out.append(f"a {ch['target'].get('path')} channel targets node {i}, past the {len(nodes)} nodes")
            else:
                targeted.add(nodes[i].get('name'))
    names = {nd.get('name') for nd in nodes}

    def own_motion(o):             # keys, drivers or NLA on its own transform, or constraints (not a moving parent)
        ad = o.animation_data
        tr = ('location', 'rotation_euler', 'rotation_quaternion', 'rotation_axis_angle', 'scale')
        return bool(o.constraints) or (ad is not None and (
            any(fc.data_path in tr for fc in _bl.fcurves(o)) or any(d.data_path in tr for d in ad.drivers)
            or any(t.strips for t in ad.nla_tracks)))
    from . import _bl
    cands = [o for o in objects if o.type in ('MESH', 'EMPTY', 'CAMERA', 'LIGHT') and o.name in names
             and o.name not in targeted and o.parent_type != 'BONE' and own_motion(o)]
    if cands:
        keep = scene.frame_current
        seen = {o.name: [] for o in cands}
        try:
            for f in sorted({scene.frame_start, (scene.frame_start + scene.frame_end) // 2, scene.frame_end}):
                scene.frame_set(f)
                for o in cands:
                    seen[o.name].append(tuple(round(x, 4) for row in o.matrix_world for x in row))
        finally:
            scene.frame_set(keep)
        out += [f'{n} moves in Blender but no channel targets its node' for n, ms in seen.items() if len(set(ms)) > 1]
    return out


def write_page(out_dir, manifest_name='scene.xr.json', template=PAGE_TEMPLATE):
    """index.html in out_dir: the page template, reading `manifest_name` beside it."""
    with open(template, encoding='utf-8') as f:
        html = f.read()
    html = html.replace("'./scene.xr.json'", f"'./{manifest_name}'")
    p = os.path.join(out_dir, 'index.html')
    with open(p, 'w', encoding='utf-8', newline='\n') as f:
        f.write(html)
    return p


# ------------------------------------------------------------------------------------------------ the export ---

def export_xr(out_dir, scene=None, *, name='scene', bake_materials=True, texel_density=24.0, max_texture=2048,
              bake_motion=True, motion_step=1, max_shape_keys=48, world=True, world_width=2048, world_frame=None,
              world_samples=32, image_format='AUTO', compress=None, cameras=True, page=True, choreo_names=(),
              log=print):
    """Export `scene` for an XR page into out_dir (see the module doc). Returns the manifest (a dict) with
    'report': what was baked, converted, skipped, and the GLB's own counts read back."""
    t0 = time.time()
    sc = scene or bpy.context.scene
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    keep_path = bpy.data.filepath
    from . import _bl
    from . import materials as M
    from . import motion as MO
    xr = get_xr(sc)
    fps = sc.render.fps / sc.render.fps_base
    rep = {'motion': {}, 'materials': {}, 'lights': {}, 'warnings': []}
    keep_frame = sc.frame_current
    # 0. what glTF cannot hold at all (reported), metaballs (converted), the cast's MToon outlines (inverted hulls the
    # page cannot draw, and would leave standing at the rest pose)
    objs = export_objects(sc)
    for n, why in unsupported(objs):
        rep['warnings'].append(f'{n}: {why}')
    rep['metaballs'] = metaballs_to_meshes(sc, objs, log=log)
    objs = export_objects(sc)
    rep['mtoon_outlines_off'] = M.drop_mtoon_outlines(objs, log=log)
    rep['mtoon'] = M.convert_mtoon(objs, log=log)            # a conversion, not a bake: done with or without bakes
    if rep['mtoon']:
        rep['warnings'].append(f"{len(rep['mtoon'])} MToon material(s) drawn as a PBR stand-in (base colour, normal, "
                               'emission, alpha); the toon ramp is not glTF' +
                               (f", outlines off on {len(rep['mtoon_outlines_off'])} mesh(es)"
                                if rep['mtoon_outlines_off'] else ''))
    # 1. motion glTF cannot carry
    if bake_motion:
        det = MO.detect(sc, objs)
        for src in det['instances'] + det['still_instances']:
            still = src in det['still_instances']
            r = MO.instances_to_objects(src, sc, step=motion_step, still=still, log=log)
            rep['motion'][src.name] = {k: v for k, v in r.items() if k != 'objects'}
            if r['dropped']:
                rep['warnings'].append(f"{src.name}: {r['dropped']} {'still' if still else 'moving'} instances over "
                                       f"the cap ({r['instances']} exported) are not in the GLB")
        for ob, why in det['deforming']:
            try:
                r = MO.deform_to_shape_keys(ob, sc, step=motion_step, max_keys=max_shape_keys, log=log)
                rep['motion'][ob.name] = {'morph_targets': r['keys'], 'step': r['step'], 'vertices': r['vertices']}
            except RuntimeError as e:
                rep['warnings'].append(str(e))
        rep['motion']['skinned'] = [o.name for o in det['skinned']]
    sc.frame_set(keep_frame)
    objs = export_objects(sc)
    # 2. the tracks glTF cannot carry (before lights are touched)
    props = MO.animated_properties(sc)
    tracks = None
    if props or choreo_names or sc.timeline_markers:
        from . import choreo
        tracks = choreo.write(sc, os.path.join(out_dir, 'choreo.json'), names=choreo_names, step=2)
        rep['tracks'] = {'lights': sorted(tracks['props']['lights']), 'emission': sorted(tracks['props']['emission']),
                         'visible': sorted(tracks['props']['visible']), 'markers': len(tracks['markers'])}
        for k, o, p in props:
            if k in ('camera', 'world') or (k == 'material' and MO.emission_socket(o, p) is None):
                rep['warnings'].append(f'{k} {getattr(o, "name", "?")}.{p} is animated: the page does not play it')
    # objects whose visibility is keyed go into the GLB shown; the page's visibility track hides them in time
    for k, o, p in props:
        if k == 'visibility':
            for fc in _bl.fcurves(o):
                if fc.data_path in ('hide_render', 'hide_viewport'):
                    fc.mute = True
            o.hide_render = False
            o.hide_viewport = False
    objs = export_objects(sc)
    # 3. materials
    meshes = [o for o in objs if o.type == 'MESH']
    if bake_materials:
        tex_dir = os.path.join(out_dir, 'textures')
        r = M.bake_for_gltf(meshes, tex_dir, texel_density=texel_density, max_size=max_texture, log=log)
        rep['materials'] = r
    else:
        rep['materials'] = {'survey': M.survey({s.material for o in meshes for s in o.material_slots if s.material})}
    # 4. lights: area -> the manifest (RectAreaLight); hide them so the exporter does not warn about them
    rect = _rect_lights(sc, objs)
    for ob in objs:
        if ob.type == 'LIGHT' and ob.data.type == 'AREA':
            ob.hide_render = True
    rep['lights'] = {'rect': [r['name'] for r in rect],
                     'punctual': [o.name for o in objs if o.type == 'LIGHT' and o.data.type != 'AREA']}
    for r in rect:
        if r['spread'] < 179.0:
            rep['warnings'].append(f"area light {r['name']}: spread {r['spread']:.0f} deg is drawn at 180 "
                                   '(three RectAreaLight has no spread)')
    # 5. the world
    world_info = None
    if world and sc.world is not None:
        from . import world as W
        wf = world_frame if world_frame is not None else sc.frame_start
        wi = W.bake_world_equirect(sc, os.path.join(out_dir, 'world.hdr'), width=world_width, samples=world_samples,
                                   frame=wf, log=log)
        world_info = {'equirect': 'world.hdr', 'frame': wf, 'mean': wi['mean'], 'max': wi['max']}
    # 6. the GLB
    glb_path = os.path.join(out_dir, f'{name}.glb')
    any_normal = any('normal' in v.get('images', {}) for v in rep['materials'].get('baked', {}).values())
    # export_gn_mesh only without the motion bake: with it every instance is an object already, and the exporter's
    # instance nodes would double what it meshes itself (curves, text: Blender 5.2 lists their surface as instances)
    # and break its own slide-to-zero pass (5.2's get_driver_on_shapekey reads a None object on an instance node)
    kw = dict(filepath=glb_path, export_format='GLB', check_existing=False, use_renderable=True, use_active_scene=True,
              export_apply=True, export_yup=True, export_extras=True, export_cameras=bool(cameras),
              export_lights=True, export_import_convert_lighting_mode='COMPAT', export_materials='EXPORT',
              export_image_format=image_format, export_texcoords=True, export_normals=True,
              export_tangents=any_normal, export_animations=True, export_animation_mode='SCENE',
              export_anim_scene_split_object=False, export_frame_range=True, export_force_sampling=True,
              export_frame_step=int(motion_step), export_anim_slide_to_zero=True, export_bake_animation=True,
              export_optimize_animation_size=True, export_skins=True, export_morph=True, export_morph_normal=True,
              export_morph_animation=True, export_gpu_instances=True, export_gn_mesh=not bake_motion,
              export_vertex_color='MATERIAL', will_save_settings=False)
    if compress == 'draco':
        kw.update(export_draco_mesh_compression_enable=True)
    elif compress == 'meshopt':
        kw.update(export_meshopt_compression_enable=True)
    sc.frame_set(sc.frame_start)
    with _GpuInstancingChannelFix():
        bpy.ops.export_scene.gltf(**kw)
    sc.frame_set(keep_frame)
    if not os.path.exists(glb_path):
        raise RuntimeError(f'export_xr: the glTF exporter wrote nothing at {glb_path}')
    g = G.read(glb_path)
    rep['channel_problems'] = check_channels(g, sc, export_objects(sc))
    for p in rep['channel_problems']:
        rep['warnings'].append(f'GLB animation: {p}')
    saved = G.strip_extras(g, keep=('xr_',))                 # only the page's own extras ride along
    if saved > 0:
        G.write(g, glb_path)
        g = G.read(glb_path)
        rep['extras_stripped_bytes'] = saved
    summ = G.summary(g)
    # 7. the manifest + the page
    page_mats = {}
    for ob in objs:
        if ob.get('xr_material'):
            try:
                params = json.loads(ob.get('xr_params', '{}'))
            except ValueError:
                params = {}
            page_mats[ob.name] = {'kind': ob['xr_material'], 'params': params}
    vt = sc.view_settings.view_transform
    if vt not in TONE:
        rep['warnings'].append(f'view transform {vt!r}: the page uses AgX')
    if sc.view_settings.look not in ('None', 'AgX - Base Contrast', ''):
        rep['warnings'].append(f'look {sc.view_settings.look!r}: the page has no looks (AgX base)')
    st = xr['start']
    tc = xr['table_centre']
    man = {
        'name': xr['name'], 'glb': os.path.basename(glb_path), 'fps': fps, 'frame_start': sc.frame_start,
        'frame_end': sc.frame_end, 'duration': (sc.frame_end - sc.frame_start) / fps, 'loop': True,
        'street': xr['street'], 'table': xr['table'], 'eye_height': xr['eye_height'],
        'start': list(to_three(st[0], st[1], st[2] if len(st) > 2 else 0.0)),
        'facing': list(to_three(*xr['facing'])),
        'table_centre': list(to_three(tc[0], tc[1], tc[2] if len(tc) > 2 else 0.0)),
        'shadows': xr['shadows'],
        'view': {'transform': vt, 'look': sc.view_settings.look, 'exposure': sc.view_settings.exposure,
                 'tone_mapping': TONE.get(vt, 'AgX')},
        'world': world_info, 'background': _fallback_background(sc),
        'rect_lights': rect, 'page_materials': page_mats,
        'tracks': 'choreo.json' if tracks is not None else None,
        'camera': sc.camera.name if sc.camera else None,
        'cameras': [c['name'] for c in summ['cameras']],
        'compression': compress,
        'counts': {k: summ[k] for k in ('nodes', 'mesh_nodes', 'triangles', 'draws', 'texture_mb_gpu', 'duration',
                                        'skins', 'joints', 'morph_targets', 'gpu_instanced_nodes', 'bytes')},
        'quest': summ['quest'], 'extensions': summ['extensions_used'],
        'source': {'blend': keep_path, 'scene': sc.name, 'exported': datetime.datetime.now().isoformat(
            timespec='seconds'), 'blender': bpy.app.version_string},
        'warnings': rep['warnings'],
    }
    with open(os.path.join(out_dir, f'{name}.xr.json'), 'w', encoding='utf-8') as f:
        json.dump(man, f, indent=1, default=str)
    if page:
        write_page(out_dir, f'{name}.xr.json')
    man['report'] = rep
    man['summary'] = summ
    man['seconds'] = round(time.time() - t0, 2)
    if log:
        log(f"[xr] {glb_path}: {summ['triangles']} triangles, {summ['draws']} draws, {summ['duration']:.2f} s of "
            f"animation, {len(summ['materials'])} materials, {len(summ['lights'])} lights + {len(rect)} rect, "
            f"Quest {summ['quest']} ({man['seconds']} s)")
        for w in rep['warnings']:
            log(f'[xr] warning: {w}')
    return man
