"""Cloth panels for Blender 5.2 EEVEE: the port of eidoverse/cloth_sim.js (createClothPanel).

The engine's kernel in numpy: a COLS x ROWS grid relaxed by Jacobi-averaged spring corrections over its 12
neighbours (structural, shear, bend) with the anti-streak ramp capped at 0.85, Verlet integration with
damping and a velocity clamp of 0.45 spacings per step, gravity and wind as per-step impulses (wind = windDir
* wind * (windBias + gust(col, row, t)) plus a vertical flutter), then sphere, box and floor colliders with a
collision skin. Each engine step() runs `iterations` (3) of those kernel passes.

Bake and playback: bake() steps the panel over the shot and writes a .pc2 point cache that a Mesh Cache
modifier plays on the panel's grid mesh (Subdivision Surface and smooth shading on top), so the .blend needs
no Python at render time.

The look: material= is the panel's material; without one the panel gets the engine's default fabric (0xcccccc,
roughness 0.6, metalness 0, both faces drawn). map= (or its alias texture=) puts a graphic on the fabric, as the
engine's opts.map did: an Image Texture on the panel's 'UVMap' times the material's base colour, so text and logos
ride the folds. It is set only where nothing feeds the Principled BSDF's Base Color yet (three's `!mat.map`).

Differences from the engine, on purpose:
  - Jacobi for real: the GPU kernel read its neighbours from the same buffer it was writing (a race the
    engine's comment calls race-free); here every pass reads the previous pass's positions;
  - time: the engine's step() advanced 1/60 s per CALL and scenes called it once per frame, so the cloth's
    speed followed the frame rate and the guide's wind recipes were tuned that way. steps_per_frame=1 (the
    default) keeps that meaning; steps_per_second=60 makes the motion frame-rate independent;
  - colliders may be any mesh (collide_with(..., mode='mesh')): nearest-surface push-out through a BVH tree,
    on top of the engine's bounding spheres and boxes.
"""

from __future__ import annotations

import math
import os
import struct

import numpy as np

from ._util import abspath, color

DEFAULTS = dict(width=3.0, height=2.0, cols=40, rows=28, stiffness=0.9, damping=0.97,
                gravity=(0.0, 0.0, -0.0006), wind=0.0004, wind_bias=0.15, wind_dir=(0.0, -1.0, 0.0),
                pin='top', settle_steps=0, iterations=3, thickness=0.03, floor=None,
                steps_per_frame=1, steps_per_second=None, map=None, texture=None)
FABRIC = dict(color=0xcccccc, roughness=0.6, metalness=0.0)     # the engine's default MeshStandardNodeMaterial


def _t3(v):
    """Blender (x, y, z) -> the engine panel's frame (x, y-up, z): (x, z, -y)."""
    return np.array([v[0], v[2], -v[1]], dtype=np.float64)


def _b3(a):
    """engine (..., 3) -> Blender."""
    a = np.asarray(a)
    return np.stack([a[..., 0], -a[..., 2], a[..., 1]], axis=-1)


class ClothPanel:
    """What create_cloth_panel returns: object (the grid mesh with its Mesh Cache), the solver state, the
    engine's setters (set_colliders, set_box_colliders, collide_with, floor, set_pin_position, wind ...) and
    bake()."""

    def __init__(self, scene, o, material, name, cache_dir, location=(0.0, 0.0, 0.0)):
        import bpy
        self.scene = scene
        self.o = o
        self.name = name
        self.material = material
        self.cache_dir = abspath(cache_dir)
        C, R = int(o['cols']), int(o['rows'])
        self.C, self.R, self.N = C, R, C * R
        W, H = float(o['width']), float(o['height'])
        cc, rr = np.meshgrid(np.arange(C), np.arange(R))
        p = np.stack([(cc / (C - 1) - 0.5) * W, (0.5 - rr / (R - 1)) * H, np.zeros_like(cc, dtype=float)], -1)
        self.pos = p.reshape(-1, 3).astype(np.float64)
        self.prev = self.pos.copy()
        self.cc, self.rr = cc.ravel(), rr.ravel()
        self.fixed = np.array([self._is_pinned(c, r) for c, r in zip(self.cc, self.rr)], dtype=bool)
        self.rest = dict(sx=W / (C - 1), sy=H / (R - 1))
        self.rest['shear'] = math.hypot(self.rest['sx'], self.rest['sy'])
        self.t = 0.0
        self.spheres = np.zeros((0, 4))
        self.boxes = np.zeros((0, 2, 3))
        self.mesh_colliders = []
        self._tracked = []
        self.floor_y = -1e9 if o['floor'] is None else float(o['floor'])
        self.stiffness, self.damping = float(o['stiffness']), float(o['damping'])
        self.wind, self.wind_bias = float(o['wind']), float(o['wind_bias'])
        wd = _t3(o['wind_dir'])
        self.wind_dir = wd / (np.linalg.norm(wd) or 1.0)
        self.grav = _t3(o['gravity'])
        self.skin = float(o['thickness'])
        self._neighbours()
        self.object = self._build_object(bpy, material)
        self.object.location = tuple(location)
        bpy.context.view_layer.update()
        self.settle(int(o['settle_steps']))

    def settle(self, steps):
        """Pre-roll `steps` engine steps (the engine's settleSteps), e.g. after adding colliders."""
        for _ in range(int(steps)):
            self.step()

    def _is_pinned(self, c, r):
        spec = self.o['pin']
        idx = r * self.C + c
        if isinstance(spec, (list, tuple, set)):
            return idx in spec
        if callable(spec):
            return bool(spec(c, r))
        return {'top': r == 0, 'top-corners': r == 0 and c in (0, self.C - 1), 'left': c == 0,
                'none': False}.get(spec, r == 0)

    def _neighbours(self):
        """The 12 springs per vertex as (index arrays, rest lengths); -1 where the neighbour is off-grid."""
        C, R = self.C, self.R
        sx, sy, sh = self.rest['sx'], self.rest['sy'], self.rest['shear']
        offs = [(-1, 0, sx), (1, 0, sx), (0, -1, sy), (0, 1, sy), (-1, -1, sh), (1, -1, sh), (-1, 1, sh), (1, 1, sh),
                (-2, 0, 2 * sx), (2, 0, 2 * sx), (0, -2, 2 * sy), (0, 2, 2 * sy)]
        self.nb_idx, self.nb_rest, self.nb_ok = [], [], []
        for dc, dr, rest in offs:
            c2, r2 = self.cc + dc, self.rr + dr
            ok = (c2 >= 0) & (c2 < C) & (r2 >= 0) & (r2 < R)
            self.nb_idx.append(np.where(ok, r2 * C + c2, 0))
            self.nb_ok.append(ok)
            self.nb_rest.append(rest)

    # -------------------------------------------------------------------------------------------
    # the kernel
    # -------------------------------------------------------------------------------------------
    def _pass(self, off3):
        p, pp = self.pos, self.prev
        corr = np.zeros_like(p)
        cnt = np.zeros(self.N)
        for idx, rest, ok in zip(self.nb_idx, self.nb_rest, self.nb_ok):
            d = p[idx] - p
            ln = np.maximum(np.linalg.norm(d, axis=1), 1e-5)
            w = np.clip((ln / rest - 1.10) / 0.25, 0.0, 1.0) * 0.35 + 0.5
            c = d / ln[:, None] * ((ln - rest) * w)[:, None]
            corr += np.where(ok[:, None], c, 0.0)
            cnt += ok
        fc, fr = self.cc.astype(float), self.rr.astype(float)
        gust = (np.sin(fc * 0.12 + self.t * 2) + np.sin(fr * 0.3 + self.t * 3.1) * 0.5) * 0.6
        ext = self.grav[None, :] + self.wind_dir[None, :] * (self.wind * (self.wind_bias + gust))[:, None]
        ext[:, 1] += self.wind * 0.15 * np.sin(fr * 0.25 + self.t * 1.7)
        vel = (p - pp) * self.damping
        vlen = np.maximum(np.linalg.norm(vel, axis=1), 1e-6)
        vmax = min(self.rest['sx'], self.rest['sy']) * 0.45
        vel *= (np.minimum(vlen, vmax) / vlen)[:, None]
        nxt = p + vel + ext + corr / np.maximum(cnt, 1)[:, None] * self.stiffness
        wp = nxt + off3
        for s in self.spheres:
            rad = s[3] + self.skin
            to = wp - s[:3]
            dl = np.maximum(np.linalg.norm(to, axis=1), 1e-5)
            m = dl < rad
            wp[m] = s[:3] + to[m] / dl[m, None] * rad
        for bmin, bmax in self.boxes:
            lo, hi = bmin - self.skin, bmax + self.skin
            inside = np.all((wp > lo) & (wp < hi), axis=1)
            if inside.any():
                q = wp[inside]
                d0, d1 = q - lo, hi - q
                dm = np.minimum(d0, d1)
                ax = np.argmin(dm, axis=1)
                tgt = np.where(d0 < d1, lo, hi)
                q[np.arange(len(q)), ax] = tgt[np.arange(len(q)), ax]
                wp[inside] = q
        if self.mesh_colliders:
            wp = self._mesh_pushout(wp)
        low = wp[:, 1] < self.floor_y + self.skin
        wp[low, 1] = self.floor_y + self.skin
        nxt = wp - off3
        nxt[self.fixed] = p[self.fixed]
        self.prev = np.where(self.fixed[:, None], p, p)
        self.pos = nxt

    def _mesh_pushout(self, wp):
        """Nearest-surface push-out against real meshes (BVH), skin proud of the surface (engine frame)."""
        for tree in self.mesh_colliders:
            pb = _b3(wp)
            for i in range(len(pb)):
                hit = tree.find_nearest(pb[i])
                if hit[0] is None:
                    continue
                loc, nrm = np.array(hit[0]), np.array(hit[1])
                d = pb[i] - loc
                side = float(d @ nrm)
                if side < self.skin:
                    pb[i] = loc + nrm * self.skin
            wp = np.stack([pb[:, 0], pb[:, 2], -pb[:, 1]], axis=-1)
        return wp

    def step(self):
        """One engine step(): t += 1/60, refresh tracked colliders, `iterations` kernel passes."""
        self.t += 1 / 60
        off3 = _t3(np.array(self.object.matrix_world.translation)) if hasattr(self, 'object') else np.zeros(3)
        for objs, kw in self._tracked:
            self._derive(objs, **kw)
        for _ in range(int(self.o['iterations'])):
            self._pass(off3)

    # -------------------------------------------------------------------------------------------
    # colliders and pins (Blender world coordinates)
    # -------------------------------------------------------------------------------------------
    def set_colliders(self, spheres):
        """[{'center': (x, y, z), 'radius': r}] world space, up to 8 (the engine's cap)."""
        self.spheres = np.array([[*_t3(s['center']), s['radius']] for s in spheres[:8]]).reshape(-1, 4)

    def set_box_colliders(self, boxes):
        """[{'min': (x, y, z), 'max': (x, y, z)}] world space AABBs, up to 8."""
        out = []
        for b in boxes[:8]:
            a, c = _t3(b['min']), _t3(b['max'])
            out.append([np.minimum(a, c), np.maximum(a, c)])
        self.boxes = np.array(out).reshape(-1, 2, 3)

    def collide_with(self, objects, as_sphere=False, track=False, mode='bounds'):
        """The engine's collideWith: colliders from objects' bounds (boxes, or spheres with as_sphere), or
        mode='mesh' for nearest-surface collision against their evaluated meshes."""
        objs = list(objects) if isinstance(objects, (list, tuple)) else [objects]
        self._derive(objs, as_sphere=as_sphere, mode=mode)
        if track:
            self._tracked.append((objs, dict(as_sphere=as_sphere, mode=mode)))
        return self

    def _derive(self, objs, as_sphere=False, mode='bounds'):
        import bpy
        from mathutils import Vector
        if mode == 'mesh':
            from mathutils.bvhtree import BVHTree
            dg = bpy.context.evaluated_depsgraph_get()
            self.mesh_colliders = []
            for ob in objs:
                ev = ob.evaluated_get(dg)
                me = ev.to_mesh()
                verts = [ob.matrix_world @ v.co for v in me.vertices]
                polys = [tuple(p.vertices) for p in me.polygons]
                ev.to_mesh_clear()
                self.mesh_colliders.append(BVHTree.FromPolygons(verts, polys))
            return
        spheres, boxes = [], []
        for ob in objs:
            cs = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
            lo = np.min(np.array(cs), axis=0)
            hi = np.max(np.array(cs), axis=0)
            if as_sphere:
                spheres.append({'center': tuple((lo + hi) / 2), 'radius': float(np.linalg.norm(hi - lo) / 2)})
            else:
                boxes.append({'min': tuple(lo), 'max': tuple(hi)})
        if spheres:
            self.set_colliders(spheres)
        if boxes:
            self.set_box_colliders(boxes)

    @property
    def floor(self):
        return self.floor_y

    @floor.setter
    def floor(self, z):
        self.floor_y = float(z)

    def set_pin_position(self, vertex_index, xyz):
        """Move a pinned vertex to a position in the panel object's LOCAL space (the engine's convention)."""
        p = _t3(xyz)
        self.pos[vertex_index] = p
        self.prev[vertex_index] = p

    def set_wind_dir(self, d):
        wd = _t3(d)
        self.wind_dir = wd / (np.linalg.norm(wd) or 1.0)

    # -------------------------------------------------------------------------------------------
    # object, bake, cache
    # -------------------------------------------------------------------------------------------
    def _build_object(self, bpy, material):
        C, R = self.C, self.R
        co = _b3(self.pos)
        a = (self.rr[:-C].reshape(R - 1, C)[:, :-1] * C + self.cc[:-C].reshape(R - 1, C)[:, :-1]).ravel()
        quads = np.stack([a, a + 1, a + C + 1, a + C], axis=1)
        me = bpy.data.meshes.new(self.name)
        me.vertices.add(len(co))
        me.vertices.foreach_set('co', co.astype(np.float32).ravel())
        me.loops.add(quads.size)
        me.loops.foreach_set('vertex_index', quads.ravel())
        me.polygons.add(len(quads))
        me.polygons.foreach_set('loop_start', np.arange(0, quads.size, 4))
        me.update(calc_edges=True)
        uv = me.uv_layers.new(name='UVMap')
        u = (self.cc / (C - 1))
        v = 1.0 - self.rr / (R - 1)
        uv.data.foreach_set('uv', np.stack([u, v], 1)[quads.ravel()].astype(np.float32).ravel())
        for p in me.polygons:
            p.use_smooth = True
        ob = bpy.data.objects.new(self.name, me)
        self.scene.collection.objects.link(ob)
        if material is not None:
            me.materials.append(material)
        return ob

    def bake(self, frame_start=None, frame_end=None, controls=None, subdivide=1, log=print):
        """Step over [frame_start, frame_end] and write <cache>/<name>.pc2, played by a Mesh Cache modifier.
        controls(frame, t, cloth) may move pins, colliders or the wind per frame."""
        sc = self.scene
        fs = sc.frame_start if frame_start is None else int(frame_start)
        fe = sc.frame_end if frame_end is None else int(frame_end)
        fps = sc.render.fps / sc.render.fps_base
        os.makedirs(self.cache_dir, exist_ok=True)
        frames = []
        acc = 0.0
        for f in range(fs, fe + 1):
            sc.frame_set(f)
            if controls:
                controls(f, (f - fs) / fps, self)
            if self.o['steps_per_second']:
                acc += self.o['steps_per_second'] / fps
                n = int(acc)
                acc -= n
            else:
                n = int(self.o['steps_per_frame'])
            for _ in range(n):
                self.step()
            frames.append(_b3(self.pos).astype(np.float32))
        path = os.path.join(self.cache_dir, self.name + '.pc2')
        _write_pc2(path, frames, fs)
        ob = self.object
        mc = ob.modifiers.get('cloth_cache') or ob.modifiers.new('cloth_cache', 'MESH_CACHE')
        mc.cache_format = 'PC2'
        mc.filepath = path
        mc.time_mode = 'FRAME'
        mc.play_mode = 'SCENE'
        mc.frame_start = fs
        mc.frame_scale = 1.0
        mc.forward_axis = 'POS_Y'
        mc.up_axis = 'POS_Z'
        if subdivide and not ob.modifiers.get('cloth_subsurf'):
            ss = ob.modifiers.new('cloth_subsurf', 'SUBSURF')
            ss.levels = ss.render_levels = int(subdivide)
        log(f'[fx.cloth] baked {len(frames)} frames of {self.N} vertices -> {path}')
        return self


def _write_pc2(path, frames, start):
    n = frames[0].shape[0]
    tmp = path + '.tmp'
    with open(tmp, 'wb') as fh:
        fh.write(struct.pack('<12siiffi', b'POINTCACHE2\0', 1, n, float(start), 1.0, len(frames)))
        for fr in frames:
            fh.write(np.ascontiguousarray(fr, dtype='<f4').tobytes())
    os.replace(tmp, path)


def fabric_material(name='cloth_fabric'):
    """The engine's default cloth material, MeshStandardNodeMaterial({color: 0xcccccc, roughness: 0.6, metalness: 0,
    side: DoubleSide}): a Principled BSDF with the colour in linear, both faces drawn."""
    import bpy
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Base Color'].default_value = (*color(FABRIC['color']), 1.0)
    bsdf.inputs['Roughness'].default_value = FABRIC['roughness']
    bsdf.inputs['Metallic'].default_value = FABRIC['metalness']
    mat.use_backface_culling = False
    return mat


def _decal_image(decal, name):
    """opts.map / opts.texture as a bpy Image: an Image as it is; a file path ('//' beside the .blend) loaded through
    harness.assets.load_image_texture (sRGB); a drawing (a media.raster.Canvas, a PIL image, or an (h, w, 3|4) uint8
    array with its top row first) made into a packed sRGB image."""
    import bpy
    if isinstance(decal, bpy.types.Image):
        return decal
    if isinstance(decal, (str, os.PathLike)):
        from ..harness.assets import load_image_texture
        return load_image_texture(abspath(os.fspath(decal)), srgb=True)
    if hasattr(decal, 'result') and hasattr(decal, 'image'):          # media.raster.Canvas
        decal = decal.result()
    if hasattr(decal, 'convert'):                                      # a PIL image
        decal = decal.convert('RGBA')
    px = np.asarray(decal)
    if px.ndim != 3 or px.shape[2] not in (3, 4) or px.dtype != np.uint8:
        raise TypeError('[fx.cloth] map: a bpy Image, an image file path, a media.raster.Canvas, a PIL image or an '
                        f'(h, w, 3|4) uint8 array, not {type(decal).__name__}')
    from ..materials.procedural import image_from_canvas
    return image_from_canvas(px, name, srgb=True, kind='cloth_map')


def apply_decal(material, decal, name='cloth_map'):
    """The engine's `if (decal && !mat.map) mat.map = decal`: an Image Texture of `decal` on the panel's 'UVMap',
    times the material's base colour (three's color x map), into the Principled BSDF's Base Color. A material whose
    Base Color something already feeds keeps it. Returns the Image Texture node, or None when the material kept
    its own."""
    nt = material.node_tree
    bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None) if nt else None
    if bsdf is None:
        raise ValueError(f'[fx.cloth] map: material {material.name!r} has no Principled BSDF to take it; '
                         'put an Image Texture on the UVMap in the material yourself')
    base = bsdf.inputs['Base Color']
    if base.is_linked:
        return None
    img = _decal_image(decal, name)
    x, y = bsdf.location.x, bsdf.location.y
    uv = nt.nodes.new('ShaderNodeUVMap')
    uv.uv_map = 'UVMap'
    uv.location = (x - 760, y - 120)
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.name = tex.label = 'cloth_map'
    tex.image = img
    tex.interpolation = 'Linear'
    tex.extension = 'EXTEND'                      # three's ClampToEdgeWrapping
    tex.location = (x - 560, y - 120)
    mul = nt.nodes.new('ShaderNodeMix')
    mul.data_type, mul.blend_type, mul.clamp_factor = 'RGBA', 'MULTIPLY', True
    mul.location = (x - 240, y - 60)
    ins = {s.identifier: s for s in mul.inputs}
    ins['Factor_Float'].default_value = 1.0
    ins['A_Color'].default_value = tuple(base.default_value)
    nt.links.new(uv.outputs['UV'], tex.inputs['Vector'])
    nt.links.new(tex.outputs['Color'], ins['B_Color'])
    nt.links.new(next(s for s in mul.outputs if s.identifier == 'Result_Color'), base)
    return tex


def create_cloth_panel(scene=None, material=None, name='cloth', cache_dir='//cloth_cache', location=(0, 0, 0),
                       **options):
    """The engine's createClothPanel. The panel hangs in Blender's XZ plane (its face looks along -Y, the
    engine's +Z), row 0 at the top; gravity, wind_dir and colliders are Blender axes, panel units as the
    engine's (gravity and wind are per-step impulses: 0.0006 and 0.0003-0.001). material=None gives the engine's
    default fabric (fabric_material); map= or texture= puts a graphic on it (apply_decal): a bpy Image, an image
    file path, a media.raster.Canvas, a PIL image or an (h, w, 3|4) uint8 array, top row at the panel's top."""
    import bpy
    o = dict(DEFAULTS)
    bad = set(options) - set(o)
    if bad:
        raise TypeError('[fx.cloth] unknown options: ' + ', '.join(sorted(bad)))
    o.update(options)
    sc = scene or bpy.context.scene
    if material is None:
        material = fabric_material(name + '_fabric')
    decal = o['map'] if o['map'] is not None else o['texture']
    if decal is not None:
        apply_decal(material, decal, name + '_map')
    return ClothPanel(sc, o, material, name, cache_dir, location)
