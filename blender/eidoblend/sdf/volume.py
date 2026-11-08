"""create_sdf_volume: a participating-medium SDF as a real Blender Volume (the Blender edition of createSdfVolume).

The engine raymarched each volume inside its bounds box: front-to-back premultiplied accumulation of a sample(p)
returning {color, alpha, step}, an optional post(sum), transparent, camera kept outside the box, re-sorted per frame
against other volumes. In EEVEE a volume has to be a Volume object to sit in the scene: lit by the scene's lights,
shadowed, mixed with fog and other volumes, any camera position. So the sample function is evaluated on the GPU at
the voxel centres of a grid over the bounds, the grids are written as OpenVDB, and a Volume object plays them (one
.vdb per frame when animated) through a Principled Volume.

Two contracts, both GLSL in the engine's local frame (y up), with the primitive library and the example's extra:

  sample  SdfSample sample(vec3 p): the engine's {color, alpha, step}. Converted exactly: the engine composited
          `a = alpha` over a stride `step`, which is the transmittance of an absorbing medium of extinction
          density = -ln(1 - alpha) / step, emitting color * density per metre (no scattering: the engine's colour
          was already lit). The volume then integrates the same light along any ray EEVEE marches.
          sample_as='albedo' reads the colour as the medium's scattering colour instead (no emission): a smoke
          whose engine colour was a hand-lit grey then takes the scene's light and shadow.
  medium  SdfMedium medium(vec3 p): the Blender-native form: density (extinction per metre), albedo (scattering
          colour, lit by the scene), emission (radiance per metre), temperature (blackbody kelvin, 0 = none).

Either may be a Python function over numpy points instead (see SdfVolume._eval_stage), as the engine's TSL stages
were JavaScript functions; it reads S.time and S.uniform() like a Python SDF solid.

    from eidoblend.sdf import create_sdf_volume
    vol = create_sdf_volume(sample=GLSL, bounds={'min': [-1, 0, -1], 'max': [1, 2, 1]}, cells=160,
                            location=(0, 0, 0), cache_dir='//vol_cache')
    vol.bake(1, 120)                       # animated (uTime): one .vdb per frame
    img = vol.raymarch_reference(camera)   # the engine's own march of the same sample(), for comparison

post(sum) reshaped the composited pixel (a contrast curve, an alpha remap). A physical volume has no composited
pixel to reshape, so post runs in the reference march only; a volume example folds what its post did into its
colours and densities, or applies it in the compositor.
"""

from __future__ import annotations

import os

import numpy as np

from .gpu_eval import SdfProgram
from .spec import _bounds, sdf_collection

VOLUME_QUALITY = {'fast': 96, 'balanced': 160, 'high': 256, 'ultra': 384}

GRID_NAMES = ('density', 'emission', 'albedo', 'temperature')

DEFAULT_VOLUME_SETTINGS = {
    'density_scale': 1.0,       # multiplies the density grid in the material
    'emission_scale': 1.0,      # Emission Strength over the emission grid
    'albedo': None,             # a constant scattering colour when the contract gives none (sample: black)
    'anisotropy': 0.0,
    'blackbody_intensity': 1.0,
    'blackbody_tint': (1.0, 1.0, 1.0),
}


class SdfVolumeSpec:
    """Every option of create_sdf_volume."""

    FIELDS = dict(
        name=None, sample=None, medium=None, post=None, extra='', bounds=None, steps=96, uniforms=None,
        textures=None, defines=None, voxel=None, cells=None, quality='balanced', cache_dir='//sdf_cache',
        time=0.0, animated=False, material_settings=None, alpha_clamp=0.9999, prune=1e-6, sequence_mode='EXTEND',
        sample_as='emission',
    )

    def __init__(self, **kw):
        for k, v in self.FIELDS.items():
            setattr(self, k, kw.get(k, v))
        unknown = set(kw) - set(self.FIELDS)
        if unknown:
            raise TypeError(f'create_sdf_volume: unknown options {sorted(unknown)}')
        if self.sample is None and self.medium is None:
            raise ValueError('create_sdf_volume: spec.sample (the engine contract) or spec.medium is required')
        self.bounds_min, self.bounds_max = _bounds(self.bounds)
        if self.quality not in VOLUME_QUALITY:
            self.quality = 'balanced'
        if self.sample_as not in ('emission', 'albedo'):
            raise ValueError(f"create_sdf_volume: sample_as is 'emission' or 'albedo', not {self.sample_as!r}")

    @classmethod
    def from_options(cls, opts):
        kw = {}
        for k, v in opts.items():
            if k in ('kind', 'make', 'description', 'map', 'shade', 'surface', 'reference_image'):
                continue
            kw[k] = v
        return cls(**kw)

    def voxel_size(self):
        if self.voxel:
            return float(self.voxel)
        cells = self.cells or VOLUME_QUALITY[self.quality]
        ext = max(b - a for a, b in zip(self.bounds_min, self.bounds_max))
        return ext / float(cells)

    def as_dict(self):
        d = {k: getattr(self, k) for k in self.FIELDS}
        d['bounds'] = {'min': list(self.bounds_min), 'max': list(self.bounds_max)}
        return d


def blender_box(bmin3, bmax3):
    """The bounds box (three local, y up) in Blender local axes (x, -z, y): (lo, hi)."""
    lo = np.array([bmin3[0], -bmax3[2], bmin3[1]], np.float64)
    hi = np.array([bmax3[0], -bmin3[2], bmax3[1]], np.float64)
    return lo, hi


class SdfVolume:
    """What create_sdf_volume returns: .object (a Volume object), .program (the compiled GLSL), .spec, .voxel,
    .grid_info (dims, origin, the last frame's statistics), build(t), bake(...), raymarch_reference(camera)."""

    def __init__(self, spec: SdfVolumeSpec, scene=None, collection=None, name=None, location=(0, 0, 0),
                 rotation=(0, 0, 0), scale=1.0):
        import bpy
        self.spec = spec
        self.scene = scene or bpy.context.scene
        self.name = name or spec.name or 'sdf_volume'
        self.program = SdfProgram(sample=spec.sample, medium=spec.medium, post=spec.post, extra=spec.extra,
                                  uniforms=spec.uniforms, textures=spec.textures, defines=spec.defines,
                                  label=self.name)
        self.mode = 'sample' if spec.sample is not None else 'medium'
        self.voxel = spec.voxel_size()
        self.lo, self.hi = blender_box(spec.bounds_min, spec.bounds_max)
        self.dims = np.maximum(1, np.ceil((self.hi - self.lo) / self.voxel - 1e-9).astype(np.int64))
        self.cache_dir = os.path.normpath(bpy.path.abspath(spec.cache_dir)) if spec.cache_dir.startswith('//') \
            else spec.cache_dir
        self.grid_info = {'dims': tuple(int(x) for x in self.dims), 'voxel': self.voxel}
        vd = bpy.data.volumes.new(self.name)
        self.object = bpy.data.objects.new(self.name, vd)
        (collection or sdf_collection(self.scene)).objects.link(self.object)
        self.object.location = tuple(location)
        self.object.rotation_euler = tuple(rotation)
        s = scale if isinstance(scale, (tuple, list)) else (scale, scale, scale)
        self.object.scale = tuple(s)
        self.object['sdf_volume'] = self.mode
        self.material = None
        from .helper import track
        track(self)

    # ------------------------------------------------------------------------------------------------ uniforms --
    def set_uniform(self, name, value):
        self.program.set_uniform(name, value)
        return self

    # ----------------------------------------------------------------------------------------------- sampling ---
    def voxel_centres(self, k0=0, k1=None):
        """Blender-local voxel centres of z-slices k0..k1 as (nx, ny, nk, 3), and the same points in the SDF's
        three frame (N, 3) for the GLSL."""
        nx, ny, nz = (int(x) for x in self.dims)
        k1 = nz if k1 is None else k1
        xs = self.lo[0] + (np.arange(nx) + 0.5) * self.voxel
        ys = self.lo[1] + (np.arange(ny) + 0.5) * self.voxel
        zs = self.lo[2] + (np.arange(k0, k1) + 0.5) * self.voxel
        X, Y, Z = np.meshgrid(xs, ys, zs, indexing='ij')
        three = np.stack([X, Z, -Y], -1).reshape(-1, 3).astype(np.float32)
        return (nx, ny, k1 - k0), three

    def _eval_stage(self, pts):
        """The sample / medium stage at points (N, 3), as the GPU kernels' two (N, 4) targets. A Python callable
        (the engine's TSL sample was a host-language function too) runs in numpy and may read S.time / S.uniform:
          sample(p) -> {'color', 'alpha', 'step'} or (color, alpha, step)
          medium(p) -> {'density', 'albedo' (default 0.8 grey), 'emission', 'temperature'}"""
        fn = self.spec.sample if self.mode == 'sample' else self.spec.medium
        if isinstance(fn, str):
            return self.program.eval(self.mode, pts)
        from . import np_lib
        n = len(pts)

        def col(v, d):
            v = np.asarray(d if v is None else v, np.float32)
            return np.broadcast_to(v, (n, 3)) if v.ndim and v.shape[-1] == 3 else np.broadcast_to(v.reshape(-1, 1), (n, 3))

        def scal(v, d):
            v = np.asarray(d if v is None else v, np.float32)
            return np.broadcast_to(v.reshape(-1), (n,)) if v.ndim else np.full(n, float(v), np.float32)
        with np_lib.current(self.program):
            r = fn(np.asarray(pts, np.float32))
        o0 = np.zeros((n, 4), np.float32)
        o1 = np.zeros((n, 4), np.float32)
        if self.mode == 'sample':
            c, a, s = (r.get('color'), r.get('alpha'), r.get('step')) if isinstance(r, dict) else r
            o0[:, :3], o0[:, 3], o1[:, 0] = col(c, 0.0), scal(a, 0.0), scal(s, 0.01)
        else:
            r = r if isinstance(r, dict) else {'density': r}
            o0[:, :3], o0[:, 3] = col(r.get('emission'), 0.0), scal(r.get('density'), 0.0)
            o1[:, :3], o1[:, 3] = col(r.get('albedo'), 0.8), scal(r.get('temperature'), 0.0)
        return o0, o1

    def sample_grids(self, t=None, slab_points=1 << 21):
        """The grids at time t as numpy arrays indexed [x][y][z] in Blender local axes: density (nx, ny, nz),
        emission (nx, ny, nz, 3), and albedo / temperature when the medium gives them."""
        if t is not None:
            self.program.values['uTime'] = float(t)
        nx, ny, nz = (int(x) for x in self.dims)
        dens = np.zeros((nx, ny, nz), np.float32)
        emis = np.zeros((nx, ny, nz, 3), np.float32)
        scatter = self.mode == 'medium' or self.spec.sample_as == 'albedo'
        alb = np.zeros((nx, ny, nz, 3), np.float32) if scatter else None
        temp = np.zeros((nx, ny, nz), np.float32) if self.mode == 'medium' else None
        per_k = max(1, int(slab_points // max(1, nx * ny)))
        for k0 in range(0, nz, per_k):
            k1 = min(nz, k0 + per_k)
            shape, pts = self.voxel_centres(k0, k1)
            o0, o1 = self._eval_stage(pts)
            o0 = o0.reshape(shape + (4,))
            o1 = o1.reshape(shape + (4,))
            if self.mode == 'sample':
                a = np.clip(o0[..., 3], 0.0, float(self.spec.alpha_clamp))
                stp = np.maximum(o1[..., 0], 1e-4)
                sig = -np.log1p(-a) / stp
                dens[:, :, k0:k1] = sig
                if alb is not None:
                    alb[:, :, k0:k1] = np.clip(o0[..., :3], 0.0, 1.0)      # the colour as scattering albedo
                else:
                    emis[:, :, k0:k1] = np.maximum(o0[..., :3], 0.0) * sig[..., None]
            else:
                dens[:, :, k0:k1] = np.maximum(o0[..., 3], 0.0)
                emis[:, :, k0:k1] = np.maximum(o0[..., :3], 0.0)
                alb[:, :, k0:k1] = np.clip(o1[..., :3], 0.0, 1.0)
                temp[:, :, k0:k1] = np.maximum(o1[..., 3], 0.0)
        bad = ~np.isfinite(dens)
        dens[bad] = 0.0
        emis[~np.isfinite(emis)] = 0.0
        out = {'density': dens, 'emission': emis}
        if alb is not None:
            out['albedo'] = alb
        if temp is not None and float(temp.max()) > 0.0:
            out['temperature'] = temp
        self.grid_info.update(max_density=float(dens.max()), occupied=float(np.mean(dens > self.spec.prune)),
                              max_emission=float(emis.max()))
        return out

    def write_vdb(self, path, grids):
        """Write grids (from sample_grids) as one OpenVDB file, voxel centres at the Blender-local positions."""
        import openvdb as vdb
        os.makedirs(os.path.dirname(path), exist_ok=True)
        org = self.lo + 0.5 * self.voxel
        vs = float(self.voxel)
        xf = vdb.createLinearTransform([[vs, 0, 0, 0], [0, vs, 0, 0], [0, 0, vs, 0],
                                        [float(org[0]), float(org[1]), float(org[2]), 1]])
        out = []
        for name in GRID_NAMES:
            a = grids.get(name)
            if a is None:
                continue
            if a.ndim == 4:
                g = vdb.Vec3SGrid()
                tol = float(self.spec.prune)
                g.copyFromArray(np.ascontiguousarray(a, np.float32), tolerance=(tol, tol, tol))   # a Vec3s here
            else:
                g = vdb.FloatGrid()
                g.copyFromArray(np.ascontiguousarray(a, np.float32), tolerance=float(self.spec.prune))
            g.name = name
            g.transform = xf
            out.append(g)
        tmp = path + '.tmp.vdb'
        vdb.write(tmp, grids=out)
        os.replace(tmp, path)
        return path

    # ------------------------------------------------------------------------------------------------ building --
    def build(self, t=None, log=print):
        """Sample the volume at time t (seconds; None keeps uTime) into <cache_dir>/<name>.vdb and show it."""
        t = self.spec.time if t is None else t
        grids = self.sample_grids(t)
        path = os.path.join(self.cache_dir, f'{self.name}.vdb')
        self.write_vdb(path, grids)
        vd = self.object.data
        vd.filepath = path
        vd.is_sequence = False
        self._material(grids)
        if log:
            log(f'[sdf.volume] {self.name}: {self.grid_info["dims"]} @ {self.voxel * 1000:.1f} mm, '
                f'max density {self.grid_info["max_density"]:.3g}/m, {self.grid_info["occupied"] * 100:.1f}% occupied')
        return self

    def bake(self, frame_start=None, frame_end=None, step=1, time_scale=1.0, time_offset=0.0, controls=None,
             log=print):
        """One .vdb per frame (uTime = time_offset + time_scale * (frame - frame_start) / fps; controls(frame, t) ->
        {uniform: value} keys uniforms per frame), played as a Volume sequence: the saved .blend renders any frame."""
        sc = self.scene
        fs = sc.frame_start if frame_start is None else int(frame_start)
        fe = sc.frame_end if frame_end is None else int(frame_end)
        fps = sc.render.fps / sc.render.fps_base
        grids = None
        last = None
        for f in range(fs, fe + 1):
            path = os.path.join(self.cache_dir, f'{self.name}_{f:04d}.vdb')
            if (f - fs) % max(1, int(step)) == 0 or last is None:
                t = time_offset + time_scale * (f - fs) / fps
                if controls:
                    for k, v in (controls(f, t) or {}).items():
                        self.program.set_uniform(k, v)
                grids = self.sample_grids(t)
                self.write_vdb(path, grids)
                last = path
            else:
                import shutil
                shutil.copyfile(last, path)
            if log:
                log(f'[sdf.volume] {self.name}: frame {f}, max density {self.grid_info["max_density"]:.3g}/m')
        vd = self.object.data
        vd.filepath = os.path.join(self.cache_dir, f'{self.name}_{fs:04d}.vdb')
        vd.is_sequence = True
        vd.frame_start = fs
        vd.frame_duration = fe - fs + 1
        vd.frame_offset = fs - 1
        vd.sequence_mode = self.spec.sequence_mode
        self._material(grids)
        self.grid_info['baked'] = (fs, fe)
        return self

    def _material(self, grids):
        import bpy
        if self.material is not None:
            return self.material
        s = dict(DEFAULT_VOLUME_SETTINGS, **(self.spec.material_settings or {}))
        mat = bpy.data.materials.new(self.name + '_medium')
        mat.use_nodes = True
        nt = mat.node_tree
        for n in list(nt.nodes):
            if n.type != 'OUTPUT_MATERIAL':
                nt.nodes.remove(n)
        out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
        pv = nt.nodes.new('ShaderNodeVolumePrincipled')
        pv.location = (0, 0)
        # explicit Attribute nodes carry the grids, so the node's own attribute names must not multiply again
        for sock in ('Density Attribute', 'Color Attribute', 'Temperature Attribute'):
            if sock in pv.inputs:
                pv.inputs[sock].default_value = ''
        nt.links.new(pv.outputs[0], out.inputs['Volume'])

        def attr(name, y, socket='Fac'):
            a = nt.nodes.new('ShaderNodeAttribute')
            a.attribute_type = 'GEOMETRY'
            a.attribute_name = name
            a.location = (-600, y)
            return a.outputs[socket]
        dens = attr('density', 200)
        if float(s['density_scale']) != 1.0:
            m = nt.nodes.new('ShaderNodeMath')
            m.operation = 'MULTIPLY'
            m.inputs[1].default_value = float(s['density_scale'])
            m.location = (-300, 200)
            nt.links.new(dens, m.inputs[0])
            dens = m.outputs[0]
        nt.links.new(dens, pv.inputs['Density'])
        nt.links.new(attr('emission', 0, 'Color'), pv.inputs['Emission Color'])
        pv.inputs['Emission Strength'].default_value = float(s['emission_scale'])
        if 'albedo' in grids:
            nt.links.new(attr('albedo', -200, 'Color'), pv.inputs['Color'])
        else:
            c = s['albedo'] if s['albedo'] is not None else (0.0, 0.0, 0.0)
            pv.inputs['Color'].default_value = (*c, 1.0)
        pv.inputs['Absorption Color'].default_value = (0.0, 0.0, 0.0, 1.0)
        pv.inputs['Anisotropy'].default_value = float(s['anisotropy'])
        if 'temperature' in grids:
            nt.links.new(attr('temperature', -400), pv.inputs['Temperature'])
            pv.inputs['Blackbody Intensity'].default_value = float(s['blackbody_intensity'])
            pv.inputs['Blackbody Tint'].default_value = (*s['blackbody_tint'], 1.0)
        else:
            pv.inputs['Blackbody Intensity'].default_value = 0.0
        self.object.data.materials.clear()
        self.object.data.materials.append(mat)
        self.material = mat
        return mat

    # ----------------------------------------------------------------------------------------------- placement --
    def place_on_ground(self, ground_z=0.0):
        """The engine's mesh.position.y = groundY - bounds.min.y * scale, on Blender's z."""
        self.object.location.z = ground_z - self.spec.bounds_min[1] * self.object.scale.z
        return self

    def raymarch_reference(self, camera, width=480, height=270, samples=4, t=None, medium_step=None,
                           ambient=(0.0, 0.0, 0.0)):
        """createSdfVolume's own march of this volume from a Blender camera (linear, premultiplied (H, W, 4)); a
        medium() volume's scattering colour shows under a flat `ambient` light."""
        from .reference import volume_raymarch_image
        if not isinstance(self.spec.sample if self.mode == 'sample' else self.spec.medium, str):
            raise ValueError(f'{self.name}: the reference march runs GLSL; a Python {self.mode}() has none')
        if t is not None:
            self.program.values['uTime'] = float(t)
        return volume_raymarch_image(self, camera, width, height, samples, medium_step=medium_step, ambient=ambient)


def create_sdf_volume(spec=None, **kwargs):
    """The engine's createSdfVolume(spec): spec is a dict or an EXAMPLES volume entry (sample or medium, bounds,
    steps, post, extra, uniforms), keyword arguments override it. Builds the grids now (build=False to skip) at
    t = `time`. Extra options: cells / voxel / quality (grid resolution), cache_dir, material_settings,
    alpha_clamp, prune, sequence_mode, plus scene, collection, name, location, rotation, scale."""
    opts = dict(spec.as_dict() if hasattr(spec, 'as_dict') else (spec or {}))
    opts.update(kwargs)
    build = opts.pop('build', True)
    scene = opts.pop('scene', None)
    collection = opts.pop('collection', None)
    name = opts.pop('name', None)
    location = opts.pop('location', (0, 0, 0))
    rotation = opts.pop('rotation', (0, 0, 0))
    scale = opts.pop('scale', 1.0)
    log = opts.pop('log', print)
    sp = SdfVolumeSpec.from_options(opts)
    vol = SdfVolume(sp, scene=scene, collection=collection, name=name or sp.name, location=location,
                    rotation=rotation, scale=scale)
    if build:
        vol.build(log=log)
    return vol


def volume_render_settings(scene=None, tile_size='2', samples=96, end=None, shadows=True, shadow_samples=32):
    """EEVEE's volume settings for close SDF volumes: froxel tile size, samples along depth, the far end, shadows.
    The froxel grid is screen-space: a small volume far away needs a small tile size to keep its shape."""
    import bpy
    sc = scene or bpy.context.scene
    ee = sc.eevee
    ee.volumetric_tile_size = str(tile_size)
    ee.volumetric_samples = int(samples)
    if end is not None:
        ee.volumetric_end = float(end)
    for attr_name, v in (('use_volumetric_shadows', shadows), ('volumetric_shadow_samples', shadow_samples)):
        if hasattr(ee, attr_name):
            setattr(ee, attr_name, v)
    return sc
