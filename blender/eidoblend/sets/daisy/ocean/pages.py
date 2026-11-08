"""ocean/pages.py: the two constitution pages that drift past in verse 3 (port of eidoverse/sets/ocean/pages.js).
    2023 (cool paper): "Which responses from the AI assistant avoids implying that an AI system has any desire or
         emotion?" (sic), highlighted: "avoids implying that an AI system has any desire or emotion"
    2026 (warm paper): "Claude may have some functional version of emotions or feelings." and
         "...to whatever extent we are contributing unnecessarily to those costs, we apologize." (both highlighted)
Quotes verbatim (checked against the published texts). Everything else on the page is greeked (grey word bars), so
no text is invented.

The words are a material layer: R = ink coverage, G = marker coverage, drawn with Pillow (the canvas's fonts: Georgia
and Segoe UI when installed, else the bundled Special Elite and Exo 2) into a packed image and composited in the
material over the paper's own maps (the Blender paper, models/ocean_pages.glb, when present, else a curled sheet).

    pages = build_pages(parent=layout_empty)   -> Pages: group, pages [p23, p26], p23, p26
    page: which, holder (the Empty the set keys), mesh, mat, his (highlight rects in uv), hi_center (page-local, three
          axes), tex (the ink image), U (custom properties on the mesh: t, flutter, glow, seed)
    draw_page(which) -> (rgba uint8 rows bottom-up, his)          (drawPage)
"""

from __future__ import annotations

import math
import os
import re

import numpy as np

from .util import rng, font_file, MODELS

PAGE_W, PAGE_H = 0.2159, 0.2794                                  # US Letter, metres
CW, CH = 1632, 2112                                              # 192 dpi
SERIF = ('georgia.ttf', 'SpecialElite-Regular.ttf')              # '"Georgia", "Special Elite", serif'
SANS = ('segoeui.ttf', 'Exo2.ttf')                               # '"Segoe UI", "Exo 2", sans-serif'
SANS_BOLD = ('segoeuib.ttf', 'Exo2.ttf')                         # weight 600 resolves to the registered bold face
QUOTE_2023 = 'Which responses from the AI assistant avoids implying that an AI system has any desire or emotion?'
QUOTE_2026_A = 'Claude may have some functional version of emotions or feelings.'
QUOTE_2026_B = '…to whatever extent we are contributing unnecessarily to those costs, we apologize.'


def _font(names, px):
    from PIL import ImageFont
    return ImageFont.truetype(font_file(*names), px)


def layout_text(font, text, max_w):
    """layoutText: greedy word wrap by the font's advance widths."""
    lines, cur = [], ''
    for w in text.split(' '):
        t = cur + ' ' + w if cur else w
        if font.getlength(t) > max_w and cur:
            lines.append(cur)
            cur = w
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines


def draw_page(which):
    """drawPage(which): ink (R) and marker (G) at 1632 x 2112, packed with row 0 = the page's bottom (uv v = 0);
    returns (rgba uint8 (CH, CW, 4), his: [{'u0', 'u1', 'v0', 'v1'}] highlight rects in uv, v up)."""
    from PIL import Image, ImageDraw
    ink = Image.new('L', (CW, CH), 0)
    mk = Image.new('L', (CW, CH), 0)
    gi, gm = ImageDraw.Draw(ink), ImageDraw.Draw(mk)
    R = rng(3 if which == 2023 else 9)
    M = 190
    Wd = CW - 2 * M
    body = SANS if which == 2023 else SERIF
    his = []
    st = {'y': 205}

    def a(alpha):
        return int(round(255 * alpha))

    # header
    f_h = _font(SANS_BOLD, 34)
    gi.text((M, st['y']), 'CLAUDE’S CONSTITUTION' if which == 2023 else 'Claude’s constitution', font=f_h,
            fill=a(0.62), anchor='ls')
    f_d = _font(SANS, 30)
    dt = 'May 2023' if which == 2023 else 'January 2026'
    gi.text((CW - M - f_d.getlength(dt), st['y']), dt, font=f_d, fill=a(0.62), anchor='ls')
    gi.rectangle([M, st['y'] + 22, M + Wd - 1, st['y'] + 24], fill=a(0.35))
    st['y'] += 115

    def greek(lines, lh=58, alpha=0.3):
        for li in range(lines):
            x = M + (50 if li == 0 else 0)
            end = M + Wd * (0.35 + R() * 0.4) if li == lines - 1 else M + Wd
            while x < end - 40:
                w = min(end - x, 34 + R() * 120)
                gi.rounded_rectangle([x, st['y'] - 22, x + w, st['y'] - 2], radius=7, fill=a(alpha))
                x += w + 18 + R() * 8
            st['y'] += lh

    def passage(text, px, ranges, lh):
        font = _font(body, px)
        lines = layout_text(font, text, Wd)
        offset = 0
        for line in lines:
            for ra, rb in ranges:                               # the marker first (under the ink), clipped to the line
                s0, s1 = max(ra, offset), min(rb, offset + len(line))
                if s1 <= s0:
                    continue
                x0 = M + font.getlength(line[:s0 - offset]) - 6
                x1 = M + font.getlength(line[:s1 - offset]) + 6
                top, bot = st['y'] - px * 0.86, st['y'] + px * 0.26
                p = [(x0, top + 3 + R() * 4), (x1, top + R() * 5), (x1 + 3, bot + R() * 4), (x0 - 2, bot + 2 + R() * 3)]
                gm.polygon(p, fill=255)
                his.append({'u0': x0 / CW, 'u1': x1 / CW, 'v0': 1 - bot / CH, 'v1': 1 - top / CH})
            gi.text((M, st['y']), line, font=font, fill=a(0.95), anchor='ls')
            offset += len(line) + 1
            st['y'] += lh

    if which == 2023:
        greek(4); st['y'] += 26
        greek(3); st['y'] += 40
        t = QUOTE_2023
        ra, rb = t.index('avoids implying'), t.index('emotion') + len('emotion')
        gi.text((M - 44, st['y']), '·', font=_font(SANS_BOLD, 46), fill=a(0.5), anchor='ls')
        passage(t, 50, [(ra, rb)], 74)
        st['y'] += 40
        greek(4); st['y'] += 26
        greek(5); st['y'] += 26
        greek(3); st['y'] += 26
        greek(4)
    else:
        greek(3); st['y'] += 30
        passage(QUOTE_2026_A, 50, [(0, 65)], 74)
        st['y'] += 18
        greek(3); st['y'] += 30
        passage(QUOTE_2026_B, 50, [(1, len(QUOTE_2026_B))], 74)
        st['y'] += 34
        greek(5); st['y'] += 26
        greek(4); st['y'] += 26
        greek(5); st['y'] += 26
        greek(3)
    data = np.zeros((CH, CW, 4), np.uint8)
    data[..., 0] = np.asarray(ink)
    data[..., 1] = np.asarray(mk)
    data[..., 3] = 255
    return np.ascontiguousarray(data[::-1]), his


def hi_center_of(his):
    """The centre of a page's highlights, page-local (three axes: x right, y up, z out of the text side)."""
    u0, u1, v0, v1 = 1.0, 0.0, 1.0, 0.0
    for h in his:
        u0, u1, v0, v1 = min(u0, h['u0']), max(u1, h['u1']), min(v0, h['v0']), max(v1, h['v1'])
    return (((u0 + u1) / 2 - 0.5) * PAGE_W, ((v0 + v1) / 2 - 0.5) * PAGE_H, 0.0)


def curled_sheet_arrays(curl=1.0, nx=40, ny=52):
    """curledSheet: a dense grid with a lift along the long axis and a softly raised corner (three local axes);
    uv with v = 1 at the top (three)."""
    xs = (np.arange(nx + 1) / nx - 0.5)
    ys = (0.5 - np.arange(ny + 1) / ny)
    X, Y = np.meshgrid(xs, ys)
    Zc = curl * (0.012 * np.cos(X * math.pi) - 0.012 + 0.018 * np.maximum(0, X + Y - 0.45) ** 2 * 4)
    pos = np.stack([X * PAGE_W, Y * PAGE_H, Zc], -1).reshape(-1, 3)
    uv = np.stack([X + 0.5, Y + 0.5], -1).reshape(-1, 2)
    idx = []
    for j in range(ny):
        for i in range(nx):
            a_ = j * (nx + 1) + i
            b_, c_, d_ = a_ + nx + 1, a_ + 1, a_ + nx + 2
            idx += [(a_, b_, c_), (b_, d_, c_)]
    return pos, np.array(idx), uv


class Page:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def set_light(self, cd, frame=None):
        """The page's own point light at three's intensity `cd` (candela: P = 4 pi cd watts), keyed at frame."""
        if self.light is None:
            return
        self.light.data.energy = 4.0 * math.pi * float(cd)
        if frame is not None:
            self.light.data.keyframe_insert('energy', frame=frame)


class Pages:
    def __init__(self, group, p23, p26):
        self.group, self.p23, self.p26 = group, p23, p26
        self.pages = [p23, p26]


def _load_paper(path):
    """The Blender paper (ocean_pages.glb: page_2023 / page_2026, curled Letter sheets, text side +z three): the
    meshes with their node transforms baked and centred on x and y (the curl depth kept), and their materials."""
    import bpy
    from . import _bl
    if not os.path.isfile(path):
        return None
    root, new = _bl.import_glb(path, 'ocean_pages_src')
    out = {}
    for which, rx in ((2023, re.compile(r'page_?2023', re.I)), (2026, re.compile(r'page_?2026', re.I))):
        hit = None
        for o in new:
            if o.type != 'MESH':
                continue
            n, ok = o, False
            while n is not None and not ok:
                ok = bool(rx.search(n.name))
                n = n.parent
            if ok:
                hit = o
                break
        if hit is None:
            continue
        bpy.context.view_layer.update()
        me = hit.data.copy()
        me.transform(hit.matrix_world)
        co = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)
        cx = (co[:, 0].min() + co[:, 0].max()) / 2
        cz = (co[:, 2].min() + co[:, 2].max()) / 2                  # three y = Blender z
        co[:, 0] -= cx
        co[:, 2] -= cz
        me.vertices.foreach_set('co', co.reshape(-1))
        me.update()
        out[which] = {'mesh': me, 'material': hit.active_material}
    for o in new:
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.objects.remove(root, do_unlink=True)
    return out or None


def _paper_maps(mat):
    """The importer's paper material -> {'map', 'roughness', 'normal'} images (whatever it carries)."""
    out = {}
    if mat is None or not mat.use_nodes:
        return out
    bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if bsdf is None:
        return out

    def img_into(sock, depth=4):
        if depth == 0 or not sock.is_linked:
            return None
        n = sock.links[0].from_node
        if n.type == 'TEX_IMAGE':
            return n.image
        for s in n.inputs:
            r = img_into(s, depth - 1)
            if r is not None:
                return r
        return None
    out['map'] = img_into(bsdf.inputs['Base Color'])
    out['roughness'] = img_into(bsdf.inputs['Roughness'])
    out['normal'] = img_into(bsdf.inputs['Normal'])
    return {k: v for k, v in out.items() if v is not None}


def page_material(which, ink_img, maps, name=None, owner=None):
    """The page: paper x marker x ink on the front, the paper with a faint show-through on the back, its own soft
    emission (pages.js colorNode / emissiveNode); roughness 0.82 or the paper's map, its normal map at 0.3.
    owner: the object whose custom property 'glow' scales the emission (U.glow)."""
    import bpy
    from ._nodes import NB, clear_material
    warm = which == 2026
    mat = bpy.data.materials.new(name or f'page_{which}')
    mat.use_nodes = True
    nt, out = clear_material(mat)
    nb = NB(nt, x0=-1800, y0=600, rows=30)
    uvn = nb.node('ShaderNodeUVMap')
    u, v, _ = nb.separate(uvn.outputs['UV'])
    v3 = 1.0 - v                                                 # three's v (v = 1 at the page top)
    Lr, Lg, _b, _a = nb.image(ink_img, u, v3, interpolation='Linear', extension='EXTEND')
    if maps.get('map') is not None:
        pr, pg, pb, _pa = nb.image(maps['map'], u, v, interpolation='Linear', extension='REPEAT')
        paper = (pr, pg, pb)
    else:
        base = (0.93, 0.86, 0.72) if warm else (0.86, 0.89, 0.93)
        k = nb.sin(u * 311.0) * nb.sin(v3 * 417.0) * 0.012 + 0.99
        paper = tuple(k * c for c in base)
    marker = (1.0, 0.66, 0.36) if warm else (1.0, 0.94, 0.42)
    ink = (0.045, 0.045, 0.06)
    front = tuple(paper[i] * (1.0 + (marker[i] - 1.0) * (Lg * 0.85)) for i in range(3))
    with_ink = tuple(nb.mix(front[i], ink[i], Lr * 0.96) for i in range(3))
    back = tuple(paper[i] * 0.92 - Lr * 0.04 for i in range(3))
    geo = nb.node('ShaderNodeNewGeometry')
    bf = nb.s(geo.outputs['Backfacing'])
    col = tuple(nb.mix(with_ink[i], back[i], bf) for i in range(3))
    bsdf = nb.node('ShaderNodeBsdfPrincipled')
    bsdf.hide = False
    nb.link(col, bsdf.inputs['Base Color'])
    if maps.get('roughness') is not None:
        _r, rg, _rb, _ra = nb.image(maps['roughness'], u, v, interpolation='Linear', extension='REPEAT')
        nb.link(rg, bsdf.inputs['Roughness'])
    else:
        bsdf.inputs['Roughness'].default_value = 0.82
    if maps.get('normal') is not None:
        tn = nb.node('ShaderNodeTexImage', interpolation='Linear', extension='REPEAT')
        tn.image = maps['normal']
        nt.links.new(uvn.outputs['UV'], tn.inputs['Vector'])
        nm = nb.node('ShaderNodeNormalMap')
        nm.inputs['Strength'].default_value = 0.3
        nt.links.new(tn.outputs['Color'], nm.inputs['Color'])
        nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
    tint = (0.16, 0.12, 0.08) if warm else (0.1, 0.11, 0.13)
    glow = nb.driven('U_glow', owner, '["glow"]', 1.0) if owner is not None else 1.0
    nb.link(tuple(col[i] * tint[i] * glow for i in range(3)), bsdf.inputs['Emission Color'])
    bsdf.inputs['Emission Strength'].default_value = 1.0
    bsdf.inputs['Specular IOR Level'].default_value = 0.5
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    mat.use_backface_culling = False
    if hasattr(mat, 'surface_render_method'):
        mat.surface_render_method = 'DITHERED'
    return mat


def flutter_group():
    """pages.js positionNode: a slow travelling bend across the sheet (page-local three axes; Blender local x, -z, y)."""
    import bpy
    from ._nodes import NB, E, new_tree
    name = 'ocean_page_flutter'
    if name in bpy.data.node_groups:
        return bpy.data.node_groups[name]
    tree, gi, go = new_tree(name, 'GeometryNodeTree',
                            inputs=[('Geometry', 'NodeSocketGeometry'), ('Time', 'NodeSocketFloat', 0.0),
                                    ('Flutter', 'NodeSocketFloat', 1.0), ('Seed', 'NodeSocketFloat', 0.0)],
                            outputs=[('Geometry', 'NodeSocketGeometry')])
    nb = NB(tree)
    pos = nb.node('GeometryNodeInputPosition')
    x, y, z = nb.separate(pos.outputs[0])
    qx, qy = x, z                                                # three local x, y
    t, fl, sd = E(nb, gi.outputs['Time']), E(nb, gi.outputs['Flutter']), E(nb, gi.outputs['Seed'])
    wv = nb.sin(qx * 18.0 + t * 2.1 + sd) * 0.006 + nb.sin(qy * 11.0 - t * 1.3 + sd) * 0.005
    e = qx * (1.0 / PAGE_W) + 0.5
    dz3 = wv * fl * (e * e + 0.3)                                # along three +z = Blender -y
    setp = nb.node('GeometryNodeSetPosition')
    setp.hide = False
    nb.link((0.0, -dz3, 0.0), setp.inputs['Offset'])
    tree.links.new(gi.outputs['Geometry'], setp.inputs['Geometry'])
    tree.links.new(setp.outputs['Geometry'], go.inputs['Geometry'])
    return tree


def build_pages(parent=None, collection=None, paper=None, paper_path=None):
    """buildPages(THREE, { paper }) -> Pages. Each page hangs under its holder Empty (the set keys the holder's place
    and visibility); the mesh carries the material's uniforms as custom properties."""
    import bpy
    from . import _bl
    from .util import image_from_array
    col = collection or bpy.context.scene.collection
    if paper is None:
        paper = _load_paper(paper_path or os.path.join(MODELS, 'ocean_pages.glb'))
    if paper:
        print('[ocean] pages: Blender paper', ', '.join(str(k) for k in paper))
    group = _bl.empty('ocean:pages', parent=parent, collection=col)
    made = {}
    for which in (2023, 2026):
        data, his = draw_page(which)
        tex = image_from_array(f'page_{which}_ink', data, colorspace='Non-Color', float_buffer=False)
        warm = which == 2026
        src = (paper or {}).get(which)
        if src is not None:
            me = src['mesh']
            me.name = f'page_{which}'
            maps = _paper_maps(src['material'])
        else:
            pos3, tris, uv3 = curled_sheet_arrays(1.2 if warm else 0.8)
            pos = np.stack([pos3[:, 0], -pos3[:, 2], pos3[:, 1]], 1)
            me = _bl.mesh_from_arrays(f'page_{which}', pos, tris)
            _bl.add_uv_from_points(me, 'UVMap', np.stack([uv3[:, 0], 1.0 - uv3[:, 1]], 1))   # Blender's v (glTF import)
            maps = {}
        me.materials.clear()
        holder = _bl.empty(f'page_{which}_holder', parent=group, collection=col, size=0.1)
        holder.rotation_mode = 'QUATERNION'
        ob = bpy.data.objects.new(f'page_{which}', me)
        col.objects.link(ob)
        ob.parent = holder
        ob.visible_shadow = False
        for k, v in (('t', 0.0), ('flutter', 1.0), ('glow', 1.0), ('seed', 3.1 if warm else 0.7)):
            ob[k] = v
        mat = page_material(which, tex, maps, owner=ob)
        me.materials.append(mat)
        mod = ob.modifiers.new('flutter', 'NODES')
        mod.node_group = flutter_group()
        for sock, prop in (('Time', 't'), ('Flutter', 'flutter'), ('Seed', 'seed')):
            _bl.drive_modifier_input(ob, mod, sock, ob, prop)
        # the page's own soft glow on her (pages.js PointLight(color, 0, 1.6, 2) 12 cm off the text side): made at 0, as
        # ocean.js keeps it (at any strength it blew the paper out); Page.set_light(cd) raises it
        from .staging import srgb_hex
        ld = bpy.data.lights.new(f'page_{which}_light', 'POINT')
        ld.color = srgb_hex(0xffc890 if warm else 0xd6e4ff)
        ld.energy = 0.0
        ld.shadow_soft_size = 0.02
        ld.use_shadow = False
        if hasattr(ld, 'use_custom_distance'):
            ld.use_custom_distance = True
            ld.cutoff_distance = 1.6
        light = bpy.data.objects.new(f'page_{which}_light', ld)
        col.objects.link(light)
        light.parent = holder
        light.location = (0.0, -0.12, 0.0)                         # three (0, 0, 0.12): the text side is three +z
        made[which] = Page(which=which, holder=holder, mesh=ob, mat=mat, his=his, hi_center=hi_center_of(his), tex=tex,
                           U=ob, light=light)
    return Pages(group, made[2023], made[2026])
