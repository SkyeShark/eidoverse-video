"""In-world screens: canvas-like content as image-sequence or movie textures on real displays (screen.js, ported).

    import bpy
    from eidoblend.media import screens, raster

    def draw(c, t, w, h):                       # c: raster.Canvas (c.image is a PIL RGBA image), t: film seconds
        c.clear('#071b22')
        raster.draw_text_fit(c, 'SYSTEM READY', x=w / 2, y=h * 0.3, max_width=w * 0.8, max_height=h * 0.4,
                             font='Share Tech Mono', px=96, fill='#c6f4ef')

    ui = screens.make_screen(width=0.64, height=0.36, px=768, draw=draw, frames=(1, 96), out_dir='//screens/ui')
    ui.obj.location = (0, -1, 1.4)              # a standalone panel: stands up, faces -Y (three's +Z, mapped)
    # or take over a model's real display surface (a GLB's screen_crt, a monitor, an LED wall):
    ui = screens.make_screen(px=512, draw=draw, frames=(1, 96), out_dir='//screens/mac', standalone=False)
    ui.apply_to(bpy.data.objects['screen_crt'], window=(0.05, 0.13, 0.95, 0.92))

Every frame of the range is drawn once at build time, written as a PNG sequence and shown through an Image
Texture whose ImageUser steps with the scene frame: no handlers at render time, any frame renders in any order.
Before the range the first drawing holds, after it the last (a marked copy of the first file, numbered one below
it, is written beside the sequence: Blender shows that file on every frame before a sequence starts).
A screen's ImageUser settings travel with its image (custom properties), so a prop can sample the same screen in
its own node tree: ``node = ui.texture_node(tree)`` or ``screens.configure_user(node.image_user, ui.image)``.

Colour: a screen is an emitter filmed by the camera, so it goes through AgX like the rest of the frame. Emission
strength 1 lands sRGB white near 197/255 at exposure 0; set ``strength`` by probe against the room's light.
"""
import glob
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector
from PIL.PngImagePlugin import PngInfo

from . import JS, REPO
from . import raster
from .timebase import Timebase


# ---------------------------------------------------------------------------------------------------- small helpers
def _abspath(p):
    p = str(p)
    return Path(bpy.path.abspath(p) if p.startswith('//') else p).resolve()


def _stored_path(p):
    """Keep a path blend-relative when the blend is saved and the file sits under its folder."""
    p = Path(p)
    if bpy.data.filepath:
        try:
            return bpy.path.relpath(str(p))
        except ValueError:            # another drive
            pass
    return str(p)


def action_fcurves(action, slot=None):
    """Every F-curve of a (layered, 4.4+) action, for one slot or all of them."""
    out = []
    for ly in action.layers:
        for st in ly.strips:
            for cb in st.channelbags:
                if slot is None or cb.slot == slot:
                    out.extend(cb.fcurves)
    return out


def set_interpolation(id_data, kind='CONSTANT', path_filter=None):
    """Set the interpolation of an ID's keys (those whose data path contains ``path_filter``). keyframe_insert
    ignores the user preference keyframe_new_interpolation_type in 5.2 (measured: BEZIER regardless), so every
    keyer here sets it explicitly after inserting."""
    ad = getattr(id_data, 'animation_data', None)
    if ad is None or ad.action is None:
        return 0
    n = 0
    for fc in action_fcurves(ad.action, getattr(ad, 'action_slot', None)):
        if path_filter is None or path_filter in fc.data_path:
            for k in fc.keyframe_points:
                k.interpolation = kind
                n += 1
    return n


def _frame_range(frames, scene):
    if frames is None:
        return scene.frame_start, scene.frame_end
    if isinstance(frames, range):
        return frames.start, frames.stop - 1
    a, b = frames
    return int(a), int(b)


def _link_collection(obj, near=None, scene=None):
    cols = list(near.users_collection) if near is not None else []
    if not cols:
        cols = [(scene or bpy.context.scene).collection]
    for c in cols:
        if obj.name not in c.objects:
            c.objects.link(obj)


# ---------------------------------------------------------------------------------------------------- the image side
def configure_user(image_user, image):
    """Point an ImageUser (an Image Texture node's ``image_user``) at a screen image's frames."""
    fs, fd = image.get('eido_frame_start'), image.get('eido_frame_duration')
    if image.source in ('SEQUENCE', 'MOVIE') and fs is not None:
        image_user.frame_start = int(fs)
        image_user.frame_duration = int(fd)
        image_user.frame_offset = int(image.get('eido_frame_offset', 0))
        image_user.use_cyclic = bool(image.get('eido_cyclic', False))
        image_user.use_auto_refresh = True
    return image_user


HOLD_KEY = 'eido_hold'           # the PNG text chunk that marks a hold file (written by _write_hold, never a frame)


def _seq_split(path):
    """'<head><digits>.<ext>' -> (head, number, digit count), or (stem, None, 0) without a trailing number. Blender
    numbers a sequence's files the same way: the last run of digits in the name, padded to that many digits."""
    m = re.match(r'^(.*?)(\d+)$', Path(path).stem)
    return (m.group(1), int(m.group(2)), len(m.group(2))) if m else (Path(path).stem, None, 0)


def _is_hold(path):
    try:
        with raster.Image.open(path) as im:
            return im.info.get(HOLD_KEY) == '1'
    except OSError:
        return False


def _write_hold(first):
    """Write the file numbered one below a sequence's first: a copy of the first, marked as a hold. Blender shows
    file <first - 1> on every frame before an ImageUser's frame_start (BKE_image_user_frame_get clamps the frame to
    0, then adds the offset), so without it a screen shows the missing-texture magenta until its range starts
    (11-07 verify). A real frame of a source sequence that already has that number is left as it is."""
    first = Path(first)
    head, num, nd = _seq_split(first)
    hold = first.with_name(f'{head}{num - 1:0{nd}d}{first.suffix}')
    is_png = first.suffix.lower() == '.png'
    if hold.exists() and not (is_png and _is_hold(hold)):
        return hold
    tmp = hold.with_name(hold.name + '.part')
    if is_png:
        info = PngInfo()
        info.add_text(HOLD_KEY, '1')
        with raster.Image.open(first) as im:
            im.save(tmp, format='PNG', pnginfo=info, compress_level=1)
    else:
        shutil.copyfile(first, tmp)
    os.replace(tmp, hold)
    return hold


def _load_sequence(first_png, frame_start, count, name):
    """An image showing the numbered sequence from ``first_png`` (file number N) at ``frame_start`` for ``count``
    frames: the ImageUser offset is N - 1, the first file holds before the range (the hold file) and the last
    after it (Blender clamps to the last)."""
    first_png = Path(first_png)
    offset = 0
    if count > 1:
        head, num, nd = _seq_split(first_png)
        if num is None or num < 1:
            raise ValueError(f'{first_png}: a screen\'s image sequence is numbered from 1 or more (<name>_0001.png): '
                             f'Blender shows file <first - 1> before the range starts, so it cannot start at 0')
        offset = num - 1
        _write_hold(first_png)
    img = bpy.data.images.load(_stored_path(first_png), check_existing=False)
    img.name = name
    if count > 1:
        img.source = 'SEQUENCE'
    img.alpha_mode = 'STRAIGHT'
    img['eido_frame_start'] = int(frame_start)
    img['eido_frame_duration'] = int(count)
    img['eido_frame_offset'] = offset
    img['eido_cyclic'] = False
    return img


def _first_of(src):
    """A directory or the first file of a numbered image sequence -> (first file, the files from it on, in order,
    up to the first gap in the numbering). A directory holds one <name>_0001.png sequence; its file 0 is the hold
    make_screen writes, not a frame."""
    p = _abspath(src)
    if p.is_dir():
        groups = {}
        for x in p.glob('*_[0-9][0-9][0-9][0-9].png'):
            head, num, _ = _seq_split(x)
            groups.setdefault(head, []).append((num, x))
        groups = {h: v for h, v in groups.items() if any(n >= 1 for n, _ in v)}
        if not groups:
            raise FileNotFoundError(f'{p}: no <name>_0001.png sequence')
        if len(groups) > 1:
            raise ValueError(f'{p} holds {len(groups)} sequences ({", ".join(sorted(groups))}): pass the first file')
        (head, found), = groups.items()
        zero = [x for n, x in found if n == 0]
        if zero and not _is_hold(zero[0]):
            print(f'[screens] {p.name}: the sequence starts at file 1; its file 0 (a frame, not a hold) shows before '
                  f'the range')
        files = [x for n, x in sorted(found) if n >= 1]
    else:
        head, num, _ = _seq_split(p)
        if num is None:
            return p, [p]
        found = []
        for x in p.parent.glob(glob.escape(head) + '[0-9]*' + p.suffix):
            h, n, _ = _seq_split(x)
            if h == head and n is not None and n >= num:
                found.append((n, x))
        files = [x for _, x in sorted(found)] or [p]
    nums = [_seq_split(x)[1] for x in files]
    gap = next((i for i in range(1, len(nums)) if nums[i] != nums[0] + i), None)
    if gap is not None:                       # Blender reads files by number: the sequence ends at its first gap
        print(f'[screens] {files[0].name}: numbering breaks after {files[gap - 1].name}; the sequence ends there')
        files = files[:gap]
    return files[0], files


def _unique_name(name):
    """A screen name no image in the blend has yet, so two screens never share frames or a folder."""
    out, k = name, 1
    while out in bpy.data.images:
        k += 1
        out = f'{name}_{k}'
    if out != name:
        print(f'[screens] the name {name!r} is taken: this screen is {out!r}')
    return out


def _default_dir(name):
    """Where a screen's frames go without out_dir: beside the saved blend (//eido_screens/<blend>/<name>), else a
    folder of its own under the system temp folder, which outlives Blender (Blender's session temp, bpy.app.tempdir,
    is deleted when it exits, and a saved film would lose its frames)."""
    if bpy.data.filepath:
        return _abspath(f'//eido_screens/{Path(bpy.data.filepath).stem}/{name}')
    d = Path(tempfile.gettempdir()) / 'eido_screens' / f'{name}_{uuid.uuid4().hex[:8]}'
    print(f'[screens] {name}: no out_dir and the blend is unsaved, so its frames go to {d} (give a film out_dir=)')
    return d


def _means_of(files):
    out = []
    for f in files:
        with raster.Image.open(f) as im:
            im.thumbnail((64, 64))
            out.append(raster.mean_linear(im))
    return out


# ---------------------------------------------------------------------------------------------------- the material
def new_material(name):
    """A material with a node tree (Material.use_nodes is deprecated in 5.x and goes in 6.0)."""
    m = bpy.data.materials.new(name)
    if m.node_tree is None:
        m.use_nodes = True
    return m


def _node(tree, idname, loc, **props):
    n = tree.nodes.new(idname)
    n.location = loc
    for k, v in props.items():
        setattr(n, k, v)
    return n


def build_material(name, image, *, lit=False, transparent=False, glass=False, strength=1.0, window=None, flip=False,
                   mirror_x=False, interpolation='Linear', double_sided=False, glass_color=(0.012, 0.013, 0.014),
                   glass_roughness=0.25, coat_roughness=0.03):
    """The screen material: the image through the mesh's UV (optionally into a ``window`` u0, v0, u1, v1 of it).

    - default: Emission only (an LED wall, a projection, a holo panel);
    - ``glass``: a display behind glass: dark Principled base, a clear coat that catches the room's reflections,
      the image as its emission (outside the window: glass only);
    - ``lit``: the image as base colour of a Principled surface (a poster, an e-ink panel, a screen switched off);
    - ``transparent``: the image's alpha cuts the surface (blended).
    """
    m = new_material(name)
    t = m.node_tree
    t.nodes.clear()
    out = _node(t, 'ShaderNodeOutputMaterial', (600, 0))
    uv = _node(t, 'ShaderNodeTexCoord', (-900, 0))
    vec = uv.outputs['UV']
    if window or flip or mirror_x:
        u0, v0, u1, v1 = window or (0.0, 0.0, 1.0, 1.0)
        su, sv = 1.0 / (u1 - u0), 1.0 / (v1 - v0)
        lx, ly = -u0 * su, -v0 * sv
        if mirror_x:
            su, lx = -su, 1.0 - lx
        if flip:
            sv, ly = -sv, 1.0 - ly
        mp = _node(t, 'ShaderNodeMapping', (-700, 0), vector_type='POINT')
        mp.inputs['Location'].default_value = (lx, ly, 0.0)
        mp.inputs['Scale'].default_value = (su, sv, 1.0)
        t.links.new(vec, mp.inputs['Vector'])
        vec = mp.outputs['Vector']
    tex = _node(t, 'ShaderNodeTexImage', (-450, 0), image=image, interpolation=interpolation,
                extension='CLIP' if window else 'EXTEND')
    configure_user(tex.image_user, image)
    t.links.new(vec, tex.inputs['Vector'])
    col, alpha = tex.outputs['Color'], tex.outputs['Alpha']
    if lit or glass:
        b = _node(t, 'ShaderNodeBsdfPrincipled', (0, 0))
        if lit:
            t.links.new(col, b.inputs['Base Color'])
            b.inputs['Roughness'].default_value = 0.45
        else:
            b.inputs['Base Color'].default_value = (*glass_color, 1.0)
            b.inputs['Roughness'].default_value = glass_roughness
            b.inputs['Coat Weight'].default_value = 1.0
            b.inputs['Coat Roughness'].default_value = coat_roughness
            t.links.new(col, b.inputs['Emission Color'])
            b.inputs['Emission Strength'].default_value = strength
        shader = b.outputs['BSDF']
    else:
        e = _node(t, 'ShaderNodeEmission', (0, 0))
        t.links.new(col, e.inputs['Color'])
        e.inputs['Strength'].default_value = strength
        shader = e.outputs['Emission']
    if transparent:
        tr = _node(t, 'ShaderNodeBsdfTransparent', (0, 180))
        mix = _node(t, 'ShaderNodeMixShader', (300, 0))
        t.links.new(alpha, mix.inputs['Fac'])
        t.links.new(tr.outputs['BSDF'], mix.inputs[1])
        t.links.new(shader, mix.inputs[2])
        shader = mix.outputs['Shader']
        m.surface_render_method = 'BLENDED'
        m.use_transparency_overlap = False
    t.links.new(shader, out.inputs['Surface'])
    m.use_backface_culling = not double_sided
    m['eido_screen'] = image.name
    return m


# ---------------------------------------------------------------------------------------------------- the screen
class Screen:
    """A baked screen. ``image`` holds the frames; ``frame_start`` shows the first file, ``frame_duration`` files
    follow (the first held before, the last after). ``obj`` is the standalone panel or the mesh taken over;
    ``light`` the spill light. ``means``: each frame's mean linear colour from ``means_start`` (default
    frame_start), for the spill."""

    def __init__(self, image, *, width, height, px_size, name, opts, means=None, means_start=None):
        self.image = image
        self.width, self.height = width, height
        self.px_size = px_size
        self.name = name
        self.opts = dict(opts)
        self.means = means
        self.means_start = means_start
        self.material = None
        self.obj = None
        self.light = None

    @property
    def frame_start(self):
        return int(self.image.get('eido_frame_start', 1))

    @property
    def frame_duration(self):
        return int(self.image.get('eido_frame_duration', 1))

    def texture_node(self, tree, location=(0, 0)):
        """An Image Texture node in any node tree, stepping with this screen's frames."""
        n = tree.nodes.new('ShaderNodeTexImage')
        n.location = location
        n.image = self.image
        configure_user(n.image_user, self.image)
        return n

    def material_for(self, **over):
        o = {k: v for k, v in self.opts.items() if k in (
            'lit', 'transparent', 'glass', 'strength', 'window', 'flip', 'mirror_x', 'interpolation', 'double_sided')}
        o.update(over)
        return build_material(self.name, self.image, **o)

    def apply_to(self, target, window=None, glass=True, flip=False, mirror_x=False, strength=None, spill=None,
                 slot=None, spill_reach=None):
        """Show the screen on a model's own display mesh: ``target`` is the mesh object, or any object whose
        children hold one named like screen / display / monitor / lcd. Blender's glTF importer already turns
        glTF's v-down UVs upright, so an imported display shows the image upright: render and look, and use
        flip / mirror_x for a model whose author shipped odd UVs. ``window`` = (u0, v0, u1, v1) puts the image in
        that part of the UV square (a raster inside a bezel'd tube). ``glass`` (default here) keeps the display's
        dark glass and coat over the image. ``slot``: only that material slot (default: all)."""
        obj = _find_display(target)
        strength = self.opts['strength'] if strength is None else strength
        mat = self.material_for(window=window, glass=glass, flip=flip, mirror_x=mirror_x, strength=strength,
                                double_sided=True)
        self.material = mat
        if not obj.material_slots:
            obj.data.materials.append(mat)
        for i, s in enumerate(obj.material_slots):
            if slot is None or i == slot:
                s.material = mat
        self.obj = obj
        gain = self.opts.get('spill', 0.0) if spill is None else spill
        if gain:
            self._spill(obj, gain, window, strength=strength, reach=spill_reach)
        return obj

    def _spill(self, obj, gain, window=None, strength=None, reach=None):
        """An area light the size of the display (its ``window``), just in front of it, keyed per frame (CONSTANT)
        to the frame's mean colour m at the display's own radiance: colour m / max(m), power
        pi * area * strength * max(m) * gain (Blender multiplies colour by power unnormalised; measured against
        Cycles 11-07, test_screens.py --only spill). EEVEE's screen-space GI only sees emitters that are on screen,
        and light probes don't follow animated content, so this is what lights a face or a desk from a screen.
        While the display itself is in frame EEVEE's GI adds about a quarter of its light on top (measured, see
        the guide). ``reach`` (metres, default the screen's spill_reach, 30): the light's custom cutoff distance.
        Without it EEVEE culls a light where its power falls under scene.eevee.light_threshold (0.01), and a
        screen's few watts reached little or nothing of the room (11-07 verify: a 0.25 W blue spill lit 0 %)."""
        if self.means is None:
            raise ValueError('spill needs per-frame means: bake with spill=..., or pass means=')
        centre, normal, ax_u, ax_v, (su, sv) = _display_frame(obj)
        if window:
            u0, v0, u1, v1 = window
            su, sv = su * (u1 - u0), sv * (v1 - v0)
        ld = bpy.data.lights.new(self.name + '_spill', 'AREA')
        ld.shape = 'RECTANGLE'
        ld.size, ld.size_y = max(su, 1e-3), max(sv, 1e-3)
        ld.use_shadow = True
        ld.use_custom_distance = True
        ld.cutoff_distance = float(reach or self.opts.get('spill_reach') or 30.0)
        lo = bpy.data.objects.new(self.name + '_spill', ld)
        _link_collection(lo, near=obj)
        z = -normal                                   # an area light shines along its local -Z: out of the display
        rot = Matrix((ax_u, z.cross(ax_u), z)).transposed()     # columns: local X (width), Y (height), Z
        lo.matrix_world = Matrix.Translation(centre + normal * 0.01) @ rot.to_4x4()
        mw = lo.matrix_world.copy()
        lo.parent = obj
        lo.matrix_parent_inverse = obj.matrix_world.inverted()
        lo.matrix_world = mw
        area = ld.size * ld.size_y
        strength = self.opts['strength'] if strength is None else strength
        f0 = self.frame_start if self.means_start is None else self.means_start
        last = None
        for k, m in enumerate(self.means):
            peak = float(max(np.max(m), 0.0))
            rgb = tuple(float(c) / peak for c in m) if peak > 1e-6 else (1.0, 1.0, 1.0)
            watts = math.pi * area * strength * peak * gain
            cur = (round(watts, 5),) + tuple(round(c, 3) for c in rgb)
            if cur == last:
                continue
            last = cur
            ld.energy = watts
            ld.color = rgb
            ld.keyframe_insert('energy', frame=f0 + k)
            ld.keyframe_insert('color', frame=f0 + k)
        set_interpolation(ld, 'CONSTANT')
        self.light = lo
        return lo


def _find_display(target):
    if target.type == 'MESH' and not any(c.type == 'MESH' for c in target.children_recursive):
        return target
    import re
    pat = re.compile(r'screen|display|monitor|lcd', re.I)
    for o in [target, *target.children_recursive]:
        if o.type == 'MESH' and pat.search(o.name):
            return o
    if target.type == 'MESH':
        return target
    raise ValueError(f'{target.name}: no mesh named like screen / display / monitor / lcd; pass the mesh itself')


def _display_frame(obj):
    """World-space centre, outward normal, in-plane axes (u along the UV's u where possible) and extents."""
    me = obj.data
    mw = obj.matrix_world
    nm = mw.to_3x3().inverted_safe().transposed()
    c, n, a = Vector(), Vector(), 0.0
    for p in me.polygons:
        w = p.area
        c += (mw @ p.center) * w
        n += (nm @ p.normal) * w
        a += w
    c /= max(a, 1e-12)
    n.normalize()
    # u axis: the world direction of d(position)/du, from a least-squares fit position ~ P0 + U u + V v over the
    # loops (picking the edge with the largest du chose triangle diagonals: 45 degrees off, 11-07); world X without UVs
    ax_u = Vector((1, 0, 0))
    uvl = me.uv_layers.active
    if uvl and len(me.loops) > 2:
        nl = len(me.loops)
        uv = np.empty(nl * 2, dtype=np.float64)
        uvl.data.foreach_get('uv', uv)
        vi = np.empty(nl, dtype=np.int64)
        me.loops.foreach_get('vertex_index', vi)
        co = np.empty(len(me.vertices) * 3, dtype=np.float64)
        me.vertices.foreach_get('co', co)
        m4 = np.array(mw)
        pw = co.reshape(-1, 3)[vi] @ m4[:3, :3].T + m4[:3, 3]
        A = np.column_stack([uv.reshape(-1, 2), np.ones(nl)])
        sol, *_ = np.linalg.lstsq(A, pw, rcond=None)
        if np.linalg.norm(sol[0]) > 1e-9:
            ax_u = Vector(sol[0].tolist())
    ax_u = (ax_u - n * ax_u.dot(n)).normalized()
    ax_v = n.cross(ax_u).normalized()
    us = [(mw @ v.co - c).dot(ax_u) for v in me.vertices]
    vs = [(mw @ v.co - c).dot(ax_v) for v in me.vertices]
    return c, n, ax_u, ax_v, (max(us) - min(us), max(vs) - min(vs))


def _plane(name, width, height):
    """A panel standing up in the XZ plane, facing -Y, UV (0, 0) at its bottom left."""
    me = bpy.data.meshes.new(name)
    w, h = width / 2, height / 2
    me.from_pydata([(-w, 0, -h), (w, 0, -h), (w, 0, h), (-w, 0, h)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name='UVMap')
    for li, co in zip(range(4), ((0, 0), (1, 0), (1, 1), (0, 1))):
        uv.data[li].uv = co
    me.update()
    return me


def make_screen(width=0.64, height=0.36, px=768, draw=None, frames=None, fps=0, lit=False, transparent=False,
                double_sided=False, glass=False, strength=1.0, interpolation='Linear', out_dir=None, name='screen',
                source=None, supersample=1, spill=0.0, standalone=True, window=None, flip=False, mirror_x=False,
                scene=None, background=None, spill_reach=30.0):
    """Bake a drawn screen (or wrap baked frames / a movie) and, with ``standalone``, build its panel.

    draw(canvas, t, w, h): a raster.Canvas per frame, t in film seconds (the scene's Timebase), w x h the canvas.
    frames: (first, last) scene frames to bake (default the scene's range); the first file shows at ``first``,
        and the first and last files hold outside the range. A single frame bakes a still (a FILE image).
    fps: the art's redraw rate (0 = every frame): a held frame repeats the last drawing, drawn at the time of the
        first film frame of each art frame, as the engine's throttle did.
    source: frames already made instead of draw: a directory or first file of a <name>_0001.png sequence (e.g.
        bake_canvas_scene's output), a still image, or a movie (see make_video_screen for retiming). A marked
        copy of the first file, numbered one below it, is written beside the sequence (the hold before the range).
    out_dir: where drawn frames go (<out_dir>/<name>_0001.png …). Default: //eido_screens/<blend>/<name> beside a
        saved blend, else a folder of the screen's own under the system temp folder.
    name: also the frames' file name; made unique among the blend's images (a second 'screen' is 'screen_2').
    spill: a gain > 0 adds an area light keyed to each frame's mean colour (see Screen._spill), reaching
        ``spill_reach`` metres.
    supersample: draw at n x the size and downsample (ImageDraw's shapes are aliased).
    Returns a Screen; with ``standalone`` its ``obj`` is a new panel at the origin, standing up and facing -Y.
    """
    scene = scene or bpy.context.scene
    tb = Timebase.of(scene)
    name = _unique_name(name)
    pw = max(2, int(round(px)))
    ph = max(2, int(round(px * height / width)))
    means = None
    if source is not None:
        first, files = _first_of(source)
        if frames is None:
            fa, count = scene.frame_start, len(files)
        else:
            fa, fb = _frame_range(frames, scene)
            count = min(len(files), fb - fa + 1)
        img = _load_sequence(first, fa, count, name)
        pw, ph = img.size[:] if img.size[0] else (pw, ph)
        if spill:
            means = _means_of(files[:count])
    else:
        if draw is None:
            raise ValueError('make_screen needs draw(canvas, t, w, h) or source=')
        fa, fb = _frame_range(frames, scene)
        out = _abspath(out_dir) if out_dir else _default_dir(name)
        out.mkdir(parents=True, exist_ok=True)
        for old in out.glob(f'{glob.escape(name)}_[0-9][0-9][0-9][0-9].png'):
            old.unlink()
        means = []
        last_art, last_bytes, first = None, None, None
        for f in range(fa, fb + 1):
            t = tb.t(f)
            art = math.floor(t * fps + 1e-6) if fps > 0 else f
            path = out / f'{name}_{f - fa + 1:04d}.png'
            if art != last_art:
                c = raster.Canvas(pw, ph, ss=supersample, background=background)
                draw(c, t, c.w, c.h)
                im = c.result()
                raster.save_png(im, path)
                last_bytes = path.read_bytes()
                last_art = art
                if spill:
                    th = im.copy()
                    th.thumbnail((64, 64))
                    means.append(raster.mean_linear(th))
            else:
                tmp = path.with_name(path.name + '.part')
                tmp.write_bytes(last_bytes)
                tmp.replace(path)
                if spill:
                    means.append(means[-1])
            first = first or path
        img = _load_sequence(first, fa, fb - fa + 1, name)
        img['eido_dir'] = str(out)
    scr = Screen(img, width=width, height=height, px_size=(pw, ph), name=name, means=means if spill else None,
                 opts=dict(lit=lit, transparent=transparent, glass=glass, strength=strength, window=window, flip=flip,
                           mirror_x=mirror_x, interpolation=interpolation, double_sided=double_sided, spill=spill,
                           spill_reach=spill_reach))
    if standalone:
        me = _plane(name, width, height)
        obj = bpy.data.objects.new(name, me)
        scene.collection.objects.link(obj)
        scr.material = scr.material_for()
        me.materials.append(scr.material)
        scr.obj = obj
        if spill:
            scr._spill(obj, spill, window)
    return scr


# ---------------------------------------------------------------------------------------------------- canvas-2D cores
from .canvas_scenes import ERA_MODULES, deno_exe, json_arg, run_deno, scene_module  # noqa: E402,F401  (Deno, no bpy)


def bake_canvas_scene(out_dir, frames, *, scene_name=None, modules=None, draw_module=None, t0=None, W=1920, H=800,
                      lyrics=None, cues=None, bpm=128, art_fps=None, prefix=None, scene=None, prewarm=False):
    """Bake a canvas-2D scene through js/canvas_bake.mjs (Deno + Skia, the engine's own drawing code).

    Era screens: ``scene_name='voder_1939'`` (``modules`` default: the two era_screens modules; the one holding the
    scene is found) with ``t0`` (the scene's start in film seconds; default 0, or its entry in ``cues``),
    ``lyrics`` (align_lyrics.py JSON, captions or a timeline with hits.kick and envelopes: a path or the data) and
    ``bpm`` (the line length: two 4/4 bars). ``cues``: {scene: t0 | {t0, dur}} (a path or the data), e.g.
    canvas_scenes.DAISY_CUES. ``prewarm``: run the module's prewarm(W, H, lineOf) first, as a host does at load
    (True, or a number: era_screens_1939_1984's draws per second for it, 12 by default).
    Any other canvas code: ``draw_module='work/<id>/panel.mjs'`` exporting draw(g, W, H, t). ``art_fps`` overrides
    the art's redraw rate (the scene's own fps by default; 0 = every film frame). Returns the bake's info dict
    (``dir``, ``first``: the first PNG, ready for make_screen(source=...); ``drawn``, ``draw_ms_mean``). Run
    canvas_scenes.nan_sweep() before baking new captions; the bake itself turns a non-finite canvas argument
    into an error instead of a process abort."""
    scene = scene or bpy.context.scene
    tb = Timebase.of(scene)
    fa, fb = _frame_range(frames, scene)
    out = _abspath(out_dir)
    prefix = prefix or scene_name or Path(draw_module).stem
    for old in out.glob(f'{glob.escape(prefix)}_[0-9][0-9][0-9][0-9].png') if out.exists() else ():
        old.unlink()                                  # the frames and the hold make_screen wrote beside them
    out.mkdir(parents=True, exist_ok=True)
    args = ['--frames', f'{fa}-{fb}', '--fps', repr(tb.fps), '--frame0', tb.frame0, '--W', W, '--H', H,
            '--out', out, '--prefix', prefix, '--bpm', bpm]

    def repo_path(p):                                 # repo-relative, blend-relative ('//') or absolute
        q = Path(str(p))
        return q if q.is_absolute() else (REPO / q if (REPO / q).exists() else _abspath(p))

    if draw_module:
        args += ['--draw', repo_path(draw_module)]
    else:
        if not modules:
            modules = [scene_module(scene_name, ERA_MODULES)]
        for m in modules:
            args += ['--module', repo_path(m)]
        args += ['--scene', scene_name]
        if t0 is not None or not cues:
            args += ['--t0', repr(float(t0 or 0.0))]
    ly = json_arg(lyrics if lyrics is None or isinstance(lyrics, (dict, list)) else _abspath(lyrics),
                  f'{prefix}_lyrics', out)
    if ly:
        args += ['--lyrics', ly]
    if cues:
        c = dict(cues) if isinstance(cues, dict) else _abspath(cues)
        if isinstance(c, dict) and t0 is not None and scene_name:
            prev = c.get(scene_name)                  # an explicit t0 wins over the scene's cue; its dur stays
            c[scene_name] = dict(prev, t0=float(t0)) if isinstance(prev, dict) else float(t0)
        args += ['--cues', json_arg(c, f'{prefix}_cues', out)]
    if art_fps is not None:
        args += ['--art-fps', art_fps]
    if prewarm is True:
        args += ['--prewarm']
    elif prewarm:
        args += ['--prewarm', float(prewarm)]
    stdout = run_deno(JS / 'canvas_bake.mjs', args)
    info = json.loads(stdout.strip().splitlines()[-1])
    info['dir'] = str(out)
    info['first'] = str(out / f'{prefix}_0001.png')
    return info


def bake_canvas_playlist(out_dir, frames, cues, *, W=1920, H=800, lyrics=None, bpm=128, prefix='playlist',
                         modules=None, scene=None, prewarm=False):
    """One wall, scenes switching on their cues, as DAISY's stage wall played one era scene per lyric line: each
    scene of ``cues`` ({scene: t0 | {t0, dur}} in film seconds, e.g. canvas_scenes.DAISY_CUES; a path or the
    data) is baked with bake_canvas_scene over the frames from its cue to the next scene's cue, within
    ``frames``, and the files are laid end to end as one sequence <out_dir>/<prefix>_0001.png … for
    make_screen(source=...). A cue's dur reaches the scene's timing (its progress), as in preview_screens. Frames
    before the first cue draw the first scene at those times (u < 0; the scenes are swept for that). Returns
    {first, dir, count, spans: [(scene, first frame, last frame)], bakes}."""
    scene = scene or bpy.context.scene
    tb = Timebase.of(scene)
    fa, fb = _frame_range(frames, scene)
    out = _abspath(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob(f'{glob.escape(prefix)}_[0-9][0-9][0-9][0-9].png'):
        old.unlink()
    if not isinstance(cues, dict):
        cues = json.loads(_abspath(cues).read_text(encoding='utf-8'))
    order = sorted(((float(c['t0'] if isinstance(c, dict) else c), n) for n, c in cues.items()), key=lambda x: x[0])
    starts = [max(fa, int(math.ceil(tb.frame(t) - 1e-9))) for t, _ in order]
    starts[0] = fa
    spans, bakes = [], []
    for i, (t0, name) in enumerate(order):
        a = starts[i]
        b = (starts[i + 1] - 1) if i + 1 < len(order) else fb
        b = min(b, fb)
        if b < a:
            continue
        tmp = out / f'_{prefix}_{name}'
        info = bake_canvas_scene(tmp, (a, b), scene_name=name, modules=modules, t0=t0, W=W, H=H, lyrics=lyrics,
                                 bpm=bpm, scene=scene, prewarm=prewarm,
                                 cues={name: cues[name]} if isinstance(cues[name], dict) else None)
        for k in range(b - a + 1):
            src = tmp / f'{name}_{k + 1:04d}.png'
            os.replace(src, out / f'{prefix}_{a - fa + k + 1:04d}.png')
        shutil.rmtree(tmp, ignore_errors=True)
        spans.append((name, a, b))
        bakes.append(info)
    return {'first': str(out / f'{prefix}_0001.png'), 'dir': str(out), 'count': fb - fa + 1, 'spans': spans,
            'bakes': bakes}


def curved_wall(name='curved_wall', radius=3.74, arc=104.0, height=2.4, bottom=0.0, segments=48, scene=None):
    """A cylinder segment seen from inside, facing its axis: a curved LED wall for screen.apply_to (DAISY's
    verse-2 wall was a 104 degree arc seen from inside). The axis is the object's local Z, the arc centred on
    local +Y, its foot at z = ``bottom``. UV u runs left to right as seen from inside and v upward, so a canvas
    reads upright and unmirrored (the engine's CylinderGeometry needed vec2(1 - u, 1 - v); this mesh's UVs are
    laid out for the viewer instead). Its arc length / height is stored as obj['eido_aspect']: give the canvas that
    aspect (DAISY: 2.83:1 at 2264 x 800, or 1698 x 600 below 1280-pixel output)."""
    scene = scene or bpy.context.scene
    th = math.radians(arc)
    verts, faces, uvs = [], [], []
    for i in range(segments + 1):
        a = math.pi / 2 + th / 2 - th * i / segments          # from the viewer's left (-X) to the right (+X)
        x, y = radius * math.cos(a), radius * math.sin(a)
        verts += [(x, y, bottom), (x, y, bottom + height)]
    for i in range(segments):
        a, b = 2 * i, 2 * i + 2
        faces.append((a, b, b + 1, a + 1))
        uvs.append(((i / segments, 0.0), ((i + 1) / segments, 0.0), ((i + 1) / segments, 1.0), (i / segments, 1.0)))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    lay = me.uv_layers.new(name='UVMap')
    for p, quad in zip(me.polygons, uvs):
        for li, uv in zip(p.loop_indices, quad):
            lay.data[li].uv = uv
    me.update()
    inward = sum(p.normal.dot(-Vector((p.center.x, p.center.y, 0.0)).normalized()) for p in me.polygons)
    if inward < 0:                                    # face the axis: flip the winding (the UVs follow the loops)
        me.flip_normals()
    obj = bpy.data.objects.new(name, me)
    scene.collection.objects.link(obj)
    obj['eido_aspect'] = radius * th / height
    return obj


# ---------------------------------------------------------------------------------------------------- video, ASCII
def _probe_movie(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-count_packets', '-show_entries',
                        'stream=width,height,avg_frame_rate,nb_read_packets,pix_fmt:stream_side_data=rotation',
                        '-of', 'json', str(path)], capture_output=True, text=True)
    s = json.loads(r.stdout)['streams'][0]
    num, den = (int(x) for x in s['avg_frame_rate'].split('/'))
    w, h = int(s['width']), int(s['height'])
    rot = next((int(d.get('rotation', 0)) for d in s.get('side_data_list', []) if 'rotation' in d), 0)
    if abs(rot) % 180 == 90:                          # ffmpeg auto-rotates on decode: the frames come out turned
        w, h = h, w
    return {'w': w, 'h': h, 'fps': num / den if den else 0.0, 'frames': int(s.get('nb_read_packets') or 0),
            'pix_fmt': s.get('pix_fmt', '')}


def engine_movie_frame(k, film_fps, movie_fps, speed, n, loop=True):
    """makeVideoScreen's frame rule (screen.js): film frame k after the screen's start shows movie frame
    floor(t * fps * speed), t = k / film fps; looping it wraps (also before the start, ((f % n) + n) % n), else it
    clamps to the movie. 0-based movie frames."""
    i = math.floor(k / film_fps * movie_fps * speed + 1e-6)
    return i % n if loop else min(max(i, 0), n - 1)


def _retime_frames(path, info, out, name, ks, film_fps, speed, loop):
    """Write <name>_0001.png … for the film frames ks (counted from the screen's start), each showing the movie
    frame engine_movie_frame picks. One ffmpeg decode at the movie's own rate, piped as raw pixels: each needed
    movie frame is encoded once and copied to every film frame that shows it. (An ffmpeg fps filter picks the
    nearest frame where the engine floors: one frame early on many film frames, 11-07 verify.)"""
    n = max(1, int(info['frames']))
    want = {}
    for j, k in enumerate(ks):
        want.setdefault(engine_movie_frame(k, film_fps, info['fps'], speed, n, loop), []).append(j)
    alpha = 'a' in info.get('pix_fmt', '').replace('gray', '').replace('bayer', '')    # yuva420p, rgba, ya8, pal8 …
    mode, ch, fmt = ('RGBA', 4, 'rgba') if alpha else ('RGB', 3, 'rgb24')
    w, h = info['w'], info['h']
    size = w * h * ch
    paths = [out / f'{name}_{j + 1:04d}.png' for j in range(len(ks))]
    cmd = ['ffmpeg', '-v', 'error', '-i', str(path), '-map', '0:v:0', '-fps_mode', 'passthrough',
           '-frames:v', str(max(want) + 1), '-f', 'rawvideo', '-pix_fmt', fmt, '-']
    done, last, i = set(), None, 0
    with subprocess.Popen(cmd, stdout=subprocess.PIPE) as p:
        while True:
            buf = p.stdout.read(size)
            if len(buf) < size:
                break
            last = buf
            if i in want:
                js = want[i]
                raster.save_png(raster.Image.frombytes(mode, (w, h), buf), paths[js[0]])
                data = paths[js[0]].read_bytes()
                for j in js[1:]:
                    paths[j].write_bytes(data)
                done.update(js)
            i += 1
    if last is None:
        raise RuntimeError(f'{path}: ffmpeg decoded no frames')
    rest = [j for j in range(len(ks)) if j not in done]
    if rest:                                          # the movie ran shorter than ffprobe counted: hold its end
        print(f'[screens] {Path(path).name}: {i} frames decoded of {n} counted; {len(rest)} film frames hold the last')
        raster.save_png(raster.Image.frombytes(mode, (w, h), last), paths[rest[0]])
        data = paths[rest[0]].read_bytes()
        for j in rest[1:]:
            paths[j].write_bytes(data)
    return paths


def _movie_means(path, n_expected=None):
    """Per-frame mean linear colour of a movie, from 8 x 8 decodes (ffmpeg)."""
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-vf', 'scale=8:8', '-f', 'rawvideo', '-pix_fmt',
                        'rgb24', '-'], capture_output=True)
    a = np.frombuffer(r.stdout, dtype=np.uint8).reshape(-1, 8, 8, 3) / 255.0
    lin = raster.srgb_to_linear(a)
    return [m for m in lin.reshape(len(lin), -1, 3).mean(axis=1)]


def make_video_screen(path, width=1.6, height=None, start_frame=None, speed=1.0, loop=True, out_dir=None,
                      name='video_screen', scene=None, spill=0.0, standalone=True, **kw):
    """A movie playing on a panel (makeVideoScreen, ported: a native movie texture, no sprite atlas).

    The movie's first frame shows at ``start_frame`` (default the scene's first frame); film frame k after it shows
    movie frame floor(k / film fps * movie fps * speed), as screen.js did. ``loop`` wraps the movie, also before
    the start (the engine's modulo); without it the first frame holds before and the last after. When the movie's
    frame rate is the film's and speed is 1 it plays as a MOVIE image (cyclic with ``loop``); otherwise the movie
    is decoded once and retimed into a PNG sequence at the film's rate (``out_dir``; with ``loop`` it covers the
    scene's range at build time), since a movie image steps one movie frame per scene frame. Other keywords go to
    make_screen (glass, strength, window, interpolation …)."""
    scene = scene or bpy.context.scene
    tb = Timebase.of(scene)
    path = _abspath(path)
    info = _probe_movie(path)
    f0 = scene.frame_start if start_frame is None else int(start_frame)
    height = height or width * info['h'] / info['w']
    name = _unique_name(name)
    if abs(info['fps'] - tb.fps) < 1e-3 and abs(speed - 1.0) < 1e-9:
        img = bpy.data.images.load(_stored_path(path), check_existing=False)
        img.name = name
        n = info['frames'] or img.frame_duration     # the counted frames (ffprobe): a looping screen wraps here
        img['eido_frame_start'] = f0
        img['eido_frame_duration'] = n
        img['eido_frame_offset'] = 0
        img['eido_cyclic'] = bool(loop)
        means, ms = None, None
        if spill:
            m = _movie_means(path)
            ms = min(scene.frame_start, f0) if loop else f0
            last = max(scene.frame_end, f0) if loop else f0 + n - 1
            means = [m[engine_movie_frame(f - f0, 1.0, 1.0, 1.0, len(m), loop)] for f in range(ms, last + 1)]
        scr = Screen(img, width=width, height=height, px_size=(info['w'], info['h']), name=name, means=means,
                     means_start=ms,
                     opts=dict(lit=kw.get('lit', False), transparent=kw.get('transparent', False),
                               glass=kw.get('glass', False), strength=kw.get('strength', 1.0),
                               window=kw.get('window'), flip=kw.get('flip', False), mirror_x=kw.get('mirror_x', False),
                               interpolation=kw.get('interpolation', 'Linear'),
                               double_sided=kw.get('double_sided', False), spill=spill,
                               spill_reach=kw.get('spill_reach', 30.0)))
        if standalone:
            me = _plane(name, width, height)
            obj = bpy.data.objects.new(name, me)
            scene.collection.objects.link(obj)
            scr.material = scr.material_for()
            me.materials.append(scr.material)
            scr.obj = obj
            if spill:
                scr._spill(obj, spill, kw.get('window'))
        return scr
    # retime: the engine's floor rule per film frame, from one decode at the movie's own rate
    out = _abspath(out_dir) if out_dir else _default_dir(name)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob(f'{glob.escape(name)}_[0-9][0-9][0-9][0-9].png'):
        old.unlink()
    n = max(1, info['frames'])
    if loop:                                          # the scene's whole range: the loop also runs before the start
        fa, fb = min(scene.frame_start, f0), max(scene.frame_end, f0)
    else:                       # until the last movie frame first shows (then it holds), or the scene's end
        r = info['fps'] * speed / tb.fps
        k_end = 0 if r <= 0 else max(0, math.ceil((n - 1) / r) - 1)
        while r > 0 and engine_movie_frame(k_end, tb.fps, info['fps'], speed, n, False) < n - 1:
            k_end += 1
        fa, fb = f0, min(f0 + k_end, max(scene.frame_end, f0))
    _retime_frames(path, info, out, name, range(fa - f0, fb - f0 + 1), tb.fps, speed, loop)
    return make_screen(width=width, height=height, source=out / f'{name}_0001.png', frames=(fa, fb),
                       name=name, scene=scene, spill=spill, standalone=standalone, **kw)


def read_atlas_info(info):
    """A video_to_sprite.mjs *_info.json (a path or the dict): {cols, rows, totalFrames, fps, frameWidth,
    frameHeight, atlasWidth, atlasHeight}."""
    if not isinstance(info, dict):
        info = json.loads(_abspath(info).read_text(encoding='utf-8'))
    for k in ('cols', 'rows', 'totalFrames', 'fps'):
        if not info.get(k):
            raise ValueError(f'atlas info needs {k} (video_to_sprite.mjs writes cols, rows, totalFrames, fps, '
                             f'frameWidth, frameHeight)')
    return info


def atlas_tile(atlas, info, i):
    """Tile ``i`` (0-based) of a sprite atlas as a PIL image: row-major from the top left, frameWidth x frameHeight
    each (ffmpeg's tile filter, video_to_sprite.mjs's layout; screen.js stepped the texture offset the same way)."""
    info = read_atlas_info(info)
    im = atlas if isinstance(atlas, raster.Image.Image) else raster.Image.open(_abspath(atlas))
    fw = int(info.get('frameWidth') or im.width // info['cols'])
    fh = int(info.get('frameHeight') or im.height // info['rows'])
    c, r = i % info['cols'], i // info['cols']
    return im.crop((c * fw, r * fh, (c + 1) * fw, (r + 1) * fh))


def make_atlas_screen(atlas, info, width=1.6, height=None, start_frame=None, speed=1.0, loop=True, out_dir=None,
                      name='video_screen', scene=None, **kw):
    """makeVideoScreen({texture, info}), the sprite-atlas form: an atlas video_to_sprite.mjs made (a JPEG of tiles +
    its *_info.json) playing on a panel by screen.js's rule: film frame k after ``start_frame`` shows tile
    floor(t * info.fps * speed), t = k / film fps, wrapping with ``loop`` (also before the start) or clamped.
    The tiles are cut once and laid out per film frame as a PNG sequence (``out_dir``), then shown by make_screen
    (other keywords: glass, strength, spill, window, transparent ...). The height defaults to the tile's aspect.
    For a movie file, make_video_screen plays it natively, frame-exact, with no atlas."""
    scene = scene or bpy.context.scene
    tb = Timebase.of(scene)
    info = read_atlas_info(info)
    im = raster.Image.open(_abspath(atlas)).convert('RGB')
    n, fps = int(info['totalFrames']), float(info['fps'])
    f0 = scene.frame_start if start_frame is None else int(start_frame)
    fw = int(info.get('frameWidth') or im.width // info['cols'])
    fh = int(info.get('frameHeight') or im.height // info['rows'])
    height = height or width * fh / fw
    name = _unique_name(name)
    out = _abspath(out_dir) if out_dir else _default_dir(name)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob(f'{glob.escape(name)}_[0-9][0-9][0-9][0-9].png'):
        old.unlink()
    if loop:
        fa, fb = min(scene.frame_start, f0), max(scene.frame_end, f0)
    else:
        k_end = 0
        while engine_movie_frame(k_end, tb.fps, fps, speed, n, False) < n - 1 and f0 + k_end < scene.frame_end:
            k_end += 1
        fa, fb = f0, f0 + k_end
    tiles = {}
    for j, f in enumerate(range(fa, fb + 1)):
        i = engine_movie_frame(f - f0, tb.fps, fps, speed, n, loop)
        dst = out / f'{name}_{j + 1:04d}.png'
        if i in tiles:
            dst.write_bytes(tiles[i].read_bytes())
        else:
            raster.save_png(atlas_tile(im, info, i), dst)
            tiles[i] = dst
    scr = make_screen(width=width, height=height, source=out / f'{name}_0001.png', frames=(fa, fb), name=name,
                      scene=scene, **kw)
    scr.atlas_info = info
    return scr


def make_ascii_panel(text, color='#27e0a0', background='#050a08', width=1.2, height=None, px=None, reveal=0.0,
                     fps=8, font='Share Tech Mono', frames=None, out_dir=None, name='ascii_panel', **kw):
    """Multi-line monospace text as a glowing terminal panel (makeAsciiPanel, ported): an optional teletype
    ``reveal`` (characters per second; 0 = all at once) and a blinking block cursor. The font is a real monospace
    file (Share Tech Mono, VT323, Space Mono …), never a generic family. Other keywords go to make_screen."""
    lines = str(text).replace('\t', '    ').split('\n')
    cols = max(1, max(len(l) for l in lines))
    px = px or min(1024, max(384, cols * 18))
    ch_w = px / (cols + 2)
    ch_h = ch_w * 1.9
    height = height or width * ((len(lines) + 1) * ch_h) / px
    total = sum(len(l) for l in lines)
    fsize = int(ch_h * 0.62)

    def draw(c, t, w, h):
        s = w / px                                     # supersampling
        c.clear(background)
        f = raster.font(font, fsize * s)
        budget = int(t * reveal) if reveal > 0 else 10 ** 9
        last_x, last_y = ch_w * s, ch_h * 0.5 * s
        for i, ln in enumerate(lines):
            if budget <= 0:
                break
            chunk = ln[:budget]
            y = (ch_h * 0.5 + i * ch_h) * s
            c.draw.text((ch_w * s, y), chunk, font=f, fill=raster.color(color), anchor='la')
            budget -= len(ln)
            last_x, last_y = ch_w * s + f.getlength(chunk), y
        if (reveal == 0 or int(t * reveal) < total + 8) and int(math.floor(t * 1.6)) % 2 == 0:
            c.draw.rectangle([last_x + 2 * s, last_y, last_x + 2 * s + ch_w * 0.55 * s, last_y + ch_h * 0.7 * s],
                             fill=raster.color(color))

    return make_screen(width=width, height=height, px=px, draw=draw, frames=frames, fps=fps, out_dir=out_dir,
                       name=name, **kw)
