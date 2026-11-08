"""eidoblend.xr.glb: read a .glb back, plain Python (no bpy, no numpy needed): what an XR export really holds.

    from eidoblend.xr import glb
    g = glb.read('work/<id>/vr/scene.glb')
    s = glb.summary(g)                     # counts, triangles, draw calls, materials, animations, lights, budgets
    m = glb.world_matrices(g, t=4.0)       # {node name: 4x4 world matrix (glTF Y-up, rows)} with the animations at t
    glb.node_position(g, 'walker_07', t=4.0, blender_axes=True)   # where the page will draw it, in Blender's axes

The export's report and the tests read GLBs through this. sample(channel, t) evaluates a glTF animation sampler
(LINEAR / STEP / CUBICSPLINE, quaternions slerped) the way three.js's AnimationMixer does, so a position read here at t
is the position the page draws at t.
"""
from __future__ import annotations

import json
import math
import struct

COMPONENT = {5120: ('b', 1), 5121: ('B', 1), 5122: ('h', 2), 5123: ('H', 2), 5125: ('I', 4), 5126: ('f', 4)}
NCOMP = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT2': 4, 'MAT3': 9, 'MAT4': 16}
NORM_DIV = {5120: 127.0, 5121: 255.0, 5122: 32767.0, 5123: 65535.0}

# Quest 3 budgets from tools-guides/webxr.md: ~1.4 M triangles and ~30 draw calls held 85-90 fps; 2.2-2.3 M dipped
QUEST = {'triangles_ok': 1_500_000, 'triangles_max': 2_200_000, 'draws_ok': 60, 'draws_max': 150,
         'texture_mb_ok': 256, 'texture_mb_max': 512}


class GLB:
    def __init__(self, path, js, bin_chunk):
        self.path, self.json, self.bin = path, js, bin_chunk
        self._cache = {}

    def accessor(self, i):
        """The accessor's values as a list of tuples (or floats for SCALAR), normalized ints mapped to floats."""
        if i in self._cache:
            return self._cache[i]
        a = self.json['accessors'][i]
        n, comp = a['count'], NCOMP[a['type']]
        fmt, size = COMPONENT[a['componentType']]
        out = [(0.0,) * comp] * n
        if 'bufferView' in a:
            bv = self.json['bufferViews'][a['bufferView']]
            if bv.get('buffer', 0) != 0:
                raise ValueError('only the GLB binary buffer is read')
            stride = bv.get('byteStride') or size * comp
            base = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
            data = self.bin
            norm = a.get('normalized') and a['componentType'] in NORM_DIV
            div = NORM_DIV.get(a['componentType'], 1.0)
            out = []
            for k in range(n):
                v = struct.unpack_from('<' + fmt * comp, data, base + k * stride)
                if norm:
                    v = tuple(max(x / div, -1.0) for x in v)
                out.append(v)
        if 'sparse' in a:
            sp = a['sparse']
            idx_bv = self.json['bufferViews'][sp['indices']['bufferView']]
            ifmt, isz = COMPONENT[sp['indices']['componentType']]
            ibase = idx_bv.get('byteOffset', 0) + sp['indices'].get('byteOffset', 0)
            val_bv = self.json['bufferViews'][sp['values']['bufferView']]
            vbase = val_bv.get('byteOffset', 0) + sp['values'].get('byteOffset', 0)
            out = list(out)
            for k in range(sp['count']):
                j = struct.unpack_from('<' + ifmt, self.bin, ibase + k * isz)[0]
                out[j] = struct.unpack_from('<' + fmt * comp, self.bin, vbase + k * size * comp)
        if comp == 1:
            out = [v[0] for v in out]
        self._cache[i] = out
        return out

    def node_by_name(self, name):
        for i, n in enumerate(self.json.get('nodes', [])):
            if n.get('name') == name:
                return i
        raise KeyError(f'no node named {name!r} in {self.path}')


def read(path) -> GLB:
    with open(path, 'rb') as f:
        data = f.read()
    magic, version, length = struct.unpack_from('<4sII', data, 0)
    if magic != b'glTF' or version != 2:
        raise ValueError(f'{path}: not a glTF 2 binary')
    off, js, bin_chunk = 12, None, b''
    while off < length:
        clen, ctype = struct.unpack_from('<II', data, off)
        chunk = data[off + 8: off + 8 + clen]
        if ctype == 0x4E4F534A:
            js = json.loads(chunk.decode('utf-8'))
        elif ctype == 0x004E4942:
            bin_chunk = chunk
        off += 8 + clen
    if js is None:
        raise ValueError(f'{path}: no JSON chunk')
    return GLB(path, js, bin_chunk)


def write(g, path=None):
    """Write a GLB back (its JSON as it now stands in g.json, its binary chunk unchanged), 4-byte padded."""
    path = path or g.path
    js = json.dumps(g.json, separators=(',', ':')).encode('utf-8')
    js += b' ' * ((4 - len(js) % 4) % 4)
    b = g.bin + b'\x00' * ((4 - len(g.bin) % 4) % 4)
    total = 12 + 8 + len(js) + (8 + len(b) if b else 0)
    with open(path, 'wb') as f:
        f.write(struct.pack('<4sII', b'glTF', 2, total))
        f.write(struct.pack('<II', len(js), 0x4E4F534A))
        f.write(js)
        if b:
            f.write(struct.pack('<II', len(b), 0x004E4942))
            f.write(b)
    return path


def strip_extras(g, keep=('xr_',)):
    """Drop every extras key that does not start with one of `keep` (Blender 5.2's exporter writes add-ons' system
    properties as extras: a VRM's whole add-on data on each node and material). Returns the bytes saved."""
    before = len(json.dumps(g.json))

    def walk(o):
        if isinstance(o, dict):
            ex = o.get('extras')
            if isinstance(ex, dict):
                kept = {k: v for k, v in ex.items() if k.startswith(tuple(keep))}
                if kept:
                    o['extras'] = kept
                else:
                    del o['extras']
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(g.json)
    return before - len(json.dumps(g.json))


# ------------------------------------------------------------------------------------------------ the summary ---

def _prim_triangles(g, prim):
    mode = prim.get('mode', 4)
    if 'indices' in prim:
        n = g.json['accessors'][prim['indices']]['count']
    else:
        n = g.json['accessors'][prim['attributes']['POSITION']]['count']
    if mode == 4:
        return n // 3
    if mode in (5, 6):
        return max(0, n - 2)
    return 0


def _image_bytes(g, img):
    if 'bufferView' in img:
        return g.json['bufferViews'][img['bufferView']]['byteLength']
    return 0


def _png_size(blob):
    if blob[:8] == b'\x89PNG\r\n\x1a\n':
        return struct.unpack('>II', blob[16:24])
    if blob[:2] == b'\xff\xd8':                      # JPEG: walk the markers to SOF0/2
        i = 2
        while i < len(blob) - 9:
            if blob[i] != 0xFF:
                i += 1
                continue
            marker, seg = blob[i + 1], struct.unpack('>H', blob[i + 2:i + 4])[0]
            if marker in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack('>HH', blob[i + 5:i + 9])
                return w, h
            i += 2 + seg
    if blob[:4] == b'RIFF' and blob[8:12] == b'WEBP':
        if blob[12:16] == b'VP8X':
            w = 1 + int.from_bytes(blob[24:27], 'little')
            h = 1 + int.from_bytes(blob[27:30], 'little')
            return w, h
        if blob[12:16] == b'VP8 ':
            w, h = struct.unpack('<HH', blob[26:30])
            return w & 0x3FFF, h & 0x3FFF
        if blob[12:16] == b'VP8L':
            b = blob[21:25]
            bits = int.from_bytes(b, 'little')
            return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    return None


def image_sizes(g):
    """[(name, mime, (w, h) or None, bytes)] of the GLB's embedded images."""
    out = []
    for img in g.json.get('images', []):
        blob = b''
        if 'bufferView' in img:
            bv = g.json['bufferViews'][img['bufferView']]
            blob = g.bin[bv.get('byteOffset', 0): bv.get('byteOffset', 0) + bv['byteLength']]
        out.append((img.get('name', ''), img.get('mimeType', ''), _png_size(blob) if blob else None, len(blob)))
    return out


def summary(g) -> dict:
    """Counts and budgets of a GLB, the numbers an XR page lives by."""
    js = g.json
    meshes = js.get('meshes', [])
    nodes = js.get('nodes', [])
    # draws: every primitive of every mesh node instance (EXT_mesh_gpu_instancing draws a mesh once per primitive)
    tris = draws = 0
    inst_nodes = 0
    for n in nodes:
        if 'mesh' not in n:
            continue
        m = meshes[n['mesh']]
        k = 1
        ext = n.get('extensions', {}).get('EXT_mesh_gpu_instancing')
        if ext:
            inst_nodes += 1
            attrs = ext.get('attributes', {})
            first = next(iter(attrs.values()), None)
            k = js['accessors'][first]['count'] if first is not None else 1
        for p in m['primitives']:
            tris += _prim_triangles(g, p) * k
            draws += 1
    texture_px = 0
    imgs = image_sizes(g)
    for _n, _mime, wh, _b in imgs:
        if wh:
            texture_px += wh[0] * wh[1]
    texture_mb = texture_px * 4 * 4 / 3 / 1e6           # RGBA8 with mips, uncompressed on the GPU
    mats = []
    for m in js.get('materials', []):
        pbr = m.get('pbrMetallicRoughness', {})
        mats.append({'name': m.get('name'), 'extensions': sorted(m.get('extensions', {})),
                     'baseColorTexture': 'baseColorTexture' in pbr, 'baseColorFactor': pbr.get('baseColorFactor'),
                     'metallicRoughnessTexture': 'metallicRoughnessTexture' in pbr,
                     'metallicFactor': pbr.get('metallicFactor', 1.0), 'roughnessFactor': pbr.get('roughnessFactor', 1.0),
                     'normalTexture': 'normalTexture' in m, 'emissiveTexture': 'emissiveTexture' in m,
                     'emissiveFactor': m.get('emissiveFactor'),
                     'emissiveStrength': m.get('extensions', {}).get('KHR_materials_emissive_strength', {}).get(
                         'emissiveStrength'),
                     'alphaMode': m.get('alphaMode', 'OPAQUE'), 'doubleSided': m.get('doubleSided', False),
                     'unlit': 'KHR_materials_unlit' in m.get('extensions', {})})
    anims = []
    for a in js.get('animations', []):
        tmax, paths = 0.0, {}
        for ch in a['channels']:
            s = a['samplers'][ch['sampler']]
            acc = js['accessors'][s['input']]
            tmax = max(tmax, (acc.get('max') or [0])[0])
            paths[ch['target'].get('path')] = paths.get(ch['target'].get('path'), 0) + 1
        anims.append({'name': a.get('name'), 'channels': len(a['channels']), 'duration': tmax, 'paths': paths})
    lights = js.get('extensions', {}).get('KHR_lights_punctual', {}).get('lights', [])
    cams = [{'name': c.get('name'), 'type': c.get('type'), **c.get(c.get('type'), {})} for c in js.get('cameras', [])]
    skins = js.get('skins', [])
    morphs = sum(len(p.get('targets', [])) for m in meshes for p in m['primitives'])
    out = {
        'nodes': len(nodes), 'meshes': len(meshes), 'mesh_nodes': sum(1 for n in nodes if 'mesh' in n),
        'triangles': tris, 'draws': draws, 'gpu_instanced_nodes': inst_nodes,
        'materials': mats, 'images': [{'name': n, 'mime': mi, 'size': wh, 'bytes': b} for n, mi, wh, b in imgs],
        'texture_mb_gpu': round(texture_mb, 1), 'animations': anims,
        'duration': max([a['duration'] for a in anims], default=0.0),
        'lights': [{'name': li.get('name'), 'type': li.get('type'), 'intensity': li.get('intensity', 1.0),
                    'color': li.get('color', [1, 1, 1]), 'range': li.get('range'), 'spot': li.get('spot')}
                   for li in lights],
        'cameras': cams, 'skins': len(skins), 'joints': sum(len(s['joints']) for s in skins), 'morph_targets': morphs,
        'extensions_used': sorted(js.get('extensionsUsed', [])),
        'extensions_required': sorted(js.get('extensionsRequired', [])),
        'bytes': len(g.bin),
    }
    out['quest'] = budget(out)
    return out


def budget(s) -> dict:
    """'ok' / 'heavy' / 'over' per Quest 3 budget (tools-guides/webxr.md's measured numbers)."""
    def grade(v, ok, mx):
        return 'ok' if v <= ok else ('heavy' if v <= mx else 'over')
    return {'triangles': grade(s['triangles'], QUEST['triangles_ok'], QUEST['triangles_max']),
            'draws': grade(s['draws'], QUEST['draws_ok'], QUEST['draws_max']),
            'textures': grade(s['texture_mb_gpu'], QUEST['texture_mb_ok'], QUEST['texture_mb_max'])}


# ------------------------------------------------------------------------------------------ animation sampling ---

def _lerp(a, b, k):
    return tuple(x + (y - x) * k for x, y in zip(a, b))


def _slerp(a, b, k):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    d = ax * bx + ay * by + az * bz + aw * bw
    if d < 0:
        bx, by, bz, bw, d = -bx, -by, -bz, -bw, -d
    if d > 0.9995:
        r = _lerp((ax, ay, az, aw), (bx, by, bz, bw), k)
    else:
        th = math.acos(min(1.0, d))
        s = math.sin(th)
        wa, wb = math.sin((1 - k) * th) / s, math.sin(k * th) / s
        r = (ax * wa + bx * wb, ay * wa + by * wb, az * wa + bz * wb, aw * wa + bw * wb)
    n = math.sqrt(sum(x * x for x in r)) or 1.0
    return tuple(x / n for x in r)


def sample(g, anim, channel, t):
    """A channel's value at t seconds (clamped to the clip), as three.js's mixer reads it (a tuple; morph weights a
    tuple of all weights)."""
    s = anim['samplers'][channel['sampler']]
    ts = g.accessor(s['input'])
    vals = g.accessor(s['output'])
    path = channel['target']['path']
    interp = s.get('interpolation', 'LINEAR')
    nkeys = len(ts)
    per = max(1, len(vals) // (nkeys * (3 if interp == 'CUBICSPLINE' else 1)))   # morph weights: several per key

    def key(i):
        if interp == 'CUBICSPLINE':
            base = (i * 3 + 1) * per
        else:
            base = i * per
        v = vals[base: base + per]
        return tuple(x for vv in v for x in (vv if isinstance(vv, tuple) else (vv,)))

    if t <= ts[0]:
        return key(0)
    if t >= ts[-1]:
        return key(nkeys - 1)
    lo, hi = 0, nkeys - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if ts[mid] <= t:
            lo = mid
        else:
            hi = mid
    t0, t1 = ts[lo], ts[hi]
    k = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
    if interp == 'STEP':
        return key(lo)
    if interp == 'CUBICSPLINE':
        dt = t1 - t0

        def part(i, which):
            base = (i * 3 + which) * per
            v = vals[base: base + per]
            return tuple(x for vv in v for x in (vv if isinstance(vv, tuple) else (vv,)))
        p0, m0, p1, m1 = part(lo, 1), part(lo, 2), part(hi, 1), part(hi, 0)
        k2, k3 = k * k, k * k * k
        h00, h10, h01, h11 = 2 * k3 - 3 * k2 + 1, k3 - 2 * k2 + k, -2 * k3 + 3 * k2, k3 - k2
        r = tuple(h00 * a + h10 * dt * b + h01 * c + h11 * dt * d for a, b, c, d in zip(p0, m0, p1, m1))
        if path == 'rotation':
            n = math.sqrt(sum(x * x for x in r)) or 1.0
            r = tuple(x / n for x in r)
        return r
    if path == 'rotation':
        return _slerp(key(lo), key(hi), k)
    return _lerp(key(lo), key(hi), k)


# ------------------------------------------------------------------------------------------- the node graph ---

def _mat_trs(t, r, s):
    x, y, z, w = r
    xx, yy, zz, xy, xz, yz, wx, wy, wz = x * x, y * y, z * z, x * y, x * z, y * z, w * x, w * y, w * z
    m = [[(1 - 2 * (yy + zz)) * s[0], (2 * (xy - wz)) * s[1], (2 * (xz + wy)) * s[2], t[0]],
         [(2 * (xy + wz)) * s[0], (1 - 2 * (xx + zz)) * s[1], (2 * (yz - wx)) * s[2], t[1]],
         [(2 * (xz - wy)) * s[0], (2 * (yz + wx)) * s[1], (1 - 2 * (xx + yy)) * s[2], t[2]],
         [0.0, 0.0, 0.0, 1.0]]
    return m


def _mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def local_trs(g, node_index, t=None, anim_index=None):
    """(translation, rotation xyzw, scale) of a node, with its animation channels applied at t (all animations, or
    one)."""
    n = g.json['nodes'][node_index]
    tr = tuple(n.get('translation', (0.0, 0.0, 0.0)))
    ro = tuple(n.get('rotation', (0.0, 0.0, 0.0, 1.0)))
    sc = tuple(n.get('scale', (1.0, 1.0, 1.0)))
    if 'matrix' in n:
        raise ValueError('matrix nodes are not sampled here (the Blender exporter writes TRS)')
    if t is not None:
        anims = g.json.get('animations', [])
        for ai, a in enumerate(anims):
            if anim_index is not None and ai != anim_index:
                continue
            for ch in a['channels']:
                if ch['target'].get('node') != node_index:
                    continue
                v = sample(g, a, ch, t)
                p = ch['target']['path']
                if p == 'translation':
                    tr = v
                elif p == 'rotation':
                    ro = v
                elif p == 'scale':
                    sc = v
    return tr, ro, sc


def world_matrices(g, t=None, scene=None):
    """{node index: world matrix (4x4 rows, glTF axes)} for every node of the scene, animations applied at t."""
    js = g.json
    sc = js['scenes'][js.get('scene', 0) if scene is None else scene]
    out = {}

    def walk(i, parent):
        m = _mul(parent, _mat_trs(*local_trs(g, i, t)))
        out[i] = m
        for c in js['nodes'][i].get('children', []):
            walk(c, m)
    ident = [[1.0 if i == j else 0.0 for j in range(4)] for i in range(4)]
    for r in sc['nodes']:
        walk(r, ident)
    return out


def node_position(g, name, t=None, blender_axes=False):
    """A node's world position at t (glTF's Y-up, or Blender's Z-up with blender_axes)."""
    i = g.node_by_name(name)
    m = world_matrices(g, t)[i]
    x, y, z = m[0][3], m[1][3], m[2][3]
    return (x, -z, y) if blender_axes else (x, y, z)


def morphed_positions(g, name, t, blender_axes=True):
    """Every vertex of a mesh node at t, world space: POSITION + the morph targets at their weights, through the
    node's animated world matrix (the vertices the page draws; skinning not applied)."""
    i = g.node_by_name(name)
    n = g.json['nodes'][i]
    m = world_matrices(g, t)[i]
    w = morph_weights(g, name, t)
    out = []
    for p in g.json['meshes'][n['mesh']]['primitives']:
        base = g.accessor(p['attributes']['POSITION'])
        deltas = [(wk, g.accessor(tg['POSITION'])) for wk, tg in zip(w, p.get('targets', [])) if abs(wk) > 1e-7]
        for vi, b in enumerate(base):
            x, y, z = b
            for wk, d in deltas:
                x += wk * d[vi][0]
                y += wk * d[vi][1]
                z += wk * d[vi][2]
            wx = m[0][0] * x + m[0][1] * y + m[0][2] * z + m[0][3]
            wy = m[1][0] * x + m[1][1] * y + m[1][2] * z + m[1][3]
            wz = m[2][0] * x + m[2][1] * y + m[2][2] * z + m[2][3]
            out.append((wx, -wz, wy) if blender_axes else (wx, wy, wz))
    return out


def morph_weights(g, name, t):
    """A mesh node's morph target weights at t (its 'weights' animation channel, else the mesh's defaults)."""
    i = g.node_by_name(name)
    n = g.json['nodes'][i]
    w = tuple(n.get('weights') or g.json['meshes'][n['mesh']].get('weights', ()))
    for a in g.json.get('animations', []):
        for ch in a['channels']:
            if ch['target'].get('node') == i and ch['target']['path'] == 'weights':
                w = sample(g, a, ch, t)
    return w
