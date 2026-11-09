"""ASTEROID MOON: the bake-once asset pipeline, its thin runtime loader, and the SHATTERED MOON.

Ported from eidoverse/asteroid_moon.js, newest in Eanpa Engine engine/asteroid_moon.js + fragment_motion.js.

  bake_asteroid_moon(height, albedo, out_dir)   ONCE, a tool: an irregular chunk (an icosphere carried onto an analytic
        'potato', radius a pure function of direction) displaced by a tileable height into real crater geometry; a
        tessellated high poly (the potato re-evaluated at every sub-vertex) baked down to the runtime mesh's 1:1 UV
        as a light-neutral shaded albedo (cavity + slope) and an OBJECT-SPACE normal atlas. Writes
        asteroid_moon_mesh.f32 + asteroid_moon_baked.png + asteroid_moon_normal.png.
  make_asteroid_moon(mesh_path, baked, normal)  the runtime: loads the three artifacts into a mesh with the celestial
        lambert material (unlit, its own sun term), unit-ish radius: scale and orbit are the scene's job.
  make_shattered_moon(scene, glb, spread)       the shieldworld's companion: the authored GLB cluster of fragments,
        every material rewired to the celestial body shading (Eanpa: a Lommel-Seeliger/Lambert blend with a geometric
        horizon guard), Eanpa's bounded fragment drift (no fragment ever touches another), the volumetric accretion
        dust (marched in the sky shader, bake/celestial.py dust_glsl, behind the fragments as WebGPU drew it) and the
        granular debris river (7000 lambert-lit grains, Geometry Nodes, analytic in time).
Geometry and maths run in three.js space (Y up) as the JS does; Blender objects get (x, -z, y).
"""
import math
import os

import numpy as np

from . import palette as P

MOON_KEYS = 'eido_moon_keys'
SPECK_N = 7000


def _h(i, k):
    v = math.sin(i * 127.1 + k * 311.7) * 43758.5453
    return v - math.floor(v)


def _norm(v):
    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1.0
    return (v[0] / n, v[1] / n, v[2] / n)


def _quat_axis_angle(axis, ang):
    s = math.sin(ang / 2)
    return (math.cos(ang / 2), axis[0] * s, axis[1] * s, axis[2] * s)        # (w, x, y, z)


def _quat_mul(a, b):
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (aw * bw - ax * bx - ay * by - az * bz, aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx, aw * bz + ax * by - ay * bx + az * bw)


# ------------------------------------------------------------------------------------- fragment motion ---

class FragmentMotion:
    """Eanpa fragment_motion.js: deterministic fragment drift in the cluster's frame. Every rotating piece stays inside
    a pivot-centred sphere and every drift inside a second bounded envelope; separating the envelopes guarantees
    clearance at all times, between sampled frames too."""

    def __init__(self, positions, radii, orientations=None, spread=1.75):
        n = len(positions)
        if not n:
            raise ValueError('Fragment motion requires at least one mesh')
        unit = lambda i, k: _norm((_h(i, k) - 0.5, _h(i, k + 1) - 0.5, _h(i, k + 2) - 0.5))
        self.radii = [float(r) for r in radii]
        self.hero_index = int(np.argmax(self.radii))
        hero_r = self.radii[self.hero_index]
        base = [np.array([p[0] * spread, p[1], p[2]], np.float64) for p in positions]
        self.orientations = list(orientations or [(1.0, 0.0, 0.0, 0.0)] * n)
        self.amplitudes = [(0.035 if i == self.hero_index else 0.10) * r + hero_r * 0.012
                           for i, r in enumerate(self.radii)]
        clearance = hero_r * 0.035
        env = [r + a for r, a in zip(self.radii, self.amplitudes)]
        mass = [max(1e-8, r ** 3) for r in self.radii]
        total = sum(mass)
        center = sum(b * m for b, m in zip(base, mass)) / total
        it = 0
        for it in range(256):
            largest = 0.0
            for i in range(n):
                for j in range(i + 1, n):
                    d = base[j] - base[i]
                    dist = float(np.linalg.norm(d))
                    overlap = env[i] + env[j] + clearance - dist
                    if overlap <= 1e-9:
                        continue
                    largest = max(largest, overlap)
                    d = d / dist if dist > 1e-10 else np.array(unit(i, j + 100))
                    move = overlap + 1e-8
                    share = mass[j] / (mass[i] + mass[j])
                    base[i] = base[i] - d * move * share
                    base[j] = base[j] + d * move * (1 - share)
            if largest < 1e-8:
                break
        adjusted = sum(b * m for b, m in zip(base, mass)) / total - center
        base = [b - adjusted for b in base]
        min_clear = min((float(np.linalg.norm(base[i] - base[j])) - env[i] - env[j]
                         for i in range(n) for j in range(i + 1, n)), default=math.inf)
        if min_clear < clearance - 1e-6:
            raise RuntimeError('Could not separate fragment motion envelopes')
        self.base_positions = [tuple(b) for b in base]
        self.motion = []
        for i in range(n):
            u = unit(i, 10)
            v = _norm(tuple(np.cross(u, unit(i, 20))))
            self.motion.append(dict(u=u, v=v, axis=unit(i, 30), phase=_h(i, 40) * math.pi * 2,
                                    frequency=math.pi * 2 / (100 + _h(i, 41) * 180),
                                    rate=0.009 if i == self.hero_index else 0.014 + _h(i, 42) * 0.018))
        self.stats = dict(fragments=n, minimumEnvelopeClearance=min_clear, clearance=clearance, iterations=it)

    def update(self, t):
        """Positions and (w, x, y, z) quaternions of every piece at time t (three.js, the cluster's frame)."""
        pos, quat = [], []
        for i, m in enumerate(self.motion):
            ph = m['phase'] + t * m['frequency']
            a = self.amplitudes[i]
            b = self.base_positions[i]
            c, s = math.cos(ph) * a, math.sin(ph) * a * 0.6
            pos.append(tuple(b[k] + m['u'][k] * c + m['v'][k] * s for k in range(3)))
            quat.append(_quat_mul(self.orientations[i], _quat_axis_angle(m['axis'], t * m['rate'])))
        return pos, quat


def make_fragment_motion(positions, radii, orientations=None, spread=1.75):
    return FragmentMotion(positions, radii, orientations, spread)


# ----------------------------------------------------------------------------------- the shattered moon ---

def _three_matrix(pos, euler_xyz, scale):
    """three's Object3D world matrix (T R S, Euler order XYZ) as a numpy 4x4."""
    x, y, z = euler_xyz
    cx, sx, cy, sy, cz, sz = math.cos(x), math.sin(x), math.cos(y), math.sin(y), math.cos(z), math.sin(z)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    R = Rx @ Ry @ Rz
    M = np.eye(4)
    M[:3, :3] = R * scale
    M[:3, 3] = pos
    return M, R


_C = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], np.float64)       # three -> Blender: (x, y, z) -> (x, -z, y)


class ShatteredMoon:
    def __init__(self, scene, glb_path, spread=1.75, scale=1400.0, collection=None):
        import bpy
        self.scene = scene
        self.spread = float(spread)
        self.scale = float(scale)
        coll = collection or bpy.data.collections.new('eido_shattered_moon')
        if coll.name not in scene.collection.children:
            scene.collection.children.link(coll)
        self.collection = coll
        before = set(bpy.data.objects)
        from .ringworld import _find_layer_collection
        lc = _find_layer_collection(bpy.context.view_layer.layer_collection, coll)
        prev = bpy.context.view_layer.active_layer_collection
        if lc:
            bpy.context.view_layer.active_layer_collection = lc
        bpy.ops.import_scene.gltf(filepath=glb_path)
        if lc:
            bpy.context.view_layer.active_layer_collection = prev
        new = [ob for ob in bpy.data.objects if ob not in before]
        pieces = sorted([ob for ob in new if ob.type == 'MESH'], key=lambda o: o.name)
        roots = [ob for ob in new if ob.parent is None]
        group = bpy.data.objects.new('eido_shattered_moon', None)
        coll.objects.link(group)
        group.scale = (self.scale,) * 3          # a placed cluster starts at its scale; the shieldworld keys its own
        for r in roots:
            r.parent = group
            r.matrix_parent_inverse.identity()
        self.group, self.pieces = group, pieces
        # placed: the scene (not the shieldworld's orbit) positions, scales and animates the group, as the JS
        # makeShatteredMoon leaves it to the scene; update(t) then reads the group's world matrix and never keys it
        self.placed = False
        self.source_images = {img for ob in pieces for m in ob.data.materials if m and m.node_tree
                              for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image for img in [n.image]}
        # the pieces in the cluster's three.js frame
        pos3, radii = [], []
        for ob in pieces:
            l = ob.location
            pos3.append(P.blender_to_three((l.x, l.y, l.z)))
            co = np.empty(len(ob.data.vertices) * 3, np.float32)
            ob.data.vertices.foreach_get('co', co)
            co = co.reshape(-1, 3) * np.array(ob.scale)
            radii.append(float(np.sqrt((co ** 2).sum(1)).max()))
        self.motion = FragmentMotion(pos3, radii, spread=self.spread)
        fm = self.motion
        hero = fm.hero_index
        hero_r = fm.radii[hero]
        base = [np.array(b) for b in fm.base_positions]
        hb = base[hero]
        self.arc_x = max(max(abs(b[0] - hb[0]) for b in base), hero_r)
        self.rc = max(hero_r * 2.3, self.arc_x * 1.2)
        self.cent = tuple(sum(base) / len(base) - hb)
        big = [i for i, _ in sorted(enumerate(fm.radii), key=lambda e: -e[1])[:7]]
        pairs = sorted(((big[a], big[b], float(np.linalg.norm(base[big[a]] - base[big[b]])))
                        for a in range(len(big)) for b in range(a + 1, len(big))), key=lambda e: e[2])
        self.plume_pairs = [(a, b) for a, b, _ in pairs[:3]]
        self.big = big
        self.streams = [i for i, _ in sorted(((i, r) for i, r in enumerate(fm.radii) if i != hero),
                                             key=lambda e: -e[1])[:6]]
        self.hero_r = hero_r
        # materials, specks, keys
        from . import moon_materials as MM
        self.keys_tree, self.key_handles = MM.moon_keys_group()
        for ob in pieces:
            MM.fragment_material(ob)
            ob.visible_shadow = False
            ob['eido_sky_element'] = 'shieldworld'
            ob['eido_dry'] = 1                     # a sky body: the weather's wetness never wraps it (JS noWet)
        self.specks = MM.speck_system(self, scene)
        self.specks['eido_sky_element'] = 'shieldworld'
        # the JS uniforms {sunDir, sunCol, gain} (+ the fade the shieldworld adds), sun_dir in BLENDER world space:
        # three's default (0, 0.4, -0.9) normalised. A placed cluster's update(t) reads them; the shieldworld writes them
        self.uniforms = dict(sun_dir=P.three_to_blender(_norm((0.0, 0.4, -0.9))), sun_col=(1.0, 1.0, 1.0), gain=2.0,
                             fade=1.0)

    # ---- what the sky shader compiles for the dust ----
    def dust_glsl(self):
        from .bake.celestial import dust_glsl
        r = list(self.motion.radii) + [self.hero_r * 0.2] * max(0, 16 - len(self.motion.radii))
        return dust_glsl(self.rc, self.cent, self.arc_x, self.hero_r, r[:16], self.big, self.streams)

    def dispose_textures(self):
        import bpy
        for img in list(self.source_images):
            if img.name in bpy.data.images and img.users == 0:
                bpy.data.images.remove(img)
        self.source_images = set()

    # ---- per frame ----
    def update(self, t, hours=None, sky_sun_dir=None, night_k=None, sun_col=None):
        """One frame of the cluster: the fragments' drift and tumble, the dust uniforms, the shading values.

        The SHIELDWORLD (hours given; the Eanpa shieldworld frame block's moon half): the moon's orbit on the sky's
        clock (rises 22.3 h, transits in 6.2 h, outside the 21 km shield at every point), its tumble, the night-only
        elevation-gated visibility, lit by sky_sun_dir (three.js) in the giant's amber sun_col.
        A PLACED cluster (hours None: the JS update(t) of a custom celestial cluster): the scene places, scales and
        animates the group; the dust follows the fragments through the group's current world matrix. It is lit by
        sky_sun_dir when a sky passes its true sun (Sky.attach_cluster), else by self.uniforms (sun_dir in Blender world
        space, sun_col, gain, fade), as the JS scene copies its sun into cluster.uniforms.sunDir.
        Returns the frame's values for key()."""
        if hours is None:
            mw = np.array(self.group.matrix_world)
            M3 = np.eye(4)
            M3[:3, :3] = _C.T @ mw[:3, :3] @ _C
            M3[:3, 3] = _C.T @ mw[:3, 3]
            scale = float(np.cbrt(abs(np.linalg.det(M3[:3, :3])))) or 1.0
            R3 = M3[:3, :3] / scale
            sun3 = _norm(sky_sun_dir if sky_sun_dir is not None else P.blender_to_three(self.uniforms['sun_dir']))
            col = tuple(sun_col if sun_col is not None else self.uniforms['sun_col'])
            gain = float(self.uniforms['gain'])
            visibility = float(self.uniforms.get('fade', 1.0))
            p3 = euler = None
            moon_up = float(M3[1, 3])
        else:
            th = (((hours - 22.3) + 24) % 24) / 6.2 * math.pi
            p3 = (math.cos(th) * 34000.0, math.sin(th) * 22000.0 + 2000.0, -12000.0)
            euler = (t * 0.01, t * 0.017, 0.0)
            M3, R3 = _three_matrix(p3, euler, self.scale)
            scale = self.scale
            elev = p3[1] / max(math.sqrt(sum(c * c for c in p3)), 1.0)
            ext = max(0.0, min(1.0, (elev - 0.36) / 0.14))
            ext_e = ext * ext * (3 - 2 * ext)
            night_e = night_k * night_k * (3 - 2 * night_k)
            visibility = night_e * ext_e
            gain = 2.0 * ext_e
            sun3 = _norm(sky_sun_dir)
            col = tuple(sun_col if sun_col is not None else (1.0, 0.62, 0.35))
            moon_up = p3[1]
        pos, quat = self.motion.update(t)
        hero = self.motion.hero_index
        hp = np.array(pos[hero])
        dust_origin = (M3 @ np.append(hp, 1.0))[:3]
        to_local = R3.T / scale                          # world -> dust-local (columns go to the shader)
        sun_l = _norm(tuple(R3.T @ np.array(sun3)))
        plumes = []
        for a, b in self.plume_pairs:
            m = (np.array(pos[a]) + np.array(pos[b])) * 0.5 - hp
            plumes.append((m[0], m[1], m[2], 0.0))
        pieces_l = [tuple(np.array(p) - hp) + (0.0,) for p in pos]
        pieces_l += [(0.0, 999.0, 0.0, 0.0)] * (16 - len(pieces_l))
        U = dict(dustOrigin=tuple(dust_origin), dustM0=tuple(to_local[:, 0]), dustM1=tuple(to_local[:, 1]),
                 dustM2=tuple(to_local[:, 2]), dustSunL=sun_l, dustT=float(t), dustSunCol=col,
                 dustGain=gain, dustFade=visibility, plumes=plumes, pieces=pieces_l[:16])
        self.uniforms = dict(sun_dir=P.three_to_blender(sun3), sun_col=col, gain=gain, fade=visibility)
        return dict(position3=p3, euler3=euler, rot3=R3, pieces=pos, quats=quat, visibility=visibility, gain=gain,
                    sun_col=col, sun_dir3=tuple(sun3), U=U, moon_up=moon_up, placed=p3 is None)

    def key(self, frame, v):
        """Key one frame: the group's orbit and tumble (the shieldworld only: a placed cluster's group is the scene's),
        every fragment, and the shading values."""
        from mathutils import Matrix, Quaternion, Vector
        from .nodes import key_values
        g = self.group
        if v.get('position3') is not None:
            RB = _C @ v['rot3'] @ _C.T
            g.rotation_mode = 'QUATERNION'
            g.location = Vector(P.three_to_blender(v['position3']))
            g.rotation_quaternion = Matrix([list(r) for r in RB]).to_quaternion()
            g.scale = (self.scale,) * 3
            for path in ('location', 'rotation_quaternion', 'scale'):
                g.keyframe_insert(path, frame=frame)
        for ob, p, q in zip(self.pieces, v['pieces'], v['quats']):
            ob.rotation_mode = 'QUATERNION'
            ob.location = Vector(P.three_to_blender(p))
            # a three.js rotation (w, x, y, z) about axis a is the Blender rotation about (ax, -az, ay)
            ob.rotation_quaternion = Quaternion((q[0], q[1], -q[3], q[2]))
            ob.keyframe_insert('location', frame=frame)
            ob.keyframe_insert('rotation_quaternion', frame=frame)
        key_values(self.key_handles, frame, dict(
            sun_dir=P.three_to_blender(v['sun_dir3']), sun_col=v['sun_col'], gain=v['gain'], fade=v['visibility']))

    def finish_keys(self):
        from .nodes import set_interpolation
        set_interpolation(self.keys_tree, 'LINEAR')
        for ob in ([] if self.placed else [self.group]) + list(self.pieces):
            set_interpolation(ob, 'LINEAR')

    def clear_keys(self):
        """Drop the keys a previous bake wrote (the scene's own animation of a placed group stays)."""
        for idd in [self.keys_tree] + ([] if self.placed else [self.group]) + list(self.pieces):
            if idd.animation_data:
                idd.animation_data_clear()
        return self

    def bake(self, frame_start=None, frame_end=None, sun_dir=None):
        """A placed cluster with no sky: run update(t) per frame of the scene (the scene on that frame, so an
        animated group is followed) and key it. sun_dir (Blender world space) overrides uniforms['sun_dir']. The
        accretion dust is marched in a sky's shader, so it appears with Sky.attach_cluster (a cluster without a sky
        shows its fragments and debris river). Returns the per-frame values."""
        if getattr(self, 'world_owned', False):
            raise ValueError('ShatteredMoon.bake: this is the shieldworld\'s own moon; its sky bakes it')
        sc = self.scene
        fs = sc.frame_start if frame_start is None else int(frame_start)
        fe = sc.frame_end if frame_end is None else int(frame_end)
        fps = sc.render.fps / sc.render.fps_base
        if sun_dir is not None:
            self.uniforms['sun_dir'] = tuple(sun_dir)
        self.placed = True
        self.clear_keys()
        before = (sc.frame_current, sc.frame_subframe)
        out = []
        try:
            for f in range(fs, fe + 1):
                sc.frame_set(f)
                v = self.update((f - sc.frame_start) / fps)
                self.key(f, v)
                out.append(v)
        finally:
            sc.frame_set(before[0], subframe=before[1])
        self.finish_keys()
        return out


def make_shattered_moon(scene, glb_path, spread=1.75, scale=1400.0, collection=None):
    """makeShatteredMoon({glbBytes, spread}): the cluster, its materials, motion, dust and debris river.

    Inside make_sky(world='shieldworld') the world owns it (its orbit, fade and light). For a CUSTOM celestial cluster
    the scene places and scales cluster.group (scale= is its starting scale) and either hands it to a sky
    (sky.attach_cluster(cluster): lit by the sky's true sun, its dust marched in the sky's shader, the sky's clouds
    over it) or drives it alone (cluster.bake(sun_dir=...)). One cluster per scene: its materials and keys are
    shared by name."""
    return ShatteredMoon(scene, glb_path, spread, scale, collection)


# ---------------------------------------------------------------------------- the bake-once pipeline ---

_ICO_T = (1 + math.sqrt(5)) / 2
_ICO_V = np.array([[-1, _ICO_T, 0], [1, _ICO_T, 0], [-1, -_ICO_T, 0], [1, -_ICO_T, 0], [0, -1, _ICO_T],
                   [0, 1, _ICO_T], [0, -1, -_ICO_T], [0, 1, -_ICO_T], [_ICO_T, 0, -1], [_ICO_T, 0, 1],
                   [-_ICO_T, 0, -1], [-_ICO_T, 0, 1]], np.float64)
_ICO_F = [0, 11, 5, 0, 5, 1, 0, 1, 7, 0, 7, 10, 0, 10, 11, 1, 5, 9, 5, 11, 4, 11, 10, 2, 10, 7, 6, 7, 1, 8,
          3, 9, 4, 3, 4, 2, 3, 2, 6, 3, 6, 8, 3, 8, 9, 4, 9, 5, 2, 4, 11, 6, 2, 10, 8, 6, 7, 9, 8, 1]


def icosahedron_nonindexed(detail):
    """three's IcosahedronGeometry(1, detail).toNonIndexed() positions (PolyhedronGeometry's subdivision)."""
    out = []
    cols = detail + 1
    for f in range(20):
        a, b, c = (_ICO_V[_ICO_F[f * 3 + k]] for k in range(3))
        v = []
        for i in range(cols + 1):
            aj = a + (c - a) * (i / cols)
            bj = b + (c - b) * (i / cols)
            rows = cols - i
            v.append([aj if (j == 0 and i == cols) else aj + (bj - aj) * (j / rows if rows else 0)
                      for j in range(rows + 1)])
        for i in range(cols):
            for j in range(2 * (cols - i) - 1):
                k = j // 2
                if j % 2 == 0:
                    out += [v[i][k + 1], v[i + 1][k], v[i][k]]
                else:
                    out += [v[i][k + 1], v[i + 1][k + 1], v[i + 1][k]]
    p = np.array(out, np.float64)
    return p / np.linalg.norm(p, axis=1, keepdims=True)


def _vn3(x, y, z, seed):
    def h3(a, b, c):
        v = np.sin(a * 127.1 + b * 311.7 + c * 74.7 + seed * 91.3) * 43758.5453
        return v - np.floor(v)
    xi, yi, zi = np.floor(x), np.floor(y), np.floor(z)
    xf, yf, zf = x - xi, y - yi, z - zi
    s = lambda t: t * t * (3 - 2 * t)
    sx, sy, sz = s(xf), s(yf), s(zf)
    acc = 0.0
    for dz in (0, 1):
        for dy in (0, 1):
            for dx in (0, 1):
                acc = acc + h3(xi + dx, yi + dy, zi + dz) * ((sx if dx else 1 - sx) * (sy if dy else 1 - sy)
                                                          * (sz if dz else 1 - sz))
    return acc


def potato(d, seed=7, squash=(1.15, 0.82, 1.0)):
    """The analytic potato: radius as a pure function of direction (d: (n, 3) unit)."""
    r = (1 + (_vn3(d[:, 0] * 1.4 + 9, d[:, 1] * 1.4, d[:, 2] * 1.4, seed) - 0.5) * 0.52
         + (_vn3(d[:, 0] * 3.1, d[:, 1] * 3.1 + 4, d[:, 2] * 3.1, seed) - 0.5) * 0.18)
    return d * r[:, None] * np.array(squash)


def _uv_of(d):
    return np.stack([np.arctan2(d[:, 2], d[:, 0]) / (math.pi * 2) + 0.5,
                     np.arcsin(np.clip(d[:, 1], -1, 1)) / math.pi + 0.5], 1)


def _seam_fix(uv):
    t = uv.reshape(-1, 3, 2)
    u = t[:, :, 0]
    wide = (u.max(1) - u.min(1)) > 0.5
    fix = wide[:, None] & (u < 0.5)
    u[fix] += 1.0
    return t.reshape(-1, 2)


def _smooth_normals(p):
    """computeVertexNormals on a non-indexed mesh (the face normal per corner), then weld by position and average."""
    t = p.reshape(-1, 3, 3)
    fn = np.cross(t[:, 2] - t[:, 1], t[:, 0] - t[:, 1])
    fn /= np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-20)
    n = np.repeat(fn, 3, axis=0)
    key = np.round(p * 1e5).astype(np.int64)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.ravel()
    acc = np.zeros((inv.max() + 1, 3))
    np.add.at(acc, inv, n)
    acc /= np.maximum(np.linalg.norm(acc, axis=1, keepdims=True), 1e-20)
    return acc[inv]


def _bilinear_wrap(img, u, v):
    H, W = img.shape
    x = np.mod(u, 1.0) * W - 0.5
    y = np.mod(v, 1.0) * H - 0.5
    x0, y0 = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    tx, ty = x - x0, y - y0
    g = lambda a, b: img[np.mod(b, H), np.mod(a, W)]
    return (g(x0, y0) * (1 - tx) * (1 - ty) + g(x0 + 1, y0) * tx * (1 - ty) + g(x0, y0 + 1) * (1 - tx) * ty
            + g(x0 + 1, y0 + 1) * tx * ty)


def _displace(p, n, height, tile, amp):
    w = np.abs(n) ** 4
    ws = w.sum(1)
    h = (_bilinear_wrap(height, p[:, 1] * tile, p[:, 2] * tile) * w[:, 0]
         + _bilinear_wrap(height, p[:, 0] * tile, p[:, 2] * tile) * w[:, 1]
         + _bilinear_wrap(height, p[:, 0] * tile, p[:, 1] * tile) * w[:, 2]) / ws
    return p + n * ((h - 0.5) * amp * 2)[:, None]


BAKE_FRAG = '''
vec3 triTex(sampler2D tex, vec3 p, vec3 n, float scale) {
    vec3 w = pow(abs(n), vec3(4.0));
    float ws = w.x + w.y + w.z;
    return (texture(tex, p.yz * scale).rgb * w.x + texture(tex, p.xz * scale).rgb * w.y
            + texture(tex, p.xy * scale).rgb * w.z) / ws;
}
void main() {
    if (uMode == 1) { fragColor = vec4(vHnrm * 0.5 + 0.5, 1.0); return; }
    vec3 op = vOpos;
    vec3 n = normalize(op);
    float hC = triTex(heightTex, op, n, uTile).r;
    vec3 t1 = normalize(cross(n, vec3(0.2, 1.0, 0.1)));
    vec3 t2 = normalize(cross(n, t1));
    float e = 0.02;
    float h1 = triTex(heightTex, op + t1 * e, n, uTile).r;
    float h2 = triTex(heightTex, op - t1 * e, n, uTile).r;
    float h3 = triTex(heightTex, op + t2 * e, n, uTile).r;
    float h4 = triTex(heightTex, op - t2 * e, n, uTile).r;
    float hAvg = (h1 + h2 + h3 + h4) * 0.25;
    float cavity = clamp(1.0 - (hAvg - hC) * 5.5, 0.5, 1.12);
    float slope = abs(h1 - h2) + abs(h3 - h4);
    float slopeK = clamp(1.0 - slope * 1.6, 0.72, 1.0);
    fragColor = vec4(triTex(albedoTex, op, n, uTile) * cavity * slopeK, 1.0);
}
'''


def bake_asteroid_moon(height_path, albedo_path, out_dir=None, opts=None):
    """bakeAsteroidMoon: the bake-once tool. Returns dict(positions, normals, uvs, albedo, normal_atlas, counts).

    opts (the JS names): seed (7), tile (2.2), reliefAmp (0.055), squash ((1.15, 0.82, 1.0)), bakeSize (1024),
    hiSub (4: hiSub^2 sub-triangles per base face), detail (24: 20 (d+1)^2 runtime faces)."""
    import bpy
    import gpu
    from gpu_extras.batch import batch_for_shader
    from .bake.baker import load_image_rgba
    o = dict(opts or {})
    seed, tile, amp = o.get('seed', 7), float(o.get('tile', 2.2)), float(o.get('reliefAmp', 0.055))
    squash = tuple(o.get('squash', (1.15, 0.82, 1.0)))
    W = int(o.get('bakeSize', 1024))
    hsub = int(o.get('hiSub', 4))
    height_rgba = load_image_rgba(height_path, srgb=False)
    height = height_rgba[..., 0].astype(np.float64)
    # ---- the RUNTIME mesh: icosphere base, analytic potato, displaced ----
    base_dirs = icosahedron_nonindexed(int(o.get('detail', 24)))
    pos = potato(base_dirs, seed, squash)
    nrm = _smooth_normals(pos)
    uv = _seam_fix(_uv_of(base_dirs))
    pos = _displace(pos, nrm, height, tile, amp)
    nrm = _smooth_normals(pos)
    # ---- the HIGH poly: barycentric tessellation of each base face, the potato re-evaluated per sub-vertex ----
    faces = base_dirs.reshape(-1, 3, 3)
    bary = []
    s = 1.0 / hsub
    for i in range(hsub):
        for j in range(hsub - i):
            a0, b0 = i * s, j * s
            bary += [(a0, b0), (a0 + s, b0), (a0, b0 + s)]
            if j < hsub - i - 1:
                bary += [(a0 + s, b0), (a0 + s, b0 + s), (a0, b0 + s)]
    bary = np.array(bary)
    a_, b_ = bary[:, 0], bary[:, 1]
    c_ = 1 - a_ - b_
    d = (faces[:, None, 0, :] * c_[None, :, None] + faces[:, None, 1, :] * a_[None, :, None]
         + faces[:, None, 2, :] * b_[None, :, None]).reshape(-1, 3)
    d /= np.linalg.norm(d, axis=1, keepdims=True)
    hi_opos = potato(d, seed, squash)
    hi_uv = _seam_fix(_uv_of(d))
    hi_n = _smooth_normals(hi_opos)
    hi_pos = _displace(hi_opos, hi_n, height, tile, amp)            # REAL crater geometry
    hi_n = _smooth_normals(hi_pos)
    # ---- bake twins in the high poly's UV space (GPU raster): shaded albedo, object-space normals ----
    try:
        gpu.init()
    except Exception:
        pass
    albedo_rgba = load_image_rgba(albedo_path, srgb=True)

    def tex(arr):
        h, w = arr.shape[:2]
        t = gpu.types.GPUTexture((w, h), format='RGBA16F',
                                 data=gpu.types.Buffer('FLOAT', w * h * 4, np.ascontiguousarray(arr, np.float32).ravel()))
        t.filter_mode(True)
        t.extend_mode('REPEAT')
        return t

    t_h, t_a = tex(height_rgba), tex(albedo_rgba)
    info = gpu.types.GPUShaderCreateInfo()
    iface = gpu.types.GPUStageInterfaceInfo('moon_bake_iface')
    iface.smooth('VEC3', 'vOpos')
    iface.smooth('VEC3', 'vHnrm')
    info.vertex_in(0, 'VEC2', 'pos')
    info.vertex_in(1, 'VEC3', 'opos')
    info.vertex_in(2, 'VEC3', 'hnrm')
    info.vertex_out(iface)
    info.push_constant('FLOAT', 'uShift')
    info.push_constant('FLOAT', 'uTile')
    info.push_constant('INT', 'uMode')
    info.sampler(0, 'FLOAT_2D', 'heightTex')
    info.sampler(1, 'FLOAT_2D', 'albedoTex')
    info.fragment_out(0, 'VEC4', 'fragColor')
    info.vertex_source('void main() { vOpos = opos; vHnrm = hnrm; '
                       'gl_Position = vec4((pos.x + uShift) * 2.0 - 1.0, pos.y * 2.0 - 1.0, 0.0, 1.0); }')
    info.fragment_source(BAKE_FRAG)
    sh = gpu.shader.create_from_info(info)
    batch = batch_for_shader(sh, 'TRIS', dict(pos=hi_uv.astype(np.float32), opos=hi_opos.astype(np.float32),
                                              hnrm=hi_n.astype(np.float32)))
    atlases = []
    for mode, clear in ((0, (0.40, 0.36, 0.32, 1.0)), (1, (0.5, 0.5, 0.5, 1.0))):
        off = gpu.types.GPUOffScreen(W, W, format='RGBA32F')
        with off.bind():
            fb = gpu.state.active_framebuffer_get()
            fb.clear(color=clear)
            sh.bind()
            sh.uniform_float('uTile', tile)
            sh.uniform_int('uMode', mode)
            sh.uniform_sampler('heightTex', t_h)
            sh.uniform_sampler('albedoTex', t_a)
            for shift in (0.0, -1.0):                   # seam faces live at u in [1, 1.5]: a wrapped copy
                sh.uniform_float('uShift', shift)
                batch.draw(sh)
            buf = fb.read_color(0, 0, W, W, 4, 0, 'FLOAT')
            atlases.append(np.asarray(buf, np.float32).reshape(W, W, 4).copy())
        off.free()
    albedo_atlas, normal_atlas = atlases
    out = dict(positions=pos.astype(np.float32), normals=nrm.astype(np.float32), uvs=uv.astype(np.float32),
               albedo=albedo_atlas, normal_atlas=normal_atlas, runtime_vertices=len(pos), bake_triangles=len(hi_pos) // 3)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        count = len(pos)
        with open(os.path.join(out_dir, 'asteroid_moon_mesh.f32'), 'wb') as f:
            f.write(np.array([count], np.uint32).tobytes())
            f.write(out['positions'].tobytes())
            f.write(out['normals'].tobytes())
            f.write(out['uvs'].tobytes())
        _save_png(os.path.join(out_dir, 'asteroid_moon_baked.png'), albedo_atlas, srgb=True)
        _save_png(os.path.join(out_dir, 'asteroid_moon_normal.png'), normal_atlas, srgb=False)
        print('[asteroid_moon] baked artifacts -> %s: asteroid_moon_mesh.f32 + asteroid_moon_baked.png + '
              'asteroid_moon_normal.png (%d runtime verts, %d bake tris)' % (out_dir, count, len(hi_pos) // 3))
    return out


def _save_png(path, arr, srgb):
    """A float atlas (rows bottom-up, Blender order) as an 8-bit PNG; srgb encodes linear colour."""
    import bpy
    h, w = arr.shape[:2]
    px = np.clip(arr.astype(np.float64), 0, 1)
    if srgb:
        rgb = px[..., :3]
        px[..., :3] = np.where(rgb <= 0.0031308, rgb * 12.92, 1.055 * np.power(rgb, 1 / 2.4) - 0.055)
    px[..., 3] = 1.0
    im = bpy.data.images.new(os.path.basename(path), w, h, alpha=True)
    im.colorspace_settings.name = 'Non-Color'
    im.pixels.foreach_set(px.astype(np.float32).ravel())
    im.filepath_raw = path
    im.file_format = 'PNG'
    im.save()
    bpy.data.images.remove(im)


def make_asteroid_moon(mesh_path, baked_path, normal_path=None, collection=None, scene=None):
    """makeAsteroidMoon({meshPath, baked, normal}): the baked artifacts as a Blender object with the celestial
    lambert material (baked object-space normals rotated by the object, against its own sun). Unit-ish radius."""
    import bpy
    from . import moon_materials as MM
    raw = open(mesh_path, 'rb').read()
    count = int(np.frombuffer(raw[:4], np.uint32)[0])
    pos = np.frombuffer(raw[4:4 + count * 12], np.float32).reshape(-1, 3)
    nrm = np.frombuffer(raw[4 + count * 12:4 + count * 24], np.float32).reshape(-1, 3)
    uv = np.frombuffer(raw[4 + count * 24:4 + count * 32], np.float32).reshape(-1, 2)
    from .ringworld import _mesh_from_arrays
    vb = np.stack([pos[:, 0], -pos[:, 2], pos[:, 1]], 1)
    tris = np.arange(count, dtype=np.int64).reshape(-1, 3)
    me = _mesh_from_arrays('asteroid_moon', vb, tris, uv)
    me.normals_split_custom_set_from_vertices([tuple(v) for v in np.stack([nrm[:, 0], -nrm[:, 2], nrm[:, 1]], 1)])
    ob = bpy.data.objects.new('asteroid_moon', me)
    (collection or (scene or bpy.context.scene).collection).objects.link(ob)
    MM.moon_keys_group()
    MM.asteroid_material(ob, baked_path, normal_path)
    return ob
