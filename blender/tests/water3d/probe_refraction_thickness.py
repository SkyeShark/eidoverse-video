"""Probe: what EEVEE's refraction does with the water's thickness. Reopens a baked probe .blend (the dam break or the
pour) and renders the same frames with the material output's Thickness unlinked (EEVEE's own default), linked to the
baked 'thick' attribute as a slab, and as a sphere (or the variants= listed: zero, slab<NN>, bed<NN> = the material's
own exit/bed rule with NN % of the path kept over a bed), plus a Cycles reference of the same frames (cycles=0 skips
it).

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 \
        bash run_blender.sh <worktree>/blender/tests/water3d/probe_refraction_thickness.py -- \
        blend=out/w3d_dambreak.blend frames=132,180 tag=dam

Writes out/probe_thick_<tag>_<variant>_f####.png and a sheet (rows = variants, columns = frames).
"""

import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
A = dict(x.split('=', 1) for x in (sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []) if '=' in x)
BLEND = os.path.join(HERE, A.get('blend', 'out/w3d_dambreak.blend'))
FRAMES = [int(f) for f in A.get('frames', '132,180').split(',')]
TAG = A.get('tag', 'dam')
SAMPLES = int(A.get('samples', 16))
bpy.ops.wm.open_mainfile(filepath=BLEND)
import _scene as S  # noqa: E402  (after the open: _scene's OUT is next to this file)

sc = bpy.context.scene
sc.eevee.taa_render_samples = SAMPLES
mats = [m for m in bpy.data.materials if m.get('w3d_shading') == 'lit']
print('materials', [m.name for m in mats])


VARIANTS = A.get('variants', 'default,slab,sphere').split(',')


def set_variant(v):
    """default: Thickness unlinked; zero: 0 (one interface, the ray continues in the refracted direction);
    slab / sphere: the baked 'thick'; slab<NN>: NN % of 'thick' as a slab; attr:<name>[:slab|sphere]: another
    baked attribute."""
    for m in mats:
        nt = m.node_tree
        out = [n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'][0]
        for lk in list(out.inputs['Thickness'].links):
            nt.links.remove(lk)
        out.inputs['Thickness'].default_value = 0.0
        if v == 'default':
            m.thickness_mode = 'SPHERE'                               # Blender's own default
            continue
        if v == 'zero':
            z = nt.nodes.get('probe_zero') or nt.nodes.new('ShaderNodeValue')
            z.name = 'probe_zero'
            z.outputs[0].default_value = 0.0
            nt.links.new(z.outputs[0], out.inputs['Thickness'])
            continue
        if v.startswith('bed'):
            # bed<NN>: the material's own rule, exit * (1 - bed * (1 - NN %)), slab
            share = int(v[3:]) / 100.0
            ex = nt.nodes.get('probe_exit') or nt.nodes.new('ShaderNodeAttribute')
            ex.name, ex.attribute_type, ex.attribute_name = 'probe_exit', 'GEOMETRY', 'exit'
            bd = nt.nodes.get('probe_bed') or nt.nodes.new('ShaderNodeAttribute')
            bd.name, bd.attribute_type, bd.attribute_name = 'probe_bed', 'GEOMETRY', 'bed'
            k = nt.nodes.get('probe_k') or nt.nodes.new('ShaderNodeMath')
            k.name, k.operation = 'probe_k', 'MULTIPLY_ADD'          # bed * (share - 1) + 1
            nt.links.new(bd.outputs['Fac'], k.inputs[0])
            k.inputs[1].default_value = share - 1.0
            k.inputs[2].default_value = 1.0
            m2 = nt.nodes.get('probe_m2') or nt.nodes.new('ShaderNodeMath')
            m2.name, m2.operation = 'probe_m2', 'MULTIPLY'
            nt.links.new(ex.outputs['Fac'], m2.inputs[0])
            nt.links.new(k.outputs[0], m2.inputs[1])
            nt.links.new(m2.outputs[0], out.inputs['Thickness'])
            m.thickness_mode = 'SLAB'
            continue
        name, mode, scale = 'thick', ('SPHERE' if v == 'sphere' else 'SLAB'), 1.0
        if v.startswith('slab') and v[4:].isdigit():
            scale = int(v[4:]) / 100.0
        if v.startswith('attr:'):
            parts = v.split(':')
            name = parts[1]
            mode = parts[2].upper() if len(parts) > 2 else 'SLAB'
        at = nt.nodes.get('probe_thick') or nt.nodes.new('ShaderNodeAttribute')
        at.name = 'probe_thick'
        at.attribute_type = 'GEOMETRY'
        at.attribute_name = name
        mul = nt.nodes.get('probe_mul') or nt.nodes.new('ShaderNodeMath')
        mul.name = 'probe_mul'
        mul.operation = 'MULTIPLY'
        mul.inputs[1].default_value = scale
        nt.links.new(at.outputs['Fac'], mul.inputs[0])
        nt.links.new(mul.outputs[0], out.inputs['Thickness'])
        m.thickness_mode = mode


shots = []
ok = True
for v in VARIANTS:
    set_variant(v)
    for f in FRAMES:
        p = os.path.join(S.OUT, f'probe_thick_{TAG}_{v.replace(":", "-")}_f{f:04d}.png')
        ok &= S.render(sc, f, p)
        shots.append(p)
set_variant('default')
if A.get('cycles', '1') == '0':
    S.contact_sheet(shots, os.path.join(S.OUT, f'probe_thick_{TAG}_sheet.png'), cols=len(FRAMES))
    print('ALL PASS' if ok else 'SOME FAIL')
    raise SystemExit(0)
sc.render.engine = 'CYCLES'
sc.cycles.samples = 64
sc.cycles.device = 'GPU'
try:
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'OPTIX'
    prefs.get_devices()
    for d in prefs.devices:
        d.use = d.type == 'OPTIX'
except Exception as e:  # noqa: BLE001
    print('cycles device setup:', e)
for f in FRAMES:
    p = os.path.join(S.OUT, f'probe_thick_{TAG}_cycles_f{f:04d}.png')
    ok &= S.render(sc, f, p)
    shots.append(p)
S.contact_sheet(shots, os.path.join(S.OUT, f'probe_thick_{TAG}_sheet.png'), cols=len(FRAMES))
print('ALL PASS' if ok else 'SOME FAIL')
