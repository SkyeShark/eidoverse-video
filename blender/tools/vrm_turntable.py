"""Turntable contact sheets (or reels) of a VRM in Blender EEVEE: outfits x clips x framings x yaws (the repo-root
vrm_turntable.py + eidoverse/vrm_turntable_scene.js, ported; tools-guides/claudesona.md, "Turntable sheets").

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tools/vrm_turntable.py -- \
        [--vrm eidoverse/assets/vrms/claude_suit_wardrobe.vrm] [--scale 0.87] [--outfits lab_coat_1961,mourning]
        [--frames face,head,chest,body] [--views 0,35,90,150,180] [--hold 12] [--size 400x520] [--anim idle]
        [--light 0.7] [--presets JSON] [--faces JSON] [--tile 8x2] [--out work/turntable/sheet.png]
        [--spin --video work/turntable/reel.mp4] [--samples 16] [--look mtoon|pbr] [--save scene.blend]

The scene is built once and KEYED: one block of --hold frames per (outfit, clip, framing, yaw), in that nesting
(yaw fastest), each with its outfit worn (wardrobe keys), its clip (an NLA strip), its yaw and camera (CONSTANT keys)
and the spring bones reset at the block's first frame, as the engine resets them (springBoneManager.reset()), then
baked over the whole run; --faces keys raw morph weights per outfit row. A sheet tiles the LAST frame of every block
(the springs settle over the block), one row per (outfit, clip, framing) and one column per yaw, or --tile CxR in
reading order. --spin renders every frame as a video instead: one eased turn per block (yaw - 25 to yaw + 360 deg).
Framing follows the character's own head height (the shots were authored on a 1.305 m head), so any rig and scale
frame the same. --outfits takes claudesona wardrobe keys (the wardrobe VRM) or '-' for any VRM; --presets adds variants
({"name": {"base": "cyclist_1892", "fold": {...}}}); "key:nofold" drops a preset's fold. --light scales the studio
(0.7 keeps white MToon cloth from blooming). Paths are relative to the repository root.
"""

import argparse
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'blender'))

SHOTS = {                          # vrm_turntable_scene.js: [fov deg, camera y, camera z, target y] (three, 1.305 m head)
    'face': (14, 1.335, 1.35, 1.33), 'head': (24, 1.42, 2.25, 1.36),
    'chest': (24, 1.15, 2.4, 1.08), 'body': (26, 1.05, 4.7, 0.92),
}
HEAD_REF = 1.305


def _lin(hexv):
    c = ((hexv >> 16) & 255, (hexv >> 8) & 255, hexv & 255)
    out = []
    for ch in c:
        s = ch / 255.0
        out.append(s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4)
    return tuple(out)


def _sun(name, pos_three, hexv, strength, angle_deg=2.0):
    x, y, z = pos_three
    d = bpy.data.lights.new(name, 'SUN')
    d.energy = strength
    d.color = _lin(hexv)
    d.angle = math.radians(angle_deg)
    ob = bpy.data.objects.new(name, d)
    bpy.context.scene.collection.objects.link(ob)
    p = Vector((x, -z, y))
    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion = (-p).to_track_quat('-Z', 'Y')
    ob.location = p
    return ob


def studio(sc, light=0.7, background=0x2c3038, floor=True):
    """the engine's neutral studio: key (0xfff1e2, 2.3) front-right, fill (0xd8e4ff, 0.75) front-left, rim (white,
    1.4) behind, a hemisphere (sky 0xe6ecf6, ground 0x3c3a40, 0.9), all x light; the floor disc (r 3 m, 0x4a4e57,
    roughness 0.9); the camera sees the flat background colour. Three's light units are irradiance, as a Blender sun's
    strength; a hemisphere of intensity I is a world of radiance I / pi."""
    L = light
    _sun('tt_key', (2.2, 3.0, 3.2), 0xfff1e2, 2.3 * L, 3.0)
    _sun('tt_fill', (-3.0, 1.6, 2.4), 0xd8e4ff, 0.75 * L, 6.0)
    _sun('tt_rim', (-0.8, 2.8, -3.4), 0xffffff, 1.4 * L, 3.0)
    wd = bpy.data.worlds.new('tt_studio')
    sc.world = wd
    wd.use_nodes = True
    nt = wd.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Generated'], sep.inputs[0])
    mr = nt.nodes.new('ShaderNodeMapRange')
    mr.inputs['From Min'].default_value, mr.inputs['From Max'].default_value = -1.0, 1.0
    nt.links.new(sep.outputs['Z'], mr.inputs['Value'])
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    nt.links.new(mr.outputs['Result'], mix.inputs['Factor'])
    mix.inputs['A'].default_value = _lin(0x3c3a40) + (1.0,)
    mix.inputs['B'].default_value = _lin(0xe6ecf6) + (1.0,)
    bg = nt.nodes.new('ShaderNodeBackground')
    bg.inputs['Strength'].default_value = 0.9 * L / math.pi
    nt.links.new(mix.outputs['Result'], bg.inputs['Color'])
    flat = nt.nodes.new('ShaderNodeBackground')
    flat.inputs['Color'].default_value = _lin(background) + (1.0,)
    lp = nt.nodes.new('ShaderNodeLightPath')
    ms = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(lp.outputs['Is Camera Ray'], ms.inputs['Fac'])
    nt.links.new(bg.outputs['Background'], ms.inputs[1])
    nt.links.new(flat.outputs['Background'], ms.inputs[2])
    out = nt.nodes.new('ShaderNodeOutputWorld')
    nt.links.new(ms.outputs['Shader'], out.inputs['Surface'])
    if floor:
        me = bpy.data.meshes.new('tt_floor')
        n = 96
        verts = [(0.0, 0.0, 0.0)] + [(3 * math.cos(2 * math.pi * i / n), 3 * math.sin(2 * math.pi * i / n), 0.0) for i in range(n)]
        me.from_pydata(verts, [], [(0, 1 + i, 1 + (i + 1) % n) for i in range(n)])
        ob = bpy.data.objects.new('tt_floor', me)
        sc.collection.objects.link(ob)
        m = bpy.data.materials.new('tt_floor')
        m.use_nodes = True
        b = m.node_tree.nodes['Principled BSDF']
        b.inputs['Base Color'].default_value = _lin(0x4a4e57) + (1.0,)
        b.inputs['Roughness'].default_value = 0.9
        me.materials.append(m)
    return wd


def render_settings(sc, w, h, samples=16):
    r, ee = sc.render, sc.eevee
    r.engine = 'BLENDER_EEVEE'
    r.resolution_x, r.resolution_y, r.resolution_percentage = w, h, 100
    r.film_transparent = False
    ee.taa_render_samples = samples
    ee.use_raytracing = True
    ee.ray_tracing_method = 'SCREEN'
    ee.ray_tracing_options.use_denoise = True
    ee.use_shadows = True
    ee.use_fast_gi = True
    ee.fast_gi_method = 'GLOBAL_ILLUMINATION'
    vs = sc.view_settings
    vs.view_transform, vs.look, vs.exposure = 'AgX', 'AgX - Base Contrast', 0.0
    r.use_motion_blur = False


def head_height(h):
    """the head bone's height (m) at rest, the scale included: the shots scale by it"""
    return (h.arm.matrix_world @ h.arm.data.bones[h.humanoid['head']].head_local).z


def shot(cam, framing, head_h, frame=None, keyed=False):
    """vrm_turntable_scene.js's framings: three's camera (0, cy, cz) looking at (0, ty, 0), fov vertical"""
    fov, cy, cz, ty = SHOTS.get(framing, SHOTS['body'])
    k = head_h / HEAD_REF
    cam.data.sensor_fit = 'VERTICAL'
    cam.data.angle = math.radians(fov)
    pos, tgt = Vector((0.0, -cz * k, cy * k)), Vector((0.0, 0.0, ty * k))
    cam.location = pos
    cam.rotation_mode = 'QUATERNION'
    cam.rotation_quaternion = (tgt - pos).to_track_quat('-Z', 'Y')
    if keyed and frame is not None:
        cam.keyframe_insert('location', frame=frame)
        cam.keyframe_insert('rotation_quaternion', frame=frame)
        cam.data.keyframe_insert('lens', frame=frame)


def _constant(idb):
    from bpy_extras import anim_utils
    ad = idb.animation_data
    if ad is None or ad.action is None:
        return
    for slot in ad.action.slots:
        cb = anim_utils.action_get_channelbag_for_slot(ad.action, slot)
        for fc in (cb.fcurves if cb else []):
            for kp in fc.keyframe_points:
                kp.interpolation = 'CONSTANT'


def tile_sheet(paths, out, cols, rows):
    """PNG tiles in reading order on a cols x rows grid (numpy + Blender's image API)"""
    ims = []
    for p in paths:
        im = bpy.data.images.load(p, check_existing=False)
        w, hh = im.size
        ims.append(np.array(im.pixels[:], dtype=np.float32).reshape(hh, w, 4))
        bpy.data.images.remove(im)
    hh, w = ims[0].shape[:2]
    big = np.zeros((rows * hh, cols * w, 4), dtype=np.float32)
    big[..., 3] = 1
    for i, a in enumerate(ims[:cols * rows]):
        r, c = divmod(i, cols)
        big[(rows - 1 - r) * hh:(rows - r) * hh, c * w:(c + 1) * w] = a
    img = bpy.data.images.new('tt_sheet', cols * w, rows * hh, alpha=True)
    img.pixels.foreach_set(big.ravel())
    img.filepath_raw = out
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)
    return out


def _clear_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)


def build(a):
    """the keyed scene; returns (scene, handle, blocks [(first frame, last frame, outfit, anim, framing, view)])"""
    from eidoblend.characters import load_vrm, play_vrma_default
    from eidoblend.characters.springs import bake_springs
    sc = bpy.context.scene
    _clear_scene()
    fps = 30
    sc.render.fps, sc.render.fps_base = fps, 1.0
    vrm = a.vrm if os.path.isabs(a.vrm) else os.path.join(REPO, a.vrm)
    base = os.path.basename(vrm)
    wardrobe_vrm = 'claude_suit_wardrobe' in base
    outfits = (a.outfits if a.outfits is not None else ('suit' if wardrobe_vrm else '-')).split(',')
    scale = a.scale if a.scale is not None else (0.87 if 'claude_suit' in base else 1.0)
    views = [float(v) for v in a.views.split(',')]
    framings = a.frames.split(',')
    anims = a.anim.split(',')
    faces = json.loads(a.faces)
    w, hgt = (int(x) for x in a.size.split('x'))
    render_settings(sc, w, hgt, a.samples)
    studio(sc, light=a.light)
    h = load_vrm(vrm)
    h.arm.scale = (scale,) * 3
    if a.look != 'mtoon':
        from eidoblend.characters.claudesona.look import set_look
        set_look(h, a.look)
    bpy.context.view_layer.update()
    H = head_height(h)
    wd = None
    if outfits[0] != '-':
        from eidoblend.characters.claudesona.wardrobe import WARDROBE, make_wardrobe
        for name, spec in json.loads(a.presets).items():
            spec = dict(spec)
            b = spec.pop('base', None)
            WARDROBE[name] = {**(WARDROBE.get(b) or {}), **spec}
        for o in outfits:
            b, _, mod = o.partition(':')
            if mod == 'nofold' and b in WARDROBE:
                WARDROBE[o] = {**WARDROBE[b], 'fold': None}
        wd = make_wardrobe(h)
    cam_d = bpy.data.cameras.new('tt_cam')
    cam_d.clip_start, cam_d.clip_end = 0.05, 100.0
    cam = bpy.data.objects.new('tt_cam', cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    blocks = []
    hold = a.hold
    b = 0
    for oi, outfit in enumerate(outfits):
        for anim in anims:
            for framing in framings:
                for view in views:
                    f0 = 1 + b * hold
                    blocks.append((f0, f0 + hold - 1, outfit, anim, framing, view, oi))
                    b += 1
    sc.frame_start, sc.frame_end = 1, blocks[-1][1]
    arm = h.arm
    arm.rotation_mode = 'XYZ'
    cur_anim, cur_outfit = None, None
    for f0, f1, outfit, anim, framing, view, oi in blocks:
        if anim != cur_anim:                   # playVRMADefault(vrm, anim, { loop: true }) at the block's start
            play_vrma_default(h, anim, t=(f0 - 1) / fps, loop=True, until=blocks[-1][1] / fps)
            cur_anim = anim
        if wd is not None and outfit != cur_outfit:
            wd.wear(outfit, frame=f0)
            cur_outfit = outfit
        if a.spin:
            for f in range(f0, f1 + 1):
                u = (f - f0) / hold
                e = u * u * (3 - 2 * u)
                arm.rotation_euler = (0.0, 0.0, math.radians(view - 25 + 385 * e))
                arm.keyframe_insert('rotation_euler', index=2, frame=f)
        else:
            arm.rotation_euler = (0.0, 0.0, math.radians(view))
            arm.keyframe_insert('rotation_euler', index=2, frame=f0)
        shot(cam, framing, H, frame=f0, keyed=True)
        if faces:                              # raw morph weights per outfit row, every other face morph 0
            raw = faces[min(len(faces) - 1, oi)] or {}
            for o in h.meshes:
                sk = o.data.shape_keys
                if not sk:
                    continue
                for kb in sk.key_blocks[1:]:
                    kb.value = float(raw.get(kb.name, 0.0))
                    kb.keyframe_insert('value', frame=f0)
    if not a.spin:
        _constant(arm)
    _constant(cam)
    _constant(cam.data)
    for o in h.meshes:
        if o.data.shape_keys:
            _constant(o.data.shape_keys)
    resets = [blk[0] for blk in blocks]
    rep = bake_springs(h, 1, sc.frame_end, resets=resets, preroll=0.0)
    print(f'[turntable] {len(blocks)} blocks of {hold} frames; springs: {rep["springs"]} springs, {rep["keys"]} keys',
          flush=True)
    return sc, h, blocks


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--vrm', default='eidoverse/assets/vrms/claude_suit_wardrobe.vrm')
    ap.add_argument('--scale', type=float, default=None)
    ap.add_argument('--outfits', default=None)
    ap.add_argument('--views', default='0,35,90,150,180')
    ap.add_argument('--frames', default='head,body')
    ap.add_argument('--hold', type=int, default=12)
    ap.add_argument('--size', default='400x520')
    ap.add_argument('--anim', default='idle')
    ap.add_argument('--light', type=float, default=0.7)
    ap.add_argument('--presets', default='{}')
    ap.add_argument('--faces', default='[]')
    ap.add_argument('--spin', action='store_true')
    ap.add_argument('--tile', default=None)
    ap.add_argument('--out', default='work/turntable/sheet.png')
    ap.add_argument('--video', default='work/turntable/turntable.mp4')
    ap.add_argument('--samples', type=int, default=16)
    ap.add_argument('--look', default='mtoon', choices=('mtoon', 'pbr'))
    ap.add_argument('--save', default=None, help='also save the keyed scene as a .blend')
    a = ap.parse_args(argv if argv is not None else (sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []))
    sc, h, blocks = build(a)
    absp = (lambda p: p if os.path.isabs(p) else os.path.join(REPO, p))
    if a.save:
        os.makedirs(os.path.dirname(absp(a.save)), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=absp(a.save), copy=True)
    if a.spin:
        out = absp(a.video)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        r = sc.render
        r.image_settings.media_type = 'VIDEO'
        r.image_settings.file_format = 'FFMPEG'
        r.ffmpeg.format, r.ffmpeg.codec = 'MPEG4', 'H264'
        r.ffmpeg.constant_rate_factor = 'HIGH'
        r.filepath = out
        bpy.ops.render.render(animation=True)
        print(f'reel: {out}', flush=True)
        return out
    out = absp(a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    tmp = os.path.splitext(out)[0] + '_tiles'
    os.makedirs(tmp, exist_ok=True)
    r = sc.render
    r.image_settings.media_type = 'IMAGE'
    r.image_settings.file_format = 'PNG'
    paths = []
    for i, (f0, f1, outfit, anim, framing, view, _oi) in enumerate(blocks):
        sc.frame_set(f1)
        p = os.path.join(tmp, f'{i:03d}_{outfit.replace(":", "-")}_{anim}_{framing}_{int(view)}.png')
        r.filepath = p
        bpy.ops.render.render(write_still=True)
        paths.append(p)
    nv = len(a.views.split(','))
    if a.tile:
        cols, rows = (int(x) for x in a.tile.split('x'))
    else:
        cols, rows = nv, math.ceil(len(paths) / nv)
    tile_sheet(paths, out, cols, rows)
    print(f'sheet: {out}  ({len(paths)} tiles on {cols}x{rows})', flush=True)
    return out


if __name__ == '__main__':
    main()
