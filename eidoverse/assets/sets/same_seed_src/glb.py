"""glb.py: a small binary glTF 2.0 writer (numpy only), for the SAME SEED rooms' export.

    from glb import GLB
    g = GLB('same_seed_src/export_room.py')
    pos = g.accessor(np.float32 positions (n, 3), 'VEC3', minmax=True, target=34962)
    idx = g.accessor(np.uint32 indices (m,), 'SCALAR', target=34963)
    mat = g.material({'name': 'wall', 'pbrMetallicRoughness': {...}})
    mesh = g.mesh('wall', [{'attributes': {'POSITION': pos}, 'indices': idx, 'material': mat}])
    g.node('wall', mesh=mesh, matrix=[16 floats, column-major])
    g.write('wall.glb')

Images go into the binary chunk (g.image(bytes, 'image/jpeg')). Vertex attributes whose names start with '_' are
application-specific (three's GLTFLoader keeps them, lower-cased). Nothing here knows Blender.
"""

import json
import struct

import numpy as np

_CTYPE = {np.dtype(np.float32): 5126, np.dtype(np.uint32): 5125, np.dtype(np.uint16): 5123, np.dtype(np.uint8): 5121,
          np.dtype(np.int16): 5122, np.dtype(np.int8): 5120}
_NCOMP = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}


class GLB:
    def __init__(self, generator='glb.py'):
        self.j = {'asset': {'version': '2.0', 'generator': generator}, 'scene': 0, 'scenes': [{'nodes': []}],
                  'nodes': [], 'meshes': [], 'materials': [], 'accessors': [], 'bufferViews': [],
                  'buffers': [{'byteLength': 0}]}
        self.bin = bytearray()

    def _view(self, data, target=None, stride=None):
        while len(self.bin) % 4:
            self.bin.append(0)
        v = {'buffer': 0, 'byteOffset': len(self.bin), 'byteLength': len(data)}
        if target:
            v['target'] = target
        if stride:
            v['byteStride'] = stride
        self.bin += data
        self.j['bufferViews'].append(v)
        return len(self.j['bufferViews']) - 1

    def accessor(self, arr, type_, target=None, minmax=False, normalized=False):
        """an accessor over a C-contiguous array: (n,) for SCALAR, (n, k) for VECk; a vertex attribute whose elements
        are not a multiple of 4 bytes (int8 VEC3) is padded to a 4-byte stride"""
        a = np.ascontiguousarray(arr)
        n = a.shape[0]
        stride = None
        if target == 34962 and a.ndim == 2 and (a.shape[1] * a.dtype.itemsize) % 4:
            stride = ((a.shape[1] * a.dtype.itemsize + 3) // 4) * 4
            pad = np.zeros((n, stride // a.dtype.itemsize), a.dtype)
            pad[:, :a.shape[1]] = a
            data = pad.tobytes()
        else:
            data = a.tobytes()
        acc = {'bufferView': self._view(data, target, stride), 'componentType': _CTYPE[a.dtype], 'count': int(n),
               'type': type_}
        if normalized:
            acc['normalized'] = True
        if minmax and n:
            r = a.reshape(n, _NCOMP[type_])
            acc['min'] = [float(x) for x in r.min(axis=0)]
            acc['max'] = [float(x) for x in r.max(axis=0)]
        self.j['accessors'].append(acc)
        return len(self.j['accessors']) - 1

    def image(self, data, mime, name=None):
        im = {'bufferView': self._view(bytes(data)), 'mimeType': mime}
        if name:
            im['name'] = name
        self.j.setdefault('images', []).append(im)
        return len(self.j['images']) - 1

    def texture(self, image, sampler=None):
        if sampler is None:
            sampler = {'magFilter': 9729, 'minFilter': 9987, 'wrapS': 33071, 'wrapT': 33071}   # linear, mips, clamp
        samplers = self.j.setdefault('samplers', [])
        if sampler not in samplers:
            samplers.append(sampler)
        self.j.setdefault('textures', []).append({'source': image, 'sampler': samplers.index(sampler)})
        return len(self.j['textures']) - 1

    def material(self, m):
        self.j['materials'].append(m)
        return len(self.j['materials']) - 1

    def mesh(self, name, primitives, extras=None):
        m = {'name': name, 'primitives': primitives}
        if extras:
            m['extras'] = extras
        self.j['meshes'].append(m)
        return len(self.j['meshes']) - 1

    def node(self, name, mesh=None, matrix=None, children=None, extras=None, root=True):
        n = {'name': name}
        if mesh is not None:
            n['mesh'] = mesh
        if matrix is not None and any(abs(a - b) > 1e-9 for a, b in zip(matrix, (1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1))):
            n['matrix'] = [float(x) for x in matrix]
        if children:
            n['children'] = list(children)
        if extras:
            n['extras'] = extras
        self.j['nodes'].append(n)
        i = len(self.j['nodes']) - 1
        if root:
            self.j['scenes'][0]['nodes'].append(i)
        return i

    def use(self, ext, required=False):
        u = self.j.setdefault('extensionsUsed', [])
        if ext not in u:
            u.append(ext)
        if required:
            r = self.j.setdefault('extensionsRequired', [])
            if ext not in r:
                r.append(ext)

    def write(self, path):
        while len(self.bin) % 4:
            self.bin.append(0)
        self.j['buffers'][0]['byteLength'] = len(self.bin)
        for k in ('materials', 'meshes', 'accessors', 'bufferViews'):
            if not self.j[k]:
                del self.j[k]
        js = json.dumps(self.j, separators=(',', ':')).encode('utf-8')
        while len(js) % 4:
            js += b' '
        total = 12 + 8 + len(js) + 8 + len(self.bin)
        with open(path, 'wb') as f:
            f.write(struct.pack('<III', 0x46546C67, 2, total))
            f.write(struct.pack('<II', len(js), 0x4E4F534A))
            f.write(js)
            f.write(struct.pack('<II', len(self.bin), 0x004E4942))
            f.write(self.bin)
        return total
