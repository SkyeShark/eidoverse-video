"""Shared staging for the voice-machines-b probes: an EEVEE scene, a museum floor, soft studio lights, a camera, stills.

Imported by the test scripts beside it (run through run_blender.sh, renders through the GPU slot). Probe renders stay
small: 960 x 540 at most, 16 EEVEE samples or fewer. Each script prints PASS / FAIL lines for what it checks.
"""
import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
WORKTREE = HERE.parents[2]
OUT = HERE / 'out'
OUT.mkdir(exist_ok=True)
if str(WORKTREE / 'blender') not in sys.path:
    sys.path.insert(0, str(WORKTREE / 'blender'))

RESULTS = []


def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok)))
    print(f'{"PASS" if ok else "FAIL"} {name}' + (f'  ({detail})' if detail else ''), flush=True)
    return ok


def summary(tag):
    n_fail = sum(1 for _, ok in RESULTS if not ok)
    print(f'[{tag}] {len(RESULTS) - n_fail} passed, {n_fail} failed', flush=True)
    return n_fail


def fresh_scene(res=(960, 540), samples=16, fps=24, frames=(1, 48)):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    r = sc.render
    r.engine = 'BLENDER_EEVEE'
    r.resolution_x, r.resolution_y = res
    r.resolution_percentage = 100
    r.fps, r.fps_base = fps, 1.0
    sc.frame_start, sc.frame_end = frames
    e = sc.eevee
    e.taa_render_samples = samples
    e.use_raytracing = True
    e.use_shadows = True
    try:                       # three shadow rays a sample: the big soft studio lights' penumbrae clean at 16 samples
        e.shadow_ray_count = 3
    except (AttributeError, TypeError):
        pass
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'None'
    w = bpy.data.worlds.new('world')
    sc.world = w
    if w.node_tree is None:
        w.use_nodes = True
    bg = w.node_tree.nodes.get('Background') or w.node_tree.nodes.new('ShaderNodeBackground')
    bg.inputs['Color'].default_value = (0.035, 0.037, 0.042, 1)
    bg.inputs['Strength'].default_value = 1.0
    return sc


def floor(sc, size=12.0, color=(0.16, 0.155, 0.15), rough=0.55, z=0.0):
    me = bpy.data.meshes.new('floor')
    s = size / 2
    me.from_pydata([(-s, -s, z), (s, -s, z), (s, s, z), (-s, s, z)], [], [(0, 1, 2, 3)])
    m = bpy.data.materials.new('floor')
    if m.node_tree is None:
        m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*color, 1)
    b.inputs['Roughness'].default_value = rough
    me.materials.append(m)
    ob = bpy.data.objects.new('floor', me)
    sc.collection.objects.link(ob)
    return ob


def look_at(obj, target):
    d = (Vector(target) - obj.location).normalized()
    obj.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def camera(sc, loc, target, lens=50.0, name='cam'):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_start = 0.01
    c = bpy.data.objects.new(name, cd)
    sc.collection.objects.link(c)
    c.location = loc
    look_at(c, target)
    sc.camera = c
    return c


def area(sc, loc, target, power, size=1.0, color=(1, 1, 1), name='key', spread=None):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.energy = power
    ld.color = color
    ld.size = size
    if spread is not None:
        ld.spread = spread
    o = bpy.data.objects.new(name, ld)
    sc.collection.objects.link(o)
    o.location = loc
    look_at(o, target)
    return o


def studio(sc, target, dist=3.0, scale=1.0, key=600.0):
    """A soft three-point museum light around target (power scaled for the subject's size)."""
    t = Vector(target)
    area(sc, t + Vector((-1.6, -2.2, 1.9)) * dist / 3, t, key * scale * scale, size=2.0 * scale, color=(1.0, 0.95, 0.88), name='key')
    area(sc, t + Vector((2.4, -1.6, 0.8)) * dist / 3, t, key * 0.35 * scale * scale, size=2.5 * scale, color=(0.85, 0.9, 1.0), name='fill')
    area(sc, t + Vector((0.6, 2.4, 2.2)) * dist / 3, t, key * 0.5 * scale * scale, size=1.5 * scale, color=(1.0, 0.97, 0.92), name='rim')


def wall(sc, y=2.0, width=12.0, height=4.0, color=(0.3, 0.29, 0.27), rough=0.8, name='wall'):
    """A back wall standing at y, facing -Y (toward the camera side)."""
    me = bpy.data.meshes.new(name)
    s = width / 2
    me.from_pydata([(-s, y, 0), (s, y, 0), (s, y, height), (-s, y, height)], [], [(0, 3, 2, 1)])
    m = bpy.data.materials.new(name)
    if m.node_tree is None:
        m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*color, 1)
    b.inputs['Roughness'].default_value = rough
    me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    sc.collection.objects.link(ob)
    return ob


def look_from(cam, loc, target, lens=None):
    cam.location = loc
    look_at(cam, target)
    if lens:
        cam.data.lens = lens
    return cam


def bounds(objs):
    """World AABB (lo, hi) of the mesh objects among objs (evaluated, so modifiers and GN count)."""
    dg = bpy.context.evaluated_depsgraph_get()
    lo = Vector((1e9, 1e9, 1e9))
    hi = -lo
    for o in objs:
        if o.type not in ('MESH', 'CURVE') or not o.visible_get():
            continue
        ev = o.evaluated_get(dg)
        for c in ev.bound_box:
            w = ev.matrix_world @ Vector(c)
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
    return lo, hi


def decals_drawn(tag, images):
    """PASS when every canvas image a machine drew holds a drawing (some ink and some contrast), read back from
    the packed Blender image (a blank pack is the failure this catches)."""
    import numpy as np
    bad = []
    for im in images:
        n = im.size[0] * im.size[1] * 4
        px = np.empty(n, np.float32)
        im.pixels.foreach_get(px)
        px = px.reshape(-1, 4)
        ink = px[:, 3].max() > 0.5 and float(px[:, :3].std()) > 0.02
        if not ink:
            bad.append(im.name)
    return check(f'{tag}: {len(images)} canvas images hold their drawings', not bad, ', '.join(bad))


def decal_standoffs(machine):
    """{decal object: (smallest, largest) gap (m) between its quad's corners and face centres and the surface behind
    them, along the quad's normal}: a decal must lie on its panel (the pack's quads sit 0.1-0.9 mm off), never float,
    never sink. A point with nothing behind it within 5 cm (the Voder's dial card overfills its bore, its corners
    under the bezel) is left out."""
    from eidoblend.props.voice_machines import voder as K
    sc = bpy.context.scene
    bpy.context.view_layer.update()
    out = {}
    for o in [machine.group] + list(machine.group.children_recursive):
        roles = K.roles_of(o) if o.type == 'MESH' else []
        if not roles or not all(r.startswith('decal') for r in roles) or not len(o.data.polygons):
            continue
        mw = o.matrix_world
        n = (mw.to_3x3().inverted().transposed() @ o.data.polygons[0].normal).normalized()
        o.hide_set(True)
        dg = bpy.context.evaluated_depsgraph_get()
        gaps = []
        for p in [mw @ v.co for v in o.data.vertices] + [mw @ f.center for f in o.data.polygons]:
            ok, loc, *_ = sc.ray_cast(dg, p + n * 0.002, -n, distance=0.05)
            if ok:
                gaps.append((p - loc).dot(n))
        o.hide_set(False)
        out[o.name] = (min(gaps), max(gaps)) if gaps else (float('inf'), float('inf'))
    return out


def decals_on_panels(tag, machine, n, extra_ok=True, extra=''):
    """PASS when the machine's n decal quads all lie on their panels: every corner 0.15..1 mm in front of the surface
    (no float; and clear of the panel's depth, which the engine's polygonOffset guaranteed)"""
    gaps = decal_standoffs(machine)
    return check(f'{tag}: every decal lies on its panel (0.15-1 mm in front: no float, no z-fight){extra}',
                 len(gaps) == n and all(0.00015 < lo and hi < 0.001 for lo, hi in gaps.values()) and extra_ok,
                 ', '.join(f'{k} {lo * 1000:.2f}-{hi * 1000:.2f} mm' for k, (lo, hi) in gaps.items()))


def rest_height(machine, skip=('cable',)):
    """The lowest point of the machine's faces, leaving out the roles in `skip` (the pack's cords and floor cables run
    down into the floor, as the WebGPU machines' did): where its feet stand."""
    import numpy as np
    from eidoblend.props.voice_machines import voder as K
    bpy.context.view_layer.update()
    low = float('inf')
    for o in [machine.group] + list(machine.group.children_recursive):
        if o.type != 'MESH' or not len(o.data.polygons):
            continue
        roles = K.roles_of(o)
        me = o.data
        mi = np.empty(len(me.polygons), np.int32)
        me.polygons.foreach_get('material_index', mi)
        keep = np.array([not (k < len(roles) and roles[k] in skip) for k in range(max(len(roles), 1) + mi.max() + 1)])
        loops = [list(p.vertices) for p, k in zip(me.polygons, mi) if keep[k]]
        if not loops:
            continue
        idx = np.unique(np.concatenate([np.array(v) for v in loops]))
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)[idx]
        mw = np.array(o.matrix_world)
        low = min(low, float((co @ mw[:3, :3].T + mw[:3, 3])[:, 2].min()))
    return low


def fcurves_of(idb):
    """every F-curve of an ID's active action (Blender 5's layered actions)"""
    ad = idb.animation_data
    if ad is None or ad.action is None:
        return []
    return [fc for ly in ad.action.layers for st in ly.strips for cb in st.channelbags for fc in cb.fcurves]


DATA_KINDS = ('objects', 'meshes', 'materials', 'images', 'node_groups', 'collections', 'actions')


def dispose_leaves_nothing(tag, build, dispose=None):
    """Build a second piece with build(), dispose it (its .dispose(), or dispose(piece)), and PASS when the blend holds
    exactly what it held before: no object, mesh, material, image, node group, collection or action left behind (the
    JS dispose() freed its GPU resources; here the data-blocks go), and nothing of the first piece taken with it."""
    before = {k: set(getattr(bpy.data, k).keys()) for k in DATA_KINDS}
    piece = build()
    made = sum(len(set(getattr(bpy.data, k).keys()) - before[k]) for k in DATA_KINDS)
    (dispose or (lambda p: p.dispose()))(piece)
    left = {k: sorted(set(getattr(bpy.data, k).keys()) - before[k]) for k in DATA_KINDS}
    left = {k: v for k, v in left.items() if v}
    gone = {k: sorted(before[k] - set(getattr(bpy.data, k).keys())) for k in DATA_KINDS}
    gone = {k: v for k, v in gone.items() if v}
    return check(f'{tag}: dispose() removes all {made} data-blocks build() made, and nothing else',
                 made > 0 and not left and not gone,
                 f'left {str(left)[:240]}, took {str(gone)[:160]}' if left or gone else '')


def contact_sheet(paths, out, cols=2, label=True):
    """Tile stills into one PNG (for looking at several probes side by side)."""
    from PIL import Image, ImageDraw
    ims = [Image.open(p).convert('RGB') for p in paths if Path(p).exists()]
    if not ims:
        return None
    w, h = ims[0].size
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new('RGB', (w * cols, h * rows), (0, 0, 0))
    for i, im in enumerate(ims):
        sheet.paste(im.resize((w, h)), ((i % cols) * w, (i // cols) * h))
        if label:
            ImageDraw.Draw(sheet).text(((i % cols) * w + 8, (i // cols) * h + 6), Path(paths[i]).stem, fill=(255, 255, 0))
    sheet.save(out)
    return out


def render(path, frame=None):
    sc = bpy.context.scene
    if frame is not None:
        sc.frame_set(frame)
    sc.render.filepath = str(path)
    sc.render.image_settings.file_format = 'PNG'
    bpy.ops.render.render(write_still=True)
    ok = os.path.exists(path)
    print(f'[render] {path} {"written" if ok else "MISSING"}', flush=True)
    return ok


def fcurve_value(idb, path, index=0, frame=1):
    ad = idb.animation_data
    if ad is None or ad.action is None:
        return None
    for ly in ad.action.layers:
        for st in ly.strips:
            for cb in st.channelbags:
                for fc in cb.fcurves:
                    if fc.data_path == path and fc.array_index == index:
                        return fc.evaluate(frame)
    return None


def count_keys(idb):
    ad = idb.animation_data
    if ad is None or ad.action is None:
        return 0
    n = 0
    for ly in ad.action.layers:
        for st in ly.strips:
            for cb in st.channelbags:
                for fc in cb.fcurves:
                    n += len(fc.keyframe_points)
    return n
