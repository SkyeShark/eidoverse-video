"""eidoblend.characters.robotics.io: io.js, the kit's shared caches, in Blender.

    asset_root()            eidoverse/assets/robotics/ (the WebGPU edition's assetRoot)
    json_file(rel)          a JSON file under it, parsed once per Blender session (io.js json)
    glb_json(path)          a GLB's JSON chunk, parsed once (the node table the loader maps objects with)
    glb_accessor(path, i)   one accessor of a GLB's binary chunk as a list of tuples (the walk clips' keys)
    shared_image(path, srgb)   one bpy image per file and colour space (io.js imageTexture): every robot that uses a
                            map shares it, so two loads of the kit never decode or upload a map twice
    check_anisotropy(gltf)  texturePlugin's rule: a sampler's extras.eidoverse_anisotropy must be an integer 1..16
    cache_stats()           {'binaryFiles', 'decodedTextures'}

Not here: io.js `bytes` (Blender's own glTF importer reads the GLBs) and texturePlugin's loading (the importer
resolves the GLBs' external ../textures/ URIs itself). Anisotropic filtering is a Blender user preference
(preferences.system.anisotropic_filter), not a per-texture setting: the validation is ported, the value is reported.
"""

from __future__ import annotations

import json
import os
import struct

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..'))
ROOT = os.path.join(REPO, 'eidoverse', 'assets', 'robotics')

_JSON: dict = {}
_GLB: dict = {}
_BIN: dict = {}
_IMAGES: dict = {}


def asset_root() -> str:
    return ROOT


def json_file(rel: str) -> dict:
    """A JSON file under eidoverse/assets/robotics/ (or an absolute path), parsed once."""
    path = rel if os.path.isabs(rel) else os.path.join(ROOT, rel)
    path = os.path.normpath(path)
    if path not in _JSON:
        with open(path, encoding='utf-8') as f:
            _JSON[path] = json.load(f)
    return _JSON[path]


def _read_glb(path: str):
    with open(path, 'rb') as f:
        magic, _ver, _length = struct.unpack('<III', f.read(12))
        if magic != 0x46546C67:
            raise ValueError(f'not a GLB: {path}')
        clen, _ctype = struct.unpack('<II', f.read(8))
        js = json.loads(f.read(clen))
        head = f.read(8)
        binary = b''
        if len(head) == 8:
            blen, _btype = struct.unpack('<II', head)
            binary = f.read(blen)
    return js, binary


def glb_json(path: str) -> dict:
    path = os.path.normpath(path)
    if path not in _GLB:
        _GLB[path], _BIN[path] = _read_glb(path)
    return _GLB[path]


_COMPONENTS = {5120: ('b', 1), 5121: ('B', 1), 5122: ('h', 2), 5123: ('H', 2), 5125: ('I', 4), 5126: ('f', 4)}
_WIDTH = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}


def glb_accessor(path: str, index: int) -> list:
    """accessor `index` of the GLB at `path` as a list of tuples (float or integer components; no sparse accessors,
    no normalisation: the kit's animation samplers are float32)"""
    js = glb_json(path)
    binary = _BIN[os.path.normpath(path)]
    acc = js['accessors'][index]
    view = js['bufferViews'][acc['bufferView']]
    fmt, size = _COMPONENTS[acc['componentType']]
    width = _WIDTH[acc['type']]
    stride = view.get('byteStride') or size * width
    base = view.get('byteOffset', 0) + acc.get('byteOffset', 0)
    out = []
    one = struct.Struct('<' + fmt * width)
    for i in range(acc['count']):
        out.append(one.unpack_from(binary, base + i * stride))
    return out


def shared_image(path: str, srgb: bool):
    """one bpy image per (file, colour space): the WebGPU io.js image cache"""
    import bpy
    key = (os.path.normcase(os.path.normpath(path)), bool(srgb))
    im = _IMAGES.get(key)
    try:
        if im is not None and im.name in bpy.data.images and bpy.data.images[im.name] == im:
            return im
    except ReferenceError:
        pass
    for cand in bpy.data.images:
        if (cand.source == 'FILE' and os.path.normcase(os.path.normpath(bpy.path.abspath(cand.filepath))) == key[0]
                and (cand.colorspace_settings.name == 'sRGB') == key[1]):
            _IMAGES[key] = cand
            return cand
    im = bpy.data.images.load(path, check_existing=False)
    im.colorspace_settings.name = 'sRGB' if srgb else 'Non-Color'
    _IMAGES[key] = im
    return im


def check_anisotropy(gltf: dict) -> dict:
    """io.js texturePlugin: a sampler's extras.eidoverse_anisotropy must be an integer 1..16 -> {texture index: n}"""
    out = {}
    samplers = gltf.get('samplers') or []
    images = gltf.get('images') or []
    for ti, tex in enumerate(gltf.get('textures', [])):
        src = tex.get('source')
        if src is None or src >= len(images) or not images[src].get('uri'):
            continue                                       # texturePlugin returns null: three's own path loads it
        s = tex.get('sampler')
        a = 1
        if s is not None and s < len(samplers):
            a = (samplers[s].get('extras') or {}).get('eidoverse_anisotropy', 1)
        if not isinstance(a, int) or isinstance(a, bool) or a < 1 or a > 16:
            raise ValueError('Atlas anisotropy must be an integer from 1 to 16')
        out[ti] = a
    return out


def cache_stats() -> dict:
    """io.js cacheStats: GLBs parsed and images shared this session"""
    return {'binaryFiles': len(_GLB), 'decodedTextures': len(_IMAGES)}
