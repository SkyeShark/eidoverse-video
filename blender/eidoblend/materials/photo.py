"""eidoblend.materials.photo: materials written as one Principled BSDF over CC0 photographic sets laid at their real
size, with NT's maths for every layer (eidoblend.materials.layered.NT), and the CC0 library a piece reads them from.

    from eidoblend.materials import photo as PH
    lib = PH.Library('my_piece/cc0.json')            # {"textures": ["Paint004_2k", ...], "models": [...], "hdris": [...]}
    M = PH.Mat('wall_paint')
    PH.box_uv(wall)                                   # a UV in metres from each face's own plane ('box_m')
    v = M.mapping(M.uv('box_m'), (1 / 0.6, 1 / 0.6, 1.0))               # Paint004 is a 0.6 m tile
    paint = M.tex(lib.tex('Paint004_2k', 'diff'), v, color=True)
    col = M.tinted(paint, lib.tex('Paint004_2k', 'diff'), (0.52, 0.50, 0.42), 0.2)   # its light and shade on a colour
    M.bump(M.tex(lib.tex('Paint004_2k', 'displacement'), v).outputs[0], 0.0002)
    PH.assign(wall, M.done(col, 0.5, 0.0))

THE LIBRARY. A piece's cc0.json lists what it reads from Poly Haven and ambientCG: {"textures": [set IDs with their
resolution, e.g. "Paint004_2k"], "models": [{"id", "res"}], "hdris": [{"id", "res"}]}. Textures and models come through
eidoblend.harness.assets (fetch_texture.py / fetch_model.py --cache: eidoverse/assets/cache/, or EIDO_ASSET_CACHE),
fetched once on first use; each model keeps its .license.json beside it. HDRIs go to the cache's hdris/<id>_<res>/
through fetch_hdri.py, with a SOURCE.txt beside each. EIDO_NO_FETCH=1 turns a missing ID into an error naming its fetch
command.

A set's colour is often used for its light and shade only (tinted(): divided by its mean, on a colour of the piece's
own), so one photograph serves many finishes; its normal map needs a UV with a tangent frame (box_uv, planar_uv) or
none at all (a box projection of object space, read as a bump).
"""

from __future__ import annotations

import json
import math
import os
import subprocess

import bpy
import numpy as np

from .. import common
from ..harness import assets as HA
from .layered import NT


# ------------------------------------------------------------------------------------------------ the library ---

class Library:
    """A piece's CC0 manifest (cc0.json): its texture sets, models and HDRIs by ID, read from the shared library."""

    def __init__(self, manifest):
        with open(manifest, encoding='utf-8') as f:
            self.spec = json.load(f)
        self._sets = {}

    @staticmethod
    def split(set_id):
        """'Paint004_2k' -> ('Paint004', '2k')"""
        base, _, res = set_id.rpartition('_')
        return (base, res) if res.lower().endswith('k') and res[:-1].isdigit() else (set_id, '1k')

    def files(self, set_id):
        """{map: path} of a texture set, e.g. 'Paint004_2k' (fetched once)"""
        if set_id not in self._sets:
            sid, res = self.split(set_id)
            self._sets[set_id] = HA.fetch_pbr(sid, res)['files']
        return self._sets[set_id]

    def tex(self, set_id, key):
        """the path of one map ('diff', 'rough', 'normal', 'displacement', ...) of a texture set"""
        files = self.files(set_id)
        if key not in files:
            raise KeyError(f'{set_id} has no {key!r} map (it has {", ".join(sorted(files))})')
        return files[key]

    def model(self, mid, res='1k'):
        """the glTF of a Poly Haven model (its folder holds its .license.json)"""
        return HA.fetch_model_file(mid, res)

    def hdri(self, hid, res='4k'):
        """the .hdr (or .exr) of a Poly Haven HDRI in the cache's hdris/<id>_<res>/, fetched once by fetch_hdri.py"""
        d = common.cache_dir('hdris', f'{hid}_{res}')
        for n in ('hdri.hdr', 'hdri.exr'):
            if os.path.isfile(os.path.join(d, n)):
                return os.path.join(d, n)
        cmd = [os.environ.get('PYTHON') or ('python' if os.name == 'nt' else 'python3'),
               os.path.join(common.REPO, 'fetch_hdri.py'), hid, res]
        if os.environ.get('EIDO_NO_FETCH') == '1':
            raise FileNotFoundError(f'HDRI {hid} ({res}) is not in the library; fetch it with: (cd {d} && {" ".join(cmd)})')
        os.makedirs(d, exist_ok=True)
        common.log('library', f'HDRI {hid} ({res}): not in the library yet; fetching once (CC0) ...')
        subprocess.run(cmd, cwd=d, capture_output=True, text=True, creationflags=0x08000000 if os.name == 'nt' else 0)
        b64 = os.path.join(d, 'hdri_b64.txt')
        if os.path.isfile(b64):
            os.remove(b64)                                     # (the WebGPU edition's injection copy: not needed here)
        for n in ('hdri.hdr', 'hdri.exr'):
            if os.path.isfile(os.path.join(d, n)):
                with open(os.path.join(d, 'SOURCE.txt'), 'w', encoding='utf-8', newline='\n') as f:
                    f.write(f'{hid} at {res}: https://polyhaven.com/a/{hid}\nLicence: CC0 (Poly Haven)\n')
                return os.path.join(d, n)
        raise FileNotFoundError(f'HDRI {hid} ({res}) could not be fetched; run in {d}: {" ".join(cmd)}')

    def fetch_all(self):
        """every ID of the manifest into the library now (else each is fetched when a material first reads it)"""
        for sid in self.spec.get('textures', []):
            self.files(sid)
        for m in self.spec.get('models', []):
            self.model(m['id'], m.get('res', '1k'))
        for h in self.spec.get('hdris', []):
            self.hdri(h['id'], h.get('res', '4k'))


# ------------------------------------------------------------------------------------------------ materials ---

IMGS, MEANS = {}, {}


def image(path, color):
    """a picture loaded once, as colour (sRGB) or data (Non-Color)"""
    k = (path, color)
    if k not in IMGS or IMGS[k].name not in bpy.data.images:
        img = bpy.data.images.load(path, check_existing=True)
        img.colorspace_settings.name = 'sRGB' if color else 'Non-Color'
        IMGS[k] = img
    return IMGS[k]


def mean_lum(path):
    """a colour picture's mean luminance in linear light (its light and shade is then used about 1.0)"""
    if path not in MEANS:
        img = image(path, True)
        a = np.empty(img.size[0] * img.size[1] * 4, np.float32)
        img.pixels.foreach_get(a)
        a = a.reshape(-1, 4)
        MEANS[path] = float(max(1e-4, (a[:, 0] * 0.2126 + a[:, 1] * 0.7152 + a[:, 2] * 0.0722).mean()))
    return MEANS[path]


class Mat(NT):
    """One material: NT's maths plus pictures, coordinates and the Principled BSDF it ends in. ROUGH_MIN floors a
    roughness that is a socket."""
    ROUGH_MIN = 0.02

    def __init__(self, name):
        self.mat = bpy.data.materials.new(name)
        self.mat.use_nodes = True
        super().__init__(self.mat.node_tree)
        for n in list(self.N):
            if n.type != 'OUTPUT_MATERIAL':
                self.N.remove(n)
        self.out = next(n for n in self.N if n.type == 'OUTPUT_MATERIAL')
        self.bsdf = self.N.new('ShaderNodeBsdfPrincipled')
        self.L.new(self.bsdf.outputs[0], self.out.inputs[0])
        self.normal = None                                     # the normal the layers bend, as it builds up

    def tex(self, path, vec, color=False, box=False, interp='Linear'):
        """an Image Texture of the picture at `path` read at `vec` (box: a box projection of an object-space vector)"""
        n = self.N.new('ShaderNodeTexImage')
        n.image = image(path, color)
        n.interpolation = interp
        if box:
            n.projection, n.projection_blend = 'BOX', 0.25
        self.L.new(vec, n.inputs['Vector'])
        return n

    def mixc(self, f, a, b):
        """NT.mixc, a colour given as three numbers made four"""
        a = (*a, 1.0) if isinstance(a, tuple) and len(a) == 3 else a
        b = (*b, 1.0) if isinstance(b, tuple) and len(b) == 3 else b
        return super().mixc(f, a, b)

    def uv(self, name):
        n = self.N.new('ShaderNodeUVMap')
        n.uv_map = name
        return n.outputs[0]

    def mapping(self, vec, scale=(1.0, 1.0, 1.0), rot=(0.0, 0.0, 0.0), loc=(0.0, 0.0, 0.0)):
        mp = self.N.new('ShaderNodeMapping')
        self.L.new(vec, mp.inputs['Vector'])
        mp.inputs['Location'].default_value = loc
        mp.inputs['Rotation'].default_value = rot
        mp.inputs['Scale'].default_value = scale
        return mp.outputs[0]

    def sep(self, vec):
        """(x, y, z) of a vector socket"""
        n = self.N.new('ShaderNodeSeparateXYZ')
        self.L.new(vec, n.inputs[0])
        return n.outputs

    def world_nrm(self):
        """(x, y, z) of the shading normal in world space"""
        g = self.N.new('ShaderNodeNewGeometry')
        return self.sep(g.outputs['Normal'])

    wnz = world_nrm

    def objm(self):
        """the point in the object's own space, metres"""
        return self.obj()

    def nmap(self, color_out, uvname, strength=1.0):
        n = self.N.new('ShaderNodeNormalMap')
        n.space, n.uv_map = 'TANGENT', uvname
        n.inputs['Strength'].default_value = strength
        self.L.new(color_out, n.inputs['Color'])
        self.normal = n.outputs[0]
        return n.outputs[0]

    def bump(self, height, dist_m, strength=1.0):
        """a Bump over the normal built so far"""
        b = self.N.new('ShaderNodeBump')
        b.inputs['Strength'].default_value, b.inputs['Distance'].default_value = strength, dist_m
        self.put(b.inputs['Height'], height)
        if self.normal is not None:
            self.L.new(self.normal, b.inputs['Normal'])
        self.normal = b.outputs[0]
        return b.outputs[0]

    def rgb(self, c):
        n = self.N.new('ShaderNodeRGB')
        n.outputs[0].default_value = (*c[:3], 1.0)
        return n.outputs[0]

    def tint(self, col, rgb, desat=0.0, gain=1.0):
        """a photograph's colour brought to a finish: desaturated by desat, multiplied by rgb, scaled by gain"""
        if desat:
            h = self.N.new('ShaderNodeHueSaturation')
            self.L.new(col, h.inputs['Color'])
            h.inputs['Saturation'].default_value = 1.0 - desat
            col = h.outputs[0]
        m = super().mixc(1.0, col, self.rgb(tuple(v * gain for v in rgb)))
        m.node.blend_type = 'MULTIPLY'
        return m

    def lum(self, col):
        n = self.N.new('ShaderNodeRGBToBW')
        self.L.new(col, n.inputs[0])
        return n.outputs[0]

    def tinted(self, tex_node, path, rgb, k):
        """the picture's own light and shade about 1.0 (divided by its mean), k of it, on the colour rgb"""
        ratio = self.m('DIVIDE', self.lum(tex_node.outputs[0]), mean_lum(path))
        return self.value(self.rgb(rgb), self.add(1.0, self.mul(self.sub(ratio, 1.0), k)))

    def attr(self, name):
        n = self.N.new('ShaderNodeAttribute')
        n.attribute_name = name
        return n

    def done(self, col, rough, metal=0.0, extra=None):
        """the Principled BSDF's inputs (numbers or sockets; extra: {input name: value}) -> the material"""
        self.put(self.bsdf.inputs['Base Color'], col)
        r = self.m('MAXIMUM', rough, self.ROUGH_MIN, clamp=True) if not isinstance(rough, float) else rough
        self.put(self.bsdf.inputs['Roughness'], r)
        self.put(self.bsdf.inputs['Metallic'], metal)
        if self.normal is not None:
            self.L.new(self.normal, self.bsdf.inputs['Normal'])
        for k, v in (extra or {}).items():
            self.put(self.bsdf.inputs[k], v)
        return self.mat


def box_uv(o, name='box_m', world=False):
    """A UV in metres from each face's own plane (u to the right as one faces it, v up): a photograph's real size is
    then one Mapping's scale, and its normal map has a tangent frame. world: in world space (the object's transform
    applied) rather than the object's own."""
    me = o.data
    if name in me.uv_layers:
        return
    act = me.uv_layers.active
    uvl = me.uv_layers.new(name=name)
    M = o.matrix_world if world else None
    R = M.to_3x3() if world else None
    for p in me.polygons:
        n = (R @ p.normal).normalized() if world else p.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            if world:
                co = M @ co
            if ax == 0:
                u, v = (co.y if n.x > 0 else -co.y), co.z
            elif ax == 1:
                u, v = (-co.x if n.y > 0 else co.x), co.z
            else:
                u, v = co.x, (co.y if n.z > 0 else -co.y)
            uvl.data[li].uv = (u, v)
    if act is not None:
        me.uv_layers.active = act


def planar_uv(o, name, centre, axes, size, deg=0.0, flip_u=False):
    """A picture's UV over a sheet: centre (mm) in the plane spanned by axes (two of 'xyz'), size (mm, w x h), turned by
    deg in that plane; flip_u: the picture is seen from the plane's back (it reads the right way round from there)."""
    me = o.data
    uvl = me.uv_layers.get(name) or me.uv_layers.new(name=name)
    c_, s_ = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    ia, ib = 'xyz'.index(axes[0]), 'xyz'.index(axes[1])
    for p in me.polygons:
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co * 1000.0
            a, b = co[ia] - centre[0], co[ib] - centre[1]
            pu, pv = a * c_ + b * s_, -a * s_ + b * c_
            u = pu / size[0] + 0.5
            uvl.data[li].uv = ((1.0 - u) if flip_u else u, pv / size[1] + 0.5)


def assign(o, m):
    """o's one material slot holds m"""
    o.data.materials.clear()
    o.data.materials.append(m)


def picture(M, folder, name, uvname, color=True):
    """a drawn picture (folder/name) through a UV of its own, clipped at its edges"""
    n = M.tex(os.path.join(folder, name), M.uv(uvname), color=color, interp='Cubic')
    n.extension = 'CLIP'
    return n
