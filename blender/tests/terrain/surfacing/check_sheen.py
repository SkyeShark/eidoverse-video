"""The material's fix round of 11-20 (SURFACING_DESIGN.md 5.4, package 2), rendered as the review videos frame it:

  - the sheen: facing the sun, grass turned into a glossy white sheen like wet plastic (the sea_cliffs downland, the
    rolling_hills fields: their orbits' frames 60-96). Per shot, the render as built and the same shot with the
    ground's specular off (both materials' Specular IOR Level 0): their difference is the light the ground mirrors,
    reported over the ground pixels (mean, 95th and 99th percentiles, in 8-bit levels of the display image) and
    written 4x as an image;
  - the far material's rings (the caldera's far plain: a hard straight ring edge, lighter and bluer beyond it): per
    shot, the render as built (the rings beyond 1.5 D0 of the shot's cameras on the far material) against the same
    shot with the near material on every ring, over the pixels those rings draw: the CIELAB difference of the mean
    colours and per pixel, and the step across the ring's edge in the render as built (3 px either side).

The terrain, palette and material are the review's (surfacing_judge/shots.py: the judge's saved terrain, the
recipe's palette as the code has it now, Terrain.build with the cameras passed), the orbit is the review video's own
(surfacing_judge/video.py's orbit_path, 96 frames: the review's 8 s at 12 fps, the camera keyed along it and the sky
baked at each frame rendered, the sun where the first frame put it), and a still view is lit as the review lights it.
No plants and no rocks: the ground's material is what is judged.

    bash run_blender.sh blender/tests/terrain/surfacing/check_sheen.py --case rolling_hills --frames 1,60,76,96
        [--variants new,before] [--tag t] [--rings]
    bash run_blender.sh blender/tests/terrain/surfacing/check_sheen.py --case caldera --views aerial_far,low_oblique
        --rings
    (a GPU job: queue it with EIDO_GPU_WRAP on a shared machine, blender/tests/_where.py)

--frames: orbit frames (1..96), or --views: the recipe's still views (views.json), one kind per run. --variants, each
rendered in turn on the same terrain, sky and cameras: new (the material as the code builds it), noaa (option
specular_aa False: the scans' own roughness at every distance), before (as noaa, and the far material's specular put
back to the palette's one, as it was before 11-20). --rings: the far material's ring comparison. Writes
out/surfacing/material/sheen/<case>_<fNN or view>_<variant><tag>[_matte|_specular_x4|_near_only|
_rings_minus_near_x4].png and sheen_<case><tag>.json.
"""
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _material_scene as MS  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from eidoblend.terrain.build import surfacing as S  # noqa: E402

TN = MS.TN
OUT = os.path.join(MS.OUT, 'sheen')
VIDEO = os.path.join(TN, 'surfacing_judge', 'video.py')
ORBIT_FRAMES = 96                                   # the review's orbits: 8 s at 12 fps
_LUMA = np.array([0.2126, 0.7152, 0.0722])


def args():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []

    def opt(k, d=None):
        return a[a.index(k) + 1] if k in a else d
    fr = opt('--frames', '')
    vs = opt('--views', '')
    tag = opt('--tag', '')
    out = dict(case=opt('--case', 'rolling_hills'), frames=[int(f) for f in fr.split(',') if f],
               views=[v for v in vs.split(',') if v], tag=f'_{tag}' if tag else '',
               variants=[v for v in opt('--variants', 'new').split(',') if v], rings='--rings' in a,
               mask_only='--mask-only' in a)
    if bool(out['frames']) == bool(out['views']):
        raise SystemExit('check_sheen: give --frames or --views (one kind per run)')
    unknown = [v for v in out['variants'] if v not in VARIANTS]
    if unknown:
        raise SystemExit(f'check_sheen: variants {unknown}: {", ".join(VARIANTS)}')
    return out


# variant: (material options, the far material's specular put back to the palette's one)
VARIANTS = {'new': ({}, False), 'noaa': ({'specular_aa': False}, False), 'before': ({'specular_aa': False}, True)}


def far_palette_specular(obj, pal):
    """The far material's BSDF specular as it was before 11-20: the palette's one (unlinked)."""
    if len(obj.data.materials) < 2:
        return
    m = obj.data.materials[1]
    grp = next(n for n in m.node_tree.nodes if n.bl_idname == 'ShaderNodeGroup')
    for nd in grp.node_tree.nodes:
        if nd.bl_idname == 'ShaderNodeBsdfPrincipled':
            sock = nd.inputs['Specular IOR Level']
            for lk in list(sock.links):
                grp.node_tree.links.remove(lk)
            sock.default_value = float(pal['options']['specular'])


def video_module():
    """surfacing_judge/video.py's functions (its orbit_path, ORBIT table, shots and views modules), without running its
    main()."""
    src = open(VIDEO, encoding='utf-8').read()
    body = src.rsplit('\nmain()', 1)[0]
    ns = dict(__file__=VIDEO, __name__='surfacing_judge_video')
    exec(compile(body, VIDEO, 'exec'), ns)
    return ns


def orbit(vv, t, recipe, plan):
    """The review orbit's camera positions (n, 3), its aim and its view, as video.py's orbit() computes them."""
    v = next(w for w in plan['views'] if w['name'] == vv['ORBIT'][recipe])
    cx, cy = t.main.x0 + t.main.side / 2.0, t.main.y0 + t.main.side / 2.0
    ex, ey = v['cam'][0] + cx, v['cam'][1] + cy
    kind, dz = v['cam_z']
    ez = float(t.height_at(ex, ey)) + float(dz) if kind == 'ground' else float(dz)
    tx, ty, tz = v['aim'][0] + cx, v['aim'][1] + cy, v['aim'][2]
    rad = math.hypot(ex - tx, ey - ty)
    b0 = math.atan2(ey - ty, ex - tx)
    if kind == 'ground':
        def z_at(x, y):
            return vv['_heights'](t, x, y) + float(dz)
    else:
        def z_at(x, y):
            return np.full(np.shape(x), ez)
    path, _turned, _lift = vv['orbit_path'](t, (tx, ty, tz), rad, b0, z_at, kind == 'ground', 90.0, ORBIT_FRAMES)
    return path, (tx, ty, tz), v


def still(t, v):
    """A still view's eye and aim (world metres), as the review places it."""
    cx, cy = t.main.x0 + t.main.side / 2.0, t.main.y0 + t.main.side / 2.0
    ex, ey = v['cam'][0] + cx, v['cam'][1] + cy
    kind, dz = v['cam_z']
    ez = float(t.height_at(ex, ey)) + float(dz) if kind == 'ground' else float(dz)
    return (ex, ey, ez), (v['aim'][0] + cx, v['aim'][1] + cy, v['aim'][2])


def specular_off(obj):
    """Every material of obj with its BSDF's Specular IOR Level unlinked and 0: returns how to put them back."""
    undo = []
    for m in obj.data.materials:
        grp = next(n for n in m.node_tree.nodes if n.bl_idname == 'ShaderNodeGroup')
        for nd in grp.node_tree.nodes:
            if nd.bl_idname != 'ShaderNodeBsdfPrincipled':
                continue
            sock = nd.inputs['Specular IOR Level']
            src = sock.links[0].from_socket if sock.links else None
            undo.append((grp.node_tree, sock, src, float(sock.default_value)))
            for lk in list(sock.links):
                grp.node_tree.links.remove(lk)
            sock.default_value = 0.0
    return undo


def specular_back(undo):
    for ng, sock, src, val in undo:
        sock.default_value = val
        if src is not None:
            ng.links.new(src, sock)


def ring_mask(sc, obj, path):
    """(far, ground) per pixel, top row first: where material slot 1 (the far material) draws, and where the terrain
    does, from a one-sample emission render (slot 0 black, slot 1 white, black world, Standard view); the scene's
    settings and the object's materials put back after."""
    me = obj.data
    slots = list(me.materials)
    idx = np.empty(len(me.polygons), np.int32)            # materials.clear() resets every face's material_index
    me.polygons.foreach_get('material_index', idx)
    mats = []
    for k, c in enumerate(((0.0, 0.0, 0.0, 1.0), (1.0, 1.0, 1.0, 1.0))):
        m = bpy.data.materials.get(f'sheen_mask_{k}') or bpy.data.materials.new(f'sheen_mask_{k}')
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        em = nt.nodes.new('ShaderNodeEmission')
        em.inputs['Color'].default_value = c
        em.inputs['Strength'].default_value = 100.0       # white at any exposure the scene may carry
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        nt.links.new(em.outputs['Emission'], out.inputs['Surface'])
        mats.append(m)
    me.materials.clear()
    for m in mats[:max(1, len(slots))]:
        me.materials.append(m)
    me.polygons.foreach_set('material_index', idx)
    me.update()
    hidden = [o for o in sc.objects if o is not obj and o.type == 'MESH' and not o.hide_render and not o.is_holdout]
    for o in hidden:                                     # the sea and the lakes are not ground, and hide it
        o.is_holdout = True
    vs, im = sc.view_settings, sc.render.image_settings
    keep = (sc.world, vs.view_transform, vs.look, vs.exposure, sc.eevee.taa_render_samples, im.file_format,
            im.color_mode, sc.render.film_transparent)
    sc.world = bpy.data.worlds.get('sheen_black') or bpy.data.worlds.new('sheen_black')
    sc.world.color = (0.0, 0.0, 0.0)
    vs.view_transform, vs.look, vs.exposure = 'Standard', 'None', 0.0
    sc.eevee.taa_render_samples = 1
    sc.render.film_transparent = True
    im.file_format, im.color_mode = 'PNG', 'RGBA'
    MS.frame(sc, path)
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    px = px.reshape(h, w, 4)[::-1]
    (sc.world, vs.view_transform, vs.look, vs.exposure, sc.eevee.taa_render_samples, im.file_format, im.color_mode,
     sc.render.film_transparent) = keep
    for o in hidden:
        o.is_holdout = False
    me.materials.clear()
    for m in slots:
        me.materials.append(m)
    me.polygons.foreach_set('material_index', idx)
    me.update()
    return px[..., 0] > 0.5, px[..., 3] > 0.5


def srgb_to_lab(rgb):
    c = np.asarray(rgb, np.float64)
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = lin @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 216.0 / 24389.0, np.cbrt(xyz), (24389.0 / 27.0 * xyz + 16.0) / 116.0)
    return np.stack([116.0 * f[..., 1] - 16.0, 500.0 * (f[..., 0] - f[..., 1]), 200.0 * (f[..., 1] - f[..., 2])], -1)


def save_x4(a, path):
    d = np.clip(a * 4.0, 0.0, 1.0).astype(np.float32)
    img = bpy.data.images.new('sheen_x4', d.shape[1], d.shape[0], alpha=False)
    img.pixels.foreach_set(np.concatenate([d[::-1], np.ones(d.shape[:2] + (1,), np.float32)], -1).ravel())
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)


def ring_compare(built, near, far, ground):
    """The far rings' pixels as built against the near material on them; and the step across the rings' edge in
    the render as built: down each column where the far region begins under 4 px of near ground, the mean of the 3 px
    just inside against the 3 px just outside."""
    sel = far & ground
    if int(sel.sum()) < 50:
        return dict(pixels=int(sel.sum()))
    la, lb = srgb_to_lab(near[sel]), srgb_to_lab(built[sel])
    de = np.linalg.norm(la - lb, axis=-1)
    out = dict(pixels=int(sel.sum()), mean_colour_dE=round(float(np.linalg.norm(la.mean(0) - lb.mean(0))), 2),
               pixel_dE_median=round(float(np.median(de)), 2), pixel_dE_p90=round(float(np.percentile(de, 90)), 2),
               near_mean_srgb=[int(round(255 * float(v))) for v in near[sel].mean(0)],
               far_mean_srgb=[int(round(255 * float(v))) for v in built[sel].mean(0)])
    H, W = far.shape
    cells = []                                           # (x, y, far below): far and near ground meet between y-1, y
    for x in range(W):
        col, g = sel[:, x], ground[:, x]
        for y in range(4, H - 4):
            if col[y] != col[y - 1] and g[y - 4:y + 4].all() and (col[y:y + 4] == col[y]).all() \
                    and (col[y - 4:y] == col[y - 1]).all():
                cells.append((x, y, bool(col[y])))
    if len(cells) >= 20:
        def step(img):
            ins = np.array([img[y + 1:y + 4, x].mean(0) if below else img[y - 4:y - 1, x].mean(0)
                            for x, y, below in cells])
            outs = np.array([img[y - 4:y - 1, x].mean(0) if below else img[y + 1:y + 4, x].mean(0)
                             for x, y, below in cells])
            de = float(np.linalg.norm(srgb_to_lab(ins).mean(0) - srgb_to_lab(outs).mean(0)))
            return de, ins.mean(0), outs.mean(0)
        de, i_m, o_m = step(built)
        de_n, _i, _o = step(near)
        # the step as built, and the same columns drawn by the near material alone (the ground's own change across
        # those few pixels: what is left of the step is the ring's)
        out.update(edge_columns=len(cells), edge_step_dE=round(de, 2), edge_step_near_only_dE=round(de_n, 2),
                   edge_inside_srgb=[int(round(255 * float(v))) for v in i_m],
                   edge_outside_srgb=[int(round(255 * float(v))) for v in o_m])
    return out


def main():
    a = args()
    case = a['case']
    os.makedirs(OUT, exist_ok=True)
    vv = video_module()
    SH, V, refs = vv['SH'], vv['V'], vv['refs']
    RR = SH.rr()
    plan = V.load()[case]
    size = refs.load(plan['reference']).extent if plan.get('reference') else None
    params = plan.get('params') or SH.PARAMS.get(case)
    c0 = SH.recipe_centre(case, params)
    sc = MS.scene(samples=16)
    ov = next(w for w in plan['views'] if w['name'] == vv['ORBIT'][case])
    focus = [(c0[0] + ov['cam'][0], c0[1] + ov['cam'][1])] if ov['focus'] else None
    t, source = SH.terrain_for(case, ov['name'], size, params, focus, None)
    path, aim, ov = orbit(vv, t, case, plan)
    pal = SH.palette_now(case)
    if a['mask_only']:
        return masks_only(a, sc, t, vv, SH, plan, path, aim, ov, pal)
    t0 = time.time()
    t.build(f'{case}_sheen', palette=pal, dress=False, plants=None, cameras=[path], mask_attributes=False,
            log=MS.log)
    MS.log(f'[sheen] {case}: terrain {source}, built in {time.time() - t0:.1f} s')
    obj = t.obj
    mat = obj.data.materials[0]
    far_m = float(mat.get('eido_far_m', 0.0))
    rpal = S.resolve(pal, t.recipe)
    rec = dict(case=case, variants=a['variants'], terrain=source, far_m=far_m,
               far_material=len(obj.data.materials) > 1, shots={})
    cam = bpy.data.objects.new('sheen_cam', bpy.data.cameras.new('sheen_cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    sky_dir = os.path.join(OUT, f'_sky_{case}{a["tag"]}')
    shots = []
    if a['frames']:
        # the video's camera keyed along its path and its sky made at the first frame (the sun stays there), baked at
        # each frame this check renders
        dist = math.dist(tuple(path[0]), aim)
        cam.data.clip_start, cam.data.clip_end = max(1.0, 0.01 * dist), 4.0 * t.levels[0].side + 40000.0
        for f in range(ORBIT_FRAMES):
            SH.aim_camera(cam, tuple(path[f]), aim, ov['frame'], ov['lens'])
            vv['key'](cam, f + 1)
        sc.frame_start, sc.frame_end = 1, ORBIT_FRAMES
        sc.frame_set(1)
        bpy.context.view_layer.update()
        from eidoblend.sky import make_sky
        os.makedirs(sky_dir, exist_ok=True)
        sky = make_sky(sc, camera=cam, world='earth', hours=RR.SUN_ELEV_HOURS, clouds='cumulus', cache_dir=sky_dir,
                       quality='film', shadows=False, azimuth=RR.sun_azimuth_option(SH.sun_xy(cam)))
        rings = S.far_rings(obj, t.surface, [path], far_m=far_m)

        def setup(k):
            sky.bake(frame_start=k, frame_end=k, log=SH.quiet)
            sc.frame_set(k)
            bpy.context.view_layer.update()
        for k in a['frames']:
            shots.append((f'{case}_f{k:02d}', (lambda k=k: setup(k)), rings))
    else:
        for name in a['views']:
            v = next(w for w in plan['views'] if w['name'] == name)
            eye, tgt = still(t, v)

            def setup(v=v, eye=eye, tgt=tgt):
                dist = math.dist(eye, tgt)
                low = eye[2] - float(t.height_at(eye[0], eye[1])) < 50.0
                cam.data.clip_start = 0.1 if low else max(1.0, 0.01 * dist)
                cam.data.clip_end = 4.0 * t.levels[0].side + 40000.0
                SH.aim_camera(cam, eye, tgt, v['frame'], v['lens'])
                bpy.context.view_layer.update()
                MS.light(sc, cam, sky_dir)
            shots.append((f'{case}_{name}', setup, S.far_rings(obj, t.surface, [cam_point(eye)], far_m=far_m)))
    for i, variant in enumerate(a['variants']):
        opts, old_far = VARIANTS[variant]
        if not (i == 0 and variant == 'new'):             # the build's own material is 'new'
            t1 = time.time()
            S.apply_surface(obj, palette=pal, recipe=t.recipe, data=t.surface, cameras=[path], options=opts or None,
                            log=MS.log)
            if old_far:
                far_palette_specular(obj, rpal)
            MS.log(f'[sheen] {case} {variant}: material in {time.time() - t1:.1f} s')
        have_far = len(obj.data.materials) > 1
        render_variant(sc, obj, shots, have_far, variant + a['tag'], a['rings'], rec)
    MS.clean(sky_dir)
    p = os.path.join(OUT, f'sheen_{case}{a["tag"]}.json')
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(rec, f, indent=1)
    MS.log(f'[sheen] done -> {p}')


def masks_only(a, sc, t, vv, SH, plan, path, aim, ov, pal):
    """--mask-only: each shot's ring mask alone (<shot>_mask.png: the far rings white, the other rings black, the sky
    transparent), on the terrain built in clay (no bake, no material to compile), its far rings chosen as the
    material run chooses them (D0 from the palette and the main level's cell; the shots' cameras). For a run whose
    own masks failed; check_sheen's ring numbers then come from the saved renders and these masks."""
    t.build(f'{a["case"]}_mask', palette=None, dress=False, plants=None, cameras=None, mask_attributes=False,
            log=MS.log)
    obj = t.obj
    obj.data.materials.append(obj.data.materials[0])       # a second slot for the far rings
    far_m = S.far_distance(S.resolve(pal, t.recipe), t)
    cam = bpy.data.objects.new('mask_cam', bpy.data.cameras.new('mask_cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    for name in a['frames'] or a['views']:
        if a['frames']:
            eye, tgt, frame, lens, cams = tuple(path[name - 1]), aim, ov['frame'], ov['lens'], [path]
            shot = f'{a["case"]}_f{name:02d}'
        else:
            v = next(w for w in plan['views'] if w['name'] == name)
            eye, tgt = still(t, v)
            frame, lens, cams = v['frame'], v['lens'], [cam_point(eye)]
            shot = f'{a["case"]}_{name}'
        dist = math.dist(eye, tgt)
        low = eye[2] - float(t.height_at(eye[0], eye[1])) < 50.0
        cam.data.clip_start = 0.1 if low else max(1.0, 0.01 * dist)
        cam.data.clip_end = 4.0 * t.levels[0].side + 40000.0
        SH.aim_camera(cam, eye, tgt, frame, lens)
        bpy.context.view_layer.update()
        rings = S.far_rings(obj, None, cams, far_m=far_m)
        S._set_far_rings(obj, rings)
        far, ground = ring_mask(sc, obj, os.path.join(OUT, f'{shot}_mask.png'))
        MS.log(f'[sheen] {shot}: D0 {far_m:.0f} m, far rings {rings}: {int((far & ground).sum())} of '
               f'{int(ground.sum())} ground pixels')


def render_variant(sc, obj, shots, have_far, tag, rings_too, rec):
    """One variant's passes over the shots: as built (each shot with its own far rings), with the ground's specular
    off (what it mirrors), and, with rings_too, the near material on every ring against the far rings as built."""
    imgs = {}
    for shot, setup, rings in shots:
        name = f'{shot}_{tag}'
        setup()
        if have_far:
            S._set_far_rings(obj, rings)
        base = os.path.join(OUT, name)
        MS.frame(sc)
        secs = MS.frame(sc, base + '.png')
        far, ground = ring_mask(sc, obj, base + '_rings_mask.png')
        imgs[name] = dict(built=MS.read_png(base + '.png'), far=far, ground=ground)
        rec['shots'][name] = dict(seconds=round(secs, 2), ground_px=int(ground.sum()),
                                  far_rings=rings if have_far else [], far_ring_px=int((far & ground).sum()))
    undo = specular_off(obj)
    for shot, setup, rings in shots:
        name = f'{shot}_{tag}'
        setup()
        if have_far:
            S._set_far_rings(obj, rings)
        base = os.path.join(OUT, name)
        MS.frame(sc)
        MS.frame(sc, base + '_matte.png')
        d = imgs[name]['built'] - MS.read_png(base + '_matte.png')
        save_x4(np.abs(d), base + '_specular_x4.png')
        lum = d @ _LUMA
        gr = imgs[name]['ground']
        if gr.any():
            rec['shots'][name].update(specular_mean_levels=round(255.0 * float(lum[gr].mean()), 2),
                                      specular_p95_levels=round(255.0 * float(np.percentile(lum[gr], 95)), 2),
                                      specular_p99_levels=round(255.0 * float(np.percentile(lum[gr], 99)), 2))
    specular_back(undo)
    if rings_too and have_far:
        for shot, setup, rings in shots:
            if not rings:
                continue
            name = f'{shot}_{tag}'
            setup()
            S._set_far_rings(obj, [])
            base = os.path.join(OUT, name)
            MS.frame(sc)
            MS.frame(sc, base + '_near_only.png')
            near = MS.read_png(base + '_near_only.png')
            im = imgs[name]
            rec['shots'][name]['rings'] = ring_compare(im['built'], near, im['far'], im['ground'])
            save_x4(np.abs(im['built'] - near), base + '_rings_minus_near_x4.png')
            S._set_far_rings(obj, rings)
    for shot, _setup, _rings in shots:
        name = f'{shot}_{tag}'
        MS.log(f'[sheen] {name}: {json.dumps(rec["shots"][name])}')


def cam_point(eye):
    return np.asarray([eye], np.float64)


try:
    main()
except Exception:                                           # noqa: BLE001
    import traceback
    traceback.print_exc()
    sys.stdout.flush()
    os._exit(1)
sys.stdout.flush()
os._exit(0)
