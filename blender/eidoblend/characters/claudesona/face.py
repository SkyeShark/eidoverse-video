"""eidoblend.characters.claudesona.face: claudesona_face.js in Blender: the claudesona's face as digi modelled it
(claude_suit.vrm / claude_suit_wardrobe.vrm), its lipsync drivers and an emotion track keyed to words
(tools-guides/claudesona.md, "The face").

    from eidoblend.characters import load_vrm
    from eidoblend.characters.claudesona import face as F
    me = load_vrm('claude_suit')
    face = F.install_suit_mouth(me)                      # once, after load: re-seats the painted face, adds the mouth
    mouth = F.make_suit_mouth(input_max=0.35)            # 0.35 for lipsync.py timelines, 1 for voicebox visemes
    feel = F.make_face_track(TL, section_base={'chorus': {'smile': 0.5}}, line_cues=[(r'goodbye', {'soft': 0.8})])
    face.bake(lambda t: F.merge_max(mouth.update(t, vis_at(t)), feel.at(t)), 1, 240)   # keyed, every frame

WHY (as in the WebGPU module): the cat-smile, the eyes and the lines are painted plates on a white face dome; the
rig's own mouth (`show MMD mouth`) slides a flat black plate straight toward the camera and floats off the face past
about 1.1, and the painted features' expression targets swing parts of them up to ~12 mm off the dome. So
install_suit_mouth re-seats every painted feature (at rest and at the end of every expression target) onto the dome
along its depth axis, `feature_standoff` proud (the blush `blush_standoff` proud), leaves every rig mouth shape at 0,
and gives the hidden mouth plate three shape keys of its own, each vertex raycast onto the face `standoff` proud:
'mouth.seat' (a sliver under the smile), 'mouth.wide' (sliver -> a full open mouth) and 'mouth.round' (sliver -> an
"oh"); the two openings are relative to the seat, as the WebGPU targets are deltas from it.

Keyed, not per frame: three's face.set(weights) writes morph influences before each render; here set() writes the
shape keys now and record()/flush() (or bake(fn, f0, f1)) key them, LINEAR, one action on the face mesh's shape keys,
so a saved .blend renders any frame. Every face shape key is keyed on every frame (zero where unset), as set() zeroes
them: the VRM add-on's expression previews are never keyed on this face, so its frame handler writes nothing.

Geometry: the VRM add-on imports the face primitives as one Blender mesh ('Body': material slots 'Material', its
'.001', 'BLUSH') bone-parented to the head; the runtime's thresholds (isMouthPlate, the smile's band, TOP) are in the
glTF geometry space, so the work happens there (Blender (x, y, z) -> three (x, z, -y)) on each slot's own vertices.
"""

import math
import re

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from . import _mesh as M

MOUTH_OPEN = 'mouthOpen'
MOUTH_ROUND = 'mouthRound'
SUIT_VISEMES = {
    'aa': {'open': 1.0, 'round': 0.0},
    'ee': {'open': 0.62, 'round': 0.0},
    'ih': {'open': 0.45, 'round': 0.0},
    'oh': {'open': 0.95, 'round': 0.8},
    'ou': {'open': 0.62, 'round': 1.0},
}
VOWELS = ('aa', 'ih', 'ou', 'ee', 'oh')
RIG_MOUTH = ('show MMD mouth', 'あ', 'い', 'う', 'え', 'お', 'JawOpen', 'A', 'I', 'U', 'E', 'O', 'LipFunnel', 'LipPucker',
             'vis_aa', 'vis_ih', 'vis_ou', 'vis_ee', 'vis_oh')
VISEME_SHAPES = {
    'seat': {'a': 10, 'bt': 0.7, 'bb': 0.7, 'n': 2, 'lift': 0},
    'AA': {'a': 25, 'bt': 4, 'bb': 22, 'n': 2.4, 'lift': 0},
    'E': {'a': 27, 'bt': 3, 'bb': 8, 'n': 3.0, 'lift': 5},
    'I': {'a': 23, 'bt': 2, 'bb': 4, 'n': 3.2, 'lift': 3},
    'O': {'a': 16, 'bt': 6, 'bb': 18, 'n': 2.0, 'lift': 0},
    'U': {'a': 10, 'bt': 3, 'bb': 7, 'n': 2.0, 'lift': 0},
    'FV': {'a': 19, 'bt': 1.2, 'bb': 3.5, 'n': 4.0, 'lift': -1},
    'L': {'a': 18, 'bt': 3, 'bb': 11, 'n': 2.4, 'lift': 1},
    'C': {'a': 21, 'bt': 2.5, 'bb': 9, 'n': 2.8, 'lift': 1},
    'CH': {'a': 14, 'bt': 3, 'bb': 9, 'n': 2.2, 'lift': 0},
    'MBP': {'a': 10, 'bt': 0, 'bb': 0, 'n': 2, 'lift': 0},
}
LINE_WARP = {
    'O': {'sx': 0.7, 'peak': 0, 'corner': 0, 'k': 1},
    'U': {'sx': 0.56, 'peak': 0, 'corner': 0, 'k': 1},
    'CH': {'sx': 0.76, 'peak': 0, 'corner': 0, 'k': 1},
    'L': {'sx': 0.92, 'peak': 0, 'corner': 0, 'k': 1},
    'MBP': {'sx': 0.9, 'peak': 0, 'corner': 0, 'k': 1},
}
VISEMES = [k for k in VISEME_SHAPES if k != 'seat']
PHONE_VISEME = {
    'AA': 'AA', 'AH': 'L', 'AE': 'AA', 'AY': 'AA', 'AW': 'AA', 'EH': 'E', 'EY': 'E', 'IY': 'I', 'IH': 'I', 'Y': 'I',
    'AO': 'O', 'OW': 'O', 'OY': 'O', 'UW': 'U', 'UH': 'U', 'W': 'U', 'ER': 'CH', 'R': 'CH', 'CH': 'CH', 'JH': 'CH',
    'SH': 'CH', 'ZH': 'CH', 'F': 'FV', 'V': 'FV', 'TH': 'L', 'DH': 'L', 'L': 'L', 'S': 'C', 'Z': 'C', 'T': 'C', 'D': 'C',
    'N': 'C', 'K': 'C', 'G': 'C', 'NG': 'C', 'HH': 'C', 'M': 'MBP', 'B': 'MBP', 'P': 'MBP',
}
KEY_PREFIX = 'claudesona.'           # the shape keys this module adds: claudesona.mouth.seat, claudesona.viseme.AA ...


def is_mouth_plate(P):
    """the hidden mouth plate's vertices (glTF geometry space): |x| < 0.03, 1.44 < y < 1.48, z < 0.095"""
    return (np.abs(P[:, 0]) < 0.03) & (P[:, 1] > 1.44) & (P[:, 1] < 1.48) & (P[:, 2] < 0.095)


# ------------------------------------------------------------------------------------------------ the face dome
def face_height_field(P, tris, res=384):
    """the face dome as a height field: z of the front-most surface over (x, y) (P: the face's vertices in the
    plate's geometry space, tris: its triangles) -> faceZ(x, y) (arrays; nan off the dome), bilinear"""
    x0, x1, y0, y1 = P[:, 0].min(), P[:, 0].max(), P[:, 1].min(), P[:, 1].max()
    gx = (P[:, 0] - x0) / (x1 - x0) * (res - 1)
    gy = (P[:, 1] - y0) / (y1 - y0) * (res - 1)
    H = np.full((res, res), -np.inf)
    for a, b, c in tris:
        ax, ay, bx, by, cx, cy = gx[a], gy[a], gx[b], gy[b], gx[c], gy[c]
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-12:
            continue
        ys = np.arange(max(0, math.floor(min(ay, by, cy))), min(res - 1, math.ceil(max(ay, by, cy))) + 1)
        xs = np.arange(max(0, math.floor(min(ax, bx, cx))), min(res - 1, math.ceil(max(ax, bx, cx))) + 1)
        if not len(ys) or not len(xs):
            continue
        X, Y = np.meshgrid(xs, ys)
        l1 = ((by - cy) * (X - cx) + (cx - bx) * (Y - cy)) / den
        l2 = ((cy - ay) * (X - cx) + (ax - cx) * (Y - cy)) / den
        l3 = 1.0 - l1 - l2
        ok = (l1 >= -1e-4) & (l2 >= -1e-4) & (l3 >= -1e-4)
        z = np.where(ok, l1 * P[a, 2] + l2 * P[b, 2] + l3 * P[c, 2], -np.inf)
        sub = H[ys[0]:ys[-1] + 1, xs[0]:xs[-1] + 1]
        np.maximum(sub, z, out=sub)

    def faceZ(x, y):
        x, y = np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64)
        fx, fy = (x - x0) / (x1 - x0) * (res - 1), (y - y0) / (y1 - y0) * (res - 1)
        out = np.full(fx.shape, np.nan)
        inside = (fx >= 0) & (fy >= 0) & (fx <= res - 1) & (fy <= res - 1)
        ix = np.minimum(res - 2, np.floor(np.where(inside, fx, 0)).astype(int))
        iy = np.minimum(res - 2, np.floor(np.where(inside, fy, 0)).astype(int))
        tx, ty = np.where(inside, fx, 0) - ix, np.where(inside, fy, 0) - iy
        h00, h10, h01, h11 = H[iy, ix], H[iy, ix + 1], H[iy + 1, ix], H[iy + 1, ix + 1]
        good = inside & np.isfinite(h00) & np.isfinite(h10) & np.isfinite(h01) & np.isfinite(h11)
        with np.errstate(invalid='ignore'):
            v = (h00 * (1 - tx) + h10 * tx) * (1 - ty) + (h01 * (1 - tx) + h11 * tx) * ty
        out[good] = v[good]
        return out
    return faceZ


def _ray_onto(Pface, tris):
    """three's Raycaster against the face, in the plate's space: (x, y) -> the first surface hit going -z from
    z = 0.4 (or None)"""
    bvh = BVHTree.FromPolygons([Vector(p) for p in Pface], [tuple(int(i) for i in t) for t in tris], epsilon=0.0)

    def hit(x, y):
        loc, _n, _i, _d = bvh.ray_cast(Vector((x, y, 0.4)), Vector((0.0, 0.0, -1.0)))
        return None if loc is None else loc.z
    return hit


class _Parts:
    """the plate (eyes + smile + mouth plate: material 'Material'), the face disc ('face') and the blush ('BLUSH')"""

    def __init__(self, h):
        self.h = h
        self.plate, self.plate_slot = M.find(h, 'Material', need_keys=True)
        self.face, self.face_slot = M.find(h, 'face')
        self.blush, self.blush_slot = M.find(h, 'BLUSH', need_keys=True)
        if self.plate is None or self.face is None:
            raise ValueError(f'claudesona face: {h.name} is not claude_suit.vrm / claude_suit_wardrobe.vrm '
                             '(no face plate with material "Material" and a face disc "face")')
        self.plate_idx = M.slot_vertices(self.plate, self.plate_slot)
        tm = M.to_space(self.face, self.plate)
        fidx = M.slot_vertices(self.face, self.face_slot)
        Pf = M.apply(tm, M.coords(self.face))
        self.face_tris = M.slot_triangles(self.face, self.face_slot)
        self.face_P = Pf
        self.face_z = face_height_field(Pf, self.face_tris)
        self.ray = _ray_onto(Pf, self.face_tris)
        self.face_vertices = len(fidx)

    def on_face(self, standoff):
        def f(x, y):
            z = self.ray(x, y)
            return (0.115 if z is None else z) + standoff
        return f


def conform_to_face(o, idx, plate, face_z, standoff, rest=True, band=0.012, all_targets=False, skip=None):
    """re-seat a mesh's painted features on the dome (three's conformToFace): idx are the vertices of its primitive;
    rest vertices within `band` of the dome move onto it (only when `rest`); every target endpoint a target moves
    from an on-face vertex (or any, `all_targets`) moves onto it too. The rig's mouth shapes are left as they are.
    Returns the number of vertices re-seated at rest and of target endpoints moved."""
    kb0 = M.ensure_basis(o)
    keys = o.data.shape_keys.key_blocks
    tm = M.to_space(o, plate)
    back = np.linalg.inv(tm)
    old_rest = M.key_coords(kb0)
    P = old_rest[idx]
    v = M.apply(tm, P)
    z = face_z(v[:, 0], v[:, 1])
    ok = ~np.isnan(z)
    if skip is not None:
        ok &= ~skip(v)
    on = ok & (np.abs(v[:, 2] - np.where(ok, z, 0.0)) < band)
    if rest:
        v[on, 2] = z[on] + standoff
    new_rest_sel = M.apply(back, v)
    new_rest = old_rest.copy()
    new_rest[idx] = new_rest_sel
    moved_ends = 0
    for kb in keys[1:]:
        co = M.key_coords(kb)
        D = co[idx] - P
        if kb.name in RIG_MOUTH:                               # never driven: its deltas kept on the new rest
            co[idx] = new_rest_sel + D
            M.set_key_coords(kb, co)
            continue
        moved = (D * D).sum(1) > 1e-12
        e = P + D
        sel = moved & (on | all_targets)
        if sel.any():
            eg = M.apply(tm, e[sel])
            ze = face_z(eg[:, 0], eg[:, 1])
            good = ~np.isnan(ze)
            eg[good, 2] = ze[good] + standoff
            e_sel = M.apply(back, eg)
            e[sel] = e_sel
            moved_ends += int(good.sum())
        co[idx] = np.where(moved[:, None], e, new_rest_sel)
        M.set_key_coords(kb, co)
    M.set_key_coords(kb0, new_rest)
    o.data.vertices.foreach_set('co', new_rest.ravel())
    o.data.update()
    return int(on.sum()), moved_ends


def _add_key(o, name, co, relative=None):
    kb = o.data.shape_keys.key_blocks.get(name) or o.shape_key_add(name=name, from_mix=False)
    M.set_key_coords(kb, co)
    if relative is not None:
        kb.relative_key = relative
    kb.slider_min, kb.slider_max = 0.0, 1.0
    kb.value = 0.0
    return kb


def _features(parts, feature_standoff, blush_standoff):
    plate = parts.plate
    n_rest, n_ends = conform_to_face(plate, parts.plate_idx, plate, parts.face_z, feature_standoff,
                                     skip=lambda v: is_mouth_plate(v))
    blush = None
    if parts.blush is not None:
        bidx = M.slot_vertices(parts.blush, parts.blush_slot)
        blush = conform_to_face(parts.blush, bidx, plate, parts.face_z, blush_standoff, rest=False, all_targets=True)
    return {'features_reseated': n_rest, 'target_ends_reseated': n_ends, 'blush': blush}


# ------------------------------------------------------------------------------------------------ the mouth
TOP = 1.4762            # the plate's top edge, just under the painted smile (glTF geometry space)


def _build_mouth_targets(parts, standoff, feature_standoff, blush_standoff):
    rep = _features(parts, feature_standoff, blush_standoff)
    plate = parts.plate
    tm = M.to_space(plate, plate)
    back = np.linalg.inv(tm)
    on_face = parts.on_face(standoff)
    kb0 = plate.data.shape_keys.key_blocks[0]
    rest_bl = M.key_coords(kb0)
    G = M.apply(tm, rest_bl[parts.plate_idx])
    mouth = parts.plate_idx[is_mouth_plate(G)]
    Gm = G[is_mouth_plate(G)]

    def at(x, y, sx, sy):
        X, Y = x * sx, TOP - (TOP - y) * sy
        return X, Y, on_face(X, Y)
    S, W, O = (np.empty_like(Gm) for _ in range(3))
    for i, (x, y, _z) in enumerate(Gm):
        S[i], W[i], O[i] = at(x, y, 0.55, 0.05), at(x, y, 1.55, 1.95), at(x, y, 0.95, 1.95)
    seat, wide, rnd = rest_bl.copy(), rest_bl.copy(), rest_bl.copy()
    seat[mouth], wide[mouth], rnd[mouth] = M.apply(back, S), M.apply(back, W), M.apply(back, O)
    ks = _add_key(plate, KEY_PREFIX + 'mouth.seat', seat)
    wide[~np.isin(np.arange(len(rest_bl)), mouth)] = seat[~np.isin(np.arange(len(rest_bl)), mouth)]
    rnd[~np.isin(np.arange(len(rest_bl)), mouth)] = seat[~np.isin(np.arange(len(rest_bl)), mouth)]
    _add_key(plate, KEY_PREFIX + 'mouth.wide', wide, relative=ks)
    _add_key(plate, KEY_PREFIX + 'mouth.round', rnd, relative=ks)
    rep.update({'mouth_plate_vertices': int(len(mouth)), 'face_vertices': parts.face_vertices})
    return rep


class _FaceBase:
    """set(weights) / record(frame, weights) / flush() / bake(fn, f0, f1) over the face plates' shape keys"""

    def __init__(self, h, parts, rep):
        self.h, self.parts, self.report = h, parts, rep
        self.plate = parts.plate
        self.plates = [o for o in h.meshes if o.data.shape_keys and len(o.data.shape_keys.key_blocks) > 1]
        self._weights = {}
        self._rec = {}

    @property
    def weights(self):
        return self._weights

    def _mouth(self, weights, out):
        raise NotImplementedError

    def values(self, weights):
        """{(object name, key name): value} for every face shape key under these weights (three's write())"""
        weights = weights or {}
        out = {}
        for p in self.plates:
            for kb in p.data.shape_keys.key_blocks[1:]:
                v = 0.0
                if kb.name in weights and kb.name not in RIG_MOUTH and isinstance(weights[kb.name], (int, float)):
                    v = float(weights[kb.name])
                out[(p.name, kb.name)] = v
        self._mouth(weights, out)
        return out

    def set(self, weights):
        """write `weights` now (every other face shape key to 0), unkeyed"""
        self._weights = dict(weights or {})
        for (on, kn), v in self.values(self._weights).items():
            bpy.data.objects[on].data.shape_keys.key_blocks[kn].value = v

    def record(self, frame, weights):
        """remember this frame's weights; flush() keys everything recorded"""
        self._weights = dict(weights or {})
        for k, v in self.values(self._weights).items():
            self._rec.setdefault(k, []).append((frame, v))

    def flush(self, interpolation='LINEAR'):
        """key every recorded frame: one action per face mesh's shape keys; returns the number of keys"""
        by_obj = {}
        for (on, kn), keys in self._rec.items():
            by_obj.setdefault(on, {})[f'key_blocks["{kn}"].value'] = keys
        n = 0
        for on, series in by_obj.items():
            sk = bpy.data.objects[on].data.shape_keys
            M.key_series(sk, series, f'{self.h.name}|face|{on}', interpolation)
            n += sum(len(v) for v in series.values())
        self._rec = {}
        return n

    def bake(self, fn, f0, f1, scene=None, interpolation='LINEAR'):
        """key fn(t) -> weights on every frame f0..f1 (t = film seconds of the frame); returns the key count"""
        from ...media.timebase import Timebase
        tb = Timebase.of(scene or bpy.context.scene)
        for f in range(int(f0), int(f1) + 1):
            self.record(f, fn(tb.t(f)))
        return self.flush(interpolation)


class SuitFace(_FaceBase):
    """installSuitMouth's handle: plate, plates, set(weights), weights; plus record / flush / bake"""

    def _mouth(self, weights, out):
        o = min(1.0, max(0.0, float(weights.get(MOUTH_OPEN, 0) or 0)))
        r = min(1.0, max(0.0, float(weights.get(MOUTH_ROUND, 0) or 0)))
        if o > 0.04:
            pn = self.plate.name
            out[(pn, KEY_PREFIX + 'mouth.seat')] = 1.0
            out[(pn, KEY_PREFIX + 'mouth.wide')] = o * (1 - r)
            out[(pn, KEY_PREFIX + 'mouth.round')] = o * r


def install_suit_mouth(h, standoff=0.0015, feature_standoff=0.0018, blush_standoff=0.001):
    """the face fixed and the mouth given its own shape keys (once per character; a second call returns the same
    face). Returns a SuitFace: set(weights) (MOUTH_OPEN, MOUTH_ROUND, any face shape key by name), record / flush /
    bake (keyed), plate, plates, report"""
    parts = _Parts(h)
    keys = parts.plate.data.shape_keys.key_blocks
    if KEY_PREFIX + 'viseme.seat' in keys:
        raise RuntimeError('install_suit_mouth: install_viseme_mouth is already on this face (one or the other)')
    if KEY_PREFIX + 'mouth.seat' in keys:
        return SuitFace(h, parts, {'already_installed': True})
    rep = _build_mouth_targets(parts, standoff, feature_standoff, blush_standoff)
    for p in [o for o in h.meshes if o.data.shape_keys]:
        for kb in p.data.shape_keys.key_blocks[1:]:
            kb.value = 0.0
    return SuitFace(h, parts, rep)


class SuitMouth:
    """makeSuitMouth: update(t, frame {aa, ih, ou, ee, oh}) -> {mouthOpen, mouthRound, Blink}, time based (any fps)"""

    def __init__(self, input_max=1.0, floor=0.3, attack=0.03, release=0.11, open_at=0.18, close_at=0.08,
                 switch_dip=0.3, switch_lead=0.25, blink_every=4.3):
        self.input_max, self.floor, self.attack, self.release = input_max, floor, attack, release
        self.open_at, self.close_at, self.switch_dip, self.switch_lead = open_at, close_at, switch_dip, switch_lead
        self.blink_every = blink_every
        self.state = {'open': 0.0, 'isOpen': False, 'pose': None, 't': None}

    def update(self, t, frame=None):
        M_ = self.state
        frame = frame or {}

        def val(k):
            return min(1.0, (frame.get(k, 0) or 0) / self.input_max)
        best, bv = None, 0.0
        for k in VOWELS:
            if val(k) > bv:
                bv, best = val(k), k
        dt = 1 / 60 if M_['t'] is None else min(0.1, max(1 / 240, t - M_['t']))
        M_['t'] = t
        tau = self.attack if bv > M_['open'] else self.release
        M_['open'] += (bv - M_['open']) * (1 - math.exp(-dt / tau))
        if not M_['isOpen'] and M_['open'] > self.open_at:
            M_['isOpen'] = True
        elif M_['isOpen'] and M_['open'] < self.close_at:
            M_['isOpen'] = False
        cur = val(M_['pose']) if M_['pose'] else 0.0
        if best and (not M_['pose'] or (best != M_['pose'] and (cur < self.switch_dip or bv > cur + self.switch_lead))):
            M_['pose'] = best
        out = {}
        if M_['isOpen'] and M_['pose']:
            v = SUIT_VISEMES[M_['pose']]
            out[MOUTH_OPEN] = v['open'] * (self.floor + (1 - self.floor) * min(1.0, M_['open']))
            out[MOUTH_ROUND] = v['round']
        if self.blink_every > 0:
            ph = (t % self.blink_every) / 0.18
            if ph < 1 and not M_['isOpen']:
                out['Blink'] = math.sin(ph * math.pi)
        return out


def make_suit_mouth(input_max=1.0, floor=0.3, attack=0.03, release=0.11, open_at=0.18, close_at=0.08, switch_dip=0.3,
                    switch_lead=0.25, blink_every=4.3):
    return SuitMouth(input_max, floor, attack, release, open_at, close_at, switch_dip, switch_lead, blink_every)


# ------------------------------------------------------------------------------------------------ the viseme mouth
def _sstep(a, b, x):
    q = max(0.0, min(1.0, (x - a) / (b - a)))
    return q * q * (3 - 2 * q)


def _build_viseme_targets(parts, shapes, standoff, feature_standoff, blush_standoff, warps):
    rep = _features(parts, feature_standoff, blush_standoff)
    plate = parts.plate
    tm = M.to_space(plate, plate)
    back = np.linalg.inv(tm)
    on_face = parts.on_face(standoff)
    rest_bl = M.key_coords(plate.data.shape_keys.key_blocks[0])
    G_all = M.apply(tm, rest_bl[parts.plate_idx])
    mp = is_mouth_plate(G_all)
    ids, G = parts.plate_idx[mp], G_all[mp]
    x0, x1, y0, y1 = G[:, 0].min(), G[:, 0].max(), G[:, 1].min(), G[:, 1].max()
    cx, cy, hx, hy = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
    BINS = 72
    rmax = np.zeros(BINS)
    polar = []
    for x, y, _z in G:
        u, v = (x - cx) / hx, (y - cy) / hy
        r, th = math.hypot(u, v), math.atan2(v, u)
        b = int(math.floor(((th + math.pi) / (2 * math.pi)) * BINS)) % BINS
        rmax[b] = max(rmax[b], r)
        polar.append((r, th))
    BIN, NB = 0.0025, 20
    lo, hi = np.full(NB, np.inf), np.full(NB, -np.inf)
    for x, y, _z in G_all[~mp]:
        if abs(x) > BIN * NB or y < 1.466 or y > 1.49:
            continue
        b = min(NB - 1, int(math.floor(abs(x) / BIN)))
        lo[b], hi[b] = min(lo[b], y), max(hi[b], y)
    mid = [((b + 0.5) * BIN, (lo[b] + hi[b]) / 2) for b in range(NB) if lo[b] < np.inf]
    TOPv = y1 - 0.0005

    def smile_y(x):
        x = abs(x)
        if not mid:
            return TOPv
        if x <= mid[0][0]:
            return mid[0][1]
        for k in range(1, len(mid)):
            if x <= mid[k][0]:
                f = (x - mid[k - 1][0]) / (mid[k][0] - mid[k - 1][0])
                return mid[k - 1][1] + (mid[k][1] - mid[k - 1][1]) * f
        return mid[-1][1]
    zmax = G[:, 2].max()
    base_y = min(m[1] for m in mid) if mid else TOPv
    half_t = 0.0015
    for b in range(NB):
        if lo[b] < np.inf:
            half_t = min(half_t, (hi[b] - lo[b]) / 2)

    def warp_xy(wp, x, y):
        ax = abs(x) * 1000
        f = 1 - _sstep(26, 60, ax)
        c = math.exp(-((ax / 13) ** 2))
        side = _sstep(8, 28, ax)
        k = wp.get('k', 1)
        yc = smile_y(x)
        yk = base_y + (yc - base_y) * (1 + (k - 1) * f) + (y - yc)
        return x * wp['sx'], yk + 0.001 * f * (wp['peak'] * c + wp['corner'] * side)

    def point(s, is_seat, r, th, z, w=None):
        u, v = r * math.cos(th), r * math.sin(th)
        span = math.sqrt(max(1e-6, 1 - u * u))
        t = min(1.0, max(0.0, (v / span + 1) / 2))
        X = s['a'] * u * 0.001
        Hs = (s['bt'] + s['bb']) * 0.001 * max(0.0, 1 - abs(u) ** s['n']) ** (1 / s['n'])
        top = smile_y(X) - 0.0002
        if is_seat:
            bot = top - min(0.0008, half_t)
        else:
            bot = min(top - min(0.0008, half_t), base_y - max(0.0, Hs - s['lift'] * 0.001 * u * u))
        Y = bot + t * (top - bot)
        XX = X
        if w:
            XX, Y = warp_xy(w, X, Y)
        return np.array((XX, Y, on_face(XX, Y) - (zmax - z) * 0.2))
    for _ in range(3):
        c = rmax.copy()
        for b in range(BINS):
            a0 = c[(b + BINS - 1) % BINS] or c[b]
            a2 = c[(b + 1) % BINS] or c[b]
            rmax[b] = max(c[b], (a0 + 2 * c[b] + a2) / 4)

    def r_at(th):
        fb = ((th + math.pi) / (2 * math.pi)) * BINS - 0.5
        b0 = ((int(math.floor(fb)) % BINS) + BINS) % BINS
        b1 = (b0 + 1) % BINS
        f = fb - math.floor(fb)
        return rmax[b0] * (1 - f) + rmax[b1] * f
    names = list(shapes)
    tgt = {nm: np.zeros_like(rest_bl) for nm in names}       # absolute positions (Blender), filled below
    S_abs = {}
    for k, (i, (r, th)) in enumerate(zip(ids, polar)):
        rr = min(1.0, r / max(1e-6, r_at(th)))
        z = G[k, 2]
        S = point(shapes['seat'], True, rr, th, z)
        S_abs[i] = S
        for nm in names:
            P = S if nm == 'seat' else point(shapes[nm], False, rr, th, z, warps.get(nm))
            tgt[nm][i] = M.apply(back, P[None, :])[0]
    # the painted line's own vertices (the whole "3", below the eyes) move with each viseme's warp, re-seated
    line = []
    for i, (x, y, z) in zip(parts.plate_idx[~mp], G_all[~mp]):
        if abs(x) > 0.11 or y < 1.455 or y > 1.507:
            continue
        line.append(i)
        z0 = on_face(x, y)
        for nm in names:
            wp = warps.get(nm)
            if not wp:
                continue
            X, Y = warp_xy(wp, x, y)
            P = np.array((X, Y, z + (on_face(X, Y) - z0)))
            tgt[nm][i] = M.apply(back, P[None, :])[0]
    filled = {nm: set(ids) | ({i for i in line} if warps.get(nm) else set()) for nm in names}
    seat_co = rest_bl.copy()
    seat_co[ids] = tgt['seat'][ids]
    ks = _add_key(plate, KEY_PREFIX + 'viseme.seat', seat_co)
    for nm in names:
        if nm == 'seat':
            continue
        co = seat_co.copy()
        sel = np.array(sorted(filled[nm]), dtype=int)
        co[sel] = tgt[nm][sel]
        _add_key(plate, KEY_PREFIX + 'viseme.' + nm, co, relative=ks)
    rep.update({'mouth_plate_vertices': int(len(ids)), 'line_vertices': len(line), 'smile_bins': len(mid),
                'half_stroke_mm': round(1000 * half_t, 3), 'base_y': round(float(base_y), 5)})
    return rep


class VisemeFace(_FaceBase):
    """installVisemeMouth's handle: set({'viseme': {AA: 0.7, ...}, 'mouth': 0..1, <face key>: w}); idx"""

    @property
    def idx(self):
        """installVisemeMouth's idx (each shape's morph target): here {shape: the plate's shape key name}"""
        p = KEY_PREFIX + 'viseme.'
        return {kb.name[len(p):]: kb.name for kb in self.plate.data.shape_keys.key_blocks if kb.name.startswith(p)}

    def _mouth(self, weights, out):
        vis = weights.get('viseme') or {}
        m = min(1.0, max(0.0, float(weights.get('mouth') or 0)))
        opening = sum(max(0.0, w) for k, w in vis.items() if k != 'MBP')
        if m > 0.02:
            pn = self.plate.name
            if opening > 0.02:
                out[(pn, KEY_PREFIX + 'viseme.seat')] = 1.0
            for k, w in vis.items():
                key = (pn, KEY_PREFIX + 'viseme.' + k)
                if k != 'seat' and key in out:
                    out[key] = max(0.0, w) * m


def install_viseme_mouth(h, shapes=None, standoff=0.0015, feature_standoff=0.0018, blush_standoff=0.001, warps=None):
    """the full viseme mouth (instead of install_suit_mouth: one or the other per character): the plate re-shaped per
    viseme (VISEME_SHAPES outlines hung from the painted line, raycast onto the dome) and the line warped (LINE_WARP)"""
    parts = _Parts(h)
    keys = parts.plate.data.shape_keys.key_blocks
    if KEY_PREFIX + 'mouth.seat' in keys:
        raise RuntimeError('install_viseme_mouth: install_suit_mouth is already on this face (one or the other)')
    if KEY_PREFIX + 'viseme.seat' in keys:
        return VisemeFace(h, parts, {'already_installed': True})
    rep = _build_viseme_targets(parts, shapes or VISEME_SHAPES, standoff, feature_standoff, blush_standoff,
                                LINE_WARP if warps is None else warps)
    for p in [o for o in h.meshes if o.data.shape_keys]:
        for kb in p.data.shape_keys.key_blocks[1:]:
            kb.value = 0.0
    return VisemeFace(h, parts, rep)


class VisemeTrack:
    """makeVisemeTrack: at(t) -> {'viseme': {shares}, 'mouth': 0..1} from events [{t0, t1, v}] (v None = closed)"""

    def __init__(self, events, lead=0.05, fade=0.07, close_gap=0.16, breath=0.06, scale=1.0):
        self.E = sorted(events, key=lambda e: e['t0'])
        self.lead, self.fade, self.close_gap, self.breath, self.scale = lead, fade, close_gap, breath, scale
        self.i0 = 0

    @staticmethod
    def _smooth(a, b, x):
        t = max(0.0, min(1.0, (x - a) / (b - a)))
        return t * t * (3 - 2 * t)

    def at(self, t):
        E, lead, fade = self.E, self.lead, self.fade
        if not E:
            return {'viseme': {}, 'mouth': 0.0}
        while self.i0 > 0 and E[self.i0]['t0'] > t:
            self.i0 -= 1
        while self.i0 < len(E) - 1 and E[self.i0 + 1]['t0'] - lead <= t:
            self.i0 += 1
        vis, mouth = {}, 0.0
        for k in range(max(0, self.i0 - 1), min(len(E) - 1, self.i0 + 1) + 1):
            e = E[k]
            win = self._smooth(e['t0'] - lead - fade, e['t0'] - lead + fade * 0.4, t) * \
                (1 - self._smooth(e['t1'] - fade * 0.3, e['t1'] + fade, t))
            if win <= 0:
                continue
            if e.get('v'):
                held = 1 + self.breath * math.sin((t - e['t0']) * 2 * math.pi * 1.3) if e['t1'] - e['t0'] > 0.35 else 1
                vis[e['v']] = max(vis.get(e['v'], 0.0), win * held * self.scale)
                mouth = max(mouth, win)
        tot = sum(vis.values())
        if tot > 1:
            vis = {k: v / tot for k, v in vis.items()}
        prev = E[self.i0]
        nxt = E[self.i0 + 1] if self.i0 + 1 < len(E) else None
        if mouth < 0.3 and prev and nxt and prev.get('v') and nxt.get('v') and nxt['t0'] - prev['t1'] < self.close_gap \
                and prev['t1'] < t < nxt['t0']:
            mouth = 0.3
        return {'viseme': vis, 'mouth': mouth}


def make_viseme_track(events, lead=0.05, fade=0.07, close_gap=0.16, breath=0.06, scale=1.0):
    return VisemeTrack(events, lead, fade, close_gap, breath, scale)


def events_from_phones(segs, phone_viseme=None):
    """timed phones [{ph, t0, t1}] (voicebox segs, ARPAbet, stress digits dropped) -> viseme events [{t0, t1, v}]
    through PHONE_VISEME (silence and unknown phones: v None)"""
    pv = phone_viseme or PHONE_VISEME
    out = []
    for s in segs:
        ph = re.sub(r'\d', '', str(s.get('ph', ''))).upper()
        out.append({'t0': float(s['t0']), 't1': float(s['t1']), 'v': pv.get(ph)})
    return out


# ------------------------------------------------------------------------------------------------ emotion + gaze
MORPHS = {
    'smile': ['Smile', 'MouthSmileLeft', 'MouthSmileRight'], 'frown': ['MouthFrown'], 'wide': ['EyeWide'],
    'soft': ['EyeClosedLeft', 'EyeClosedRight'], 'down': ['EyeLookDownLeft', 'EyeLookDownRight'],
    'up': ['EyeLookUpLeft', 'EyeLookUpRight\t'],                 # (digi's morph name carries a tab)
}
SWITCHES = {
    'blush': lambda v: {'Blush': 1} if v >= 0.3 else {},
    'jaw': lambda v: {MOUTH_OPEN: 0.3 + 0.7 * min(1.0, v)} if v >= 0.15 else {},
}


def merge_max(*ws):
    """weight dicts merged by the per-morph maximum"""
    out = {}
    for w in ws:
        for k, v in (w or {}).items():
            if isinstance(v, dict):
                out[k] = merge_max(out.get(k) or {}, v)
            else:
                out[k] = max(out.get(k, 0), v)
    return out


def _smooth(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


class FaceTrack:
    """makeFaceTrack: feelings keyed to words and sections: at(t) -> face weights"""

    def __init__(self, TL, section_base=None, line_cues=(), close_after_last=True):
        self.sections = list(TL.get('sections') or [])
        self.section_base = section_base or {}
        self.close_after_last = close_after_last
        caps = list(TL.get('captions') or [])
        self.cues = []
        for c in caps:
            for pat, feel in line_cues:
                rx = pat if hasattr(pat, 'search') else re.compile(pat)
                if rx.search(c['text']):
                    self.cues.append({'t0': c['t0'], 't1': c['t1'], 'f': feel})
                    break
        self.last_word = max(c['t1'] for c in caps) if caps else math.inf

    def at(self, t):
        sec = next((s for s in self.sections if s['t0'] <= t < s['t1']), None)
        if sec is None and self.sections:
            prev, first = None, self.sections[0]
            for s in self.sections:
                if s['t0'] < first['t0']:
                    first = s
                if s['t0'] <= t and (prev is None or s['t0'] >= prev['t0']):
                    prev = s
            sec = prev or first
        f = dict(self.section_base.get(sec['name'], {})) if sec else {}
        for c in self.cues:
            w = _smooth(c['t0'] - 0.25, c['t0'] + 0.4, t) * (1 - _smooth(c['t1'] + 0.3, c['t1'] + 0.9, t))
            if w <= 0:
                continue
            for k, v in c['f'].items():
                f[k] = f.get(k, 0) * (1 - w) + v * w
            for k in list(f):
                if k not in c['f']:
                    f[k] *= 1 - 0.6 * w
        if self.close_after_last:
            dusk = _smooth(self.last_word - 3.5, self.last_word + 1.5, t)
            if dusk > 0:
                f['soft'] = max(f.get('soft', 0), 0.92 * dusk)
                f['smile'] = max(f.get('smile', 0), 0.35 * dusk)
        out = {}
        for k, v in f.items():
            for m in MORPHS.get(k, []):
                out[m] = max(out.get(m, 0), v)
            sw = SWITCHES.get(k)
            for m, w in (sw(v) if sw else {}).items():
                out[m] = max(out.get(m, 0), w)
        return out


def make_face_track(TL, section_base=None, line_cues=(), close_after_last=True):
    return FaceTrack(TL, section_base, line_cues, close_after_last)
