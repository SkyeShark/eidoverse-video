"""A top-down render of D across a window edge (SURFACING_DESIGN.md 5.4, package 1, item 3: no line at 2x zoom):

    bash run_blender.sh blender/tests/terrain/surface_data/render_seam.py --case toroweap [--level 4] [--side west]
    (queue it with EIDO_GPU_WRAP on a shared machine: blender/tests/_where.py)

A plane at the ground's mean height spans 64 child cells either side of the level's window edge; its material reads
the D atlas the way the material's reader does (SURFACING_DESIGN.md 2.4: the level by the window holding the pixel,
the atlas rectangle of that level, one Linear EXTEND read), and emits the field normal lit from the north-west
(n . l), so a step in D across the edge shows as a line. Orthographic, 960 x 540 at one sample, Standard view. Writes
out/surface_data/seam_<case>_L<level>_<side>.png (the render), _2x.png (the edge band at 2x) and .json (the mean
absolute step across the edge against the mean step between texel columns either side).
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _cases as C  # noqa: E402


def build_reader(nt, img, tiles, lay, levels):
    """Nodes: uv of the finest of `levels` holding the pixel -> the atlas image -> its colour."""
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Object'], sep.inputs['Vector'])
    x, y = sep.outputs['X'], sep.outputs['Y']

    def math_node(op, a, b=None):
        n = nt.nodes.new('ShaderNodeMath')
        n.operation = op
        for k, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[k].default_value = float(v)
            else:
                nt.links.new(v, n.inputs[k])
        return n.outputs[0]

    def uv_of(t):
        u0, v0, du, dv = t.rect(lay)
        u = math_node('ADD', math_node('MULTIPLY', math_node('SUBTRACT', x, t.x0), du / t.side), u0)
        v = math_node('ADD', math_node('MULTIPLY', math_node('SUBTRACT', y, t.y0), dv / t.side), v0)
        return u, v
    parent, child = levels
    up, vp = uv_of(tiles[parent])
    uc, vc = uv_of(tiles[child])
    tcl = tiles[child]
    cx, cy = tcl.x0 + tcl.side / 2, tcl.y0 + tcl.side / 2
    dx = math_node('ABSOLUTE', math_node('SUBTRACT', x, cx))
    dy = math_node('ABSOLUTE', math_node('SUBTRACT', y, cy))
    inside = math_node('LESS_THAN', math_node('MAXIMUM', dx, dy), tcl.side / 2)
    u = math_node('ADD', up, math_node('MULTIPLY', math_node('SUBTRACT', uc, up), inside))
    v = math_node('ADD', vp, math_node('MULTIPLY', math_node('SUBTRACT', vc, vp), inside))
    comb = nt.nodes.new('ShaderNodeCombineXYZ')
    nt.links.new(u, comb.inputs['X'])
    nt.links.new(v, comb.inputs['Y'])
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = img
    tex.interpolation = 'Linear'
    tex.extension = 'EXTEND'
    nt.links.new(comb.outputs['Vector'], tex.inputs['Vector'])
    return tex.outputs['Color']


def main():
    import bpy
    import numpy as np
    from eidoblend.terrain import surface as S
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    name = a[a.index('--case') + 1] if '--case' in a else 'toroweap'
    t = C.terrain(name)
    roles = [lv.role for lv in t.levels]
    li = int(a[a.index('--level') + 1]) if '--level' in a else roles.index('main') + 2
    side = a[a.index('--side') + 1] if '--side' in a else 'west'
    sd = S.bake_surface(t, cache=os.path.join(C.OUT, 'cache', name))
    img = sd.images()['D']
    lay = sd.layouts['D']
    child, parent = t.levels[li], t.levels[li - 1]
    ex = child.x0 if side == 'west' else child.x1
    span = 64 * child.cell
    cy = child.y0 + child.side / 2
    z = float(np.mean(t.fields(li)['h']))
    W, H = 960, 540
    sx = 2 * span
    sy = sx * H / W
    scene = bpy.data.scenes.new('seam_probe')
    me = bpy.data.meshes.new('plane')
    me.from_pydata([(ex - span, cy - sy / 2, z), (ex + span, cy - sy / 2, z), (ex + span, cy + sy / 2, z),
                    (ex - span, cy + sy / 2, z)], [], [(0, 1, 2, 3)])
    ob = bpy.data.objects.new('plane', me)
    scene.collection.objects.link(ob)
    mat = bpy.data.materials.new('seam')
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    col = build_reader(nt, img, lay.tiles, lay, (parent.index, child.index))
    sep = nt.nodes.new('ShaderNodeSeparateColor')
    nt.links.new(col, sep.inputs['Color'])
    # n . l with l from the north-west at 45 degrees, n = (nx, ny, sqrt(1 - nx^2 - ny^2))
    lx, ly, lz = -0.5, 0.5, math.sqrt(0.5)
    nodes = nt.nodes

    def m(op, a_, b_=None):
        n = nodes.new('ShaderNodeMath')
        n.operation = op
        for k, v in enumerate((a_, b_)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[k].default_value = float(v)
            else:
                nt.links.new(v, n.inputs[k])
        return n.outputs[0]
    nx, ny = sep.outputs[0], sep.outputs[1]
    nz = m('SQRT', m('MAXIMUM', m('SUBTRACT', m('SUBTRACT', 1.0, m('MULTIPLY', nx, nx)), m('MULTIPLY', ny, ny)), 0.0))
    lit = m('ADD', m('ADD', m('MULTIPLY', nx, lx), m('MULTIPLY', ny, ly)), m('MULTIPLY', nz, lz))
    em = nodes.new('ShaderNodeEmission')
    nt.links.new(lit, em.inputs['Strength'])
    em.inputs['Color'].default_value = (1, 1, 1, 1)
    mo = nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(em.outputs['Emission'], mo.inputs['Surface'])
    me.materials.append(mat)
    cam = bpy.data.cameras.new('cam')
    cam.type = 'ORTHO'
    cam.ortho_scale = sx
    cam.clip_end = 1.0e5
    co = bpy.data.objects.new('cam', cam)
    co.location = (ex, cy, z + 5000.0)
    scene.collection.objects.link(co)
    scene.camera = co
    r = scene.render
    r.engine = 'BLENDER_EEVEE'
    r.resolution_x, r.resolution_y, r.resolution_percentage = W, H, 100
    scene.eevee.taa_render_samples = 1
    scene.view_settings.view_transform = 'Standard'
    scene.world = bpy.data.worlds.new('w')
    r.image_settings.file_format = 'PNG'
    base = os.path.join(C.OUT, f'seam_{name}_L{li}_{side}')
    r.filepath = base + '.png'
    bpy.ops.render.render(write_still=True, scene=scene.name)
    from PIL import Image
    im = np.asarray(Image.open(base + '.png').convert('L'), np.float64)
    c = W // 2                                            # the window edge is the frame's middle column
    band = im[:, c - 60:c + 60]
    Image.fromarray(band.astype(np.uint8)).resize((240, H * 2), Image.NEAREST).save(base + '_2x.png')
    steps = np.abs(np.diff(im, axis=1)).mean(axis=0)
    at_edge = float(steps[c - 2:c + 1].max())
    typical = float(np.median(np.concatenate([steps[:c - 10], steps[c + 10:]])))
    rec = dict(case=name, level=li, side=side, edge_x=ex, step_at_edge=at_edge, typical_step=typical,
               ratio=at_edge / max(typical, 1e-9))
    with open(base + '.json', 'w', encoding='utf-8') as f:
        json.dump(rec, f, indent=1)
    print(f"[render_seam] {name} L{li} {side}: mean step at the edge {at_edge:.2f} grey levels, typical {typical:.2f}"
          f" ({rec['ratio']:.2f} x) -> {base}.png", flush=True)
    return 0


if __name__ == '__main__':
    code = main()
    sys.stdout.flush()
    os._exit(code)
