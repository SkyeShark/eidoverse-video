"""Hardcover books in Blender: the engine's own rig (book_core.js) posed in Deno, cached here (book.js, ported).

    from eidoblend.media import book
    plan = book.schedule((1, 120), open=[(1, 0.0), (30, 1.0)], turns=[(40, 58), (70, 88)])
    b = book.make_book('work/<id>/book', plan, size=(0.15, 0.222, 0.026),
                       cover={'front': 'eidoverse/assets/book_template/front.png', 'back': ..., 'spine': ...,
                              'color': '#1e4d2b'},
                       spreads=sorted(Path('eidoverse/assets/book_spreads').glob('*.jpg')),
                       lining='eidoverse/assets/book_template/lining.png')
    b.root.location = (0, 0, desk_top)          # the closed book's underside sits on z = 0 of its root

The rig (case binding, 12-segment leaf headings, mull, window leaves) runs unchanged in Deno through
js/book_export.mjs: every frame of the schedule is posed there and written as vertex caches; here each part is a
mesh with a Mesh Cache (PC2, LINEAR) modifier and native materials: bookcloth with sheen, paper with translucency,
the spreads on the three window leaves from one image sequence whose frame offset is keyed to the page. Nothing
runs at render time, and the leaves are inextensible arcs exactly as in the engine.

A schedule is a list of per-frame states {f, open, page, turn, wad} or {f, open, riffle: {...}}; ``schedule()`` and
``riffle_schedule()`` build them. A PDF becomes spreads through the system Python's pymupdf (``spreads_from_pdf``).
"""
import json
import math
import os
import struct
import subprocess
from pathlib import Path

import bpy
import numpy as np

from . import JS, REPO, raster
from .screens import _abspath, new_material, run_deno, set_interpolation
from .timebase import Timebase

PAPER = (0.88, 0.87, 0.84)


# ---------------------------------------------------------------------------------------------------- schedules
def _smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def schedule(frames, open=None, page=0, turns=(), back_turns=(), wad=1, side=None):
    """Per-frame states for make_book. ``open``: [(frame, amount 0..1)] keys, eased between (a constant number
    also works); ``page``: the page the book starts on; ``turns``: [(f0, f1)] forward turns, the next leaf
    flying over f0..f1 and landing (page + 1 from f1 on); ``back_turns``: [(f0, f1)] the same backwards.
    ``side``: which cover the open amount swings, setOpen(k, side): 'front' (the default; the back board lies on
    the desk) or 'back' (the back cover closes over the block, the finished book lying front-cover-down at
    open 0), or [(frame, side)] switches. Finish a turn and keep the case fully open while the side changes."""
    a, b = frames
    keys = sorted(open) if isinstance(open, (list, tuple)) else None
    sides = sorted(side) if isinstance(side, (list, tuple)) else None
    out = []
    for f in range(a, b + 1):
        if keys is None:
            k = float(open or 0.0)
        elif f <= keys[0][0]:
            k = keys[0][1]
        elif f >= keys[-1][0]:
            k = keys[-1][1]
        else:
            i = max(j for j in range(len(keys)) if keys[j][0] <= f)
            (f0, v0), (f1, v1) = keys[i], keys[i + 1]
            k = v0 + (v1 - v0) * _smooth((f - f0) / (f1 - f0))
        p, turn = page, None
        for f0, f1 in sorted(turns):
            if f >= f1:
                p += 1
            elif f >= f0:
                turn = (f - f0) / (f1 - f0)
        for f0, f1 in sorted(back_turns):
            if f >= f1:
                p -= 1
            elif f >= f0:
                p -= 1
                turn = 1 - (f - f0) / (f1 - f0)
        d = {'f': f, 'open': k, 'page': p}
        if sides is not None:
            cur = [s for fs, s in sides if fs <= f]
            d['side'] = cur[-1] if cur else 'front'
        elif side:
            d['side'] = side
        if turn is not None:
            d['turn'] = turn
            d['wad'] = wad
        out.append(d)
    return out


def riffle_schedule(frames, start, seconds_per_page=1.2, turn_fraction=0.72, open=1.0, scene=None):
    """rig.riffle's film driver: timed sequential turns from film time ``start``."""
    tb = Timebase.of(scene or bpy.context.scene)
    return [{'f': f, 'open': open, 'riffle': {'t': tb.t(f), 'start': start, 'secondsPerPage': seconds_per_page,
                                              'turnFraction': turn_fraction}} for f in range(frames[0], frames[1] + 1)]


# ---------------------------------------------------------------------------------------------------- spreads
def spreads_from_pdf(pdf, out_dir, page_height=1200, python=None):
    """Rasterise a PDF's pages with pymupdf (the system Python; BOOK_PYTHON picks the executable, as book.js) and
    compose two-page spreads with Pillow: spread 0 = blank | page 1, spread i = page 2i | page 2i + 1."""
    out = _abspath(out_dir)
    pages = out / 'pages'
    pages.mkdir(parents=True, exist_ok=True)
    code = ('import sys, pymupdf\ndoc = pymupdf.open(sys.argv[1])\nh = float(sys.argv[3])\n'
            'for i, p in enumerate(doc):\n    z = h / max(1.0, p.rect.height)\n'
            '    p.get_pixmap(matrix=pymupdf.Matrix(z, z)).save(f"{sys.argv[2]}/p_{i:04d}.png")\nprint(len(doc))\n')
    py = python or os.environ.get('BOOK_PYTHON') or 'python'
    # -E, not -I: pymupdf lives in the user site-packages, which -I hides; the working directory is the pages
    # folder (images only), so nothing local can shadow an import
    env = {k: v for k, v in os.environ.items() if k not in ('PYTHONHOME', 'PYTHONPATH')}
    r = subprocess.run([py, '-E', '-c', code, str(_abspath(pdf)), str(pages), str(page_height)],
                       capture_output=True, text=True, env=env, cwd=str(pages))
    if r.returncode != 0:
        raise RuntimeError(f'pdf rasterise failed: {r.stderr[-600:]}')
    n = int(r.stdout.strip().splitlines()[-1])
    files = []
    ref = raster.Image.open(pages / 'p_0000.png')
    pw, ph = ref.size
    for i in range(n // 2 + 1):
        sp = raster.Image.new('RGB', (pw * 2, ph), (244, 241, 232))
        for side, j in ((0, 2 * i - 1), (1, 2 * i)):
            if 0 <= j < n:
                with raster.Image.open(pages / f'p_{j:04d}.png') as im:
                    sp.paste(im.convert('RGB').resize((pw, ph)), (side * pw, 0))
        p = out / f'pdf_spread_{i:04d}.png'
        sp.save(p)
        files.append(p)
    return files, n


def _spread_sequence(spreads, out_dir, paper=PAPER):
    """file 0 = blank paper, file k = spread k - 1, all at the first spread's size (an image sequence)."""
    seq = _abspath(out_dir) / 'spreads'
    seq.mkdir(parents=True, exist_ok=True)
    for old in seq.glob('spread_*.png'):
        old.unlink()
    size = None
    for k, src in enumerate(spreads, start=1):
        with raster.Image.open(_abspath(src)) as im:
            im = im.convert('RGB')
            size = size or im.size
            if im.size != size:
                im = im.resize(size, raster.Image.Resampling.LANCZOS)
            im.save(seq / f'spread_{k:04d}.png', compress_level=1)
    size = size or (2048, 1434)
    raster.Image.new('RGB', size, tuple(int(round(c * 255)) for c in paper)).save(seq / 'spread_0000.png')
    return seq


# ---------------------------------------------------------------------------------------------------- materials
def _img(path, colorspace='sRGB'):
    im = bpy.data.images.load(str(_abspath(path)), check_existing=True)
    im.colorspace_settings.name = colorspace
    return im


def _principled(name, color=None, image=None, roughness=0.9, sheen=0.0, translucent=0.0, bump=0.0, bump_scale=900.0,
                double_sided=False):
    m = new_material(name)
    t = m.node_tree
    b = t.nodes.get('Principled BSDF')
    out = t.nodes.get('Material Output')
    col = None
    if image is not None:
        tx = t.nodes.new('ShaderNodeTexImage')
        tx.image = image
        tx.interpolation = 'Smart'
        col = tx.outputs['Color']
        t.links.new(col, b.inputs['Base Color'])
    elif color is not None:
        b.inputs['Base Color'].default_value = (*color, 1)
    b.inputs['Roughness'].default_value = roughness
    if sheen:
        b.inputs['Sheen Weight'].default_value = sheen
        b.inputs['Sheen Roughness'].default_value = 0.4
    if bump:
        # a fine weave / paper tooth in object space, so it follows the strip as it bends
        tc = t.nodes.new('ShaderNodeTexCoord')
        wv = t.nodes.new('ShaderNodeTexNoise')
        wv.inputs['Scale'].default_value = bump_scale
        wv.inputs['Detail'].default_value = 2.0
        t.links.new(tc.outputs['Object'], wv.inputs['Vector'])
        bp = t.nodes.new('ShaderNodeBump')
        bp.inputs['Strength'].default_value = bump
        bp.inputs['Distance'].default_value = 0.0002
        t.links.new(wv.outputs['Fac'], bp.inputs['Height'])
        t.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    shader = b.outputs['BSDF']
    if translucent:
        # paper lets light through: the underside of a lifting page is lit, not a hole (book.js did this with an
        # emissive glow; here it is real translucency, thin slab)
        tl = t.nodes.new('ShaderNodeBsdfTranslucent')
        if col is not None:
            t.links.new(col, tl.inputs['Color'])
        else:
            tl.inputs['Color'].default_value = b.inputs['Base Color'].default_value
        mx = t.nodes.new('ShaderNodeMixShader')
        mx.inputs['Fac'].default_value = translucent
        t.links.new(shader, mx.inputs[1])
        t.links.new(tl.outputs['BSDF'], mx.inputs[2])
        shader = mx.outputs['Shader']
        m.thickness_mode = 'SLAB'
    t.links.new(shader, out.inputs['Surface'])
    m.use_backface_culling = not double_sided
    return m, (t.nodes.get('Image Texture') if image is not None else None)


# ---------------------------------------------------------------------------------------------------- meshes
def _read_pc2(path):
    with open(path, 'rb') as f:
        head = f.read(32)
        n, start, rate, ns = struct.unpack('<i f f i', head[16:32])
        first = np.frombuffer(f.read(n * 12), dtype='<f4').reshape(n, 3)
    return n, ns, first


GLTF_UV = 'UVMap_gltf'


def _build_mesh(name, part, pc2, gltf_uv=False):
    """A part's mesh from its exported topology; the first PC2 sample as its rest. ``gltf_uv`` adds a second UV
    layer (GLTF_UV, v -> 1 - v) for a GLB's own textures: the rig's UVs read a glTF image top-down (three loads
    glTF textures unflipped) and a composed canvas bottom-up (CanvasTexture flips), and Blender reads every image
    bottom-up, so the asset's materials sample the flipped layer."""
    n, ns, first = _read_pc2(pc2)
    if n != part['n']:
        raise RuntimeError(f'{name}: {n} cached points for {part["n"]} vertices')
    tris = np.asarray(part['tris'], dtype=np.int32).reshape(-1, 3)
    me = bpy.data.meshes.new(name)
    me.vertices.add(n)
    me.vertices.foreach_set('co', first.astype(np.float32).ravel())
    nt = len(tris)
    me.loops.add(nt * 3)
    me.loops.foreach_set('vertex_index', tris.ravel())
    me.polygons.add(nt)
    me.polygons.foreach_set('loop_start', np.arange(0, nt * 3, 3, dtype=np.int32))
    me.polygons.foreach_set('loop_total', np.full(nt, 3, dtype=np.int32))
    if part.get('mat'):
        me.polygons.foreach_set('material_index', np.asarray(part['mat'], dtype=np.int32))
    uv = np.asarray(part['uv'], dtype=np.float32).reshape(-1, 2)
    lay = me.uv_layers.new(name='UVMap')
    lay.data.foreach_set('uv', uv[tris.ravel()].ravel())
    if gltf_uv:
        fl = uv.copy()
        fl[:, 1] = 1.0 - fl[:, 1]
        me.uv_layers.new(name=GLTF_UV).data.foreach_set('uv', fl[tris.ravel()].ravel())
        me.uv_layers.active_index = 0
    me.update(calc_edges=True)
    me.validate(clean_customdata=False)
    me.shade_smooth()
    return me, ns


CODE_SURFACES = False      # globalThis.__CODE_SURFACES: turns on every book's code_surfaces() (make_book(code=True): one)


class Book:
    """A built book: ``root`` (the empty everything hangs from), ``parts`` (the cached meshes: case, mull, leaves,
    window0..2), ``info`` (book.json: the rig spec, metrics, per-frame state), ``out`` (its folder). A book from a
    GLB also has ``gltf_root`` (the imported asset, its source pieces hidden) and ``source`` (those pieces by
    name), as makeBook's ``part``. ``frames`` is rig.frames: {'case_frame', 'page_frame'}, the rig's two coordinate
    frames as empties keyed per film frame. The facade's state getters (page, openAmount, maxPage, spreadCount)
    are per frame here: ``states`` (every frame's state), ``frame_state(f)``, ``page_at(f)``, ``open_amount(f)``,
    ``max_page``, ``spread_count``."""

    # rig.codeSurfaces()'s colours: case cloth red, lining blue, case rim cyan, leaf recto green, leaf verso yellow,
    # leaf edges magenta, the stock paper dark green
    CODE = {'cloth': '#dd2222', 'lining': '#2255ee', 'trim': '#00cccc', 'recto': '#22cc22', 'verso': '#dddd22',
            'edge': '#dd22dd', 'paper': '#116611'}

    def __init__(self, root, parts, info, out, gltf_root=None, source=None, materials=None, frames=None, code=False):
        self.root, self.parts, self.info, self.out = root, parts, info, out
        self.gltf_root, self.source = gltf_root, dict(source or {})
        self.materials = dict(materials or {})
        self.frames = dict(frames or {})
        self.code = bool(code)
        self._real = None

    def page_materials(self):
        """rig.pageMaterials(): the stock paper, then each window leaf's recto and verso."""
        return [self.materials['paper']] + [m for pair in self.materials.get('windows', ()) for m in pair]

    @property
    def edge_material(self):
        """rig.edgeMaterial: the block's cut edges."""
        return self.materials.get('edge')

    def code_surfaces(self, on=True):
        """rig.codeSurfaces(), for debugging: every surface a flat primary so a render names the surface it shows
        (Book.CODE: cloth red, lining blue, case rim cyan, recto green, verso yellow, leaf edges magenta, stock paper
        dark green). Parts the engine does not code (the mull, the spine inlay) keep their materials. Gated as
        makeBook's facade gates it: it codes only a book made with code=True, or any book while the module's
        CODE_SURFACES is set (globalThis.__CODE_SURFACES), so a scene can leave the call in; otherwise it does
        nothing and returns False. on=False puts the real materials back. Returns True when coded."""
        if not on:
            for (o, i), m in (self._real or {}).items():
                o.material_slots[i].material = m
            self._real = None
            return False
        if not (self.code or CODE_SURFACES):
            return False
        role = {}
        for k in ('cloth', 'lining', 'trim', 'edge', 'paper'):
            if self.materials.get(k) is not None:
                role[self.materials[k]] = k
        for recto, verso in self.materials.get('windows', ()):
            role[recto], role[verso] = 'recto', 'verso'
        coded = {}
        for k, hexc in self.CODE.items():
            m, _ = _principled(f'{self.root.name}_code_{k}', color=tuple(float(raster.srgb_to_linear(c / 255))
                                                                         for c in raster.color(hexc)[:3]),
                               roughness=0.6)
            coded[k] = m
        self._real = self._real or {}
        for o in self.parts.values():
            for i, s in enumerate(o.material_slots):
                if s.material in role:
                    self._real.setdefault((o, i), s.material)
                    s.material = coded[role[s.material]]
        print('[book] surfaces colour-coded', flush=True)
        return True

    @property
    def metrics(self):
        return self.info['metrics']

    @property
    def states(self):
        """Every film frame's rig state: [{f, page, open, side, turn, slots, minZ, caseFrame, pageFrame}]."""
        return self.info['frames']

    @property
    def max_page(self):
        return self.info.get('maxPage')

    @property
    def spread_count(self):
        return self.info.get('spreadCount', self.info.get('spreads', 0))

    def frame_state(self, f):
        return next((x for x in self.info['frames'] if x['f'] == f), None)

    def page_at(self, f):
        """The facade's page at film frame f."""
        s = self.frame_state(f)
        return None if s is None else s['page']

    def open_amount(self, f):
        """The facade's openAmount at film frame f (0 shut .. 1 open)."""
        s = self.frame_state(f)
        return None if s is None else s['open']

    def seat_box(self):
        """rig.seatBox(): the closed case's bounds in the book root's space, Blender axes ((min x, y, z), (max …));
        the underside rests on z = 0 there."""
        sb = self.info.get('seatBox')
        if not sb:
            return None
        (x0, y0, z0), (x1, y1, z1) = sb['min'], sb['max']
        seat = -self.info['frames'][0]['minZ']
        return (x0, -z1, y0 + seat), (x1, -z0, y1 + seat)

    def page_turn_events(self, clip='eidoverse/assets/book_sfx/page_turn.wav', gain=0.8, scene=None):
        """[{t, clip, gain}] at each frame a turn starts, for audio.place_events / a mix's event list."""
        tb = Timebase.of(scene or bpy.context.scene)
        ev, prev = [], None
        for fr in self.info['frames']:
            if fr['turn'] is not None and (prev is None or prev['turn'] is None):
                ev.append({'t': tb.t(fr['f']), 'clip': str(REPO / clip), 'gain': gain})
            prev = fr
        return ev


# ---------------------------------------------------------------------------------------------------- the GLB path
GLB_HIDE = ('board_front', 'board_back', 'spine', 'block_left', 'block_right', 'page_left', 'page_right')


def _base_name(n):
    """'board_back.001' -> 'board_back' (Blender's suffix for a name already taken)."""
    head, dot, tail = n.rpartition('.')
    return head if dot and tail.isdigit() and len(tail) == 3 else n


def import_book_glb(path):
    """Import a book GLB (Blender's glTF importer) and return its root object (the node holding the rest)."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(_abspath(path)))
    new = [o for o in bpy.data.objects if o not in before]
    tops = [o for o in new if o.parent is None or o.parent not in new]
    if len(tops) == 1:
        return tops[0]
    root = bpy.data.objects.new(Path(str(path)).stem[:40], None)
    bpy.context.scene.collection.objects.link(root)
    for o in tops:
        o.parent = root
    return root


def _book_parts(root):
    """makeBook's ``part``: mesh objects by (base) name. A glTF mesh of several primitives is one Blender mesh with
    one material slot per primitive, in order; three made a group of meshes and makeBook took the first (slot 0)."""
    part = {}
    for o in [root, *root.children_recursive]:
        if o.type == 'MESH':
            part.setdefault(_base_name(o.name), o)
    return part


def _three_points(obj, slot=None, local=False):
    """An object's vertices in three's axes (Blender (x, y, z) -> three (x, z, -y)): world space, or the mesh's own
    coordinates with ``local``; only those of faces in material ``slot`` when given (the first primitive)."""
    me = obj.data
    co = np.empty(len(me.vertices) * 3, dtype=np.float64)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    if slot is not None and len(me.polygons):
        mi = np.empty(len(me.polygons), dtype=np.int32)
        me.polygons.foreach_get('material_index', mi)
        keep = set()
        for p in me.polygons:
            if mi[p.index] == slot:
                keep.update(p.vertices)
        co = co[sorted(keep)] if keep else co
    if not local:
        m = np.array(obj.matrix_world)
        co = co @ m[:3, :3].T + m[:3, 3]
    return np.column_stack([co[:, 0], co[:, 2], -co[:, 1]])


def measure_book_glb(root):
    """makeBook(gltf)'s measure, ported: read the case's dimensions and the wrap-U landmark off a book asset (named
    board_front, board_back, optional spine), never assumed. ``root``: the imported GLB's root object (or a path,
    imported first). Returns the rig spec part {boardLen, jointX, foreX, halfH, halfT, lip, round, uJoint}.

    halfT / halfH: the whole asset's largest |z| / |y| (three's axes: thickness z, height y); jointX / foreX: the
    back board's extent along -x / +x; lip: how far the spine cloth runs flat past the board (its farthest point
    where |z| > 0.95 halfT, minus jointX); round: how far it bulges past that; uJoint: the back board's largest
    UV u (kept only between 0.2 and 0.5; else 0.4573)."""
    if isinstance(root, (str, os.PathLike)):
        root = import_book_glb(root)
    part = _book_parts(root)
    for n in ('board_front', 'board_back'):
        if n not in part:
            raise ValueError(f'[measure_book_glb] missing {n}: a book GLB names its boards board_front / board_back')
    allp = np.concatenate([_three_points(o) for o in part.values()])
    back = _three_points(part['board_back'], slot=0)
    half_t = float(max(abs(allp[:, 2].min()), abs(allp[:, 2].max())))
    half_h = float(max(abs(allp[:, 1].min()), abs(allp[:, 1].max())))
    joint_x = float(-back[:, 0].min())
    fore_x = float(back[:, 0].max())
    lip, rnd = 0.005, 0.003
    if 'spine' in part:
        g = _three_points(part['spine'], slot=0, local=True)
        cx, cz = -g[:, 0], np.abs(g[:, 2])
        max_all = max(0.0, float(cx.max()))
        edge = cx[cz > half_t * 0.95]
        max_edge = max(0.0, float(edge.max())) if len(edge) else 0.0
        lip = max(0.0005, max_edge - joint_x)
        rnd = max(0.001, max_all - max_edge)
    u_joint = 0.4573
    me = part['board_back'].data
    if me.uv_layers.active and len(me.polygons):
        uv = np.empty(len(me.loops) * 2, dtype=np.float64)
        me.uv_layers.active.data.foreach_get('uv', uv)
        uv = uv.reshape(-1, 2)
        loops = [li for p in me.polygons if p.material_index == 0 for li in p.loop_indices]
        m = float(uv[loops, 0].max()) if loops else 0.0
        if 0.2 < m < 0.5:
            u_joint = m
    spec = {'boardLen': joint_x + fore_x, 'jointX': joint_x, 'foreX': fore_x, 'halfH': half_h, 'halfT': half_t,
            'lip': lip, 'round': rnd, 'uJoint': u_joint}
    print(f'[measure_book_glb] case halfT={half_t:.4f} halfH={half_h:.4f} board={joint_x + fore_x:.4f} '
          f'joint={joint_x:.4f} lip={lip:.4f} round={rnd:.4f} uJoint={u_joint:.4f}')
    return spec


def _glb_materials(part):
    """The asset's own materials by (base) name: case_cloth, case_inner, page_edges, page_spread."""
    out = {}
    for o in part.values():
        for s in o.material_slots:
            if s.material is not None:
                out.setdefault(_base_name(s.material.name), s.material)
    return out


def _on_gltf_uv(src, name, double_sided=None):
    """A copy of an imported glTF material for the rig's meshes: every image and the normal map's tangent space
    read the GLTF_UV layer (the rig's UVs flipped in v; see _build_mesh). The asset's own pieces keep the
    original."""
    m = src.copy()
    m.name = name
    t = m.node_tree
    uvn = t.nodes.new('ShaderNodeUVMap')
    uvn.uv_map = GLTF_UV
    uvn.location = (-1400, 0)
    for n in list(t.nodes):
        if n.bl_idname == 'ShaderNodeTexImage':
            sock = n.inputs['Vector']
            if not sock.is_linked:
                t.links.new(uvn.outputs['UV'], sock)
                continue
            up = sock.links[0].from_node                      # a UV Map node, or a Mapping (texture transform)
            if up.bl_idname == 'ShaderNodeUVMap':
                up.uv_map = GLTF_UV
            elif up.bl_idname == 'ShaderNodeMapping':
                v = up.inputs['Vector']
                if not v.is_linked:
                    t.links.new(uvn.outputs['UV'], v)
                elif v.links[0].from_node.bl_idname == 'ShaderNodeUVMap':
                    v.links[0].from_node.uv_map = GLTF_UV
        elif n.bl_idname == 'ShaderNodeNormalMap':
            n.uv_map = GLTF_UV
    if double_sided is not None:
        m.use_backface_culling = not double_sided
    return m


def make_book(out_dir, frames, size=(0.15, 0.222, None), cover=None, spreads=(), pdf=None, lining=None, edges=None,
              pages=None, open_at=1, name='book', scene=None, cloth_roughness=0.82, rig=None, wrap_res=4096,
              pdf_page_height=1200, gltf=None, angle=180, page_angle=179, page_glow=0.55, code=False):
    """Export the rig over ``frames`` (a schedule) and build the book under an empty ``name`` at the origin.

    makeBookFromSpec, ported: size: (width, height, thickness) of the closed book in metres (thickness None:
    estimated from the pages). cover: {front, back, spine, color} images (composed into the arc-length wrap by
    the rig's own composer) or {wrap: <image>, color}. spreads: two-page images in reading order; or pdf=<file>.
    lining / edges: an image or an sRGB hex. rig: a raw makeBookRig spec instead.

    makeBook(gltf), ported: ``gltf`` = a book GLB's path (or its imported root object). Its dimensions and the
    wrap-U landmark are measured off the asset (measure_book_glb), the rig rides in the asset's own frame, and the
    asset's own materials dress it: case_cloth (with its normal and ORM maps) as the cloth and, double-sided, the
    trim; case_inner as the lining; page_edges on the cut edges; page_spread's roughness on the paper. The source
    pieces (boards, spine, block, pages) stay, hidden, as ``book.source``, laid flat with the rig (the engine kept
    them to measure and seat by). ``pages`` defaults to 26 there, ``spreads`` / ``pdf`` load as loadSpreads did.

    angle / page_angle: the case's opening sweep and where a turned leaf lies (degrees). page_glow: the engine's
    paper glow (an emissive proxy for light through the sheet) becomes real translucency, 0.4 x page_glow.
    open_at: the rig's openAt (the leaves already on the left when the book opens). code: opts.code, the gate on
    Book.code_surfaces() (the module's CODE_SURFACES opens it for every book)."""
    scene = scene or bpy.context.scene
    out = _abspath(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    cover = dict(cover or {})
    pdf_pages = 0
    if pdf:
        spreads, pdf_pages = spreads_from_pdf(pdf, out, pdf_page_height)
    spreads = [str(_abspath(s)) for s in spreads]
    gltf_root, gpart, gmats = None, {}, {}
    if gltf is not None:
        gltf_root = gltf if isinstance(gltf, bpy.types.Object) else import_book_glb(gltf)
        gpart = _book_parts(gltf_root)
        gmats = _glb_materials(gpart)
        rig = dict(measure_book_glb(gltf_root), pages=pages or 26, openAt=open_at, angle=angle, pageAngle=page_angle)
    spec = {'size': {'width': size[0], 'height': size[1]}, 'spreads': len(spreads), 'openAt': open_at,
            'wrapRes': wrap_res}
    if size[2]:
        spec['size']['thickness'] = size[2]
    if pages:
        spec['pages'] = pages
    if pdf_pages:
        spec['pdfPages'] = pdf_pages
    spec['cover'] = {k: (str(_abspath(v)) if k in ('front', 'back', 'spine', 'wrap') else v) for k, v in cover.items()}
    job = {'out': str(out), 'frames': frames}
    if rig:
        job['rig'] = rig
        job['spreads'] = len(spreads)
    else:
        job['spec'] = spec
    (out / 'job.json').write_text(json.dumps(job), encoding='utf-8')
    run_deno(JS / 'book_export.mjs', [out / 'job.json'])
    info = json.loads((out / 'book.json').read_text(encoding='utf-8'))

    # ---- materials
    paper_col = PAPER
    translucent = 0.4 * page_glow                     # the engine's 0.55 glow -> 0.22 translucency
    paper_rough = 0.9
    mats = {}
    if gltf_root is not None:
        # the asset's own materials, as makeBook passed them to the rig: cloth (its wrap, normal and ORM maps as
        # the glTF importer wired them), lining = case_inner, edge = page_edges; trim = the cloth, double-sided
        # (its wrap has plain cloth where the rims sample it); paper takes page_spread's roughness
        cloth = gmats.get('case_cloth') or gpart['board_front'].material_slots[0].material
        mats['cloth'] = _on_gltf_uv(cloth, f'{name}_cloth')
        mats['trim'] = _on_gltf_uv(cloth, f'{name}_trim', double_sided=True)
        mats['lining'] = _on_gltf_uv(gmats.get('case_inner') or cloth, f'{name}_lining')
        mats['edge'] = _on_gltf_uv(gmats.get('page_edges') or gmats.get('case_inner') or cloth, f'{name}_edge')
        sp = gmats.get('page_spread')
        bsdf = next((n for n in sp.node_tree.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled'), None) if sp else None
        if bsdf is not None and not bsdf.inputs['Roughness'].is_linked:
            paper_rough = float(bsdf.inputs['Roughness'].default_value)
    else:
        cloth_col = raster.color(cover.get('color', '#8a1420'))
        cloth_lin = tuple(float(raster.srgb_to_linear(c / 255)) for c in cloth_col[:3])
        wrap = cover.get('wrap') or (out / info['images']['wrap'] if info['images'].get('wrap') else None)
        mats['cloth'], _ = _principled(f'{name}_cloth', color=cloth_lin, image=_img(wrap) if wrap else None,
                                       roughness=cloth_roughness, sheen=0.5, bump=0.25, bump_scale=2400.0)
        mats['trim'], _ = _principled(f'{name}_trim', color=cloth_lin, roughness=cloth_roughness, sheen=0.5,
                                      bump=0.25, bump_scale=2400.0, double_sided=True)

        def surface(nm, src, default_hex, **kw):
            if src and not str(src).startswith('#'):
                return _principled(f'{name}_{nm}', image=_img(src), **kw)[0]
            c = raster.color(src or default_hex)
            return _principled(f'{name}_{nm}', color=tuple(float(raster.srgb_to_linear(v / 255)) for v in c[:3]),
                               **kw)[0]
        mats['lining'] = surface('lining', lining, '#efe9dc', roughness=0.92, bump=0.1, bump_scale=3000.0)
        mats['edge'] = surface('edge', edges, '#ddd8ca', roughness=0.92)
    mats['inlay'], _ = _principled(f'{name}_inlay', image=_img(out / info['images']['inlay']), roughness=0.96)
    mats['mull'], _ = _principled(f'{name}_mull', image=_img(out / info['images']['mull']), roughness=0.96,
                                  double_sided=True)
    # no paper bump: a 0.25 mm tooth is sub-pixel at reading distance and aliases into a stipple wherever the light
    # grazes the page (as in the turn's shadow)
    mats['paper'], _ = _principled(f'{name}_paper', color=paper_col, roughness=paper_rough, translucent=translucent)

    # the three window leaves: recto / verso sample one spread sequence, the file keyed to the page
    seq = _spread_sequence(spreads, out)
    first = seq / 'spread_0000.png'
    win_mats = []
    f_last = max(fr['f'] for fr in info['frames'])
    for w in range(3):
        pair = []
        for side in ('recto', 'verso'):
            img = bpy.data.images.load(str(first), check_existing=False)
            img.name = f'{name}_spreads_{w}{side[0]}'
            img.source = 'SEQUENCE'
            m, tex = _principled(f'{name}_{side}{w}', image=img, roughness=paper_rough, translucent=translucent)
            iu = tex.image_user
            iu.frame_start = 1
            iu.frame_duration = f_last + 1                # never clamped: the file is cfra + offset
            iu.use_cyclic = False
            iu.use_auto_refresh = True
            last = None
            for fr in info['frames']:
                s = fr['slots'][w]
                k = s[side]
                want = k + 1 if 0 <= k < len(spreads) else 0
                off = want - fr['f']
                if off != last:
                    iu.frame_offset = off
                    iu.keyframe_insert('frame_offset', frame=fr['f'])
                    last = off
            set_interpolation(m.node_tree, 'CONSTANT', 'frame_offset')
            pair.append(m)
        win_mats.append(pair)

    # ---- the parts, cached
    root = bpy.data.objects.new(name, None)
    root.empty_display_type = 'PLAIN_AXES'
    root.empty_display_size = 0.05
    scene.collection.objects.link(root)
    seat = -info['frames'][0]['minZ']
    parts = {}
    f0 = info['frames'][0]['f']
    for pname, part in info['parts'].items():
        me, ns = _build_mesh(f'{name}_{pname}', part, out / f'{pname}.pc2', gltf_uv=gltf_root is not None)
        if pname.startswith('window'):
            w = int(pname[-1])
            for m in (win_mats[w][0], win_mats[w][1], mats['edge']):
                me.materials.append(m)
        else:
            for mn in part['materials']:
                me.materials.append(mats[mn])
        o = bpy.data.objects.new(f'{name}_{pname}', me)
        scene.collection.objects.link(o)
        o.parent = root
        o.location = (0, 0, seat)
        mc = o.modifiers.new('rig', 'MESH_CACHE')
        mc.cache_format = 'PC2'
        mc.filepath = str(out / f'{pname}.pc2')
        mc.frame_start = f0
        mc.frame_scale = 1.0
        mc.play_mode = 'SCENE'
        mc.time_mode = 'FRAME'
        mc.interpolation = 'LINEAR'
        mc.deform_mode = 'OVERWRITE'
        parts[pname] = o
    # rig.frames: caseFrame / pageFrame as empties under the root, keyed per frame (their own local axes, the
    # rig's world placement in Blender axes, seated with the parts)
    rig_frames = {}
    if info['frames'] and 'caseFrame' in info['frames'][0]:
        from mathutils import Matrix
        for key, nm in (('caseFrame', 'case_frame'), ('pageFrame', 'page_frame')):
            e = bpy.data.objects.new(f'{name}_{nm}', None)
            e.empty_display_type = 'ARROWS'
            e.empty_display_size = 0.03
            scene.collection.objects.link(e)
            e.parent = root
            e.rotation_mode = 'QUATERNION'
            prev = None
            for fr in info['frames']:
                m = Matrix(fr[key])
                m.translation.z += seat
                loc, q, _s = m.decompose()
                if prev is not None and prev.dot(q) < 0:
                    q.negate()                        # the short way round: LINEAR keys between frames
                e.location, e.rotation_quaternion = loc, q
                e.keyframe_insert('location', frame=fr['f'])
                e.keyframe_insert('rotation_quaternion', frame=fr['f'])
                prev = q
            set_interpolation(e, 'LINEAR')
            rig_frames[nm] = e
    source = {}
    if gltf_root is not None:
        # the asset rides with the rig, laid flat as book.layFlat() laid it (three's -90 degrees about x; Blender's
        # importer already turned glTF's y-up into z-up, so the same rotation lays the model's thickness along +Z),
        # seated with the rig; its source pieces stay, hidden, for measuring and seating
        gltf_root.parent = root
        gltf_root.matrix_parent_inverse.identity()
        gltf_root.rotation_mode = 'XYZ'
        gltf_root.rotation_euler = (-math.pi / 2, 0.0, 0.0)
        gltf_root.location = (0.0, 0.0, seat)
        for n, o in gpart.items():
            if any(n == h or n.startswith(h + '_') for h in GLB_HIDE):
                o.hide_render = True
                o.hide_viewport = True
                source[n] = o
    return Book(root, parts, info, out, gltf_root=gltf_root, source=source, materials={**mats, 'windows': win_mats},
                frames=rig_frames, code=code)
