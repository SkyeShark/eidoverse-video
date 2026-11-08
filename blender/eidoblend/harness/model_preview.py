"""eidoblend.harness.model_preview: fetch_model.py's orientation preview, rendered in Blender, in Blender's words.

The WebGPU edition's fetch_model.py renders a 512 x 512 `<model>_preview.jpg` with three.js (Deno) and prints three
lines an agent reads before placing a model: [PREVIEW_BBOX], [ORIGIN_INFO] and [KIT_INFO], all Y-up. This is the same
preview from the model as Blender imports it (glTF's +Y up becomes +Z up): the model in EEVEE under a three-point
rig, a yellow bounding-box wireframe and a faint ground grid (both depth-tested), the axes from the box centre and the
face labels drawn on top (red X, green Y, blue Z up; the dimmer rays are -X and -Y), and a title plate with the file
name and its size X x Y x Z.

    bash run_blender.sh blender/eidoblend/harness/model_preview.py <model.glb> [<model2.gltf> ...] [--out DIR|FILE]
                                                                   [--size 512] [--samples 16] [--no-render]

Without --out the preview lands beside the model as <name>_preview.jpg (fetch_model.py's place for it). Printed per
model, for fetch_model.py to relay (it parses these lines):

    [PREVIEW_BBOX] sx sy sz            the glTF / three order (width, height, depth), as fetch_model.py reads it
    [PREVIEW_BBOX_BLENDER] X Y Z       Blender's (Z up), metres
    [ORIGIN_INFO] ...                  where the pivot sits in the box: BASE / CENTERED / TOP / OUTSIDE / OFFSET
    [KIT_INFO] ...                     a parts catalogue (LIKELY A MODULAR KIT) or a few named parts to judge
    Preview: <path>

In a script: preview(path, out=None, size=512, samples=16) -> {'bbox', 'bbox_blender', 'origin_info', 'kit_info',
'preview'}. classify_kit(names) and origin_words(lo, hi) are the plain heuristics (no bpy), shared with the tests.
"""

from __future__ import annotations

import math
import os
import re
import sys

KIT_STEM_SUFFIX = re.compile(r'_(small|med|medium|large|xl|sm|lg|s|m|l)$')


# ---------------------------------------------------------------------------------- the heuristics (no bpy) ---

def kit_stem(name: str) -> str:
    """A part name's base type, as the engine's preview stems it: a trailing _LODn first (Poly Haven plants bury the
    variant letter before it), then trailing enumeration (_NN / _a..z / _small|med|large) until nothing changes.
    Blender's own '.001' duplicate suffix is dropped first."""
    x = re.sub(r'\.\d{3}$', '', str(name)).lower()
    x = re.sub(r'_lod\d+$', '', x)
    while True:
        prev = x
        x = re.sub(r'_(\d+)$', '', x)
        x = re.sub(r'_[a-z]$', '', x)
        x = KIT_STEM_SUFFIX.sub('', x)
        if x == prev:
            return x


def classify_kit(names) -> str | None:
    """[KIT_INFO] from a model's top-level part names, the engine's rule: a LIKELY KIT when repeated variants of one
    item make up at least half the parts, or there are 8 or more; otherwise a neutral line to judge from the preview.
    None for fewer than 2 parts."""
    parts = list(names)
    if len(parts) < 2:
        return None
    fam = {}
    for p in parts:
        k = kit_stem(p)
        fam[k] = fam.get(k, 0) + 1
    families = sorted(fam.items(), key=lambda kv: -kv[1])          # stable: ties keep first-seen order
    in_multi = sum(v for v in fam.values() if v >= 2)
    pct = int(math.floor(100 * in_multi / len(parts) + 0.5))       # JavaScript's Math.round
    fam_str = ', '.join(f'{k}×{v}' if v > 1 else k for k, v in families[:8]) + (', …' if len(families) > 8 else '')
    if pct >= 50 or len(parts) >= 8:
        return (f'[KIT_INFO] LIKELY A MODULAR KIT / ASSET-LIBRARY: {len(parts)} named parts'
                + (f', {pct}% in repeated variant-families' if pct >= 50 else '') + f' ({fam_str}). '
                'These are parts laid out for ASSEMBLY, not one finished model: placing the whole import scatters '
                'them. Use eidoblend.harness.assets.load_kit(path): kit.list() / kit.get(name) / kit.family(prefix) / '
                'kit.islands() give named parts standing on their own base, to place / array / combine. Pick one, or '
                'build from several.')
    return (f'[KIT_INFO] {len(parts)} named parts ({fam_str}). Could be a finished assembly (place it whole) OR a '
            'small set to split: JUDGE FROM THIS PREVIEW. If the parts should be used separately, '
            'eidoblend.harness.assets.load_kit(path) gives them one by one (each standing on its base).')


def _cls(lo, hi, size):
    t = 1e-4 + size * 0.08
    if abs(lo) <= t:
        return 'min'
    if abs(hi) <= t:
        return 'max'
    if abs((lo + hi) / 2) <= t:
        return 'center'
    return 'outside' if (0 < lo or 0 > hi) else 'offset'


def origin_words(lo, hi) -> str:
    """[ORIGIN_INFO]: where the model's origin (0, 0, 0) sits inside its box, in words, Z up. lo, hi: the box's
    (x, y, z) corners in model space."""
    size = [hi[i] - lo[i] for i in range(3)]
    oz = _cls(lo[2], hi[2], size[2])
    zw = {'min': 'at the BASE: z=0 is the model BOTTOM, so it rests directly ON a surface (do NOT add half-height)',
          'center': 'CENTERED vertically: z=0 is mid-height, so to stand it on a floor add half the height (or just '
                    'use place_on)',
          'max': 'at the TOP: z=0 is the model TOP, so it hangs DOWN from z',
          'outside': 'OUTSIDE the box vertically (the origin is away from the geometry)',
          'offset': 'OFFSET vertically (the origin is not at the base, centre or top)'}[oz]
    return (f'[ORIGIN_INFO] Pivot/origin: {zw}. Lateral: X {_cls(lo[0], hi[0], size[0])}, '
            f'Y {_cls(lo[1], hi[1], size[1])}. bbox(modelspace, Z up) Z[{lo[2]:.3f}..{hi[2]:.3f}] '
            f'X[{lo[0]:.3f}..{hi[0]:.3f}] Y[{lo[1]:.3f}..{hi[1]:.3f}]. PREFER place_on / place_against (they seat the '
            'box, ignoring the origin) or assets.rest_on over a hand-set location.z.')


# ------------------------------------------------------------------------------------------------ the render ---

GRID = (0x66 / 255, 0x66 / 255, 0x88 / 255)
GRID_DIM = (0x3a / 255, 0x3a / 255, 0x4a / 255)
BACKGROUND = '#2a2a38'
LABEL_COLOURS = {'X': '#c64a4a', 'Y': '#3eaa3e', 'Z': '#4a5fc6'}
AXIS_COLOURS = {'X': (255, 64, 64), 'Y': (64, 220, 64), 'Z': (80, 110, 255)}


def _srgb(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _emissive(name, rgb, strength=1.0):
    import bpy
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (*rgb, 1.0)
    em.inputs['Strength'].default_value = strength
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    return m


def _bars(name, segments, width, mat):
    """Thin square bars along segments [(a, b)] (a wireframe that renders, depth-tested like three's helpers)."""
    import bpy
    from mathutils import Vector
    verts, faces = [], []
    for a, b in segments:
        a, b = Vector(a), Vector(b)
        d = b - a
        if d.length < 1e-9:
            continue
        d.normalize()
        u = d.cross(Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))).normalized() * (width / 2)
        v = d.cross(u).normalized() * (width / 2)
        k = len(verts)
        for p in (a, b):
            verts += [p + u + v, p - u + v, p - u - v, p + u - v]
        faces += [(k, k + 1, k + 5, k + 4), (k + 1, k + 2, k + 6, k + 5), (k + 2, k + 3, k + 7, k + 6),
                  (k + 3, k, k + 4, k + 7), (k, k + 3, k + 2, k + 1), (k + 4, k + 5, k + 6, k + 7)]
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(p) for p in verts], [], faces)
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.visible_shadow = False
    return ob


def _sun(name, pos, energy, rgb):
    import bpy
    from mathutils import Vector
    d = bpy.data.lights.new(name, 'SUN')
    d.energy, d.color, d.angle = energy, rgb, math.radians(3)
    ob = bpy.data.objects.new(name, d)
    ob.rotation_euler = (-Vector(pos)).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.collection.objects.link(ob)
    return ob


def _world():
    import bpy
    w = bpy.data.worlds.new('preview')
    w.use_nodes = True
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    bg = nt.nodes.new('ShaderNodeBackground')                    # what the camera sees: the engine's #2a2a38
    bg.inputs['Color'].default_value = (_srgb(0x2a / 255), _srgb(0x2a / 255), _srgb(0x38 / 255), 1)
    amb = nt.nodes.new('ShaderNodeBackground')                   # the AmbientLight(0xffffff, 0.7): light only
    amb.inputs['Color'].default_value = (1, 1, 1, 1)
    amb.inputs['Strength'].default_value = 0.32
    lp = nt.nodes.new('ShaderNodeLightPath')
    mix = nt.nodes.new('ShaderNodeMixShader')
    out = nt.nodes.new('ShaderNodeOutputWorld')
    nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs['Fac'])
    nt.links.new(amb.outputs[0], mix.inputs[1])
    nt.links.new(bg.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    bpy.context.scene.world = w


def _parts(root):
    """The import's top-level parts with geometry, descending single-child wrappers (as the engine's preview)."""
    host = root
    while len(host.children) == 1 and len(host.children[0].children) > 1:
        host = host.children[0]
    out = []
    for ch in host.children:
        if any(d.type == 'MESH' for d in [ch] + list(ch.children_recursive)):
            out.append(ch.name)
    return out


def _overlay(png, out, cam, scene, centre, lo, hi, max_dim, title, subtitle, size):
    """The engine's on-top layer (depthTest false): axes from the box centre, the face labels, the title plate."""
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Vector
    from PIL import Image, ImageDraw
    from ..media import raster
    im = Image.open(png).convert('RGB')
    W, H = im.size
    d = ImageDraw.Draw(im, 'RGBA')

    def px(p):
        v = world_to_camera_view(scene, cam, Vector(p))
        return (v.x * W, (1 - v.y) * H), v.z > 0
    c, _ = px(centre)
    L = max_dim * 0.75
    lw = max(2, size // 200)
    for ax, k, dim in (('X', 0, False), ('Y', 1, False), ('Z', 2, False), ('X', 0, True), ('Y', 1, True)):
        e = list(centre)
        e[k] += -L if dim else L
        p, ok = px(e)
        if not ok:
            continue
        r, g, b = AXIS_COLOURS[ax]
        d.line([c, p], fill=(r, g, b, 140 if dim else 255), width=lw)
    f = raster.font('SpaceMono-Bold', max(12, int(size * 0.052)))
    off = max_dim * 0.10
    specs = [('+Z', 'Z', (centre[0], centre[1], hi[2] + off)), ('+X', 'X', (hi[0] + off, centre[1], centre[2])),
             ('-X', 'X', (lo[0] - off, centre[1], centre[2])), ('+Y', 'Y', (centre[0], hi[1] + off, centre[2])),
             ('-Y', 'Y', (centre[0], lo[1] - off, centre[2]))]
    for text, ax, pos in specs:
        p, ok = px(pos)
        if not ok:
            continue
        d.text(p, text, font=f, fill=LABEL_COLOURS[ax], anchor='mm', stroke_width=max(2, size // 128),
               stroke_fill=(0, 0, 0, 216))
    ft = raster.font('SpaceMono-Bold', max(10, int(size * 0.031)))
    fs = raster.font('SpaceMono-Regular', max(9, int(size * 0.024)))
    pad = max(6, size // 42)
    tw = max(ft.getlength(title), fs.getlength(subtitle))
    th = ft.size + fs.size + pad // 2
    x0, y0 = pad, pad
    d.rectangle([x0, y0, x0 + tw + 2 * pad, y0 + th + 2 * pad], fill=(0, 0, 0, 184))
    d.text((x0 + pad, y0 + pad), title, font=ft, fill=(255, 255, 255, 255))
    d.text((x0 + pad, y0 + pad + ft.size + pad // 2), subtitle, font=fs, fill=(204, 204, 204, 255))
    im.save(out, quality=92)


def preview(path: str, out: str = None, size: int = 512, samples: int = 16, render: bool = True) -> dict:
    """Render one model's preview and return its info lines (see the module docstring). Resets the open file.
    render=False measures and classifies only (the lines without the picture)."""
    import bpy
    from mathutils import Vector
    from . import assets
    bpy.ops.wm.read_homefile(use_empty=True)
    scene = bpy.context.scene
    root = assets.import_model(os.path.abspath(path), name='model')
    bpy.context.view_layer.update()
    lo, hi = assets.bounds(root)
    sz = hi - lo
    centre = (lo + hi) / 2
    max_dim = max(sz) or 1.0
    info = {'bbox': (sz.x, sz.z, sz.y), 'bbox_blender': tuple(sz),
            'origin_info': origin_words(tuple(lo), tuple(hi)), 'kit_info': classify_kit(_parts(root)),
            'preview': None}
    if not render:
        return info
    r = scene.render
    r.engine = 'BLENDER_EEVEE'
    r.resolution_x = r.resolution_y = int(size)
    r.resolution_percentage = 100
    r.film_transparent = False
    r.image_settings.media_type = 'IMAGE'
    r.image_settings.file_format = 'PNG'
    scene.eevee.taa_render_samples = int(samples)
    scene.eevee.use_raytracing = True
    scene.eevee.use_fast_gi = True
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Base Contrast'
    scene.view_settings.exposure = 0.14                          # the engine's toneMappingExposure 1.1
    _world()
    _sun('key', (4, -3, 6), 3.4, (1.0, 1.0, 1.0))                # three (4, 6, 3) -> Blender (x, -z, y)
    _sun('fill', (-4, 2, 2), 1.1, (0.73, 0.8, 1.0))              # three (-4, 2, -2), 0xbbccff
    _sun('rim', (0, 5, 3), 0.9, (1.0, 0.88, 0.69))               # three (0, 3, -5), 0xffe0b0
    w = max_dim * 0.006
    edges = []
    xs, ys, zs = (lo.x, hi.x), (lo.y, hi.y), (lo.z, hi.z)
    for y in ys:
        for z in zs:
            edges.append(((lo.x, y, z), (hi.x, y, z)))
    for x in xs:
        for z in zs:
            edges.append(((x, lo.y, z), (x, hi.y, z)))
    for x in xs:
        for y in ys:
            edges.append(((x, y, lo.z), (x, y, hi.z)))
    _bars('bbox', edges, w, _emissive('bbox', (1.0, 1.0, 0.0), 1.2))
    g = max_dim * 2.6
    gz = min(0.0, lo.z)
    lines_c, lines = [], []
    for i in range(13):
        t = -g / 2 + g * i / 12
        seg_x = ((centre.x - g / 2, centre.y + t, gz), (centre.x + g / 2, centre.y + t, gz))
        seg_y = ((centre.x + t, centre.y - g / 2, gz), (centre.x + t, centre.y + g / 2, gz))
        (lines_c if i == 6 else lines).extend([seg_x, seg_y])
    _bars('grid', lines, w * 0.6, _emissive('grid', tuple(map(_srgb, GRID_DIM)), 1.0))
    _bars('grid_centre', lines_c, w * 0.8, _emissive('grid_centre', tuple(map(_srgb, GRID)), 1.0))
    cd = bpy.data.cameras.new('preview')
    cd.sensor_fit = 'VERTICAL'
    cd.angle_y = math.radians(35)
    diag = sz.length
    dist = max(diag, max_dim) * 1.35
    cd.clip_start, cd.clip_end = dist * 0.01, dist * 10
    cam = bpy.data.objects.new('preview', cd)
    cam.location = centre + Vector((0.85, -0.85, 0.78)) * dist    # three's (0.85, 0.78, 0.85): front-right, above
    aim = centre + Vector((0, 0, max_dim * 0.05))
    cam.rotation_euler = (aim - cam.location).to_track_quat('-Z', 'Y').to_euler()
    scene.collection.objects.link(cam)
    scene.camera = cam
    stem = os.path.splitext(os.path.basename(path))[0]
    if out is None:
        out = os.path.join(os.path.dirname(os.path.abspath(path)), f'{stem}_preview.jpg')
    elif os.path.isdir(out) or out.endswith(('/', '\\')):
        os.makedirs(out, exist_ok=True)
        out = os.path.join(out, f'{stem}_preview.jpg')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    png = os.path.abspath(out) + '.render.png'
    r.filepath = png
    r.use_file_extension = False
    bpy.context.view_layer.update()                              # the camera's matrix, for the overlay's projection
    bpy.ops.render.render(write_still=True)
    _overlay(png, out, cam, scene, tuple(centre), tuple(lo), tuple(hi), max_dim, os.path.basename(path),
             f'{sz.x:.2f} x {sz.y:.2f} x {sz.z:.2f} m (X x Y x Z up)', int(size))
    os.remove(png)
    info['preview'] = os.path.abspath(out)
    return info


def main(argv):
    paths, out, size, samples, render = [], None, 512, 16, True
    it = iter(argv)
    for a in it:
        if a == '--no-render':
            render = False
        elif a == '--out':
            out = next(it)
        elif a == '--size':
            size = int(next(it))
        elif a == '--samples':
            samples = int(next(it))
        else:
            paths.append(a)
    if not paths:
        print('usage: model_preview.py <model> [<model> ...] [--out DIR|FILE] [--size 512] [--samples 16]')
        return 2
    rc = 0
    for p in paths:
        try:
            o = out if (out is None or len(paths) == 1) else (out if out.endswith(('/', '\\')) else out + '/')
            info = preview(p, o, size, samples, render)
        except Exception as e:                                   # noqa: BLE001 - a preview never stops the batch
            print(f'[preview] {p}: failed ({type(e).__name__}: {e})', flush=True)
            rc = 1
            continue
        bx, by, bz = info['bbox']
        print(f'[PREVIEW_BBOX] {bx} {by} {bz}')
        print('[PREVIEW_BBOX_BLENDER] ' + ' '.join(str(v) for v in info['bbox_blender']))
        print(info['origin_info'])
        if info['kit_info']:
            print(info['kit_info'])
        if info['preview']:
            print(f"Preview: {info['preview']}", flush=True)
    return rc


if __name__ == '__main__':
    here = os.path.dirname(os.path.abspath(__file__))
    pkg_root = os.path.dirname(os.path.dirname(here))            # <repo>/blender
    if pkg_root not in sys.path:
        sys.path.insert(0, pkg_root)
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    from eidoblend.harness import model_preview as _mp            # the package's copy (relative imports)
    code = _mp.main(args)
    sys.stdout.flush()
    os._exit(code)
