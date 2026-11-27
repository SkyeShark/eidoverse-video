"""eidoblend.characters.crowd: crowds and marching columns of any VRM, as a Geometry Nodes flipbook (characters.md,
"Crowds and columns").

    from eidoblend.characters import crowd, load_vrm
    me = load_vrm('claude_robot')                                        # the donor: any VRM
    lamp = crowd.HeldProp(lantern, bone='rightHand', grip='fist', hang=True)          # any mesh, object or collection
    cyc = crowd.stride_cycle(me, 'walk', bpm=116, props=[lamp], curl={'right': 80.0})   # ONE stride, baked to poses
    pts = crowd.formation(files=3, ranks=12, interval=0.8, distance=1.0, origin=(0, 0, 0), heading=0.0,
                          jitter={'lateral': 0.03, 'along': 0.05, 'phase': 0.03, 'seed': 11})
    col = crowd.crowd_object('column', pts, crowd.column_group(cyc, ref_frame=1))   # ONE object, a point a body

    crowd.reset_donor(me)                                                # the same donor, a one-shot clip
    wave = crowd.once_flipbook(me, 'wave_goodbye', every=2)
    pts = crowd.grid(lines=4, units=6)
    crowd.crowd_object('wave', pts, crowd.once_group(wave, hold=(140, 48)),
                       starts=crowd.canon_starts(pts, first=12, step_line=10, step_unit=4))
    crowd.drop_donor(me)                                                 # only plain meshes stay in the file

THE DONOR      one body of the VRM is keyed once and baked: a stride of a locomotion clip walked by
               locomotion.walk_path (its feet planted, the clip timed so a stride is two beats), a stationary loop or a
               one-shot clip placed by vrma.play_vrma. Held props, fingers curled round a handle, the face's expressions
               are on the donor when it is baked, so every body carries them
THE FLIPBOOK   each pose is ONE plain mesh of the donor's meshes as Blender evaluates them (the skin, the shape keys,
               the bone-parented parts), in the pose's own frame; parts under a refracting material (a glass dome over a
               face screen) are a second mesh a pose, as EEVEE sees nothing of an object's own surfaces through its
               refraction. Pose 0 is baked whole; every later pose is a copy of it with its positions written over, so
               the poses share topology, UVs, materials and the custom normals' layout in memory (checked: every pose's
               corners name the same vertices as pose 0's). A held prop is one object a pose, its mesh shared, its
               matrix the hand bone's matrix times the prop's grip, in the pose's frame (or hanging plumb from the grip
               point: hang=True). No collection is in a scene: the node group names them, so appending the crowd's
               object brings them along
THE STRIDE     stride_cycle walks the donor a few strides down a straight line on level ground at a rate of one baked
               frame a pose, from the clip time its left heel strikes, and bakes one stride in its steady state. The
               poses are in a frame that moves forward at the stride's own mean speed (S metres a stride): a planted
               foot slides back through the poses at exactly that speed, so an instancer that carries a body forward
               S x k / N for the k-th pose it shows keeps every planted foot where it landed. A stride is two beats (the
               left heel on beats one and three, the right on two and four) and N = poses_per_frame x the stride's film
               frames, the stride's frames rounded so that every film frame shows every poses_per_frame-th pose (the
               tempo used is in the record)
THE INSTANCER  column_group (a cycle, stride_cycle or loop_cycle): per point, phase = (frame + Frame Offset - Ref
                   Frame) / Stride Frames + dphase; k = floor(N x phase + 0.5); the pose shown k mod N; the point carried
                   Stride x k / N along its heading (its yaw turns the pose's front, local -Y). Ref Frame is a film frame
                   on which the left heel strikes (a downbeat)
               once_group (a one-shot clip, once_flipbook): per point, the pose clamp(floor((frame - start) / Every),
                   0, Poses - 1): folded at its first pose before its start, holding its last after the clip
               both: Show From / Show To (frames outside them delete the points), a hold (Hold From, Hold Frames: every
               body stops on Hold From, holds that pose Hold Frames frames, and carries on from where it held) and a
               point's own stop (its 'stop' attribute: from that frame on it holds for good)
THE POINTS     formation (files abreast at an interval, ranks at a distance, jitter in spacing and phase), grid (lines
               of units side by side) and canon_starts (start = first + step_line x the line's place + step_unit x the
               unit's place in its line); crowd_object writes them as one mesh of points with the attributes the groups
               read: yaw, dphase, start, stop (and rank, file, line, unit, kept for the user)
THE CHECKS     instances_at (what a frame shows), feet_slide (a body's floor points in the world, frame after frame:
               they must not move while planted), shown_poses (the pose every point shows against the one its
               attributes ask for)

Limits: the flipbook is rigid per pose, so a crowd walks on level ground (each point's z is its floor's height) and in
straight lines; every body of one flipbook is the same body doing the same thing, set apart by place, phase and start.
Motion blur on instances switching meshes is EEVEE's to judge: render the crowd's frames with it off if it smears.
"""

import json
import math
import random
import time

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

from .ground import Ground
from .locomotion import Body, analyze_clip, walk_path
from .vrma import load_clip, play_vrma

FRONT_TURN = Matrix.Rotation(math.pi / 2.0, 4, 'Z')     # a pose frame whose -Y (a VRM's front) points along world +X
FAR = 1.0e9                                             # 'stop' when a body never stops alone
FINGERS = ('Thumb', 'Index', 'Middle', 'Ring', 'Little')
JOINTS = {'Thumb': ('Metacarpal', 'Proximal', 'Distal'), 'Index': ('Proximal', 'Intermediate', 'Distal'),
          'Middle': ('Proximal', 'Intermediate', 'Distal'), 'Ring': ('Proximal', 'Intermediate', 'Distal'),
          'Little': ('Proximal', 'Intermediate', 'Distal')}


def _log(*a):
    print('[crowd]', *a, flush=True)


# ------------------------------------------------------------------------------------------------------ the props
def prop_mesh(source):
    """a held prop's mesh: a Mesh as it is; a mesh Object's evaluated mesh in the object's own space; a Collection's
    mesh objects joined into one mesh in the collection's (world) space, their materials and attributes kept"""
    if isinstance(source, bpy.types.Mesh):
        return source
    dg = bpy.context.evaluated_depsgraph_get()
    if isinstance(source, bpy.types.Object):
        return bpy.data.meshes.new_from_object(source.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    if not isinstance(source, bpy.types.Collection):
        raise TypeError(f'crowd.prop_mesh: a Mesh, an Object or a Collection, not {type(source).__name__}')
    tmp = bpy.data.collections.new('crowd.tmp_prop')
    bpy.context.scene.collection.children.link(tmp)
    parts = []
    for o in source.all_objects:
        if o.type != 'MESH':
            continue
        oe = o.evaluated_get(dg)
        me = bpy.data.meshes.new_from_object(oe, preserve_all_data_layers=True, depsgraph=dg)
        me.transform(oe.matrix_world)
        p = bpy.data.objects.new('crowd.tmp_prop.' + o.name, me)
        tmp.objects.link(p)
        parts.append(p)
    if not parts:
        bpy.data.collections.remove(tmp)
        raise ValueError(f'crowd.prop_mesh: the collection {source.name!r} holds no mesh')
    me = _join(parts, source.name)
    bpy.data.collections.remove(tmp)
    return me


class HeldProp:
    """a prop held in one hand: `source` (prop_mesh's Mesh, Object or Collection, made at its own origin), `bone` (a
    humanoid hand bone, 'rightHand' or 'leftHand'), `grip` (the prop's origin in the bone's frame: a Matrix, or (x, y,
    z), or ((x, y, z), (rx, ry, rz) degrees); or 'fist': the middle of the four fingers' middle joints, which lies inside
    a hand closed by curl). hang=True keeps the prop plumb: only the grip point follows the hand, the prop's axes are
    the pose frame's (up +Z, the body's front -Y) turned `turn` degrees about +Z (a lantern by its bail, a bag, a
    bucket); else the prop turns with the hand (a flag's pole in the fist, a tool)."""

    def __init__(self, source, bone='rightHand', grip=None, hang=False, turn=0.0, name=None):
        self.mesh = prop_mesh(source)
        self.bone, self.hang, self.turn = bone, bool(hang), float(turn)
        self.name = name or self.mesh.name.replace('.', '_')
        self.fist = isinstance(grip, str) and grip == 'fist'
        self.grip = Matrix.Identity(4) if self.fist else _matrix(grip)

    def matrix(self, h, pose_inv):
        """this prop's matrix in the pose frame (pose_inv: the world -> pose frame matrix) on the current frame"""
        pb = h.pb(self.bone)
        if pb is None:
            raise KeyError(f'crowd.HeldProp: the VRM has no bone {self.bone!r}')
        W = h.arm.matrix_world @ pb.matrix @ self.grip
        if self.fist:
            side = 'left' if self.bone.startswith('left') else 'right'
            heads = [h.pb(f'{side}{f}Intermediate') for f in ('Index', 'Middle', 'Ring', 'Little')]
            heads = [h.arm.matrix_world @ b.head for b in heads if b is not None]
            if heads:
                W = Matrix.Translation(sum(heads, Vector()) / len(heads)) @ W.to_3x3().to_4x4()
        if not self.hang:
            return pose_inv @ W
        return Matrix.Translation(pose_inv @ W.translation) @ Matrix.Rotation(math.radians(self.turn), 4, 'Z')


def _matrix(m):
    if m is None:
        return Matrix.Identity(4)
    if isinstance(m, Matrix):
        return m.copy()
    m = list(m)
    if len(m) == 3 and all(isinstance(v, (int, float)) for v in m):
        return Matrix.Translation(Vector(m))
    loc, rot = m
    R = Matrix.Rotation(math.radians(rot[2]), 4, 'Z') @ Matrix.Rotation(math.radians(rot[1]), 4, 'Y') @ \
        Matrix.Rotation(math.radians(rot[0]), 4, 'X')
    return Matrix.Translation(Vector(loc)) @ R


# ------------------------------------------------------------------------------------------------------ the hands
def curl_fingers(h, curl, thumb=0.6):
    """close a hand round a handle on the current frame: each finger joint of the side's hand turned `degrees` toward the
    palm (the thumb `thumb` times as far), in the VRM's normalized frame. curl: {'right': degrees, 'left': degrees}.
    The bakes apply it after every frame change (a value set on a bone holds until the next one), so the clip's own keys
    on the fingers never show"""
    arm = h.arm
    for side, deg in (curl or {}).items():
        sign = 1.0 if side == 'right' else -1.0
        for f in FINGERS:
            for j in JOINTS[f]:
                hb = h.humanoid.get(f'{side}{f}{j}')
                if hb is None or hb not in arm.pose.bones:
                    continue
                a = math.radians(deg) * (thumb if f == 'Thumb' else 1.0)
                # the fingers point along -X (right) / +X (left) in the T-pose's normalized frame, the palm down:
                # a turn about +Z (right) / -Z (left) brings the tips down toward the palm; the thumb closes about -+Y
                axis = Vector((0.0, -sign, 0.0)) if f == 'Thumb' else Vector((0.0, 0.0, sign))
                pb = arm.pose.bones[hb]
                pb.rotation_mode = 'QUATERNION'
                pb.rotation_quaternion = h.basis_from_normalized(hb, Quaternion(axis, a))


def reset_donor(h):
    """the donor back to a clean start for another bake: its keys and NLA strips off, the rest pose, at the origin
    facing -Y"""
    h.arm.animation_data_clear()
    h.zero_pose()
    h.arm.matrix_world = Matrix.Identity(4)
    bpy.context.view_layer.update()


# ------------------------------------------------------------------------------------------------------ the bake
def _join(parts, name):
    """join objects (in the view layer) into the first one's mesh -> that mesh (the objects removed)"""
    bpy.context.view_layer.update()
    datas = [p.data for p in parts[1:]]
    if len(parts) > 1:
        with bpy.context.temp_override(active_object=parts[0], object=parts[0], selected_objects=parts,
                                       selected_editable_objects=parts):
            res = bpy.ops.object.join()
        if 'FINISHED' not in res:
            raise RuntimeError(f'crowd: the join answered {res}')
    me = parts[0].data
    me.name = name
    for an in ('.select_vert', '.select_edge', '.select_poly'):
        a = me.attributes.get(an)
        if a is not None:
            try:
                me.attributes.remove(a)
            except (RuntimeError, ReferenceError):
                pass
    bpy.data.objects.remove(parts[0], do_unlink=True)
    for d in datas:
        if d.users == 0:
            bpy.data.meshes.remove(d)
    return me


def _refracts(o):
    """a part whose material refracts (EEVEE's raytraced transmission): joined with what lies behind it, EEVEE would not
    see that through it (a face screen under a glass dome), so it is baked as a layer of its own"""
    for s in o.material_slots:
        m = s.material
        if m is None:
            continue
        if getattr(m, 'use_raytrace_refraction', False):
            return True
        nt = m.node_tree
        for n in (nt.nodes if nt else []):
            if n.type == 'BSDF_PRINCIPLED' and n.inputs['Transmission Weight'].default_value > 0.0:
                return True
    return False


def _layers(h):
    """the donor's rendered meshes in two layers: 'body' and 'glass' (the refracting parts), in a fixed order"""
    out = {'body': [], 'glass': []}
    for o in h.meshes:
        if not o.hide_render:
            out['glass' if _refracts(o) else 'body'].append(o)
    if not out['body']:
        raise ValueError('crowd: the donor shows no mesh')
    return out


def _body_mesh(parts, pose_inv, name, tmp):
    """these donor meshes as Blender evaluates them now, in the pose frame, joined -> one Mesh"""
    dg = bpy.context.evaluated_depsgraph_get()
    objs = []
    for o in parts:
        oe = o.evaluated_get(dg)
        me = bpy.data.meshes.new_from_object(oe, preserve_all_data_layers=True, depsgraph=dg)
        me.transform(pose_inv @ oe.matrix_world)
        p = bpy.data.objects.new('crowd.tmp.' + o.name, me)
        tmp.objects.link(p)
        objs.append(p)
    return _join(objs, name)


class Flipbook:
    """a baked flipbook: bodies (the collection of pose objects), glass (the refracting parts' poses, or None), props
    ({name: collection}), poses (N), kind ('cycle' or 'once'), stride (m a cycle; 0 in place), stride_frames (film frames
    a cycle), every (film frames a pose, once), record (what the bake measured)"""

    def __init__(self, name, kind, bodies, glass, props, poses, record):
        self.name, self.kind, self.bodies, self.glass, self.props, self.poses = name, kind, bodies, glass, props, poses
        self.record = record
        self.stride = float(record.get('stride_m', 0.0))
        self.stride_frames = float(record.get('stride_frames', 0.0))
        self.every = float(record.get('every', 1.0))

    def layers(self):
        """the pose collections every point instances, in order: the bodies, the glass, each prop"""
        return [self.bodies] + ([self.glass] if self.glass is not None else []) + list(self.props.values())


class _Poses:
    """one layer's poses: pose 0 baked whole, the others copies of it with their positions written"""

    def __init__(self, name):
        self.name, self.meshes, self.checked = name, [], 0
        self.co = self.lv0 = None

    def add(self, me, i, last):
        if not self.meshes:
            self.co = np.empty(len(me.vertices) * 3, np.float32)
            self.lv0 = np.empty(len(me.loops), np.int32)
            me.loops.foreach_get('vertex_index', self.lv0)
            self.meshes.append(me)
            return
        base = self.meshes[0]
        if len(me.vertices) != len(base.vertices) or len(me.loops) != len(base.loops):
            raise RuntimeError(f'crowd: pose {i} of the {self.name} has {len(me.vertices)} vertices, pose 0 '
                               f'{len(base.vertices)}: the donor\'s meshes changed between frames')
        if i in (1, last // 2, last):
            lv = np.empty(len(me.loops), np.int32)
            me.loops.foreach_get('vertex_index', lv)
            if not np.array_equal(lv, self.lv0):
                raise RuntimeError(f'crowd: pose {i}\'s corners name other vertices than pose 0\'s ({self.name})')
            self.checked += 1
        me.vertices.foreach_get('co', self.co)
        name_i = me.name
        bpy.data.meshes.remove(me)
        cp = base.copy()
        cp.name = name_i
        cp.vertices.foreach_set('co', self.co)
        cp.update()
        self.meshes.append(cp)


def _goto(h, f, curl):
    """the donor on scene frame f, its hands closed (curl) after the frame change"""
    bpy.context.scene.frame_set(int(f))
    if curl:
        curl_fingers(h, curl)
    bpy.context.view_layer.update()


def bake_poses(h, frames, pose_frame, name, props=(), kind='cycle', record=None, curl=None):
    """bake the donor on each scene frame of `frames` into a Flipbook named `name`: pose_frame(i, f) -> the pose's frame
    in the world (a Matrix); props: HeldProp list; curl: curl_fingers' dict, applied on every frame. Each layer's pose 0
    is baked whole, its others are copies of it with their positions written (the vertex order checked on the first,
    middle and last). The donor's refracting parts are a layer of their own (EEVEE sees nothing of an object's own
    surfaces through its refraction)"""
    scene = bpy.context.scene
    t0 = time.time()
    parts = _layers(h)
    tmp = bpy.data.collections.new('crowd.tmp')
    scene.collection.children.link(tmp)
    layers = {k: _Poses(k) for k in ('body', 'glass') if parts[k]}
    pcols = {}
    for p in props:
        c = bpy.data.collections.new(f'crowd.{name}.{p.name}')
        c.use_fake_user = True
        pcols[p.name] = c
    last = len(frames) - 1
    for i, f in enumerate(frames):
        _goto(h, f, curl)
        inv = pose_frame(i, f).inverted()
        for k, lay in layers.items():
            lay.add(_body_mesh(parts[k], inv, f'crowd.{name}.{k}.{i:03d}', tmp), i, last)
        for p in props:
            o = bpy.data.objects.new(f'crowd.{name}.{p.name}.{i:03d}', p.mesh)
            o.matrix_world = p.matrix(h, inv)
            pcols[p.name].objects.link(o)
    cols = {}
    for k, lay in layers.items():
        c = bpy.data.collections.new(f'crowd.{name}.{"bodies" if k == "body" else k}')
        c.use_fake_user = True
        for i, me in enumerate(lay.meshes):
            c.objects.link(bpy.data.objects.new(f'crowd.{name}.{k}.{i:03d}', me))
        cols[k] = c
    bpy.data.collections.remove(tmp)
    base = layers['body'].meshes[0]
    rec = dict(record or {})
    rec.update({'name': name, 'kind': kind, 'poses': len(frames),
                'verts': sum(len(lay.meshes[0].vertices) for lay in layers.values()),
                'vertex_order_checked_on': layers['body'].checked, 'bake_seconds': round(time.time() - t0, 2),
                'props': [p.name for p in props], 'glass_parts': [o.name for o in parts['glass']]})
    base.calc_loop_triangles()
    rec['tris'] = len(base.loop_triangles)
    cols['body']['crowd'] = json.dumps({k: v for k, v in rec.items() if isinstance(v, (int, float, str, list))})
    return Flipbook(name, kind, cols['body'], cols.get('glass'), pcols, len(frames), rec)


def _flat(x, y):
    return 0.0 * np.asarray(x, dtype=np.float64)


def _left_strike(an):
    """the clip time the left heel strikes (the first sample of the left foot's stance) and the right's"""
    out = {}
    for s in ('left', 'right'):
        st = an['side'][s]['stance']
        n = len(st)
        i = next((k for k in range(n) if st[k] and not st[k - 1]), 0)
        out[s] = i * an['dtc']
    return out


def stride_cycle(h, clip='walk', bpm=None, poses_per_frame=2, props=(), curl=None, face=None, name=None, warmup=2,
                 log=_log, **walk_kw):
    """ONE stride of a locomotion clip on this VRM, its feet planted, baked -> a Flipbook (kind 'cycle').

    bpm: the march's tempo, a stride being two beats (None: the clip's own pace on this body); poses_per_frame: poses
    a film frame (2 or 3 keep the swing smooth at any tempo); props: HeldProp list; curl: {'right': deg, ...} fingers
    closed round a handle; face: expression weights held through the stride (walk_path's face). The scene's frame
    rate is the film's; the walk is keyed at poses_per_frame times it and set back. The donor stays keyed (drop_donor).
    The record: the stride (m), its film frames, N, the tempo used, the clip times of both heel strikes, the pose the
    right heel strikes on, and seam_mm (the stride's last pose + one against its first: the largest vertex distance)."""
    scene = bpy.context.scene
    c = load_clip(h, clip) if isinstance(clip, str) else clip
    fps_i, fps_base = scene.render.fps, scene.render.fps_base
    fps = fps_i / fps_base
    body = Body(h)
    an = analyze_clip(body, c)
    ppf = max(1, int(poses_per_frame))
    sf_asked = (120.0 * fps / bpm) if bpm else c.duration * fps
    n = max(8, int(round(sf_asked * ppf)))
    sf = n / ppf                                            # the stride's film frames, locked to the poses
    stride_s = sf / fps
    ts = c.duration / stride_s
    speed = ts * an['v_clip']
    strikes = _left_strike(an)
    path_len = (warmup + 2.6) * an['stride']
    rec = {'clip': c.slot, 'bpm_asked': bpm, 'bpm_used': round(120.0 * fps / sf, 4), 'stride_frames': sf,
           'poses_per_frame': ppf, 'time_scale': round(ts, 5), 'speed_m_s': round(speed, 4),
           'clip_stride_m': round(an['stride'], 4), 'left_strike_clip_s': round(strikes['left'], 4),
           'right_strike_clip_s': round(strikes['right'], 4), 'double_support': round(an['double_support'], 4)}
    keep = (scene.frame_start, scene.frame_end, scene.frame_current)
    scene.render.fps = fps_i * ppf                       # one keyed frame a pose
    try:
        walk_kw.setdefault('body', body)
        walk_path(h, c, [(0.0, 0.0), (path_len, 0.0)], Ground(fn=_flat), f0=1, speed=speed, phase=strikes['left'],
                  face=face, log=log, **walk_kw)
        fa = 1 + warmup * n
        scene.frame_set(fa)
        xa = h.arm.matrix_world.translation.x
        scene.frame_set(fa + n)
        xb = h.arm.matrix_world.translation.x
        S = xb - xa
        rec.update({'stride_m': round(S, 5), 'first_frame_at_bake_rate': fa})

        def pose_frame(i, f):
            return Matrix.Translation((xa + S * i / n, 0.0, 0.0)) @ FRONT_TURN
        fb = bake_poses(h, list(range(fa, fa + n)), pose_frame, name or f'{c.slot}_stride', props, 'cycle', rec, curl)
        # the seam: the pose one stride on, in its own moving frame, against pose 0
        tmp = bpy.data.collections.new('crowd.tmp')
        scene.collection.children.link(tmp)
        _goto(h, fa + n, curl)
        me = _body_mesh(_layers(h)['body'], pose_frame(n, fa + n).inverted(), 'crowd.tmp_seam', tmp)
        a = np.empty(len(me.vertices) * 3, np.float32)
        b = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get('co', a)
        fb.bodies.objects[0].data.vertices.foreach_get('co', b)
        bpy.data.meshes.remove(me)
        bpy.data.collections.remove(tmp)
        fb.record['seam_mm'] = round(float(np.abs(a - b).max()) * 1000.0, 3)
        fb.record['right_strike_pose'] = int(round(((strikes['right'] - strikes['left']) % c.duration) / c.duration * n)) % n
    finally:
        scene.render.fps, scene.render.fps_base = fps_i, fps_base
        scene.frame_start, scene.frame_end = keep[0], keep[1]
        scene.frame_set(keep[2])
    fb.stride = fb.record['stride_m']
    fb.stride_frames = sf
    log('stride', {k: v for k, v in fb.record.items() if not isinstance(v, (list, dict))})
    return fb


def loop_cycle(h, clip, bpm=None, beats=2, poses_per_frame=1, props=(), curl=None, name=None, log=_log):
    """ONE loop of a stationary clip (a sway, a dance, an idle) in place, baked -> a Flipbook (kind 'cycle', stride 0).
    bpm: the loop timed to last `beats` beats (None: the clip's own length). column_group plays it on the beat."""
    scene = bpy.context.scene
    c = load_clip(h, clip) if isinstance(clip, str) else clip
    fps_i, fps_base = scene.render.fps, scene.render.fps_base
    fps = fps_i / fps_base
    ppf = max(1, int(poses_per_frame))
    sf_asked = (60.0 * beats * fps / bpm) if bpm else c.duration * fps
    n = max(4, int(round(sf_asked * ppf)))
    sf = n / ppf
    ts = c.duration / (sf / fps)
    rec = {'clip': c.slot, 'bpm_asked': bpm, 'beats': beats, 'stride_frames': sf, 'poses_per_frame': ppf,
           'time_scale': round(ts, 5), 'stride_m': 0.0}
    keep = (scene.frame_start, scene.frame_end, scene.frame_current)
    scene.render.fps = fps_i * ppf
    try:
        play_vrma(h, c, t=0.0, loop=True, time_scale=ts)
        M = h.arm.matrix_world.copy()
        fb = bake_poses(h, list(range(1, n + 1)), lambda i, f: M, name or f'{c.slot}_loop', props, 'cycle', rec, curl)
    finally:
        scene.render.fps, scene.render.fps_base = fps_i, fps_base
        scene.frame_start, scene.frame_end = keep[0], keep[1]
        scene.frame_set(keep[2])
    fb.stride, fb.stride_frames = 0.0, sf
    log('loop', {k: v for k, v in fb.record.items() if not isinstance(v, (list, dict))})
    return fb


def once_flipbook(h, clip, every=2, props=(), curl=None, name=None, log=_log):
    """a one-shot clip played once from its start, baked every `every` film frames -> a Flipbook (kind 'once'). The pose
    frame is the donor's own (place it at the origin, unturned)."""
    scene = bpy.context.scene
    c = load_clip(h, clip) if isinstance(clip, str) else clip
    fps = scene.render.fps / scene.render.fps_base
    play_vrma(h, c, t=0.0, loop=False)
    last = 1 + int(round(c.duration * fps))
    frames = list(range(1, last, max(1, int(every))))
    if frames[-1] != last:
        frames.append(last)
    M = h.arm.matrix_world.copy()
    rec = {'clip': c.slot, 'every': int(every), 'clip_frames': last, 'pose_frames': frames}
    keep = scene.frame_current
    try:
        fb = bake_poses(h, frames, lambda i, f: M, name or f'{c.slot}_once', props, 'once', rec, curl)
    finally:
        scene.frame_set(keep)
    log('once', {k: v for k, v in fb.record.items() if not isinstance(v, (list, dict))})
    return fb


def drop_donor(h):
    """remove the donor body (its objects, collection and actions): only the flipbook's plain meshes stay"""
    acts = set()
    ad = h.arm.animation_data
    if ad is not None:
        if ad.action is not None:
            acts.add(ad.action)
        for tr in ad.nla_tracks:
            for st in tr.strips:
                if st.action is not None:
                    acts.add(st.action)
    for o in list(h.objects):
        if o.name in bpy.data.objects:
            bpy.data.objects.remove(o, do_unlink=True)
    if h.collection is not None and h.collection.name in bpy.data.collections and not h.collection.objects:
        bpy.data.collections.remove(h.collection)
    for a in acts:
        if a.users == 0:
            bpy.data.actions.remove(a)


# ------------------------------------------------------------------------------------------------------ the instancers
class _Nodes:
    def __init__(self, ng):
        self.ng, self.N, self.L = ng, ng.nodes, ng.links

    def m(self, op, a=None, b=None, va=None, vb=None):
        x = self.N.new('ShaderNodeMath')
        x.operation = op
        for i, (s, v) in enumerate(((a, va), (b, vb))):
            if s is not None:
                self.L.new(s, x.inputs[i])
            elif v is not None:
                x.inputs[i].default_value = v
        return x.outputs[0]

    def attr(self, name, default=None):
        x = self.N.new('GeometryNodeInputNamedAttribute')
        x.data_type = 'FLOAT'
        x.inputs['Name'].default_value = name
        if default is None:
            return x.outputs['Attribute']
        # a missing attribute reads 0: here it reads `default`
        miss = self.m('SUBTRACT', va=1.0, b=x.outputs['Exists'])
        return self.m('ADD', self.m('MULTIPLY', x.outputs['Attribute'], x.outputs['Exists']), self.m('MULTIPLY', miss, vb=default))


def _group(name, inputs):
    ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    it = ng.interface
    it.new_socket(name='Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    for nm, kind, default in inputs:
        s = it.new_socket(name=nm, in_out='INPUT', socket_type=kind)
        s.default_value = default
    it.new_socket(name='Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    gi, go = ng.nodes.new('NodeGroupInput'), ng.nodes.new('NodeGroupOutput')
    return ng, gi, go


def _clock(X, gi):
    """the frame each point plays: the scene's frame + Frame Offset, held from its own 'stop' on, and the hold (Hold From,
    Hold Frames) taken out: before the hold as it is, through it the hold's first frame, after it Hold Frames earlier"""
    st = X.N.new('GeometryNodeInputSceneTime')
    f = X.m('ADD', st.outputs['Frame'], gi.outputs['Frame Offset'])
    f1 = X.m('MINIMUM', f, X.attr('stop', FAR))
    held = X.m('MAXIMUM', X.m('MINIMUM', X.m('SUBTRACT', f1, gi.outputs['Hold From']), gi.outputs['Hold Frames']), vb=0.0)
    return f, X.m('SUBTRACT', f1, held)


def _window(X, gi, geo, f):
    out_ = X.m('MAXIMUM', X.m('LESS_THAN', f, gi.outputs['Show From']), X.m('GREATER_THAN', f, gi.outputs['Show To']))
    dl = X.N.new('GeometryNodeDeleteGeometry')
    dl.domain = 'POINT'
    X.L.new(geo, dl.inputs['Geometry'])
    X.L.new(out_, dl.inputs['Selection'])
    return dl.outputs['Geometry']


def _instances(X, fb, points, idx, rot):
    outs = []
    for col in fb.layers():
        reset = col not in fb.props.values()                    # (a prop keeps its place in the pose)
        ci = X.N.new('GeometryNodeCollectionInfo')
        ci.inputs['Collection'].default_value = col
        ci.inputs['Separate Children'].default_value = True
        ci.inputs['Reset Children'].default_value = reset
        iop = X.N.new('GeometryNodeInstanceOnPoints')
        X.L.new(points, iop.inputs['Points'])
        X.L.new(ci.outputs[0], iop.inputs['Instance'])
        iop.inputs['Pick Instance'].default_value = True
        X.L.new(idx, iop.inputs['Instance Index'])
        X.L.new(rot, iop.inputs['Rotation'])
        outs.append(iop.outputs['Instances'])
    jn = X.N.new('GeometryNodeJoinGeometry')
    for o in outs:
        X.L.new(o, jn.inputs[0])
    return jn.outputs[0]


def _common_inputs(show, hold, frame_offset):
    show = show or (-FAR, FAR)
    hold = hold or (FAR, 0.0)
    return [('Frame Offset', 'NodeSocketFloat', float(frame_offset)), ('Show From', 'NodeSocketFloat', float(show[0])),
            ('Show To', 'NodeSocketFloat', float(show[1])), ('Hold From', 'NodeSocketFloat', float(hold[0])),
            ('Hold Frames', 'NodeSocketFloat', float(hold[1]))]


def column_group(fb, ref_frame=1.0, show=None, hold=None, frame_offset=0.0, name=None):
    """the node group for a cycle Flipbook: every point plays the cycle from Ref Frame (a frame its left heel strikes on)
    and is carried forward by its stride -> the GeometryNodeTree. show: (first, last) frame; hold: (from, frames)."""
    if fb.kind != 'cycle':
        raise ValueError('crowd.column_group: a cycle flipbook (stride_cycle, loop_cycle); once_group plays a one-shot')
    ng, gi, go = _group(name or f'crowd.{fb.name}.column', [
        ('Poses', 'NodeSocketInt', fb.poses), ('Stride Frames', 'NodeSocketFloat', float(fb.stride_frames)),
        ('Ref Frame', 'NodeSocketFloat', float(ref_frame)), ('Stride', 'NodeSocketFloat', float(fb.stride))]
        + _common_inputs(show, hold, frame_offset))
    X = _Nodes(ng)
    f, fe = _clock(X, gi)
    pts = _window(X, gi, gi.outputs['Geometry'], f)
    ph = X.m('ADD', X.m('DIVIDE', X.m('SUBTRACT', fe, gi.outputs['Ref Frame']), gi.outputs['Stride Frames']), X.attr('dphase'))
    k = X.m('FLOOR', X.m('ADD', X.m('MULTIPLY', ph, gi.outputs['Poses']), vb=0.5))
    idx = X.m('SUBTRACT', k, X.m('MULTIPLY', X.m('FLOOR', X.m('DIVIDE', k, gi.outputs['Poses'])), gi.outputs['Poses']))
    idx = X.m('ADD', idx, vb=0.25)                             # (an exact integer whichever way the int socket rounds)
    travel = X.m('DIVIDE', X.m('MULTIPLY', k, gi.outputs['Stride']), gi.outputs['Poses'])
    yaw = X.attr('yaw')
    fwd = X.N.new('ShaderNodeCombineXYZ')                      # the front (-Y) turned by yaw: (sin yaw, -cos yaw, 0)
    X.L.new(X.m('MULTIPLY', X.m('SINE', yaw), travel), fwd.inputs['X'])
    X.L.new(X.m('MULTIPLY', X.m('MULTIPLY', X.m('COSINE', yaw), vb=-1.0), travel), fwd.inputs['Y'])
    sp = X.N.new('GeometryNodeSetPosition')
    X.L.new(pts, sp.inputs['Geometry'])
    X.L.new(fwd.outputs[0], sp.inputs['Offset'])
    rz = X.N.new('ShaderNodeCombineXYZ')
    X.L.new(yaw, rz.inputs['Z'])
    rot = X.N.new('FunctionNodeEulerToRotation')
    X.L.new(rz.outputs[0], rot.inputs[0])
    X.L.new(_instances(X, fb, sp.outputs['Geometry'], idx, rot.outputs[0]), go.inputs[0])
    ng['crowd'] = json.dumps({'kind': 'column', 'flipbook': fb.name, 'poses': fb.poses, 'stride_m': fb.stride,
                              'stride_frames': fb.stride_frames, 'ref_frame': float(ref_frame)})
    return ng


def once_group(fb, show=None, hold=None, frame_offset=0.0, name=None):
    """the node group for a one-shot Flipbook: every point plays it from its 'start' frame -> the GeometryNodeTree"""
    if fb.kind != 'once':
        raise ValueError('crowd.once_group: a one-shot flipbook (once_flipbook); column_group plays a cycle')
    ng, gi, go = _group(name or f'crowd.{fb.name}.once', [
        ('Poses', 'NodeSocketInt', fb.poses), ('Every', 'NodeSocketFloat', float(fb.every))]
        + _common_inputs(show, hold, frame_offset))
    X = _Nodes(ng)
    f, fe = _clock(X, gi)
    pts = _window(X, gi, gi.outputs['Geometry'], f)
    t = X.m('SUBTRACT', fe, X.attr('start'))
    i = X.m('FLOOR', X.m('DIVIDE', t, gi.outputs['Every']))
    i = X.m('MINIMUM', X.m('MAXIMUM', i, vb=0.0), X.m('SUBTRACT', gi.outputs['Poses'], vb=1.0))
    i = X.m('ADD', i, vb=0.25)
    rz = X.N.new('ShaderNodeCombineXYZ')
    X.L.new(X.attr('yaw'), rz.inputs['Z'])
    rot = X.N.new('FunctionNodeEulerToRotation')
    X.L.new(rz.outputs[0], rot.inputs[0])
    X.L.new(_instances(X, fb, pts, i, rot.outputs[0]), go.inputs[0])
    ng['crowd'] = json.dumps({'kind': 'once', 'flipbook': fb.name, 'poses': fb.poses, 'every': fb.every})
    return ng


# ------------------------------------------------------------------------------------------------------ the points
def formation(files, ranks, interval=0.75, distance=0.95, origin=(0.0, 0.0, 0.0), heading=0.0, jitter=None):
    """a column at its phase 0: `files` abreast `interval` m apart, `ranks` one behind another `distance` m apart, the
    head rank's middle at `origin`, marching toward `heading` (degrees about +Z; 0 marches toward -Y, a VRM's front).
    jitter: {'lateral': m, 'along': m, 'phase': strides, 'seed': n}, each uniform in +-that -> [point dict]"""
    j = dict({'lateral': 0.0, 'along': 0.0, 'phase': 0.0, 'seed': 1}, **(jitter or {}))
    rng = random.Random(j['seed'])
    yaw = math.radians(heading)
    fwd = Vector((math.sin(yaw), -math.cos(yaw), 0.0))
    left = Vector((-fwd.y, fwd.x, 0.0))
    o = Vector(origin)
    out = []
    for r in range(ranks):
        for fi in range(files):
            a = -r * distance + rng.uniform(-1.0, 1.0) * j['along']
            s = (fi - (files - 1) / 2.0) * interval + rng.uniform(-1.0, 1.0) * j['lateral']
            out.append({'p': tuple(o + fwd * a + left * s), 'yaw': yaw, 'dphase': rng.uniform(-1.0, 1.0) * j['phase'],
                        'rank': r, 'file': fi})
    return out


def grid(lines, units, line_pitch=2.4, unit_pitch=1.2, origin=(0.0, 0.0, 0.0), heading=0.0):
    """lines of units: a line's units side by side `unit_pitch` apart along the bodies' left, the lines one behind
    another `line_pitch` apart, every body facing `heading` (degrees; 0 faces -Y). Lines and units count from 1 ->
    [point dict]"""
    yaw = math.radians(heading)
    fwd = Vector((math.sin(yaw), -math.cos(yaw), 0.0))
    left = Vector((-fwd.y, fwd.x, 0.0))
    o = Vector(origin)
    out = []
    for ln in range(lines):
        for u in range(units):
            p = o - fwd * (ln * line_pitch) + left * ((u - (units - 1) / 2.0) * unit_pitch)
            out.append({'p': tuple(p), 'yaw': yaw, 'line': ln + 1, 'unit': u + 1})
    return out


def canon_starts(points, first, step_line, step_unit, order=None):
    """the canon as numbers: start = first + step_line x (the line's place in `order`, by default the lines in number
    order) + step_unit x (the unit's place in its line) -> [start frame, one a point]"""
    lines = sorted({p['line'] for p in points}, key=order)
    place = {ln: i for i, ln in enumerate(lines)}
    first_unit = {ln: min(p['unit'] for p in points if p['line'] == ln) for ln in lines}
    return [first + step_line * place[p['line']] + step_unit * (p['unit'] - first_unit[p['line']]) for p in points]


def crowd_object(name, points, group, collection=None, starts=None, stops=None):
    """ONE object, a point a body, its Geometry Nodes modifier 'crowd' running `group`. points: [{'p': (x, y, z), 'yaw':
    radians, 'dphase', 'rank', 'file', 'line', 'unit'}] (missing ones 0); starts / stops: a frame a point (stops: None
    or FAR where a body never stops alone) -> the object"""
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(p['p']) for p in points], [], [])
    n = len(points)
    cols = {'yaw': [float(p.get('yaw', 0.0)) for p in points], 'dphase': [float(p.get('dphase', 0.0)) for p in points],
            'start': [float(s) for s in (starts or [0.0] * n)],
            'stop': [float(FAR if s is None else s) for s in (stops or [None] * n)]}
    for k, vals in cols.items():
        a = me.attributes.new(k, 'FLOAT', 'POINT')
        a.data.foreach_set('value', vals)
    for k in ('rank', 'file', 'line', 'unit'):
        if any(k in p for p in points):
            a = me.attributes.new(k, 'INT', 'POINT')
            a.data.foreach_set('value', [int(p.get(k, 0)) for p in points])
    ob = bpy.data.objects.new(name, me)
    md = ob.modifiers.new('crowd', 'NODES')
    md.node_group = group
    (collection or bpy.context.scene.collection).objects.link(ob)
    return ob


# ------------------------------------------------------------------------------------------------------ the checks
def instances_at(ob, frame, prefix=None):
    """the crowd object's evaluated instances on `frame` -> [(the instanced object's name, its world matrix)], in point
    order; prefix: only objects whose name starts with it (a flipbook's bodies: 'crowd.<name>.body.')"""
    bpy.context.scene.frame_set(int(frame))
    dg = bpy.context.evaluated_depsgraph_get()
    out = []
    for inst in dg.object_instances:
        if inst.is_instance and inst.parent is not None and inst.parent.original == ob:
            nm = inst.object.original.name
            if prefix is None or nm.startswith(prefix):
                out.append((nm, inst.matrix_world.copy()))
    return out


def feet_slide(ob, fb, frames, point=0, floor=0.0025, touch=0.0004):
    """ONE body's planted feet in the world, frame after frame (the measure walk_path's report makes): a foot is down on
    a frame when its lowest vertex is within `touch` of the pose frame's floor; on each side (+X its left) down on two
    frames running, the vertices within `floor` on both are the contact, and a planted foot's contact does not slip, so
    the least move among them (a sole rolling about its heel or ball keeps that point still) is the slip. A heel still
    coming down or a toe lifting off is not down -> {'worst_slide_mm' (the slip, the worst pair), 'worst_spread_mm' (the
    largest move of any contact vertex: the roll), 'pairs', 'frames'}"""
    prefix = f'crowd.{fb.name}.body.'
    worst, spread, prev, looked = 0.0, 0.0, None, 0
    for f in frames:
        bodies = instances_at(ob, f, prefix)
        if len(bodies) <= point:
            prev = None
            continue
        name, M = bodies[point]
        me = bpy.data.objects[name].data
        co = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)
        low = np.where(co[:, 2] < floor)[0]
        W = np.array(M)
        w = co[low] @ W[:3, :3].T + W[:3, 3]
        cur = {}
        for s, sel in (('left', co[low, 0] > 0), ('right', co[low, 0] < 0)):
            ids = low[sel]
            cur[s] = set(ids.tolist()) if len(ids) and co[ids, 2].min() < touch else set()
        pos = dict(zip(low.tolist(), w))
        if prev is not None:
            for s in ('left', 'right'):
                both = cur[s] & prev[0][s]
                if len(both) >= 3:
                    d = [float(np.linalg.norm(pos[i][:2] - prev[1][i][:2])) for i in both]
                    worst = max(worst, min(d) * 1000.0)
                    spread = max(spread, max(d) * 1000.0)
                    looked += 1
        prev = (cur, pos)
    return {'worst_slide_mm': round(worst, 3), 'worst_spread_mm': round(spread, 3), 'pairs': looked,
            'frames': [frames[0], frames[-1]]}


def shown_poses(ob, fb, frame):
    """the pose each point shows on `frame` against the one its attributes and the group's inputs ask for (the group's
    own values: a crowd whose modifier overrides an input is measured against the group's) -> {'points', 'found',
    'wrong'}"""
    ng = ob.modifiers['crowd'].node_group
    inp = {s.name: s.default_value for s in ng.interface.items_tree if getattr(s, 'in_out', '') == 'INPUT'
           and s.name != 'Geometry'}
    me = ob.data
    n = len(me.vertices)

    def col(k, d=0.0):
        a = me.attributes.get(k)
        if a is None:
            return [d] * n
        v = np.empty(n, np.float32)
        a.data.foreach_get('value', v)
        return v.tolist()
    start, stop, dph = col('start'), col('stop', FAR), col('dphase')
    f = frame + inp['Frame Offset']
    want = []
    for i in range(n):
        f1 = min(f, stop[i])
        fe = f1 - max(min(f1 - inp['Hold From'], inp['Hold Frames']), 0.0)
        if fb.kind == 'once':
            want.append(int(min(max(math.floor((fe - start[i]) / inp['Every']), 0), inp['Poses'] - 1)))
        else:
            ph = (fe - inp['Ref Frame']) / inp['Stride Frames'] + dph[i]
            want.append(int(math.floor(ph * inp['Poses'] + 0.5)) % int(inp['Poses']))
    got = [int(nm.rsplit('.', 1)[1]) for nm, _M in instances_at(ob, frame, f'crowd.{fb.name}.body.')]
    return {'points': n, 'found': len(got), 'wrong': sum(1 for a, b in zip(want, got) if a != b) + abs(len(got) - n),
            'want_first': want[:6], 'got_first': got[:6]}
