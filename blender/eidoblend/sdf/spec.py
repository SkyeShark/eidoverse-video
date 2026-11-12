"""The SDF spec, the quality presets, the EXAMPLES registry and the example convention.

AN EXAMPLE (the convention the solid, vehicle and volume examples share) is GLSL plus numbers, as the engine's
GLSL EXAMPLES were:

    register_example('basic_sphere', kind='solid',
        bounds={'min': [-1, -1, -1], 'max': [1, 1, 1]},     # the SDF's local frame, three.js style (y up)
        quality='fast',                                      # QUALITY_PRESETS key
        extra=GLSL,          # helpers, #defines, material functions (optional)
        map=GLSL,            # vec2 map(vec3 p): (distance, material id) -- the engine's map, unchanged
        shade=GLSL,          # vec3 shade(vec3 p, vec3 n, float mat): the engine's lit colour (its own look)
        surface=GLSL,        # SdfSurface surface(vec3 p, vec3 n, float mat): what EEVEE renders (PBR)
        uniforms={'uPaint': ('color', '#c8c8d2')},           # live knobs (+ uTime, always there)
        animated=False,      # map/surface read uTime: bake() re-meshes per frame
        cut_by_bounds=False, # the shape runs past its bounds on purpose (a TPMS): the box cuts it
        make=None)           # optional factory(**opts) -> SdfObject (the engine's make(opts))

  Without surface=, a GLSL (or Python) shade() is the material: its colour seen head-on becomes the base colour
  (shade_as='albedo', the default) or the emission (shade_as='emission', the engine's unlit look). That is how a
  spec written for the engine's own contract (map + shade) renders; writing surface() is better, since shade()'s
  hand lighting otherwise stays in the colour.

  A volume example gives sample=GLSL (SdfSample sample(vec3 p): the engine's {color, alpha, step}) or
  medium=GLSL (SdfMedium medium(vec3 p): density / albedo / emission per metre) instead of map/surface.

EXAMPLES['basic_sphere'].make(location=(0, 0, 1)) builds one; create_sdf_object(EXAMPLES['x'], **overrides) too.
"""

from __future__ import annotations

# The engine's presets, its four raymarch numbers unchanged (a spec carries them as the engine set them; the mesh
# does not march), plus what quality means for a mesh: `cells` voxels along the bounds' longest side, `texels` atlas
# texels along each quad side.
QUALITY_PRESETS = {
    'fast':     {'max_steps': 64,  'surf_eps': 0.0020, 'step_scale': 0.90, 'max_dist': 60.0,  'cells': 128, 'texels': 3},
    'balanced': {'max_steps': 128, 'surf_eps': 0.0010, 'step_scale': 0.85, 'max_dist': 100.0, 'cells': 256, 'texels': 4},
    'high':     {'max_steps': 192, 'surf_eps': 0.0005, 'step_scale': 0.75, 'max_dist': 150.0, 'cells': 384, 'texels': 4},
    'ultra':    {'max_steps': 256, 'surf_eps': 0.0003, 'step_scale': 0.70, 'max_dist': 200.0, 'cells': 640, 'texels': 5},
}

_CAMEL = {'maxSteps': 'max_steps', 'maxDist': 'max_dist', 'stepScale': 'step_scale', 'surfEps': 'surf_eps'}


def _bounds(b):
    if b is None:
        return (-1.0, -1.0, -1.0), (1.0, 1.0, 1.0)
    if isinstance(b, dict):
        return tuple(float(x) for x in b['min']), tuple(float(x) for x in b['max'])
    return tuple(float(x) for x in b[0]), tuple(float(x) for x in b[1])


class SdfSpec:
    """Every option of create_sdf_object (and the solid part of an example)."""

    FIELDS = dict(
        name=None, map=None, shade=None, surface=None, extra='', bounds=None, quality='balanced',
        max_steps=None, max_dist=None, step_scale=None, surf_eps=None, uniforms=None, textures=None, defines=None,
        voxel=None, cells=None, texels=None, carrier='atlas', normals='corner', brick=4, lipschitz_k=None,
        materials=None, material_settings=None, cache_dir='//sdf_cache', pack_images=False, time=0.0,
        animated=False, iso=0.0, refine=3, qef_lambda=0.01, min_component=0, atlas_budget=16_777_216,
        shade_as='albedo', cut_by_bounds=False, view_terms=None,
    )

    def __init__(self, **kw):
        for k, v in self.FIELDS.items():
            setattr(self, k, kw.get(k, v))
        unknown = set(kw) - set(self.FIELDS)
        if unknown:
            raise TypeError(f'create_sdf_object: unknown options {sorted(unknown)}')
        if self.quality not in QUALITY_PRESETS:
            self.quality = 'balanced'
        self.bounds_min, self.bounds_max = _bounds(self.bounds)
        q = QUALITY_PRESETS[self.quality]
        self.max_steps = q['max_steps'] if self.max_steps is None else self.max_steps
        self.max_dist = q['max_dist'] if self.max_dist is None else self.max_dist
        self.step_scale = q['step_scale'] if self.step_scale is None else self.step_scale
        self.surf_eps = q['surf_eps'] if self.surf_eps is None else self.surf_eps
        self.texels = int(q['texels'] if self.texels is None else self.texels)

    @classmethod
    def from_options(cls, opts):
        kw = {}
        for k, v in opts.items():
            k = _CAMEL.get(k, k)
            if k == 'lipschitz':
                k = 'lipschitz_k'
            if k in ('kind', 'make', 'description', 'sample', 'medium', 'steps', 'post', 'reference_image'):
                continue
            kw[k] = v
        return cls(**kw)

    def voxel_size(self):
        if self.voxel:
            return float(self.voxel)
        cells = self.cells or QUALITY_PRESETS[self.quality]['cells']
        ext = max(b - a for a, b in zip(self.bounds_min, self.bounds_max))
        return ext / float(cells)

    def lipschitz(self):
        """How much faster than distance the field may change (culling safety): 1.25 / stepScale by default."""
        return float(self.lipschitz_k) if self.lipschitz_k else 1.25 / float(self.step_scale)

    def as_dict(self):
        d = {k: getattr(self, k) for k in self.FIELDS}
        d['bounds'] = {'min': list(self.bounds_min), 'max': list(self.bounds_max)}
        return d


class SdfExample(dict):
    """One EXAMPLES entry: a dict of its spec fields (pass it to create_sdf_object / create_sdf_volume) with
    .make(**opts), .kind and .name."""

    def __init__(self, name, kind='solid', make=None, description='', **fields):
        super().__init__(fields)
        self['name'] = name
        self.name = name
        self.kind = kind
        self.description = description
        self._make = make

    def make(self, opts=None, **kw):
        """The engine's EXAMPLES.x.make(opts): build one with these overrides (a dict, keywords, or both)."""
        opts = dict(opts or {}, **kw)
        if self._make is not None:
            return self._make(self, **opts)
        if self.kind == 'volume':
            from .volume import create_sdf_volume
            return create_sdf_volume(self, **opts)
        from .solid import create_sdf_object
        return create_sdf_object(self, **opts)

    def as_dict(self):
        return dict(self)

    def __repr__(self):
        return f'<SdfExample {self.name} ({self.kind})>'


class _Examples(dict):
    """EXAMPLES: name -> SdfExample. Solid examples register from examples_solids.py; the vehicle and volume
    steps add theirs with register_example (they import this module's EXAMPLES)."""

    def solids(self):
        return [k for k, v in self.items() if v.kind == 'solid']

    def volumes(self):
        return [k for k, v in self.items() if v.kind == 'volume']


EXAMPLES = _Examples()


def register_example(name, kind='solid', make=None, description='', **fields):
    ex = SdfExample(name, kind=kind, make=make, description=description, **fields)
    EXAMPLES[name] = ex
    return ex


def file_stem(name):
    """The stem of an SDF's cache files (atlases, frame meshes, grids, screen frames): the name of its Blender
    datablock. Blender keeps object names, and image names, unique in a file ('mr_hege', 'mr_hege.001'), so two SDFs
    of one example never write over each other's files; characters a file name cannot hold become '_'."""
    import re
    return re.sub(r'[\\/:*?"<>|\s]+', '_', str(name)).strip('_') or 'sdf'


_WARNED_UNSAVED = set()


def resolve_cache_dir(path):
    """A cache_dir as an absolute folder. '//x' is beside the open .blend; before the file is saved (a harness build
    saves it only at the end) that is the working directory, which every build run from there shares, so it says so
    once: two builds there that each make a 'mr_hege' write the same files, and the first build's .blend then plays
    the second's. A scene keeps its own with cache_dir=os.path.join(ctx.out_dir, 'sdf_cache')."""
    import os
    import bpy
    if not path.startswith('//'):
        return os.path.normpath(os.path.abspath(path))
    out = os.path.normpath(os.path.abspath(bpy.path.abspath(path)))
    if not bpy.data.filepath and out not in _WARNED_UNSAVED:
        _WARNED_UNSAVED.add(out)
        print(f"[sdf] cache_dir {path!r}: the .blend is not saved yet, so the files go to {out}, shared by every "
              f"unsaved build run from this folder; pass cache_dir=os.path.join(ctx.out_dir, 'sdf_cache') to keep a "
              f"scene's own", flush=True)
    return out


def sdf_collection(scene=None, name='SDF'):
    """The collection every SDF object and volume is linked into (the engine's helper-owned SDF scene)."""
    import bpy
    scene = scene or bpy.context.scene
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
    if coll.name not in scene.collection.children:
        try:
            scene.collection.children.link(coll)
        except RuntimeError:
            pass
    return coll
