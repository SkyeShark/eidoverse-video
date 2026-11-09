"""tests/xr/test_xr_cli.py: what export_cli.py's options wrote, read back. Plain Python (no Blender, no GPU):

    python blender/tests/xr/test_xr_cli.py          (after run_all.sh's cli step, which makes the bundles)

The cli step exports with every option of export_cli.py between its runs:
  out/city/vr_meshopt_webp   the city: --compress meshopt --images WEBP --world-width 1024
  out/city/vr_draco_jpeg     the city: --compress draco --images JPEG --no-world --name city_draco
  out/city/vr_bake_sizes     the city: --texel-density 4 --max-texture 4096 --world-frame 97 --world-width 256
  out/city/vr_bake_cap       the city: --max-texture 512 --no-world
  out/features/vr_cli        the features set (CPU only): --street 0.5 --table 0.05 --start 1,-3 --facing 1,0
                             --name features_cli --shadows --no-bake --no-motion --no-world --max-image 512
                             --choreo ball,cam_film
(--survey is printed into the run's log.) Checked here: each option shows in the manifest, the GLB or the bundle's
files.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..', '..')))

from eidoblend.xr import glb as G  # noqa: E402

RESULTS = []


def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok), detail))
    print(f"[check] {'PASS' if ok else 'FAIL'} {name}{': ' + str(detail) if detail else ''}", flush=True)


def bundle(d):
    if not os.path.exists(os.path.join(d, 'scene.glb')):
        check(f'{os.path.relpath(d, HERE)}: the bundle exists (run_all.sh cli)', False)
        return None, None, None
    g = G.read(os.path.join(d, 'scene.glb'))
    return g, G.summary(g), json.load(open(os.path.join(d, 'scene.xr.json')))


def hdr_size(p):
    """(width, height) from a Radiance .hdr header ('-Y h +X w')."""
    with open(p, 'rb') as f:
        head = f.read(4096).split(b'\n')
    for line in head:
        if line.startswith(b'-Y '):
            parts = line.split()
            return int(parts[3]), int(parts[1])
    return None


close = lambda a, b, e=1e-6: all(abs(x - y) <= e for x, y in zip(a, b)) and len(a) == len(b)   # noqa: E731

# --compress meshopt --images WEBP --world-width 1024
g, s, m = bundle(os.path.join(HERE, 'out', 'city', 'vr_meshopt_webp'))
if g:
    check('--compress meshopt: EXT_meshopt_compression, the manifest says meshopt',
          'EXT_meshopt_compression' in s['extensions_used'] and m['compression'] == 'meshopt', s['extensions_used'])
    check('--images WEBP: every image in the GLB is WebP', s['images'] and all(i['mime'] == 'image/webp' for i in s['images']),
          [(i['mime'], i['size']) for i in s['images']])
    wsz = hdr_size(os.path.join(HERE, 'out', 'city', 'vr_meshopt_webp', 'world.hdr'))
    check('--world-width 1024: world.hdr is 1024 x 512', wsz == (1024, 512), wsz)

# --compress draco --images JPEG --no-world --name city_draco
g, s, m = bundle(os.path.join(HERE, 'out', 'city', 'vr_draco_jpeg'))
if g:
    check('--compress draco: KHR_draco_mesh_compression, the manifest says draco',
          'KHR_draco_mesh_compression' in s['extensions_used'] and m['compression'] == 'draco', s['extensions_used'])
    check('--images JPEG: every image in the GLB is JPEG', s['images'] and all(i['mime'] == 'image/jpeg' for i in s['images']),
          [(i['mime'], i['size']) for i in s['images']])
    check("--no-world: no world image; the background is the world's measured mean (not its viewport grey)",
          m['world'] is None and not close(m['background'], [0.05, 0.05, 0.05], 1e-4), m['background'])
    check('--name city_draco: the bundle is named', m['name'] == 'city_draco', m['name'])


def png_size(p):
    import struct
    if not os.path.exists(p):
        return None
    with open(p, 'rb') as f:
        head = f.read(24)
    return struct.unpack('>II', head[16:24]) if head[:8] == b'\x89PNG\r\n\x1a\n' else None


# --texel-density 4 --max-texture 4096 --world-frame 97 --world-width 256: the towers' bake sized by the density (their
# ~11 700 m2 at 4 texels a metre: 1024 px, where the default 24 would ask for 4096); the world captured at frame 97
d = os.path.join(HERE, 'out', 'city', 'vr_bake_sizes')
g, s, m = bundle(d)
if g:
    tw = png_size(os.path.join(d, 'textures', 'xr_city_towers_color.png'))
    check('--texel-density 4 (--max-texture 4096): the towers baked at 1024 px (24 texels a metre would be 4096)',
          tw == (1024, 1024), tw)
    check('--world-frame 97 --world-width 256: the world captured at frame 97, 256 x 128',
          (m.get('world') or {}).get('frame') == 97 and hdr_size(os.path.join(d, 'world.hdr')) == (256, 128),
          (m.get('world'), hdr_size(os.path.join(d, 'world.hdr'))))
# --max-texture 512: the bake capped below what the density asks for
d = os.path.join(HERE, 'out', 'city', 'vr_bake_cap')
g, s, m = bundle(d)
if g:
    tw = png_size(os.path.join(d, 'textures', 'xr_city_towers_color.png'))
    sizes = [max(i['size']) for i in s['images'] if i['size']]
    check('--max-texture 512: the towers baked at 512 px, no texture in the GLB larger', tw == (512, 512)
          and sizes and max(sizes) <= 512, (tw, sizes))

# the features set: the placement options, --shadows, --no-bake, --no-motion, --no-world, --max-image, --choreo
d = os.path.join(HERE, 'out', 'features', 'vr_cli')
g, s, m = bundle(d)
if g:
    check('--street 0.5 --table 0.05: the scales in the manifest', m['street'] == 0.5 and m['table'] == 0.05,
          (m['street'], m['table']))
    check("--start 1,-3 --facing 1,0 (Blender axes): three's (1, 0, 3) facing (1, 0, 0)",
          close(m['start'], [1.0, 0.0, 3.0]) and close(m['facing'], [1.0, 0.0, 0.0]), (m['start'], m['facing']))
    check('--name features_cli --shadows', m['name'] == 'features_cli' and m['shadows'] is True, (m['name'], m['shadows']))
    mnames = {mt['name'] for mt in s['materials']}
    check('--no-bake: nothing baked (no textures folder; the procedural ground and flag go as the exporter writes '
          'them, under their own names)', not os.path.exists(os.path.join(d, 'textures'))
          and {'ground_procedural', 'flag_stripes'} <= mnames and not {'gltf_ground', 'gltf_flag'} & mnames,
          sorted(n for n in mnames if 'ground' in (n or '') or 'flag' in (n or '')))
    cast = sorted(n for n in mnames if (n or '').startswith('gltf_') and 'Instance' in n)
    check("a headless export opens the VRM add-on itself: the cast's MToon materials go out converted (PBR stand-ins), "
          "and the add-on's UV drivers are not taken for animated material values",
          len(cast) >= 10 and not any('Mtoon1' in w for w in m['warnings']),
          f'{len(cast)} converted, e.g. {cast[:2]}; {len(m["warnings"])} warnings')
    nodes = g.json['nodes']
    animated = {nodes[ch['target']['node']].get('name') for a in g.json.get('animations', []) for ch in a['channels']
                if ch['target'].get('node') is not None}
    flag = next((n for n in nodes if n.get('name') == 'flag'), {})
    flag_morphs = sum(len(p.get('targets', [])) for p in g.json['meshes'][flag['mesh']]['primitives']) if 'mesh' in flag \
        else None
    orbit = [n.get('name') for n in nodes if (n.get('name') or '').startswith('orbiters')]
    check('--no-motion: instances and deformation exported still, at the first frame: the orbiters there with no '
          'channel on them, the flag a mesh without morph targets, the rest of the timeline still keyed',
          orbit and not any((n or '').startswith('orbiters') for n in animated) and flag_morphs == 0
          and 'ball' in animated and any(w.startswith('orbiters') and 'exported still' in w for w in m['warnings']),
          f'{len(orbit)} orbiter nodes, flag morph targets {flag_morphs}, {len(animated)} animated nodes')
    sizes = [max(i['size']) for i in s['images'] if i['size']]
    check('--max-image 512: every texture in the GLB is 512 px or less on its long side', sizes and max(sizes) <= 512,
          f'{len(sizes)} images, largest {max(sizes) if sizes else None}, {s["texture_mb_gpu"]} MB on the GPU')
    check('--no-world: the measured flat colour (a blue sky over a dark ground: bluish, not grey)',
          m['world'] is None and m['background'][2] > m['background'][0] and not close(m['background'], [0.05] * 3, 1e-4),
          m['background'])
    ch = json.load(open(os.path.join(d, 'choreo.json')))
    tr = ch.get('track', {})
    check('--choreo ball,cam_film: their world tracks (t, x, y, z, qx, qy, qz, qw) in choreo.json',
          set(tr) == {'ball', 'cam_film'} and all(len(r) == 8 for rows in tr.values() for r in rows)
          and all(abs(math.sqrt(sum(x * x for x in r[4:])) - 1) < 1e-3 for r in tr['cam_film']),
          {k: len(v) for k, v in tr.items()})

n_fail = sum(1 for _, ok, _ in RESULTS if not ok)
print(f'[check] {len(RESULTS) - n_fail} passed, {n_fail} failed', flush=True)
sys.exit(1 if n_fail else 0)
