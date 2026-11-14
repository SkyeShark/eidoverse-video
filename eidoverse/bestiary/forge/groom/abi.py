"""THE COAT ABI WRITER: GLB.coat_mesh (WOLF_PLAN §5.4 "Card ABI", HAIR_STUDY §9.4), and its verifier.

A coat glb holds the BASE'S OWN SKELETON (every joint node of the base, same names, same local TRS, same order in the
skin, the base's inverse bind matrices copied byte for byte), so the runtime binds the coat's SkinnedMesh to the base's
Skeleton directly, and one mesh `coat` with one primitive per base texture set (the root colour and the remix masks are
read from that set's maps at the root uv):

  POSITION   vec3 f32   bind pose, metres
  NORMAL     vec3 f32   the root's skin normal (bind pose): cards shade with the base normal, never their own
  TANGENT    vec4 f32   the strand direction at the vertex (the card's spine), w = 1 (skinned by three for free)
  JOINTS_0   vec4 u16   the root triangle's skin weights, one vector per card (base.tri_weights)
  WEIGHTS_0  vec4 f32
  _FURDATA   vec4 f32   (strandRandom 0..1, rootToTip 0..1, side -1..1, flex 0..1)
  _ROOTDATA  vec4 f32   (root u, root v: the base set's glTF uv; the base maps' mip for the card's footprint;
                        rank * 32 + tile)
  _FURCENTER vec3 f32   the card's centreline point at this row (the width floor's centre)

The three custom attributes are INTERLEAVED in ONE bufferView (byteStride 44: _FURDATA @0, _ROOTDATA @16,
_FURCENTER @32). three r184's GLTFLoader turns accessors sharing a strided view into one InterleavedBuffer, and its
WebGPU backend keys vertex buffers by that buffer, so the coat binds 6 of WebGPU's 8 vertex buffers (WOLF_PLAN §5.4,
read from the r184 source). There is NO TEXCOORD_0: atlas uv = (tile.u0 + (side + 1) / 2 (tile.u1 - tile.u0),
tile.v0 + rootToTip (tile.v1 - tile.v0)), tile = rootdata.w mod 32, rank = floor(rootdata.w / 32). GLTFLoader lowercases
custom attribute names (_furdata, _rootdata, _furcenter).

Cards are sorted by (primitive, rank): LOD k draws the first prefix_by_rank[R - 1 - k] indices of each primitive
(geometry.setDrawRange); the manifest carries the tables.

Materials (one per primitive): alphaMode MASK at the base threshold, double sided, the coverage page as the base colour
texture (atlas v1: in R and A; v2 and later: ONE grey channel, which loaders expand to R = G = B with A = 1, and coat.js
reads R), the attribute page in the emissive slot at factor 0 (the forge's way of carrying a data map in a standard slot,
so loaders bind it like any map). Atlas v3 (coat round 3) writes the attribute page as RGB with NO alpha channel (R depth,
G the lock's id + a per-strand offset, B the sideways slope): the engine's glTF image path divides an RGBA page's colour
by its alpha (Deno 2.8, work/bestiary/patches/scratch_decode/NOTES.md), which corrupted v1 / v2's page (A = sideways)
in every engine shot.
"""
import io
import json
import struct

import numpy as np

from ..gltf import GLB
from .base import read_glb

ABI_VERSION = 1
STRIDE = 44


class CoatGLB(GLB):
    def interleaved(self, arrays, kinds, target=34962):
        """float32 arrays (n, k_i) packed row by row into ONE bufferView with byteStride = sum of the row sizes;
        returns one accessor per array (byteOffset into the row)"""
        n = len(arrays[0])
        rows = np.concatenate([np.asarray(a, np.float32).reshape(n, -1) for a in arrays], axis=1)
        stride = rows.shape[1] * 4
        assert stride % 4 == 0 and stride <= 252
        view = self._view(np.ascontiguousarray(rows).tobytes(), target)
        self.j['bufferViews'][view]['byteStride'] = stride
        accs = []
        off = 0
        for a, kind in zip(arrays, kinds):
            a = np.asarray(a, np.float32).reshape(n, -1)
            acc = {'bufferView': view, 'byteOffset': off, 'componentType': 5126, 'count': int(n), 'type': kind,
                   'min': a.min(0).astype(float).tolist(), 'max': a.max(0).astype(float).tolist()}
            self.j['accessors'].append(acc)
            accs.append(len(self.j['accessors']) - 1)
            off += a.shape[1] * 4
        return accs, stride

    def copy_skeleton(self, base):
        """the base's joint nodes (names, local TRS as written) in the base's skin order, and a skin with the base's
        inverse bind matrices copied; returns (skin index, base node index -> new node index)"""
        bj = base.json
        joints = list(base.skin['joints'])
        jset = set(joints)
        newi = {}
        order = []                                            # parents before children
        seen = set()

        def visit(i):
            if i in seen:
                return
            p = int(base.node_parent[i])
            if p >= 0 and p in jset:
                visit(p)
            seen.add(i)
            order.append(i)
        for nd in joints:
            visit(nd)
        for i in order:
            src = bj['nodes'][i]
            n = {'name': src.get('name', f'node{i}')}
            for k in ('translation', 'rotation', 'scale', 'matrix'):
                if k in src:
                    n[k] = src[k]
            self.j['nodes'].append(n)
            newi[i] = len(self.j['nodes']) - 1
            p = int(base.node_parent[i])
            if p >= 0 and p in newi:
                self.j['nodes'][newi[p]].setdefault('children', []).append(newi[i])
            else:
                self.j['scenes'][0]['nodes'].append(newi[i])
        # the inverse bind matrices: the base's accessor bytes, verbatim
        ibm = base._acc(base.skin['inverseBindMatrices']).astype(np.float32).reshape(-1, 16)
        acc = self.accessor(ibm, 'MAT4')
        skin = {'joints': [newi[i] for i in joints], 'inverseBindMatrices': acc}
        if 'skeleton' in base.skin:
            skin['skeleton'] = newi.get(base.skin['skeleton'], newi[joints[0]])
        self.j['skins'].append(skin)
        return len(self.j['skins']) - 1, newi

    def png(self, img, mode=None):
        from PIL import Image
        buf = io.BytesIO()
        Image.fromarray(np.asarray(img, np.uint8), mode).save(buf, 'PNG', optimize=False, compress_level=6)
        view = self._view(buf.getvalue())
        self.j['images'].append({'bufferView': view, 'mimeType': 'image/png'})
        self.j['textures'].append({'sampler': 0, 'source': len(self.j['images']) - 1})
        return len(self.j['textures']) - 1

    def coat_mesh(self, name, va, prim_materials):
        """the coat mesh in the ABI: va from Cards.vertex_arrays (sorted by primitive, rank), prim_materials one
        material index per va['prims'] entry"""
        a = {'POSITION': self.accessor(va['POSITION'].astype(np.float32), 'VEC3', 34962, minmax=True),
             'NORMAL': self.accessor(va['NORMAL'].astype(np.float32), 'VEC3', 34962),
             'TANGENT': self.accessor(va['TANGENT'].astype(np.float32), 'VEC4', 34962),
             'JOINTS_0': self.accessor(va['JOINTS_0'].astype(np.uint16), 'VEC4', 34962),
             'WEIGHTS_0': self.accessor(va['WEIGHTS_0'].astype(np.float32), 'VEC4', 34962)}
        (fd, rd, fc), stride = self.interleaved([va['furdata'], va['rootdata'], va['furcenter']],
                                                ['VEC4', 'VEC4', 'VEC3'])
        assert stride == STRIDE
        a['_FURDATA'], a['_ROOTDATA'], a['_FURCENTER'] = fd, rd, fc
        idx = va['index'].astype(np.uint32)
        view = self._view(idx.tobytes(), 34963)
        prims = []
        for p, mat in zip(va['prims'], prim_materials):
            acc = {'bufferView': view, 'byteOffset': int(p['index_start'] * 4), 'componentType': 5125,
                   'count': int(p['index_count']), 'type': 'SCALAR'}
            self.j['accessors'].append(acc)
            prims.append({'attributes': dict(a), 'indices': len(self.j['accessors']) - 1, 'material': mat, 'mode': 4})
        self.j['meshes'].append({'name': name, 'primitives': prims})
        return len(self.j['meshes']) - 1


def write_coat_glb(path, base, va, atlas_cov, atlas_attr, style_name, thr=0.34, extras=None, coat_packs=None,
                   runtime=None, shell_tile=None, atlas_version=1):
    """the coat glb for one style; atlas_cov (h, w) 0..1, atlas_attr (h, w, 4) 0..1; coat_packs {set name: RGBA uint8
    on that set's uv} embedded as textures (their indices go to runtime['coat_pack'] by base material name);
    runtime: the manifest coat.js reads, written to the glb's extras as bestiary.coat (g_runtime/ABI_RUNTIME.md §2).
    atlas_version 2 (coat round 2): the coverage page is ONE channel (an 8-bit greyscale PNG: loaders read it as
    R = G = B, A = 1; coat.js reads R), not repeated into RGBA. atlas_version 3 (coat round 3): the attribute page is an
    RGB PNG, no alpha channel (atlas_attr's first three channels: depth, the lock's id, sideways)"""
    g = CoatGLB(generator='eidoverse bestiary forge: groom')
    skin, _ = g.copy_skeleton(base)
    cov8 = (np.clip(atlas_cov, 0, 1) * 255 + 0.5).astype(np.uint8)
    if atlas_version >= 2:
        t_cov = g.png(cov8, 'L')
    else:
        # coverage in R (what coat.js reads) and in A (a plain viewer's MASK alpha)
        t_cov = g.png(np.stack([cov8, cov8, cov8, cov8], axis=-1), 'RGBA')
    a8 = (np.clip(atlas_attr, 0, 1) * 255 + 0.5).astype(np.uint8)
    t_attr = g.png(a8[..., :3], 'RGB') if atlas_version >= 3 else g.png(a8, 'RGBA')
    pack_idx = {}
    for sname, img in (coat_packs or {}).items():
        mname = base.json['materials'][base.set_material[base.sets.index(sname)]].get('name')
        pack_idx[mname] = g.png(np.asarray(img, np.uint8), 'RGBA')
    if runtime is not None:
        runtime = dict(runtime)
        if pack_idx:
            runtime['coat_pack'] = pack_idx
        if shell_tile is not None and 'shells' in runtime:
            runtime['shells'] = dict(runtime['shells'], tile=g.png((np.clip(shell_tile, 0, 1) * 255 + 0.5)
                                                                  .astype(np.uint8), 'RGBA'))
    mats = []
    for p in va['prims']:
        sname = base.sets[p['set']]
        m = {'name': f'coat_{sname}', 'alphaMode': 'MASK', 'alphaCutoff': float(thr), 'doubleSided': True,
             'pbrMetallicRoughness': {'baseColorTexture': {'index': t_cov}, 'metallicFactor': 0.0,
                                      'roughnessFactor': 0.8},
             'emissiveTexture': {'index': t_attr}, 'emissiveFactor': [0.0, 0.0, 0.0],
             'extras': {'bestiary': 'coat', 'set': sname,
                        'base_material': base.json['materials'][base.set_material[p['set']]].get('name'),
                        'style': style_name, 'abi': ABI_VERSION,
                        'slots': ('coverage = baseColorTexture R (one channel, true area coverage)' if atlas_version >= 2
                                  else 'coverage = baseColorTexture R (and A)') +
                                 ('; attributes = emissiveTexture (factor 0), RGB, no alpha: R depth behind the card '
                                  'plane (the clump\'s shape), G the lock\'s id + a small per-strand offset, B sideways '
                                  'slope' if atlas_version >= 3 else
                                  '; attributes = emissiveTexture (factor 0): R depth behind the card plane, G strand id, '
                                  'B root-to-tip, A sideways tangent')}}
        g.j['materials'].append(m)
        mats.append(len(g.j['materials']) - 1)
    mesh = g.coat_mesh('coat', va, mats)
    g.node('coat', mesh=mesh, skin=skin, root=True)
    ex = {'bestiary': dict(coat=runtime if runtime is not None else style_name, coat_style=style_name,
                           abi=ABI_VERSION, base=base.species, base_sha1=base.sha1, units='m', up='+Y', forward='+Z',
                           **(extras or {}))}
    size = g.save(path, extras=ex)
    return size


def verify_coat_glb(path, base, va):
    """read the glb back and check the ABI: returns a dict of checks (each True / False) and facts"""
    j, b, acc = read_glb(path)
    out = {}
    mesh = j['meshes'][0]
    prims = mesh['primitives']
    a0 = prims[0]['attributes']
    out['no_texcoord'] = all('TEXCOORD_0' not in p['attributes'] for p in prims)
    custom = [a0[k] for k in ('_FURDATA', '_ROOTDATA', '_FURCENTER')]
    views = {j['accessors'][i]['bufferView'] for i in custom}
    out['custom_share_one_view'] = len(views) == 1
    v = j['bufferViews'][views.pop()]
    out['custom_view_stride_44'] = v.get('byteStride') == STRIDE
    out['custom_offsets'] = [j['accessors'][i].get('byteOffset', 0) for i in custom] == [0, 16, 32]
    nviews = {j['accessors'][i]['bufferView'] for i in a0.values()}
    out['vertex_buffers'] = len(nviews)
    out['vertex_buffers_le_8'] = len(nviews) <= 8
    for k, src in (('POSITION', 'POSITION'), ('NORMAL', 'NORMAL'), ('TANGENT', 'TANGENT'), ('JOINTS_0', 'JOINTS_0'),
                   ('WEIGHTS_0', 'WEIGHTS_0'), ('_FURDATA', 'furdata'), ('_ROOTDATA', 'rootdata'),
                   ('_FURCENTER', 'furcenter')):
        got = acc(a0[k])
        out[f'roundtrip_{k}'] = bool(np.array_equal(got.astype(np.float64), va[src].astype(np.float64)))
    W = acc(a0['WEIGHTS_0']).astype(np.float64)
    out['weights_sum_1'] = bool(np.abs(W.sum(1) - 1).max() < 1e-4)
    skin = j['skins'][0]
    names = [j['nodes'][i]['name'] for i in skin['joints']]
    out['joint_order_equals_base'] = names == base.joint_names
    ibm = acc(skin['inverseBindMatrices']).reshape(-1, 16)
    bibm = base._acc(base.skin['inverseBindMatrices']).reshape(-1, 16)
    out['ibm_equal_base'] = bool(np.array_equal(ibm, bibm))
    # each joint node's local TRS equals the base's
    same = True
    for i_new, i_base in zip(skin['joints'], base.skin['joints']):
        nn, nb = j['nodes'][i_new], base.json['nodes'][i_base]
        for k in ('translation', 'rotation', 'scale', 'matrix'):
            if nn.get(k) != nb.get(k):
                same = False
    out['joint_trs_equal_base'] = same
    nv = len(va['POSITION'])
    out['indices_in_range'] = all(int(acc(p['indices']).max()) < nv for p in prims)
    out['index_counts'] = [int(j['accessors'][p['indices']]['count']) for p in prims]
    out['prefix_last_equals_count'] = all(pr['prefix_by_rank'][-1] == c for pr, c in
                                          zip(va['prims'], out['index_counts']))
    out['materials'] = [j['materials'][p['material']]['name'] for p in prims]
    # the runtime's manifest (extras bestiary.coat): ranks, primitives' prefix tables, coat packs that resolve
    rt = j.get('extras', {}).get('bestiary', {}).get('coat')
    if isinstance(rt, dict):
        out['runtime_manifest'] = True
        out['runtime_rank_index_end'] = all(
            rp['rank_index_end'][-1] == c and len(rp['rank_index_end']) == rt['ranks']
            and rp['base_material'] == j['materials'][p['material']]['extras']['base_material']
            for rp, c, p in zip(rt['primitives'], out['index_counts'], prims))
        out['runtime_coat_pack'] = all(0 <= i < len(j['textures']) for i in rt.get('coat_pack', {}).values())
        out['runtime_tiles'] = len(rt.get('atlas', {}).get('tiles', [])) <= 32
    out['ok'] = all(v for k, v in out.items() if isinstance(v, bool))
    return out
