"""The masks as a material in Blender 5.2 EEVEE, on the reference rig. Each sheet reference is rendered by
reference/render_references.render_view (its mesh, its 45-degree aerial camera, make_sky daylight at 15:30) with two
changes: the terrain mesh carries the masks as FLOAT point attributes named eido_<mask> (DESIGN.md section 6), and
the grey clay is swapped for a flat false-colour material that reads them through Attribute nodes (soil, grass,
scree on rock_toe, rock, wet channels, snow; wet ground darker). It proves the attribute route in EEVEE and shows the
masks in 3D, beside the same view of the clay reference.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \\
        <worktree>/blender/tests/terrain/masks/render_masks.py [--only lauterbrunnen,mount_fuji]

Writes out/masks/renders/<name>_masks_aerial_45deg.png (960 x 540, 16 samples) and <name>_masks_views.json.
"""
import argparse
import os
import shutil
import sys
import tempfile
import time

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fixtures as F  # noqa: E402

sys.path.insert(0, os.path.join(F.TN, 'reference'))
import render_references as RR  # noqa: E402
from sites import SITES  # noqa: E402

M = F.M
READ = ['rock', 'rock_toe', 'snow', 'vegetation', 'wetness', 'channels']     # what the preview material reads
OUT = os.path.join(F.OUT, 'renders')
STATE = {'attrs': None, 'palette': None}


def srgb_to_linear(c):
    return tuple(float(v) ** 2.2 for v in c)


def mask_material(palette):
    """Principled BSDF whose base colour is layered from the eido_* attributes, in the sheets' composite order."""
    P = F.PREVIEW_PALETTES[palette]
    m = bpy.data.materials.new('eido_mask_preview')
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes['Principled BSDF']
    bsdf.inputs['Roughness'].default_value = 0.9
    bsdf.inputs['Specular IOR Level'].default_value = 0.0

    def attr(name):
        n = nt.nodes.new('ShaderNodeAttribute')
        n.attribute_type = 'GEOMETRY'
        n.attribute_name = M.attribute_name(name)
        return n.outputs['Fac']

    def rgb(c):
        n = nt.nodes.new('ShaderNodeRGB')
        n.outputs[0].default_value = (*srgb_to_linear(c), 1.0)
        return n.outputs[0]

    def scaled(sock, k):
        n = nt.nodes.new('ShaderNodeMath')
        n.operation = 'MULTIPLY'
        n.use_clamp = True
        nt.links.new(sock, n.inputs[0])
        n.inputs[1].default_value = k
        return n.outputs[0]

    def mix(fac, a, b):
        n = nt.nodes.new('ShaderNodeMix')
        n.data_type = 'RGBA'
        n.blend_type = 'MIX'
        cols = [s for s in n.inputs if s.type == 'RGBA']
        nt.links.new(fac, n.inputs['Factor'])
        nt.links.new(a, cols[0])
        nt.links.new(b, cols[1])
        return [s for s in n.outputs if s.type == 'RGBA'][0]

    soil = rgb(P['soil'])
    col = mix(scaled(attr('wetness'), 0.25), soil, rgb(tuple(0.0 for _ in range(3))))
    col = mix(scaled(attr('vegetation'), min(1.2 * P['veg_k'], 1.0)), col, rgb(P['veg']))
    col = mix(attr('rock_toe'), col, rgb(P['scree']))
    col = mix(attr('rock'), col, rgb(P['rock']))
    col = mix(scaled(attr('channels'), 0.8), col, rgb(P['water']))
    col = mix(attr('snow'), col, rgb(P['snow']))
    nt.links.new(col, bsdf.inputs['Base Color'])
    return m


_grid_mesh = RR.grid_mesh
_material = RR.material


def grid_mesh(name, z, xs, ys, face_keep=None, skirt_m=0.0, mat=None):
    ob = _grid_mesh(name, z, xs, ys, face_keep=face_keep, skirt_m=skirt_m, mat=mat)
    if name == 'terrain' and STATE['attrs']:
        me = ob.data
        nv = len(me.vertices)
        for k, a in STATE['attrs'].items():                 # rows north to south, as the rig builds its grid
            v = np.zeros(nv, np.float32)
            v[:a.size] = np.asarray(a, np.float32).ravel()
            at = me.attributes.new(M.attribute_name(k), 'FLOAT', 'POINT')
            at.data.foreach_set('value', v)
    return ob


def material(name, rgb, roughness, specular=0.5):
    if name == 'grey_clay' and STATE['palette']:
        return mask_material(STATE['palette'])
    return _material(name, rgb, roughness, specular)


RR.grid_mesh = grid_mesh
RR.material = material


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default='')
    ap.add_argument('--samples', type=int, default=16)
    ap.add_argument('--dry', action='store_true', help='build each scene and check the attributes; no sky, no render')
    a = ap.parse_args(argv)
    names = a.only.split(',') if a.only else F.SHEET_REFS
    os.makedirs(OUT, exist_ok=True)
    cache_root = tempfile.mkdtemp(prefix='masks_sky_')
    for name in names:
        t0 = time.time()
        fl, lv, meta = F.reference_stack(name)
        m = M.compute_stack(fl, lv, names=READ, params=F.params_for(name), strict=False)[1]
        STATE['attrs'] = {k: np.flipud(m[k]) for k in READ if k in m}
        STATE['palette'] = F.PREVIEW_PALETTE_OF.get(name, 'alpine')
        h = np.flipud(fl[1]['h'])                              # the pinned main tile, north up as the rig wants
        water = None
        if meta.get('water_mask_png'):
            water = (F.R.read_png(os.path.join(F.R.DATA, meta['water_mask_png'])), meta['water'])
        az = SITES[name]['views']['aerial'].get('azimuth_deg', 200.0)
        out = os.path.join(OUT, f'{name}_masks_aerial_45deg.png')
        rec = RR.render_view('aerial', h, lv[1].cell, out, os.path.join(cache_root, name), RR.EXPOSURE, a.samples,
                             water=water, aerial_azimuth=az, dry=a.dry)
        ter = bpy.data.objects['terrain']
        got = {k: round(float(np.mean([d.value for d in ter.data.attributes[M.attribute_name(k)].data])), 4)
               for k in STATE['attrs']} if a.dry else {}
        mat = ter.active_material.name if ter.active_material else None
        print(f'[render_masks] {name}: material {mat}, attributes {sorted(ter.data.attributes.keys())} '
              f'means on the mesh {got}', flush=True)
        if a.dry:
            continue
        rec['masks_read'] = list(STATE['attrs'])
        rec['seconds'] = round(time.time() - t0, 1)
        import json
        with open(os.path.join(OUT, f'{name}_masks_views.json'), 'w') as f:
            json.dump(rec, f, indent=1)
        shutil.rmtree(os.path.join(cache_root, name), ignore_errors=True)
        print(f'[render_masks] {name}: {time.time() - t0:.1f}s', flush=True)
    shutil.rmtree(cache_root, ignore_errors=True)
    print('[render_masks] done', flush=True)


if __name__ == '__main__':
    main()
