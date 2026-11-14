"""A minimal glTF 2.0 BINARY (.glb) writer and reader for the Bestiary's creatures.

Writes skinned meshes (POSITION, NORMAL, TANGENT, TEXCOORD_0, JOINTS_0, WEIGHTS_0; primitives sharing one vertex set),
MORPH TARGETS (position and normal deltas, sparse: only the vertices a target moves), PBR materials with embedded
textures (WebP through EXT_texture_webp, which three.js's GLTFLoader reads), a joint hierarchy with inverse bind
matrices, socket nodes and extras.

Conventions are converted ONCE, here (craft guide 00.88, AG 00.86): metres, +Y up, the creature facing +Z; the forge's
UVs have v up the image, glTF's run down it (v' = 1 - v); tangents are (x, y, z, w) with the bitangent cross(N, T) * w,
the bake's own frame; ORM packs occlusion R, roughness G, metalness B (glTF reads exactly those channels).

    g = GLB(); ...; g.save(path)        read(path) -> dict of the parsed JSON and numpy views (verification)
"""
import io
import json
import struct

import numpy as np

_COMP = {np.dtype(np.float32): 5126, np.dtype(np.uint16): 5123, np.dtype(np.uint32): 5125, np.dtype(np.uint8): 5121}
_NP = {5126: np.float32, 5123: np.uint16, 5125: np.uint32, 5121: np.uint8}
_NCOMP = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}


def quat_from_matrix(R):
    """(x, y, z, w) of a rotation matrix"""
    R = np.asarray(R, np.float64)
    tr = np.trace(R)
    if tr > 0:
        s = np.sqrt(tr + 1.0) * 2
        q = [(R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s, 0.25 * s]
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2
        q = [0.25 * s, (R[0, 1] + R[1, 0]) / s, (R[0, 2] + R[2, 0]) / s, (R[2, 1] - R[1, 2]) / s]
    elif R[1, 1] > R[2, 2]:
        s = np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2
        q = [(R[0, 1] + R[1, 0]) / s, 0.25 * s, (R[1, 2] + R[2, 1]) / s, (R[0, 2] - R[2, 0]) / s]
    else:
        s = np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2
        q = [(R[0, 2] + R[2, 0]) / s, (R[1, 2] + R[2, 1]) / s, 0.25 * s, (R[1, 0] - R[0, 1]) / s]
    q = np.array(q)
    return (q / np.linalg.norm(q)).tolist()


class GLB:
    def __init__(self, generator='eidoverse bestiary forge'):
        self.bin = bytearray()
        # the samplers CLAMP: the maps are atlases, and a repeating sampler's mips blended each strip's end with the
        # atlas's opposite edge (r4 review, seams lens)
        self.j = dict(asset={'version': '2.0', 'generator': generator}, scene=0, scenes=[{'nodes': []}], nodes=[],
                      meshes=[], accessors=[], bufferViews=[], materials=[], textures=[], images=[], skins=[],
                      samplers=[{'magFilter': 9729, 'minFilter': 9987, 'wrapS': 33071, 'wrapT': 33071}])
        self.ext_used = set()

    # ------------------------------------------------------------------------------------------------- data
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
        acc = {'bufferView': view, 'componentType': _COMP[arr.dtype], 'count': int(arr.shape[0]), 'type': kind}
        if minmax:
            acc['min'] = arr.reshape(len(arr), -1).min(0).astype(float).tolist()
            acc['max'] = arr.reshape(len(arr), -1).max(0).astype(float).tolist()
        self.j['accessors'].append(acc)
        return len(self.j['accessors']) - 1

    def sparse_accessor(self, count, idx, values, kind, minmax=False):
        """an accessor of `count` elements, zero but at idx (uint32) where it takes values (float32): no bufferView of
        its own (glTF 2.0: zeros, the sparse part over them), so a morph target that moves a few thousand vertices of a
        large vertex set ships only those"""
        values = np.ascontiguousarray(values, np.float32).reshape(len(idx), _NCOMP[kind])
        acc = {'componentType': 5126, 'count': int(count), 'type': kind}
        if len(idx):
            acc['sparse'] = {'count': int(len(idx)),
                             'indices': {'bufferView': self._view(np.asarray(idx, np.uint32).tobytes()),
                                         'componentType': 5125},
                             'values': {'bufferView': self._view(values.tobytes())}}
        if minmax:
            v = np.vstack([values, np.zeros((1, values.shape[1]), np.float32)])
            acc['min'] = v.min(0).astype(float).tolist()
            acc['max'] = v.max(0).astype(float).tolist()
        self.j['accessors'].append(acc)
        return len(self.j['accessors']) - 1

    def morph_targets(self, mesh, targets, names, eps=1e-7, extra=None):
        """MORPH TARGETS on every primitive of a mesh (glTF: each primitive the same targets, in order): targets is a
        list of (position deltas (n, 3), normal deltas (n, 3) or None) over the vertex set of the mesh's first
        primitive, so the primitives sharing it share the accessors; a primitive with its own vertex set takes its own
        targets from extra {primitive index: [(position deltas, normal deltas or None) per target]} (the suckers' rigid
        compensation), else zero targets (accessors with no data: zeros). Each target ships its moved vertices only
        (sparse accessors). The mesh's default weights are 0 (the bind) and its extras.targetNames the names (three's
        morphTargetDictionary)"""
        m = self.j['meshes'][mesh]
        base = m['primitives'][0]['attributes']['POSITION']
        n = self.j['accessors'][base]['count']

        def accs_for(tlist, count):
            # every target of a primitive carries a NORMAL when any does (zeros, no data, where it has none): three
            # r184's GLTFLoader (addMorphTargets) hands a target WITHOUT one the BASE normal attribute as its delta, and
            # MorphNode adds it at the target's weight (morphTargetsRelative), so an uneven set shades wrong
            any_n = any(dn is not None for _, dn in tlist)
            out = []
            for dp, dn in tlist:
                dp = np.asarray(dp, np.float64)
                assert dp.shape == (count, 3), (dp.shape, count)
                moved = np.nonzero(np.abs(dp).max(1) > eps)[0]
                t = {'POSITION': self.sparse_accessor(count, moved, dp[moved], 'VEC3', minmax=True)}
                if dn is not None or any_n:
                    dn = np.zeros((count, 3)) if dn is None else np.asarray(dn, np.float64)
                    mn = np.nonzero(np.abs(dn).max(1) > eps)[0]
                    t['NORMAL'] = self.sparse_accessor(count, mn, dn[mn], 'VEC3')
                out.append(t)
            return out
        accs = accs_for(targets, n)
        for pi, p in enumerate(m['primitives']):
            if p['attributes']['POSITION'] == base:
                p['targets'] = [dict(t) for t in accs]
            else:
                c = self.j['accessors'][p['attributes']['POSITION']]['count']
                if extra and pi in extra:
                    assert len(extra[pi]) == len(targets)
                    p['targets'] = accs_for(extra[pi], c)
                else:
                    p['targets'] = [{k: self.sparse_accessor(c, [], np.zeros((0, 3)), 'VEC3',
                                                             minmax=(k == 'POSITION')) for k in t} for t in accs]
        m['weights'] = [0.0] * len(targets)
        m.setdefault('extras', {})['targetNames'] = list(names)

    def texture(self, img, lossless=False, quality=92, fmt='webp'):
        """an RGB / RGBA / gray uint8 image, embedded as WebP (EXT_texture_webp), PNG or JPEG. The eidoverse engine
        decodes PNG / JPEG headless; WebP needs the loader's browser-side support check"""
        from PIL import Image
        buf = io.BytesIO()
        im = Image.fromarray(np.asarray(img, np.uint8))
        if fmt == 'webp':
            im.save(buf, 'WEBP', lossless=lossless, quality=quality, method=4)
        elif fmt == 'png':
            im.save(buf, 'PNG', optimize=False, compress_level=6)
        else:
            im.convert('RGB').save(buf, 'JPEG', quality=quality, subsampling=0)
        view = self._view(buf.getvalue())
        mime = {'webp': 'image/webp', 'png': 'image/png'}.get(fmt, 'image/jpeg')
        self.j['images'].append({'bufferView': view, 'mimeType': mime})
        src = len(self.j['images']) - 1
        if fmt == 'webp':
            self.j['textures'].append({'sampler': 0, 'extensions': {'EXT_texture_webp': {'source': src}}})
            self.ext_used.add('EXT_texture_webp')
        else:
            self.j['textures'].append({'sampler': 0, 'source': src})
        return len(self.j['textures']) - 1

    def material(self, name, base=None, normal=None, orm=None, extras=None, double_sided=False, volume_tex=None,
                 emissive_tex=None, irid_tex=None):
        """volume_tex / emissive_tex / irid_tex: extra data maps carried in STANDARD slots (KHR_materials_volume's
        thickness texture; the emissive texture with a zero emissive factor; KHR_materials_iridescence's texture at
        factor 0: the GROWTH pack, work/bestiary/patches/material_ids_v2.md) so loaders bind them like any material map
        (the eidoverse engine converts exactly the textures a material holds) and a plain viewer shows nothing odd"""
        pbr = {'metallicFactor': 1.0 if orm is not None else 0.0, 'roughnessFactor': 1.0 if orm is not None else 0.5}
        if base is not None:
            pbr['baseColorTexture'] = {'index': base}
        if orm is not None:
            pbr['metallicRoughnessTexture'] = {'index': orm}
        m = {'name': name, 'pbrMetallicRoughness': pbr, 'doubleSided': double_sided}
        if orm is not None:
            m['occlusionTexture'] = {'index': orm}
        if normal is not None:
            m['normalTexture'] = {'index': normal}
        if emissive_tex is not None:
            m['emissiveTexture'] = {'index': emissive_tex}
            m['emissiveFactor'] = [0.0, 0.0, 0.0]
        if volume_tex is not None:
            m.setdefault('extensions', {})['KHR_materials_volume'] = {'thicknessFactor': 0.0,
                                                                      'thicknessTexture': {'index': volume_tex}}
            self.ext_used.add('KHR_materials_volume')
        if irid_tex is not None:
            # three's GLTFLoader binds iridescenceTexture to iridescenceMap and the thickness texture to
            # iridescenceThicknessMap whatever the factor; the runtime reads the pack's four channels itself
            m.setdefault('extensions', {})['KHR_materials_iridescence'] = {
                'iridescenceFactor': 0.0, 'iridescenceTexture': {'index': irid_tex},
                'iridescenceThicknessMinimum': 100.0, 'iridescenceThicknessMaximum': 400.0,
                'iridescenceThicknessTexture': {'index': irid_tex}}
            self.ext_used.add('KHR_materials_iridescence')
        if extras:
            m['extras'] = extras
        self.j['materials'].append(m)
        return len(self.j['materials']) - 1

    def node(self, name, T=None, R=None, mesh=None, skin=None, extras=None, parent=None, root=False):
        n = {'name': name}
        if T is not None:
            n['translation'] = [float(x) for x in T]
        if R is not None:
            n['rotation'] = [float(x) for x in R]
        if mesh is not None:
            n['mesh'] = mesh
        if skin is not None:
            n['skin'] = skin
        if extras:
            n['extras'] = extras
        self.j['nodes'].append(n)
        i = len(self.j['nodes']) - 1
        if parent is not None:
            self.j['nodes'][parent].setdefault('children', []).append(i)
        if root:
            self.j['scenes'][0]['nodes'].append(i)
        return i

    def skeleton(self, sk):
        """the joints as nodes (local TRS from the rest world frames) and a skin; returns (skin index, joint nodes)"""
        nodes = []
        for i, name in enumerate(sk.names):
            L = sk.local(i)
            p = sk.parent[i]
            nodes.append(self.node(name, T=L[:3, 3], R=quat_from_matrix(L[:3, :3]),
                                   parent=None if p < 0 else nodes[p], root=p < 0))
        ibm = np.stack([np.linalg.inv(W).T.reshape(-1) for W in sk.world]).astype(np.float32)   # column-major
        acc = self.accessor(ibm, 'MAT4')
        self.j['skins'].append({'joints': nodes, 'inverseBindMatrices': acc, 'skeleton': nodes[0]})
        return len(self.j['skins']) - 1, nodes

    def mesh(self, name, V, N, TAN, UV, primitives, joints=None, weights=None):
        """one vertex set shared by primitives [(triangles (m, 3), material)]; UV in the forge's v-up convention"""
        a = {'POSITION': self.accessor(np.asarray(V, np.float32), 'VEC3', 34962, minmax=True),
             'NORMAL': self.accessor(np.asarray(N, np.float32), 'VEC3', 34962),
             'TANGENT': self.accessor(np.asarray(TAN, np.float32), 'VEC4', 34962),
             'TEXCOORD_0': self.accessor(np.column_stack([UV[:, 0], 1.0 - UV[:, 1]]).astype(np.float32), 'VEC2',
                                         34962)}
        if joints is not None:
            a['JOINTS_0'] = self.accessor(np.asarray(joints, np.uint16), 'VEC4', 34962)
            a['WEIGHTS_0'] = self.accessor(np.asarray(weights, np.float32), 'VEC4', 34962)
        prims = [{'attributes': dict(a), 'indices': self.accessor(np.asarray(F, np.uint32).reshape(-1), 'SCALAR',
                                                                  34963), 'material': m, 'mode': 4}
                 for F, m in primitives]
        self.j['meshes'].append({'name': name, 'primitives': prims})
        return len(self.j['meshes']) - 1

    def save(self, path, extras=None):
        if extras:
            self.j['extras'] = extras
        if self.ext_used:
            self.j['extensionsUsed'] = sorted(self.ext_used)
            req = sorted(self.ext_used & {'EXT_texture_webp'})          # a viewer may ignore volume, never webp
            if req:
                self.j['extensionsRequired'] = req
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


def read(path):
    """parse a .glb: the JSON and an accessor reader (for verifying what was shipped)"""
    with open(path, 'rb') as f:
        data = f.read()
    magic, ver, total = struct.unpack_from('<III', data, 0)
    assert magic == 0x46546C67 and ver == 2 and total == len(data)
    jl, jt = struct.unpack_from('<II', data, 12)
    j = json.loads(data[20:20 + jl])
    bl, bt = struct.unpack_from('<II', data, 20 + jl)
    b = data[28 + jl:28 + jl + bl]

    def acc(i):
        a = j['accessors'][i]
        n = _NCOMP[a['type']]
        if 'bufferView' in a:
            v = j['bufferViews'][a['bufferView']]
            arr = np.frombuffer(b, dtype=_NP[a['componentType']], count=a['count'] * n,
                                offset=v.get('byteOffset', 0) + a.get('byteOffset', 0))
        else:                                                   # no data of its own: zeros (glTF 2.0)
            arr = np.zeros(a['count'] * n, _NP[a['componentType']])
        if 'sparse' in a:
            s = a['sparse']
            vi, vv = j['bufferViews'][s['indices']['bufferView']], j['bufferViews'][s['values']['bufferView']]
            idx = np.frombuffer(b, dtype=_NP[s['indices']['componentType']], count=s['count'],
                                offset=vi.get('byteOffset', 0) + s['indices'].get('byteOffset', 0))
            val = np.frombuffer(b, dtype=_NP[a['componentType']], count=s['count'] * n,
                                offset=vv.get('byteOffset', 0) + s['values'].get('byteOffset', 0))
            arr = arr.copy().reshape(a['count'], n)
            arr[idx] = val.reshape(-1, n)
            arr = arr.reshape(-1)
        return arr.reshape(a['count'], n) if n > 1 else arr
    return dict(json=j, accessor=acc, bin=b)
