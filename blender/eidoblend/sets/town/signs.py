"""eidoblend.sets.town.signs: the boards over the town's shops, and what they say when you give them something to say.
Blender (the words are laid out by Blender's own text objects).

    from eidoblend.sets.town import signs
    S = signs.prepare(['BAKERY', 'PHARMACY', '/path/to/my_sign.png'], font='Anton-Regular.ttf')
    # the layout does this from build(signs=..., sign_font=...); each shop with a sign takes one of S at random

The town ships no sign texts. A shop's board is a boxed panel over its shutter; with no signs given it is painted
plain (BOARDS: eight paints a shopfront has), so the shop fronts still read as shops from the air. Given signs, each
one is either:
  a picture   a .png / .jpg / .webp path: laid on the board through its UVs, packed into the .blend
  words       any other string: written in the board's ink (BOARDS' second colour) as flat letters a hair proud of
              the board, set in `font` (a file name of eidoverse/assets/fonts/, all of them OFL-licensed, or a path to
              a font of your own; its licence travels with it), centred and fitted to the board
Blender's text objects set a line left to right, glyph by glyph: a script whose letters join or that runs right to
left (Arabic, Persian, Hebrew ...) comes out unjoined and reversed. For such a sign give a picture of it, set by a
shaping text engine and checked by a reader of the language.
"""
import os

from ... import common

FONTS = common.asset_path('fonts')
DEFAULT_FONT = 'Anton-Regular.ttf'
PICTURE = ('.png', '.jpg', '.jpeg', '.webp', '.tif', '.tiff')
# a shop's painted sign board when it carries no picture (linear albedo), and the ink of the letters set on it
BOARDS = [((0.30, 0.05, 0.04), (0.62, 0.60, 0.55)), ((0.05, 0.12, 0.28), (0.62, 0.60, 0.55)), ((0.07, 0.20, 0.10), (0.60, 0.58, 0.50)),
          ((0.56, 0.54, 0.48), (0.30, 0.05, 0.04)), ((0.58, 0.46, 0.08), (0.04, 0.04, 0.04)), ((0.04, 0.04, 0.045), (0.60, 0.50, 0.10)),
          ((0.50, 0.48, 0.42), (0.05, 0.12, 0.28)), ((0.40, 0.14, 0.05), (0.60, 0.58, 0.52))]
N_BOARDS = len(BOARDS)


def font_path(font=None):
    """a font file: a name in eidoverse/assets/fonts/ or a path"""
    f = font or DEFAULT_FONT
    for p in (f, os.path.join(FONTS, f)):
        if os.path.isfile(p):
            return os.path.abspath(p)
    have = sorted(n for n in os.listdir(FONTS) if n.lower().endswith(('.ttf', '.otf'))) if os.path.isdir(FONTS) else []
    raise FileNotFoundError(f'[town] sign font {f!r}: not a file, nor one of eidoverse/assets/fonts/ ({", ".join(have)})')


def words(text, font=None):
    """the letters of `text` set in `font`, as filled polygons in a unit box: {'text', 'polys': [[(u, v), ...]],
    'aspect': width / height}. Blender: a text object is laid out, evaluated to its mesh, read and removed"""
    import bpy
    cu = bpy.data.curves.new('town_sign_words', 'FONT')
    cu.body = text
    fnt = bpy.data.fonts.load(font_path(font), check_existing=True)
    cu.font = fnt
    cu.align_x, cu.align_y = 'CENTER', 'CENTER'
    cu.resolution_u = 3
    ob = bpy.data.objects.new('town_sign_words', cu)
    bpy.context.scene.collection.objects.link(ob)
    try:
        ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
        me = ev.to_mesh()
        V = [(v.co.x, v.co.y) for v in me.vertices]
        F = [tuple(p.vertices) for p in me.polygons]
        ev.to_mesh_clear()
    finally:
        bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.curves.remove(cu)
        if fnt.users == 0:
            bpy.data.fonts.remove(fnt)
    if not V or not F:
        raise ValueError(f'[town] sign {text!r}: the font drew nothing for it')
    x0, x1 = min(v[0] for v in V), max(v[0] for v in V)
    y0, y1 = min(v[1] for v in V), max(v[1] for v in V)
    w, h = max(x1 - x0, 1e-6), max(y1 - y0, 1e-6)
    return {'text': text, 'polys': [[((V[i][0] - x0) / w, (V[i][1] - y0) / h) for i in f] for f in F], 'aspect': w / h}


def prepare(signs, font=None):
    """the town's signs from what it was given: None or [] -> [] (painted boards); each item a picture's path, a
    string of words, or {'image': path} / {'text': str, 'font': font}"""
    out = []
    for s in signs or ():
        if isinstance(s, dict):
            if s.get('image'):
                out.append({'image': os.path.abspath(s['image'])})
            else:
                out.append(words(str(s['text']), s.get('font', font)))
        elif isinstance(s, str) and s.lower().endswith(PICTURE):
            if not os.path.isfile(s):
                raise FileNotFoundError(f'[town] sign picture {s} not found')
            out.append({'image': os.path.abspath(s)})
        else:
            out.append(words(str(s), font))
    return out


def lay_words(b, P, sign, rect, depth, m, pad=0.12):
    """a prepared sign's letters on a board: rect (a0, b0, a1, b1) in its wall's measures (P(a, b, depth): a along the
    wall, b up it, depth into it; negative is proud of it), fitted inside a margin of `pad` of the board's height"""
    a0, b0, a1, b1 = rect
    mg = (b1 - b0) * pad
    aw, ah = (a1 - a0) - 2.0 * mg, (b1 - b0) - 2.0 * mg
    if aw <= 0 or ah <= 0:
        return
    W, H = (aw, aw / sign['aspect']) if sign['aspect'] > aw / ah else (ah * sign['aspect'], ah)
    ox, oy = a0 + mg + (aw - W) / 2.0, b0 + mg + (ah - H) / 2.0
    for poly in sign['polys']:
        b.poly([P(ox + u * W, oy + v * H, depth) for u, v in poly], m)
