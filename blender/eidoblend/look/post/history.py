"""look/post/history.py: earlier frames inside the compositor, for the effects that need them.

The WebGPU passes kept earlier frames on the GPU (three's AfterImageNode feedback, aeropittura's history ring).
Blender's compositor has no previous-frame node, so the frames go through the disk:

    h = History(scene, 'era_in', rider_of='era_looks')   # a File Output records what the 'era_looks' stage sees,
                                                          #   <dir>/era_in/era_in_####_rgba.exr (half float, alpha 1)
    img, present = h.tap(tree, 3)                         # an Image node reading the frame 3 back (frame_offset -3);
                                                          # present = its alpha: 0 where that file does not exist
    h.key_offsets(tree, 3, cuts)                          # never read across a cut: after cut c, max(n - 3, c)

A rider (`node['look_input_of'] = stage`) gets the same input as its stage on every chain relink (look/post/chain.py).
The file name carries '####', which Blender fills with the frame number in a still render as well as in an animation
(without it a still render writes '<name>.exr' with no number). During an animation render the File Output of frame n
is on disk before frame n + 1 composites, so a tap reads the frame just made (measured: an emissive sphere's position
at frame n - 1, every frame, and again in a single still render of a frame after them).
Where the earlier frame was never rendered the tap is transparent black (`present` 0) and the effect falls back as
WebGPU did on its first frame. Cuts (timeline markers that switch cameras, camera jumps, any frames given to cut())
restart a history: scene_cuts(scene), camera_jumps(scene) (era looks' camJumped(), found ahead of the render),
camera_of(scene, frame) (the marker camera Blender renders a frame with), evaluated(scene, ob) (an object as the
scene's own depsgraph has it after a frame_set, also for a scene that is not the window's).
Checked as a film renders (tests/post_era/test_film_render.py): an animation render in this session and the saved
.blend rendered by a fresh Blender from the command line give the frames the stills give.

Disk: half float, ZIP (lossless: a feedback trail must not carry a lossy codec's error from frame to frame), about
0.62 MB a frame at 960x540 (measured on after_image's trail; DWAA is 0.5 MB but lossy). prune() deletes frames
older than a history needs; auto_prune() does it after every rendered frame while this Python session renders (a
.blend rendered elsewhere keeps its files until prune() or clear()).
"""
from __future__ import annotations

import glob
import os
import re

import bpy

ROOT_DEFAULT = 'post_history'


def history_dir(scene):
    """Where a scene's histories live: //post_history/<scene>/ beside a saved .blend, else Blender's temp folder."""
    base = scene.get('eido_history_dir')
    if base:
        return bpy.path.abspath(base)
    if bpy.data.filepath:
        return os.path.join(os.path.dirname(bpy.data.filepath), ROOT_DEFAULT, bpy.path.clean_name(scene.name))
    return os.path.join(bpy.app.tempdir or os.environ.get('TEMP', '.'), 'eido_' + ROOT_DEFAULT,
                        bpy.path.clean_name(scene.name))


def set_history_dir(scene, path):
    scene['eido_history_dir'] = str(path)


class History:
    """A per-frame record of one compositor socket (a File Output), with Image-node taps reading it back.
    rider_of: a chain stage whose input this records (the writer rides along with it on every relink); else feed() a
    socket."""

    ITEM = 'rgba'

    def __init__(self, scene, key, source=None, codec='ZIP', depth='16', tree=None, rider_of=None):
        self.scene, self.key = scene, key
        self.tree = tree or scene.compositing_node_group
        self.dir = os.path.join(history_dir(scene), key)
        self.codec, self.depth = codec, depth
        self.writer = self._writer()
        if rider_of is not None:
            self.tree.nodes[f'hist:{self.key}:alpha']['look_input_of'] = rider_of
        if source is not None:
            self.feed(source)

    # ------------------------------------------------------------------------------------- writing
    def file(self, frame):
        return os.path.join(self.dir, f'{self.key}_{int(frame):04d}_{self.ITEM}.exr')

    def _writer(self):
        t = self.tree
        name = f'hist:{self.key}:write'
        fo = t.nodes.get(name)
        if fo is None:
            fo = t.nodes.new('CompositorNodeOutputFile')
            fo.name = fo.label = name
            fo.file_output_items.new('RGBA', self.ITEM)
            sa = t.nodes.new('CompositorNodeSetAlpha')
            sa.name = sa.label = f'hist:{self.key}:alpha'
            sa['eido_history'] = self.key
            sa.inputs['Alpha'].default_value = 1.0
            try:
                sa.inputs['Type'].default_value = 'Replace Alpha'
            except (KeyError, TypeError):
                pass
            t.links.new(sa.outputs['Image'], fo.inputs[self.ITEM])
            sa.location = fo.location = (0, -600 - 160 * len([n for n in t.nodes if n.get('eido_history')]))
            fo.location = (sa.location[0] + 200, sa.location[1])
        fo.directory = self.dir + os.sep
        fo.file_name = f'{self.key}_####_'            # '####': the frame number, in still renders too
        fmt = fo.format
        fmt.media_type = 'IMAGE'
        fmt.file_format = 'OPEN_EXR'
        fmt.color_depth = self.depth
        fmt.exr_codec = self.codec
        fo.save_as_render = False
        fo['eido_history'] = self.key
        os.makedirs(self.dir, exist_ok=True)
        return fo

    @property
    def input(self):
        """The socket the recorded image goes into (alpha is forced to 1 there: the presence flag)."""
        return self.tree.nodes[f'hist:{self.key}:alpha'].inputs['Image']

    def feed(self, socket):
        for lk in list(self.input.links):
            self.tree.links.remove(lk)
        self.tree.links.new(socket, self.input)

    def alpha_from(self, socket):
        """Record `socket` (0..1) as each frame's alpha instead of 1: a per-frame flag the taps read back with the
        picture (the era pass records whether its CRT was on, so persistence restarts when the tube comes on).
        A frame never rendered still reads 0."""
        a = self.tree.nodes[f'hist:{self.key}:alpha'].inputs['Alpha']
        for lk in list(a.links):
            self.tree.links.remove(lk)
        self.tree.links.new(socket, a)

    # ------------------------------------------------------------------------------------- reading
    def image(self):
        """The Image datablock of the recorded sequence (one per history)."""
        name = f'hist_{self.scene.name}_{self.key}'
        im = bpy.data.images.get(name)
        first = self.file(1)
        if im is None:
            im = bpy.data.images.new(name, 4, 4, float_buffer=True)
        im.source = 'SEQUENCE'
        im.filepath = first
        try:
            im.colorspace_settings.name = 'Linear Rec.709'
        except TypeError:
            pass
        return im

    def tap(self, tree, offset, name=None):
        """An Image node in `tree` reading the frame `offset` frames back. Returns (image socket, alpha socket):
        alpha is 1 where the frame exists and 0 where it does not."""
        nm = name or f'hist:{self.key}:-{int(offset)}'
        n = tree.nodes.get(nm)
        if n is None:
            n = tree.nodes.new('CompositorNodeImage')
            n.name = n.label = nm
        n.image = self.image()
        n.frame_start = 1
        n.frame_duration = 1000000
        n.frame_offset = -int(offset)
        n.use_cyclic = False
        n.use_auto_refresh = True
        n['eido_history'] = self.key
        n['eido_offset'] = int(offset)
        return n.outputs['Image'], n.outputs['Alpha']

    # ------------------------------------------------------------------------------------- cuts
    def key_offsets(self, tree, offset, cuts, clamp_to_cut=True, name=None):
        """Key the tap's frame_offset so that, after each cut c, frame n reads max(n - offset, c) (clamp_to_cut, the
        WebGPU ring refilled with the cut frame) and never a frame of the shot before."""
        nm = name or f'hist:{self.key}:-{int(offset)}'
        n = tree.nodes[nm]
        key_offset_ramp(tree, n, int(offset), cuts)
        return n

    def taps(self, tree=None):
        """{offset: Image node} of this history's taps in `tree` (default: the writer's tree)."""
        tree = tree or self.tree
        return {int(n['eido_offset']): n for n in tree.nodes
                if n.bl_idname == 'CompositorNodeImage' and n.get('eido_history') == self.key}

    def set_cuts(self, cuts, tree=None, fresh=None):
        """Key every tap so no frame reads across a cut (frames: the scene's first frame is always one): after cut c,
        frame n reads max(n - k, c). fresh: a socket keyed 1 on each cut frame and 0 after it (CONSTANT): on the cut
        frame itself every tap would read that frame's own record before it is written (missing, or stale from an
        earlier render), so the effect ignores its taps there, as the WebGPU ring refilled with the new shot."""
        tree = tree or self.tree
        cuts = sorted({int(c) for c in cuts} | {int(self.scene.frame_start)})
        self.tree['eido_cuts_' + self.key] = cuts
        for off, n in self.taps(tree).items():
            key_offset_ramp(tree, n, off, cuts)
        if fresh is not None:
            self.fresh_path = fresh.path_from_id('default_value')
            key_fresh(fresh, cuts)
        elif getattr(self, 'fresh_path', None):
            key_fresh(self.tree.path_resolve(self.fresh_path.rsplit('.', 1)[0]), cuts)
        return cuts

    def add_cuts(self, frames, tree=None):
        old = list(self.tree.get('eido_cuts_' + self.key, []))
        return self.set_cuts(old + [int(f) for f in frames], tree)

    # ------------------------------------------------------------------------------------- disk
    def files(self):
        return sorted(glob.glob(os.path.join(self.dir, f'{self.key}_*_{self.ITEM}.exr')))

    def prune(self, before_frame):
        """Delete recorded frames older than `before_frame`. Returns how many went."""
        k = 0
        for p in self.files():
            m = re.search(r'_(-?\d+)_' + self.ITEM + r'\.exr$', p)
            if m and int(m.group(1)) < before_frame:
                try:
                    os.remove(p)
                    k += 1
                except OSError:
                    pass
        return k

    def clear(self):
        return self.prune(10 ** 9)

    def bytes(self):
        return sum(os.path.getsize(p) for p in self.files())


def key_offset_ramp(tree, node, offset, cuts):
    """frame_offset keys on an Image node: after each cut c, 0 at c ramping to -offset at c + offset (LINEAR, so each
    integer frame reads exactly max(n - offset, c)), then held (CONSTANT) until the next cut."""
    path = f'nodes["{node.name}"].frame_offset'
    ad = tree.animation_data or tree.animation_data_create()
    if ad.action:
        for fc in [f for f in _fcurves(ad.action, tree) if f.data_path == path]:
            _remove_fcurve(ad.action, tree, fc)
    node.frame_offset = -offset
    cuts = sorted(set(int(c) for c in cuts))
    for i, c in enumerate(cuts):
        nxt = cuts[i + 1] if i + 1 < len(cuts) else None
        end = c + offset if nxt is None else min(c + offset, nxt - 1)
        node.frame_offset = 0
        node.keyframe_insert('frame_offset', frame=c)
        if end > c:
            node.frame_offset = -(end - c)
            node.keyframe_insert('frame_offset', frame=end)
    for fc in [f for f in _fcurves(tree.animation_data.action, tree) if f.data_path == path]:
        for k in fc.keyframe_points:
            k.interpolation = 'LINEAR' if k.co.y == 0 else 'CONSTANT'
        fc.update()


def key_fresh(socket, cuts):
    """A socket keyed 1 on each cut frame and 0 on the frame after (CONSTANT): 'this frame starts a shot'."""
    tree = socket.id_data
    path = socket.path_from_id('default_value')
    ad = tree.animation_data or tree.animation_data_create()
    if ad.action:
        for fc in [f for f in _fcurves(ad.action, tree) if f.data_path == path]:
            _remove_fcurve(ad.action, tree, fc)
    for c in sorted(set(int(c) for c in cuts)):
        socket.default_value = 1.0
        socket.keyframe_insert('default_value', frame=c)
        socket.default_value = 0.0
        socket.keyframe_insert('default_value', frame=c + 1)
    for fc in [f for f in _fcurves(tree.animation_data.action, tree) if f.data_path == path]:
        for k in fc.keyframe_points:
            k.interpolation = 'CONSTANT'
        fc.update()


def _fcurves(action, owner):
    """An action's F-curves for `owner` (5.x layered actions: through the slot's channelbag)."""
    try:
        from bpy_extras import anim_utils
        cb = anim_utils.action_get_channelbag_for_slot(action, owner.animation_data.action_slot)
        return list(cb.fcurves) if cb else []
    except Exception:
        return list(getattr(action, 'fcurves', []))


def _remove_fcurve(action, owner, fc):
    try:
        from bpy_extras import anim_utils
        cb = anim_utils.action_get_channelbag_for_slot(action, owner.animation_data.action_slot)
        cb.fcurves.remove(fc)
    except Exception:
        action.fcurves.remove(fc)


def _camera_markers(scene):
    """The timeline markers that bind a camera, in frame order (a camera hidden from renders is skipped, as Blender's
    camera switch skips it)."""
    return sorted((m for m in scene.timeline_markers if m.camera is not None and not m.camera.hide_render),
                  key=lambda m: m.frame)


def camera_of(scene, frame):
    """The camera a render of `frame` uses: with camera markers, the one bound by the last marker at or before the
    frame, and before the first marker the first marker's camera (Blender's camera switch); without, scene.camera."""
    ms = _camera_markers(scene)
    if not ms:
        return scene.camera
    cam = ms[0].camera
    for m in ms:
        if m.frame <= frame:
            cam = m.camera
    return cam


def scene_cuts(scene, extra=()):
    """The frames a history restarts at: the scene's first frame, every timeline marker that switches to another
    camera (the first marker's camera is the shot's from the start, so it is not a switch), and `extra` (U.cut() in
    the WebGPU passes)."""
    cuts = {int(scene.frame_start)}
    ms = _camera_markers(scene)
    prev = ms[0].camera if ms else None
    for m in ms:
        if m.camera != prev:
            cuts.add(int(m.frame))
        prev = m.camera
    cuts.update(int(c) for c in extra)
    return sorted(c for c in cuts if c >= scene.frame_start)


def evaluated(scene, ob):
    """`ob` as the scene's own depsgraph evaluated it (after scene.frame_set): its world matrix, pose and data at
    that frame. Blender writes the evaluated values back onto the original objects only for the active depsgraph
    (the window's scene), so a scene that is not the active one must be read this way."""
    vl = bpy.context.view_layer if scene == bpy.context.scene else scene.view_layers[0]
    return ob.evaluated_get(vl.depsgraph)


def _camera_at(scene, frame):
    """The active camera's (object, world matrix) at `frame`. A camera with no parent, constraints or drivers is
    read from its own F-curves (no scene evaluation); any other is read after a frame_set, from the scene's own
    depsgraph (evaluated(): right for a scene that is not the active one too)."""
    from mathutils import Euler, Matrix, Quaternion, Vector
    cam = camera_of(scene, frame)
    if cam is None:
        return None, None
    ad = cam.animation_data
    simple = cam.parent is None and not cam.constraints and not (ad and ad.drivers)
    if not simple:
        scene.frame_set(frame)
        return cam, evaluated(scene, cam).matrix_world.copy()
    loc, rot_e, rot_q, scl = Vector(cam.location), Euler(cam.rotation_euler, cam.rotation_mode
                                                          if cam.rotation_mode in ('XYZ', 'XZY', 'YXZ', 'YZX',
                                                                                   'ZXY', 'ZYX') else 'XYZ'), \
        Quaternion(cam.rotation_quaternion), Vector(cam.scale)
    if ad and ad.action:
        for fc in _fcurves(ad.action, cam):
            v = fc.evaluate(frame)
            if fc.data_path == 'location':
                loc[fc.array_index] = v
            elif fc.data_path == 'rotation_euler':
                rot_e[fc.array_index] = v
            elif fc.data_path == 'rotation_quaternion':
                rot_q[fc.array_index] = v
            elif fc.data_path == 'scale':
                scl[fc.array_index] = v
    rot = rot_q.to_matrix() if cam.rotation_mode == 'QUATERNION' else rot_e.to_matrix()
    return cam, Matrix.LocRotScale(loc, rot, scl)


def camera_jumps(scene, frames=None, dist=0.6, angle_deg=10.0):
    """Frames where the active camera jumps (> dist metres or > angle_deg degrees since the frame before): era
    looks' camJumped(). Found once, ahead of the render: from the camera's own F-curves when it has no parent,
    constraints or drivers (fast), else by stepping the scene (a frame_set per frame)."""
    import math
    from mathutils import Vector
    frames = frames or range(scene.frame_start, scene.frame_end + 1)
    out, prev = [], None
    keep = scene.frame_current
    cos_lim = math.cos(math.radians(angle_deg))
    for f in frames:
        cam, mw = _camera_at(scene, f)
        if cam is None:
            continue
        p = mw.translation.copy()
        d = (mw.to_3x3() @ Vector((0, 0, -1))).normalized()
        if prev is not None and ((p - prev[0]).length > dist or d.dot(prev[1]) < cos_lim):
            out.append(f)
        prev = (p, d)
    if scene.frame_current != keep:
        scene.frame_set(keep)
    return out


_PRUNERS = {}


def auto_prune(scene, keep=None):
    """While this Python session renders, delete each history's frames older than it needs after every frame.
    keep: {history key: frames kept behind the current one}."""
    _PRUNERS[scene.name] = dict(keep or {})

    @bpy.app.handlers.persistent
    def _after_frame(sc, *_a):
        k = _PRUNERS.get(sc.name)
        if not k:
            return
        base = history_dir(sc)
        for key, back in k.items():
            h_dir = os.path.join(base, key)
            for p in glob.glob(os.path.join(h_dir, f'{key}_*_{History.ITEM}.exr')):
                m = re.search(r'_(-?\d+)_' + History.ITEM + r'\.exr$', p)
                if m and int(m.group(1)) < sc.frame_current - int(back):
                    try:
                        os.remove(p)
                    except OSError:
                        pass

    hs = bpy.app.handlers.render_post
    for h in [h for h in hs if getattr(h, '__name__', '') == '_after_frame']:
        hs.remove(h)
    hs.append(_after_frame)
    return _after_frame
