"""eidoblend.characters.robotics.inspector: robotics/inspector/viewer.js, as a Blender inspector scene.

The WebGPU inspector is a browser page (serve_inspector.py on localhost:8989): the catalog in a list, the robot in the
studio, a motion selector with play / time, colour pickers, wireframe, part picking, the UV split view, triangle counts,
the ports list, joint sliders and, on the G430 machines, the fabrication process with its stock, timing and workpiece
controls. A browser page has no place in a Blender port; the same tool is a scene you open, driven by an Inspector
(the page's state and its window.roboticsInspector handle):

    from eidoblend.characters.robotics.inspector import inspector_scene
    insp = inspector_scene('payloads/arm_hand')                        # clip: the robot's first, keyed over 20 s
    insp = inspector_scene('humanoid', clip='run-circle', wireframe=True, part='LG rolling foot carrier')
    insp = inspector_scene('arm', joints=True)                         # manual mode: one slider per joint
    insp = inspector_scene('fdm')                                      # a machine with a tool opens on 'process'
    insp.set_time(4.0); insp.pick(0.5, 0.45); insp.set_wireframe(True)
    bpy.ops.wm.save_as_mainfile(filepath='arm_inspector.blend')

    inspector_scene(model='payloads/arm_hand', clip=None, duration=20, joints=False, wireframe=False, reference=False,
                    part='', uv=None, primary=None, accent=None, scene=None, fps=24, resolution=(1280, 720),
                    process_options=None) -> Inspector
        model / clip / duration (20 s, the inspector's time slider) / primary / accent (the colour pickers)
        joints=True     manual mode: rig.rig_joints, the joint sliders as keyable custom properties on the robot's empty
        wireframe       the "Wireframe" toggle: every kit mesh with a wire overlay (#132e37 at 65 %), its own collection
        reference       the "Hand grasp cylinder" toggle: the grasped cylinders (made always, hidden unless on)
        part            the part picker: its triangle count, and the UV split view limited to its triangles
        uv=path         the UV split view: draw_uv() writes the map with the UV layout drawn over it
        process_options extra options for the fabrication job (e.g. cache_dir for the rotary stock, resolution)

    Inspector (also a dict: 'robot', 'camera', 'studio', 'clip', 'stats', 'status', 'ports', 'parts',
    'part_triangles', 'uv', 'wire', 'references', 'joints', 'target', 'job', 'time'; the status line and the
    ports list are also on the scene as custom properties 'inspector_status' / 'inspector_ports'):
        load(model)                 the asset list (asset_list(): the catalog without the 'rotors_*' variants):
                                    another catalog model in the same studio (the old one disposed)
        clips()                     the motion list ('process' first on a machine with a tool, as there)
        set_motion(clip)            setMotion / the motion list: keys the clip over the time range (or makes the job)
        set_time(t) / reset()       setTime / the time slider (the keyed timeline, sub-frames included) / Reset
        play(on=True)               Play: the scene's playback range is the clip's 20 s (or the job's duration)
        fit() / frame_work()        the Frame and "Inspect workpiece" buttons
        set_colors(primary, accent) the Body / Accent pickers; set_filament_color(c) the Filament picker;
                                    pickers() their current values ('#rrggbb')
        set_wireframe(on) / set_reference(on)        the two toggles
        pick(x, y) -> part          a click on the image (x, y in 0..1 from the top left): the part under it
        pick_part(name)             the part list: the selection and its 'N selected triangles'
        draw_uv(path, batch=None, channel=None, material=None)       the UV split view of the selection
        set_joint(name, value)      a joint slider (manual mode: the rig's sliders drive the modules)
        set_stock(material=None, preset=None, length=None, width=None, height=None)   the stock controls
        set_timing('lapse' | 'physical')             the process playback select (18 s / 32 s rotary, or the job's own
                                    time, keyed frame by frame: refused past MAX_KEYED_FRAMES, 25 min at 24 fps; the
                                    pocket mill is 20 min, the print 15 min, the relief 7.8 hours)
        set_source(source, name)    setSource: a workpiece for the process (a bpy Object / Mesh / Collection, or a
                                    manufacturing sample name: 'handle', 'bracket', 'ring'; None: the demonstration)
        process_state()             the processState line; dispose()

The camera fit is the inspector's: for walk, drive-circle, flight and the runs, the box over the clip sampled every
0.5 s from 0 to 20 s; otherwise the current pose; frameCamera with margin 1.08 from (.9, .55, 1.5) (from the left,
(-.9, .55, 1.5), when the robot has a filament), over the visible meshes without the overlays. The inspector imports
eidoblend.fabrication before it loads (viewer.js imports fabrication.js), so a dispenser loads with its live filament
and its first motion, 'filament-feed', pays the strand out. The process entries
make their job with eidoblend.fabrication (print, mill, carve, rotary_carve: the fabrication port's), with the
inspector's own settings: a 6 mm lathe ring printed at 40 mm with 25 % infill, a pocket mill, the relief, the rotary
sample; time lapse 18 s (32 s on the rotary machine).
"""

from __future__ import annotations

import math
import os

import bpy
import numpy as np
from mathutils import Vector

from .kit import make_robot
from .studio import frame_camera, make_camera, studio, world_box

SWEEP_CLIPS = ('walk', 'drive-circle', 'flight')
STOCK_MATERIALS = ('aluminum', 'brass', 'steel', 'wood', 'plywood')
STOCK_PRESETS = {'140,36,36': (140, 36, 36), '100,24,28': (100, 24, 28), '180,44,50': (180, 44, 50)}
SOURCE_SAMPLES = ('handle', 'bracket', 'ring')
MAX_KEYED_FRAMES = 36000      # 25 min at 24 fps: physical timing keys every frame (the relief alone is 7.8 hours)


def _source_group():
    """a Geometry Nodes group that outputs another object's EVALUATED mesh in its own coordinates (Object Info,
    'ORIGINAL'): the overlay of a procedural mesh (a fabrication tube or strand, deformed by its Geometry Nodes inputs)
    follows the deformed surface, as viewer.js gives such a wire the mesh's own positionNode"""
    ng = bpy.data.node_groups.get('inspector wire source')
    if ng is not None:
        return ng
    ng = bpy.data.node_groups.new('inspector wire source', 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Source', in_out='INPUT', socket_type='NodeSocketObject')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    gi = ng.nodes.new('NodeGroupInput')
    go = ng.nodes.new('NodeGroupOutput')
    oi = ng.nodes.new('GeometryNodeObjectInfo')
    oi.transform_space = 'ORIGINAL'
    ng.links.new(gi.outputs['Source'], oi.inputs['Object'])
    ng.links.new(oi.outputs['Geometry'], go.inputs['Geometry'])
    return ng


def wire_overlay(robot, visible=True, colour='#132e37', opacity=0.65, thickness=None):
    """the inspector's wireframe: a linked copy of every kit mesh with a Wireframe modifier, an unlit translucent
    line colour, in a 'wire|<robot>' collection; a mesh deformed by Geometry Nodes (a registered fabrication tube)
    gets an overlay that reads its evaluated surface first. Returns the overlay objects."""
    from .materials import to_linear
    col = bpy.data.collections.new('wire|' + robot.group.name)
    robot.collection.children.link(col)
    mat = bpy.data.materials.new('inspector wire')
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = tuple(to_linear(colour)) + (1.0,)
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix = nt.nodes.new('ShaderNodeMixShader')
    mix.inputs['Fac'].default_value = opacity
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    mat.surface_render_method = 'BLENDED'
    if thickness is None:
        lo, hi = world_box([robot.group])
        thickness = max(0.0002, (hi - lo).length * 0.0006)
    made = []
    for o in robot.meshes():
        if o.get('overlay'):
            continue
        w = bpy.data.objects.new(o.name + '|wire', o.data)
        col.objects.link(w)
        w.parent = o
        w.matrix_parent_inverse.identity()
        if any(md.type == 'NODES' for md in o.modifiers):
            src = w.modifiers.new('source', 'NODES')
            src.node_group = _source_group()
            item = next(i for i in src.node_group.interface.items_tree
                        if getattr(i, 'in_out', None) == 'INPUT' and i.name == 'Source')
            getattr(src.properties.inputs, item.identifier).value = o
            w['procedural_source'] = True
        m = w.modifiers.new('wire', 'WIREFRAME')
        m.thickness = thickness
        m.use_replace = True
        m.use_even_offset = False
        m.material_offset = 0
        for s in w.material_slots:                       # the mesh is shared: the overlay's material is per object
            s.link = 'OBJECT'
            s.material = mat
        w.visible_shadow = False
        w.hide_render = w.hide_viewport = not visible
        w['overlay'] = True
        made.append(w)
    robot.extra_objects.extend(made)
    return made


def part_triangles(robot, part):
    """how many triangles part `part` owns (the inspector's 'N selected triangles')"""
    return sum(sum(1 for p in robot.part_for_face.get(o.name) or () if p == part) for o in robot.meshes()
               if not o.get('overlay'))


def map_choices(robot):
    """the inspector's map list: '<batch> / <channel>' for every metadata texture binding, else
    '<material> / <channel>' for the robot's materials"""
    tb = robot.report.get('texture_bindings') or {}
    if tb:
        return [(b, c) for b, chans in tb.items() for c in chans]
    out = []
    for m in robot.materials.materials:
        if m.use_nodes:
            for n in m.node_tree.nodes:
                if n.type == 'TEX_IMAGE' and n.image is not None:
                    out.append(('@' + m.name, n.label or n.image.name))
    return out


def draw_uv(robot, path, part='', material=None, size=1024, background=True, batch=None, channel=None):
    """the inspector's UV split view: a map with the UV triangles drawn over it in #f180a1 (limited to `part`'s
    triangles when given) and the 0..1 frame in #a3c6c6, written to `path` (PNG). The map: a metadata texture binding
    (batch, channel: the triangles of the meshes of that batch), or a material's base-colour map (the triangles that
    use the material; the first kit material by default). Returns {'triangles', 'material', 'map'}."""
    mats = [m for m in robot.materials.materials if m.use_nodes]
    binding = None
    if batch is not None:
        binding = ((robot.report.get('texture_bindings') or {}).get(batch) or {}).get(channel or 'base')
        if binding is None:
            raise KeyError(f'no texture binding {batch} / {channel}; choices: {map_choices(robot)}')
        material = None
    elif material is None:
        material = next((m for m in mats if any(n.type == 'TEX_IMAGE' and n.image for n in m.node_tree.nodes)),
                        mats[0] if mats else None)
    img = np.zeros((size, size, 4), np.float32)
    img[..., :3] = (0x11 / 255, 0x1a / 255, 0x1e / 255)
    img[..., 3] = 1.0
    src = None
    if background and binding is not None:
        from . import io as kio
        uri = binding if isinstance(binding, str) else binding['uri']
        meta_dir = os.path.dirname(os.path.join(kio.ROOT, robot.entry['metadata']))
        src = kio.shared_image(os.path.normpath(os.path.join(meta_dir, uri)), channel in ('base', 'fixed'))
    if background and material is not None:
        b = next((n for n in material.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        cand = [n for n in material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image is not None]
        fixed = [n for n in cand if n.label == 'recolor fixed']
        base = [n for n in cand if b is not None and b.inputs['Base Color'].is_linked
                and any(lk.from_node == n for lk in b.inputs['Base Color'].links)]
        pick_n = (fixed or base or cand or [None])[0]
        if pick_n is not None:
            src = pick_n.image
    if src is not None:
        w, h = src.size
        if w and h:
            px = np.empty(w * h * 4, np.float32)
            src.pixels.foreach_get(px)
            px = px.reshape(h, w, 4)
            ys = (np.arange(size) * h // size).clip(0, h - 1)
            xs = (np.arange(size) * w // size).clip(0, w - 1)
            img = px[ys][:, xs].copy()
            img[..., 3] = 1.0
    segs = []
    count = 0
    for o in robot.meshes():
        if o.get('overlay'):
            continue
        if material is not None and material.name not in [s.material.name for s in o.material_slots if s.material]:
            continue
        if batch is not None and str(o.get('batch')) != batch:
            continue
        me = o.data
        uvl = me.uv_layers.active
        if uvl is None:
            continue
        faces = robot.part_for_face.get(o.name)
        nL = len(me.loops)
        uv = np.empty(nL * 2, np.float32)
        uvl.data.foreach_get('uv', uv)
        uv = uv.reshape(-1, 2)
        ls = np.empty(len(me.polygons), np.int32)
        lt = np.empty(len(me.polygons), np.int32)
        me.polygons.foreach_get('loop_start', ls)
        me.polygons.foreach_get('loop_total', lt)
        sel = np.ones(len(me.polygons), bool)
        if part:
            sel = np.array([p == part for p in faces], bool) if faces else np.zeros(len(me.polygons), bool)
        if material is not None:
            mi = np.empty(len(me.polygons), np.int32)
            me.polygons.foreach_get('material_index', mi)
            slot = [i for i, s in enumerate(o.material_slots) if s.material == material]
            sel &= np.isin(mi, slot)
        for f in np.nonzero(sel)[0]:
            pts = uv[ls[f]:ls[f] + lt[f]]
            segs.append(np.stack([pts, np.roll(pts, -1, axis=0)], axis=1))
            count += 1
    line = np.array((0xf1 / 255, 0x80 / 255, 0xa1 / 255, 1.0), np.float32)
    if segs:
        s = np.concatenate(segs) * (size - 1)
        n = int(np.ceil(np.abs(s[:, 1] - s[:, 0]).max(axis=1).max())) + 1 if len(s) else 1
        n = min(n, 2 * size)
        t = np.linspace(0, 1, n)
        for chunk in range(0, len(s), 20000):
            c = s[chunk:chunk + 20000]
            p = c[:, :1, :] + (c[:, 1:2, :] - c[:, :1, :]) * t[None, :, None]
            x = np.clip(np.round(p[..., 0]).astype(int), 0, size - 1)
            y = np.clip(np.round(p[..., 1]).astype(int), 0, size - 1)
            img[y.ravel(), x.ravel()] = img[y.ravel(), x.ravel()] * 0.45 + line * 0.55
    edge = np.array((0xa3 / 255, 0xc6 / 255, 0xc6 / 255, 1.0), np.float32)
    img[0, :], img[-1, :], img[:, 0], img[:, -1] = edge, edge, edge, edge
    out = bpy.data.images.new('inspector uv', size, size, alpha=False)
    if src is not None and src.colorspace_settings.name != 'sRGB':
        out.colorspace_settings.name = 'Non-Color'
    out.pixels.foreach_set(img.ravel())
    out.filepath_raw = path
    out.file_format = 'PNG'
    out.save()
    bpy.data.images.remove(out)
    return {'triangles': count, 'material': material.name if material else None, 'map': src.name if src else None}


def fit(robot, camera, clip=None, margin=1.08):
    """the inspector's fit(): the clip's sweep for walk / drive-circle / flight / runs, else the pose, over the
    visible meshes without the overlays (traverseVisible)"""
    boxes = []
    if clip and (clip in SWEEP_CLIPS or clip.startswith('run-')):
        t = 0.0
        while t <= 20.0:
            robot.sample(clip, t)
            boxes.append(world_box([robot.group], visible_only=True))
            t += 0.5
        robot.sample(clip, 0.0)
    else:
        boxes.append(world_box([robot.group], visible_only=True))
    direction = (-0.9, -1.5, 0.55) if robot.filament is not None else (0.9, -1.5, 0.55)
    return frame_camera(camera, boxes, direction=direction, margin=margin)


def camera_ray(camera, x, y, scene=None):
    """the world ray through (x, y) of the camera's image, 0..1 from the top left (Raycaster.setFromCamera of the
    click's normalised device coordinates) -> (origin, direction)"""
    sc = scene or bpy.context.scene
    tr, br, bl, tl = [Vector(v) for v in camera.data.view_frame(scene=sc)]
    p = tl.lerp(tr, x).lerp(bl.lerp(br, x), y)                    # camera space, on the frame plane
    M = camera.matrix_world
    if camera.data.type == 'ORTHO':
        origin = M @ Vector((p.x, p.y, 0.0))
        return origin, (M.to_3x3() @ Vector((0.0, 0.0, -1.0))).normalized()
    origin = M.translation.copy()
    return origin, ((M @ p) - origin).normalized()


def pick(robot, camera, x, y, scene=None):
    """the inspector's click: the nearest kit mesh (overlays and hidden meshes excluded) under (x, y) of the camera's
    image and the part that owns the hit triangle -> (part or '', {'object', 'face', 'location', 'distance'} or None)"""
    bpy.context.view_layer.update()
    origin, d = camera_ray(camera, x, y, scene)
    best = None
    dg = bpy.context.evaluated_depsgraph_get()
    for o in robot.meshes():
        if o.get('overlay') or o.hide_render or o.hide_viewport or not o.visible_get():
            continue
        mi = o.matrix_world.inverted()
        lo = mi @ origin
        ld = (mi.to_3x3() @ d).normalized()
        ok, loc, _nor, face = o.ray_cast(lo, ld, depsgraph=dg)
        if not ok:
            continue
        w = o.matrix_world @ loc
        dist = (w - origin).length
        if best is None or dist < best['distance']:
            best = {'object': o, 'face': face, 'location': w, 'distance': dist}
    if best is None:
        return '', None
    faces = robot.part_for_face.get(best['object'].name)
    name = faces[best['face']] if faces and 0 <= best['face'] < len(faces) else ''
    return name or '', best


def asset_list():
    """the inspector's asset list: (id, label) for every catalog entry except the rotor-only 'rotors_*' variants"""
    from .kit import catalog
    return [(rid, e.get('label', rid)) for rid, e in catalog()['models'].items() if not rid.startswith('rotors_')]


def _ring_source(name='inspector ring'):
    """viewer.js's FDM demonstration: LatheGeometry([[.014, 0], [.020, 0], [.020, .006], [.014, .006], [.014, 0]],
    48), a 6 mm ring standing on its base, as a mesh in Blender's axes"""
    from . import mech_parts as mp
    return mp.to_mesh(name, mp.lathe_geometry([(.014, 0), (.020, 0), (.020, .006), (.014, .006), (.014, 0)], 48))


class Inspector(dict):
    """viewer.js's page state and window.roboticsInspector, over one Blender scene (see the module docstring)"""

    def __init__(self, scene, camera, studio_rec, duration=20.0, fps=24, process_options=None):
        super().__init__(scene=scene, camera=camera, studio=studio_rec, robot=None, clip=None, job=None, time=0.0,
                         stats=None, status='', ports='', parts=[], part_triangles=None, uv=None, wire=[],
                         references=[], joints={}, target=None)
        self.duration, self.fps = float(duration), fps
        self.manual = False
        self.selection = ''
        self.wire_on = False
        self.reference_on = False
        self.filament_color = '#218675'
        self.stock_material = 'aluminum'
        self.stock_size = (140, 36, 36)
        self.timing = 'lapse'
        self.source, self.source_name = None, ''
        self.process_options = dict(process_options or {})
        self.playing = False

    # ------------------------------------------------------------------------------------------------ helpers
    @property
    def robot(self):
        return self['robot']

    @property
    def scene(self):
        return self['scene']

    @property
    def camera(self):
        return self['camera']

    @property
    def job(self):
        return self['job']

    def _range(self, seconds):
        sc = self.scene
        sc.render.fps, sc.render.fps_base = self.fps, 1.0
        sc.frame_start = 1
        sc.frame_end = max(1, int(round(seconds * self.fps)))

    def clips(self):
        r = self.robot
        out = list(r.clips)
        if (r.machine or {}).get('tool'):
            out.insert(0, 'process')
        return out

    def _dispose_job(self):
        if self['job'] is not None:
            try:
                self['job'].stop()
            except Exception:  # noqa: BLE001 - a job of the fabrication port without stop()
                pass
            self['job'].dispose()
            self['job'] = None

    # ------------------------------------------------------------------------------------------------ load
    def load(self, model, primary=None, accent=None):
        """the asset list: dispose the job and the robot, load `model`, rebuild the lists, choose the first motion
        ('process' on a machine with a tool), fit, update the status"""
        self._dispose_job()
        if self['robot'] is not None:
            self['robot'].stop()
            self['robot'].dispose()
        try:                    # viewer.js imports fabrication.js: the dispensers load with their live filament
            import eidoblend.fabrication  # noqa: F401
        except ImportError:
            pass
        r = make_robot(model, scene=self.scene)
        self['robot'] = r
        self['time'] = 0.0
        self.manual = False
        self.selection = ''
        if primary is not None or accent is not None:
            r.set_colors(primary, accent)
        if 'rotary_chuck' in r.roots:
            self.stock_material = 'wood'
        refs = r.grasp_reference()
        for o in refs:
            o.hide_render = o.hide_viewport = not self.reference_on
        self['references'] = refs
        self['wire'] = wire_overlay(r, visible=self.wire_on)
        self['parts'] = sorted(r.parts())
        ports = '\n'.join(f"{n} · {p['interface']}" for n, p in r.ports.items()) or \
            'No declared interface on this individual library part.'
        self['ports'] = ports
        self.scene['inspector_ports'] = ports
        self.scene['inspector_model'] = model
        self['joints'] = {}
        self.set_motion(self.clips()[0])
        return self

    # ------------------------------------------------------------------------------------------------ motion
    def set_motion(self, clip):
        """chooseClip: the job disposed, time 0, manual mode off; 'process' makes the fabrication job (keyed over its
        duration), any other motion is keyed over the time slider's 20 s; then the camera fit"""
        r = self.robot
        if clip not in self.clips():
            raise ValueError(f'Unknown motion {clip!r} for {r.id}; motions: {self.clips()}')
        self._dispose_job()
        if self.manual and self['joints']:
            from .rig import unrig_joints
            unrig_joints(r)
            self['joints'] = {}
        self.manual = False
        self['time'] = 0.0
        self['clip'] = clip
        self.scene['inspector_clip'] = clip
        r.stop()
        if clip == 'process':
            job = self._make_job()
            frames = int(math.ceil(job.duration * self.fps))
            if frames > MAX_KEYED_FRAMES:
                job.dispose()
                raise ValueError(f'physical timing makes this job {job.duration:.0f} s long, {frames:,} keyed frames '
                                 f'(more than {MAX_KEYED_FRAMES:,}): use the time lapse, or '
                                 "process_options={'duration': seconds}")
            self['job'] = job
            self._range(job.duration)
            job.play(frame_start=self.scene.frame_start, frame_end=self.scene.frame_end, scene=self.scene)
            self['target'] = fit(r, self.camera, None)
        else:
            self._range(self.duration)
            self['target'] = fit(r, self.camera, clip)                     # sampled, before the keys exist
            r.play(clip, frame_start=self.scene.frame_start, frame_end=self.scene.frame_end, scene=self.scene)
        self.set_time(0.0)
        self.update_stats()
        return self

    def _make_job(self):
        try:
            from eidoblend import fabrication as fab
        except ImportError as e:                                       # pragma: no cover - the package is present
            raise RuntimeError('the process motion is a fabrication job: eidoblend.fabrication is needed') from e
        r = self.robot
        tool = (r.machine or {}).get('tool')
        lapse = 32.0 if 'rotary_chuck' in r.roots else 18.0
        opts = dict(self.process_options)
        if self.timing != 'physical':
            opts['duration'] = lapse
        source = self.source
        if tool == 'extruder_fixed':
            src = source if source is not None else _ring_source()
            job = fab.print(r, src, size=.04, infill=.25, color=self.filament_color, **opts)
            if source is None and src.users == 0:
                bpy.data.meshes.remove(src)
            return job
        if 'rotary_chuck' in r.roots:
            length, width, height = self.stock_size
            return fab.rotary_carve(r, source if source is not None else fab.sample_rotary, material=self.stock_material,
                                    stock_length=length / 1000, stock_width=width / 1000, stock_height=height / 1000,
                                    **opts)
        if ((r.machine or {}).get('cutter') or {}).get('kind') == 'ball':
            fitted = (fab.fit_source_geometry(source, bounds=((-.032, -.055, .004), (.032, .055, .019)))
                      if source is not None else None)
            return fab.carve(r, fitted if fitted is not None else fab.sample_relief, material=self.stock_material,
                             resolution=192, **opts)
        if source is not None:
            raise ValueError('Choose the CNC relief or rotary machine to carve a supplied mesh.')
        return fab.mill(r, None, material=self.stock_material, **opts)

    def set_time(self, t):
        """setTime / the time slider: the keyed timeline at t seconds (a sub-frame between keys)"""
        t = max(0.0, float(t))
        sc = self.scene
        f = sc.frame_start + t * self.fps
        sc.frame_set(int(math.floor(f)), subframe=f - math.floor(f))
        self['time'] = t
        return self

    def reset(self):
        """the Reset button: time 0, manual mode off"""
        self.manual = False
        return self.set_time(0.0)

    def play(self, on=True):
        """the Play button: the scene plays its keyed range (open the file and press play, or render the range)"""
        self.playing = bool(on)
        self.scene.frame_current = self.scene.frame_start
        return self

    # ------------------------------------------------------------------------------------------------ view
    def fit(self):
        """the Frame button: the sweep of a keyed walk / drive-circle / flight / run read from the timeline (the keys
        would override a sample), else the current pose"""
        r = self.robot
        clip = None if (self.manual or self['job'] is not None) else self['clip']
        if clip is not None and (clip in SWEEP_CLIPS or clip.startswith('run-')) and r._played is not None:
            t0, boxes, t = self['time'], [], 0.0
            while t <= 20.0:
                self.set_time(t)
                boxes.append(world_box([r.group], visible_only=True))
                t += 0.5
            self.set_time(t0)
            direction = (-0.9, -1.5, 0.55) if r.filament is not None else (0.9, -1.5, 0.55)
            target = frame_camera(self.camera, boxes, direction=direction, margin=1.08)
        else:
            target = fit(r, self.camera, clip)
        self['target'] = target
        return target

    def frame_work(self):
        """the "Inspect workpiece" button: frameCamera on the job's mesh"""
        job = self['job']
        if job is None:
            return None
        printing = getattr(job, 'kind', '') == 'print'
        direction = (-0.7, -1.3, 0.34) if printing else (0.8, -0.5, 1.1)
        return frame_camera(self.camera, [job.mesh], direction=direction, margin=1.55 if printing else 1.2)

    def set_colors(self, primary=None, accent=None):
        self.robot.set_colors(primary, accent)
        return self

    def pickers(self):
        """the colour pickers' values: the palette as '#rrggbb' (what load() shows in Body / Accent / Filament)"""
        from .materials import to_srgb_hex
        return {k: to_srgb_hex(v) for k, v in self.robot.materials.colors().items()}

    def set_filament_color(self, color):
        """the Filament picker: the print job's bead, reel and strand, else the robot's live filament"""
        self.filament_color = color
        job = self['job']
        if job is not None and getattr(job, 'kind', '') == 'print':
            job.set_color(color)
        elif getattr(self.robot, 'filament', None) is not None:
            self.robot.filament.set_color(color)
        else:
            self.robot.set_colors(filament=color)
        return self

    def set_wireframe(self, on=True):
        self.wire_on = bool(on)
        for w in self['wire']:
            w.hide_render = w.hide_viewport = not self.wire_on
        return self

    def set_reference(self, on=True):
        self.reference_on = bool(on)
        for o in self['references']:
            o.hide_render = o.hide_viewport = not self.reference_on
        return self

    # ------------------------------------------------------------------------------------------------ parts
    def update_stats(self):
        s = self.robot.stats()
        status = (f"{s['triangles']:,} triangles · {s['meshes']} meshes · {s['materials']} material bindings · "
                  f"{s['textures']} shared maps")
        self['stats'], self['status'] = s, status
        self.scene['inspector_status'] = status
        self['part_triangles'] = part_triangles(self.robot, self.selection) if self.selection else None
        return status

    def pick_part(self, name):
        """the part list: select `name` ('' for all parts); returns its triangle count"""
        if name and name not in self.robot.parts():
            raise KeyError('Unknown part ' + name)
        self.selection = name or ''
        self.update_stats()
        return self['part_triangles']

    def pick(self, x, y):
        """a click on the image at (x, y), 0..1 from the top left: the part under it becomes the selection"""
        name, hit = pick(self.robot, self.camera, x, y, self.scene)
        self.pick_part(name)
        self['hit'] = hit
        return name

    def draw_uv(self, path, batch=None, channel=None, material=None):
        """the UV split view of the current selection (the map list's first entry by default)"""
        if batch is None and material is None:
            choices = map_choices(self.robot)
            if choices and not choices[0][0].startswith('@'):
                batch, channel = choices[0]
        rec = draw_uv(self.robot, path, part=self.selection, batch=batch, channel=channel, material=material)
        self['uv'] = rec
        return rec

    def set_joint(self, name, value):
        """a joint slider: manual mode (the rig's simple-expression drivers move the module)"""
        from .rig import rig_joints, set_slider
        r = self.robot
        if not self.manual or not self['joints']:
            self._dispose_job()
            r.stop()
            r.reset()
            self['joints'] = rig_joints(r)
            self.manual = True
        set_slider(r, name, value)
        return self

    # ------------------------------------------------------------------------------------------------ process
    def set_stock(self, material=None, preset=None, length=None, width=None, height=None):
        """the stock controls: material (aluminum, brass, steel, wood, plywood), the rotary blank (a preset
        '140,36,36' / '100,24,28' / '180,44,50', or mm sizes); restarts the process ("Fit blank and restart")"""
        if material is not None:
            if material not in STOCK_MATERIALS:
                raise ValueError(f'Stock material must be one of {STOCK_MATERIALS}')
            self.stock_material = material
        size = list(STOCK_PRESETS[preset]) if preset is not None else list(self.stock_size)
        for i, v in enumerate((length, width, height)):
            if v is not None:
                size[i] = v
        self.stock_size = tuple(size)
        if 'process' in self.clips():
            self.set_motion('process')
        return self

    def set_timing(self, timing):
        """the process playback: 'lapse' (18 s; 32 s on the rotary machine) or 'physical' (the job's own time)"""
        if timing not in ('lapse', 'physical'):
            raise ValueError("Process playback is 'lapse' or 'physical'")
        self.timing = timing
        if self['clip'] == 'process':
            self.set_motion('process')
        return self

    def set_source(self, source, name='Supplied mesh'):
        """setSource: the process workpiece (a bpy Object / Mesh / Collection, a manufacturing sample name, or None
        for the machine demonstration); chooses the process motion"""
        if isinstance(source, str):
            if source not in SOURCE_SAMPLES:
                raise ValueError(f'Workpiece samples: {SOURCE_SAMPLES}')
            from eidoblend import fabrication as fab
            name, source = source, fab.manufacturing_sample(source)
        self.source, self.source_name = source, (name if source is not None else '')
        return self.set_motion('process')

    def process_state(self):
        """the processState line: the print's fed / retracted filament, or the cut's material, rpm, stage, A angle
        and feed"""
        job = self['job']
        if job is None or job.state is None:
            return ''
        st = job.state
        get = (lambda k, d=None: st.get(k, d)) if isinstance(st, dict) else (lambda k, d=None: getattr(st, k, d))
        if get('filament_length') is not None:
            return (f"{get('type')} | {get('filament_length') * 1000:.1f} mm fed | "
                    f"{(get('filament_retraction') or 0) * 1000:.2f} mm retracted")
        settings = getattr(job, 'settings', None) or getattr(job, 'options', {}) or {}
        sget = (lambda k, d=None: settings.get(k, d)) if isinstance(settings, dict) else \
            (lambda k, d=None: getattr(settings, k, d))
        angle = get('angle')
        rpm = sget('rpm', 0) or 0
        return (f"{sget('material', self.stock_material)} | {int(rpm):,} rpm | {get('stage') or get('type')}"
                + ('' if angle is None else f' | A {math.degrees(angle):.1f}°')
                + f" | {(get('speed') or 0) * 60000:.0f} mm/min")

    def dispose(self):
        self._dispose_job()
        if self['robot'] is not None:
            self['robot'].stop()
            self['robot'].dispose()
            self['robot'] = None


def inspector_scene(model='payloads/arm_hand', clip=None, duration=20.0, joints=False, wireframe=False,
                    reference=False, part='', uv=None, primary=None, accent=None, scene=None, fps=24,
                    resolution=(1280, 720), process_options=None) -> Inspector:
    sc = scene or bpy.context.scene
    sc.render.fps, sc.render.fps_base = fps, 1.0
    sc.render.resolution_x, sc.render.resolution_y = resolution
    st = studio(sc)
    cam = make_camera(35, 'inspector camera', sc)
    cam.data.clip_start, cam.data.clip_end = 0.001, 40.0
    sc.camera = cam
    insp = Inspector(sc, cam, st, duration, fps, process_options)
    insp.wire_on, insp.reference_on = bool(wireframe), bool(reference)
    insp.load(model, primary, accent)
    r = insp.robot
    if joints:
        r.stop()
        r.reset()
        from .rig import rig_joints
        insp['joints'] = rig_joints(r)
        insp.manual = True
        insp['clip'] = None
        sc['inspector_clip'] = ''
        insp['target'] = insp.fit()
    elif clip is not None and clip != insp['clip']:
        insp.set_motion(clip)
    if part:
        insp.pick_part(part)
    if uv:
        insp.draw_uv(uv)
    return insp
