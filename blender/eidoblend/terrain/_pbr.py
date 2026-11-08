"""A small private PBR texture-set loader for the terrain family.

The shared texture library is eidoverse/assets/cache/textures/<SET>_<res>/, filled by
fetch_texture.py (CC0 sets from AmbientCG and Poly Haven, never committed). This finds a set by
name and loads its maps as Blender images with the right colour spaces. It stays private to the
family until a shared Blender fetch_pbr exists.

Where it looks, in order:
  1. this checkout's eidoverse/assets/cache/textures/
  2. $EIDO_TEXTURE_CACHE (a folder of sets), then $EIDO_ASSET_CACHE/textures
  3. the main checkout's cache, when this checkout is a git worktree (read only)

File names: AmbientCG `<ID>_Color / _NormalGL / _Roughness / _AmbientOcclusion / _Displacement`,
Poly Haven `<id>_diff / _normal (OpenGL) / _rough / _ao / _displacement / _arm`.
Blender's Normal Map node wants OpenGL normals; `_NormalDX` is never picked.
"""
import os
from pathlib import Path

import bpy

_ROLES = {
    'color': ('_Color', '_diff', '_diffuse', '_albedo', '_basecolor', '_col'),
    'normal': ('_NormalGL', '_normal', '_nor_gl'),
    'roughness': ('_Roughness', '_rough', '_roughness'),
    'ao': ('_AmbientOcclusion', '_ao'),
    'displacement': ('_Displacement', '_displacement', '_disp', '_height'),
    'arm': ('_arm',),
    'metalness': ('_Metalness', '_metal', '_metallic'),
}
_LINEAR = {'normal', 'roughness', 'ao', 'displacement', 'arm', 'metalness'}
_EXTS = ('.jpg', '.jpeg', '.png', '.exr', '.tif', '.tiff')


def _checkout_root():
    return Path(__file__).resolve().parents[3]


def _main_checkout(root):
    git = root / '.git'
    try:
        if git.is_file():
            line = git.read_text().strip()
            if line.startswith('gitdir:'):
                return Path(line.split(':', 1)[1].strip()).parents[2]
    except OSError:
        pass
    return None


def texture_roots():
    root = _checkout_root()
    roots = [root / 'eidoverse' / 'assets' / 'cache' / 'textures']
    env = os.environ.get('EIDO_TEXTURE_CACHE')
    if env:
        roots.append(Path(env))
    env = os.environ.get('EIDO_ASSET_CACHE')         # the shared library root (eidoblend.common's)
    if env:
        roots.append(Path(env) / 'textures')
    main = _main_checkout(root)
    if main:
        roots.append(main / 'eidoverse' / 'assets' / 'cache' / 'textures')
    return [r for r in roots if r.is_dir()]


def _res_rank(name, prefer):
    order = [prefer, '2k', '4k', '1k', '8k']
    for i, r in enumerate(order):
        if name.lower().endswith('_' + r):
            return i
    return len(order)


def find_set(name, prefer='2k'):
    """Locate a texture set: 'Ground106' (best resolution, 2k first) or 'Ground106_2k'.

    Returns {'name', 'dir', role: path, ...} for the roles found, or raises FileNotFoundError
    naming where it looked.
    """
    roots = texture_roots()
    cands = []
    for r in roots:
        exact = r / name
        if exact.is_dir():
            cands.append(exact)
            break
        for d in r.iterdir():
            if d.is_dir() and d.name.lower().startswith(name.lower() + '_'):
                cands.append(d)
        if cands:
            break
    if not cands:
        raise FileNotFoundError("texture set '%s' not found in %s (fetch it with fetch_texture.py)"
                                % (name, [str(r) for r in roots]))
    d = sorted(cands, key=lambda p: _res_rank(p.name, prefer))[0]
    files = [f for f in d.iterdir() if f.suffix.lower() in _EXTS]
    out = {'name': d.name, 'dir': d}
    for role, sufs in _ROLES.items():
        for suf in sufs:
            hit = [f for f in files if f.stem.lower().endswith(suf.lower())
                   and not f.stem.lower().endswith('normaldx')]
            if hit:
                out[role] = hit[0]
                break
    return out


def load_image(path, role='color'):
    """Load (or reuse) an image; colour maps sRGB, data maps Non-Color, repeat extension."""
    if isinstance(path, bpy.types.Image):
        return path
    img = bpy.data.images.load(str(path), check_existing=True)
    want = 'Non-Color' if role in _LINEAR else 'sRGB'
    try:
        if img.colorspace_settings.name != want:
            img.colorspace_settings.name = want
    except TypeError:
        pass
    return img


def load_set(name_or_dict, prefer='2k'):
    """{'color': Image, 'normal': Image, ...} for a set name, or pass a dict of role -> path/Image."""
    if isinstance(name_or_dict, dict):
        src = {k: v for k, v in name_or_dict.items() if k in _ROLES}
        label = name_or_dict.get('name', 'custom')
    else:
        src = find_set(name_or_dict, prefer)
        label = src['name']
    imgs = {role: load_image(p, role) for role, p in src.items() if role in _ROLES}
    imgs['name'] = label
    return imgs
