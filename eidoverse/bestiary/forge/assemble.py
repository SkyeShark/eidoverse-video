"""ASSEMBLE (work/bestiary/research/CROSSBREED_DESIGN.md §3.1, §4; the lead's decisions 1, 2, 4, 7): a forge step,
CPU only, seconds. It reads a cached BASE glb and its forged PARTS and writes ONE glb per crossbreed, which the
runtime's create() loads as it loads any creature:

  * the base minus each part's NATIVE GROUP: its faces left out of their primitives' index buffers, the vertices only
    they used left out of their vertex sets (so nothing reads a dropped vertex: the runtime's fleshReach walks every
    vertex of a skinned primitive), its joints (the graft root's descendants, decision 2) and its sockets left out of
    the node tree;
  * plus each part: its joints under the graft ROOT (a kept base joint), its sockets, its skin primitive (its own
    vertex set: POSITION, NORMAL, TANGENT, TEXCOORD_0, JOINTS_0, WEIGHTS_0) in its own material on the PARTS ATLAS
    (decision 7; masks in KHR_materials_volume's thickness slot and the display in the emissive slot as t13 writes the
    skin's, the GRAFT pack in KHR_materials_sheen's colour and roughness slots at factor 0: §2.8), its geometric
    suckers (their own vertex set, COLOR_0) on the base's sucker material (one stacked template: no new texels);
  * ONE skin: the kept base joints in their order, then every part's joints; inverse binds the base's bytes for its
    joints and inv(bind) for the parts'; every primitive bound to it, JOINTS_0 uint16 and uint32 indices (§4.6);
  * the base's images, textures and samplers copied BYTE FOR BYTE (the base's sets untouched: G-R9);
  * the scene extras' bestiary.chains (C0b's records, the grafted chain's joints renamed, its cuts none, its anatomy
    and graft written: decision 4, the runtime reads chains from here) and bestiary.grafts (each part's ring record).

Nothing of the base is re-cut, re-baked or re-weighted: every kept vertex keeps its position, normal, tangent, UV and
(joint name, weight) pairs; only joint INDICES and vertex indices are renumbered (G-R9's terms).

(HX0, work/bestiary/human/hx0: the private copy of live cb61ba4b; staged as hx0/patches/assemble_multi.md) A base of
MANY meshes (the human's 13) goes through assemble_multi() below: assemble() routes it there and keeps its one-mesh path
(the octopus's M1a / M2 builds) exactly as it was. assemble_multi() drops the MESH NODES past a cut, keeps every mesh's
primitives, attributes, skin and materials whole, gives each part its own mesh and node, renumbers THE VRM MAP
(VRMC_vrm and its siblings) and rewrites the scene's RECORDS (rings, chains, regions, the human's face and twists).
"""
import io
import json
import struct

import numpy as np

_COMP = {np.dtype(np.float32): 5126, np.dtype(np.uint16): 5123, np.dtype(np.uint32): 5125, np.dtype(np.uint8): 5121,
         np.dtype(np.int8): 5120, np.dtype(np.int16): 5122}           # (HX0) the signed types: any glTF attribute kept whole
_NP = {5126: np.float32, 5123: np.uint16, 5125: np.uint32, 5121: np.uint8, 5120: np.int8, 5122: np.int16}
_NC = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}


def read_glb(path):
    with open(path, 'rb') as f:
        data = f.read()
    magic, ver, total = struct.unpack_from('<III', data, 0)
    assert magic == 0x46546C67 and ver == 2 and total == len(data)
    jl, _ = struct.unpack_from('<II', data, 12)
    j = json.loads(data[20:20 + jl])
    bl, _ = struct.unpack_from('<II', data, 20 + jl)
    return j, data[28 + jl:28 + jl + bl]


def accessor_array(j, b, i):
    a = j['accessors'][i]
    v = j['bufferViews'][a['bufferView']]
    n = _NC[a['type']]
    arr = np.frombuffer(b, dtype=_NP[a['componentType']], count=a['count'] * n,
                        offset=v.get('byteOffset', 0) + a.get('byteOffset', 0))
    return arr.reshape(a['count'], n) if n > 1 else arr


class _Bin:
    def __init__(self):
        self.bin = bytearray()
        self.views, self.accessors = [], []

    def view(self, data, target=None):
        while len(self.bin) % 4:
            self.bin.append(0)
        v = {'buffer': 0, 'byteOffset': len(self.bin), 'byteLength': len(data)}
        if target:
            v['target'] = target
        self.bin += data
        self.views.append(v)
        return len(self.views) - 1

    def accessor(self, arr, kind, target=None, minmax=False):
        arr = np.ascontiguousarray(arr)
        a = {'bufferView': self.view(arr.tobytes(), target), 'componentType': _COMP[arr.dtype],
             'count': int(arr.shape[0]), 'type': kind}
        if minmax:
            a['min'] = arr.reshape(len(arr), -1).min(0).astype(float).tolist()
            a['max'] = arr.reshape(len(arr), -1).max(0).astype(float).tolist()
        self.accessors.append(a)
        return len(self.accessors) - 1


def quat_from_matrix(R):
    from .gltf import quat_from_matrix as q
    return q(R)


def _encode(img, kind):
    """t13's encoding: PNG for data (normals, masks, packs), JPEG q94 4:4:4 for colour"""
    from PIL import Image
    buf = io.BytesIO()
    im = Image.fromarray(np.asarray(img, np.uint8))
    if kind == 'data':
        im.save(buf, 'PNG', optimize=False, compress_level=6)
        return buf.getvalue(), 'image/png'
    im.convert('RGB').save(buf, 'JPEG', quality=94, subsampling=0)
    return buf.getvalue(), 'image/jpeg'


def assemble(base_path, parts, out_path, chains=None, grafts=None, log=print):
    """base_path: the base glb; parts: [dict(
         name, root (the kept joint the part hangs from),
         native=dict(prims={material name: triangle positions in that primitive}, joints=[names], sockets=[names]),
         joints=[dict(name, parent, world (4x4 bind, the creature's frame))] parent-first,
         sockets=[dict(name, parent, T, extras)],
         mesh=dict(V, N, TAN (n, 4), UV (the forge's v up), F, J (n, 4) joint NAMES, W (n, 4)),
         material=dict(name, maps={albedo, normal, orm, masks, display, graft}, extras),
         suckers=None | dict(V, N, TAN, UV, COLOR (n, 4) linear, F, J names, W))].
    chains: the scene's bestiary.chains to write; grafts: the bestiary.grafts records. Returns the report (remaps for
    the gates)"""
    j, b = read_glb(base_path)
    if len(j.get('meshes', [])) > 1:                 # (HX0) a base of many meshes: assemble_multi (the one-mesh path below
        return assemble_multi(base_path, parts, out_path, chains=chains, grafts=grafts, log=log)   # stays as it was)
    J = json.loads(json.dumps(j))
    B = _Bin()
    nodes = j['nodes']
    name_of = [n.get('name', '') for n in nodes]
    idx_of = {n: i for i, n in enumerate(name_of)}
    # ---------------------------------------------------------------- the nodes: the native groups out, the parts in
    drop_nodes = set()
    for p in parts:
        for nm in p['native']['joints'] + p['native']['sockets']:
            drop_nodes.add(idx_of[nm])
    for i in list(drop_nodes):
        for c in nodes[i].get('children', []):
            assert c in drop_nodes, f'{name_of[i]}: a child {name_of[c]} not in the native group'
    keep_nodes = [i for i in range(len(nodes)) if i not in drop_nodes]
    new_of = {old: k for k, old in enumerate(keep_nodes)}
    out_nodes = []
    for old in keep_nodes:
        n = dict(nodes[old])
        if 'children' in n:
            ch = [new_of[c] for c in n['children'] if c in new_of]
            if ch:
                n['children'] = ch
            else:
                n.pop('children')
        out_nodes.append(n)
    world_of = {}
    for p in parts:
        for jt in p['joints']:
            world_of[jt['name']] = np.asarray(jt['world'], np.float64)
    added = {}
    for p in parts:
        Wroot = np.asarray(p['root_world'], np.float64)
        for jt in p['joints']:
            par = jt['parent']
            Wp = Wroot if par == p['root'] else world_of[par]
            Lc = np.linalg.inv(Wp) @ world_of[jt['name']]
            n = {'name': jt['name'], 'translation': [float(x) for x in Lc[:3, 3]],
                 'rotation': [float(x) for x in quat_from_matrix(Lc[:3, :3])]}
            out_nodes.append(n)
            k = len(out_nodes) - 1
            added[jt['name']] = k
            pk = new_of[idx_of[par]] if par in idx_of and idx_of[par] in new_of else added[par]
            out_nodes[pk].setdefault('children', []).append(k)
        for so in p.get('sockets', []):
            n = {'name': so['name'], 'translation': [float(x) for x in so['T']]}
            if so.get('extras'):
                n['extras'] = so['extras']
            out_nodes.append(n)
            k = len(out_nodes) - 1
            par = so['parent']
            pk = added[par] if par in added else new_of[idx_of[par]]
            out_nodes[pk].setdefault('children', []).append(k)
    J['nodes'] = out_nodes
    J['scenes'] = [dict(s, nodes=[new_of[i] for i in s['nodes'] if i in new_of]) for s in j['scenes']]
    # ---------------------------------------------------------------- the skin
    sk = j['skins'][0]
    ibm = accessor_array(j, b, sk['inverseBindMatrices'])
    keep_j = [k for k, nd in enumerate(sk['joints']) if nd not in drop_nodes]
    jmap = -np.ones(len(sk['joints']), np.int64)
    jmap[keep_j] = np.arange(len(keep_j))
    part_j = [jt['name'] for p in parts for jt in p['joints']]
    joint_names = [name_of[sk['joints'][k]] for k in keep_j] + part_j
    jidx = {n: k for k, n in enumerate(joint_names)}
    ibm_new = [ibm[keep_j]]
    for nm in part_j:
        ibm_new.append(np.linalg.inv(world_of[nm]).T.reshape(1, 16).astype(np.float32))
    skin = dict(sk, joints=[new_of[sk['joints'][k]] for k in keep_j] + [added[n] for n in part_j],
                inverseBindMatrices=B.accessor(np.concatenate(ibm_new).astype(np.float32), 'MAT4'))
    if 'skeleton' in sk:
        skin['skeleton'] = new_of[sk['skeleton']]
    J['skins'] = [skin]
    # ---------------------------------------------------------------- the base's primitives, the native faces out
    mats = [m['name'] for m in j['materials']]
    prims = j['meshes'][0]['primitives']
    drop_tris = {}
    for p in parts:
        for mname, tris in p['native']['prims'].items():
            drop_tris.setdefault(mname, set()).update(int(t) for t in tris)
    sets = {}                                  # vertex set (POSITION accessor) -> its primitives
    for k, pr in enumerate(prims):
        sets.setdefault(pr['attributes']['POSITION'], []).append(k)
    new_prims = [None] * len(prims)
    report = dict(sets={}, joints_before=len(sk['joints']), joints_after=len(joint_names), joint_names=joint_names,
                  dropped_tris={}, node_map={name_of[o]: n for o, n in new_of.items()})
    for pos_acc, pks in sets.items():
        Fs = {k: accessor_array(j, b, prims[k]['indices']).reshape(-1, 3).astype(np.int64) for k in pks}
        keepF = {}
        orig_used = np.zeros(j['accessors'][pos_acc]['count'], bool)
        used = np.zeros_like(orig_used)
        for k in pks:
            mname = mats[prims[k]['material']]
            m = np.ones(len(Fs[k]), bool)
            if mname in drop_tris:
                m[sorted(drop_tris[mname])] = False
            keepF[k] = m
            orig_used[Fs[k].ravel()] = True
            used[Fs[k][m].ravel()] = True
        # a vertex leaves only when the native faces were its only users (a vertex no primitive used stays)
        keepV = used | ~orig_used
        vmap = -np.ones(len(keepV), np.int64)
        vmap[keepV] = np.arange(int(keepV.sum()))
        attrs = prims[pks[0]]['attributes']
        new_attrs = {}
        for an, ai in attrs.items():
            arr = accessor_array(j, b, ai)[keepV]
            if an == 'JOINTS_0':
                W = accessor_array(j, b, attrs['WEIGHTS_0'])[keepV]
                Jm = jmap[arr.astype(np.int64)]
                assert not ((Jm < 0) & (W > 0)).any(), 'a kept vertex weighted on a dropped joint'
                arr = np.where(Jm < 0, 0, Jm).astype(np.uint16)
            new_attrs[an] = B.accessor(arr, j['accessors'][ai]['type'], 34962, minmax=(an == 'POSITION'))
        for k in pks:
            pr = dict(prims[k], attributes=dict(new_attrs))
            pr['indices'] = B.accessor(vmap[Fs[k][keepF[k]]].astype(np.uint32).reshape(-1), 'SCALAR', 34963)
            new_prims[k] = pr
            report['dropped_tris'][mats[prims[k]['material']]] = int((~keepF[k]).sum())
        report['sets'][pos_acc] = dict(prims=[mats[prims[k]['material']] for k in pks], vmap=vmap,
                                       kept=int(keepV.sum()), before=len(keepV))
    # ---------------------------------------------------------------- the images: the base's bytes, then the parts'
    images, textures = [], []
    for im in j['images']:
        v = j['bufferViews'][im['bufferView']]
        data = b[v.get('byteOffset', 0):v.get('byteOffset', 0) + v['byteLength']]
        images.append(dict(im, bufferView=B.view(bytes(data))))
    textures = [dict(t) for t in j.get('textures', [])]
    ext_used = set(j.get('extensionsUsed', []))

    def tex(img, kind):
        data, mime = _encode(img, kind)
        images.append({'bufferView': B.view(data), 'mimeType': mime})
        textures.append({'sampler': 0, 'source': len(images) - 1})
        return len(textures) - 1

    materials = [dict(m) for m in j['materials']]
    f32 = lambda a: np.ascontiguousarray(a, np.float32)
    for p in parts:
        mt = p['material']
        mp = mt['maps']
        # metallicFactor: the part's own (default 0). A part's ORM blue is DATA, not metalness (the graft's chitin
        # carries its clear coat's roughness there, as the beetle's glb does): at 1.0 a plain glTF viewer drew the
        # shells ~23 % metallic (up to ~49 %, the M2 seam check); the bestiary runtime reads the channels itself
        m = {'name': mt['name'], 'doubleSided': False,
             'pbrMetallicRoughness': {'metallicFactor': float(mt.get('metallic', 0.0)), 'roughnessFactor': 1.0,
                                      'baseColorTexture': {'index': tex(mp['albedo'], 'colour')},
                                      'metallicRoughnessTexture': {'index': tex(mp['orm'], 'colour')}}}
        m['occlusionTexture'] = {'index': m['pbrMetallicRoughness']['metallicRoughnessTexture']['index']}
        m['normalTexture'] = {'index': tex(mp['normal'], 'data')}
        ex = {}
        if 'display' in mp:
            m['emissiveTexture'] = {'index': tex(mp['display'], 'data')}
            m['emissiveFactor'] = [0.0, 0.0, 0.0]
        if 'masks' in mp:
            ex['KHR_materials_volume'] = {'thicknessFactor': 0.0, 'thicknessTexture': {'index': tex(mp['masks'], 'data')}}
            ext_used.add('KHR_materials_volume')
        if 'graft' in mp:
            tg = tex(mp['graft'], 'data')
            ex['KHR_materials_sheen'] = {'sheenColorFactor': [0.0, 0.0, 0.0], 'sheenColorTexture': {'index': tg},
                                         'sheenRoughnessFactor': 0.0, 'sheenRoughnessTexture': {'index': tg}}
            ext_used.add('KHR_materials_sheen')
        if ex:
            m['extensions'] = ex
        if mt.get('extras'):
            m['extras'] = mt['extras']
        materials.append(m)
        mi = len(materials) - 1
        ms = p['mesh']

        def skin_attrs(d):
            Jn = np.vectorize(lambda s: jidx[s] if s else 0)(np.asarray(d['J'], object)).astype(np.uint16)
            W = f32(d['W'])
            assert np.allclose(W.sum(1), 1.0, atol=1e-5), 'part weights do not sum to 1'
            a = {'POSITION': B.accessor(f32(d['V']), 'VEC3', 34962, minmax=True),
                 'NORMAL': B.accessor(f32(d['N']), 'VEC3', 34962),
                 'TANGENT': B.accessor(f32(d['TAN']), 'VEC4', 34962),
                 'TEXCOORD_0': B.accessor(f32(np.column_stack([d['UV'][:, 0], 1.0 - d['UV'][:, 1]])), 'VEC2', 34962)}
            if 'COLOR' in d:
                a['COLOR_0'] = B.accessor(f32(d['COLOR']), 'VEC4', 34962)
            a['JOINTS_0'] = B.accessor(Jn, 'VEC4', 34962)
            a['WEIGHTS_0'] = B.accessor(W, 'VEC4', 34962)
            return a
        new_prims.append({'attributes': skin_attrs(ms), 'indices': B.accessor(
            np.asarray(ms['F'], np.uint32).reshape(-1), 'SCALAR', 34963), 'material': mi, 'mode': 4})
        if p.get('suckers') is not None:
            su = p['suckers']
            smat = mats.index('octopus_suckers')
            new_prims.append({'attributes': skin_attrs(su), 'indices': B.accessor(
                np.asarray(su['F'], np.uint32).reshape(-1), 'SCALAR', 34963), 'material': smat, 'mode': 4})
    J['images'], J['textures'], J['materials'] = images, textures, materials
    J['meshes'] = [dict(j['meshes'][0], primitives=new_prims)]
    J['accessors'], J['bufferViews'] = B.accessors, B.views
    if ext_used:
        J['extensionsUsed'] = sorted(ext_used)
    ex = J.setdefault('extras', {}).setdefault('bestiary', {})
    if chains is not None:
        ex['chains'] = chains
    if grafts is not None:
        ex['grafts'] = grafts
    ex['joints'] = len(joint_names)
    while len(B.bin) % 4:
        B.bin.append(0)
    J['buffers'] = [{'byteLength': len(B.bin)}]
    js = json.dumps(J, separators=(',', ':')).encode()
    js += b' ' * ((4 - len(js) % 4) % 4)
    total = 12 + 8 + len(js) + 8 + len(B.bin)
    with open(out_path, 'wb') as f:
        f.write(struct.pack('<III', 0x46546C67, 2, total))
        f.write(struct.pack('<II', len(js), 0x4E4F534A) + js)
        f.write(struct.pack('<II', len(B.bin), 0x004E4942) + bytes(B.bin))
    report['bytes'] = total
    report['primitives'] = [(materials[pr['material']]['name'], len(pr['attributes'])) for pr in new_prims]
    log(f'[assemble] {out_path}: {total / 1e6:.1f} MB; joints {report["joints_before"]} -> {report["joints_after"]}; '
        f'primitives {report["primitives"]}; native faces left out {report["dropped_tris"]}')
    return report


def chain_records(spec, arms_order, tips, grafted=None):
    """C0b's eight arm chain records (patches/cyborg_c0_t13.md: slots.chain_record with octopus_rig's shares and
    octopus.arm_radius, the listed cuts 6 / 8 / 10 / 12 / 14, the tip sockets, sides and labels from the tips'
    azimuths), the GRAFTED chains rewritten (decision 4): their joints named as the assembled skin names them, no cuts
    (§4.3: a grafted chain lists none in v1), its anatomy (the donor's chain kind, which motion reads) and its graft
    (the part, the root, the ring record's place). grafted: {chain name: dict(joints, radius, s, part, root, cut)}"""
    from ..remix import slots as SL
    from .species import octopus as O
    from .species import octopus_rig as OR
    js = OR.arm_joint_s(spec)
    rad = O.arm_radius(js, spec)
    labels = {}
    for side in 'LR':
        on = sorted((k for k in tips if (tips[k][0] > 0) == (side == 'L')),
                    key=lambda k: abs(np.degrees(np.arctan2(tips[k][0], tips[k][2]))))
        labels.update({k: f'{side}{n + 1}' for n, k in enumerate(on)})
    out = []
    for k in sorted(tips):
        nm = f'arm{k}'
        g = (grafted or {}).get(nm)
        if g is None:
            rec = SL.chain_record(nm, 'tentacle', [f'{nm}_{q:02d}' for q in range(OR.N_ARM_JOINTS)], js, rad,
                                  [dict(joint=c, s=round(float(0.5 * (js[c - 1] + js[c])), 6)) for c in (6, 8, 10, 12, 14)],
                                  tip=f'socket_{nm}_tip', side=labels[k][0], label=labels[k])
            rec['anatomy'] = 'tentacle'
        else:
            rec = SL.chain_record(nm, 'tentacle', g['joints'], g['s'], g['radius'], [], tip=f'socket_{nm}_tip',
                                  side=labels[k][0], label=labels[k])
            rec['anatomy'] = 'tentacle'
            rec['graft'] = dict(part=g['part'], root=g['root'], cut=g['cut'], ring='extras.bestiary.grafts')
        out.append(rec)
    return out


# ============================================================================================ (HX0) a base of many meshes
# The human (work/bestiary/human/hx0; HUMAN_PLAN §10 HX0, the human grafted onto itself) is 13 meshes on ONE skin: the
# two skin meshes, the eyes (unskinned, under their eye joints), the mouth's three (a custom _MOUTH attribute), the six
# eye parts (_SHELL / _RING; two materials shared by six meshes, so a material cannot name a mesh). G-R9's terms hold as
# in the one-mesh path: every kept vertex keeps its attribute bits and its (joint name, weight) pairs, the base's images,
# textures, samplers and materials stay as written; only node, mesh, joint, vertex and triangle INDICES are renumbered.

def _write_like(B, j, b, ai, rows=None, arr=None, target=34962):
    """the base's accessor ai written again: its rows `rows` (None: all), or `arr` in its place, with the base's type,
    component type (unless arr's dtype differs: joints past 255) and normalized flag; min / max where the base had them,
    VERBATIM when every row is kept (so a null graft writes the base's own JSON)"""
    a = j['accessors'][ai]
    src = accessor_array(j, b, ai) if arr is None else arr
    if rows is not None:
        src = src[rows]
    if arr is None:
        src = np.ascontiguousarray(src, dtype=_NP[a['componentType']])
    k = B.accessor(np.ascontiguousarray(src), a['type'], target, minmax='min' in a)
    acc = B.accessors[k]
    if 'min' in a and (rows is None or bool(np.all(rows))) and arr is None:
        acc['min'], acc['max'] = list(a['min']), list(a['max'])
    if a.get('normalized'):
        acc['normalized'] = True
    return k


def _tri_set(native, mesh_name_list=None):
    """a native group's triangles as {(mesh name, primitive): set}, from its per-MESH lists (native['meshes'])"""
    out = {}
    for mn, d in (native.get('meshes') or {}).items():
        tris = d.get('triangles', []) if isinstance(d, dict) else d
        pi = int(d.get('prim', 0)) if isinstance(d, dict) else 0
        if len(tris):
            out[(mn, pi)] = set(int(t) for t in tris)
    return out


def _vrm_remap(J, new_of, added, name_of, parts, report):
    """THE VRM MAP after a graft (the brief's item 2): VRMC_vrm's node indices renumbered, the humanBones of dropped
    joints pruned, a part's own bones added (part['vrm_bones'] = {bone: joint name}), firstPerson annotations and
    expression morph binds renumbered or pruned (materials are only appended, so material indices stand); lookAt of
    type 'bone' needs both eye bones: without them it is reported (three-vrm's bone applier then has no eyes to turn).
    VRMC_springBone's and VRMC_node_constraint's node references are renumbered too, a spring joint or a constraint
    whose node left is pruned. The VRM 0.x 'VRM' extension is refused (the forge writes VRM 1.0, forge/vrm.py)."""
    ex = J.get('extensions') or {}
    assert 'VRM' not in ex, 'a VRM 0.x extension: the forge writes VRM 1.0 only'
    rep = dict(pruned=[], added=[], renumbered=0, expressions_pruned=[], first_person_pruned=[], look_at=None,
               springs_pruned=0, constraints_pruned=[])
    v = ex.get('VRMC_vrm')
    if v:
        hb = v.get('humanoid', {}).get('humanBones', {})
        for bone in list(hb):
            old = hb[bone]['node']
            if old in new_of:
                hb[bone] = dict(hb[bone], node=new_of[old])
                rep['renumbered'] += 1
            else:
                rep['pruned'].append(f'{bone}={name_of[old]}')
                del hb[bone]
        for p in parts:
            for bone, jn in (p.get('vrm_bones') or {}).items():
                assert bone not in hb, f'{p["name"]}: the humanBone {bone} is still held by a kept joint'
                hb[bone] = {'node': added[jn]}
                rep['added'].append(f'{bone}={jn}')
        fp = v.get('firstPerson')
        if fp and fp.get('meshAnnotations'):
            keep = []
            for a in fp['meshAnnotations']:
                if a['node'] in new_of:
                    keep.append(dict(a, node=new_of[a['node']]))
                else:
                    rep['first_person_pruned'].append(name_of[a['node']])
            fp['meshAnnotations'] = keep
        for grp in ('preset', 'custom'):
            for nm, e in (v.get('expressions', {}).get(grp) or {}).items():
                mb = e.get('morphTargetBinds')
                if mb:
                    keep = [dict(x, node=new_of[x['node']]) for x in mb if x['node'] in new_of]
                    if len(keep) != len(mb):
                        rep['expressions_pruned'].append(f'{grp}.{nm}: {len(mb) - len(keep)} morph binds')
                    e['morphTargetBinds'] = keep
        la = v.get('lookAt')
        if la and la.get('type') == 'bone':
            missing = [b_ for b_ in ('leftEye', 'rightEye') if b_ not in hb]
            rep['look_at'] = f'type bone, eye bones missing: {missing}' if missing else 'type bone, both eyes kept'
    sb = ex.get('VRMC_springBone')
    if sb:
        for c in sb.get('colliders', []):
            assert c['node'] in new_of, 'a spring collider on a dropped node (prune it with its group)'
            c['node'] = new_of[c['node']]
        for s in sb.get('springs', []):
            js = [dict(x, node=new_of[x['node']]) for x in s.get('joints', []) if x['node'] in new_of]
            rep['springs_pruned'] += len(s.get('joints', [])) - len(js)
            s['joints'] = js
            if 'center' in s:
                s['center'] = new_of.get(s['center'], s['center'])
    for k, n in enumerate(J['nodes']):
        nc = (n.get('extensions') or {}).get('VRMC_node_constraint')
        if not nc:
            continue
        for kind, c in nc.get('constraint', {}).items():
            if c['source'] in new_of:
                c['source'] = new_of[c['source']]
            else:
                rep['constraints_pruned'].append(n.get('name', ''))
                n['extensions'].pop('VRMC_node_constraint')
                break
    report['vrm'] = rep


def _rewrite_records(J, j, parts, report, part_meshes, mesh_material):
    """THE RECORDS after a graft (extras.bestiary; CROSSBREED §2.11, §4.3 and the lead's decision 4):
      * the grafted ring (part['ring']) leaves bestiary.rings for bestiary.grafts, with the part that took its place;
      * a ring whose native group is DISJOINT from the graft's keeps its lists, renumbered through the new triangle
        indices; one INSIDE it (a nail on the hand) leaves with the native group, unless the part re-makes it
        (part['rings'], in the part's own mesh); one that CONTAINS it (the elbow's group holds the hand) trades the
        graft's native for the part: its mesh's triangles, its joints, sockets and node. Any other overlap is an error:
        the rings nest or keep apart, by the cage's construction;
      * the chain through the grafted ring: the grafted cut and every cut past it leave (one replacement per chain, §4.3),
        the cuts before it stay (the elbow's ring now holds the part, so a later graft there takes both), and the chain
        gains `graft` and `anatomy`; its joints and tip as the part names them (part['chain'], else as they were);
      * regions, the human's face and twist records keep only joints that exist; a face whose joints left goes whole.
    """
    bx = (J.get('extras') or {}).get('bestiary')
    if not bx:
        return
    rep = dict(grafted=[], dropped=[], remade=[], contains={}, remapped=0, chains=[], regions={}, human={})
    tmaps = report['tri_maps']
    joint_set = set(report['joint_names'])
    node_names = {n.get('name', '') for n in J['nodes']}
    grafted_names = {p['ring'] for p in parts if p.get('ring')}
    G = {p['ring']: _tri_set(p['native']) for p in parts if p.get('ring')}
    out_rings = []
    for r in bx.get('rings', []):
        if r['name'] in grafted_names:
            continue
        S = _tri_set(r['native'])
        nat = json.loads(json.dumps(r['native']))
        inside_of = None
        for p in parts:
            if not p.get('ring'):
                continue
            Gs = G[p['ring']]
            inter = sum(len(S.get(k, set()) & Gs.get(k, set())) for k in S)
            if not inter:
                continue
            if all(S[k] <= Gs.get(k, set()) for k in S):
                inside_of = p
                break
            if all(Gs[k] <= S.get(k, set()) for k in Gs):           # r contains the graft: its native trades for the part
                for k in Gs:
                    S[k] = S[k] - Gs[k]
                nat['joints'] = [x for x in nat['joints'] if x not in set(p['native'].get('joints', []))]
                nat['joints'] += [jt['name'] for jt in p.get('joints', []) if jt['name'] not in nat['joints']]
                if set(nat['joints']) == set(r['native']['joints']):
                    nat['joints'] = list(r['native']['joints'])
                socks = _socket_names(p.get('sockets', []))
                nat['sockets'] = [x for x in nat['sockets'] if x not in set(p['native'].get('sockets', []))]
                nat['sockets'] += [s for s in socks if s not in nat['sockets']]
                if set(nat['sockets']) == set(r['native']['sockets']):
                    nat['sockets'] = list(r['native']['sockets'])
                nat['nodes'] = [x for x in nat.get('nodes', []) if x not in set(p['native'].get('nodes', []))]
                if p.get('node'):
                    nat['nodes'].append(p['node']['name'])
                rep['contains'].setdefault(r['name'], []).append(p['name'])
                continue
            raise AssertionError(f'ring {r["name"]}: its native group overlaps {p["ring"]}\'s without nesting')
        if inside_of is not None:
            rep['dropped'].append(f'{r["name"]} (inside {inside_of["ring"]})')
            continue
        # the lists renumbered (the base's meshes), then the parts' meshes for a containing ring
        meshes = {}
        for mn, d in nat.get('meshes', {}).items():
            pi = int(d.get('prim', 0)) if isinstance(d, dict) else 0
            tris = sorted(S.get((mn, pi), set()))
            tm = tmaps.get((mn, pi))
            if tm is None:
                assert not tris, f'ring {r["name"]}: triangles on the dropped mesh {mn}'
                continue                                        # a mesh left out whole: it leaves the record
            new = tm[np.asarray(tris, np.int64)] if tris else np.zeros(0, np.int64)
            assert (new >= 0).all(), f'ring {r["name"]}: a listed triangle was dropped'
            nd = dict(d) if isinstance(d, dict) else {}
            nd['triangles'] = new.tolist()
            if 'of' in nd:
                nd['of'] = int((tm >= 0).sum())
            meshes[mn] = nd
        for p in parts:
            if r['name'] in rep['contains'] and p['name'] in rep['contains'][r['name']] and p.get('node'):
                pm = part_meshes[p['name']]
                meshes[pm['mesh']] = dict(material=pm['material'], triangles=list(range(pm['triangles'])),
                                          of=pm['triangles'], part=p['name'])
        nat['meshes'] = meshes
        prims = {}
        for mn, d in meshes.items():
            if d['triangles'] and mesh_material.get(mn):
                prims.setdefault(mesh_material[mn], []).extend(d['triangles'])
        nat['prims'] = prims
        rr = dict(r, native=nat)
        out_rings.append(rr)
        rep['remapped'] += 1
    for p in parts:
        for rr in p.get('rings') or []:
            out_rings.append(rr)
            rep['remade'].append(f'{rr["name"]} (on {p["name"]})')
    bx['rings'] = out_rings
    grafts = list(bx.get('grafts') or [])
    for p in parts:
        if not p.get('ring'):
            continue
        rec = next((r for r in j['extras']['bestiary'].get('rings', []) if r['name'] == p['ring']), None)
        g = dict(part=p['name'], ring=p['ring'], root=p.get('root'), node=(p.get('node') or {}).get('name'),
                 kind=p.get('kind', 'identity'), record=rec)
        g.update(p.get('graft_record') or {})
        grafts.append(g)
        rep['grafted'].append(f'{p["ring"]} -> {p["name"]}')
    if grafts or 'grafts' in bx:
        bx['grafts'] = grafts
    # the chains through a grafted ring
    out_chains = []
    for c in bx.get('chains', []):
        c2 = json.loads(json.dumps(c))
        for p in parts:
            cut = next((u for u in c.get('cuts', []) if u.get('ring') == p.get('ring')), None)
            if cut is None:
                continue
            c2['cuts'] = [u for u in c2.get('cuts', []) if u['joint'] < cut['joint']]
            pc = p.get('chain') or {}
            for k in ('joints', 's', 'radius', 'tip'):
                if k in pc:
                    c2[k] = pc[k]
            c2['anatomy'] = pc.get('anatomy', c.get('anatomy', c['kind']))
            c2['graft'] = dict(part=p['name'], root=p.get('root'), cut=p['ring'], ring='extras.bestiary.grafts')
            if 'joints' not in pc and any(x not in joint_set for x in c2['joints']) and p.get('root') in c2['joints']:
                n_keep = c2['joints'].index(p['root']) + 1           # no part names the chain past its root: a stump
                for k in ('joints', 's', 'radius'):
                    if k in c2:
                        c2[k] = c2[k][:n_keep]
                c2['anatomy'] = pc.get('anatomy', 'stump')
            rep['chains'].append(f'{c["name"]}: cuts {[u["ring"] for u in c.get("cuts", [])]} -> '
                                 f'{[u["ring"] for u in c2["cuts"]]}, graft {p["name"]}, joints {len(c2["joints"])}')
        missing = [x for x in c2['joints'] if x not in joint_set]
        assert not missing, f'chain {c["name"]}: joints {missing} left with no part naming them (part["chain"])'
        if c2.get('tip') and c2['tip'] not in node_names:
            rep['chains'].append(f'{c["name"]}: tip {c2["tip"]} left: none')
            c2['tip'] = None
        out_chains.append(c2)
    bx['chains'] = out_chains
    for rg in bx.get('regions', []):
        keep = [x for x in rg.get('joints', []) if x in joint_set]
        if len(keep) != len(rg.get('joints', [])):
            rep['regions'][rg['name']] = len(rg['joints']) - len(keep)
            rg['joints'] = keep
    hu = bx.get('human')
    if hu:
        face = hu.get('face')
        if face and any(x not in joint_set for x in face.get('joints', [])):
            hu.pop('face')
            rep['human']['face'] = 'left whole: its joints left'
        tw = hu.get('twists')
        if tw:
            bad = [k for k, d in tw.items() if any(x not in joint_set for x in (k, d.get('source'), d.get('axis_bone'),
                                                                                d.get('axis_to')) if x)]
            for k in bad:
                tw.pop(k)
            if bad:
                rep['human']['twists_pruned'] = bad
    report['records'] = rep


def _socket_names(socks):
    out = []
    for s in socks:
        out.append(s['name'])
        out += _socket_names(s.get('children', []))
    return out


def assemble_multi(base_path, parts, out_path, chains=None, grafts=None, log=print):
    """(HX0) ASSEMBLE on a base of MANY meshes (the human's 13), each kept WHOLE but for its native faces.
    parts: [dict(
        name, root (the kept joint the part hangs from), root_world (4x4), ring (the grafted ring's name, or None),
        native=dict(joints, sockets, nodes (the MESH NODES past the cut), meshes={mesh name: {'triangles': [...]}}),
        joints=[dict(name, parent, world (4x4 bind), local (optional: the node's TRS verbatim), ibm (optional: 16
                floats verbatim))] parent-first,
        sockets=[dict(name, parent, node (a glTF node's TRS + extras, verbatim), children=[the same])],
        node=dict(name, parent (a kept node: the skinned meshes' parent)): the part's OWN mesh node, skinned to the skin,
        mesh=dict(V, N, TAN (n, 4), UV (v up) or UV_gltf (v down, verbatim), F, J (n, 4) joint NAMES, W (n, 4)),
        material=dict(name, json (a glTF material whose texture 'index' values are '@key'), images={key: (bytes, mime)}),
        vrm_bones={humanBone: joint name} (optional), rings=[ring records re-made on the part] (optional),
        chain=dict(joints, s, radius, tip, anatomy) (optional), graft_record={...} (optional))].
    chains / grafts: as assemble()'s (written over the rewritten records when given). Returns the report."""
    j, b = read_glb(base_path)
    J = json.loads(json.dumps(j))
    B = _Bin()
    nodes = j['nodes']
    name_of = [n.get('name', '') for n in nodes]
    idx_of = {n: i for i, n in enumerate(name_of)}
    assert len(idx_of) == len(nodes), 'node names must be unique: ASSEMBLE names everything by them'
    meshes = j.get('meshes', [])
    mesh_name = [m.get('name', f'mesh{k}') for k, m in enumerate(meshes)]
    mesh_idx = {n: k for k, n in enumerate(mesh_name)}
    assert len(mesh_idx) == len(meshes), 'mesh names must be unique: native groups name meshes'
    mats = [m.get('name', '') for m in j.get('materials', [])]
    users = {}
    for i, n in enumerate(nodes):
        if 'mesh' in n:
            users.setdefault(n['mesh'], []).append(i)
    report = dict(sets={}, tri_maps={}, vmaps={}, dropped=dict(joints=[], sockets=[], nodes=[], meshes=[], other=[]),
                  auto_dropped=[], parts=[p['name'] for p in parts])
    # ---------------------------------------------------------------- what the native groups take
    drop_nodes = set()
    drop_tris = {}
    for p in parts:
        nat = p['native']
        for nm in list(nat.get('joints', [])) + list(nat.get('sockets', [])) + list(nat.get('nodes', [])):
            assert nm in idx_of, f'{p["name"]}: its native group names {nm}: no such node'
            drop_nodes.add(idx_of[nm])
        if 'meshes' in nat:
            for (mn, pi), tris in _tri_set(nat).items():
                assert mn in mesh_idx, f'{p["name"]}: no mesh {mn}'
                drop_tris.setdefault((mesh_idx[mn], pi), set()).update(tris)
        else:                                                    # the one-mesh form: per material on mesh 0
            for mname, tris in nat.get('prims', {}).items():
                pi = next(k for k, pr in enumerate(meshes[0]['primitives']) if mats[pr['material']] == mname)
                drop_tris.setdefault((0, pi), set()).update(int(t) for t in tris)
    gone_mesh = {mi for mi, us in users.items() if all(u in drop_nodes for u in us)}
    # ---------------------------------------------------------------- the skin
    assert len(j.get('skins', [])) == 1, 'one skin per creature (DESIGN.md: one skeleton)'
    sk = j['skins'][0]
    ibm = accessor_array(j, b, sk['inverseBindMatrices'])
    keep_j = [k for k, nd in enumerate(sk['joints']) if nd not in drop_nodes]
    jmap = -np.ones(len(sk['joints']), np.int64)
    jmap[keep_j] = np.arange(len(keep_j))
    part_j = [jt['name'] for p in parts for jt in p.get('joints', [])]
    joint_names = [name_of[sk['joints'][k]] for k in keep_j] + part_j
    assert len(set(joint_names)) == len(joint_names), 'a part joint takes the name of a kept joint'
    jidx = {n: k for k, n in enumerate(joint_names)}
    report.update(joints_before=len(sk['joints']), joints_after=len(joint_names), joint_names=joint_names)
    # ---------------------------------------------------------------- every kept mesh, every attribute whole
    sets = {}
    for mi, m in enumerate(meshes):
        if mi in gone_mesh:
            continue
        for pi, pr in enumerate(m['primitives']):
            assert pr.get('mode', 4) == 4 and 'indices' in pr, f'{mesh_name[mi]}: indexed triangles only'
            sets.setdefault(pr['attributes']['POSITION'], []).append((mi, pi))
    new_prim = {}
    for pos_acc, pks in sets.items():
        attrs = meshes[pks[0][0]]['primitives'][pks[0][1]]['attributes']
        assert all(meshes[mi]['primitives'][pi]['attributes'] == attrs for mi, pi in pks), \
            'primitives sharing a vertex set share every attribute'
        Fs = {k: accessor_array(j, b, meshes[k[0]]['primitives'][k[1]]['indices']).reshape(-1, 3).astype(np.int64)
              for k in pks}
        n_v = j['accessors'][pos_acc]['count']
        orig_used, used, keepF = np.zeros(n_v, bool), np.zeros(n_v, bool), {}
        for k in pks:
            mk = np.ones(len(Fs[k]), bool)
            if k in drop_tris:
                mk[sorted(drop_tris[k])] = False
            keepF[k] = mk
            orig_used[Fs[k].ravel()] = True
            used[Fs[k][mk].ravel()] = True
        keepV = used | ~orig_used                    # a vertex leaves only when native faces were its only users
        vmap = -np.ones(n_v, np.int64)
        vmap[keepV] = np.arange(int(keepV.sum()))
        whole = bool(keepV.all())
        rows = None if whole else keepV
        new_attrs = {}
        if keepV.any():
            for an, ai in attrs.items():
                if an.startswith('JOINTS_'):
                    J0 = accessor_array(j, b, ai)[keepV].astype(np.int64)
                    W0 = accessor_array(j, b, attrs['WEIGHTS_' + an.split('_', 1)[1]])[keepV]
                    Jm = jmap[J0]
                    assert not ((Jm < 0) & (W0 > 0)).any(), f'{mesh_name[pks[0][0]]}: a kept vertex weighted on a dropped joint'
                    dt = _NP[j['accessors'][ai]['componentType']]
                    if len(joint_names) - 1 > np.iinfo(dt).max:
                        dt = np.uint16
                    new_attrs[an] = _write_like(B, j, b, ai, arr=np.where(Jm < 0, 0, Jm).astype(dt))
                else:
                    new_attrs[an] = _write_like(B, j, b, ai, rows=rows)
        for k in pks:
            pr = meshes[k[0]]['primitives'][k[1]]
            tm = -np.ones(len(Fs[k]), np.int64)
            tm[keepF[k]] = np.arange(int(keepF[k].sum()))
            report['tri_maps'][(mesh_name[k[0]], k[1])] = tm
            report['vmaps'][(mesh_name[k[0]], k[1])] = vmap
            if not keepF[k].any():
                new_prim[k] = None
                continue
            q = dict(pr, attributes=dict(new_attrs))
            q['indices'] = B.accessor(vmap[Fs[k][keepF[k]]].astype(np.uint32).reshape(-1), 'SCALAR', 34963)
            if pr.get('targets'):
                q['targets'] = [{an: _write_like(B, j, b, ai, rows=rows) for an, ai in t.items()} for t in pr['targets']]
            new_prim[k] = q
        report['sets'][pos_acc] = dict(prims=[f'{mesh_name[mi]}[{pi}]' for mi, pi in pks], vmap=vmap,
                                       kept=int(keepV.sum()), before=n_v)
    out_meshes, new_mesh = [], {}
    for mi, m in enumerate(meshes):
        if mi in gone_mesh:
            report['dropped']['meshes'].append(mesh_name[mi])
            continue
        prims = [new_prim[(mi, pi)] for pi in range(len(m['primitives'])) if new_prim[(mi, pi)] is not None]
        if not prims:                        # every face native (the HEAD at the neck): the mesh leaves with its nodes
            report['dropped']['meshes'].append(mesh_name[mi])
            for u in users.get(mi, []):
                drop_nodes.add(u)
                report['auto_dropped'].append(name_of[u])
            continue
        new_mesh[mi] = len(out_meshes)
        out_meshes.append(dict(m, primitives=prims))
    report['mesh_map'] = {mesh_name[mi]: k for mi, k in new_mesh.items()}
    # ---------------------------------------------------------------- the nodes: the native groups out, the parts in
    for i in list(drop_nodes):
        for c in nodes[i].get('children', []):
            assert c in drop_nodes, f'{name_of[i]}: a child {name_of[c]} not in the native group'
    skin_nodes = set(sk['joints'])
    for i in sorted(drop_nodes):
        kind = 'joints' if i in skin_nodes else 'nodes' if 'mesh' in nodes[i] else \
            'sockets' if name_of[i].startswith(('socket_', 'seat_')) else 'other'
        report['dropped'][kind].append(name_of[i])
    keep_nodes = [i for i in range(len(nodes)) if i not in drop_nodes]
    new_of = {old: k for k, old in enumerate(keep_nodes)}
    out_nodes = []
    for old in keep_nodes:
        n = json.loads(json.dumps(nodes[old]))
        if 'children' in n:
            ch = [new_of[c] for c in n['children'] if c in new_of]
            if ch:
                n['children'] = ch
            else:
                n.pop('children')
        if 'mesh' in n:
            n['mesh'] = new_mesh[n['mesh']]
        out_nodes.append(n)
    world_of = {jt['name']: np.asarray(jt['world'], np.float64) for p in parts for jt in p.get('joints', [])}
    added = {}

    def add_node(nd, parent_name):
        out_nodes.append(nd)
        k = len(out_nodes) - 1
        added[nd['name']] = k
        pk = added[parent_name] if parent_name in added else new_of[idx_of[parent_name]]
        out_nodes[pk].setdefault('children', []).append(k)
        return k

    def add_socket(so, parent_name):
        nd = {'name': so['name']}
        nd.update({k: v for k, v in (so.get('node') or {}).items() if k not in ('name', 'children', 'mesh', 'skin')})
        if 'node' not in so and 'T' in so:
            nd['translation'] = [float(x) for x in so['T']]
            if so.get('extras'):
                nd['extras'] = so['extras']
        add_node(nd, parent_name)
        for c in so.get('children', []):
            add_socket(c, so['name'])

    for p in parts:
        Wroot = np.asarray(p['root_world'], np.float64)
        for jt in p.get('joints', []):
            if jt.get('local') is not None:                  # the node's own TRS, verbatim (an identity part)
                nd = dict({'name': jt['name']}, **{k: v for k, v in jt['local'].items() if k in
                                                   ('translation', 'rotation', 'scale', 'matrix', 'extras')})
            else:
                Wp = Wroot if jt['parent'] == p['root'] else world_of[jt['parent']]
                Lc = np.linalg.inv(Wp) @ world_of[jt['name']]
                nd = {'name': jt['name'], 'translation': [float(x) for x in Lc[:3, 3]],
                      'rotation': [float(x) for x in quat_from_matrix(Lc[:3, :3])]}
            add_node(nd, jt['parent'])
        for so in p.get('sockets', []):
            add_socket(so, so['parent'])
    # ---------------------------------------------------------------- one skin: the kept joints, then the parts'
    ibm_new = [ibm[keep_j]]
    for p in parts:
        for jt in p.get('joints', []):
            if jt.get('ibm') is not None:
                ibm_new.append(np.asarray(jt['ibm'], np.float32).reshape(1, 16))
            else:
                ibm_new.append(np.linalg.inv(world_of[jt['name']]).T.reshape(1, 16).astype(np.float32))
    ibm_all = np.concatenate(ibm_new).astype(np.float32)
    skin = dict(sk, joints=[new_of[sk['joints'][k]] for k in keep_j] + [added[nm] for nm in part_j])
    skin['inverseBindMatrices'] = _write_like(B, j, b, sk['inverseBindMatrices'], arr=ibm_all, target=None) \
        if not parts else B.accessor(ibm_all, 'MAT4')
    if 'skeleton' in sk:
        skin['skeleton'] = new_of[sk['skeleton']]
    J['skins'] = [skin]
    # ---------------------------------------------------------------- the images: the base's bytes, then the parts'
    images = []
    for im in j.get('images', []):
        v = j['bufferViews'][im['bufferView']]
        data = b[v.get('byteOffset', 0):v.get('byteOffset', 0) + v['byteLength']]
        images.append(dict(im, bufferView=B.view(bytes(data))))
    textures = [dict(t) for t in j.get('textures', [])]
    materials = [json.loads(json.dumps(m)) for m in j.get('materials', [])]
    ext_used = set(j.get('extensionsUsed', []))
    f32 = lambda a: np.ascontiguousarray(a, np.float32)

    shared_tex = {}          # (HX1) parts whose material names the same 'share' key share each image (one copy)

    def template_material(mt):
        tj = json.loads(json.dumps(mt['json']))
        made = shared_tex.setdefault(mt['share'], {}) if mt.get('share') else {}

        def walk(o):
            if isinstance(o, dict):
                if isinstance(o.get('index'), str) and o['index'].startswith('@'):
                    key = o['index'][1:]
                    if key not in made:
                        data, mime = mt['images'][key]
                        images.append({'bufferView': B.view(data), 'mimeType': mime})
                        textures.append({'sampler': int(mt.get('sampler', 0)), 'source': len(images) - 1})
                        made[key] = len(textures) - 1
                    o['index'] = made[key]
                for x in o.values():
                    walk(x)
            elif isinstance(o, list):
                for x in o:
                    walk(x)
        walk(tj)
        tj['name'] = mt['name']
        ext_used.update((tj.get('extensions') or {}).keys())
        materials.append(tj)
        return len(materials) - 1

    def part_attrs(d):
        Jn = np.vectorize(lambda s: jidx[s] if s else 0)(np.asarray(d['J'], object)).astype(np.uint16)
        W = f32(d['W'])
        assert np.allclose(W.sum(1), 1.0, atol=1e-5), 'part weights do not sum to 1'
        uv = f32(d['UV_gltf']) if 'UV_gltf' in d else f32(np.column_stack([d['UV'][:, 0], 1.0 - d['UV'][:, 1]]))
        a = {'POSITION': B.accessor(f32(d['V']), 'VEC3', 34962, minmax=True),
             'NORMAL': B.accessor(f32(d['N']), 'VEC3', 34962),
             'TANGENT': B.accessor(f32(d['TAN']), 'VEC4', 34962),
             'TEXCOORD_0': B.accessor(uv, 'VEC2', 34962)}
        if 'COLOR' in d:
            a['COLOR_0'] = B.accessor(f32(d['COLOR']), 'VEC4', 34962)
        a['JOINTS_0'] = B.accessor(Jn, 'VEC4', 34962)
        a['WEIGHTS_0'] = B.accessor(W, 'VEC4', 34962)
        return a

    part_meshes, mesh_material = {}, {}
    for mi, k in new_mesh.items():
        pm = [mats[pr['material']] for pr in out_meshes[k]['primitives'] if 'material' in pr]
        if len(set(pm)) == 1 and sum(1 for mi2 in new_mesh for pr in meshes[mi2]['primitives']
                                     if mats[pr.get('material', -1)] == pm[0]) == 1:
            mesh_material[mesh_name[mi]] = pm[0]      # a material that names exactly this mesh
    for p in parts:
        if p.get('mesh') is None:
            continue
        mt = p['material']
        mi_ = template_material(mt) if 'json' in mt else None
        assert mi_ is not None, f'{p["name"]}: a many-mesh base takes a template material (material["json"])'
        ms = p['mesh']
        prim = {'attributes': part_attrs(ms), 'indices': B.accessor(np.asarray(ms['F'], np.uint32).reshape(-1),
                                                                     'SCALAR', 34963), 'material': mi_, 'mode': 4}
        nd = p['node']
        out_meshes.append({'name': nd.get('mesh_name', nd['name']), 'primitives': [prim]})
        node = {'name': nd['name'], 'mesh': len(out_meshes) - 1, 'skin': 0}
        add_node(node, nd['parent'])
        part_meshes[p['name']] = dict(mesh=nd.get('mesh_name', nd['name']), material=mt['name'],
                                      triangles=int(len(ms['F'])))
        mesh_material[nd.get('mesh_name', nd['name'])] = mt['name']
    J['nodes'] = out_nodes
    J['meshes'] = out_meshes
    J['scenes'] = [dict(s, nodes=[new_of[i] for i in s['nodes'] if i in new_of]) for s in j['scenes']]
    J['images'], J['textures'], J['materials'] = images, textures, materials
    J['accessors'], J['bufferViews'] = B.accessors, B.views
    if ext_used:
        J['extensionsUsed'] = sorted(ext_used) if set(ext_used) != set(j.get('extensionsUsed', [])) \
            else list(j['extensionsUsed'])
    for k in ('animations', 'cameras'):
        assert not j.get(k), f'a base with {k}: renumber their node references first'
    report['node_map'] = {name_of[o]: n for o, n in new_of.items()}
    report['added_nodes'] = dict(added)
    _vrm_remap(J, new_of, added, name_of, parts, report)
    # (C3) a PART's own VRMC_node_constraint stages (the robot hand's WristRoll / WristFlex / ThumbRotor rolls):
    # jt['constraint'] = {kind: {..., 'source': a joint NAME (a part joint or a kept base node)}}, written after the
    # base's constraints were renumbered (so the loop above never reads a part's source as an old index)
    added_c = []
    for p in parts:
        for jt in p.get('joints', []):
            if not jt.get('constraint'):
                continue
            con = json.loads(json.dumps(jt['constraint']))
            for kind, c in con.items():
                src = c['source']
                c['source'] = added[src] if src in added else new_of[idx_of[src]]
            J['nodes'][added[jt['name']]].setdefault('extensions', {})['VRMC_node_constraint'] = dict(
                specVersion='1.0', constraint=con)
            added_c.append(jt['name'])
    if added_c:
        J['extensionsUsed'] = sorted(set(J.get('extensionsUsed', [])) | {'VRMC_node_constraint'})
    report['constraints_added'] = added_c
    _rewrite_records(J, j, parts, report, part_meshes, mesh_material)
    ex = J.setdefault('extras', {}).setdefault('bestiary', {})
    if chains is not None:
        ex['chains'] = chains
    if grafts is not None:
        ex['grafts'] = grafts
    if parts:
        ex['joints'] = len(joint_names)
    while len(B.bin) % 4:
        B.bin.append(0)
    J['buffers'] = [dict(j['buffers'][0], byteLength=len(B.bin))] if j.get('buffers') else [{'byteLength': len(B.bin)}]
    js = json.dumps(J, separators=(',', ':')).encode()
    js += b' ' * ((4 - len(js) % 4) % 4)
    total = 12 + 8 + len(js) + 8 + len(B.bin)
    with open(out_path, 'wb') as f:
        f.write(struct.pack('<III', 0x46546C67, 2, total))
        f.write(struct.pack('<II', len(js), 0x4E4F534A) + js)
        f.write(struct.pack('<II', len(B.bin), 0x004E4942) + bytes(B.bin))
    report['bytes'] = total
    report['primitives'] = [(m['name'], len(pr['attributes'])) for m in out_meshes for pr in m['primitives']]
    d = report['dropped']
    log(f'[assemble_multi] {out_path}: {total / 1e6:.1f} MB; meshes {len(meshes)} -> {len(out_meshes)}; joints '
        f'{report["joints_before"]} -> {report["joints_after"]}; dropped joints {len(d["joints"])}, sockets '
        f'{len(d["sockets"])}, mesh nodes {len(d["nodes"])} (+ {report["auto_dropped"]} emptied), meshes {d["meshes"]}; '
        f'humanBones pruned {len(report["vrm"]["pruned"])}, added {len(report["vrm"]["added"])}; rings '
        f'{report.get("records", {}).get("remapped", 0)} kept, dropped {report.get("records", {}).get("dropped", [])}, '
        f're-made {len(report.get("records", {}).get("remade", []))}, grafted {report.get("records", {}).get("grafted", [])}')
    return report
