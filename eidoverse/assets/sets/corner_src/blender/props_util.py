"""props_util.py - helpers for the corner PROPS builds (lamp, pen, notebook, mug, books, clock,
pinned pages, chair, rug). Sits beside clib.py and never modifies it.
"""
import bpy, bmesh, math, os, random
from mathutils import Vector, Matrix
import clib

REPO = os.path.abspath(os.path.join(clib.ROOT, '..', '..', '..', '..'))
FONTS = os.path.join(REPO, 'eidoverse', 'assets', 'fonts')
WINFONTS = 'C:/Windows/Fonts'
ART = os.path.join(clib.ROOT, 'art')
os.makedirs(ART, exist_ok=True)


def font(name, size):
    from PIL import ImageFont
    for d in (FONTS, WINFONTS):
        p = os.path.join(d, name)
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    raise FileNotFoundError(name)


# ------------------------------------------------------------------------------ closeup lights
def add_lights(target, cam_pos, energy=None, world=0.12, warm=True):
    """Key (camera-right, high), fill (camera-left, low), rim (behind). Returns objects."""
    sc = bpy.context.scene
    w = sc.world or bpy.data.worlds.new('w')
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes['Background']
    bg.inputs['Color'].default_value = (0.55, 0.6, 0.68, 1)
    bg.inputs['Strength'].default_value = world
    t = Vector(target)
    c = Vector(cam_pos)
    f = (t - c)
    dist = f.length
    f.normalize()
    up = Vector((0, 0, 1))
    right = f.cross(up).normalized()
    e = energy if energy is not None else 60 * dist * dist + 1.0
    out = []
    for off, en, col, sz in (
            (-f * 0.6 + right * 0.9 + up * 0.8, e, (1.0, 0.9, 0.78) if warm else (1, 1, 1), 0.6),
            (-f * 0.8 - right * 1.0 + up * 0.15, e * 0.35, (0.78, 0.86, 1.0), 0.8),
            (f * 1.2 + up * 0.9 - right * 0.3, e * 0.7, (1, 1, 1), 0.5)):
        ld = bpy.data.lights.new('cl', 'AREA')
        ld.energy = en
        ld.size = sz * dist
        ld.color = col
        lo = bpy.data.objects.new('cl', ld)
        clib.link(lo)
        lo.location = t + off * dist
        lo.rotation_euler = (t - lo.location).to_track_quat('-Z', 'Y').to_euler()
        out.append(lo)
    return out


def lit_closeup(filename, cam_pos, target, lens=50, size=768, samples=64, energy=None, world=0.12):
    ls = add_lights(target, cam_pos, energy, world)
    sc = bpy.context.scene
    sc.cycles.samples = samples
    sc.render.resolution_x = size
    sc.render.resolution_y = size
    cd = bpy.data.cameras.new('cu')
    cd.lens = lens
    dist = (Vector(target) - Vector(cam_pos)).length
    cd.clip_start = min(0.01, dist * 0.05)
    cd.clip_end = 100
    cam = bpy.data.objects.new('cu', cd)
    clib.link(cam)
    cam.location = Vector(cam_pos)
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.camera = cam
    sc.render.filepath = os.path.join(clib.PREV, f'{filename}.png')
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(cam)
    for lo in ls:
        bpy.data.objects.remove(lo)
    p = sc.render.filepath
    print('[props] closeup', p, flush=True)
    return p


# ---------------------------------------------------------------------------------------- UVs
def uv_cyl(o, axis='Z', scale=1.0, uvname='TexUV', r_ref=None):
    """Cylindrical projection: U = arc length around `axis` (at r_ref or each vertex radius),
    V = position along the axis. Seam-wrapped per face."""
    me = o.data
    if uvname not in me.uv_layers:
        me.uv_layers.new(name=uvname)
    uvl = me.uv_layers[uvname]
    ai = 'XYZ'.index(axis)
    oi = [k for k in range(3) if k != ai]
    for poly in me.polygons:
        angs, uvs = [], []
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            a = math.atan2(co[oi[1]], co[oi[0]])
            angs.append(a)
        # unwrap across the seam
        ref = angs[0]
        un = []
        for a in angs:
            while a - ref > math.pi: a -= math.tau
            while a - ref < -math.pi: a += math.tau
            un.append(a)
        for li, a in zip(poly.loop_indices, un):
            co = me.vertices[me.loops[li].vertex_index].co
            r = r_ref if r_ref is not None else max(1e-4, math.hypot(co[oi[0]], co[oi[1]]))
            uvl.data[li].uv = (a * r / scale, co[ai] / scale)


def uv_planar(o, u_axis='X', v_axis='Y', bounds=None, uvname='ArtUV'):
    """Normalized planar projection (u,v in 0..1 across `bounds` = (umin, umax, vmin, vmax))."""
    me = o.data
    if uvname not in me.uv_layers:
        me.uv_layers.new(name=uvname)
    uvl = me.uv_layers[uvname]
    ui, vi = 'XYZ'.index(u_axis[-1]), 'XYZ'.index(v_axis[-1])
    su = -1.0 if u_axis.startswith('-') else 1.0
    sv = -1.0 if v_axis.startswith('-') else 1.0
    if bounds is None:
        us = [su * v.co[ui] for v in me.vertices]
        vs = [sv * v.co[vi] for v in me.vertices]
        bounds = (min(us), max(us), min(vs), max(vs))
    u0, u1, v0, v1 = bounds
    for li, lp in enumerate(me.loops):
        co = me.vertices[lp.vertex_index].co
        uvl.data[li].uv = ((su * co[ui] - u0) / (u1 - u0), (sv * co[vi] - v0) / (v1 - v0))
    return bounds


def clean_uvs(o, keep=('BakeUV',)):
    me = o.data
    for uvl in list(me.uv_layers):
        if uvl.name not in keep:
            me.uv_layers.remove(uvl)
    if len(me.uv_layers):
        me.uv_layers[0].active = True
        me.uv_layers[0].active_render = True


# --------------------------------------------------------------------------------- art layers
def art_hook(img_path, uvname='ArtUV', front_normal=None, extension='CLIP', strength=1.0):
    """extra_color hook: composite an RGBA painted image (alpha = ink) over the base colour.
    front_normal=(x,y,z): only faces whose geometry normal points that way receive the art."""
    def hook(nb, col, vec):
        uvn = nb.n('ShaderNodeUVMap', uv_map=uvname)
        t = nb.n('ShaderNodeTexImage')
        t.image = clib.load_img(img_path)
        t.extension = extension
        t.interpolation = 'Cubic'
        nb.l(uvn.outputs[0], t.inputs[0])
        a = t.outputs['Alpha']
        if front_normal is not None:
            geo = nb.n('ShaderNodeNewGeometry')
            dp = nb.n('ShaderNodeVectorMath', operation='DOT_PRODUCT')
            nb.l(geo.outputs['Normal'], dp.inputs[0])
            dp.inputs[1].default_value = front_normal
            m = nb.ramp(dp.outputs['Value'], 0.2, 0.5)
            a = nb.math('MULTIPLY', a, m)
        if strength != 1.0:
            a = nb.math('MULTIPLY', a, strength, clamp=True)
        return nb.mix(a, col, t.outputs['Color'])
    return hook


def multi_hook(*hooks):
    def hook(nb, col, vec):
        for h in hooks:
            col = h(nb, col, vec)
        return col
    return hook


# ----------------------------------------------------------------------------- handwriting
def hand_line(img, xy, text, fnt, fill=(28, 36, 64), jitter=1.0, rot=1.6, seed=1, alpha=(215, 255),
              spacing=0.0, baseline_wave=0.0):
    """Draw text glyph by glyph with small rotation / baseline / size jitter onto an RGBA image.
    Returns the x end position."""
    from PIL import Image, ImageDraw
    rnd = random.Random(seed)
    x, y = xy
    for i, ch in enumerate(text):
        if ch == ' ':
            x += fnt.getlength(' ') * (0.9 + 0.2 * rnd.random()) + spacing
            continue
        bbox = fnt.getbbox(ch)
        w = int(bbox[2] - bbox[0] + 8); h = int(fnt.size * 1.6)
        g = Image.new('L', (w + 16, h + 16), 0)
        ImageDraw.Draw(g).text((8 - bbox[0], 8), ch, font=fnt, fill=rnd.randint(*alpha))
        g = g.rotate(rnd.uniform(-rot, rot), resample=Image.BICUBIC, expand=False)
        dy = rnd.uniform(-jitter, jitter) + baseline_wave * math.sin(i * 0.45 + seed)
        layer = Image.new('RGBA', g.size, (*fill, 0))
        layer.putalpha(g)
        img.alpha_composite(layer, (int(x - 8), int(y + dy - 8)))
        x += fnt.getlength(ch) + spacing + rnd.uniform(-0.4, 0.4) * jitter
    return x


def ink_bleed(img, amount=0.6):
    """Soften ink edges slightly (fibre bleed)."""
    from PIL import ImageFilter
    a = img.getchannel('A').filter(ImageFilter.GaussianBlur(amount))
    img.putalpha(a)
    return img
