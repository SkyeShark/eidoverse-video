#!/usr/bin/env python3
"""tests/harness/test_fetch_hints.py: what the fetchers and the doctor tell an agent on this branch, in Blender's
words (plain Python: no Blender, no network). From the repo root:

    python blender/tests/harness/test_fetch_hints.py

  fetch_texture.py  the lines after a fetch: a library set -> assets.load_pbr(id, res, maps=...), its tiling as
                    load_pbr's repeat; Poly Haven URLs -> --cache first; extracted files -> load_image_texture; a height
                    map -> load_pbr's displacement and terrain.relief; no three.js names left
  fetch_hdri.py     the line after a fetch: assets.load_hdri (.hdr and .exr), lookdev only; no three.js loaders named
  fetch_model.py    a curated nose axis in drive_along / face_toward's words (glTF +z -> '-y'); the crow and the
                    cactus wren read '-y'; drive_along accepts every axis it prints; the catalogue's sizes Z up;
                    the kit advice names both load_kits
  eido_blender.py   doctor's Deno check imports exactly the npm packages the media family's Deno scripts name
"""
import ast
import io
import os
import re
import sys
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'blender'))
sys.dont_write_bytecode = True
sys.argv = sys.argv[:1]                       # the fetchers read their query from argv when imported
FAIL = []
WEBGPU = re.compile(r'THREE\.|loadImageTexture|createParallaxMaterial|RepeatWrapping|EXRLoader|RGBELoader|'
                    r'computeTangents|globalThis')


def check(ok, what):
    print(f"[hints] {'PASS' if ok else 'FAIL'}: {what}", flush=True)
    if not ok:
        FAIL.append(what)


def texture():
    import fetch_texture as ft
    lib = ft.usage_lines('Concrete031', 'ambientcg', {'diff': 'a.jpg', 'normal': 'n.jpg', 'rough': 'r.jpg',
                                                      'ao': 'ao.jpg', 'displacement': 'd.jpg'}, '1k', True)
    check(any("assets.load_pbr('Concrete031', res='1k', maps=('diff', 'normal', 'rough')" in l for l in lib),
          "a library set: assets.load_pbr('Concrete031', res='1k', maps=('diff', 'normal', 'rough'), ...) (AO left to "
          'EEVEE)')
    check(any("repeat=(u, v)" in l for l in lib), 'tiling is load_pbr\'s repeat')
    check(any('displacement=' in l and 'relief.create_parallax_material' in l for l in lib),
          'a height map: load_pbr\'s displacement, and terrain.relief for real depth')
    ph = ft.usage_lines('brick_wall_006', 'polyhaven', {'diff': 'https://dl.polyhaven.org/a.jpg',
                                                        'normal': 'https://dl.polyhaven.org/b.jpg'}, '2k', False)
    check(any('python fetch_texture.py brick_wall_006 2k --cache' in l for l in ph) and any('CDN URLs' in l for l in ph),
          'Poly Haven URLs: fetch the set into the library with --cache first')
    acg = ft.usage_lines('Bricks074', 'ambientcg', {'diff': os.path.abspath('Bricks074_Color.jpg'),
                                                    'normal_dx': os.path.abspath('n.png'), 'arm': 'x.jpg'}, '1k', False)
    check(any('assets.load_image_texture(path' in l for l in acg), 'extracted files: one map loads with '
          'load_image_texture')
    check(ft.pbr_maps({'diff': 1, 'normal_dx': 1, 'arm': 1, 'opacity': 1}) == ('diff', 'normal_dx', 'arm', 'opacity'),
          f"the maps named for a DirectX-normal, ARM-packed, cut-out set: {ft.pbr_maps({'diff': 1, 'normal_dx': 1, 'arm': 1, 'opacity': 1})}")
    check(any('NONE' in l for l in acg), 'no height map: said so')
    bad = [l for l in lib + ph + acg if WEBGPU.search(l)]
    check(not bad, f'no WebGPU API named: {bad[:1]}')
    src = open(os.path.join(ROOT, 'fetch_texture.py'), encoding='utf-8').read()
    prints = [l for l in src.splitlines() if 'print(' in l and WEBGPU.search(l)]
    check(not prints, f'no print in fetch_texture.py names the WebGPU API: {prints[:1]}')


def hdri():
    import fetch_hdri as fh
    lines = fh.usage_lines(os.path.abspath('hdri.exr'))
    check(any("assets.load_hdri(ctx.assets['hdri']" in l and '.exr' in l and 'make_sky' in l for l in lines),
          'an HDRI: assets.load_hdri (Blender reads .hdr and .exr), lookdev only, the sky family for skies')
    src = open(os.path.join(ROOT, 'fetch_hdri.py'), encoding='utf-8').read()
    tree = ast.parse(src)
    strings = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    bad = [s for s in strings if WEBGPU.search(s) and 'RGBELoader' not in s and 'WebGPU' not in s]
    check(not bad, f'fetch_hdri.py names no three.js loader outside its WebGPU-sidecar notes: {bad[:1]}')


def model():
    import fetch_model as fm
    words = {a: fm._blender_axis(a) for a in ('+z', '-z', '+x', '-x', '+Z')}
    check(words == {'+z': '-y', '-z': '+y', '+x': '+x', '-x': '-x', '+Z': '-y'},
          f"glTF axes in Blender's words (the importer's (x, -z, y)): {words}")
    crow = os.path.join(ROOT, 'eidoverse', 'assets', 'models',
                        'crow_bird_animated_corvid_raven_black_cawing_flying_walking.glb')
    wren = os.path.join(ROOT, 'eidoverse', 'assets', 'models',
                        'cactus_wren_bird_animated_desert_songbird_calling_hopping_walking.glb')
    got = (fm._blender_axis(fm._forward_axis_for(crow)), fm._blender_axis(fm._forward_axis_for(wren)))
    check(got == ('-y', '-y'), f'the crow and the cactus wren (curated +z) read forward -y: {got}')
    src = open(os.path.join(ROOT, 'blender', 'eidoblend', 'placement', 'helpers.py'), encoding='utf-8').read()
    yaw = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Assign)
               and any(getattr(t, 'id', '') == '_YAW' for t in n.targets))      # (helpers imports bpy: read, not run)
    allowed = {k.value for k in yaw.value.keys}
    curated = {fm._blender_axis(v) for v in fm._FORWARD_AXES_CACHE.values()}
    check(allowed and curated <= allowed, f'drive_along / face_toward accept every curated axis printed: {sorted(curated)} '
          f'within {sorted(allowed)}')
    buf = io.StringIO()
    with redirect_stdout(buf):
        fm.list_local_models()
    lines = [l for l in buf.getvalue().splitlines() if 'crow_bird' in l]
    check(lines and "forward='-y'" in lines[0] and 'X x Y x Z up' in lines[0],
          f'the catalogue lists sizes Z up and the nose axis in Blender\'s words: {lines[0][-90:] if lines else "no row"}')
    from eidoblend.harness import model_preview as MP
    k = MP.classify_kit(['barrel_a', 'barrel_b', 'barrel_c', 'barrel_d'])
    check('eidoblend.harness.assets.load_kit' in k and 'eidoblend.placement.load_kit' in k and 'loadKit' not in k,
          'the kit advice names both load_kits')


def doctor():
    import eido_blender as eb
    pkgs = eb.media_npm_packages()
    js = os.path.join(ROOT, 'blender', 'eidoblend', 'media', 'js')
    named = set()
    for n in os.listdir(js):
        if n.endswith('.mjs'):
            named |= set(re.findall(r"['\"](npm:[^'\"]+)['\"]", open(os.path.join(js, n), encoding='utf-8').read()))
    check(pkgs and set(pkgs) == named and any('three@' in p for p in pkgs) and any('@napi-rs/canvas@' in p for p in pkgs),
          f"doctor's Deno check imports the media family's npm packages: {pkgs}")


if __name__ == '__main__':
    for fn in (texture, hdri, model, doctor):
        try:
            fn()
        except Exception as e:                                       # noqa: BLE001
            import traceback
            traceback.print_exc()
            check(False, f'{fn.__name__} raised {type(e).__name__}: {e}')
    print(f"[hints] {'ALL PASS' if not FAIL else f'{len(FAIL)} FAIL'}", flush=True)
    sys.exit(1 if FAIL else 0)
