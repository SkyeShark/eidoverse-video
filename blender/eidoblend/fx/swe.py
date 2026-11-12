"""Shallow-water liquid for Blender 5.2 EEVEE: the port of eidoverse/fluid_swe.js.

The solver is the engine's (see _swe_solver.py): flux-form shallow water over a static bed with per-cell
pipe outflows and proportional rescale (h >= 0, mass exact), semi-Lagrangian velocity with surface gravity,
Bingham yield, Manning bed friction and drag; disc emitters; sphere coupling for bodies; advected foam from
churn, crests, wakes and landings; optional hydraulic erosion with talus slumping and an eroding terrain
patch; rain with squall bands; and the spray exchange (Ihmsen-style promotion of droplets that carry volume,
pour droplets, fixed-point deposit of volume, momentum and foam on landing) with the pour stream tubes.

Build, bake, playback:
    swe = create_water_swe(bed_fn=lambda x, y: ..., world_size=(10.8, 10.8), spray_max=6144, ...)
    swe.bake(1, 240, controls=lambda frame, t, swe: swe.set_pours([...]))
  bake() runs the engine's step(dt) once per frame and writes per-frame OpenEXR "data images" that Geometry
  Nodes read back by frame number: the surface (height, depth, foam, foam noise), the bed (erosion), the
  spray points and the stream tubes. The .blend then plays the water with no Python at render time.

Coordinates: Blender's. bed_fn(x, y) -> z (world). Pours, emitters and spheres take Blender world positions
and velocities. Inside, the solver works in three's frame (x, y-up, z) like the engine.

The look is EEVEE's: a Principled water surface with ray-traced refraction and reflections of the scene's
own world (the engine's envTex/skyColor fresnel term and hand-tuned specular are not needed), the engine's
depth tint and absorption, suspended-sediment muddying, eroded foam coverage through the flow-advected foam
noise, shore fade, optional emission (lava); white-grey droplets stretched along their velocity; glassy
streams that aerate as they fall.
"""

from __future__ import annotations

import math
import os
import time

import numpy as np

from ._swe_solver import SWESolver, SOLVER_DEFAULTS, LIQUID_PRESETS, EROSION_DEFAULTS, NEMI, SSEG, SRAD
from ._util import color, abspath, frame_file, write_exr, scene_fps, smoothstep

__all__ = ['create_water_swe', 'LIQUID_PRESETS', 'WaterSWE']

SPRAY_W = 128
DRY_SHOW = 1e-3          # metres: thinner columns are drawn as dry (their shore-fade alpha is under 0.004)


def _camel(name):
    parts = name.split('_')
    return parts[0] + ''.join(p[:1].upper() + p[1:] for p in parts[1:])


def _b2t(p):
    return (float(p[0]), float(p[2]), -float(p[1]))


def _b2t_vec(v):
    return (float(v[0]), float(v[2]), -float(v[1]))


class WaterSWE:
    """What create_water_swe returns (engine names in brackets):

    surface_object   the displaced water surface (surfaceMesh)
    terrain_object   the eroding ground patch, erosion with terrain only (terrainMesh)
    spray_object     the droplet points, spray_max > 0 only (sprayMesh)
    stream_object    the pour streams, spray_max > 0 only (streamMesh)
    material         the surface material
    solver           the numpy solver (fields, setters, volume())
    set_pours / set_emitters / set_spheres / set_rain      as the engine's, Blender coordinates
    bake(frame_start, frame_end, controls)                 step once per frame and write the caches
    """

    def __init__(self, scene, o, bed_fn, name, cache_dir, precision, dry_sink=None):
        import bpy
        self.scene = scene
        self.o = o
        self.name = name
        self.cache_dir = abspath(cache_dir)
        cell = float(o['worldSize'][0]) / float(o['gridSize'][0])
        self.dry_sink = max(0.01, 0.25 * cell) if dry_sink is None else float(dry_sink)
        cb = o['domainCenter']                          # Blender
        self.center_b = np.array(cb, dtype=np.float64)
        o3 = dict(o)
        o3['domainCenter'] = _b2t(cb)
        NX, NZ = int(o['gridSize'][0]), int(o['gridSize'][1])
        WX, WZ = float(o['worldSize'][0]), float(o['worldSize'][1])
        c3 = o3['domainCenter']
        wx = ((np.arange(NX) + 0.5) / NX - 0.5) * WX + c3[0]
        wz = ((np.arange(NZ) + 0.5) / NZ - 0.5) * WZ + c3[2]
        WXg, WZg = np.meshgrid(wx, wz)
        bed = self._eval_bed(bed_fn, WXg, -WZg)          # Blender (x, y = -z) -> z = three y
        self.solver = SWESolver(o3, bed, precision=precision)
        self.NX, self.NZ, self.WX, self.WZ = NX, NZ, WX, WZ
        self.center3 = np.array(c3)
        self.materials = {}
        self.surface_object = self._grid_object(bpy, name + '_surface')
        # the engine's surface cast no shadow (a transparent, depth-write-free sheet); EEVEE would shadow the
        # bed under the water with a refractive sheet as if it were opaque
        self.surface_object.visible_shadow = False
        self.material = self._surface_material(bpy)
        self.surface_object.data.materials.append(self.material)
        self._surface_nodes(bpy)
        self.terrain_object = None
        if self.solver.ERO and self.solver.EK['terrain']:
            self.terrain_object = self._grid_object(bpy, name + '_terrain')
            self.terrain_object.data.materials.append(self._terrain_material(bpy))
            self._terrain_nodes(bpy)
        self.spray_object = self.stream_object = None
        if self.solver.spray is not None:
            self.spray_object = self._spray_object(bpy)
            self.stream_object = self._stream_object(bpy)

    @staticmethod
    def _eval_bed(fn, X, Y):
        try:
            z = np.asarray(fn(X, Y), dtype=np.float64)
            if z.shape == X.shape:
                return z.astype(np.float32)
        except Exception:
            pass
        out = np.empty(X.shape, dtype=np.float32)
        for k in range(X.shape[0]):
            for i in range(X.shape[1]):
                out[k, i] = fn(float(X[k, i]), float(Y[k, i]))
        return out

    # ------------------------------------------------------------------------------------------------
    # setters (Blender coordinates)
    # ------------------------------------------------------------------------------------------------
    def set_pours(self, pours):
        """[{x, y, z, vx, vy, vz, rate (m3/s), style 'jet'|'seep', seep_width}] -- mouths on the visible lip."""
        lst = []
        for p in pours or []:
            x, y, z = _b2t((p['x'], p['y'], p['z']))
            vx, vy, vz = _b2t_vec((p.get('vx', 0), p.get('vy', 0), p.get('vz', 0)))
            lst.append(dict(x=x, y=y, z=z, vx=vx, vy=vy, vz=vz, rate=p.get('rate', 0), style=p.get('style', 'jet'),
                            seepWidth=p.get('seep_width', p.get('seepWidth', 0.5))))
        self.solver.set_pours(lst)

    def set_emitters(self, emitters):
        """[{x, y, rate (m3/s), vx, vy, foam}] -- disc injection at a ground point (no droplets)."""
        lst = []
        for e in emitters or []:
            lst.append(dict(x=e['x'], z=-e['y'], rate=e.get('rate', 0), vx=e.get('vx', 0), vz=-e.get('vy', 0),
                            foam=e.get('foam', 0.8)))
        self.solver.set_emitters(lst)

    def set_spheres(self, spheres):
        """[{x, y, z, r, vx, vy, vz}] -- bodies in the water; vz (Blender's vertical) drives the entry splash."""
        lst = []
        for s in spheres or []:
            x, y, z = _b2t((s['x'], s['y'], s['z']))
            vx, vy, vz = _b2t_vec((s.get('vx', 0), s.get('vy', 0), s.get('vz', 0)))
            lst.append(dict(x=x, y=y, z=z, r=s['r'], vx=vx, vy=vy, vz=vz))
        self.solver.set_spheres(lst)

    def set_rain(self, v):
        self.solver.rain = max(0.0, float(v))

    # ------------------------------------------------------------------------------------------------
    # bake
    # ------------------------------------------------------------------------------------------------
    def bake(self, frame_start=None, frame_end=None, controls=None, track_spheres=(), log=print):
        """Step once per frame over [frame_start, frame_end] (the engine's renderFrame: controls, then step).

        controls(frame, t, swe) sets pours / spheres / emitters / rain for the frame (t = seconds from
        frame_start). track_spheres = [(object, radius), ...] feeds those objects' positions and velocities
        as spheres every frame. Writes <cache>/<name>_{water,bed,spray,stream}_####.exr."""
        sc = self.scene
        fs = sc.frame_start if frame_start is None else int(frame_start)
        fe = sc.frame_end if frame_end is None else int(frame_end)
        fps = scene_fps(sc)
        os.makedirs(self.cache_dir, exist_ok=True)
        S = self.solver
        t0 = time.time()
        prev = {}
        v0 = S.volume()
        for f in range(fs, fe + 1):
            t = (f - fs) / fps
            if track_spheres:
                sc.frame_set(f)
                sph = []
                for ob, r in track_spheres:
                    p = np.array(ob.matrix_world.translation)
                    v = (p - prev[ob.name]) * fps if ob.name in prev else np.zeros(3)
                    prev[ob.name] = p
                    sph.append(dict(x=p[0], y=p[1], z=p[2], r=r, vx=v[0], vy=v[1], vz=v[2]))
                self.set_spheres(sph)
            if controls:
                controls(f, t, self)
            S.step(1.0 / fps)
            self._write_frame(f)
            if (f - fs) % 24 == 0 or f == fe:
                log(f'[fx.swe] frame {f} t {t:.2f} s  water {S.volume():.3f} m3 (start {v0:.3f})'
                    f'  max depth {float(S.h.max()):.3f} m  {time.time() - t0:.1f} s')
        self._attach(fs, fe)
        log(f'[fx.swe] baked frames {fs}..{fe} in {time.time() - t0:.1f} s -> {self.cache_dir}')
        return self

    def _surface_height(self, bedL, h, level):
        """Where the surface mesh's vertices go. Wet columns sit at their water level (bed + h + ripple, the
        engine's displace kernel). Dry ones must never sit ON the bed: the engine's surface was alpha-blended with
        no depth write, so its dry part was simply invisible, but EEVEE's raytraced-refraction layer draws a
        fragment that lies exactly on an opaque surface (the eroding patch, a ground built from the same bed) even
        where its alpha is 0, and draws it black: z-fight speckle over a dry patch, a black seam along the rim.
        So dry vertices sit dry_sink under their bed: far enough for the depth buffer at film distances, little
        enough not to poke through a thin-walled vessel. A shoreline triangle then dips under the bank where the
        engine's thin edge faded out."""
        return np.where(h > DRY_SHOW, level, bedL - self.dry_sink)

    def _write_frame(self, f):
        S = self.solver
        cy = self.center3[1]
        bedL = S.live_bed()
        surf = self._surface_height(bedL, S.h, bedL + S.h + S.ripple) - cy
        write_exr(frame_file(self.cache_dir, self.name + '_water', f, 'exr'),
                  np.stack([surf, S.h, S.foam, S.foam_nz], axis=-1))
        if S.ERO:
            write_exr(frame_file(self.cache_dir, self.name + '_bed', f, 'exr'),
                      np.stack([bedL - cy, S.dbed, S.silt, S.age], axis=-1))
        if S.spray is not None:
            write_exr(frame_file(self.cache_dir, self.name + '_spray', f, 'exr'), self._spray_image())
            write_exr(frame_file(self.cache_dir, self.name + '_stream', f, 'exr'), self._stream_image())

    def _spray_image(self):
        """Per droplet: (x, y, z, alpha) rows then (scale along velocity, across, 0, 0) and velocity rows, Blender
        axes, positions relative to the domain centre. alpha/size follow the engine's sprite material."""
        o, S = self.o, self.solver.spray
        P, V = S['P'], S['V']
        M = S['M']
        life = P[:, 3]
        alive = life > 0
        foamP = V[:, 3] < -0.5
        mist = S['is_mist']
        lifeK = np.clip(life / 1.3, 0, 1)
        born = 1 - lifeK
        spd = np.linalg.norm(V[:, :3], axis=1)
        stretchD = np.minimum(spd * (0.14 * o['sprayStretch']) + 1.0, 1.0 + 2.4 * o['sprayStretch'])
        stretch = np.where(foamP, 1.0, np.where(mist, np.minimum(spd * 0.04 + 1.0, 1.6), stretchD))
        szK = np.where(foamP, 0.0, np.where(mist, 1.8, 1.0))
        baseS = o['spraySize'] * (S['size_rand'] * 0.9 + 0.55) * (born * 0.5 + 0.6) * szK
        mistFade = smoothstep(0.3, 1.2, spd)
        aK = np.where(foamP, 0.0, np.where(mist, 0.11 * mistFade, lifeK * 0.6 + 0.2))
        alpha = smoothstep(0.0, 0.15, born) * aK * o['dropletVisibility'] * alive
        # the engine's sprite fades by alpha; a lit droplet in EEVEE fades by SIZE (no dithering noise on
        # centimetre-sized drops): the visible disc of the soft sprite is about half its quad, and its
        # coverage scales the drop's cross-section (radius ~ sqrt(alpha / 0.8))
        k = np.sqrt(np.clip(alpha / 0.8, 0.0, 1.0)) * 0.5
        along = np.minimum(baseS * stretch, 0.26) * k
        across = baseS / (stretch * 0.5 + 0.5) * k
        c = self.center3
        pb = np.stack([P[:, 0] - c[0], -(P[:, 2] - c[2]), P[:, 1] - c[1]], axis=1)
        vb = np.stack([V[:, 0], -V[:, 2], V[:, 1]], axis=1)
        R = int(math.ceil(M / SPRAY_W))
        img = np.zeros((3 * R, SPRAY_W, 4), dtype=np.float32)
        a = img[:R].reshape(-1, 4)
        a[:M, :3], a[:M, 3] = pb, alpha
        b = img[R:2 * R].reshape(-1, 4)
        b[:M, 0], b[:M, 1], b[:M, 2] = along, across, mist.astype(np.float32)
        cc = img[2 * R:].reshape(-1, 4)
        cc[:M, :3] = vb
        return img

    def _stream_image(self):
        S = self.solver.spray
        c = self.center3
        pos, nor = S['stream_pos'], S['stream_nor']
        n = len(pos)
        R = int(math.ceil(n / SPRAY_W))
        img = np.zeros((2 * R, SPRAY_W, 4), dtype=np.float32)
        a = img[:R].reshape(-1, 4)
        a[:n, 0], a[:n, 1], a[:n, 2], a[:n, 3] = pos[:, 0] - c[0], -(pos[:, 2] - c[2]), pos[:, 1] - c[1], pos[:, 3]
        b = img[R:].reshape(-1, 4)
        b[:n, 0], b[:n, 1], b[:n, 2], b[:n, 3] = nor[:, 0], -nor[:, 2], nor[:, 1], nor[:, 3]
        return img

    def _attach(self, fs, fe):
        """Point the GN image sequences at the baked files (file number = scene frame)."""
        import bpy
        for key, img in self._images.items():
            path = frame_file(self.cache_dir, self.name + '_' + key, fs, 'exr')
            img.filepath = path
            img.source = 'SEQUENCE'
            img.colorspace_settings.is_data = True
            img.alpha_mode = 'CHANNEL_PACKED'
            img.reload()

    # ------------------------------------------------------------------------------------------------
    # objects and node groups
    # ------------------------------------------------------------------------------------------------
    def _image(self, bpy, key):
        if not hasattr(self, '_images'):
            self._images = {}
        if key not in self._images:
            img = bpy.data.images.new(f'{self.name}_{key}', 4, 4, float_buffer=True, alpha=True)
            img.colorspace_settings.is_data = True
            img.alpha_mode = 'CHANNEL_PACKED'
            self._images[key] = img
        return self._images[key]

    def _grid_object(self, bpy, name):
        """NX x NZ vertices spanning the domain like the engine's PlaneGeometry(WX, WZ, NX-1, NZ-1); attribute
        swe_uv = (i/(NX-1), k/(NZ-1)) is where the GN graph samples the cache images."""
        NX, NZ, WX, WZ = self.NX, self.NZ, self.WX, self.WZ
        ii, kk = np.meshgrid(np.arange(NX), np.arange(NZ))
        u = (ii / (NX - 1)).ravel()
        w = (kk / (NZ - 1)).ravel()
        co = np.stack([(u - 0.5) * WX, -(w - 0.5) * WZ, np.zeros_like(u)], axis=1)
        a = (kk[:-1, :-1] * NX + ii[:-1, :-1]).ravel()
        quads = np.stack([a, a + NX, a + NX + 1, a + 1], axis=1)       # counter-clockwise seen from +Z
        me = bpy.data.meshes.new(name)
        me.vertices.add(len(co))
        me.vertices.foreach_set('co', co.astype(np.float32).ravel())
        me.loops.add(quads.size)
        me.loops.foreach_set('vertex_index', quads.ravel())
        me.polygons.add(len(quads))
        me.polygons.foreach_set('loop_start', np.arange(0, quads.size, 4))
        me.update(calc_edges=True)
        at = me.attributes.new('swe_uv', 'FLOAT_VECTOR', 'POINT')
        at.data.foreach_set('vector', np.stack([u, w, np.zeros_like(u)], axis=1).astype(np.float32).ravel())
        uvl = me.uv_layers.new(name='UVMap')
        lu = np.stack([u, 1 - w], axis=1)[quads.ravel()]
        uvl.data.foreach_set('uv', lu.astype(np.float32).ravel())
        ob = bpy.data.objects.new(name, me)
        self.scene.collection.objects.link(ob)
        ob.location = tuple(self.center_b)
        return ob

    def _gn(self, bpy, name):
        from ._nodes import new_group
        tree, gi, go = new_group(name, 'GeometryNodeTree', [('Geometry', 'NodeSocketGeometry')],
                                 [('Geometry', 'NodeSocketGeometry')])
        return tree, gi, go

    @staticmethod
    def _img_node(nodes, img, interp='Linear'):
        n = nodes.new('GeometryNodeImageTexture')
        n.interpolation = interp
        n.extension = 'EXTEND'
        n.inputs['Image'].default_value = img
        return n

    def _surface_nodes(self, bpy):
        tree, gi, go = self._gn(bpy, self.name + '.surface')
        N, L = tree.nodes, tree.links
        uv = N.new('GeometryNodeInputNamedAttribute')
        uv.data_type = 'FLOAT_VECTOR'
        uv.inputs['Name'].default_value = 'swe_uv'
        tm = N.new('GeometryNodeInputSceneTime')
        tex = self._img_node(N, self._image(bpy, 'water'))
        L.new(uv.outputs['Attribute'], tex.inputs['Vector'])
        L.new(tm.outputs['Frame'], tex.inputs['Frame'])
        sep = N.new('FunctionNodeSeparateColor')
        L.new(tex.outputs['Color'], sep.inputs['Color'])
        pos = N.new('GeometryNodeInputPosition')
        sxyz = N.new('ShaderNodeSeparateXYZ')
        L.new(pos.outputs[0], sxyz.inputs[0])
        cxyz = N.new('ShaderNodeCombineXYZ')
        L.new(sxyz.outputs[0], cxyz.inputs[0])
        L.new(sxyz.outputs[1], cxyz.inputs[1])
        L.new(sep.outputs[0], cxyz.inputs[2])
        sp = N.new('GeometryNodeSetPosition')
        L.new(gi.outputs[0], sp.inputs['Geometry'])
        L.new(cxyz.outputs[0], sp.inputs['Position'])
        geo = sp.outputs[0]
        for ch, nm in ((1, 'swe_depth'), (2, 'swe_foam')):
            st = N.new('GeometryNodeStoreNamedAttribute')
            st.data_type = 'FLOAT'
            st.domain = 'POINT'
            st.inputs['Name'].default_value = nm
            L.new(geo, st.inputs['Geometry'])
            L.new(sep.outputs[ch], st.inputs['Value'])
            geo = st.outputs[0]
        st = N.new('GeometryNodeStoreNamedAttribute')
        st.data_type = 'FLOAT'
        st.domain = 'POINT'
        st.inputs['Name'].default_value = 'swe_foam_nz'
        L.new(geo, st.inputs['Geometry'])
        L.new(tex.outputs['Alpha'], st.inputs['Value'])
        geo = st.outputs[0]
        if self.solver.ERO:
            btex = self._img_node(N, self._image(bpy, 'bed'))
            L.new(uv.outputs['Attribute'], btex.inputs['Vector'])
            L.new(tm.outputs['Frame'], btex.inputs['Frame'])
            bsep = N.new('FunctionNodeSeparateColor')
            L.new(btex.outputs['Color'], bsep.inputs['Color'])
            st = N.new('GeometryNodeStoreNamedAttribute')
            st.data_type = 'FLOAT'
            st.domain = 'POINT'
            st.inputs['Name'].default_value = 'swe_silt'
            L.new(geo, st.inputs['Geometry'])
            L.new(bsep.outputs[2], st.inputs['Value'])
            geo = st.outputs[0]
        sm = N.new('GeometryNodeSetShadeSmooth')
        L.new(geo, sm.inputs['Geometry'])
        L.new(sm.outputs[0], go.inputs[0])
        mod = self.surface_object.modifiers.new('swe', 'NODES')
        mod.node_group = tree

    def _terrain_nodes(self, bpy):
        tree, gi, go = self._gn(bpy, self.name + '.terrain')
        N, L = tree.nodes, tree.links
        uv = N.new('GeometryNodeInputNamedAttribute')
        uv.data_type = 'FLOAT_VECTOR'
        uv.inputs['Name'].default_value = 'swe_uv'
        tm = N.new('GeometryNodeInputSceneTime')
        btex = self._img_node(N, self._image(bpy, 'bed'))
        L.new(uv.outputs['Attribute'], btex.inputs['Vector'])
        L.new(tm.outputs['Frame'], btex.inputs['Frame'])
        bsep = N.new('FunctionNodeSeparateColor')
        L.new(btex.outputs['Color'], bsep.inputs['Color'])
        wtex = self._img_node(N, self._image(bpy, 'water'))
        L.new(uv.outputs['Attribute'], wtex.inputs['Vector'])
        L.new(tm.outputs['Frame'], wtex.inputs['Frame'])
        wsep = N.new('FunctionNodeSeparateColor')
        L.new(wtex.outputs['Color'], wsep.inputs['Color'])
        pos = N.new('GeometryNodeInputPosition')
        sxyz = N.new('ShaderNodeSeparateXYZ')
        L.new(pos.outputs[0], sxyz.inputs[0])
        cxyz = N.new('ShaderNodeCombineXYZ')
        L.new(sxyz.outputs[0], cxyz.inputs[0])
        L.new(sxyz.outputs[1], cxyz.inputs[1])
        L.new(bsep.outputs[0], cxyz.inputs[2])
        sp = N.new('GeometryNodeSetPosition')
        L.new(gi.outputs[0], sp.inputs['Geometry'])
        L.new(cxyz.outputs[0], sp.inputs['Position'])
        geo = sp.outputs[0]
        for src, nm in ((bsep.outputs[1], 'swe_delta'), (btex.outputs['Alpha'], 'swe_age'), (wsep.outputs[1], 'swe_depth')):
            st = N.new('GeometryNodeStoreNamedAttribute')
            st.data_type = 'FLOAT'
            st.domain = 'POINT'
            st.inputs['Name'].default_value = nm
            L.new(geo, st.inputs['Geometry'])
            L.new(src, st.inputs['Value'])
            geo = st.outputs[0]
        sm = N.new('GeometryNodeSetShadeSmooth')
        L.new(geo, sm.inputs['Geometry'])
        L.new(sm.outputs[0], go.inputs[0])
        mod = self.terrain_object.modifiers.new('swe', 'NODES')
        mod.node_group = tree

    def _index_sampler(self, N, L, img, rows_total, row_offset, interp='Closest'):
        """GN: sample the data image's texel for each element's index: x = i % W, y = i // W + row_offset."""
        idx = N.new('GeometryNodeInputIndex')
        mod = N.new('ShaderNodeMath')
        mod.operation = 'MODULO'
        mod.inputs[1].default_value = SPRAY_W
        L.new(idx.outputs[0], mod.inputs[0])
        div = N.new('ShaderNodeMath')
        div.operation = 'DIVIDE'
        div.inputs[1].default_value = SPRAY_W
        L.new(idx.outputs[0], div.inputs[0])
        fl = N.new('ShaderNodeMath')
        fl.operation = 'FLOOR'
        L.new(div.outputs[0], fl.inputs[0])
        ux = N.new('ShaderNodeMath')
        ux.operation = 'MULTIPLY_ADD'
        ux.inputs[1].default_value = 1.0 / SPRAY_W
        ux.inputs[2].default_value = 0.5 / SPRAY_W
        L.new(mod.outputs[0], ux.inputs[0])
        uy = N.new('ShaderNodeMath')
        uy.operation = 'MULTIPLY_ADD'
        uy.inputs[1].default_value = 1.0 / rows_total
        uy.inputs[2].default_value = (row_offset + 0.5) / rows_total
        L.new(fl.outputs[0], uy.inputs[0])
        cv = N.new('ShaderNodeCombineXYZ')
        L.new(ux.outputs[0], cv.inputs[0])
        L.new(uy.outputs[0], cv.inputs[1])
        tex = self._img_node(N, img, interp)
        L.new(cv.outputs[0], tex.inputs['Vector'])
        tm = N.new('GeometryNodeInputSceneTime')
        L.new(tm.outputs['Frame'], tex.inputs['Frame'])
        return tex

    def _spray_object(self, bpy):
        """Droplets: one point per spray slot, placed from the spray image; dead and foam-state slots are
        deleted; live ones instance a small sphere stretched along the velocity."""
        M = self.solver.spray['M']
        R = int(math.ceil(M / SPRAY_W))
        me = bpy.data.meshes.new(self.name + '_spray')
        me.vertices.add(M)
        ob = bpy.data.objects.new(self.name + '_spray', me)
        self.scene.collection.objects.link(ob)
        ob.location = tuple(self.center_b)
        tree, gi, go = self._gn(bpy, self.name + '.spray')
        N, L = tree.nodes, tree.links
        img = self._image(bpy, 'spray')
        t_pos = self._index_sampler(N, L, img, 3 * R, 0)
        t_sz = self._index_sampler(N, L, img, 3 * R, R)
        t_vel = self._index_sampler(N, L, img, 3 * R, 2 * R)
        sp = N.new('GeometryNodeSetPosition')
        L.new(gi.outputs[0], sp.inputs['Geometry'])
        L.new(t_pos.outputs['Color'], sp.inputs['Position'])
        geo = sp.outputs[0]
        # store per-point data BEFORE deleting the dead slots: deletion renumbers the indices
        ssz = N.new('FunctionNodeSeparateColor')
        L.new(t_sz.outputs['Color'], ssz.inputs['Color'])
        scl = N.new('ShaderNodeCombineXYZ')
        L.new(ssz.outputs[0], scl.inputs[0])
        L.new(ssz.outputs[1], scl.inputs[1])
        L.new(ssz.outputs[1], scl.inputs[2])
        for src, nm, dt in ((t_vel.outputs['Color'], 'swe_vel', 'FLOAT_VECTOR'), (scl.outputs[0], 'swe_scale', 'FLOAT_VECTOR'),
                            (t_pos.outputs['Alpha'], 'swe_alpha', 'FLOAT')):
            st = N.new('GeometryNodeStoreNamedAttribute')
            st.data_type = dt
            st.domain = 'POINT'
            st.inputs['Name'].default_value = nm
            L.new(geo, st.inputs['Geometry'])
            L.new(src, st.inputs['Value'])
            geo = st.outputs[0]
        cmp = N.new('FunctionNodeCompare')
        cmp.data_type = 'FLOAT'
        cmp.operation = 'LESS_EQUAL'
        cmp.inputs[1].default_value = 0.002
        L.new(t_pos.outputs['Alpha'], cmp.inputs[0])
        dl = N.new('GeometryNodeDeleteGeometry')
        dl.domain = 'POINT'
        L.new(geo, dl.inputs['Geometry'])
        L.new(cmp.outputs[0], dl.inputs['Selection'])
        ico = N.new('GeometryNodeMeshIcoSphere')
        ico.inputs['Radius'].default_value = 0.5            # scale = diameter
        ico.inputs['Subdivisions'].default_value = 2
        smooth = N.new('GeometryNodeSetShadeSmooth')
        L.new(ico.outputs['Mesh'], smooth.inputs['Geometry'])
        # geometry made inside the graph carries no material slot: give the droplet the spray material
        spray_mat = self._spray_material(bpy)
        setm = N.new('GeometryNodeSetMaterial')
        L.new(smooth.outputs[0], setm.inputs['Geometry'])
        setm.inputs['Material'].default_value = spray_mat
        smooth = setm
        a_vel = N.new('GeometryNodeInputNamedAttribute')
        a_vel.data_type = 'FLOAT_VECTOR'
        a_vel.inputs['Name'].default_value = 'swe_vel'
        a_scl = N.new('GeometryNodeInputNamedAttribute')
        a_scl.data_type = 'FLOAT_VECTOR'
        a_scl.inputs['Name'].default_value = 'swe_scale'
        rot = N.new('FunctionNodeAlignRotationToVector')
        rot.axis = 'X'
        L.new(a_vel.outputs['Attribute'], rot.inputs['Vector'])
        inst = N.new('GeometryNodeInstanceOnPoints')
        L.new(dl.outputs[0], inst.inputs['Points'])
        L.new(smooth.outputs[0], inst.inputs['Instance'])
        L.new(rot.outputs[0], inst.inputs['Rotation'])
        L.new(a_scl.outputs['Attribute'], inst.inputs['Scale'])
        L.new(inst.outputs[0], go.inputs[0])
        mod = ob.modifiers.new('swe', 'NODES')
        mod.node_group = tree
        ob.data.materials.append(spray_mat)
        return ob

    def _stream_object(self, bpy):
        n = NEMI * SSEG * SRAD
        R = int(math.ceil(n / SPRAY_W))
        faces = []
        for p in range(NEMI):
            base = p * SSEG * SRAD
            for i in range(SSEG - 1):
                for j in range(SRAD):
                    a = base + i * SRAD + j
                    b = base + i * SRAD + (j + 1) % SRAD
                    c = base + (i + 1) * SRAD + j
                    d = base + (i + 1) * SRAD + (j + 1) % SRAD
                    faces.append((a, b, d, c))
        me = bpy.data.meshes.new(self.name + '_stream')
        me.from_pydata([(0, 0, 0)] * n, [], faces)
        uvs = np.array([((v % (SSEG * SRAD)) % SRAD / SRAD, (v % (SSEG * SRAD)) // SRAD / (SSEG - 1)) for v in range(n)])
        at = me.attributes.new('swe_suv', 'FLOAT_VECTOR', 'POINT')
        at.data.foreach_set('vector', np.concatenate([uvs, np.zeros((n, 1))], axis=1).astype(np.float32).ravel())
        ob = bpy.data.objects.new(self.name + '_stream', me)
        self.scene.collection.objects.link(ob)
        ob.location = tuple(self.center_b)
        tree, gi, go = self._gn(bpy, self.name + '.stream')
        N, L = tree.nodes, tree.links
        img = self._image(bpy, 'stream')
        t_pos = self._index_sampler(N, L, img, 2 * R, 0)
        t_nor = self._index_sampler(N, L, img, 2 * R, R)
        sp = N.new('GeometryNodeSetPosition')
        L.new(gi.outputs[0], sp.inputs['Geometry'])
        L.new(t_pos.outputs['Color'], sp.inputs['Position'])
        geo = sp.outputs[0]
        for src, nm in ((t_pos.outputs['Alpha'], 'swe_alpha'), (t_nor.outputs['Alpha'], 'swe_tl')):
            st = N.new('GeometryNodeStoreNamedAttribute')
            st.data_type = 'FLOAT'
            st.domain = 'POINT'
            st.inputs['Name'].default_value = nm
            L.new(geo, st.inputs['Geometry'])
            L.new(src, st.inputs['Value'])
            geo = st.outputs[0]
        tm = N.new('GeometryNodeInputSceneTime')
        st = N.new('GeometryNodeStoreNamedAttribute')
        st.data_type = 'FLOAT'
        st.domain = 'POINT'
        st.inputs['Name'].default_value = 'swe_time'
        L.new(geo, st.inputs['Geometry'])
        L.new(tm.outputs['Seconds'], st.inputs['Value'])
        sm = N.new('GeometryNodeSetShadeSmooth')
        L.new(st.outputs[0], sm.inputs['Geometry'])
        L.new(sm.outputs[0], go.inputs[0])
        mod = ob.modifiers.new('swe', 'NODES')
        mod.node_group = tree
        ob.data.materials.append(self._stream_material(bpy))
        return ob

    # ------------------------------------------------------------------------------------------------
    # materials
    # ------------------------------------------------------------------------------------------------
    def _surface_material(self, bpy):
        from ._nodes import Builder
        o = self.o
        mat = bpy.data.materials.new(self.name + '_water')
        mat.use_nodes = True
        mat.surface_render_method = 'DITHERED'
        mat.use_raytrace_refraction = True
        mat.use_backface_culling = False
        nt = mat.node_tree
        nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        out.location = (1200, 0)
        b = Builder(nt)

        def attr(nm):
            n = b.node('ShaderNodeAttribute', attribute_name=nm, attribute_type='GEOMETRY')
            return b.s(n.outputs['Fac'])

        h = attr('swe_depth')
        f = attr('swe_foam')
        fnz = attr('swe_foam_nz')
        shallow, deep = color(o['shallowColor']), color(o['deepColor'])
        absorb = 1.0 - b.exp(-h * o['absorption'])                  # the engine's depth tint factor
        tint = b.rgb_mix((*shallow, 1), (*deep, 1), absorb)
        if self.solver.ERO:
            silt = attr('swe_silt')
            muddy = b.smoothstep(0.004, 0.10, silt)
            tint = b.rgb_mix(tint, (*color(self.solver.EK['siltWaterColor']), 1), muddy * 0.85)
        rough = 0.02 + 0.5 / max(o['specPow'], 1.0) ** 0.5            # specPow 90 -> 0.07, gel 260 -> 0.05, mud 18 -> 0.14
        # Clear water refracts (transmission); the tinted body and the foam are diffuse. EEVEE renders a pixel's
        # refraction or its opaque closures, not a blend of the two: given both (a transmission weight between 0
        # and 1, or Principled BSDFs mixed by Mix Shader) it shows a fixed per-pixel pattern without the refraction,
        # at any sample count (tests/water3d/probe_partial_transmission.py). So the choice is made here, per
        # shading sample, with the engine's weights, as EEVEE's own dithered transparency chooses: a white-noise
        # hash of the shaded position (new at every sample, since EEVEE jitters each sample's projection) picks
        # clear water with probability (1 - body)(1 - foam), else body-or-foam, and ONE Principled renders the pick
        # with transmission exactly 0 or 1. The samples then average to the engine's blend.
        body = absorb * o['surfaceOpacity']                         # the body (tinted, opaque) share of the water
        clear_tint = b.rgb_mix((1, 1, 1, 1), tint, b.min(absorb * 1.6, 1.0))
        fv = b.clamp(f * o['foamStrength'], 0.0, 1.2)
        cov = b.smoothstep(0.02, 0.30, fv - fnz * 0.55)
        wisp = b.smoothstep(0.0, 0.5, fv) * b.smoothstep(0.75, 0.35, fnz) * 0.25
        foam = b.clamp(cov * 0.8 + wisp)                            # the engine's coverage + lace residue
        w_body = body * (1.0 - foam)
        share_foam = foam / b.max(foam + w_body, 1e-4)              # of the non-clear picks, how many are foam
        geo = b.node('ShaderNodeNewGeometry')
        pick = b.node('ShaderNodeTexWhiteNoise', noise_dimensions='3D')
        nt.links.new(geo.outputs['Position'], pick.inputs['Vector'])
        clear = b.math('LESS_THAN', b.s(pick.outputs['Value']), (1.0 - body) * (1.0 - foam))   # 1 = clear water
        opaque_col = b.rgb_mix(tint, (*[c * 0.92 for c in color(o['foamColor'])], 1), share_foam)
        P = b.node('ShaderNodeBsdfPrincipled')
        P.inputs['IOR'].default_value = 1.333
        b.link(b.rgb_mix(opaque_col, clear_tint, clear), P.inputs['Base Color'])
        b.link(clear, P.inputs['Transmission Weight'])
        b.link(rough + share_foam * (1.0 - clear) * (0.65 - rough), P.inputs['Roughness'])
        shader = P.outputs[0]
        if o['emissiveStrength'] > 0:
            # the engine: col = mix(surface, emissiveColor * strength, glow * min(strength, 1)) under the foam,
            # glow = 1 - exp(-h * emissiveFalloff): deep water glows, the shallows stay water. Emission is not a
            # G-buffer closure, so this mix costs no extra closure
            glow = 1.0 - b.exp(-h * o['emissiveFalloff'])
            em = b.node('ShaderNodeEmission')
            em.inputs['Color'].default_value = (*[c * o['emissiveStrength'] for c in color(o['emissiveColor'])], 1)
            em.inputs['Strength'].default_value = 1.0
            mg = b.node('ShaderNodeMixShader')
            b.link(glow * min(o['emissiveStrength'], 1.0) * (1.0 - foam), mg.inputs['Fac'])
            nt.links.new(shader, mg.inputs[1])
            nt.links.new(em.outputs[0], mg.inputs[2])
            shader = mg.outputs[0]
        alpha = b.clamp(b.smoothstep(0.0, o['shoreFade'], h) + b.clamp(f, 0, 1) * 0.22)
        tr = b.node('ShaderNodeBsdfTransparent')
        m3 = b.node('ShaderNodeMixShader')
        b.link(alpha, m3.inputs['Fac'])
        nt.links.new(tr.outputs[0], m3.inputs[1])
        nt.links.new(shader, m3.inputs[2])
        nt.links.new(m3.outputs[0], out.inputs['Surface'])
        return mat

    def _terrain_material(self, bpy):
        from ._nodes import Builder
        EK = self.solver.EK
        mat = bpy.data.materials.new(self.name + '_terrain')
        mat.use_nodes = True
        nt = mat.node_tree
        bsdf = nt.nodes['Principled BSDF']
        bsdf.inputs['Roughness'].default_value = 0.95
        b = Builder(nt, x0=-1800, y0=600)

        def attr(nm):
            n = b.node('ShaderNodeAttribute', attribute_name=nm, attribute_type='GEOMETRY')
            return b.s(n.outputs['Fac'])

        dd, age, hW = attr('swe_delta'), attr('swe_age'), attr('swe_depth')
        maps = EK.get('terrainMaps') or {}
        uv = None
        if EK.get('terrainTexPeriod'):
            tc = b.node('ShaderNodeTexCoord')
            # the engine's (world x, -world z) / period is Blender's (world x, world y) / period
            uv = b.vscale(b.vec(tc.outputs['Object']) + tuple(self.center_b), 1.0 / EK['terrainTexPeriod'])
        else:
            uvn = b.node('ShaderNodeUVMap')
            uv = b.vscale(b.vec(uvn.outputs['UV']), float(EK['terrainRepeat']))

        def tex(path, data):
            n = b.node('ShaderNodeTexImage')
            n.image = path if hasattr(path, 'pixels') else bpy.data.images.load(path, check_existing=True)
            if data:
                n.image.colorspace_settings.is_data = True
            b.link(uv, n.inputs['Vector'])
            return n

        cut_c, silt_c = color(EK['cutColor']), color(EK['siltColor'])
        if maps.get('albedo'):
            base = b.vec(tex(maps['albedo'], False).outputs['Color'])
        else:
            base = b.vec(tuple(c * 1.35 for c in cut_c) + (1.0,))
        cut = b.smoothstep(0.015, 0.3, -dd)
        silt = b.max(b.smoothstep(0.06, 0.5, age), b.smoothstep(0.01, 0.2, dd))
        wet = b.smoothstep(0.0, 0.02, hW) * EK['wetDarken']
        col = b.rgb_mix(base, (*cut_c, 1), cut * 0.75)
        col = b.rgb_mix(col, (*silt_c, 1), silt * 0.8)
        col = b.vscale(col, 1.0 - wet)
        b.link(col, bsdf.inputs['Base Color'])
        if maps.get('rough'):
            b.link(tex(maps['rough'], True).outputs['Color'], bsdf.inputs['Roughness'])
        if maps.get('normal'):
            nm = b.node('ShaderNodeNormalMap')
            b.link(tex(maps['normal'], True).outputs['Color'], nm.inputs['Color'])
            nt.links.new(nm.outputs[0], bsdf.inputs['Normal'])
        return mat

    def _spray_material(self, bpy):
        # white-grey aerated water (never a clear liquid: spray reads white): a rough, partly translucent white
        mat = bpy.data.materials.new(self.name + '_spray')
        mat.use_nodes = True
        nt = mat.node_tree
        bsdf = nt.nodes['Principled BSDF']
        bsdf.inputs['Base Color'].default_value = (0.88, 0.92, 0.92, 1)    # the engine's grey-white albedo
        bsdf.inputs['Roughness'].default_value = 0.3
        bsdf.inputs['Transmission Weight'].default_value = 0.35
        bsdf.inputs['IOR'].default_value = 1.333
        return mat

    def _stream_material(self, bpy):
        from ._nodes import Builder
        o = self.o
        mat = bpy.data.materials.new(self.name + '_stream')
        mat.use_nodes = True
        mat.surface_render_method = 'DITHERED'
        mat.use_raytrace_refraction = True
        nt = mat.node_tree
        nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        out.location = (1200, 0)
        b = Builder(nt)

        def attr(nm, vec=False):
            n = b.node('ShaderNodeAttribute', attribute_name=nm, attribute_type='GEOMETRY')
            return b.vec(n.outputs['Vector']) if vec else b.s(n.outputs['Fac'])

        sx, s2, _ = attr('swe_suv', True).xyz()
        tL = b.max(attr('swe_tl'), 0.08)
        t = attr('swe_time')
        alpha = attr('swe_alpha')

        def vnoise(x, y):
            # value noise with Blender's own hash (White Noise) at the lattice corners and the engine's quintic
            # weights: the shape of fluid_swe.js's vnoise (its PCG hash needs integer ops shaders lack here)
            ix, iy = b.floor(x), b.floor(y)
            fx, fy = x - ix, y - iy
            ux = fx * fx * fx * (fx * (fx * 6.0 - 15.0) + 10.0)
            uy = fy * fy * fy * (fy * (fy * 6.0 - 15.0) + 10.0)

            def hc(ox, oy):
                n = b.node('ShaderNodeTexWhiteNoise', noise_dimensions='2D')
                b.link(b.combine(ix + ox, iy + oy, 0.0), n.inputs['Vector'])
                return b.s(n.outputs['Value'])

            a0 = b.mix(hc(0, 0), hc(1, 0), ux)
            a1 = b.mix(hc(0, 1), hc(1, 1), ux)
            return b.mix(a0, a1, uy)

        scroll = s2 - t / tL
        streak = (b.smoothstep(0.35, 0.85, vnoise(scroll * 16.0, sx * 2.0 + s2 * 1.5))
                  * b.smoothstep(0.06, 0.4, s2 * tL) * o['streamAeration'])
        nzE = vnoise(scroll * 18.0, sx * 2.0 + s2 * 1.5 + 5.3)
        erode = b.smoothstep(0.5, 0.95, s2) * b.smoothstep(0.3, 0.8, nzE) * (0.55 * o['streamAeration'])
        shallow, deep = color(o['shallowColor']), color(o['deepColor'])
        # glassy stream or white aerated streak, picked per shading sample like the surface's clear/body
        # (a glass/white Mix Shader is a refraction and a diffuse closure at once: a grain that never clears)
        geo = b.node('ShaderNodeNewGeometry')
        pick = b.node('ShaderNodeTexWhiteNoise', noise_dimensions='3D')
        nt.links.new(geo.outputs['Position'], pick.inputs['Vector'])
        glassy = b.math('GREATER_THAN', b.s(pick.outputs['Value']), streak * 0.85)    # 1 = glass
        P = b.node('ShaderNodeBsdfPrincipled')
        P.inputs['IOR'].default_value = 1.333
        glass_col = (*[1 - 0.35 * (1 - (s * 0.65 + d * 0.35)) for s, d in zip(shallow, deep)], 1)
        b.link(b.rgb_mix((*[c * 0.95 for c in color(o['foamColor'])], 1), glass_col, glassy), P.inputs['Base Color'])
        b.link(glassy, P.inputs['Transmission Weight'])
        b.link(0.5 - glassy * 0.46, P.inputs['Roughness'])                       # white 0.5, glass 0.04
        tr = b.node('ShaderNodeBsdfTransparent')
        m2 = b.node('ShaderNodeMixShader')
        b.link(b.clamp(alpha * (1.0 - erode) / 0.85), m2.inputs['Fac'])
        nt.links.new(tr.outputs[0], m2.inputs[1])
        nt.links.new(P.outputs[0], m2.inputs[2])
        nt.links.new(m2.outputs[0], out.inputs['Surface'])
        return mat


def create_water_swe(bed_fn, scene=None, preset='water', name='water_swe', cache_dir='//swe_cache',
                     precision='half', dry_sink=None, **options):
    """Build the shallow-water system. Options are fluid_swe.js's in snake_case (world_size, grid_size,
    domain_center, spray_max, rain_rate, erosion={...}, deep_color, ...); see SOLVER_DEFAULTS. Returns a
    WaterSWE; call .bake() before rendering. bed_fn(x, y) -> z in Blender world coordinates, vectorised over
    numpy arrays when it can be (a scalar function also works). dry_sink: metres the surface's dry vertices sit
    under the bed (default max(1 cm, a quarter cell)); raise it for distant shots, keep it under the wall
    thickness of a vessel the water fills."""
    import bpy
    if bed_fn is None:
        raise ValueError('[fx.swe] bed_fn(x, y) -> z is required')
    if preset not in LIQUID_PRESETS:
        raise ValueError(f'[fx.swe] unknown liquid preset "{preset}" - have: {", ".join(LIQUID_PRESETS)}')
    o = dict(SOLVER_DEFAULTS)
    o.update(LIQUID_PRESETS[preset])
    for k, v in options.items():
        ck = _camel(k)
        if ck not in SOLVER_DEFAULTS:
            raise TypeError(f'[fx.swe] unknown option {k}')
        if ck == 'erosion' and isinstance(v, dict):
            v = {_camel(a): b for a, b in v.items()}
            bad = set(v) - set(EROSION_DEFAULTS)
            if bad:
                raise TypeError('[fx.swe] unknown erosion options: ' + ', '.join(sorted(bad)))
        o[ck] = v
    o['preset'] = preset
    if abs(o['worldSize'][0] / o['gridSize'][0] - o['worldSize'][1] / o['gridSize'][1]) > 1e-6:
        print('[fx.swe] warning: non-square cells; the flux form assumes square cells')
    return WaterSWE(scene or bpy.context.scene, o, bed_fn, name, cache_dir, precision, dry_sink)
