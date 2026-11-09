"""create_sdf_object: an SDF solid as real EEVEE geometry (the Blender edition of createSdfObject).

    from eidoblend.sdf import create_sdf_object, EXAMPLES
    sdf = create_sdf_object(map=MAP_GLSL, surface=SURFACE_GLSL, bounds={'min': [-1, -1, -1], 'max': [1, 1, 1]},
                            quality='balanced', location=(2, 1, 0))
    sdf.object                      # the bpy Object: lit, shadowed, reflected, in the depth buffer like any mesh
    sdf.place_on_ground(0.0)        # the engine's mesh.position.y = groundY - bounds.min.y * scale, from the mesh
    sdf.bake(1, 96)                 # an animated SDF (uTime): one mesh per frame, played by Geometry Nodes

What happens: the GLSL map() is evaluated on the GPU over a sparse grid, dual-contoured into quads (mesher.py),
converted from the SDF's local three.js frame (y up) to Blender's (z up), and the example's surface() is baked
per texel (an atlas + object-space normal map) or per vertex. map() and the bounds stay in the engine's local
frame, so every GLSL original runs unchanged.
"""

from __future__ import annotations

import os

import numpy as np

from . import materials as M
from .gpu_eval import SdfProgram
from .mesher import drop_small_components, dual_contour, quad_corner_points
from .spec import SdfSpec, file_stem, resolve_cache_dir, sdf_collection

T2B = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], np.float32)    # three (x, y, z) -> Blender (x, -z, y)


def three_to_blender(v):
    v = np.asarray(v, np.float32)
    return v @ T2B.T


def _abspath(p):
    return resolve_cache_dir(p)


def _morton_order(points):
    """Indices sorting points along a Z-order curve (spatially coherent atlas blocks)."""
    p = np.asarray(points, np.float64)
    lo, hi = p.min(axis=0), p.max(axis=0)
    q = ((p - lo) / np.maximum(hi - lo, 1e-12) * 1023).astype(np.uint64)

    def spread(x):
        x = x & np.uint64(0x3FF)
        x = (x | (x << np.uint64(16))) & np.uint64(0x30000FF)
        x = (x | (x << np.uint64(8))) & np.uint64(0x300F00F)
        x = (x | (x << np.uint64(4))) & np.uint64(0x30C30C3)
        x = (x | (x << np.uint64(2))) & np.uint64(0x9249249)
        return x
    code = spread(q[:, 0]) | (spread(q[:, 1]) << np.uint64(1)) | (spread(q[:, 2]) << np.uint64(2))
    return np.argsort(code, kind='stable')


def write_exr(path, rgba, half=True):
    """(H, W, 4) float array, row 0 at the bottom (Blender order), to an EXR (OpenImageIO, bundled)."""
    import OpenImageIO as oiio
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = np.ascontiguousarray(np.asarray(rgba, np.float32)[::-1])
    h, w, c = data.shape
    spec = oiio.ImageSpec(w, h, c, 'half' if half else 'float')
    spec.channelnames = ('R', 'G', 'B', 'A')[:c]
    spec.attribute('compression', 'zip')
    out = oiio.ImageOutput.create(path)
    if out is None:
        raise RuntimeError('cannot write ' + path)
    tmp = path + '.tmp.exr'
    out.open(tmp, spec)
    out.write_image(data)
    out.close()
    os.replace(tmp, path)


def write_ply(path, verts, normals, faces, attrs, uvs=None):
    """Binary PLY: x y z nx ny nz [s t] <float attrs...> + polygon faces (all quads or a (F, k) array)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    n = len(verts)
    names = list(attrs)
    cols = [np.asarray(verts, np.float32), np.asarray(normals, np.float32)]
    hdr = ['ply', 'format binary_little_endian 1.0', f'element vertex {n}',
           'property float x', 'property float y', 'property float z',
           'property float nx', 'property float ny', 'property float nz']
    if uvs is not None:
        hdr += ['property float s', 'property float t']
        cols.append(np.asarray(uvs, np.float32))
    for k in names:
        hdr.append(f'property float {k}')
        cols.append(np.asarray(attrs[k], np.float32).reshape(n, 1))
    faces = np.asarray(faces, np.int32)
    hdr += [f'element face {len(faces)}', 'property list uchar int vertex_indices', 'end_header']
    vb = np.ascontiguousarray(np.concatenate(cols, axis=1).astype('<f4'))
    fk = faces.shape[1]
    fb = np.empty((len(faces), 1 + 4 * fk), np.uint8)
    fb[:, 0] = fk
    fb[:, 1:] = np.ascontiguousarray(faces.astype('<i4')).view(np.uint8).reshape(len(faces), 4 * fk)
    tmp = path + '.tmp'
    with open(tmp, 'wb') as fh:
        fh.write(('\n'.join(hdr) + '\n').encode('ascii'))
        fh.write(vb.tobytes())
        fh.write(fb.tobytes())
    os.replace(tmp, path)


class SdfObject:
    """What create_sdf_object returns. .object is the Blender object; .program the compiled GLSL (or Python)
    SDF; .spec its settings; .contour / .stats the last mesh build; .images the atlas images."""

    def __init__(self, spec: SdfSpec, scene=None, collection=None, name=None, location=(0, 0, 0),
                 rotation=(0, 0, 0), scale=1.0):
        import bpy
        self.spec = spec
        self.scene = scene or bpy.context.scene
        self.name = name or spec.name or 'sdf'
        self.program = SdfProgram(map=spec.map, surface=spec.surface, shade=spec.shade, extra=spec.extra,
                                  uniforms=spec.uniforms, textures=spec.textures, defines=spec.defines,
                                  label=self.name, shade_as=spec.shade_as)
        self.program.values['sdfUseClip'] = 1.0
        self.program.values['sdfIso'] = float(spec.iso)
        self.voxel = spec.voxel_size()
        pad = 2.0 * self.voxel
        self.clip_min = np.asarray(spec.bounds_min, np.float64) - pad
        self.clip_max = np.asarray(spec.bounds_max, np.float64) + pad
        self.program.values['sdfClipMin'] = tuple(float(x) for x in self.clip_min)
        self.program.values['sdfClipMax'] = tuple(float(x) for x in self.clip_max)
        self.contour = None
        self.stats = {}
        self.images = {}
        self.material = None
        self.materials_by_id = dict(spec.materials or {})
        me = bpy.data.meshes.new(self.name)
        self.object = bpy.data.objects.new(self.name, me)
        coll = collection or sdf_collection(self.scene)
        coll.objects.link(self.object)
        self.object.location = tuple(location)
        self.object.rotation_euler = tuple(rotation)
        s = scale if isinstance(scale, (tuple, list)) else (scale, scale, scale)
        self.object.scale = tuple(s)
        self.object['sdf_example'] = spec.name or ''
        self.object['sdf_bounds_min'] = list(spec.bounds_min)
        self.object['sdf_bounds_max'] = list(spec.bounds_max)
        self.object['sdf_voxel'] = self.voxel
        self.cache_dir = _abspath(spec.cache_dir)
        # the cache files are named for the object, which Blender keeps unique: a second EXAMPLES['x'].make() is
        # 'x.001' and writes its own atlases and frames instead of over the first one's
        self.stem = file_stem(self.object.name)
        from .helper import track
        track(self)

    # ---------------------------------------------------------------------------------------- uniforms -------
    def set_uniform(self, name, value):
        """A live uniform (the engine's material.uniforms.X.value = v / make({paintColor})): the next build or
        baked frame uses it."""
        self.program.set_uniform(name, value)
        return self

    @property
    def uniforms(self):
        return dict(self.program.values)

    # ---------------------------------------------------------------------------------------- building -------
    def _contour(self, log=print):
        prog = self.program
        lo = self.clip_min - self.voxel
        hi = self.clip_max + self.voxel
        c = dual_contour(lambda p: prog.dist(p)[0], lambda p, h: prog.grad(p, h)[2], lo, hi, self.voxel,
                         brick=self.spec.brick, lipschitz=self.spec.lipschitz(), iso=self.spec.iso,
                         refine=self.spec.refine, qef_lambda=self.spec.qef_lambda, log=log)
        if self.spec.min_component and len(c.quads):
            c = drop_small_components(c, int(self.spec.min_component))
        self.contour = c
        self.stats.update(c.stats)
        return c

    def _corner_normals(self, c, chunk=1 << 20):
        """Crease-keeping normals, one per quad corner (the field's gradient just inside each corner), in Blender
        axes as float32 (4 Q, 3). Evaluated a million quads at a time into one array: a mesh of fifteen million quads
        (the Menger sponge at 'high') would otherwise hold about 400 bytes of temporaries a quad, 6 GB."""
        h = max(0.0004, 0.25 * self.voxel)
        Q = len(c.quads)
        out = np.empty((Q * 4, 3), np.float32)
        for s in range(0, Q, chunk):
            e = min(Q, s + chunk)
            pts = quad_corner_points(c.verts, c.quads[s:e], 0.3).reshape(-1, 3)
            g = self.program.grad(pts, h)[2]
            del pts
            out[s * 4:e * 4] = three_to_blender(g / np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-20))
        return out

    def _normals_at(self, points, h, chunk=1 << 22):
        """Unit gradients at points (the SDF's frame, float32), four million at a time."""
        out = np.empty((len(points), 3), np.float32)
        for s in range(0, len(points), chunk):
            g = self.program.grad(points[s:s + chunk], h)[2]
            out[s:s + chunk] = g / np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-20)
        return out

    def _vertex_normals(self, c):
        return self._normals_at(c.verts, max(0.0004, 0.5 * self.voxel))

    def _surface_at(self, pts, texel):
        """Surface channels at points: projected onto the zero set (2 Newton steps), normal at the storage
        resolution (the engine's 0.0004 at the finest)."""
        return self.program.surface_eval(pts, project=2, grad_h=max(0.0002, 0.25 * texel),
                                         normal_h=max(0.0002, 0.5 * texel))

    def build(self, t=None, log=print):
        """Mesh the SDF at time t (seconds; None keeps uTime) into the object, with its baked material."""
        import bpy
        if t is not None:
            self.program.values['uTime'] = float(t)
        c = self._contour(log)
        if len(c.quads) == 0:
            # nothing to show (the explosion's radius collapses for part of its cycle): the object empties, as the
            # engine's march drew nothing; the last surface must not stay on screen
            print(f'[sdf] {self.name}: no surface inside the bounds at t={self.program.values["uTime"]}')
            old = self.object.data
            me = bpy.data.meshes.new(self.name)
            for mat in old.materials:
                me.materials.append(mat)
            self.object.data = me
            if old.users == 0:
                bpy.data.meshes.remove(old)
            self.stats['carrier'] = None
            return self
        carrier = self.spec.carrier
        if carrier == 'atlas' and not self.atlas_fits(len(c.quads)):
            # even 2 x 2 texels a quad would pass the budget: a mesh this dense carries its detail in its vertices
            # (an atlas of it held 300 MB EXRs and as much VRAM), so its channels go on the vertices
            if log:
                log(f'[sdf] {self.name}: {len(c.quads)} quads pass the atlas budget even at 2 texels a side: '
                    f'surface channels per vertex')
            carrier = 'vertex'
        if carrier == 'atlas':
            me = self._mesh_atlas(c, log)
        else:
            me = self._mesh_vertex(c, log)
        old = self.object.data
        self.object.data = me
        if old.users == 0:
            bpy.data.meshes.remove(old)
        self._assign_id_materials(me, c)
        self.stats['carrier'] = carrier
        return self

    def _new_mesh(self, verts_b, quads):
        import bpy
        me = bpy.data.meshes.new(self.name)
        nv, nf = len(verts_b), len(quads)
        me.vertices.add(nv)
        me.vertices.foreach_set('co', np.ascontiguousarray(verts_b, np.float32).ravel())
        me.loops.add(nf * 4)
        me.loops.foreach_set('vertex_index', np.ascontiguousarray(quads, np.int32).ravel())
        me.polygons.add(nf)
        me.polygons.foreach_set('loop_start', np.arange(0, nf * 4, 4, dtype=np.int32))
        me.update(calc_edges=True)
        me.polygons.foreach_set('use_smooth', np.ones(nf, bool))
        return me

    @staticmethod
    def set_custom_normals(me, normals, domain='CORNER'):
        """Free custom normals (Blender 5.x): a FLOAT_VECTOR attribute named custom_normal on the corner or point
        domain, filled straight from numpy (normals_split_custom_set needs a Python list: 4 s per 4 M corners)."""
        if 'custom_normal' in me.attributes:
            me.attributes.remove(me.attributes['custom_normal'])
        at = me.attributes.new('custom_normal', 'FLOAT_VECTOR', domain)
        at.data.foreach_set('vector', np.ascontiguousarray(normals, np.float32).ravel())

    def _set_corner_normals(self, me, c):
        self.set_custom_normals(me, self._corner_normals(c), 'CORNER')

    def _mesh_vertex(self, c, log):
        verts_b = three_to_blender(c.verts)
        me = self._new_mesh(verts_b, c.quads)
        ch = self._surface_at(c.verts, self.voxel)
        const = M.constant_channels(ch)
        for name, width, _inp, _d in M.CHANNELS:
            if name in const:
                continue
            a = np.asarray(ch[name], np.float32)
            if width == 3:
                at = me.attributes.new('sdf_' + name, 'FLOAT_COLOR', 'POINT')
                rgba = np.concatenate([a, np.ones((len(a), 1), np.float32)], 1)
                at.data.foreach_set('color', rgba.ravel())
            else:
                at = me.attributes.new('sdf_' + name, 'FLOAT', 'POINT')
                at.data.foreach_set('value', a.ravel())
        me.attributes.new('sdf_mat', 'FLOAT', 'POINT').data.foreach_set('value', ch['mat'].astype(np.float32))
        if self.spec.normals == 'corner':
            self._set_corner_normals(me, c)
        else:
            self.set_custom_normals(me, three_to_blender(self._vertex_normals(c)), 'POINT')
        mat = M.vertex_material(self.name + '_surface', const, self.spec.material_settings)
        me.materials.append(mat)
        self.material = mat
        self.stats['constants'] = sorted(const)
        return me

    ATLAS_GUTTER = 1

    @staticmethod
    def atlas_blocks(slot):
        """Block (column, row) of each atlas slot along a 2D Z-order curve. Slots are the quads' 3D Morton ranks,
        so blocks that touch in the atlas, across a row as well as along it, hold quads that touch on the surface:
        when the GPU's mipmaps blend neighbouring blocks, they blend neighbouring surface."""
        s = np.asarray(slot, np.uint64)

        def compact(x):
            x = x & np.uint64(0x5555555555555555)
            x = (x | (x >> np.uint64(1))) & np.uint64(0x3333333333333333)
            x = (x | (x >> np.uint64(2))) & np.uint64(0x0F0F0F0F0F0F0F0F)
            x = (x | (x >> np.uint64(4))) & np.uint64(0x00FF00FF00FF00FF)
            x = (x | (x >> np.uint64(8))) & np.uint64(0x0000FFFF0000FFFF)
            x = (x | (x >> np.uint64(16))) & np.uint64(0x00000000FFFFFFFF)
            return x.astype(np.int64)
        return compact(s), compact(s >> np.uint64(1))

    def _atlas_points(self, c, k):
        """Texel points (Q, k, k, 3) of every quad (bilinear over its corners) in Morton slot order."""
        v = c.verts[c.quads].astype(np.float64)                    # (Q, 4, 3)
        u = np.linspace(0.0, 1.0, k)
        U, V = np.meshgrid(u, u, indexing='xy')                    # [j][i]
        w0 = ((1 - U) * (1 - V))[None, :, :, None]
        w1 = (U * (1 - V))[None, :, :, None]
        w2 = (U * V)[None, :, :, None]
        w3 = ((1 - U) * V)[None, :, :, None]
        return (w0 * v[:, None, None, 0] + w1 * v[:, None, None, 1] + w2 * v[:, None, None, 2]
                + w3 * v[:, None, None, 3])

    def atlas_texels(self, quads):
        """Texels per quad side: the spec's (quality preset's), lowered until quads * k^2 fits atlas_budget. A mesh
        that large already carries its detail in geometry, and EEVEE holds each atlas image in VRAM (half float
        RGBA: 8 bytes a texel)."""
        k = int(self.spec.texels)
        g2 = 2 * self.ATLAS_GUTTER
        while k > 2 and quads * (k + g2) ** 2 > int(self.spec.atlas_budget):
            k -= 1
        return k

    def atlas_fits(self, quads):
        """Whether an atlas of `quads` blocks fits atlas_budget at its smallest (2 x 2 texels and the gutter)."""
        return quads * (2 + 2 * self.ATLAS_GUTTER) ** 2 <= int(self.spec.atlas_budget)

    def _atlas_bake(self, c, k, frame=None, log=print, keys=None):
        """Bake the atlas images for contour c: returns (uvs per loop (4Q, 2), {key: path}, constants, mats). A
        pack whose channels are all constant is not written, unless `keys` names the packs to write (an atlas
        sequence writes every frame the packs its first frame needed, so each image sequence is complete)."""
        Q = len(c.quads)
        k = self.atlas_texels(Q) if k is None else k
        order = _morton_order(c.verts[c.quads].mean(axis=1))
        slot = np.empty(Q, np.int64)
        slot[order] = np.arange(Q)
        g = self.ATLAS_GUTTER
        s = k + 2 * g                                              # block side: k texels and a gutter ring
        col, row = self.atlas_blocks(slot)
        W, H = int(col.max() + 1) * s, int(row.max() + 1) * s
        texel = self.voxel / max(1, k - 1)
        pts = self._atlas_points(c, k)                             # (Q, k, k, 3), quads in mesh order
        ch = self._surface_at(pts.reshape(-1, 3), texel)
        const = M.constant_channels(ch)
        bx, by = col * s, row * s
        # every texel of every block, gutter included, and the interior texel it shows: the gutter repeats the
        # block's edge, so mip level 1 (and the bilinear filter at level 0) never reads another quad's texels
        full = np.arange(s)
        inner = np.clip(full - g, 0, k - 1)
        fi, fj = np.meshgrid(full, full, indexing='xy')            # [j][i]
        ci, cj = np.meshgrid(inner, inner, indexing='xy')
        X = (bx[:, None, None] + fi[None]).ravel()
        Y = (by[:, None, None] + fj[None]).ravel()
        SRC = (np.arange(Q)[:, None, None] * (k * k) + (cj * k + ci)[None]).ravel()
        paths = {}
        tag = self.stem if frame is None else f'{self.stem}_{frame:04d}'
        for key, layout in M.ATLAS_PACK.items():
            if (key not in keys) if keys is not None else all(name in const for name, _w in layout):
                continue
            img = np.zeros((H, W, 4), np.float32)
            comp = 0
            for name, w in layout:
                a = np.asarray(ch[name], np.float32).reshape(-1, w)
                img[Y, X, comp:comp + w] = a[SRC]
                comp += w
            p = os.path.join(self.cache_dir, f'{tag}_{key}.exr')
            write_exr(p, img)
            paths[key] = p
        nrm = three_to_blender(ch['normal'])
        img = np.zeros((H, W, 4), np.float32)
        img[..., 3] = 1.0
        img[Y, X, :3] = nrm[SRC] * 0.5 + 0.5
        p = os.path.join(self.cache_dir, f'{tag}_normal.exr')
        write_exr(p, img)
        paths['normal'] = p
        # per-loop UVs at the corner texel centres of each block's interior
        cu = np.array([g + 0.5, g + k - 0.5, g + k - 0.5, g + 0.5])
        cv = np.array([g + 0.5, g + 0.5, g + k - 0.5, g + k - 0.5])
        uvs = np.empty((Q, 4, 2), np.float32)
        uvs[:, :, 0] = (bx[:, None] + cu[None]) / W
        uvs[:, :, 1] = (by[:, None] + cv[None]) / H
        mats = ch['mat'].reshape(Q, k * k)
        self.stats.update(atlas=(W, H), texels=k, texel_mm=round(texel * 1000, 3))
        return uvs.reshape(-1, 2), paths, const, mats

    def _mesh_atlas(self, c, log):
        import bpy
        uvs, paths, const, _mats = self._atlas_bake(c, None, log=log)
        verts_b = three_to_blender(c.verts)
        me = self._new_mesh(verts_b, c.quads)
        uvl = me.uv_layers.new(name='UVMap')
        uvl.data.foreach_set('uv', uvs.ravel())
        if self.spec.normals == 'corner':
            self._set_corner_normals(me, c)
        else:
            self.set_custom_normals(me, three_to_blender(self._vertex_normals(c)), 'POINT')
        for img in self.images.values():
            if img is not None and img.users == 0:
                bpy.data.images.remove(img)
        self.images = {}
        for key, p in paths.items():
            self.images[key] = M.load_atlas_image(p, f'{self.name}_{key}')
        mat = M.atlas_material(self.name + '_surface', {k_: v for k_, v in self.images.items() if k_ != 'normal'},
                               const, self.spec.material_settings, normal_image=self.images.get('normal'))
        me.materials.append(mat)
        self.material = mat
        self.stats['constants'] = sorted(const)
        if self.spec.pack_images:
            for img in self.images.values():
                img.pack()
        return me

    def _assign_id_materials(self, me, c):
        """materials={mat_id: bpy Material}: faces whose material id (at the face centre) matches get it."""
        if not self.materials_by_id:
            return
        cent = c.verts[c.quads].mean(axis=1)
        _d, mid = self.program.dist(cent)
        ids = np.rint(mid).astype(np.int64)
        idx = np.zeros(len(ids), np.int32)
        for mat_id, mat in self.materials_by_id.items():
            me.materials.append(mat)
            idx[ids == int(round(mat_id))] = len(me.materials) - 1
        me.polygons.foreach_set('material_index', idx)

    # ------------------------------------------------------------------------------------------ animation ----
    def bake(self, frame_start=None, frame_end=None, step=1, time_scale=1.0, time_offset=0.0, controls=None,
             carrier=None, log=print):
        """Re-mesh the SDF once per frame (uTime = time_offset + time_scale * (frame - frame_start) / fps) into
        <cache_dir>/<stem>_####.ply (the stem is the object's name) and play the sequence with a Geometry Nodes
        Import PLY on the object; the surface channels travel as PLY vertex properties ('vertex', default) or as a
        per-frame atlas image sequence ('atlas'). controls(frame, t) -> {uniform: value} keys uniforms per frame.
        A frame with no surface inside the bounds is an empty mesh."""
        import bpy
        sc = self.scene
        fs = sc.frame_start if frame_start is None else int(frame_start)
        fe = sc.frame_end if frame_end is None else int(frame_end)
        fps = sc.render.fps / sc.render.fps_base
        carrier = carrier or ('vertex' if self.spec.carrier != 'atlas_sequence' else 'atlas')
        os.makedirs(self.cache_dir, exist_ok=True)
        import shutil
        k = self.spec.texels
        step = max(1, int(step))
        last = None
        seq_keys, seq_const = None, {}
        decided = False              # the atlas budget is judged on the first frame that has a surface
        atlas_frames = []            # frames whose atlas images this bake wrote (or held)
        empty_frames = 0
        n = len(self.stem)
        for f in range(fs, fe + 1):
            if (f - fs) % step and last is not None:
                # held frame: the last computed frame's files under this frame's number
                for src in last:
                    # <stem>_<frame>.ply / <stem>_<frame>_<key>.exr: swap the frame right after the stem
                    d, b = os.path.split(src)
                    shutil.copyfile(src, os.path.join(d, f'{b[:n]}_{f:04d}{b[n + 5:]}'))
                if len(last) > 1:
                    atlas_frames.append(f)
                continue
            t = time_offset + time_scale * (f - fs) / fps
            self.program.values['uTime'] = float(t)
            if controls:
                for name, v in (controls(f, t) or {}).items():
                    self.program.set_uniform(name, v)
            c = self._contour(log=None)
            ply = os.path.join(self.cache_dir, f'{self.stem}_{f:04d}.ply')
            last = [ply]
            if len(c.quads) == 0:
                # no surface this frame (the explosion's radius collapses through zero for part of its cycle): an
                # empty mesh, as the engine's march drew nothing
                write_ply(ply, np.zeros((0, 3), np.float32), np.zeros((0, 3), np.float32), np.zeros((0, 4), np.int32),
                          {}, uvs=np.zeros((0, 2), np.float32) if carrier == 'atlas' else None)
                empty_frames += 1
                if log:
                    log(f'[sdf] {self.name}: frame {f} t={t:.3f}s no surface')
                continue
            if carrier == 'atlas' and not decided and not self.atlas_fits(len(c.quads)):
                if log:
                    log(f'[sdf] {self.name}: {len(c.quads)} quads pass the atlas budget: the sequence carries its '
                        f'channels per vertex')
                carrier = 'vertex'
            decided = True
            if carrier == 'atlas':
                k = self.atlas_texels(len(c.quads))
                # the first frame with a surface decides which packs the sequence carries; its constant channels
                # become the material's values (a pack left out would leave its BSDF inputs at the defaults: the
                # Principled default Emission Color is white, so a missing 'emit' pack made the whole object glow)
                uvs, paths, const, _m = self._atlas_bake(c, k, frame=f, keys=seq_keys)
                if seq_keys is None:
                    seq_keys = {key for key in paths if key != 'normal'}
                    seq_const = const
                # one vertex per loop so the per-corner UVs survive PLY (custom normals keep them smooth)
                verts = c.verts[c.quads].reshape(-1, 3)
                faces = np.arange(len(verts), dtype=np.int32).reshape(-1, 4)
                nrm = self._normals_at(verts, max(0.0004, 0.5 * self.voxel))
                write_ply(ply, three_to_blender(verts), three_to_blender(nrm), faces, {}, uvs=uvs)
                last += list(paths.values())
                atlas_frames.append(f)
            else:
                ch = self._surface_at(c.verts, self.voxel)
                nrm = self._vertex_normals(c)
                attrs = {}
                for name, width, _inp, _d in M.CHANNELS:
                    a = np.asarray(ch[name], np.float32).reshape(len(c.verts), -1)
                    if width == 3:
                        for i, comp in enumerate('rgb'):
                            attrs[f'sdf_{name}_{comp}'] = a[:, i]
                    else:
                        attrs[f'sdf_{name}'] = a[:, 0]
                attrs['sdf_mat'] = ch['mat']
                write_ply(ply, three_to_blender(c.verts), three_to_blender(nrm), c.quads, attrs)
            if log:
                log(f'[sdf] {self.name}: frame {f} t={t:.3f}s {len(c.quads)} quads')
        keys = []
        if carrier == 'atlas' and atlas_frames:
            keys = sorted(seq_keys) + ['normal']
            # every frame of an image sequence needs its file: an empty frame (no surface, so its images never
            # show) takes the nearest atlas frame's, the one before it when there is one
            have = set(atlas_frames)
            for f in range(fs, fe + 1):
                if f in have:
                    continue
                before = [g for g in atlas_frames if g < f]
                src_f = before[-1] if before else atlas_frames[0]
                for key in keys:
                    shutil.copyfile(os.path.join(self.cache_dir, f'{self.stem}_{src_f:04d}_{key}.exr'),
                                    os.path.join(self.cache_dir, f'{self.stem}_{f:04d}_{key}.exr'))
            # an image sequence shows file <first - 1> before its range: hold the first frame there
            for key in keys:
                shutil.copyfile(os.path.join(self.cache_dir, f'{self.stem}_{fs:04d}_{key}.exr'),
                                os.path.join(self.cache_dir, f'{self.stem}_{fs - 1:04d}_{key}.exr'))
        self._player(bpy, carrier, fs, fe, k, constants=seq_const, keys=keys)
        self.stats.update(baked=(fs, fe), carrier=carrier, empty_frames=empty_frames)
        return self

    def _player(self, bpy, carrier, fs, fe, k, constants=None, keys=()):
        """GN tree: Import PLY of the current frame's file, colour channels recombined, shaded smooth."""
        tree = bpy.data.node_groups.new(self.name + '.player', 'GeometryNodeTree')
        tree.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
        tree.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
        N, L = tree.nodes, tree.links
        gi = N.new('NodeGroupInput')
        go = N.new('NodeGroupOutput')
        tm = N.new('GeometryNodeInputSceneTime')
        vts = N.new('FunctionNodeValueToString')
        vts.data_type = 'INT'
        vts.inputs['Padding'].default_value = 4
        clampn = N.new('ShaderNodeClamp')
        clampn.inputs['Min'].default_value = fs
        clampn.inputs['Max'].default_value = fe
        L.new(tm.outputs['Frame'], clampn.inputs['Value'])
        L.new(clampn.outputs['Result'], vts.inputs['Value'])
        join = N.new('GeometryNodeStringJoin')
        a = N.new('FunctionNodeInputString')
        a.string = os.path.join(self.cache_dir, self.stem + '_')
        b = N.new('FunctionNodeInputString')
        b.string = '.ply'
        # Join Strings concatenates its multi-input links in reverse creation order (5.2): suffix first
        L.new(b.outputs[0], join.inputs['Strings'])
        L.new(vts.outputs[0], join.inputs['Strings'])
        L.new(a.outputs[0], join.inputs['Strings'])
        imp = N.new('GeometryNodeImportPLY')
        L.new(join.outputs[0], imp.inputs['Path'])
        geo = imp.outputs[0]
        if carrier == 'vertex':
            for name, width, _inp, _d in M.CHANNELS:
                if width != 3:
                    continue
                comb = N.new('ShaderNodeCombineXYZ')
                for i, comp in enumerate('rgb'):
                    na = N.new('GeometryNodeInputNamedAttribute')
                    na.data_type = 'FLOAT'
                    na.inputs['Name'].default_value = f'sdf_{name}_{comp}'
                    L.new(na.outputs['Attribute'], comb.inputs['XYZ'[i]])
                st = N.new('GeometryNodeStoreNamedAttribute')
                st.data_type = 'FLOAT_COLOR'
                st.domain = 'POINT'
                st.inputs['Name'].default_value = f'sdf_{name}'
                L.new(geo, st.inputs['Geometry'])
                L.new(comb.outputs['Vector'], st.inputs['Value'])
                geo = st.outputs['Geometry']
        sm = N.new('GeometryNodeSetShadeSmooth')
        L.new(geo, sm.inputs['Geometry'])
        geo = sm.outputs[0]
        if carrier == 'vertex':
            mat = M.vertex_material(self.name + '_surface', {}, self.spec.material_settings)
        else:
            images = {}
            for key in keys:
                # the packs this bake wrote (a file left by an earlier bake of another layout is not one of them)
                first = os.path.join(self.cache_dir, f'{self.stem}_{fs:04d}_{key}.exr')
                images[key] = M.load_atlas_image(first, f'{self.name}_{key}_seq', sequence=(fs, fe - fs + 1))
            mat = M.atlas_material(self.name + '_surface', {k_: v for k_, v in images.items() if k_ != 'normal'},
                                   dict(constants or {}), self.spec.material_settings,
                                   normal_image=images.get('normal'))
            for node in mat.node_tree.nodes:
                if node.type == 'TEX_IMAGE':
                    iu = node.image_user
                    iu.frame_duration = fe - fs + 1
                    iu.frame_start = fs
                    iu.frame_offset = fs - 1
                    iu.use_auto_refresh = True
                    iu.use_cyclic = False
            self.images = images
        setm = N.new('GeometryNodeSetMaterial')
        setm.inputs['Material'].default_value = mat
        L.new(geo, setm.inputs['Geometry'])
        L.new(setm.outputs[0], go.inputs[0])
        mod = self.object.modifiers.get('sdf_player') or self.object.modifiers.new('sdf_player', 'NODES')
        mod.node_group = tree
        self.material = mat
        self.player = tree

    # ------------------------------------------------------------------------------------------ placement ----
    def place_on_ground(self, ground_z=0.0, from_mesh=True):
        """Seat the object on a ground plane at ground_z. The engine's rule was position.y = groundY -
        bounds.min.y * scale; with a real mesh the lowest vertex is known, so it is used (from_mesh=True)."""
        import bpy
        self.object.location.z = 0.0
        bpy.context.view_layer.update()
        me = self.object.data
        if from_mesh and len(me.vertices):
            co = np.empty(len(me.vertices) * 3, np.float32)
            me.vertices.foreach_get('co', co)
            mw = np.array(self.object.matrix_world, np.float64)
            zs = co.reshape(-1, 3).astype(np.float64) @ mw[2, :3] + mw[2, 3]
            self.object.location.z = ground_z - float(zs.min())
        else:
            self.object.location.z = ground_z - self.spec.bounds_min[1] * self.object.scale.z
        return self

    def bounds_report(self):
        """How tight the declared bounds are: the mesh's extent in the SDF's local frame against bounds, and
        whether the surface reached the clip box (geometry the bounds cut off)."""
        c = self.contour
        if c is None or len(c.verts) == 0:
            return {}
        lo, hi = c.verts.min(axis=0), c.verts.max(axis=0)
        bmin, bmax = np.asarray(self.spec.bounds_min), np.asarray(self.spec.bounds_max)
        clipped = bool((lo < bmin - 0.5 * self.voxel).any() or (hi > bmax + 0.5 * self.voxel).any())
        return {'mesh_min': lo.round(4).tolist(), 'mesh_max': hi.round(4).tolist(), 'bounds_min': bmin.tolist(),
                'bounds_max': bmax.tolist(), 'clipped': clipped,
                'gap_min': (lo - bmin).round(4).tolist(), 'gap_max': (bmax - hi).round(4).tolist()}

    # ------------------------------------------------------------------------------------------ reference ----
    def raymarch_reference(self, camera, width=480, height=270, samples=4, t=None):
        """The engine's own raymarch of this SDF (its quality preset, its shade()) seen from a Blender camera: a
        linear float image (H, W, 4), row 0 at the bottom. The original look, to judge the EEVEE port against."""
        from .reference import raymarch_image
        if t is not None:
            self.program.values['uTime'] = float(t)
        return raymarch_image(self, camera, width, height, samples)


def create_sdf_object(spec=None, **kwargs):
    """The engine's createSdfObject(spec): spec is a dict (or an EXAMPLES entry) with map / surface / shade /
    extra / bounds / quality / uniforms ..., and keyword arguments override it. Builds the mesh now (build=False
    to skip) at t = `time` seconds. See SdfSpec for every option."""
    opts = dict(spec.as_dict() if hasattr(spec, 'as_dict') else (spec or {}))
    opts.update(kwargs)
    build = opts.pop('build', True)
    t = opts.pop('time', None)
    scene = opts.pop('scene', None)
    collection = opts.pop('collection', None)
    name = opts.pop('name', None)
    location = opts.pop('location', (0, 0, 0))
    rotation = opts.pop('rotation', (0, 0, 0))
    scale = opts.pop('scale', 1.0)
    log = opts.pop('log', print)
    sp = SdfSpec.from_options(opts)
    obj = SdfObject(sp, scene=scene, collection=collection, name=name or sp.name, location=location,
                    rotation=rotation, scale=scale)
    if build and sp.map is not None:
        obj.build(t=t if t is not None else sp.time, log=log)
    return obj
