"""Parole in liberta in Blender: the lyric layer of parole.js, posed in Deno, built and keyed in the overlay layer.

    from eidoblend.media import overlay, parole, timebase
    ov = overlay.make_overlay_layer(film_scene)
    layer = parole.make_parole(ov, 'work/<id>/parole', timing=timebase.load_lines('work/<id>/lyrics_aligned.json'),
                               add_lines=[{'text': 'UNKNOWN FORCE', 'start': 26, 'end': 33.5, 'template': 'rows',
                                           'sizeScale': 1.6}])
    overlay.render_overlay(ov, 'work/<id>/overlay')      # then the edit scene lays it over the film

parole.js runs unchanged (js/parole_export.mjs, makeParole without a GPU): its layouts, inks, atlases and every
sprite's pose per frame are the reviewed ones. Here each sprite is a plane parented to the overlay camera (the
overlay camera and three's share their local frame: looking down -Z, +Y up), its location, rotation (quaternion)
and scale keyed per frame, and its four parameters (alpha, reveal, bright, desat) keyed as object properties that
one material per atlas reads through Attribute (Object) nodes: the reveal wipe, the cell-edge fade for glows,
desaturation and brightness, as the engine's material did. The overlay scene renders in view Standard, so solid ink
lands as drawn with no inverse tone curve.

Keeping the face clear: ``spare={frame: {x, y, r}}`` (frame heights, centre origin, y up) is set before each frame
is laid out; ``face_spare(scene, camera, head_obj, bone)`` computes it from a head bone, as the film did.
"""
import json
import math
from pathlib import Path

import bpy
from bpy_extras import anim_utils
from mathutils import Vector

from . import JS
from .screens import _abspath, new_material, run_deno
from .timebase import Timebase

PARAMS = ('alpha', 'reveal', 'bright', 'desat')
_IPO = {'CONSTANT': 0, 'LINEAR': 1, 'BEZIER': 2}


# ---------------------------------------------------------------------------------------------------- the material
def _material(name, image):
    m = new_material(name)
    t = m.node_tree
    t.nodes.clear()
    N, L = t.nodes.new, t.links.new

    def node(idname, **kw):
        n = N(idname)
        for k, v in kw.items():
            setattr(n, k, v)
        return n

    def smooth(src, lo, hi):
        mr = node('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP', clamp=True)
        mr.inputs['From Min'].default_value, mr.inputs['From Max'].default_value = lo, hi
        L(src, mr.inputs['Value'])
        return mr.outputs['Result']

    def math(op, a, b=None):
        n = node('ShaderNodeMath', operation=op)
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                L(v, n.inputs[i])
        return n.outputs[0]

    def attr(nm):
        a = node('ShaderNodeAttribute', attribute_type='OBJECT', attribute_name=nm)
        return a.outputs['Fac']

    out = node('ShaderNodeOutputMaterial')
    uva = node('ShaderNodeUVMap', uv_map='atlas')
    uvq = node('ShaderNodeUVMap', uv_map='quad')
    tex = node('ShaderNodeTexImage', image=image, interpolation='Linear', extension='CLIP')
    L(uva.outputs['UV'], tex.inputs['Vector'])
    sep = node('ShaderNodeSeparateXYZ')
    L(uvq.outputs['UV'], sep.inputs['Vector'])
    px, py = sep.outputs['X'], sep.outputs['Y']
    a_tex = tex.outputs['Alpha']
    solid = smooth(a_tex, 0.55, 0.95)
    edge = math('MULTIPLY',
                math('MULTIPLY', smooth(px, 0.0, 0.04), smooth(math('SUBTRACT', 1.0, px), 0.0, 0.04)),
                math('MULTIPLY', smooth(py, 0.0, 0.06), smooth(math('SUBTRACT', 1.0, py), 0.0, 0.06)))
    keep = node('ShaderNodeMix', data_type='FLOAT')                  # mix(edge, 1, solid)
    L(solid, keep.inputs[0])
    L(edge, keep.inputs[2])
    keep.inputs[3].default_value = 1.0
    wipe = math('GREATER_THAN', attr('reveal'), px)                    # step(uv.x, reveal)
    alpha = math('MULTIPLY', math('MULTIPLY', a_tex, attr('alpha')), math('MULTIPLY', wipe, keep.outputs[0]))
    # colour: desaturate toward luminance, brighten, cap at 0.93; glows (non-solid) at 0.8
    dot = node('ShaderNodeVectorMath', operation='DOT_PRODUCT')
    L(tex.outputs['Color'], dot.inputs[0])
    dot.inputs[1].default_value = (0.2126, 0.7152, 0.0722)
    gray = node('ShaderNodeCombineXYZ')
    for i in range(3):
        L(dot.outputs['Value'], gray.inputs[i])
    des = node('ShaderNodeMix', data_type='RGBA')
    L(attr('desat'), des.inputs[0])
    L(tex.outputs['Color'], des.inputs[6])
    L(gray.outputs['Vector'], des.inputs[7])
    br = node('ShaderNodeVectorMath', operation='SCALE')
    L(des.outputs[2], br.inputs[0])
    L(attr('bright'), br.inputs['Scale'])
    cap = node('ShaderNodeVectorMath', operation='MINIMUM')
    L(br.outputs['Vector'], cap.inputs[0])
    cap.inputs[1].default_value = (0.93, 0.93, 0.93)
    glow = node('ShaderNodeVectorMath', operation='SCALE')
    L(cap.outputs['Vector'], glow.inputs[0])
    glow.inputs['Scale'].default_value = 0.8
    col = node('ShaderNodeMix', data_type='RGBA')
    L(solid, col.inputs[0])
    L(glow.outputs['Vector'], col.inputs[6])
    L(cap.outputs['Vector'], col.inputs[7])
    em = node('ShaderNodeEmission')
    L(col.outputs[2], em.inputs['Color'])
    em.inputs['Strength'].default_value = 1.0
    tr = node('ShaderNodeBsdfTransparent')
    mix = node('ShaderNodeMixShader')
    L(alpha, mix.inputs['Fac'])
    L(tr.outputs['BSDF'], mix.inputs[1])
    L(em.outputs['Emission'], mix.inputs[2])
    L(mix.outputs['Shader'], out.inputs['Surface'])
    m.surface_render_method = 'BLENDED'
    m.use_backface_culling = False
    m.use_transparency_overlap = True
    return m


# ---------------------------------------------------------------------------------------------------- sprites
def _sprite_mesh(name, rect, aw, ah):
    """A 1 x 1 plane in XY facing +Z; UV 'atlas' on its cell (the canvas has y down), UV 'quad' 0..1."""
    ax, ay, cw, ch = rect
    me = bpy.data.meshes.new(name)
    me.from_pydata([(-0.5, -0.5, 0), (0.5, -0.5, 0), (0.5, 0.5, 0), (-0.5, 0.5, 0)], [], [(0, 1, 2, 3)])
    ua = me.uv_layers.new(name='atlas')
    uq = me.uv_layers.new(name='quad')
    for li, (u, v) in enumerate(((0, 0), (1, 0), (1, 1), (0, 1))):
        ua.data[li].uv = ((ax + u * cw) / aw, 1 - (ay + (1 - v) * ch) / ah)
        uq.data[li].uv = (u, v)
    me.update()
    return me


def _bulk_keys(obj, channels, interp='LINEAR'):
    """channels: {(data_path, index): [(frame, value), …]} -> F-curves written in one go."""
    act = bpy.data.actions.new(obj.name)
    slot = act.slots.new(id_type='OBJECT', name=obj.name)
    ad = obj.animation_data_create()
    ad.action = act
    ad.action_slot = slot
    cb = anim_utils.action_ensure_channelbag_for_slot(act, slot)
    for (path, idx), keys in channels.items():
        if not keys:
            continue
        fc = cb.fcurves.new(path, index=idx)
        fc.keyframe_points.add(len(keys))
        flat = [c for f, v in keys for c in (float(f), float(v))]
        fc.keyframe_points.foreach_set('co', flat)
        fc.keyframe_points.foreach_set('interpolation', [_IPO[interp]] * len(keys))
        fc.update()
    return act


class ParoleLayer:
    def __init__(self, objects, data, out):
        self.objects, self.data, self.out = objects, data, out


def make_parole(ov, out_dir, timing, frames=None, opts=None, add_lines=(), quotes=(), preheard=(), spare=None,
                hush=None, name='parole'):
    """Lay the parole layer into an overlay (overlay.make_overlay_layer) over ``frames`` (default the overlay
    scene's range). ``timing``: lines as parole takes them (timebase.load_lines output works: {text, start, end,
    words: [{w, s, e}]}). ``opts``: styleOverrides, preheardDefault, spare. ``add_lines``: addLine specs (a
    title, an aside). ``quotes``: [{text, opts}] (opts.alignWith = an earlier quote's index). ``preheard``:
    [{line, alternatives, opts}]. ``spare`` / ``hush``: a value, or {frame: value} per frame."""
    sc = ov.scene
    tb = Timebase.of(sc)
    a, b = frames or (sc.frame_start, sc.frame_end)
    out = _abspath(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    fov = math.degrees(2 * math.atan(ov.half_h))
    job = {'out': str(out), 'width': sc.render.resolution_x, 'height': sc.render.resolution_y, 'fov': fov,
           'timing': list(timing), 'opts': opts or {}, 'addLines': list(add_lines), 'quotes': list(quotes),
           'preheard': list(preheard), 'frames': {'first': a, 'last': b, 'fps': tb.fps, 'frame0': tb.frame0}}
    if spare is not None:
        job['spare'] = {str(k): v for k, v in spare.items()} if isinstance(spare, dict) and all(
            str(k).lstrip('-').isdigit() for k in spare) else spare
    if hush is not None:
        job['hush'] = {str(k): v for k, v in hush.items()} if isinstance(hush, dict) else hush
    (out / 'job.json').write_text(json.dumps(job), encoding='utf-8')
    run_deno(JS / 'parole_export.mjs', [out / 'job.json'])
    data = json.loads((out / 'parole.json').read_text(encoding='utf-8'))

    # every sprite's track: {(gid, k): {frame: row}}
    tracks = {}
    for fr in data['frames']:
        for gid, rows in fr['live']:
            for r in rows:
                tracks.setdefault((gid, r[0]), {})[fr['f']] = r
    groups = {g['id']: g for g in data['groups']}
    # draw order: the engine drew by group order, then instance order, depth test off; EEVEE sorts blended
    # surfaces by distance, so later sprites sit a hair nearer, their position and size scaled to project the same
    ranks = {key: i for i, key in enumerate(sorted(tracks, key=lambda k: (groups[k[0]]['order'], k[0], k[1])))}
    objs = []
    mats = {}
    for (gid, k), tr in sorted(tracks.items()):
        g = groups[gid]
        if gid not in mats:
            img = bpy.data.images.load(str(out / g['atlas']), check_existing=False)
            img.name = f'{name}_{g["atlas"]}'
            img.alpha_mode = 'STRAIGHT'
            mats[gid] = _material(f'{name}_g{gid:03d}', img)
        me = _sprite_mesh(f'{name}_g{gid:03d}_{k:03d}', g['rects'][k], g['w'], g['h'])
        me.materials.append(mats[gid])
        o = bpy.data.objects.new(me.name, me)
        sc.collection.objects.link(o)
        o.parent = ov.camera
        o.rotation_mode = 'QUATERNION'
        for p in PARAMS:
            o[p] = 0.0
        eps = ranks[(gid, k)] * 1e-4
        fs = sorted(tr)
        ch = {('location', i): [] for i in range(3)}
        ch.update({('rotation_quaternion', i): [] for i in range(4)})
        ch.update({('scale', i): [] for i in range(3)})
        ch.update({(f'["{p}"]', 0): [] for p in PARAMS})
        frames_keyed = list(range(max(a, fs[0] - 1), min(b, fs[-1] + 1) + 1))
        last = tr[fs[0]]
        for f in frames_keyed:
            row = tr.get(f)
            vis = row is not None
            row = row or last
            last = row
            _k, x, y, z, qw, qx, qy, qz, sx, sy, al, rv, bt, ds = row
            s = (-z - eps) / -z                     # nearer by eps, same projection
            for i, v in enumerate((x * s, y * s, z + eps)):
                ch[('location', i)].append((f, v))
            for i, v in enumerate((qw, qx, qy, qz)):
                ch[('rotation_quaternion', i)].append((f, v))
            for i, v in enumerate((sx * s, sy * s, 1.0)):
                ch[('scale', i)].append((f, v))
            for p, v in zip(PARAMS, (al if vis else 0.0, rv, bt, ds)):
                ch[(f'["{p}"]', 0)].append((f, v))
        _bulk_keys(o, ch, 'LINEAR')
        objs.append(o)
    return ParoleLayer(objs, data, out)


def face_spare(scene, camera, arm, bone='head', lift=0.1, frames=None):
    """The singer's face per frame for the layout to avoid: {frame: {x, y, r}} (frame heights, centre origin,
    y up), from a head bone projected through the camera (the film's own recipe: radius from a point 0.24 m to
    the camera's right, x 1.15, clamped 0.06 .. 0.35; {r: 0} when the head is out of view)."""
    from bpy_extras.object_utils import world_to_camera_view
    a, b = frames or (scene.frame_start, scene.frame_end)
    r_ = scene.render
    asp = (r_.resolution_x * r_.pixel_aspect_x) / (r_.resolution_y * r_.pixel_aspect_y)
    out = {}
    keep = scene.frame_current
    for f in range(a, b + 1):
        scene.frame_set(f)
        pb = arm.pose.bones[bone]
        h = arm.matrix_world @ pb.head + Vector((0, 0, lift))
        right = camera.matrix_world.to_3x3() @ Vector((1, 0, 0))
        e = h + right * 0.24
        pa, pe = world_to_camera_view(scene, camera, h), world_to_camera_view(scene, camera, e)
        ax, ay = pa.x * 2 - 1, pa.y * 2 - 1                    # NDC
        bx, by = pe.x * 2 - 1, pe.y * 2 - 1
        in_view = abs(ax) < 1.1 and abs(ay) < 1.1 and pa.z > 0
        r = math.hypot((bx - ax) * asp / 2, (by - ay) / 2) * 1.15
        out[f] = ({'x': ax * asp / 2, 'y': ay / 2, 'r': min(0.35, max(0.06, r))} if in_view and math.isfinite(r)
                  else {'r': 0})
    scene.frame_set(keep)
    return out
