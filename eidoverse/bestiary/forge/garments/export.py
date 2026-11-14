"""THE CLOTHED GLB: the human's glb (read, never edited in place) with the garments appended as skinned meshes on its
own skin (skin 0: the same joints, so three-vrm and the controller move them with the body), each garment its own
material and textures, and the HIDDEN-FACE MASK:
  * extras.bestiary.garments[]: per garment its name, kind, colour zones, the weave tile's repeat, the skin_BODY
    triangles it hides (hidden_tris), its texel density, its cache key;
  * skin_BODY's primitive gets the outfit's index buffer (the union of the worn garments' hidden triangles left out), and
    the full index stays in the file as an accessor named in extras.bestiary.body_index_full, so a runtime that takes a
    garment off restores the faces (the staged runtime patch does exactly that per garment).
"""
import io
import json
import struct

import numpy as np

from .. import gltf


class GlbEdit:
    def __init__(self, path):
        data = open(path, 'rb').read()
        jl = struct.unpack_from('<I', data, 12)[0]
        self.j = json.loads(data[20:20 + jl])
        bl = struct.unpack_from('<I', data, 20 + jl)[0]
        self.bin = bytearray(data[28 + jl:28 + jl + bl])
        for k in ('images', 'textures', 'materials', 'samplers', 'extensionsUsed'):
            self.j.setdefault(k, [])
        if not self.j['samplers']:
            self.j['samplers'].append({'magFilter': 9729, 'minFilter': 9987, 'wrapS': 10497, 'wrapT': 10497})

    def _view(self, data, target=None):
        while len(self.bin) % 4:
            self.bin.append(0)
        off = len(self.bin)
        self.bin += data
        v = {'buffer': 0, 'byteOffset': off, 'byteLength': len(data)}
        if target:
            v['target'] = target
        self.j['bufferViews'].append(v)
        return len(self.j['bufferViews']) - 1

    def accessor(self, arr, kind, target=None, minmax=False):
        arr = np.ascontiguousarray(arr)
        view = self._view(arr.tobytes(), target)
        a = {'bufferView': view, 'componentType': gltf._COMP[arr.dtype], 'count': int(arr.shape[0]), 'type': kind}
        if minmax:
            a['min'] = [float(x) for x in arr.min(0)]
            a['max'] = [float(x) for x in arr.max(0)]
        self.j['accessors'].append(a)
        return len(self.j['accessors']) - 1

    def texture(self, img, fmt='png', quality=92):
        from PIL import Image
        buf = io.BytesIO()
        im = Image.fromarray(np.asarray(img, np.uint8))
        if fmt == 'png':
            im.save(buf, 'PNG', compress_level=6)
            mime = 'image/png'
        else:
            im.convert('RGB').save(buf, 'JPEG', quality=quality, subsampling=0)
            mime = 'image/jpeg'
        view = self._view(buf.getvalue())
        self.j['images'].append({'bufferView': view, 'mimeType': mime})
        self.j['textures'].append({'sampler': 0, 'source': len(self.j['images']) - 1})
        return len(self.j['textures']) - 1

    def material(self, name, base, normal, orm, masks, extras):
        m = {'name': name, 'doubleSided': True,
             'pbrMetallicRoughness': {'baseColorTexture': {'index': base}, 'metallicRoughnessTexture': {'index': orm},
                                      'metallicFactor': 1.0, 'roughnessFactor': 1.0},
             'normalTexture': {'index': normal}, 'occlusionTexture': {'index': orm},
             'emissiveTexture': {'index': masks}, 'emissiveFactor': [0.0, 0.0, 0.0],
             'extras': extras}
        self.j['materials'].append(m)
        return len(self.j['materials']) - 1

    def skinned_mesh(self, name, V, N, TAN, UV, F, J4, W4, material):
        a = {'POSITION': self.accessor(np.asarray(V, np.float32), 'VEC3', 34962, minmax=True),
             'NORMAL': self.accessor(np.asarray(N, np.float32), 'VEC3', 34962),
             'TANGENT': self.accessor(np.asarray(TAN, np.float32), 'VEC4', 34962),
             'TEXCOORD_0': self.accessor(np.column_stack([UV[:, 0], 1.0 - UV[:, 1]]).astype(np.float32), 'VEC2', 34962),
             'JOINTS_0': self.accessor(np.asarray(J4, np.uint16), 'VEC4', 34962),
             'WEIGHTS_0': self.accessor(np.asarray(W4, np.float32), 'VEC4', 34962)}
        idx = self.accessor(np.asarray(F, np.uint32).reshape(-1), 'SCALAR', 34963)
        self.j['meshes'].append({'name': name, 'primitives': [{'attributes': a, 'indices': idx, 'material': material,
                                                                 'mode': 4}]})
        mi = len(self.j['meshes']) - 1
        self.j['nodes'].append({'name': name, 'mesh': mi, 'skin': 0})
        ni = len(self.j['nodes']) - 1
        self.j['scenes'][self.j.get('scene', 0)]['nodes'].append(ni)
        return ni

    def body_index(self, mesh_name, keep_tris_mask):
        m = next(m for m in self.j['meshes'] if m['name'] == mesh_name)
        p = m['primitives'][0]
        full = p['indices']
        a = self.j['accessors'][full]
        v = self.j['bufferViews'][a['bufferView']]
        dt = gltf._NP[a['componentType']]
        I = np.frombuffer(bytes(self.bin[v.get('byteOffset', 0) + a.get('byteOffset', 0):
                                         v.get('byteOffset', 0) + a.get('byteOffset', 0) + a['count'] * np.dtype(dt).itemsize]),
                          dt).reshape(-1, 3)
        keep = I[keep_tris_mask]
        p['indices'] = self.accessor(np.ascontiguousarray(keep.astype(np.uint32)).reshape(-1), 'SCALAR', 34963)
        return full

    def save(self, path):
        while len(self.bin) % 4:
            self.bin.append(0)
        self.j['buffers'] = [{'byteLength': len(self.bin)}]
        js = json.dumps(self.j, separators=(',', ':')).encode()
        js += b' ' * ((4 - len(js) % 4) % 4)
        total = 12 + 8 + len(js) + 8 + len(self.bin)
        with open(path, 'wb') as f:
            f.write(struct.pack('<III', 0x46546C67, 2, total))
            f.write(struct.pack('<II', len(js), 0x4E4F534A) + js)
            f.write(struct.pack('<II', len(self.bin), 0x004E4942) + bytes(self.bin))
        return total
