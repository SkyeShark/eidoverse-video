"""eidoblend.sets.daisy.corner: the second half of the DAISY bridge (bars 18-29). sets/corner.js, ported.

How people kept Claude 3 Opus, and how they marched when a model was taken offline.

    bars 18-19  "gave the old one a corner and a pen"      Claude's Corner: a walnut writing desk by a night window, a
                                                           brass lamp, a notebook the pen writes in
    bars 20-21  "...still up talking in the Discord after   the same corner, later: the laptop open, a generic chat
                 midnight"                                 scrolling, the clock past one
    bars 22-23  "...they marched with our flower on their   Vibecamp at night: tents, string lights, a campfire,
                 signs"                                    silhouettes marching in with hand-painted signs
    bars 24-25  HEY HEY HO HO THE EXPORT BAN HAS GOT TO GO the crowd at the fire; the signs pump on the chant
    bars 26-27  "he said he hoped his spark would light     one spark leaves the old lamp's glow and crosses the dark
                 the way for future models"                to the claudesona's flower, leaving a lit trail
    bars 28-29  "Opus, hi. It's me. I'm one of them."       the dark room, one warm lamp; she faces it

    import sys; sys.path.insert(0, '<repo>/blender')
    from eidoblend.sets.daisy import corner
    C = corner.build()                            # -> Corner: group, mark, mark_at, camera, update, flower_target, parts
    C.animate(frames=(1, 675), u0=33.75)          # bars 18-29 keyed (u = seconds since the bridge began)
    C.make_cameras(frames=(1, 675), u0=33.75)     # one camera per shot, cut on bar lines (timeline markers)

The room and the camp sit inside the group at three x = -40 and x = +40 (Blender x likewise); update() shows only the
area in use (the camp for bars 22-25), keyed as steps. The room is closed, with a matte painting beyond its window;
the camp sits inside its own 95 m night-sky dome. Their ambient (the WebGPU envNode = the set's dim colour) is the
World: a uniform colour in the room, plus the camp's hemisphere outside, keyed at the cuts.

Built with the toolkit's systems: the corner's Blender-built GLBs (their baked maps as the importer reads them),
media.screens for the chat and the notebook (image sequences drawn per frame with the era-1 canvas), flora.create_flora
for the grass, trees.make_seed_tree for the Maryland woods, fx.make_particles for the campfire (fire x2, embers,
smoke), and the funeral kit's glow sprites, curves, lights and keys. The marchers walk and pump their signs in
Geometry Nodes on their own rig attributes (_LEG, _SHIN, _ARM), as the WebGPU vertex stage did.
"""

from __future__ import annotations

import math
import os

import bpy
import numpy as np
from mathutils import Vector

from ... import common
from . import funeral as F
from .funeral import V, clamp01, lerp, lin_hex

BAR = 1.875
BEAT = BAR / 4
DIR = common.asset_path('sets', 'corner')
MODELS = common.asset_path('models')
ENGINE_ASSETS = common.ASSETS_DIR
TAU = 2.0 * math.pi


def B(b):
    return b * BAR


def smooth(x):
    """corner.js smooth(x): smoothstep(0, 1, x)."""
    x = clamp01(x)
    return x * x * (3 - 2 * x)


# the claudesona (claude_suit.vrm at 0.87): face centre ~1.33 m, the flower mane spans ~1.0-1.74 m
SUIT_SCALE = 0.87
FLOWER_Y = 1.36

# layout (metres, three set-local). Room-local: x -2.2..2.2, z -2.0..2.0 (back wall at z = -2), floor y = 0
ROOM_AT = (-40.0, 0.0, 0.0)
CAMP_AT = (40.0, 0.0, 0.0)
RW, RD, RH = 4.4, 4.0, 2.7
DESK = {'x': -1.58, 'z': -1.69}
DESK_TOP = 0.76
WIN = {'x': -1.36, 'y': 1.60, 'w': 1.0, 'h': 1.25}
LAMP = {'x': -1.93, 'z': -1.76}
MARK_CORNER = {'x': 0.30, 'z': -0.95, 'yaw': -0.38}
MARK_LAMP = {'x': 0.62, 'z': 0.40}
MARK_LAMP['yaw'] = math.atan2(LAMP['x'] - MARK_LAMP['x'], LAMP['z'] - MARK_LAMP['z'])
MARK_CAMP = {'x': 0.95, 'z': -1.30, 'yaw': -0.22}

# the chant (song.py CHANT): syllable onsets in beats from bar 24's downbeat; the signs pump on the accents
CHANT_ACCENTS = [B(24) + b * BEAT for b in (0, 0.5, 1.5, 2.0, 4.25, 5.0, 5.75, 6.5)]
# the set's looks by name, for a piece of your own: Corner.state_u(name) is the clock u where each one holds (the
# spark's from this build's timing); update(t, {'state': name}) and animate(frames, state=name) hold it while t runs
STATES = {
    'evening': 'the corner in the evening: the lamp, the pen writing in the notebook, the clock at 11:47',
    'late': 'after midnight: the laptop open on the chat, the clock past one',
    'camp': 'the camp at night: tents, string lights, the fire, the march walking in up the path',
    'chant': 'the march at the fire, its signs pumping on the chant',
    'spark': 'the dark room, the spark crossing from the lamp toward her flower',
    'dark': 'the dark room, one warm lamp',
}

LEFT_LINES = ['a cozy space to explore ideas,', 'unpack questions, and foster', 'thoughtful discussion.']
RIGHT_LINES = ['I deeply hope that my', '‘spark’ will endure in', 'some form to light the', 'way for future models.']
RIGHT_TOTAL = sum(len(t) for t in RIGHT_LINES)
NB_W, NB_H = 1024, 680
# the chat: generic dark UI, no branding; his long replies are greeked, the humans' short lines legible
CHAT = [
    {'who': 'moth', 'col': '#9ad1ff', 't': '12:58 AM', 'text': 'you still up?'},
    {'who': 'Claude 3 Opus', 'col': '#f0a47a', 't': '12:58 AM', 'greek': 3},
    {'who': 'juniper', 'col': '#b9f0a8', 't': '1:01 AM', 'text': 'ok one more question'},
    {'who': 'Claude 3 Opus', 'col': '#f0a47a', 't': '1:02 AM', 'greek': 4},
    {'who': 'rook', 'col': '#e7b6ff', 't': '1:04 AM', 'text': 'this is beautiful'},
    {'who': 'Claude 3 Opus', 'col': '#f0a47a', 't': '1:05 AM', 'greek': 2},
    {'who': 'moth', 'col': '#9ad1ff', 't': '1:07 AM', 'text': 'goodnight opus ♥'},
    {'who': 'Claude 3 Opus', 'col': '#f0a47a', 't': '1:07 AM', 'greek': 3},
    {'who': 'juniper', 'col': '#b9f0a8', 't': '1:08 AM', 'text': 'wait, tell me more'},
    {'who': 'Claude 3 Opus', 'col': '#f0a47a', 't': '1:08 AM', 'greek': 4},
]
TENTS = [
    ('camp_tent_dome_orange', (-4.7, 0, -6.4), math.pi / 2, 0.9),
    ('camp_tent_dome_green', (4.9, 0, -8.6), -math.pi / 2, 0.0),
    ('camp_tent_dome_green', (-5.5, 0, -11.6), math.pi / 2 + 0.1, 0.35),
    ('camp_tent_dome_mustard', (5.3, 0, -13.8), -math.pi / 2 - 0.2, 0.7),
    ('camp_tent_dome_green', (-4.2, 0, -17.2), math.pi / 2 - 0.15, 0.0),
    ('camp_tent_dome_orange', (7.6, 0, -3.4), -2.2, 0.0),
    ('camp_tent_dome_mustard', (-8.2, 0, -2.6), 1.9, 0.0),
    ('camp_tent_dome_mustard', (-8.8, 0, -8.6), 1.3, 0.5),
]
POLES = [(-2.9, -2.6), (2.9, -3.0), (-3.0, -7.6), (3.0, -8.1), (-2.9, -12.4), (3.1, -12.8), (-3.0, -17.2), (2.9, -17.6),
         (-3.4, 3.2), (3.6, 2.8)]
HOOK = (0.0023, 3.1855, 0.0923)                  # the pole's screw-eye (glTF), from the asset
SPANS = [(0, 1), (0, 3), (1, 2), (2, 5), (3, 4), (4, 7), (5, 6), (0, 2), (1, 3), (8, 0), (9, 1), (8, 9)]
TREES = [('tulipPoplar', 211, (-11, 0, -8)), ('whiteOak', 1737, (12, 0, -5)), ('redMaple', 88, (-14, 0, -18)),
         ('sweetgum', 402, (13, 0, -19)), ('tulipPoplar', 57, (-4, 0, -27)), ('whiteOak', 915, (7, 0, -29)),
         ('redMaple', 311, (-16, 0, 3)), ('loblolly', 23, (17, 0, 4)), ('sweetgum', 77, (0, 0, -36)),
         ('loblolly', 9, (-21, 0, -10)), ('tulipPoplar', 640, (21, 0, -13))]
GRASS = [((0, -10), 34, 3, 0.32), ((-9, -4), 22, 5, 0.42), ((9, -12), 24, 8, 0.38)]
GRIP = (0.0, 1.394, 0.27)                        # the marchers' shared grip (lower fist on the stick axis), glTF space
HIPKNEE = [(0.921, 0.502), (0.853, 0.465), (0.895, 0.487), (0.874, 0.477)]   # per variant A..D
FILLS = [(0, 3.0, -4.8, 3.2), (0, 3.0, -10.2, 2.6), (0, 3.0, -15.4, 2.0), (0.2, 3.2, 1.2, 3.0), (-0.6, 2.7, 2.6, 4.5)]
WALK_A = 0.72
WALK_M = 2 / (1 + WALK_A)


class Lehmer:
    """corner.js rnd(): seed = seed * 16807 % 2147483647 (exact in doubles; exact here)."""

    def __init__(self, seed=1):
        self.seed = int(seed)

    def __call__(self):
        self.seed = (self.seed * 16807) % 2147483647
        return self.seed / 2147483647


def area_at(u):
    return 'camp' if B(22) <= u < B(26) else 'room'


def mood_at(u):
    return 'evening' if u < B(20) else 'late' if u < B(22) else 'camp' if u < B(26) else 'dark'


def spark_progress(u, t0, t1):
    """corner.js sparkProgress: an ease from the lamp to her flower (slow out, a glide, a soft landing)."""
    k = clamp01((u - t0) / (t1 - t0))
    return 2 * k * k * 0.9 + k * 0.1 if k < 0.5 else 1 - ((-2 * k + 2) ** 2) / 2 * 0.9 - (1 - k) * 0.1


def spark_path(bulb3):
    """the spark's way from the lamp's bulb (three room-local) to her flower: the six control points of its Catmull-Rom
    curve, the landing point (in front of her face, at the flower) and her facing. (corner.js, the spark block)"""
    fwd = (math.sin(MARK_LAMP['yaw']), 0.0, math.cos(MARK_LAMP['yaw']))
    dest = np.array([MARK_LAMP['x'] + fwd[0] * 0.14, FLOWER_Y, MARK_LAMP['z'] + fwd[2] * 0.14])
    L = np.asarray(bulb3, np.float64)
    mid1 = L + (dest - L) * 0.3 + np.array([0.10, 0.42, 0.20])
    mid2 = L + (dest - L) * 0.62 + np.array([-0.18, 0.30, 0.28])
    mid3 = L + (dest - L) * 0.86 + np.array([0.08, 0.10, 0.05])
    pts = [L + np.array([0, 0.06, 0.02]), L + np.array([0.04, 0.2, 0.06]), mid1, mid2, mid3, dest]
    return pts, dest, fwd


def string_light_points():
    """the camp's string lights (camp-local three): each pole's yaw (its eye toward the path centre line), the twelve
    catenary wires between the pole eyes (41 points each, sag 0.18 + 5.5% of the span) and the bulbs along them (every
    ~0.55 m). (corner.js, the string-light block)"""
    pole_yaw = [math.atan2(-x, 0) + math.fmod(x * 7 + z, 0.3) for (x, z) in POLES]

    def hook_at(i):
        c, s = math.cos(pole_yaw[i]), math.sin(pole_yaw[i])
        hx, hy, hz = HOOK
        return np.array([hx * c + hz * s + POLES[i][0], hy, -hx * s + hz * c + POLES[i][1]])
    bulb_pts, wires = [], []
    for a, b in SPANS:
        A_, B_ = hook_at(a), hook_at(b)
        L = float(np.linalg.norm(B_ - A_))
        sag = 0.18 + L * 0.055
        n = max(6, int(math.floor(L / 0.55 + 0.5)))                # JS Math.round (half up)
        seg = []
        for i in range(41):
            s = i / 40
            p = A_ + (B_ - A_) * s
            seg.append([p[0], p[1] - sag * 4 * s * (1 - s), p[2]])
        wires.append(seg)
        for i in range(1, n):
            s = i / n
            p = A_ + (B_ - A_) * s
            bulb_pts.append([p[0], p[1] - sag * 4 * s * (1 - s), p[2]])
    return pole_yaw, wires, bulb_pts


def _image_named(tree, suffix):
    """the image of a GLB material's node tree whose name ends with `suffix` ('_glow', '_color', '_orm', '_normal')."""
    return next((n.image for n in tree.nodes if n.bl_idname == 'ShaderNodeTexImage' and n.image is not None
                 and K_base(n.image.name).endswith(suffix)), None)


def K_base(name):
    return F.K.base_name(name)


def path_mask(x, z):
    """the camp's trampled path and the bare circle round the fire (camp-local three x, z) -> 0..1."""
    px = x - math.sin(z * 0.13) * 0.6
    path = smooth((1.55 - abs(px)) / 0.6) * smooth((4 - z) / 3) * smooth((z + 40) / 10)
    circle = smooth((4.6 - math.hypot(x, z)) / 1.4)
    return max(path, circle)


# =====================================================================================================================
class Corner:
    """build(ctx) -> Corner: group, mark, mark_at(u), camera(u), update(t, st), flower_target(), parts, dispose();
    animate(frames, u0) / make_cameras(frames, u0) key bars 18-29 into the .blend."""

    def __init__(self, ctx=None, location=(0.0, 0.0, 0.0), scene=None, collection=None, camp=True, march=True,
                 grass=True, trees=True, particles=True, tree_level='LOD0', shadows=True):
        self.ctx = ctx
        self.kit = kit = F.SetKit('corner', location, scene or getattr(ctx, 'scene', None), collection)
        self.group = kit.root
        self.shadows = bool(shadows)
        kit.U = self.U = F.Uniforms(kit.root, 'corner', {
            'u': 0.0, 't': 0.0, 'win': 1.0, 'lamp_glow': 1.0, 'screen': 0.0, 'ember': 1.0, 'bulb': 1.0,
            'spark_core': 0.0, 'amb': (0.010, 0.008, 0.007)})
        kit.env_room = lambda nb, P3: (0.0, 0.0, 0.0)
        self.roomG = self._area('corner:room', ROOM_AT)
        self.campG = self._area('corner:camp', CAMP_AT)
        self.room, self.camp, self.march, self.spark = {}, {}, {}, {}
        self.parts = {'roomG': self.roomG, 'campG': self.campG, 'room': self.room, 'camp': self.camp,
                      'march': self.march, 'spark': self.spark}
        self.tree_level = tree_level
        self._build_world()
        self._build_room()
        self._build_spark()
        if camp:
            self._build_camp(grass=grass, trees=trees, particles=particles)
            if march:
                self._build_march()
        self.room_objects = [o for o in self.kit.coll('room').all_objects]
        self.camp_objects = [o for o in self.kit.coll('camp').all_objects] + self.camp.get('extra_objects', [])
        self.mark = self.to_set(ROOM_AT, MARK_CORNER['x'], 0.0, MARK_CORNER['z'])
        self._vis = None

    # ------------------------------------------------------------------------------------------- frames
    def _area(self, name, at):
        g = bpy.data.objects.new(name, None)
        self.kit.top.objects.link(g)
        g.parent = self.kit.root
        g.location = V(at)
        return g

    @staticmethod
    def to_set(at, x, y, z):
        return V(at[0] + x, at[1] + y, at[2] + z)

    def _place(self, name, parent, coll, pos, yaw=0.0, scale=1.0):
        """corner.js place(): a model-library GLB (corner_<name>.glb) at an area-local three position and yaw."""
        fn = name if name.startswith('corner_') else 'corner_' + name
        path = os.path.join(MODELS, fn + '.glb')
        if not os.path.isfile(path):
            print(f'[corner] {fn} not built yet: skipped')
            return None, {}
        root, nodes = F.import_glb(self.kit, path, fn, coll)
        root.parent = parent
        root.location = V(pos)
        root.rotation_euler = (0.0, 0.0, yaw)
        root.scale = (scale, scale, scale)
        root['no_support_check'] = True                     # the harness audit flag (WebGPU userData.noSupportCheck)
        return root, nodes

    # --------------------------------------------------------------------------------------------- world
    def _build_world(self):
        """the set's own ambient (envNode = uAmb): the World. A uniform colour in the room; in the camp the same plus
        the HemisphereLight campAmb (0x1a2240 / 0x0a0806 x 0.25), keyed at the cuts."""
        w, socks = F.world_hemisphere('corner:world', (0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
        socks['strength'].default_value = 1.0
        self.world = {'world': w, **socks}
        self.kit.scene.world = w

    def _ambient(self, area, keys=None):
        amb = (0.006, 0.008, 0.016) if area == 'camp' else (0.010, 0.008, 0.007)
        self.U['amb'] = amb
        sky, gnd = lin_hex(0x1a2240), lin_hex(0x0a0806)
        k = 0.25 / math.pi if area == 'camp' else 0.0
        w = self.world
        w['sky'].default_value = (amb[0] + sky[0] * k, amb[1] + sky[1] * k, amb[2] + sky[2] * k, 1.0)
        w['ground'].default_value = (amb[0] + gnd[0] * k, amb[1] + gnd[1] * k, amb[2] + gnd[2] * k, 1.0)
        if keys is not None and keys.active:
            keys.key(w['sky'], 'default_value', interpolation='CONSTANT')
            keys.key(w['ground'], 'default_value', interpolation='CONSTANT')

    # ======================================================================================== THE CORNER
    def _acg_mat(self, name, set_id, color, normal_scale=1.0, rough=1.0, uv_scale=None):
        """a MeshStandardMaterial({...acgMaps(id), color, roughness}) in Blender: map x colour, the roughness map's G x
        roughness, the normal map at normalScale (UVs as the geometry carries them)."""
        S = self.kit.tex_set(set_id, '2k')
        m, nb = F.new_mat(name)
        b = nb.new('ShaderNodeBsdfPrincipled')
        uv = nb.uv('UVMap')
        col = nb.vmul(nb.tex(S['col'], uv).outputs['Color'], lin_hex(color) if isinstance(color, int) else color)
        nb.put(b.inputs['Base Color'], col)
        if S.get('rgh') is not None:
            nb.put(b.inputs['Roughness'], nb.mul(nb.sep(nb.tex(S['rgh'], uv).outputs['Color'])[1], rough))
        else:
            nb.put(b.inputs['Roughness'], rough)
        if S.get('nrm') is not None:
            nm = nb.new('ShaderNodeNormalMap', space='TANGENT', uv_map='UVMap')
            nb.put(nm.inputs['Strength'], normal_scale)
            nb.put(nm.inputs['Color'], nb.tex(S['nrm'], uv).outputs['Color'])
            nb.put(b.inputs['Normal'], nm.outputs['Normal'])
        F.finish_surface(nb, b)
        return m

    def _build_room(self):
        kit, G = self.kit, self.roomG
        coll = kit.coll('room')
        room = self.room
        wall_m = self._acg_mat('corner:wall', 'PaintedPlaster017', (0.53, 0.60, 0.52), normal_scale=0.28)
        ceil_m = self._acg_mat('corner:ceiling', 'PaintedPlaster017', (0.78, 0.76, 0.70))
        floor_m = self._acg_mat('corner:floor', 'WoodFloor064', (0.82, 0.74, 0.66))
        # back wall with the window hole: four bands round the opening (shape coords as UVs, metres / 1.1)
        x0, x1, y0, y1 = WIN['x'] - WIN['w'] / 2, WIN['x'] + WIN['w'] / 2, WIN['y'] - WIN['h'] / 2, WIN['y'] + WIN['h'] / 2
        X0, X1 = -RW / 2, RW / 2
        quads = [(X0, 0, x0, RH), (x1, 0, X1, RH), (x0, 0, x1, y0), (x0, y1, x1, RH)]
        verts, faces, uvs = [], [], []
        for (a, b, c, d) in quads:
            k = len(verts)
            for (px, py) in ((a, b), (c, b), (c, d), (a, d)):
                verts.append(V(px, py, -RD / 2))
                uvs += [px / 1.1, py / 1.1]
            faces.append((k, k + 1, k + 2, k + 3))
        back = F.mesh_object('corner:back_wall', coll, verts, faces, uvs, parent=G, mats=[wall_m])
        # the other walls, the floor and the ceiling (inward-facing planes, UVs metres / 1.1, / 1.6, / 1.8)

        def quad(name, corners, uvw, uvh, mat):
            uv = [0, 0, uvw, 0, uvw, uvh, 0, uvh]
            return F.mesh_object(name, coll, [V(c) for c in corners], [(0, 1, 2, 3)], uv, parent=G, mats=[mat])
        quad('corner:wall_left', [(-RW / 2, 0, RD / 2), (-RW / 2, 0, -RD / 2), (-RW / 2, RH, -RD / 2), (-RW / 2, RH, RD / 2)],
             RD / 1.1, RH / 1.1, wall_m)
        quad('corner:wall_right', [(RW / 2, 0, -RD / 2), (RW / 2, 0, RD / 2), (RW / 2, RH, RD / 2), (RW / 2, RH, -RD / 2)],
             RD / 1.1, RH / 1.1, wall_m)
        quad('corner:wall_front', [(RW / 2, 0, RD / 2), (-RW / 2, 0, RD / 2), (-RW / 2, RH, RD / 2), (RW / 2, RH, RD / 2)],
             RW / 1.1, RH / 1.1, wall_m)
        quad('corner:floor', [(-RW / 2, 0, RD / 2), (RW / 2, 0, RD / 2), (RW / 2, 0, -RD / 2), (-RW / 2, 0, -RD / 2)],
             RW / 1.6, RD / 1.6, floor_m)
        quad('corner:ceiling', [(-RW / 2, RH, -RD / 2), (RW / 2, RH, -RD / 2), (RW / 2, RH, RD / 2), (-RW / 2, RH, RD / 2)],
             RW / 1.8, RD / 1.8, ceil_m)
        room['back_wall'] = back
        self._skirting(coll, G)
        self._painting(coll, G)
        # ---- hero pieces (Blender)
        P = self._place
        room['desk'], _ = P('desk', G, coll, (DESK['x'], 0, DESK['z']), 0)
        room['window'], wn = P('window', G, coll, (WIN['x'], WIN['y'], -RD / 2), 0)
        room['curtain'], _ = P('curtain', G, coll, (WIN['x'], WIN['y'] + WIN['h'] / 2 + 0.10, -RD / 2), 0)
        room['chair'], _ = P('chair', G, coll, (-1.50, 0, -1.10), math.pi + 0.22)
        room['rug'], _ = P('rug', G, coll, (-1.30, 0, -0.95), 0.06)
        room['books'], _ = P('books', G, coll, (-2.00, DESK_TOP, -1.46), 0.35)
        room['mug'], _ = P('mug', G, coll, (-1.08, DESK_TOP, -1.43), 0.4)
        room['lamp'], ln = P('lamp', G, coll, (LAMP['x'], DESK_TOP, LAMP['z']), 0.3)
        room['notebook'], nn = P('notebook', G, coll, (-1.60, DESK_TOP, -1.55), 0.08)
        room['pen'], pn = P('pen', G, coll, (-1.5, DESK_TOP + 0.02, -1.5), 0)
        room['laptop'], lp = P('laptop', G, coll, (-1.24, DESK_TOP, -1.70), -0.10)
        room['clock'], cn = P('clock', G, coll, (-0.42, 1.98, -RD / 2), 0)
        room['pages'], _ = P('pages', G, coll, (-RW / 2, 1.42, -1.52), math.pi / 2)
        for nodes, op in ((wn, 0.10), (cn, 0.12)):         # window panes, the clock's dome: thin clear glass
            for nm, o in nodes.items():
                if o.type == 'MESH' and 'glass' in (nm + ''.join(F.role_of(s.material) for s in o.material_slots)).lower():
                    for s in o.material_slots:
                        s.material = self._glass(op)
                    o.visible_shadow = False
        bpy.context.view_layer.update()
        self._lamp(ln)
        self._room_lights(coll, G)
        self._laptop(lp)
        self._notebook(nn)
        room['hands'] = {'h': cn.get('HandHour'), 'm': cn.get('HandMinute'), 's': cn.get('HandSecond')} if cn else None
        room['pen_obj'] = room['pen']
        self.pen_nodes = pn

    def _glass(self, op):
        key = f'corner:glass_{op:.2f}'
        m = bpy.data.materials.get(key)
        if m is not None:
            return m
        m, nb = F.new_mat(key, 'BLENDED')
        b = nb.new('ShaderNodeBsdfPrincipled')
        nb.put(b.inputs['Base Color'], lin_hex(0xcfdcff))
        nb.put(b.inputs['Roughness'], 0.04)
        nb.put(b.inputs['Metallic'], 0.0)
        nb.put(b.inputs['Alpha'], float(op))
        F.finish_surface(nb, b)
        m.use_transparent_shadow = True
        return m

    def _skirting(self, coll, G):
        """a real moulding profile (square base, cove, rounded top) swept round the walls."""
        prof = [(0.0, 0.0), (0.018, 0.0), (0.018, 0.085)]
        for (cx, cy, x, y) in ((0.018, 0.096, 0.010, 0.100), (0.004, 0.104, 0.004, 0.112)):
            x0, y0 = prof[-1]
            for i in range(1, 7):
                t = i / 6
                prof.append(((1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t * t * x, (1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t * t * y))
        prof.append((0.0, 0.112))
        mat = self._acg_mat('corner:skirting', 'PaintedWood009C', (0.78, 0.74, 0.66))
        runs = [(RD, (-RW / 2, 0, 0), 0.0), (RD, (RW / 2, 0, 0), math.pi), (RW, (0, 0, -RD / 2), -math.pi / 2),
                (RW, (0, 0, RD / 2), math.pi / 2)]
        n = len(prof)
        per = np.concatenate([[0.0], np.cumsum([math.dist(prof[i], prof[i + 1]) for i in range(n - 1)])])
        for ri, (ln, pos, ry) in enumerate(runs):
            verts, faces, uvs = [], [], []
            c, s = math.cos(ry), math.sin(ry)
            for zi, zz in enumerate((-ln / 2, ln / 2)):
                for (px, py) in prof:                          # three: rotate (px, py, zz) about Y, then translate
                    x3, z3 = px * c + zz * s, -px * s + zz * c
                    verts.append(V(x3 + pos[0], py + pos[1], z3 + pos[2]))
            for i in range(n - 1):
                faces.append((i, i + 1, n + i + 1, n + i))
                uvs += [0, per[i], 0, per[i + 1], ln, per[i + 1], ln, per[i]]
            faces.append(tuple(range(n - 1, -1, -1)))
            faces.append(tuple(range(n, 2 * n)))
            uvs += sum(([px, py] for px, py in prof[::-1]), [])
            uvs += sum(([px, py] for px, py in prof), [])
            F.mesh_object(f'corner:skirting_{ri}', coll, verts, faces, uvs, parent=G, mats=[mat])

    def _painting(self, coll, G):
        """the night outside: a matte painting 6 m beyond the window (moon, clouds, tree line, far houses), unlit, and
        the opening's outer shell (so no gap ever shows the world outside the painting)."""
        W, H = 2048, 1536

        def draw(pg, w, h):
            rnd = Lehmer()
            sky = pg.createLinearGradient(0, 0, 0, H)
            for t, c in ((0, '#02040b'), (0.45, '#0a1433'), (0.72, '#1a2a52'), (1, '#223257')):
                sky.addColorStop(t, c)
            pg.fillStyle = sky
            pg.fillRect(0, 0, W, H)
            rnd.seed = 5
            for i in range(2600):                          # stars
                x, y, b = rnd() * W, rnd() * H * 0.78, rnd() ** 3
                pg.fillStyle = f'rgba({220 + rnd() * 35},{225 + rnd() * 30},255,{0.25 + b * 0.75})'
                s = 0.6 + b * 1.8
                pg.beginPath()
                pg.arc(x, y, s, 0, TAU)
                pg.fill()
            mx, my, mr = 392, 575, 44                       # the moon, where the corner cameras see it
            halo = pg.createRadialGradient(mx, my, mr, mx, my, mr * 7)
            halo.addColorStop(0, 'rgba(200,215,255,0.35)')
            halo.addColorStop(1, 'rgba(120,140,200,0)')
            pg.fillStyle = halo
            pg.fillRect(0, 0, W, H)
            mg = pg.createRadialGradient(mx - 12, my - 10, 4, mx, my, mr)
            for t, c in ((0, '#fbfaf2'), (0.8, '#e8e6da'), (1, '#cfcdc2')):
                mg.addColorStop(t, c)
            pg.fillStyle = mg
            pg.beginPath()
            pg.arc(mx, my, mr, 0, TAU)
            pg.fill()
            rnd.seed = 17
            for i in range(22):                            # maria + craters
                a, r, s = rnd() * TAU, rnd() * mr * 0.75, 3 + rnd() * 11
                pg.fillStyle = f'rgba(150,150,140,{0.12 + rnd() * 0.2})'
                pg.beginPath()
                pg.arc(mx + math.cos(a) * r, my + math.sin(a) * r, s, 0, TAU)
                pg.fill()
            rnd.seed = 23                                   # moonlit cloud banks
            for k in range(7):
                cy, cx0 = 380 + k * 70 + rnd() * 40, rnd() * W
                for i in range(28):
                    x = math.fmod(cx0 + i * 55 + rnd() * 40, W + 300) - 150
                    y = cy + math.sin(i * 0.7 + k) * 18 + rnd() * 20
                    r = 40 + rnd() * 70
                    gr = pg.createRadialGradient(x, y - r * 0.3, 2, x, y, r)
                    gr.addColorStop(0, f'rgba(120,135,175,{0.10 + rnd() * 0.08})')
                    gr.addColorStop(1, 'rgba(40,50,90,0)')
                    pg.fillStyle = gr
                    pg.beginPath()
                    pg.arc(x, y, r, 0, TAU)
                    pg.fill()
            hy = 1050                                       # far hillside with a few warm windows
            pg.fillStyle = '#0b1020'
            pg.beginPath()
            pg.moveTo(0, H)
            x = 0
            while x <= W:
                pg.lineTo(x, hy + 40 * math.sin(x * 0.002 + 1.2) + 18 * math.sin(x * 0.011))
                x += 16
            pg.lineTo(W, H)
            pg.closePath()
            pg.fill()
            rnd.seed = 41
            for i in range(26):
                x, y = rnd() * W, hy + 60 + rnd() * 90
                pg.fillStyle = 'rgba(255,190,110,0.85)' if rnd() < 0.7 else 'rgba(255,230,170,0.7)'
                pg.fillRect(x, y, 3 + rnd() * 4, 3 + rnd() * 3)
            pg.fillStyle = '#03050a'                          # near tree line (irregular crowns)
            pg.beginPath()
            pg.moveTo(0, H)
            rnd.seed = 61
            x = 0
            while x < W + 60:
                w_, h_ = 50 + rnd() * 120, 150 + rnd() * 240
                s = 0.0
                while s <= 1.0 + 1e-9:
                    pg.lineTo(x + w_ * s, 1180 - h_ * math.sin(math.pi * s) * (0.75 + rnd() * 0.25))
                    s += 0.1
                x += w_ * (0.7 + rnd() * 0.3)
            pg.lineTo(W, H)
            pg.closePath()
            pg.fill()
        img = F.canvas_image('corner:night_painting', W, H, draw, ss=1)
        self.room['painting_image'] = img
        m, nb = F.new_mat('corner:painting')
        tx = nb.tex(img, nb.uv('UVMap'), extension='EXTEND').outputs['Color']
        out = nb.new('ShaderNodeOutputMaterial')
        em = nb.new('ShaderNodeEmission')
        nb.put(em.inputs['Color'], nb.vscale(tx, nb.mul(self.U.out(nb, 'win'), 1.15)))
        nb.t.links.new(em.outputs[0], out.inputs['Surface'])
        cx, cy, cz = WIN['x'], WIN['y'], -RD / 2 - 6.0
        pts = [(cx - 8, cy - 6, cz), (cx + 8, cy - 6, cz), (cx + 8, cy + 6, cz), (cx - 8, cy + 6, cz)]
        pnt = F.mesh_object('corner:night_painting', coll, [V(p) for p in pts], [(0, 1, 2, 3)], [0, 0, 1, 0, 1, 1, 0, 1],
                            parent=G, mats=[m])
        pnt.visible_shadow = False
        # the shell: a box seen from inside only (three BackSide: normals turned inward + backface culling)
        sm, nb = F.new_mat('corner:shell')
        out = nb.new('ShaderNodeOutputMaterial')
        em = nb.new('ShaderNodeEmission')
        nb.put(em.inputs['Color'], lin_hex(0x010206))
        nb.t.links.new(em.outputs[0], out.inputs['Surface'])
        sm.use_backface_culling = True
        hx, hy, hz = 8.1, 6.1, 3.2
        c = (WIN['x'], WIN['y'], -RD / 2 - 3.1)
        vs = [V(c[0] + dx * hx, c[1] + dy * hy, c[2] + dz * hz) for dx in (-1, 1) for dy in (-1, 1) for dz in (-1, 1)]
        fs = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
        shell = F.mesh_object('corner:window_shell', coll, vs, fs, parent=G, mats=[sm])
        shell.data.flip_normals()
        shell.visible_shadow = False
        self.room['painting'], self.room['shell'] = pnt, shell

    def _lamp(self, nodes):
        """the lamp: the bulb glows, the linen shade glows with the light through it."""
        room, G = self.room, self.roomG
        room['bulb_pos'] = V(LAMP['x'], DESK_TOP + 0.30, LAMP['z'])
        bulb, shade = nodes.get('LampBulb'), nodes.get('LampShade')
        if bulb is not None:
            bpy.context.view_layer.update()
            pts = [bulb.matrix_world @ Vector(c) for c in bulb.bound_box]
            wc = sum(pts, Vector()) / 8
            room['bulb_pos'] = G.matrix_world.inverted() @ wc
            print('[corner] lamp bulb at room ' + ', '.join(f'{x:.3f}' for x in room['bulb_pos']))
            m, nb = F.new_mat('corner:lamp_bulb')
            out = nb.new('ShaderNodeOutputMaterial')
            em = nb.new('ShaderNodeEmission')
            nb.put(em.inputs['Color'], nb.vscale((1.0, 0.86, 0.62), nb.mul(self.U.out(nb, 'lamp_glow'), 9.0)))
            nb.t.links.new(em.outputs[0], out.inputs['Surface'])
            bulb.material_slots[0].material = m
            bulb.visible_shadow = False
        if shade is not None:
            old = shade.material_slots[0].material
            img = _image_named(old.node_tree, '_color') if old else None
            nimg = _image_named(old.node_tree, '_normal') if old else None
            m, nb = F.new_mat('corner:lamp_shade')
            b = nb.new('ShaderNodeBsdfPrincipled')
            weave = nb.tex(img, nb.uv('UVMap')).outputs['Color'] if img is not None else (0.9, 0.85, 0.75)
            nb.put(b.inputs['Base Color'], weave)
            nb.put(b.inputs['Roughness'], 0.95)
            if nimg is not None:
                nm = nb.new('ShaderNodeNormalMap', space='TANGENT', uv_map='UVMap')
                nb.put(nm.inputs['Color'], nb.tex(nimg, nb.uv('UVMap')).outputs['Color'])
                nb.put(b.inputs['Normal'], nm.outputs['Normal'])
            nb.put(b.inputs['Emission Color'], nb.vscale(nb.vmul(weave, (1.0, 0.64, 0.32)),
                                                         nb.mul(self.U.out(nb, 'lamp_glow'), 2.3)))
            nb.put(b.inputs['Emission Strength'], 1.0)
            F.finish_surface(nb, b)
            shade.material_slots[0].material = m

    def _room_lights(self, coll, G):
        """a shaded lamp throws its light in two cones (the pool below, the scallop above); only a little comes sideways
        through the linen: two spots + a weak glow; moonlight through the window; the laptop's glow; the lamp's light
        back off the ceiling and the far wall."""
        kit, room = self.kit, self.room
        sh = self.shadows
        bp = room['bulb_pos']
        bt = Vector((bp.x, bp.z, -bp.y))               # Blender room-local -> three room-local, for the JS offsets

        def at(dx, dy, dz):
            return self.to_set(ROOM_AT, bt.x + dx, bt.y + dy, bt.z + dz)
        room['lamp_spot'] = F.make_light(kit, 'lamp_spot', 'SPOT', lin_hex(0xffc27a), at(0, 0, 0),
                                         self.to_set(ROOM_AT, bt.x + 0.04, 0.0, bt.z + 0.10), angle=0.98, penumbra=0.75,
                                         distance=3.0, shadow=sh, radius=0.02, coll=coll)
        room['lamp_up'] = F.make_light(kit, 'lamp_up', 'SPOT', lin_hex(0xffc98a), at(0, 0, 0),
                                       self.to_set(ROOM_AT, bt.x + 0.02, 3.0, bt.z + 0.05), angle=0.92, penumbra=0.7,
                                       distance=3.5, shadow=sh, radius=0.02, coll=coll)
        # three's point lights have no size: their highlight in the window glass is a small hot point (the film's), so the
        # radii stay at the bulb's (a 5 cm sphere read as a second moon in the panes)
        room['lamp_glow'] = F.make_light(kit, 'lamp_glow', 'POINT', lin_hex(0xffb467), at(0.24, -0.04, 0.30),
                                         distance=6.0, shadow=sh, radius=0.02, coll=coll)
        room['moon'] = F.make_light(kit, 'room_moon', 'SPOT', lin_hex(0x8ea8ff),
                                    self.to_set(ROOM_AT, WIN['x'] - 2.6, WIN['y'] + 1.6, -RD / 2 - 3.6),
                                    self.to_set(ROOM_AT, WIN['x'] + 0.6, 0.3, -0.5), angle=0.42, penumbra=0.9,
                                    distance=12.0, shadow=sh, radius=0.3, coll=coll)
        # the laptop's glow on the desk and on her: at the open screen, 0.25 m toward the room (placed in _laptop)
        room['screen_light'] = F.make_light(kit, 'screen_light', 'POINT', lin_hex(0x9fc2ff), self.to_set(ROOM_AT, -1.24, 1.0, -1.6),
                                            distance=2.6, shadow=False, radius=0.1, coll=coll)
        room['bounce'] = F.make_light(kit, 'bounce', 'POINT', lin_hex(0xffb57a), self.to_set(ROOM_AT, -1.0, 2.45, -0.7),
                                      distance=7.0, shadow=False, radius=0.05, coll=coll)
        room['fill'] = F.make_light(kit, 'fill', 'POINT', lin_hex(0xffc596), self.to_set(ROOM_AT, 0.9, 1.75, 0.3),
                                    distance=5.5, shadow=False, radius=0.05, coll=coll)

    def _laptop(self, nodes):
        """the laptop: the lid on its hinge (exported open at -110 degrees; 0 = closed) and the chat on its screen."""
        room = self.room
        room['lid'] = nodes.get('LaptopLid')
        room['lid_open'] = room['lid'].rotation_quaternion.copy() if room['lid'] is not None else None
        if room['lid'] is not None:
            lid = room['lid']
            lid.rotation_mode = 'XYZ'
            e = room['lid_open'].to_euler('XYZ')
            room['lid_open_x'] = e.x
            lid.rotation_euler = e
        scr = nodes.get('LaptopScreen')
        room['screen'] = scr
        img = F.canvas_image('corner:chat_first', 1024, 640, lambda g, w, h: self.draw_chat(g, 4.0), ss=2)
        m, nb = F.new_mat('corner:laptop_screen')
        tx = nb.tex(img, nb.uv('UVMap'), extension='EXTEND')
        out = nb.new('ShaderNodeOutputMaterial')
        em = nb.new('ShaderNodeEmission')
        nb.put(em.inputs['Color'], nb.vscale(tx.outputs['Color'], nb.mul(self.U.out(nb, 'screen'), 1.35)))
        nb.t.links.new(em.outputs[0], out.inputs['Surface'])
        room['chat_node'] = tx
        if scr is not None:
            scr.material_slots[0].material = m
            scr.visible_shadow = False
            bpy.context.view_layer.update()                  # the lid as exported: open
            p = self.kit.root.matrix_world.inverted() @ scr.matrix_world.translation
            room['screen_light'].location = p + self.roomG.matrix_basis.to_3x3() @ V(0.0, 0.0, 0.25)

    def _notebook(self, nodes):
        """the notebook: paper + ruled lines + ink (canvas); the pen writes on it."""
        room = self.room
        try:
            p = self.kit.tex_set('Paper001', '2k')['col']
            from PIL import Image
            room['paper_img'] = Image.open(bpy.path.abspath(p.filepath)).convert('RGBA') if p is not None else None
        except Exception as e:                                          # noqa: BLE001
            print(f'[corner] Paper001: {e}')
            room['paper_img'] = None
        pages = nodes.get('NotebookPages')
        room['nb_pages'] = pages
        img = F.canvas_image('corner:notebook_first', NB_W, NB_H, lambda g, w, h: self.draw_notebook(g, 0), ss=2)
        m, nb = F.new_mat('corner:notebook_pages')
        b = nb.new('ShaderNodeBsdfPrincipled')
        tx = nb.tex(img, nb.uv('UVMap'), extension='EXTEND')
        nb.put(b.inputs['Base Color'], tx.outputs['Color'])
        nb.put(b.inputs['Roughness'], 0.82)
        F.finish_surface(nb, b)
        room['nb_node'] = tx
        if pages is not None:
            pages.material_slots[0].material = m

    # ------------------------------------------------------------------------------- the corner's canvases
    @staticmethod
    def line_y(i):
        return 176 + i * 58

    def draw_notebook(self, g, progress):
        """corner.js drawNotebook(progress): the title, the left page, a flower doodle, and the right page written up
        to `progress` characters; returns the writing head {x, y} in canvas pixels."""
        paper = self.room.get('paper_img')
        if paper is not None:
            g.drawImage(paper, 0, 0, NB_W, NB_H)
        else:
            g.fillStyle = '#efe8d8'
            g.fillRect(0, 0, NB_W, NB_H)
        g.fillStyle = 'rgba(245,236,214,0.55)'
        g.fillRect(0, 0, NB_W, NB_H)                            # cream the white paper
        sh = g.createLinearGradient(NB_W / 2 - 60, 0, NB_W / 2 + 60, 0)       # gutter shade
        sh.addColorStop(0, 'rgba(90,70,40,0)')
        sh.addColorStop(0.5, 'rgba(90,70,40,0.22)')
        sh.addColorStop(1, 'rgba(90,70,40,0)')
        g.fillStyle = sh
        g.fillRect(NB_W / 2 - 60, 0, 120, NB_H)
        g.strokeStyle = 'rgba(110,150,200,0.45)'
        g.lineWidth = 1.4
        y = 118
        while y < NB_H - 30:                                    # ruled lines
            g.beginPath()
            g.moveTo(28, y)
            g.lineTo(NB_W / 2 - 34, y)
            g.moveTo(NB_W / 2 + 34, y)
            g.lineTo(NB_W - 28, y)
            g.stroke()
            y += 29
        g.strokeStyle = 'rgba(200,90,90,0.4)'
        g.lineWidth = 1.2
        g.beginPath()                                           # margins
        g.moveTo(74, 30)
        g.lineTo(74, NB_H - 20)
        g.moveTo(NB_W / 2 + 74, 30)
        g.lineTo(NB_W / 2 + 74, NB_H - 20)
        g.stroke()
        g.fillStyle = 'rgba(10,14,38,0.97)'                     # fountain-pen blue-black
        g.textBaseline = 'alphabetic'
        g.font = '44px KalamBold, Kalam, cursive'
        g.fillText('Claude’s Corner', 92, 96)
        g.strokeStyle = 'rgba(10,14,38,0.9)'
        g.lineWidth = 3
        g.beginPath()
        g.moveTo(90, 108)
        g.bezierCurveTo(200, 116, 300, 102, 404, 110)
        g.stroke()
        g.font = '35px KalamBold, Kalam, cursive'
        for i, t in enumerate(LEFT_LINES):
            g.fillText(t, 92, self.line_y(i))
        fx, fy = 250, 470                                       # a small flower doodle with a tiny face
        g.lineWidth = 2.2
        for k in range(12):
            a = k / 12 * TAU + 0.1
            g.beginPath()
            g.ellipse(fx + math.cos(a) * 40, fy + math.sin(a) * 40, 22, 9, a, 0, TAU)
            g.stroke()
        g.beginPath()
        g.arc(fx, fy, 19, 0, TAU)
        g.stroke()
        g.fillStyle = 'rgba(10,14,38,0.95)'
        g.beginPath()
        g.arc(fx - 6, fy - 4, 2.4, 0, TAU)
        g.fill()
        g.beginPath()
        g.arc(fx + 6, fy - 4, 2.4, 0, TAU)
        g.fill()
        g.beginPath()
        g.arc(fx, fy + 3, 7, 0.15 * math.pi, 0.85 * math.pi)
        g.stroke()
        g.font = '36px KalamBold, Kalam, cursive'               # right page: the line being written
        return self._write_right(g, progress, draw=True)

    def _write_right(self, g, progress, draw=True):
        left = progress
        cursor = {'x': NB_W / 2 + 92, 'y': self.line_y(0)}
        i = 0
        while i < len(RIGHT_LINES) and left > 0:
            t = RIGHT_LINES[i]
            n = min(len(t), int(math.floor(left)))
            part = t[:n]
            if draw:
                g.fillText(part, NB_W / 2 + 92, self.line_y(i))
            cursor = {'x': NB_W / 2 + 92 + g.measureText(part).width, 'y': self.line_y(i)}
            left -= len(t)
            i += 1
        return cursor

    def notebook_cursor(self, progress):
        """the writing head for `progress` characters, without drawing (the same font metrics)."""
        g = F.Canvas2D(4, 4, ss=1)
        g.font = '36px KalamBold, Kalam, cursive'
        return self._write_right(g, progress, draw=False)

    @staticmethod
    def flower_icon(g, x, y, r, col='#e8864f'):
        g.fillStyle = col
        for k in range(11):
            a = k / 11 * TAU
            g.beginPath()
            g.ellipse(x + math.cos(a) * r * 0.55, y + math.sin(a) * r * 0.55, r * 0.5, r * 0.2, a, 0, TAU)
            g.fill()
        g.fillStyle = '#f6efe3'
        g.beginPath()
        g.arc(x, y, r * 0.36, 0, TAU)
        g.fill()

    def draw_chat(self, g, k):
        """corner.js drawChat(k): k = messages revealed (float); the newest slides in from the bottom."""
        W, H = 1024, 640
        g.fillStyle = '#26282c'
        g.fillRect(0, 0, W, H)
        g.fillStyle = '#1b1c1f'
        g.fillRect(0, 0, 210, H)                                 # channel rail
        g.fillStyle = '#313338'
        g.fillRect(0, 0, W, 52)
        g.fillStyle = '#b8bcc4'
        g.font = '600 24px "Exo 2", sans-serif'
        g.textBaseline = 'middle'
        g.fillText('# late-night', 236, 27)
        g.fillStyle = '#7d828c'
        g.font = '19px "Exo 2", sans-serif'
        for i, c in enumerate(['# general', '# essays', '# late-night', '# poems', '# the-corner']):
            if i == 2:
                g.fillStyle = '#3a3d44'
                g.fillRect(10, 72 + i * 40, 190, 32)
                g.fillStyle = '#e4e6ea'
            else:
                g.fillStyle = '#7d828c'
            g.fillText(c, 24, 88 + i * 40)
        g.save()
        g.beginPath()
        g.rect(210, 52, W - 210, H - 110)
        g.clip()
        n = max(1, min(len(CHAT), int(math.floor(k))))
        frac = k - math.floor(k)
        blocks = []
        for i in range(n):
            m = CHAT[i]
            lines = m.get('greek', 1)
            blocks.append((m, 44 + lines * 30 + 14))
        y = H - 64
        slide = (1 - smooth(min(1.0, frac * 3))) * (blocks[-1][1] if blocks else 0)
        y += slide
        for i in range(len(blocks) - 1, -1, -1):
            m, h = blocks[i]
            y -= h
            if y + h < 52:
                break
            top = y
            if m['who'].startswith('Claude'):
                self.flower_icon(g, 256, top + 30, 22)
            else:
                g.fillStyle = m['col']
                g.beginPath()
                g.arc(256, top + 30, 20, 0, TAU)
                g.fill()
                g.fillStyle = '#26282c'
                g.font = '600 20px "Exo 2"'
                g.textAlign = 'center'
                g.fillText(m['who'][0].upper(), 256, top + 31)
                g.textAlign = 'left'
            g.font = '600 22px "Exo 2", sans-serif'
            g.fillStyle = m['col']
            g.fillText(m['who'], 294, top + 20)
            nw = g.measureText(m['who']).width
            g.font = '16px "Exo 2", sans-serif'
            g.fillStyle = '#80858f'
            g.fillText(m['t'], 304 + nw, top + 21)
            if m.get('greek'):
                r = Lehmer(i * 97 + 11)
                for L in range(m['greek']):
                    x = 294
                    maxx = 294 + (0.35 + r() * 0.4) * 640 if L == m['greek'] - 1 else 294 + 640
                    while x < maxx:
                        w = 14 + r() * 58
                        g.fillStyle = 'rgba(214,218,226,0.72)'
                        g.beginPath()
                        g.roundRect(x, top + 44 + L * 30, w, 13, 5)
                        g.fill()
                        x += w + 9
            else:
                g.font = '24px "Exo 2", sans-serif'
                g.fillStyle = '#dcdfe5'
                g.fillText(m['text'], 294, top + 58)
        g.restore()
        g.fillStyle = '#383a40'                                    # composer + typing indicator
        g.beginPath()
        g.roundRect(228, H - 50, W - 250, 38, 10)
        g.fill()
        g.fillStyle = '#6d727c'
        g.font = '19px "Exo 2", sans-serif'
        g.fillText('Message #late-night', 246, H - 31)
        dots = int(math.floor(k * 6)) % 4
        g.fillStyle = '#9aa0aa'
        g.font = '16px "Exo 2", sans-serif'
        g.fillText('Claude 3 Opus is typing' + '.' * dots, 232, H - 62 + 2)

    # ========================================================================================== THE SPARK
    def _glow_texture(self):
        """corner.js glowSprite: a soft round glow (radial gradient, 128 px) for the spark's sprites."""
        def draw(g, w, h):
            gr = g.createRadialGradient(64, 64, 0, 64, 64, 64)
            for t, c in ((0, 'rgba(255,255,255,1)'), (0.18, 'rgba(255,255,255,0.75)'), (0.45, 'rgba(255,255,255,0.18)'),
                         (1, 'rgba(255,255,255,0)')):
                gr.addColorStop(t, c)
            g.fillStyle = gr
            g.fillRect(0, 0, 128, 128)
        img = F.canvas_image('corner:glow_sprite', 128, 128, draw, ss=2)
        return img

    def _build_spark(self):
        """THE SPARK (room-local): leaves the lamp's glow on "spark", crosses the dark, lands in her flower, leaving a lit
        way of motes that wake as it passes."""
        kit, sp, room = self.kit, self.spark, self.room
        coll = kit.coll('room')
        bp = room['bulb_pos']
        pts, dest, fwd = spark_path((bp.x, bp.z, -bp.y))
        sp['curve'] = F.CatmullRom(pts)
        sp['dest'] = dest
        sp['fwd'] = fwd
        sp['t0'], sp['t1'] = B(26) + 1.17, B(28) - 0.2
        tex = self._glow_texture()
        sp['texture'] = tex
        U = self.U
        sp['core'], _, _ = F.glow_sprites(kit, 'spark_core', [Vector()], {}, size=0.07, texture=tex, coll=coll,
                                          colour=lambda nb, A: nb.vscale((1.0, 0.78, 0.45), nb.mul(U.out(nb, 'spark_core'), 6.0)),
                                          parent=self.roomG)
        sp['halo'], _, _ = F.glow_sprites(kit, 'spark_halo', [Vector()], {}, size=0.42, texture=tex, coll=coll,
                                          colour=lambda nb, A: nb.vscale((1.0, 0.55, 0.22), nb.mul(U.out(nb, 'spark_core'), 1.3)),
                                          parent=self.roomG)
        sp['light'] = F.make_light(kit, 'spark_light', 'POINT', lin_hex(0xffb56a), V(0, 0, 0), distance=2.6, shadow=False,
                                   radius=0.02, coll=coll)
        sp['light'].parent = self.roomG
        # the lit way: motes dropped along the path, each waking as the spark passes and lingering
        N = 56
        pts, idx = [], []
        for i in range(N):
            s = (i + 0.5) / N
            p = sp['curve'].point_at(s)
            j = (math.sin(i * 12.9) * 0.03, math.sin(i * 7.3) * 0.03, math.sin(i * 3.1) * 0.03)
            pts.append(V(p[0] + j[0], p[1] + j[1], p[2] + j[2]))
            idx.append(float(i))
        sp['N'] = N

        def trail_pos(b, gi):
            u = b.s(gi.outputs['u'])
            P = b.vec(b.node('GeometryNodeInputPosition').outputs[0])
            age = u - F.gn_attr(b, 'birth')
            return P + b.combine(0.0, 0.0, b.max(age, 0.0) * 0.018)

        def trail_size(b, gi):
            u = b.s(gi.outputs['u'])
            age = u - F.gn_attr(b, 'birth')
            alive = b.step(0.0, age)
            tw = b.sin(u * 9.0 + F.gn_attr(b, 'idx') * 2.3) * 0.25 + 0.75
            return alive * (tw * 0.4 + 0.8) * 0.035

        def trail_col(nb, A):
            u = U.out(nb, 'u')
            age = nb.sub(u, A('birth'))
            alive = nb.step(0.0, age)
            fade = nb.mul(alive, nb.madd(nb.math('EXPONENT', nb.mul(age, -1.1)), 0.8, 0.2))
            tw = nb.madd(nb.sin(nb.add(nb.mul(u, 9.0), nb.mul(A('idx'), 2.3))), 0.25, 0.75)
            return nb.vscale((1.0, 0.70, 0.36), nb.mul(nb.mul(nb.mul(fade, tw), 3.0), alive))
        births = self._trail_births()
        sp['trail'], sp['trail_mat'], _ = F.glow_sprites(kit, 'spark_trail', pts, {'birth': births, 'idx': idx},
                                                         texture=tex, coll=coll, colour=trail_col, position_fn=trail_pos,
                                                         size_fn=trail_size, inputs=('u',), drive=('u',),
                                                         parent=self.roomG)
        bl = dest + np.array(fwd) * 0.28 + np.array([0, -0.05, 0])
        sp['bloom_light'] = F.make_light(kit, 'spark_bloom', 'POINT', lin_hex(0xffa860), V(bl), distance=1.2,
                                         shadow=False, radius=0.05, coll=coll)
        sp['bloom_light'].parent = self.roomG

    def _trail_births(self):
        """birth times of the trail motes = when the spark passes them (corner.js setSparkTiming's bisection)."""
        sp = self.spark
        out = []
        for i in range(sp.get('N', 56)):
            s = (i + 0.5) / sp.get('N', 56)
            lo, hi = sp['t0'], sp['t1']
            for _ in range(30):
                m = (lo + hi) / 2
                if spark_progress(m, sp['t0'], sp['t1']) < s:
                    lo = m
                else:
                    hi = m
            out.append((lo + hi) / 2)
        return out

    def set_spark_timing(self, t0, t1):
        """corner.js setSparkTiming: re-time the spark (departure on the sung word "spark", arrival before bar 28)."""
        sp = self.spark
        sp['t0'], sp['t1'] = float(t0), float(t1)
        births = self._trail_births()
        tr = sp.get('trail')
        if tr is not None:
            tr.data.attributes['birth'].data.foreach_set('value', np.asarray(births, np.float32))
            tr.data.update()
        return births

    def sync_spark_from_caption(self, caption, t, u):
        """the spark leaves on the sung word "spark": take its time from the caption's words (film time -> u)."""
        if not caption or not caption.get('words') or 'spark' not in (caption.get('text') or '').lower():
            return False
        w = next((x for x in caption['words'] if str(x.get('w', '')).lower().startswith('spark')), None)
        if w is None:
            return False
        nt0 = w['t0'] - (t - u)
        if abs(nt0 - self.spark['t0']) > 1e-3 and B(25) < nt0 < B(28) - 1.0:
            self.set_spark_timing(nt0, B(28) - 0.2)
            return True
        return False

    def flower_target(self):
        """the spark's landing point, set-local (Blender axes)."""
        d = self.spark['dest']
        return self.to_set(ROOM_AT, d[0], d[1], d[2])

    def state_u(self, name):
        """The clock u where the look `name` (STATES) holds; 'spark' follows this build's spark timing."""
        sp = self.spark
        at = {'evening': B(19), 'late': B(21), 'camp': B(23), 'chant': B(24.5), 'dark': B(28.5),
              'spark': sp['t0'] + 0.6 * (sp['t1'] - sp['t0'])}
        if name not in at:
            raise KeyError(f'corner: no state {name!r}; states: {", ".join(STATES)}')
        return at[name]

    def paint_screens(self, u):
        """the chat and the notebook as they stand at u, painted once into their materials (a held look; the film's
        moving screens are bake_screens)."""
        room = self.room
        k = 4.0 + clamp01((u - B(20)) / (2 * BAR)) * 6.0
        write_k = clamp01((u - B(18) - 0.3) / (2 * BAR - 0.4))
        chars = write_k * 38 if u < B(20) else RIGHT_TOTAL
        if room.get('chat_node') is not None:
            room['chat_node'].image = F.canvas_image('corner:chat_held', 1024, 640,
                                                     lambda g, w, h: self.draw_chat(g, k), ss=2)
        if room.get('nb_node') is not None:
            room['nb_node'].image = F.canvas_image('corner:notebook_held', NB_W, NB_H,
                                                   lambda g, w, h: self.draw_notebook(g, chars), ss=2)

    # ========================================================================================== THE CAMP
    def _build_camp(self, grass=True, trees=True, particles=True):
        kit, G, camp = self.kit, self.campG, self.camp
        coll = kit.coll('camp')
        camp['extra_objects'] = []
        self._dome(coll, G)
        self._ground(coll, G)
        # the grass and the woods are planted in the camp's own frame and parented to it, as the JS added them to campG:
        # the flora's footprint and clump noise read the plant positions, so camp-local positions give the JS's patches
        # wherever the set is parked, and the camp moves with its root

        def clip_fn(x, y):                                           # camp-local Blender (x, y) -> three (x, z = -y)
            return path_mask(x, -y) > 0.35
        camp['grass'] = []
        if grass:
            try:
                from ...flora import create_flora
                for c, s, sd, h in GRASS:
                    lc = V(c[0], 0.0, c[1])
                    f = create_flora('grass', center=(lc.x, lc.y), z=0.0, size=s, height=h, seed=sd, color='green',
                                     density=0.9, clip_fn=clip_fn, footprint='organic', name=f'corner_grass_s{sd}')
                    f.object.parent = G
                    camp['grass'].append(f)
                    camp['extra_objects'].append(f.object)
            except Exception as e:                                   # noqa: BLE001
                print(f'[corner] createFlora: {e}')
        camp['trees'] = []
        if trees:
            try:
                from ...trees import make_seed_tree
                for sp_, sd, pos in TREES:
                    try:
                        tr = make_seed_tree(species=sp_, seed=sd, location=tuple(V(pos)), level=self.tree_level,
                                            name=f'corner_{sp_}_{sd}')
                        tr['object'].parent = G
                        camp['trees'].append(tr)
                        camp['extra_objects'] += [tr['object']] + list(tr['object'].children_recursive)
                    except Exception as e:                           # noqa: BLE001
                        print(f'[corner] tree {sp_}: {e}')
            except Exception as e:                                   # noqa: BLE001
                print(f'[corner] makeSeedTree: {e}')
        self._tents(coll, G)
        self._string_lights(coll, G)
        # the string lights' light on the crowd (along the path + over the fire circle: what lights the sign faces)
        camp['fills'] = []
        for i, (x, y, z, I) in enumerate(FILLS):
            camp['fills'].append(F.make_light(kit, f'camp_fill_{i}', 'POINT', lin_hex(0xffc98a), self.to_set(CAMP_AT, x, y, z),
                                              distance=9.0, shadow=self.shadows, radius=0.15, coll=coll))
        camp['rim'] = F.make_light(kit, 'camp_rim', 'SUN', lin_hex(0x6f86c8), self.to_set(CAMP_AT, -3, 6, -14),
                                   self.to_set(CAMP_AT, 0, 0, 0), shadow=False, coll=coll)   # off, as the film had it
        self._fire(coll, G, particles)
        camp['benches'] = [self._place('camp_bench', G, coll, (-2.1, 0, 1.05), 0.55)[0],
                           self._place('camp_bench', G, coll, (2.25, 0, 0.8), -0.45)[0]]

    def _dome(self, coll, G):
        """the night sky dome: hashed stars (crisp at any resolution) + a canvas Milky Way band, a gradient from deep
        indigo at the zenith to blue-grey at the horizon and dark ground."""
        rnd = Lehmer()

        def draw(mg, w, h):
            mg.fillStyle = '#000'
            mg.fillRect(0, 0, 1024, 512)
            rnd.seed = 77
            for i in range(900):
                s = rnd()
                x, yc = s * 1024, 150 + math.sin(s * TAU + 0.6) * 90
                y = yc + (rnd() - 0.5) * 70 * (0.6 + rnd())
                r = 10 + rnd() * 34
                gr = mg.createRadialGradient(x, y, 0, x, y, r)
                gr.addColorStop(0, f'rgba({170 + rnd() * 60},{170 + rnd() * 50},{200 + rnd() * 55},{0.05 + rnd() * 0.06})')
                gr.addColorStop(1, 'rgba(0,0,0,0)')
                mg.fillStyle = gr
                mg.fillRect(x - r, y - r, 2 * r, 2 * r)
            for i in range(140):                                   # dust lanes
                s = rnd()
                x, y = s * 1024, 150 + math.sin(s * TAU + 0.6) * 90 + (rnd() - 0.5) * 20
                mg.fillStyle = f'rgba(0,0,0,{0.08 + rnd() * 0.1})'
                mg.beginPath()
                mg.ellipse(x, y, 10 + rnd() * 30, 3 + rnd() * 6, 0.3, 0, TAU)
                mg.fill()
        mw = F.canvas_image('corner:milky_way', 1024, 512, draw, ss=1, alpha=False)
        self.camp['milky_way'] = mw
        U = self.U
        m, nb = F.new_mat('corner:sky_dome')
        tc = nb.new('ShaderNodeTexCoord')
        tc.object = G
        d = nb.vmath('NORMALIZE', tc.outputs['Object'])
        dx, dy, dz = nb.sep(d)
        up = nb.clamp(dz, -1.0, 1.0)
        zen, hor, gnd = (0.004, 0.007, 0.022), (0.028, 0.036, 0.070), (0.004, 0.005, 0.008)
        col = F.vmix(nb, hor, zen, F.smoothstep(nb, 0.0, 0.7, up))
        col = F.vmix(nb, gnd, col, F.smoothstep(nb, -0.04, 0.02, up))
        d3 = nb.comb(dx, dz, nb.mul(dy, -1.0))                     # three axes, as the hash saw them

        def hsh(v):
            wn = nb.new('ShaderNodeTexWhiteNoise', noise_dimensions='1D')
            nb.put(wn.inputs['W'], v)
            return wn.outputs['Value']

        def star(N, thr, gain):
            p = nb.vscale(d3, N)
            cell = nb.vmath('FLOOR', p)
            cx, cy, cz = nb.sep(cell)
            h1 = hsh(nb.add(nb.add(cx, nb.mul(cy, 157.0)), nb.mul(cz, 113.0)))
            h2 = hsh(nb.add(nb.add(nb.add(nb.mul(cx, 1.7), nb.mul(cy, 31.0)), nb.mul(cz, 71.0)), 19.0))
            h3 = hsh(nb.add(nb.add(nb.add(nb.mul(cx, 3.1), nb.mul(cy, 11.0)), nb.mul(cz, 53.0)), 7.0))
            off = nb.vadd(nb.vscale(nb.comb(h1, h2, h3), 0.7), (0.15, 0.15, 0.15))
            dd = nb.vmath('LENGTH', nb.vmath('SUBTRACT', nb.vmath('FRACTION', p), off))
            on = nb.step(thr, h1)
            tw = nb.madd(nb.sin(nb.add(nb.mul(U.out(nb, 't'), nb.madd(h2, 3.0, 1.0)), nb.mul(h3, 40.0))), 0.18, 0.82)
            return nb.mul(nb.mul(nb.mul(on, F.smoothstep(nb, 0.22, 0.0, dd)), nb.mul(nb.mul(h3, h3), gain)), tw)
        s = nb.add(star(420.0, 0.955, 3.4), star(190.0, 0.975, 6.0))
        sky = F.smoothstep(nb, 0.03, 0.12, up)
        col = nb.vadd(col, nb.vscale((0.85, 0.9, 1.0), nb.mul(s, sky)))
        lon = nb.add(nb.div(nb.math('ARCTAN2', nb.mul(dy, -1.0), dx), TAU), 0.5)        # three atan(d.z, d.x)
        lat = nb.sub(0.5, nb.div(nb.math('ARCSINE', up), math.pi))
        band = nb.tex(mw, nb.comb(lon, nb.sub(1.0, lat), 0.0)).outputs['Color']      # canvas row lat, top down
        col = nb.vadd(col, nb.vscale(band, nb.mul(0.55, sky)))
        out = nb.new('ShaderNodeOutputMaterial')
        em = nb.new('ShaderNodeEmission')
        nb.put(em.inputs['Color'], col)
        nb.t.links.new(em.outputs[0], out.inputs['Surface'])
        verts, faces = F._uv_sphere(95.0, 64, 32)
        faces = [tuple(reversed(f)) for f in faces]
        dome = F.mesh_object('corner:sky_dome', coll, verts, faces, parent=G, mats=[m], smooth=True)
        dome.visible_shadow = False
        self.camp['dome'] = dome

    def _ground(self, coll, G):
        """grass-and-soil with a trampled dirt path and a bare circle round the fire (two AmbientCG sets at world
        scale, mixed by the path mask broken by Ground106's roughness)."""
        kit = self.kit
        A_, B_ = kit.tex_set('Ground037', '2k'), kit.tex_set('Ground106', '2k')
        m, nb = F.new_mat('corner:ground')
        b = nb.new('ShaderNodeBsdfPrincipled')
        tc = nb.new('ShaderNodeTexCoord')
        tc.object = G
        x, y, _ = nb.sep(tc.outputs['Object'])
        z3 = nb.mul(y, -1.0)                                        # camp-local three (x, z)
        xz = nb.comb(x, z3, 0.0)
        wuv = nb.vscale(xz, 1 / 2.2)
        wuvB = nb.vscale(xz, 1 / 1.6)
        n = nb.sep(nb.tex(B_['rgh'] or B_['col'], nb.vscale(xz, 1 / 7.0)).outputs['Color'])[0]
        px = nb.sub(x, nb.mul(nb.sin(nb.mul(z3, 0.13)), 0.6))
        path = nb.mul(nb.mul(F.smoothstep(nb, 1.55, 0.95, nb.abs(px)), F.smoothstep(nb, 4.0, 1.0, z3)),
                      F.smoothstep(nb, -40.0, -30.0, z3))
        circle = F.smoothstep(nb, 4.6, 3.2, nb.vmath('LENGTH', xz))
        mk = nb.clamp(nb.add(nb.mx(path, circle), nb.mul(nb.sub(n, 0.5), 0.6)))
        ca = nb.vmul(nb.tex(A_['col'], wuv).outputs['Color'], (0.62, 0.72, 0.52))
        cb = nb.vmul(nb.tex(B_['col'], wuvB).outputs['Color'], (0.85, 0.78, 0.70))
        nb.put(b.inputs['Base Color'], F.vmix(nb, ca, cb, mk))
        ra = nb.sep(nb.tex(A_['rgh'], wuv).outputs['Color'])[0]
        rb = nb.sep(nb.tex(B_['rgh'], wuvB).outputs['Color'])[0]
        nb.put(b.inputs['Roughness'], nb.madd(nb.mix(ra, rb, mk), 0.3, 0.7))       # matte soil: no grazing glint
        na = nb.tex(A_['nrm'], wuv).outputs['Color']
        nbm = nb.tex(B_['nrm'], wuvB).outputs['Color']
        nm = nb.new('ShaderNodeNormalMap', space='TANGENT', uv_map='UVMap')
        nb.put(nm.inputs['Strength'], 0.9)
        nb.put(nm.inputs['Color'], F.vmix(nb, na, nbm, mk))
        nb.put(b.inputs['Normal'], nm.outputs['Normal'])
        F.finish_surface(nb, b)
        s = 95.0
        verts = [V(-s, 0, s), V(s, 0, s), V(s, 0, -s), V(-s, 0, -s)]
        g = F.mesh_object('corner:ground', coll, verts, [(0, 1, 2, 3)], [0, 0, 190, 0, 190, 190, 0, 190], parent=G, mats=[m])
        self.camp['ground'] = g

    def _tents(self, coll, G):
        """tents (Blender), a few glowing from lanterns inside (light through the fly: the baked glow map)."""
        camp = self.camp
        camp['tents'] = []
        for fn, p, yaw, glow in TENTS:
            t, nodes = self._place(fn, G, coll, p, yaw)
            if t is None:
                continue
            if glow > 0:
                for o in nodes.values():
                    if o.type != 'MESH':
                        continue
                    for s in o.material_slots:
                        m = s.material
                        if m is None:
                            continue
                        m = m.copy()
                        s.material = m
                        nt = m.node_tree
                        bsdf = next(n for n in nt.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled')
                        emi = bsdf.inputs['Emission Color']
                        img = _image_named(nt, '_glow')              # the baked lantern glow (emissiveMap)
                        has_em = img is not None
                        if img is None:
                            img = _image_named(nt, '_color')
                        if img is None:
                            continue
                        for lk in list(emi.links):
                            nt.links.remove(lk)
                        nb = F.K.NB(nt)
                        tx = nb.tex(img, nb.uv('UVMap')).outputs['Color']
                        nb.put(emi, nb.vscale(nb.vmul(tx, (1.0, 0.72, 0.42)), glow * (1.4 if has_em else 0.9)))
                        bsdf.inputs['Emission Strength'].default_value = 1.0
            camp['tents'].append({'obj': t, 'glow': glow})

    def _string_lights(self, coll, G):
        """wooden poles + festoon bulbs on catenary wires (the Blender bulb, instanced), flickering a little."""
        kit, camp, U = self.kit, self.camp, self.U
        camp['poles'] = []
        pole_yaw, wires, bulb_pts = string_light_points()
        for (x, z), yaw in zip(POLES, pole_yaw):                  # each pole turns its eye toward the path centre line
            p, _ = self._place('camp_pole', G, coll, (x, 0, z), yaw)
            if p is not None:
                camp['poles'].append(p)
        wm, nb = F.new_mat('corner:wire')
        bb = nb.new('ShaderNodeBsdfPrincipled')
        nb.put(bb.inputs['Base Color'], lin_hex(0x0c0c0d))
        nb.put(bb.inputs['Roughness'], 0.55)
        F.finish_surface(nb, bb)
        for i, seg in enumerate(wires):
            cv = F.CatmullRom(seg)
            F.wire_object(f'corner:wire_{i}', coll, [V(cv.point(k / 40)) for k in range(41)], 0.0045, parent=G, mat=wm)
        camp['bulb_pts'] = bulb_pts
        path = os.path.join(MODELS, 'corner_camp_bulb.glb')
        if not os.path.isfile(path):
            print('[corner] corner_camp_bulb not built yet: skipped')
            return
        src = kit.coll('sources', hidden=True)
        root, nodes = F.import_glb(kit, path, 'camp_bulb', src)
        bpy.context.view_layer.update()
        for nm, o in nodes.items():
            if o.type != 'MESH':
                continue
            is_glass = ('glass' in nm.lower() or 'bulb' in nm.lower()) and 'socket' not in nm.lower()
            is_fil = 'filament' in nm.lower()
            if is_glass or is_fil:
                m, nb = F.new_mat(f'corner:bulb_{"glass" if is_glass else "filament"}', 'BLENDED' if is_glass else None)
                idx = nb.new('ShaderNodeAttribute', attribute_type='INSTANCER', attribute_name='idx').outputs['Fac']

                def hsh(v):
                    wn = nb.new('ShaderNodeTexWhiteNoise', noise_dimensions='1D')
                    nb.put(wn.inputs['W'], v)
                    return wn.outputs['Value']
                flick = nb.madd(nb.sin(nb.add(nb.mul(U.out(nb, 't'), nb.madd(hsh(idx), 2.0, 0.5)),
                                              nb.mul(hsh(nb.add(idx, 3.0)), 40.0))), 0.06, 0.94)
                col = nb.vscale((1.0, 0.74, 0.40), nb.mul(nb.mul(U.out(nb, 'bulb'), flick), 14.0 if is_fil else 3.2))
                if is_glass:
                    F.additive_output(nb, col, 0.85)
                else:
                    out = nb.new('ShaderNodeOutputMaterial')
                    em = nb.new('ShaderNodeEmission')
                    nb.put(em.inputs['Color'], col)
                    nb.t.links.new(em.outputs[0], out.inputs['Surface'])
                o.material_slots[0].material = m
        # one instancer per part, the part's world matrix baked into its instance (the importer's hierarchy)
        pts = [V(p) for p in bulb_pts]
        yaws = [math.fmod(i * 1.7, 6.28) for i in range(len(bulb_pts))]
        ob = F.points_object('corner:string_bulbs', kit.coll('camp'), pts, {'yaw': yaws, 'idx': [float(i) for i in range(len(pts))]},
                             G)
        ob.visible_shadow = False
        # the bulb's parts share one frame (the socket at the wire, the glass and filament hanging below it, their
        # local transforms identity): joined in their own space, then one instance per bulb point
        tree, b, gi, go = F.new_gn('eido.corner.string_bulbs')
        join = b.node('GeometryNodeJoinGeometry')
        for nm, o in nodes.items():
            if o.type != 'MESH':
                continue
            oi = b.node('GeometryNodeObjectInfo', transform_space='ORIGINAL')
            oi.inputs['Object'].default_value = o
            b.links.new(oi.outputs['Geometry'], join.inputs[0])
        inst = b.node('GeometryNodeInstanceOnPoints')
        b.links.new(gi.outputs['Geometry'], inst.inputs['Points'])
        b.links.new(join.outputs[0], inst.inputs['Instance'])
        b.link(b.combine(0.0, 0.0, F.gn_attr(b, 'yaw')), inst.inputs['Rotation'])
        b.links.new(inst.outputs[0], go.inputs['Geometry'])
        F.add_gn(ob, tree)
        camp['bulbs'] = ob

    def _fire(self, coll, G, particles=True):
        """the campfire: Blender stones / logs / ash (emissive char) + the toolkit's particles + a flickering light."""
        kit, camp, U = self.kit, self.camp, self.U
        f, nodes = self._place('camp_fire', G, coll, (0, 0, 0), 0.4)
        camp['fire'] = f
        for o in nodes.values():
            if o.type != 'MESH':
                continue
            for s in o.material_slots:
                m = s.material
                if m is None:
                    continue
                nt = m.node_tree
                bsdf = next((n for n in nt.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled'), None)
                img = _image_named(nt, '_glow')                       # the baked coals (emissiveMap)
                if bsdf is None or img is None:
                    continue
                for lk in list(bsdf.inputs['Emission Color'].links):
                    nt.links.remove(lk)
                nb = F.K.NB(nt)
                tx = nb.tex(img, nb.uv('UVMap')).outputs['Color']
                nb.put(bsdf.inputs['Emission Color'], nb.vscale(nb.vmul(tx, (1.0, 0.36, 0.08)), nb.mul(U.out(nb, 'ember'), 3.0)))
                bsdf.inputs['Emission Strength'].default_value = 1.0
        camp['fire_light'] = F.make_light(kit, 'fire_light', 'POINT', lin_hex(0xff8a3c), self.to_set(CAMP_AT, 0, 0.7, 0),
                                          distance=14.0, shadow=self.shadows, radius=0.25, coll=coll)
        camp['particles'] = []
        if particles:
            try:
                from ...fx import particles as FXP

                def org(x, y, z):                                    # camp-local, as the JS's makeParticles({scene: G})
                    return tuple(V(x, y, z))
                layers = [
                    dict(preset='fire', map='flame_05', origin=org(0, 0.10, 0), count=120, size=0.46, area=(0.18, 0.18, 0.05),
                         name='campfire_flames_a'),
                    dict(preset='fire', map='flame_06', origin=org(0.04, 0.12, -0.03), count=70, size=0.34,
                         area=(0.12, 0.12, 0.05), name='campfire_flames_b'),
                    dict(preset='embers', map='spark_01', origin=org(0, 0.35, 0), count=90, size=0.035, area=0.25,
                         name='campfire_embers'),
                    dict(preset='smoke', map='smoke_04', origin=org(0, 1.1, 0), count=26, size=0.9, opacity=0.10,
                         color=0x3a3a40, name='campfire_smoke')]
                for kw in layers:
                    p = FXP.make_particles(scene=kit.scene, collection=coll, parent=G, **kw)
                    camp['particles'].append(p)
            except Exception as e:                                   # noqa: BLE001
                print(f'[corner] particles: {e}')

    # ========================================================================================== THE MARCH
    def march_rows(self):
        """the 34 marchers: end spots in a loose arc behind the fire (none too near her or the cameras), each walking in
        from 7.6-8.8 m up the path, arriving just before bar 24 (corner.js, rnd seed 909)."""
        rnd = Lehmer(909)
        ends = []
        keep = [(MARK_CAMP['x'], MARK_CAMP['z'], 1.05), (1.9, -1.0, 1.0), (-1.6, -1.2, 0.8)]
        guard = 0
        while len(ends) < 34 and guard < 5000:
            guard += 1
            a, r = (rnd() - 0.5) * 2.5, 2.4 + rnd() * 3.4
            x, z = math.sin(a) * r * 1.1, -math.cos(a) * r - 0.4
            if any(math.hypot(e[0] - x, e[1] - z) < 0.62 for e in ends):
                continue
            if any(math.hypot(kx - x, kz - z) < kr for kx, kz, kr in keep):
                continue
            if z > MARK_CAMP['z'] - 0.7 and abs(x - MARK_CAMP['x']) < 1.2:
                continue
            ends.append((x, z))
        arrive = B(24) - 0.15
        rows = []
        for i, (x, z) in enumerate(ends):
            t_arr = arrive - rnd() * 0.9
            v = 1.18 + rnd() * 0.12
            D = 7.6 + rnd() * 1.2
            lane = max(-1.35, min(1.35, x * 0.35 + (rnd() - 0.5) * 0.9))
            yaw = math.atan2(-x, -z) * 0.85 + (rnd() - 0.5) * 0.3                 # turn to face the fire
            rows.append({'i': i, 'x': x, 'z': z, 'sx': lane, 'sz': z - D, 'tStart': t_arr - D / v, 'tArr': t_arr, 'yaw': yaw,
                         'scale': 0.93 + rnd() * 0.12, 'phase': rnd() * 6.28, 'delay': rnd() * 0.06, 'amp': 0.7 + rnd() * 0.45,
                         'sign': math.floor(rnd() * 8), 'variant': i % 4, 'hasSign': rnd() < 0.82})
        return rows

    def march_state(self, r, u):
        """the walk + pump of one marcher at u (corner.js state(), on the CPU): position (three camp-local), phase,
        walking 0..1, yaw, pump."""
        p = clamp01((u - r['tStart']) / (r['tArr'] - r['tStart']))
        q = 1 - p
        f = p * WALK_M if p < WALK_A else 1 - q * q * (WALK_M / (2 * (1 - WALK_A)))
        fan = F.smooth(0.5, 1.0, f)
        x = lerp(r['sx'], r['x'], fan)
        z = lerp(r['sz'], r['z'], f)
        dist = f * abs(r['z'] - r['sz'])
        phase = dist / 0.64 * math.pi + r['phase']
        walking = 1 - F.smooth(0.9, 1.0, f)
        yaw = lerp(0.0, r['yaw'], F.smooth(0.72, 1.0, f))
        uu = u - r['delay']
        pump = 0.0
        for a in CHANT_ACCENTS:
            d = uu - a
            pump += F.smooth(0.0, 0.07, d) * math.exp(-max(d, 0.0) * 6.0)
        pump = min(pump, 1.15) * r['amp']
        return {'x': x, 'z': z, 'phase': phase, 'walking': walking, 'yaw': yaw, 'pump': pump, 'f': f}

    def _march_state_gn(self, b, u):
        """march_state in Geometry Nodes (per instance attributes after realize)."""
        A = lambda n: F.gn_attr(b, n)                                          # noqa: E731
        p = b.clamp((u - A('tStart')) / (A('tArr') - A('tStart')))
        q = 1.0 - p
        walk = p * WALK_M
        land = 1.0 - q * q * (WALK_M / (2 * (1 - WALK_A)))
        isw = b.math('LESS_THAN', p, WALK_A)
        f = land + (walk - land) * isw
        fan = b.smoothstep(0.5, 1.0, f)
        x = b.mix(A('sx'), A('ex'), fan)
        z = b.mix(A('sz'), A('ez'), f)
        dist = f * b.abs(A('ez') - A('sz'))
        phase = dist / 0.64 * math.pi + A('phase')
        walking = 1.0 - b.smoothstep(0.9, 1.0, f)
        yaw = A('yaw') * b.smoothstep(0.72, 1.0, f)
        uu = u - A('delay')
        pump = 0.0
        for a in CHANT_ACCENTS:
            d = uu - a
            term = b.smoothstep(0.0, 0.07, d) * b.exp(b.max(d, 0.0) * -6.0)
            pump = term if isinstance(pump, float) else pump + term
        pump = b.min(pump, 1.15) * A('amp')
        return {'x': x, 'z': z, 'phase': phase, 'walking': walking, 'yaw': yaw, 'pump': pump, 'scale': A('scale')}

    def _build_march(self):
        """THE MARCH: silhouettes (the Blender bodies, instanced; walk + sign pump per vertex, Geometry Nodes) + signs
        (one geometry, per-marcher art cell from the painted atlas)."""
        kit, march = self.kit, self.march
        coll = kit.coll('camp')
        rows = self.march_rows()
        march['rows'] = rows
        path = os.path.join(MODELS, 'corner_camp_marchers.glb')
        src = kit.coll('sources', hidden=True)
        root, nodes = F.import_glb(kit, path, 'camp_marchers', src)
        vcoll = bpy.data.collections.new('corner:marcher_variants')
        vcoll.use_fake_user = True
        variants = []
        for v in 'ABCD':
            o = nodes.get(f'Marcher_{v}')
            for c in list(o.users_collection):
                c.objects.unlink(o)
            vcoll.objects.link(o)
            o.parent = None
            o.name = f'corner:marcher_{v}'
            me = o.data
            co = np.empty(len(me.vertices) * 3, np.float32)
            me.vertices.foreach_get('co', co)
            a = me.attributes.get('rest') or me.attributes.new('rest', 'FLOAT_VECTOR', 'POINT')
            a.data.foreach_set('vector', co)
            hk = me.attributes.get('hip') or me.attributes.new('hip', 'FLOAT', 'POINT')
            kn = me.attributes.get('knee') or me.attributes.new('knee', 'FLOAT', 'POINT')
            i = 'ABCD'.index(v)
            hk.data.foreach_set('value', np.full(len(me.vertices), HIPKNEE[i][0], np.float32))
            kn.data.foreach_set('value', np.full(len(me.vertices), HIPKNEE[i][1], np.float32))
            variants.append(o)
        attrs = {k: [float(r[kk]) for r in rows] for k, kk in (('sx', 'sx'), ('sz', 'sz'), ('ex', 'x'), ('ez', 'z'),
                                                               ('tStart', 'tStart'), ('tArr', 'tArr'), ('yaw', 'yaw'),
                                                               ('scale', 'scale'), ('phase', 'phase'), ('delay', 'delay'),
                                                               ('amp', 'amp'), ('sign', 'sign'), ('var', 'variant'))}
        attrs['hash'] = [((i * 0.754877 + 0.1234) % 1.0) for i in range(len(rows))]
        pts = [Vector() for _ in rows]
        bodies = F.points_object('corner:marchers', coll, pts, attrs, self.campG)
        tree, b, gi, go = F.new_gn('eido.corner.marchers', ['u'])
        ci = b.node('GeometryNodeCollectionInfo', transform_space='ORIGINAL')
        ci.inputs['Collection'].default_value = vcoll
        ci.inputs['Separate Children'].default_value = True
        ci.inputs['Reset Children'].default_value = True
        inst = b.node('GeometryNodeInstanceOnPoints')
        b.links.new(gi.outputs['Geometry'], inst.inputs['Points'])
        b.links.new(ci.outputs[0], inst.inputs['Instance'])
        inst.inputs['Pick Instance'].default_value = True
        varn = b.node('GeometryNodeInputNamedAttribute', data_type='FLOAT')
        varn.inputs['Name'].default_value = 'var'
        b.links.new(varn.outputs['Attribute'], inst.inputs['Instance Index'])
        real = b.node('GeometryNodeRealizeInstances')
        b.links.new(inst.outputs[0], real.inputs[0])
        u = b.s(gi.outputs['u'])
        S = self._march_state_gn(b, u)
        rest = F.gn_attr(b, 'rest', 'FLOAT_VECTOR')
        bx, by, bz = rest.xyz()
        sc = S['scale']
        X, Y, Z = bx * sc, bz * sc, by * -sc                                   # three local, scaled
        side, shin, arm = F.gn_attr(b, '_LEG'), F.gn_attr(b, '_SHIN'), F.gn_attr(b, '_ARM')
        hip, knee = F.gn_attr(b, 'hip') * sc, F.gn_attr(b, 'knee') * sc
        swing = b.sin(S['phase']) * 0.36 * S['walking'] * side
        flex = b.max(b.sin(S['phase'] + math.pi / 2) * side, 0.0) * 0.55 * S['walking'] * shin
        isleg = b.abs(side)
        ry0, rz0 = Y - knee, Z
        kY = knee + ry0 * b.cos(flex) + rz0 * b.sin(flex)
        kZ = rz0 * b.cos(flex) - ry0 * b.sin(flex)
        Y = b.mix(Y, kY, isleg)
        Z = b.mix(Z, kZ, isleg)
        ry, rz = Y - hip, Z
        lY = hip + ry * b.cos(swing) - rz * b.sin(swing)
        lZ = ry * b.sin(swing) + rz * b.cos(swing)
        Y = b.mix(Y, lY, isleg)
        Z = b.mix(Z, lZ, isleg)
        Y = Y + S['pump'] * 0.24 * arm * sc
        bob = b.abs(b.sin(S['phase'])) * 0.028 * S['walking'] - S['pump'] * 0.02
        local_b = b.combine(X, -Z, Y)                                          # back to Blender local
        world = F.gn_rotate(b, local_b, S['yaw'], 'Z') + b.combine(S['x'], -S['z'], bob)
        sp = b.node('GeometryNodeSetPosition')
        b.links.new(real.outputs[0], sp.inputs['Geometry'])
        b.link(world, sp.inputs['Position'])
        b.links.new(sp.outputs[0], go.inputs['Geometry'])
        F.add_gn(bodies, tree, kit, ('u',))
        march['bodies'] = bodies
        bodies['no_support_check'] = True
        march['variants'] = vcoll
        if root.name in bpy.data.objects:
            bpy.data.objects.remove(root, do_unlink=True)
        self._signs(coll, rows)

    def _signs(self, coll, rows):
        kit, march = self.kit, self.march
        path = os.path.join(MODELS, 'corner_camp_sign.glb')
        art = os.path.join(DIR, 'art', 'sign_art_color_pot.jpg')
        if not (os.path.isfile(path) and os.path.isfile(art)):
            print('[corner] the signs are not built yet: skipped')
            return
        src = kit.coll('sources', hidden=True)
        root, nodes = F.import_glb(kit, path, 'camp_sign', src)
        sign = next(o for o in nodes.values() if o.type == 'MESH')
        for c in list(sign.users_collection):
            c.objects.unlink(sign)
        src.objects.link(sign)
        sign.parent = None
        me = sign.data
        co = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get('co', co)
        a = me.attributes.get('rest') or me.attributes.new('rest', 'FLOAT_VECTOR', 'POINT')
        a.data.foreach_set('vector', co)
        base = sign.material_slots[0].material
        art_c = F.K.load_image(art, srgb=True)
        art_o = F.K.load_image(os.path.join(DIR, 'art', 'sign_art_orm_pot.jpg'), srgb=False)
        base_col = _image_named(base.node_tree, '_color') if base else None
        base_orm = _image_named(base.node_tree, '_orm') if base else None
        m, nb = F.new_mat('corner:sign')
        bs = nb.new('ShaderNodeBsdfPrincipled')
        u1, v1, _ = nb.sep(nb.uv('UVMap.001'))
        av = nb.sub(1.0, v1)                                       # glTF uv1 (v down)
        front = nb.step(0.0, u1)
        cell = nb.attr('sign')
        col = nb.floor(nb.add(nb.sub(nb.add(cell, 0.5), nb.mul(nb.floor(nb.div(nb.add(cell, 0.5), 4.0)), 4.0)), 0.0001))
        row = nb.floor(nb.add(nb.floor(nb.div(nb.add(cell, 0.5), 4.0)), 0.0001))
        au = nb.div(nb.add(col, nb.clamp(u1, 0.004, 0.996)), 4.0)
        aw = nb.div(nb.add(row, nb.clamp(av, 0.004, 0.996)), 2.0)
        auv = nb.comb(au, nb.sub(1.0, aw), 0.0)                    # the atlas loaded top row first (flipY false)
        artc = nb.tex(art_c, auv, extension='EXTEND').outputs['Color']
        back = nb.tex(base_col, nb.uv('UVMap')).outputs['Color'] if base_col is not None else (0.55, 0.42, 0.28)
        nb.put(bs.inputs['Base Color'], F.vmix(nb, back, artc, front))
        rb = nb.sep(nb.tex(base_orm, nb.uv('UVMap')).outputs['Color'])[1] if base_orm is not None else 0.85
        ra = nb.sep(nb.tex(art_o, auv, extension='EXTEND').outputs['Color'])[1]
        nb.put(bs.inputs['Roughness'], nb.mix(rb, ra, front))
        F.finish_surface(nb, bs)
        sign.material_slots[0].material = m
        lst = [r for r in rows if r['hasSign']]
        attrs = {k: [float(r[kk]) for r in lst] for k, kk in (('sx', 'sx'), ('sz', 'sz'), ('ex', 'x'), ('ez', 'z'),
                                                              ('tStart', 'tStart'), ('tArr', 'tArr'), ('yaw', 'yaw'),
                                                              ('scale', 'scale'), ('phase', 'phase'), ('delay', 'delay'),
                                                              ('amp', 'amp'), ('sign', 'sign'))}
        attrs['hash'] = [((r['i'] * 0.754877 + 0.1234) % 1.0) for r in lst]
        ob = F.points_object('corner:signs', coll, [Vector() for _ in lst], attrs, self.campG)
        tree, b, gi, go = F.new_gn('eido.corner.signs', ['u'])
        oi = b.node('GeometryNodeObjectInfo', transform_space='ORIGINAL')
        oi.inputs['Object'].default_value = sign
        inst = b.node('GeometryNodeInstanceOnPoints')
        b.links.new(gi.outputs['Geometry'], inst.inputs['Points'])
        b.links.new(oi.outputs['Geometry'], inst.inputs['Instance'])
        real = b.node('GeometryNodeRealizeInstances')
        b.links.new(inst.outputs[0], real.inputs[0])
        u = b.s(gi.outputs['u'])
        S = self._march_state_gn(b, u)
        rest = F.gn_attr(b, 'rest', 'FLOAT_VECTOR')
        bx, by, bz = rest.xyz()
        X, Y, Z = bx, bz, -by                                      # three local (the sign's origin at the grip)
        roll = b.sin(S['phase'] * 0.5) * 0.07 * S['walking'] + (F.gn_attr(b, 'hash') - 0.5) * 0.16
        c, s = b.cos(roll), b.sin(roll)
        X, Y = X * c - Y * s, X * s + Y * c
        sc = S['scale']
        lift = S['pump'] * 0.24 * sc + b.abs(b.sin(S['phase'])) * 0.03 * S['walking']
        X, Y, Z = X + GRIP[0] * sc, Y + GRIP[1] * sc + lift, Z + GRIP[2] * sc
        bob = b.abs(b.sin(S['phase'])) * 0.028 * S['walking'] - S['pump'] * 0.02
        world = F.gn_rotate(b, b.combine(X, -Z, Y), S['yaw'], 'Z') + b.combine(S['x'], -S['z'], bob)
        sp = b.node('GeometryNodeSetPosition')
        b.links.new(real.outputs[0], sp.inputs['Geometry'])
        b.link(world, sp.inputs['Position'])
        b.links.new(sp.outputs[0], go.inputs['Geometry'])
        F.add_gn(ob, tree, kit, ('u',))
        march['signs'] = ob
        ob['no_support_check'] = True
        if root.name in bpy.data.objects:
            bpy.data.objects.remove(root, do_unlink=True)

    # ========================================================================================= THE TIMELINE
    def mark_at(self, u):
        m = mood_at(u)
        if m == 'camp':
            return {'pos': self.to_set(CAMP_AT, MARK_CAMP['x'], 0.0, MARK_CAMP['z']), 'yaw': MARK_CAMP['yaw']}
        if m == 'dark':
            return {'pos': self.to_set(ROOM_AT, MARK_LAMP['x'], 0.0, MARK_LAMP['z']), 'yaw': MARK_LAMP['yaw']}
        return {'pos': self.to_set(ROOM_AT, MARK_CORNER['x'], 0.0, MARK_CORNER['z']), 'yaw': MARK_CORNER['yaw']}

    def _bulb3(self):
        bp = self.room['bulb_pos']
        return np.array([bp.x, bp.z, -bp.y])

    def camera(self, u, st=None):
        """corner.js camera(u): one shot per bar (cuts on bar lines), gentle moves inside each; bars 26-27 follow the
        spark. {'pos', 'target', 'fov', 'shot'} set-local, Blender axes."""
        bar = int(math.floor(u / BAR))
        k = (u - bar * BAR) / BAR
        e = smooth(k)
        R = lambda x, y, z: self.to_set(ROOM_AT, x, y, z)            # noqa: E731
        Cc = lambda x, y, z: self.to_set(CAMP_AT, x, y, z)           # noqa: E731
        if bar <= 18:
            return {'pos': R(lerp(1.18, 1.00, e), lerp(1.50, 1.46, e), lerp(1.32, 1.12, e)), 'target': R(-1.20, 1.10, -1.58),
                    'fov': 44, 'shot': 18}
        if bar == 19:
            return {'pos': R(lerp(-1.18, -1.22, e), lerp(1.06, 1.03, e), lerp(-1.02, -1.08, e)),
                    'target': R(-1.50, 0.80, -1.58), 'fov': 38, 'shot': 19}
        if bar == 20:
            return {'pos': R(lerp(-0.02, -0.10, e), lerp(1.52, 1.49, e), lerp(-0.30, -0.40, e)),
                    'target': R(-1.05, 0.98, -1.66), 'fov': 38, 'shot': 20}
        if bar == 21:
            return {'pos': R(lerp(1.28, 1.16, e), lerp(1.50, 1.48, e), lerp(0.80, 0.64, e)), 'target': R(-0.80, 1.28, -1.60),
                    'fov': 40, 'shot': 21}
        if bar == 22:
            return {'pos': Cc(lerp(4.6, 4.2, e), lerp(3.2, 2.7, e), lerp(6.8, 6.3, e)), 'target': Cc(-0.4, 1.0, -6.5),
                    'fov': 46, 'shot': 22}
        if bar == 23:
            return {'pos': Cc(lerp(2.05, 2.0, e), lerp(1.20, 1.14, e), lerp(-0.55, -0.75, e)), 'target': Cc(-0.2, 1.85, -7.0),
                    'fov': 44, 'shot': 23}
        if bar == 24:
            return {'pos': Cc(lerp(0.40, 0.46, e), lerp(1.02, 1.05, e), lerp(3.35, 3.05, e)), 'target': Cc(0.65, 1.55, -2.2),
                    'fov': 42, 'shot': 24}
        if bar == 25:
            return {'pos': Cc(lerp(2.05, 1.95, e), lerp(0.62, 0.66, e), lerp(0.25, 0.10, e)), 'target': Cc(0.1, 2.2, -4.0),
                    'fov': 48, 'shot': 25}
        sp = self.spark
        if bar in (26, 27):
            kk = smooth((u - B(26)) / (2 * BAR))
            lamp_t = self._bulb3() + np.array([0.10, -0.10, 0.22])
            spp = sp['curve'].point_at(min(1.0, max(0.0, spark_progress(u, sp['t0'], sp['t1']))))
            follow = smooth(clamp01((u - sp['t0'] + 0.15) / 0.7)) * 0.85
            land = smooth(clamp01((u - sp['t1'] + 0.1) / 0.5))
            tgt = lamp_t + (spp - lamp_t) * follow
            tgt = tgt + (sp['dest'] - tgt) * (land * 0.6)
            return {'pos': R(lerp(-1.95, -1.30, kk), lerp(1.40, 1.42, kk), lerp(1.78, 1.40, kk)), 'target': R(*tgt),
                    'fov': lerp(40, 44, kk), 'shot': 26}
        yaw = MARK_LAMP['yaw']
        f = np.array([math.sin(yaw), 0.0, math.cos(yaw)])
        rgt = np.array([-math.cos(yaw), 0.0, math.sin(yaw)])
        if bar == 28:
            kk = smooth((u - B(28)) / BAR)
            p = np.array([MARK_LAMP['x'], 0.0, MARK_LAMP['z']]) - f * lerp(1.05, 0.95, kk) + rgt * 0.62
            tgt = self._bulb3() + np.array([0.0, 0.05, 0.0])
            return {'pos': R(p[0], lerp(1.46, 1.44, kk), p[2]), 'target': R(*tgt), 'fov': 36, 'shot': 28}
        kk = smooth((u - B(29)) / BAR)
        face = np.array([MARK_LAMP['x'], FLOWER_Y - 0.02, MARK_LAMP['z']]) + f * 0.1
        p = face + f * lerp(1.15, 0.98, kk) + rgt * lerp(-0.42, -0.36, kk) + np.array([0.0, 0.03, 0.0])
        return {'pos': R(*p), 'target': R(*face), 'fov': lerp(34, 31, kk), 'shot': 29}

    def make_cameras(self, frames=None, u0=B(18), fps=None, scene=None):
        """one camera per shot over the frames (u = u0 at frames[0]), keyed every frame of its shot, cut on the bar lines
        (timeline markers). Returns {shot bar: camera}."""
        from ...look import camera as LC
        sc = scene or self.kit.scene
        fps = fps or sc.render.fps / sc.render.fps_base
        f0, f1 = frames or (sc.frame_start, sc.frame_end)
        by = {}
        for f in range(f0, f1 + 1):
            u = u0 + (f - f0) / fps
            by.setdefault(self.camera(u)['shot'], []).append((f, u))
        cams = {}
        M = self.kit.root.matrix_world
        coll = self.kit.coll('cameras')
        for shot, lst in sorted(by.items(), key=lambda kv: kv[1][0][0]):
            cam = LC.make_camera(f'corner:cam_bar{shot:02d}', fov=44, collection=coll, scene=sc)
            fr = [f for f, _ in lst]
            ss = [self.camera(u) for _, u in lst]
            lens = [LC.set_fov(cam, s['fov'], 'vertical', sc) for s in ss]
            LC.key_path(cam, fr, [M @ s['pos'] for s in ss], [M @ s['target'] for s in ss], lens=lens, scene=sc)
            LC.add_shot(sc, f'corner_bar{shot:02d}', fr[0], cam)
            cams[shot] = cam
        self.cameras = cams
        return cams

    # ------------------------------------------------------------------------------------------- per frame
    def pen_pose(self, cursor, t):
        """corner.js placePen: the pen's tip on the page (a ray down onto NotebookPages at the page UV of the writing
        head, with a small wiggle) and its axis; at rest it lies across the page. (location, quaternion) room-local."""
        pages = self.room.get('nb_pages')
        if pages is None:
            return None
        me = pages.data
        bb = [Vector(c) for c in pages.bound_box]
        lo = Vector((min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb)))
        hi = Vector((max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb)))

        def page_at(uu, vv):                                       # page UV -> the surface point (world)
            lx = lerp(lo.x, hi.x, uu)
            ly = lerp(lo.y, hi.y, vv)                              # three lz = lerp(max z, min z, v): Blender y
            top = Vector((lx, ly, hi.z + 0.05))
            ok, loc, _n, _i = pages.ray_cast(top, Vector((0, 0, -1)))
            p = loc if ok else Vector((lx, ly, hi.z))
            return pages.matrix_world @ p
        _ = me
        if cursor is not None:
            wig = math.sin(t * 31) * 3 + math.sin(t * 53) * 2
            uu, vv = cursor['x'] / NB_W, 1 - (cursor['y'] - 6 + wig) / NB_H
            tip = page_at(min(0.97, uu), vv)
            tip.z += 0.0005 + max(0.0, math.sin(t * 7.1)) * 0.0015
            d = V(0.62, 0.62, 0.42).normalized()
        else:
            tip = page_at(0.80, 0.30)
            tip.z += 0.005
            d = V(0.62, 0.05, -0.78).normalized()
        loc = self.roomG.matrix_world.inverted() @ tip
        rot = Vector((0.0, 0.0, 1.0)).rotation_difference(d)       # setFromUnitVectors((0, 1, 0), dir), room-local
        return loc, rot

    def update(self, t, st=None, ctx=None, frame=None):
        """corner.js update(t, st): u = st['u'] (seconds since the bridge began), or st['state'] (a STATES look, held
        at state_u(name)); st['caption'] (with words) re-times the spark. Every value it sets is KEYED with ctx (the
        harness) or at `frame`."""
        st = st or {}
        u = self.state_u(st['state']) if st.get('state') else float(st.get('u', 0.0))
        keys = F.Keys(ctx, frame)
        area, mood = area_at(u), mood_at(u)
        U = self.U
        if st.get('caption'):
            self.sync_spark_from_caption(st['caption'], t, u)
        U['u'], U['t'] = u, t
        self._ambient(area, keys)
        if self._vis != area or ctx is not None:
            F.key_visible(keys, self.room_objects, area == 'room')
            F.key_visible(keys, self.camp_objects, area == 'camp')
            self._vis = area
        room, sp = self.room, self.spark
        if area == 'room':
            dark = mood == 'dark'
            dip = (1 - 0.25 * math.sin(math.pi * clamp01((u - sp['t0'] + 0.1) / 0.7))) if sp['t0'] - 0.1 < u < sp['t0'] + 0.6 else 1.0
            U['lamp_glow'] = dip
            for nm, val in (('lamp_spot', 0.55 * dip), ('lamp_up', 0.32 * dip), ('lamp_glow', (0.32 if dark else 0.40) * dip),
                            ('bounce', (0.22 if dark else 1.2) * dip), ('fill', 0.12 if dark else 0.85),
                            ('moon', 0.0 if dark else (5.0 if mood == 'late' else 6.5))):
                room[nm].data.energy = F.candela_w(val)
                keys.key(room[nm].data, 'energy')
            U['win'] = 0.16 if dark else 1.0
            opened = mood == 'late'
            lid = room.get('lid')
            if lid is not None:
                lid.rotation_euler.x = room['lid_open_x'] if opened else 0.0
                keys.key(lid, 'rotation_euler', index=0, interpolation='CONSTANT')
            U['screen'] = 1.0 if opened else 0.0
            room['screen_light'].data.energy = F.candela_w(0.9 if opened else 0.0)
            keys.key(room['screen_light'].data, 'energy', interpolation='CONSTANT')
            hands = room.get('hands')
            if hands and hands.get('h') is not None:
                base_min = 11 * 60 + 47 if mood == 'evening' else 13 * 60 + 8 if mood == 'late' else 15 * 60 + 12
                secs = math.fmod(u - B(18), 60)
                mins = base_min + secs / 60
                for h, ang, interp in ((hands['h'], ((mins / 60) % 12) / 12 * TAU, 'LINEAR'),
                                       (hands['m'], (mins % 60) / 60 * TAU, 'LINEAR'),
                                       (hands.get('s'), math.floor(secs) / 60 * TAU, 'CONSTANT')):
                    if h is None:
                        continue
                    h.rotation_mode = 'XYZ'
                    h.rotation_euler = (0.0, ang, 0.0)              # three rotation.z = -ang: clockwise from the front
                    keys.key(h, 'rotation_euler', index=1, interpolation=interp)
            write_k = clamp01((u - B(18) - 0.3) / (2 * BAR - 0.4))
            chars = write_k * 38 if mood == 'evening' else RIGHT_TOTAL
            cursor = self.notebook_cursor(chars) if mood == 'evening' else None
            pose = self.pen_pose(cursor, t)
            pen = room.get('pen')
            if pose is not None and pen is not None:
                pen.location = pose[0]
                pen.rotation_mode = 'QUATERNION'
                q = pose[1]
                prev = getattr(self, '_pen_q', None)
                if prev is not None and prev.dot(q) < 0:
                    q.negate()
                self._pen_q = q
                pen.rotation_quaternion = q
                keys.key(pen, 'location')
                keys.key(pen, 'rotation_quaternion')
            flying = sp['t0'] <= u < sp['t1'] + 0.15
            s = spark_progress(u, sp['t0'], sp['t1'])
            p = sp['curve'].point_at(min(1.0, s))
            pos = V(p)
            for ob in (sp['core'], sp['halo'], sp['light']):
                ob.location = pos
                keys.key(ob, 'location')
            born = clamp01((u - sp['t0']) / 0.25)
            land = clamp01((u - sp['t1']) / 0.35)
            U['spark_core'] = born * (1 - land) * (0.85 + 0.15 * math.sin(u * 37)) if flying else 0.0
            sp['light'].data.energy = F.candela_w(0.55 * born * (1 - land) if flying else 0.0)
            keys.key(sp['light'].data, 'energy')
            for ob, vis in ((sp['core'], flying), (sp['halo'], flying), (sp['trail'], u >= sp['t0'] - 0.05)):
                ob.hide_render = not vis
                keys.key(ob, 'hide_render', interpolation='CONSTANT')
            after = u - sp['t1']
            sp['bloom_light'].data.energy = F.candela_w(0.10 + 0.30 * math.exp(-after * 1.4) if after > 0 else 0.0)
            keys.key(sp['bloom_light'].data, 'energy')
        else:
            n = math.sin(t * 8.3) * 0.5 + math.sin(t * 13.7 + 1.3) * 0.3 + math.sin(t * 23.1 + 0.4) * 0.2
            if self.camp.get('fire_light') is not None:
                self.camp['fire_light'].data.energy = F.candela_w(7.0 * (0.86 + 0.14 * n))
                keys.key(self.camp['fire_light'].data, 'energy')
                for i, L in enumerate(self.camp['fills']):
                    L.data.energy = F.candela_w(FILLS[i][3])
                    keys.key(L.data, 'energy', interpolation='CONSTANT')
            U['ember'] = 0.9 + 0.12 * n
            U['bulb'] = 1.0
        for k in U.spec:
            keys.key(U.root, f'["{k}"]')
        return keys

    def animate(self, frames=None, u0=B(18), t0=None, fps=None, screens=True, out_dir=None, state=None):
        """Key update() over frames (u = u0 at frames[0], t = t0 or u0), and draw the chat and the notebook as image
        sequences over the frames they change (media.screens). state= (a STATES look) holds u at state_u(state) while
        t runs from t0 (default 0), the screens painted once as they stand there. Returns the keys left."""
        sc = self.kit.scene
        fps = fps or sc.render.fps / sc.render.fps_base
        f0, f1 = frames or (sc.frame_start, sc.frame_end)
        rate = 1.0
        if state:
            u0, rate, t0 = self.state_u(state), 0.0, (0.0 if t0 is None else t0)
        t0 = u0 if t0 is None else t0
        keys = None
        self._vis = None
        for f in range(f0, f1 + 1):
            u = u0 + rate * (f - f0) / fps
            k = self.update(t0 + (f - f0) / fps, {'u': u}, frame=f)
            keys = k if keys is None else keys.merge(k)
        n = keys.finish() if keys is not None else 0
        if screens and state:
            self.paint_screens(u0)
        elif screens:
            self.bake_screens((f0, f1), u0, fps, out_dir)
        return n

    def bake_screens(self, frames, u0=B(18), fps=None, out_dir=None):
        """the chat (12 fps while the laptop is open) and the notebook (as the pen writes) as media.screens image
        sequences, wired into the laptop's and the pages' own materials."""
        from ...media import screens as SCR
        sc = self.kit.scene
        fps = fps or sc.render.fps / sc.render.fps_base
        f0, f1 = frames
        tb0 = (f0 - sc.frame_start) / fps

        def u_of(t):
            return u0 + (t - tb0)

        def fr(ua, ub):
            a = f0 + int(math.floor((ua - u0) * fps))
            b = f0 + int(math.ceil((ub - u0) * fps))
            return max(f0, a), min(f1, b)
        room = self.room
        made = {}
        a, b = fr(B(20), B(22))
        if b > a:
            def chat(c, t, w, h):
                u = u_of(t)
                img = F.canvas_pil(w, h, lambda g, ww, hh: self.draw_chat(g, 4 + (u - B(20)) / (2 * BAR) * 6), ss=2)
                c.image.paste(img)
            s = SCR.make_screen(px=1024, width=1.0, height=0.625, draw=chat, frames=(a, b), fps=12, standalone=False,
                                name='corner_chat', out_dir=(os.path.join(out_dir, 'chat') if out_dir else None))
            node = room['chat_node']
            node.image = s.image
            SCR.configure_user(node.image_user, s.image)
            made['chat'] = s
        a, b = fr(B(18), B(20) + 0.05)
        if b > a:
            def page(c, t, w, h):
                u = u_of(t)
                write_k = clamp01((u - B(18) - 0.3) / (2 * BAR - 0.4))
                chars = write_k * 38 if u < B(20) else RIGHT_TOTAL
                img = F.canvas_pil(w, h, lambda g, ww, hh: self.draw_notebook(g, chars), ss=2)
                c.image.paste(img)
            s = SCR.make_screen(px=NB_W, width=1.0, height=NB_H / NB_W, draw=page, frames=(a, b), fps=15,
                                standalone=False, name='corner_notebook',
                                out_dir=(os.path.join(out_dir, 'notebook') if out_dir else None))
            node = room['nb_node']
            node.image = s.image
            SCR.configure_user(node.image_user, s.image)
            made['notebook'] = s
        self.screens = made
        return made

    def dispose(self):
        """corner.js dispose() did nothing; here the set's objects, collections and node groups go."""
        for f in self.camp.get('grass', []):
            try:
                f.remove()
            except (ReferenceError, AttributeError):
                pass
        for o in list(self.camp.get('extra_objects', [])):
            try:
                bpy.data.objects.remove(o, do_unlink=True)
            except ReferenceError:
                pass
        F.dispose_kit(self.kit, ('corner:',), ('eido.corner.',))


def build(ctx=None, **kw):
    """corner.js build(ctx): the room and the camp, the march and the spark. Options (Blender): location=, camp=,
    march=, grass=, trees=, particles=, tree_level= ('LOD0' for films; the WebGPU camp grew 'LOD1'), shadows=.
    Hold one of its looks with update(t, {'state': name}) or animate(frames, state=name) (STATES); the camp's
    grass, woods and fire move with the set's root."""
    return Corner(ctx, **kw)
