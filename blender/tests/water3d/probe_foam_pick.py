"""Probe: how the lit material's foam pick converges in EEVEE. Reopens a baked probe .blend (the pour) and renders the
same frames with the per-sample white-noise pick as built, with no churn foam at all, and with a pick that is fixed
per surface point (a 3D noise of the position, remapped to an even spread, so foam forms coherent lace and only its
edges dither), at two sample counts.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 \
        bash run_blender.sh <worktree>/blender/tests/water3d/probe_foam_pick.py -- blend=out/w3d_pour.blend frames=60,144

Writes out/probe_foam_<variant>_s<samples>_f####.png, crops of the stream and the splash, and a sheet.
"""

import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
A = dict(x.split('=', 1) for x in (sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []) if '=' in x)
BLEND = os.path.join(HERE, A.get('blend', 'out/w3d_pour.blend'))
FRAMES = [int(f) for f in A.get('frames', '60,144').split(',')]
SAMPLES = [int(s) for s in A.get('samples', '16,64').split(',')]
SCALE = float(A.get('scale', 90.0))
bpy.ops.wm.open_mainfile(filepath=BLEND)
import _scene as S  # noqa: E402

sc = bpy.context.scene
mat = [m for m in bpy.data.materials if m.get('w3d_shading') == 'lit'][0]
nt = mat.node_tree
white = [n for n in nt.nodes if n.bl_idname == 'ShaderNodeTexWhiteNoise'][0]
users = [lk.to_socket for lk in nt.links if lk.from_node == white]
churn = nt.nodes['w3d.foam_churn']
churn0 = churn.outputs[0].default_value
print('white noise feeds', [(s.node.name, s.name) for s in users], 'churn', churn0)

# the coherent pick: Noise Texture (3D, the object position) remapped from its central spread to 0..1
geo = nt.nodes.new('ShaderNodeNewGeometry')
nz = nt.nodes.new('ShaderNodeTexNoise')
nz.noise_dimensions = '3D'
nz.inputs['Scale'].default_value = SCALE
nz.inputs['Detail'].default_value = 3.0
nz.inputs['Roughness'].default_value = 0.55
nt.links.new(geo.outputs['Position'], nz.inputs['Vector'])
mr = nt.nodes.new('ShaderNodeMapRange')
mr.clamp = True
mr.inputs['From Min'].default_value = 0.32
mr.inputs['From Max'].default_value = 0.68
nt.links.new(nz.outputs['Fac'], mr.inputs['Value'])


RT = sc.eevee.ray_tracing_options
RT0 = (RT.resolution_scale, RT.screen_trace_quality)


def variant(v):
    """white | nochurn | coherent, with _rt1 = ray tracing at full resolution and full screen-trace quality."""
    base = v.replace('_rt1', '')
    for s in users:
        for lk in list(s.links):
            nt.links.remove(lk)
        nt.links.new((mr.outputs['Result'] if base == 'coherent' else white.outputs['Value']), s)
    churn.outputs[0].default_value = 0.0 if base == 'nochurn' else churn0
    RT.resolution_scale, RT.screen_trace_quality = ('1', 1.0) if v.endswith('_rt1') else RT0


shots, crops = [], []
ok = True
for v in A.get('variants', 'white,nochurn,coherent,white_rt1,coherent_rt1').split(','):
    variant(v)
    for n in SAMPLES:
        sc.eevee.taa_render_samples = n
        for f in FRAMES:
            p = os.path.join(S.OUT, f'probe_foam_{v}_s{n}_f{f:04d}.png')
            ok &= S.render(sc, f, p)
            shots.append(p)
            a = S.read_png(p)
            c = a[30:300, 360:760] if f < 100 else a[120:390, 280:680]       # the stream, or the basin
            cp = p.replace('.png', '_crop.png')
            S.write_png(cp, c)
            crops.append(cp)
S.contact_sheet(crops, os.path.join(S.OUT, 'probe_foam_crops_sheet.png'), cols=len(SAMPLES) * len(FRAMES),
                half=False)
print('ALL PASS' if ok else 'SOME FAIL')
