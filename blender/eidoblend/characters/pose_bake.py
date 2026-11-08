"""eidoblend.characters.pose_bake: solve a performance ONCE, then play it back for nothing (eidoverse/pose_bake.js).

    from eidoblend.characters import pose_bake as PB
    tracks = [PB.track(name, target) ...]           # a Blender object, (VRMHandle, humanoid name), or None (unbound)
    bake = PB.create_pose_bake(tracks=tracks, morphs=[PB.morph('face', mesh_obj)], frames=N, fps=30,
                               file='E:/proj/work/bake/perf_<key>.bin', key=PB.bake_key([...source and data files]))
    if not bake.load():
        for k in range(N):
            pose_live(k)                            # whatever solves the frame and writes the targets (or frame_set)
            bake.record(k)
        bake.save()
    bake.key(frame_start=1)                         # the whole bake as keyed actions: the .blend plays it alone
    # or per frame, as the JS: bake.apply(k); bake.apply_morphs(k)

The WebGPU edition records what a live solve WRITES each frame (the local transforms of the bones and props it moves,
and morph weights) into one binary file, and every render after that copies frame k back. This edition reads and writes
THE SAME FILES: the values are three.js's (Y-up local transforms: position, quaternion x y z w, scale; morph influences),
the format is the JS's byte for byte ('EIDO-POSEBAKE-1': a little-endian uint32 header length, the JSON header padded
with spaces to 4 bytes, then float32 frames of the columns that move; the columns that never move stored once in the
header), and the key is the JS's bakeKey for the same files and extra string. So a bake solved in either edition plays
in the other (the shipped eidoverse/assets/animations/ska_band bakes play here: tests/robot_body/test_pose_bake.py).

Targets and the change of axes (three (x, y, z) -> Blender (x, -z, y): C = +90 deg about X):
    an Object          its matrix_basis is C T C^-1 for three's local T: location (x, -z, y), the quaternion conjugated
                       (w, x, -z, y), scale (sx, sz, sy). Bind objects whose parent inverse is the identity (the glTF
                       importer's, or made so): then a three parent / child pair maps to the same Blender pair
    (h, 'leftUpperArm') a VRM's NORMALIZED humanoid bone (three-vrm's normalizedHumanBones[name].node): its rotation
                       through the handle (VRMHandle.basis_from_normalized), the hips' position as the hips' offset
                       from its rest; the other bones' positions are their rest offsets (written once, never moved)
    None               an unbound track: kept in the file, read as the rest (0, identity, 1), never applied
Morphs: a mesh object's shape keys after the basis, in order (three's morphTargetInfluences).

FACES: bake the body, drive the face live (a face is cheap and a function of time); morphs are for a morph with no live
driver. The key must change whenever anything the solve reads changes (its source, its data, the assets): bake_key
hashes file contents (sources) and size + mtime (assets of 4 MB or more); a stale bake is refused, never played. A scene
file that holds the performance AND its rendering marks what the solve never reads, and those regions drop out of its
key: /* bake-key: skip */ ... /* bake-key: end */ in .js / .mjs / .ts (the JS's markers), and in Python, lines
`# bake-key: skip` ... `# bake-key: end` (this edition's, for its scene scripts; anything unmarked counts).
"""

import hashlib
import json
import math
import os
import re
import struct

import numpy as np

MAGIC = 'EIDO-POSEBAKE-1'
SKIP_JS = re.compile(r'/\* bake-key: skip \*/[\s\S]*?/\* bake-key: end \*/')
SKIP_PY = re.compile(r'[ \t]*#[ \t]*bake-key: skip[^\n]*\n[\s\S]*?#[ \t]*bake-key: end[^\n]*')
_KEYED = re.compile(r'[0-9a-f]{24}\.bin$')


def bake_key(files, extra=''):
    """bakeKey(files, extra): a 24-hex key over the files' contents (size + mtime for 4 MB or more; 'missing' for a file
    that is not there) and `extra` (the solve's settings), the JS's exactly for the same path strings"""
    parts = [extra]
    for f in files:
        try:
            st = os.stat(f)
            if st.st_size >= 4e6:
                parts.append(f'{f}:{st.st_size}:{st.st_mtime_ns // 1000000}')
                continue
            with open(f, 'rb') as fh:
                data = fh.read()
            if re.search(r'\.(m?js|ts)$', f, re.I):
                data = SKIP_JS.sub('', data.decode('utf-8', errors='replace')).encode('utf-8')
            elif f.lower().endswith('.py'):
                data = SKIP_PY.sub('', data.decode('utf-8', errors='replace')).encode('utf-8')
            parts.append(f'{f}:{hashlib.sha256(data).hexdigest()}')
        except OSError:
            parts.append(f'{f}:missing')
    return hashlib.sha256('\n'.join(parts).encode('utf-8')).hexdigest()[:24]


def bake_header(file):
    """bakeHeader(file): a bake's header without its data: {magic, key, frames, fps, full, cols, consts, tracks, morphs}.
    To play a SHIPPED bake bind targets to its track names in this order and pass its key"""
    with open(file, 'rb') as fh:
        hl = struct.unpack('<I', fh.read(4))[0]
        return json.loads(fh.read(hl).decode('utf-8'))


# ------------------------------------------------------------------------------------------------------------ targets
def _v_to_three(v):
    return (v[0], v[2], -v[1])


def _v_from_three(v):
    return (v[0], -v[2], v[1])


class ObjectTarget:
    """a Blender object as three's Object3D: its local transform (matrix_basis) in three's axes"""

    def __init__(self, obj):
        self.obj = obj

    def read(self):
        from mathutils import Quaternion  # noqa: F401
        loc, rot, sc = self.obj.matrix_basis.decompose()
        return (*_v_to_three(loc), rot.x, rot.z, -rot.y, rot.w, sc[0], sc[2], sc[1])

    def write(self, v):
        from mathutils import Matrix, Quaternion, Vector
        loc = Vector(_v_from_three(v[0:3]))
        q = Quaternion((v[6], v[3], -v[5], v[4]))
        S = Matrix.Diagonal((v[7], v[9], v[8], 1.0))
        self.obj.matrix_basis = Matrix.Translation(loc) @ q.normalized().to_matrix().to_4x4() @ S

    def channels(self, v):
        """the Blender channels for one stored frame: [(id, data path, index, value)]"""
        from mathutils import Quaternion
        loc = _v_from_three(v[0:3])
        q = Quaternion((v[6], v[3], -v[5], v[4])).normalized()
        out = [(self.obj, 'location', i, loc[i]) for i in range(3)]
        out += [(self.obj, 'rotation_quaternion', i, q[i]) for i in range(4)]
        out += [(self.obj, 'scale', i, s) for i, s in enumerate((v[7], v[9], v[8]))]
        return out

    def prepare(self):
        self.obj.rotation_mode = 'QUATERNION'


class NormalizedBoneTarget:
    """a VRM's normalized humanoid bone (h: eidoblend.characters.vrm.VRMHandle; name: 'hips', 'leftUpperArm', ...)"""

    def __init__(self, h, name):
        self.h, self.name = h, name
        self.bone = h.humanoid[name]
        p = h.arm.data.bones[self.bone].parent
        by_bone = {b: n for n, b in h.humanoid.items()}
        while p is not None and p.name not in by_bone:
            p = p.parent
        self.parent = p.name if p is not None else None
        self.is_hips = name == 'hips'

    def _rest_offset(self):
        h = self.h
        head = h.rest_head[self.bone]
        return head if self.parent is None else head - h.rest_head[self.parent]

    def read(self):
        from ._math import q_to_three
        h = self.h
        pb = h.arm.pose.bones[self.bone]
        q = q_to_three(h.normalized_from_basis(self.bone, pb.rotation_quaternion))
        off = self._rest_offset()
        if self.is_hips:
            off = off + h.rest_q[self.bone] @ pb.location
        p = _v_to_three(off)
        return (*p, q.x, q.y, q.z, q.w, 1.0, 1.0, 1.0)

    def _basis(self, v):
        from mathutils import Quaternion, Vector
        from ._math import q_from_three
        h = self.h
        q = q_from_three(Quaternion((v[6], v[3], v[4], v[5])).normalized())
        bq = h.basis_from_normalized(self.bone, q)
        loc = None
        if self.is_hips:
            loc = h.rest_q[self.bone].inverted() @ (Vector(_v_from_three(v[0:3])) - self.h.rest_head[self.bone])
        return bq, loc

    def write(self, v):
        bq, loc = self._basis(v)
        pb = self.h.arm.pose.bones[self.bone]
        pb.rotation_quaternion = bq
        if loc is not None:
            pb.location = loc

    def channels(self, v):
        bq, loc = self._basis(v)
        arm, b = self.h.arm, self.bone
        out = [(arm, f'pose.bones["{b}"].rotation_quaternion', i, bq[i]) for i in range(4)]
        if loc is not None:
            out += [(arm, f'pose.bones["{b}"].location', i, loc[i]) for i in range(3)]
        return out

    def prepare(self):
        self.h.arm.pose.bones[self.bone].rotation_mode = 'QUATERNION'


class Unbound:
    """a track kept in the file but bound to nothing here (read as the rest, never applied)"""

    def read(self):
        return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0)

    def write(self, v):
        pass

    def channels(self, v):
        return []

    def prepare(self):
        pass


def target_of(obj):
    if obj is None:
        return Unbound()
    if isinstance(obj, (ObjectTarget, NormalizedBoneTarget, Unbound)):
        return obj
    if isinstance(obj, tuple) and len(obj) == 2:
        return NormalizedBoneTarget(*obj)
    return ObjectTarget(obj)


def track(name, obj):
    """{name, obj}: obj a Blender object, (VRMHandle, humanoid name), a target, or None"""
    return {'name': name, 'obj': obj}


def morph(name, mesh):
    """{name, mesh}: a mesh object whose shape keys (after the basis) are the influences"""
    return {'name': name, 'mesh': mesh}


def _keys(mesh):
    sk = mesh.data.shape_keys if mesh is not None else None
    return list(sk.key_blocks)[1:] if sk else []


def _jsnum(x):
    """a number as JSON.stringify writes it (integral floats without '.0', -0 as 0, NaN and Infinity as null)"""
    if isinstance(x, float):
        if not math.isfinite(x):
            return None
        if x == int(x) and abs(x) < 1e21:
            return int(x)
    return x


# ------------------------------------------------------------------------------------------------------------ the bake
class PoseBake:
    """createPoseBake's object: record, save, load, apply, apply_morphs, release, ready, frames, fps; and key(), this
    edition's: the bake written into keyed actions on every bound target"""

    def __init__(self, tracks=(), morphs=(), frames=0, fps=30, file=None, key=None):
        self.tracks = [{'name': t['name'], 'target': target_of(t.get('obj'))} for t in tracks]
        self.morphs = list(morphs)
        self.frames, self.fps, self.file, self.key_ = int(frames), fps, file, key
        self.T = len(self.tracks)
        self.mN = [len(_keys(m['mesh'])) for m in self.morphs]
        self.full = self.T * 10 + sum(self.mN)
        self._rec = None
        self._recorded = 0
        self._play = None

    @property
    def ready(self):
        return self._play is not None

    def record(self, k):
        """the targets' current values as frame k (the live solve has just written them, or frame_set(k) showed them)"""
        if self._rec is None:
            self._rec = np.zeros((self.frames, self.full), dtype=np.float32)
        row = []
        for t in self.tracks:
            row.extend(t['target'].read())
        for m, n in zip(self.morphs, self.mN):
            row.extend(kb.value for kb in _keys(m['mesh'])[:n])
        self._rec[k] = np.array(row, dtype=np.float32)
        self._recorded = max(self._recorded, k + 1)

    def save(self):
        """prune the columns that never change, write the file (the JS's layout), supersede older bakes of the same
        performance (the same name before the key), and play from it -> {tracks, columns, of, mb}"""
        if self._rec is None or self._recorded < self.frames:
            raise RuntimeError(f'[bake] save: {self._recorded} of {self.frames} frames recorded')
        rec = self._rec
        varies = np.any(rec != rec[0:1], axis=0)
        cols = [int(c) for c in np.nonzero(varies)[0]]
        consts = {str(c): _jsnum(float(rec[0, c])) for c in range(self.full) if not varies[c]}
        data = np.ascontiguousarray(rec[:, cols], dtype='<f4')
        header = {'magic': MAGIC, 'key': self.key_, 'frames': self.frames, 'fps': _jsnum(float(self.fps)),
                  'full': self.full, 'cols': cols, 'consts': consts, 'tracks': [t['name'] for t in self.tracks],
                  'morphs': [{'name': m['name'], 'n': n} for m, n in zip(self.morphs, self.mN)]}
        hb = json.dumps(header, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')
        pad = (4 - ((4 + len(hb)) % 4)) % 4
        d = os.path.dirname(self.file)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(self.file, 'wb') as fh:
            fh.write(struct.pack('<I', len(hb) + pad))
            fh.write(hb)
            fh.write(b' ' * pad)
            fh.write(data.tobytes())
        base = os.path.basename(self.file)
        stem = _KEYED.sub('', base)
        if stem != base and d:
            for e in os.listdir(d):
                if e != base and e.startswith(stem) and _KEYED.search(e) and os.path.isfile(os.path.join(d, e)):
                    os.remove(os.path.join(d, e))
        self._rec = None
        self._setup(header, data)
        return {'tracks': self.T, 'columns': len(cols), 'of': self.full, 'mb': (4 + len(hb) + pad + data.nbytes) / 1e6}

    def load(self):
        """a bake made for exactly these tracks and morphs and this key; anything else is refused (False)"""
        try:
            with open(self.file, 'rb') as fh:
                raw = fh.read()
        except OSError:
            return False
        hl = struct.unpack('<I', raw[:4])[0]
        header = json.loads(raw[4:4 + hl].decode('utf-8'))
        same = (len(header['tracks']) == self.T and all(n == t['name'] for n, t in zip(header['tracks'], self.tracks))
                and len(header['morphs']) == len(self.morphs)
                and all(m['name'] == mm['name'] and m['n'] == n for m, mm, n in zip(header['morphs'], self.morphs, self.mN)))
        if header.get('magic') != MAGIC or header.get('key') != self.key_ or header.get('frames') != self.frames or not same:
            return False
        nc = len(header['cols'])
        data = np.frombuffer(raw, dtype='<f4', count=header['frames'] * nc, offset=4 + hl).reshape(header['frames'], nc)
        self._setup(header, data)
        return True

    def _setup(self, header, data):
        full = header['full']
        table = np.zeros((header['frames'], full), dtype=np.float32)
        for c, v in header['consts'].items():
            table[:, int(c)] = np.nan if v is None else v
        if header['cols']:
            table[:, header['cols']] = data
        self._play = {'header': header, 'table': table}

    def values(self, k):
        """frame k's full row (every column), clamped into the bake"""
        k = max(0, min(self.frames - 1, int(k)))
        return self._play['table'][k]

    def apply(self, k):
        """frame k's transforms written to the targets"""
        if self._play is None:
            return False
        row = self.values(k)
        for i, t in enumerate(self.tracks):
            t['target'].write([float(x) for x in row[i * 10:i * 10 + 10]])
        return True

    def apply_morphs(self, k):
        """frame k's morph weights written to the shape keys"""
        if self._play is None:
            return False
        row, c = self.values(k), self.T * 10
        for m, n in zip(self.morphs, self.mN):
            for kb in _keys(m['mesh'])[:n]:
                kb.value = float(row[c])
                c += 1
        return True

    def release(self):
        """release(): the JS suspends a mesh's draw-time face hook (onBeforeRender) while playing; Blender has no draw-time
        hooks (a face is keyed or driven), so there is nothing to give back"""
        return None

    def key(self, frame_start=1, frames=None, name='pose_bake', tracks=None, morphs=True):
        """the bake as keyed data: every bound target's channels LINEAR at frame_start + k (k in `frames`, default all),
        quaternions kept on one hemisphere so the interpolation never takes the long way; morphs keyed on their shape
        keys. Only the columns that move are keyed per frame; a constant column is set once. -> {fcurves, keys}"""
        if self._play is None:
            raise RuntimeError('[bake] key: nothing loaded or saved')
        import bpy
        from bpy_extras import anim_utils
        ks = list(range(self.frames)) if frames is None else list(frames)
        moving = np.zeros(self.full, dtype=bool)
        moving[self._play['header']['cols']] = True
        series = {}
        statics = []
        want = set(tracks) if tracks else None
        for i, t in enumerate(self.tracks):
            if want is not None and t['name'] not in want:
                continue
            tgt = t['target']
            if isinstance(tgt, Unbound):
                continue
            tgt.prepare()
            if not moving[i * 10:i * 10 + 10].any():
                statics.append((tgt, self.values(0)[i * 10:i * 10 + 10]))
                continue
            prev = {}
            for k in ks:
                v = [float(x) for x in self.values(k)[i * 10:i * 10 + 10]]
                ch = tgt.channels(v)
                quat = {}
                for idb, path, idx, val in ch:
                    if path.endswith('rotation_quaternion'):
                        quat.setdefault(path, [None] * 4)[idx] = val
                for path, q in quat.items():
                    p = prev.get(path)
                    if p is not None and sum(a * b for a, b in zip(p, q)) < 0:
                        q = [-x for x in q]
                    prev[path] = q
                    quat[path] = q
                for idb, path, idx, val in ch:
                    if path in quat:
                        val = quat[path][idx]
                    series.setdefault((idb.name, path, idx), [idb, []])[1].append((frame_start + k, val))
        for tgt, v in statics:
            tgt.write([float(x) for x in v])
        nkeys = 0
        bags = {}
        for (_n, path, idx), (idb, kv) in series.items():
            cb = bags.get(idb.name)
            if cb is None:
                ad = idb.animation_data or idb.animation_data_create()
                if ad.action is None:
                    ad.action = bpy.data.actions.new(f'{name}|{idb.name}')
                if ad.action_slot is None:
                    ad.action_slot = (ad.action.slots[0] if len(ad.action.slots)
                                      else ad.action.slots.new(id_type='OBJECT', name=idb.name))
                cb = bags[idb.name] = anim_utils.action_ensure_channelbag_for_slot(ad.action, ad.action_slot)
            grp = path.split('"')[1] if path.startswith('pose.bones') else 'Object Transforms'
            fc = cb.fcurves.find(path, index=idx) or cb.fcurves.new(path, index=idx, group_name=grp)
            fc.keyframe_points.clear()
            fc.keyframe_points.add(len(kv))
            fc.keyframe_points.foreach_set('co', [c for f, v in kv for c in (f, v)])
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'
            fc.update()
            nkeys += len(kv)
        if morphs and self.morphs:
            row_c = self.T * 10
            for m, n in zip(self.morphs, self.mN):
                kbs = _keys(m['mesh'])[:n]
                for j, kb in enumerate(kbs):
                    c = row_c + j
                    if not moving[c]:
                        kb.value = float(self.values(0)[c])
                        continue
                    for k in ks:
                        kb.value = float(self.values(k)[c])
                        kb.keyframe_insert('value', frame=frame_start + k)
                        nkeys += 1
                row_c += n
        return {'fcurves': len(series), 'keys': nkeys, 'static_tracks': len(statics)}


def create_pose_bake(tracks=(), morphs=(), frames=0, fps=30, file=None, key=None):
    """createPoseBake(THREE, {tracks, morphs, frames, fps, file, key}) (three's module argument does not apply here)"""
    return PoseBake(tracks, morphs, frames, fps, file, key)
